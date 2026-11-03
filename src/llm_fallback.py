"""Gemini Free-Tier Multi-Model Fallback Router for Empório da Música.

Why: Guarantees high availability on Google AI Studio Free Tier quotas by
routing requests across a prioritized cascade of 5 Gemini models. Automatically
tracks per-model cooldowns (60s for RPM/TPM limits, 3600s for daily RPD exhaustion,
30s after transient server overload) and permanently disables unsupported models,
ensuring seamless mid-turn failover without losing ReAct tool-execution progress.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from google import genai
from google.genai import errors, types

from src import config as settings

logger = logging.getLogger(__name__)

_DAILY_QUOTA_INDICATORS: tuple[str, ...] = ("perday", "rpd", "daily")


class GeminiFallbackRouter:
    """Multi-model fallback router with per-model cooldowns and telemetry logging.

    Why: Wraps `genai.Client.models.generate_content` with deterministic retry and
    cascade rotation logic so rate limits (HTTP 429) or transient server errors
    (HTTP 500/503/504) never crash a customer support conversation turn.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        models: Optional[list[str]] = None,
        client: Optional[genai.Client] = None,
    ) -> None:
        """Initialize the Gemini client, model cascade, and cooldown tracking state.

        Why: Allows dependency injection of a mock client or custom model list in unit
        tests while defaulting to `settings.GEMINI_API_KEY` and `settings.GEMINI_MODEL_CASCADE`.
        """
        resolved_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        # Use a placeholder string if no key is configured yet so client instantiation
        # succeeds during offline unit tests that mock `client.models.generate_content`.
        self.api_key: str = resolved_key or "UNSET_GEMINI_API_KEY"
        self.client: genai.Client = client or genai.Client(api_key=self.api_key)
        self.models: list[str] = list(
            models if models is not None else settings.GEMINI_MODEL_CASCADE
        )
        self.model_cooldown_until: dict[str, float] = {}
        self.disabled_models: set[str] = set()

    def _get_candidate_models(self) -> list[str]:
        """Return ordered candidate models not in `disabled_models` and not on cooldown.

        Why: If all non-disabled models are currently on cooldown, selects the model
        with the earliest expiring cooldown and sleeps until it is ready (capped at 5s)
        so the router can still attempt generation rather than failing immediately.
        """
        enabled_models = [m for m in self.models if m not in self.disabled_models]
        if not enabled_models:
            return []

        now = time.monotonic()
        ready_models = [
            m
            for m in enabled_models
            if self.model_cooldown_until.get(m, 0.0) <= now
        ]
        if ready_models:
            return ready_models

        # All enabled models are on cooldown: find the earliest expiring cooldown
        earliest_model = min(
            enabled_models,
            key=lambda m: self.model_cooldown_until.get(m, 0.0),
        )
        wait_seconds = max(
            0.0, self.model_cooldown_until.get(earliest_model, 0.0) - now
        )
        sleep_duration = min(wait_seconds, 5.0)
        if sleep_duration > 0:
            logger.info(
                "All candidate models on cooldown. Sleeping %.2fs for earliest model '%s'.",
                sleep_duration,
                earliest_model,
            )
            time.sleep(sleep_duration)

        # Return enabled models ordered with earliest_model first, followed by remaining cascade
        remaining = [m for m in enabled_models if m != earliest_model]
        return [earliest_model, *remaining]

    @staticmethod
    def _extract_error_code(exc: Exception) -> int:
        """Extract HTTP status code from a `google.genai.errors.APIError` or generic exception.

        Why: Handles both standard `APIError.code` attributes and string-formatted status codes.
        """
        code = getattr(exc, "code", None)
        if isinstance(code, int):
            return code
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            return status_code
        msg = str(exc)
        for candidate in (429, 503, 500, 504, 404, 400):
            if str(candidate) in msg:
                return candidate
        return 500

    @staticmethod
    def _is_daily_quota_error(exc: Exception) -> bool:
        """Check whether an HTTP 429 error indicates daily quota exhaustion (RPD/PerDay).

        Why: Distinguishes per-minute rate limits (60s cooldown) from daily quota
        exhaustion (3600s cooldown) so exhausted models are not repeatedly polled.
        """
        full_text = f"{exc} {getattr(exc, 'message', '')} {getattr(exc, 'details', '')}".lower()
        return any(indicator in full_text for indicator in _DAILY_QUOTA_INDICATORS)

    def get_health_status(self) -> list[dict[str, Any]]:
        """Return real-time health and cooldown telemetry for all models in the cascade.

        Why: Powers the Streamlit sidebar and CLI telemetry panels with deterministic
        per-model status (`ready`, `cooldown`, `disabled`) and remaining cooldown seconds.
        """
        now = time.monotonic()
        status_list: list[dict[str, Any]] = []
        for idx, model_name in enumerate(self.models):
            cooldown_until = self.model_cooldown_until.get(model_name, 0.0)
            remaining = max(0.0, cooldown_until - now)
            if model_name in self.disabled_models:
                state = "disabled"
            elif remaining > 0:
                state = "cooldown"
            else:
                state = "ready"

            status_list.append(
                {
                    "priority": idx + 1,
                    "model": model_name,
                    "state": state,
                    "cooldown_remaining_s": round(remaining, 1),
                }
            )
        return status_list

    def generate_with_fallback(
        self,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> tuple[types.GenerateContentResponse, str, list[dict[str, Any]]]:
        """Execute `generate_content` across the prioritized model cascade with automatic failover.

        Why: Ensures every LLM call in the manual ReAct loop is resilient to Free-Tier
        rate limits (429), transient server overload (500/503/504), and model deprecations (404/400).

        Args:
            contents: Sanitized list of `types.Content` conversation turns.
            config: `types.GenerateContentConfig` with system instruction and tools.

        Returns:
            A 3-tuple of `(response, model_used, fallback_events)`.

        Raises:
            RuntimeError: If all models in the cascade fail or are disabled.
        """
        fallback_events: list[dict[str, Any]] = []
        candidates = self._get_candidate_models()

        if not candidates:
            raise RuntimeError(
                "Nenhum modelo Gemini disponível na cascata (todos os modelos estão desativados)."
            )

        last_exception: Optional[Exception] = None

        for model_name in candidates:
            # Skip if placed on cooldown or disabled during this turn's loop
            if model_name in self.disabled_models:
                continue
            now = time.monotonic()
            if self.model_cooldown_until.get(model_name, 0.0) > now and len(candidates) > 1:
                continue

            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                return response, model_name, fallback_events

            except errors.APIError as exc:
                last_exception = exc
                code = self._extract_error_code(exc)
                err_msg = str(exc)

                # Case 1: HTTP 429 RESOURCE_EXHAUSTED (Rate Limit / Quota Exceeded)
                if code == 429:
                    is_daily = self._is_daily_quota_error(exc)
                    cooldown_s = 3600.0 if is_daily else 60.0
                    self.model_cooldown_until[model_name] = time.monotonic() + cooldown_s
                    reason = "daily_quota_exhausted" if is_daily else "rate_limit_exceeded"
                    event = {
                        "model": model_name,
                        "status_code": 429,
                        "reason": reason,
                        "action": "cooldown_and_fallback",
                        "cooldown_seconds": cooldown_s,
                        "retried_same_model": False,
                        "error": err_msg,
                    }
                    fallback_events.append(event)
                    logger.warning(
                        "Model '%s' hit HTTP 429 (%s). Cooldown %.0fs. Falling back to next model.",
                        model_name,
                        reason,
                        cooldown_s,
                    )
                    continue

                # Case 2: HTTP 503 UNAVAILABLE, 500 INTERNAL, or 504 DEADLINE_EXCEEDED
                if code in (503, 500, 504):
                    logger.warning(
                        "Model '%s' hit HTTP %d. Sleeping 1.5s and retrying once on same model.",
                        model_name,
                        code,
                    )
                    time.sleep(1.5)
                    try:
                        response = self.client.models.generate_content(
                            model=model_name,
                            contents=contents,
                            config=config,
                        )
                        return response, model_name, fallback_events
                    except errors.APIError as retry_exc:
                        last_exception = retry_exc
                        retry_code = self._extract_error_code(retry_exc)
                        cooldown_s = 30.0
                        self.model_cooldown_until[model_name] = time.monotonic() + cooldown_s
                        event = {
                            "model": model_name,
                            "status_code": retry_code,
                            "reason": "server_overloaded_or_unavailable",
                            "action": "retry_failed_cooldown_and_fallback",
                            "cooldown_seconds": cooldown_s,
                            "retried_same_model": True,
                            "error": str(retry_exc),
                        }
                        fallback_events.append(event)
                        logger.warning(
                            "Model '%s' failed retry with HTTP %d. Cooldown %.0fs. Falling back.",
                            model_name,
                            retry_code,
                            cooldown_s,
                        )
                        continue

                # Case 3: HTTP 404 NOT_FOUND or 400 INVALID_ARGUMENT
                if code in (404, 400):
                    self.disabled_models.add(model_name)
                    event = {
                        "model": model_name,
                        "status_code": code,
                        "reason": "model_not_found_or_unsupported",
                        "action": "disable_model_and_fallback",
                        "cooldown_seconds": None,
                        "retried_same_model": False,
                        "error": err_msg,
                    }
                    fallback_events.append(event)
                    logger.error(
                        "Model '%s' hit HTTP %d. Added to disabled_models. Falling back.",
                        model_name,
                        code,
                    )
                    continue

                # Any other unexpected APIError: apply short 30s cooldown and fall back
                cooldown_s = 30.0
                self.model_cooldown_until[model_name] = time.monotonic() + cooldown_s
                event = {
                    "model": model_name,
                    "status_code": code,
                    "reason": "unexpected_api_error",
                    "action": "cooldown_and_fallback",
                    "cooldown_seconds": cooldown_s,
                    "retried_same_model": False,
                    "error": err_msg,
                }
                fallback_events.append(event)
                logger.warning(
                    "Model '%s' hit unexpected APIError (%d). Cooldown %.0fs. Falling back.",
                    model_name,
                    code,
                    cooldown_s,
                )
                continue

        raise RuntimeError(
            f"Todos os modelos Gemini na cascata falharam. Eventos de fallback: {len(fallback_events)}. "
            f"Último erro: {last_exception}"
        ) from last_exception
