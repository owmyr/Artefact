"""Unit tests for zero-local-install external fallback provider (Groq / Remote Ollama).

Why: Verifies that `ExternalFallbackProvider` accurately converts Gemini SDK types
to/from OpenAI chat completion schemas, and that `GeminiFallbackRouter` and `EmporioAgent`
seamlessly fall back to Groq/Ollama without local disk/model overhead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors, types

from src.agent import EmporioAgent
from src.external_fallback import ExternalFallbackProvider, STORE_TOOL_SCHEMAS
from src.llm_fallback import GeminiFallbackRouter
from src.tools import calculate_payment_options, search_catalog


def _make_api_error(code: int, message: str, status: str = "ERROR") -> errors.APIError:
    """Create a realistic `google.genai.errors.APIError` instance for testing."""
    return errors.APIError(
        code=code,
        response_json={
            "error": {
                "code": code,
                "message": message,
                "status": status,
            }
        },
    )


# ---------------------------------------------------------------------------
# 1. Provider Configuration & Resolution Tests
# ---------------------------------------------------------------------------


def test_provider_resolution_groq_defaults() -> None:
    """Verify provider configures Groq endpoint and model when GROQ_API_KEY is supplied."""
    provider = ExternalFallbackProvider(
        api_key="gsk_test_key_12345",
        host="",
    )
    assert provider.is_available() is True
    assert provider.endpoint_url == "https://api.groq.com/openai/v1/chat/completions"
    assert provider.model == "llama-3.3-70b-versatile"
    assert provider.provider_name == "groq/llama-3.3-70b-versatile"
    assert provider.headers["Authorization"] == "Bearer gsk_test_key_12345"


def test_provider_resolution_remote_ollama() -> None:
    """Verify provider configures remote Ollama endpoint when host is supplied."""
    provider = ExternalFallbackProvider(
        host="http://192.168.1.100:11434",
        model="llama3.3",
    )
    assert provider.is_available() is True
    assert provider.endpoint_url == "http://192.168.1.100:11434/v1/chat/completions"
    assert provider.model == "llama3.3"
    assert provider.provider_name == "ollama/llama3.3"
    assert "Authorization" not in provider.headers


def test_provider_unconfigured_when_no_credentials() -> None:
    """Verify provider reports is_available=False when neither key nor host is set."""
    provider = ExternalFallbackProvider(api_key="", host="")
    assert provider.is_available() is False
    assert provider.endpoint_url == ""
    assert provider.provider_name == "external/disabled"


# ---------------------------------------------------------------------------
# 2. Schema and Message Conversion Tests
# ---------------------------------------------------------------------------


def test_convert_store_tools_to_openai_schema() -> None:
    """Verify store tool callables are accurately translated to OpenAI function schemas."""
    tools = [search_catalog, calculate_payment_options]
    schemas = ExternalFallbackProvider.convert_tools_to_openai(tools)

    assert len(schemas) == 2
    names = [s["function"]["name"] for s in schemas]
    assert "search_catalog" in names
    assert "calculate_payment_options" in names
    assert "properties" in schemas[0]["function"]["parameters"]


def test_convert_contents_to_openai_messages_with_tool_roundtrip() -> None:
    """Verify conversation history containing text, tool call, and tool response is converted properly."""
    contents: list[types.Content] = [
        # 1. User asks question
        types.Content(
            role="user",
            parts=[types.Part.from_text(text="Quanto fica o Giannini GF-1D à vista?")],
        ),
        # 2. Assistant requests function call
        types.Content(
            role="model",
            parts=[
                types.Part.from_function_call(
                    name="calculate_payment_options",
                    args={"price_brl": 799.90, "has_active_promotion": False},
                )
            ],
        ),
        # 3. User passes function response
        types.Content(
            role="user",
            parts=[
                types.Part.from_function_response(
                    name="calculate_payment_options",
                    response={"pix_discount_5pct": {"final_price_pix": 759.91}},
                )
            ],
        ),
    ]

    messages = ExternalFallbackProvider.convert_contents_to_openai_messages(
        contents,
        system_instruction="Você é o assistente virtual da Empório da Música.",
    )

    assert len(messages) == 4
    # Message 0: System instruction
    assert messages[0]["role"] == "system"
    assert "Empório da Música" in messages[0]["content"]

    # Message 1: User message
    assert messages[1]["role"] == "user"
    assert "Giannini" in messages[1]["content"]

    # Message 2: Assistant tool call
    assert messages[2]["role"] == "assistant"
    assert "tool_calls" in messages[2]
    assert messages[2]["tool_calls"][0]["function"]["name"] == "calculate_payment_options"

    # Message 3: Tool response
    assert messages[3]["role"] == "tool"
    assert messages[3]["name"] == "calculate_payment_options"
    parsed_resp = json.loads(messages[3]["content"])
    assert parsed_resp["pix_discount_5pct"]["final_price_pix"] == 759.91


def test_convert_openai_response_to_gemini_types() -> None:
    """Verify OpenAI chat completion JSON is converted to google.genai.types.GenerateContentResponse."""
    # Text response
    raw_text_json = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "O valor no PIX é R$ 759,91 com 5% de desconto.",
                }
            }
        ]
    }
    resp_text = ExternalFallbackProvider.convert_openai_response_to_gemini(raw_text_json)
    assert isinstance(resp_text, types.GenerateContentResponse)
    assert "R$ 759,91" in resp_text.candidates[0].content.parts[0].text

    # Tool call response
    raw_tc_json = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_calc",
                            "type": "function",
                            "function": {
                                "name": "calculate_payment_options",
                                "arguments": json.dumps({"price_brl": 1200.0}),
                            },
                        }
                    ],
                }
            }
        ]
    }
    resp_tc = ExternalFallbackProvider.convert_openai_response_to_gemini(raw_tc_json)
    fc = resp_tc.candidates[0].content.parts[0].function_call
    assert fc.name == "calculate_payment_options"
    assert fc.args["price_brl"] == 1200.0


def test_convert_openai_response_with_dict_arguments() -> None:
    """Verify pre-parsed dict tool arguments in OpenAI-compatible responses do not raise UnboundLocalError."""
    raw_dict_tc_json = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_dict_1",
                            "type": "function",
                            "function": {
                                "name": "search_catalog",
                                "arguments": {"query": "violão", "max_price": 1000.0},
                            },
                        }
                    ],
                }
            }
        ]
    }
    resp = ExternalFallbackProvider.convert_openai_response_to_gemini(raw_dict_tc_json)
    fc = resp.candidates[0].content.parts[0].function_call
    assert fc.name == "search_catalog"
    assert fc.args["query"] == "violão"
    assert fc.args["max_price"] == 1000.0


def test_convert_contents_unique_tool_call_ids_for_repeated_tool() -> None:
    """Verify multiple calls to the same tool in a single turn get distinct tool_call_ids."""
    contents: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text="Compare os pedidos 8 e 11.")],
        ),
        types.Content(
            role="model",
            parts=[
                types.Part.from_function_call(
                    name="get_order_status",
                    args={"order_id": 8, "customer_identifier": "Pedro Oliveira"},
                ),
                types.Part.from_function_call(
                    name="get_order_status",
                    args={"order_id": 11, "customer_identifier": "Pedro Oliveira"},
                ),
            ],
        ),
        types.Content(
            role="user",
            parts=[
                types.Part.from_function_response(
                    name="get_order_status",
                    response={"order_id": 8, "status": "shipped"},
                ),
                types.Part.from_function_response(
                    name="get_order_status",
                    response={"order_id": 11, "status": "delivered"},
                ),
            ],
        ),
    ]

    messages = ExternalFallbackProvider.convert_contents_to_openai_messages(contents)
    assistant_msg = messages[1]
    tool_msg_1 = messages[2]
    tool_msg_2 = messages[3]

    call_id_1 = assistant_msg["tool_calls"][0]["id"]
    call_id_2 = assistant_msg["tool_calls"][1]["id"]
    assert call_id_1 != call_id_2
    assert tool_msg_1["tool_call_id"] == call_id_1
    assert tool_msg_2["tool_call_id"] == call_id_2


# ---------------------------------------------------------------------------
# 3. Router Fallback to External Provider Tests
# ---------------------------------------------------------------------------


def test_router_falls_back_to_external_provider_when_all_gemini_fail() -> None:
    """Verify router invokes external provider when every Gemini model in cascade fails."""
    mock_gemini_client = MagicMock()
    mock_external_provider = MagicMock()
    mock_external_provider.is_available.return_value = True
    mock_external_provider.provider_name = "groq/llama-3.3-70b-versatile"

    expected_resp = types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(
                    role="model",
                    parts=[types.Part.from_text(text="Resposta via Groq Fallback.")],
                )
            )
        ]
    )
    mock_external_provider.generate_content.return_value = expected_resp

    test_cascade = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
    router = GeminiFallbackRouter(
        client=mock_gemini_client,
        models=test_cascade,
        external_provider=mock_external_provider,
    )

    # Both Gemini models raise 429
    def side_effect(*, model: str, contents: Any, config: Any) -> Any:
        raise _make_api_error(429, "Rate limit exceeded (Free Tier exhausted).")

    mock_gemini_client.models.generate_content.side_effect = side_effect

    contents = [types.Content(role="user", parts=[types.Part.from_text(text="Olá!")])]
    config = types.GenerateContentConfig(temperature=0.1)

    response, model_used, fallback_events = router.generate_with_fallback(
        contents=contents,
        config=config,
    )

    assert response == expected_resp
    assert model_used == "groq/llama-3.3-70b-versatile"
    # 2 Gemini 429 events + 1 external provider success event == 3 events
    assert len(fallback_events) == 3
    assert fallback_events[-1]["action"] == "external_provider_succeeded"
    assert fallback_events[-1]["model"] == "groq/llama-3.3-70b-versatile"
    mock_external_provider.generate_content.assert_called_once_with(
        contents=contents, config=config
    )


# ---------------------------------------------------------------------------
# 4. End-to-End Stateful ReAct Agent Loop with External Provider
# ---------------------------------------------------------------------------


def test_agent_executes_react_tool_with_external_provider(tmp_path: Path) -> None:
    """Verify EmporioAgent executes multi-iteration ReAct tool loop backed by external provider."""
    mock_gemini_client = MagicMock()
    mock_external_provider = MagicMock()
    mock_external_provider.is_available.return_value = True
    mock_external_provider.provider_name = "groq/llama-3.3-70b-versatile"

    # All Gemini models disabled/fail
    mock_gemini_client.models.generate_content.side_effect = _make_api_error(
        429, "Daily quota exhausted."
    )

    # External provider returns function call on iter 1, final text on iter 2
    fc_part = types.Part.from_function_call(
        name="calculate_payment_options",
        args={"price_brl": 1000.0, "has_active_promotion": False},
    )
    resp_step1 = types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[fc_part]))]
    )

    text_part = types.Part.from_text(
        text="No PIX à vista o valor é R$ 950,00 (5% de desconto) ou em até 10x de R$ 100,00 sem juros."
    )
    resp_step2 = types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[text_part]))]
    )

    mock_external_provider.generate_content.side_effect = [resp_step1, resp_step2]

    test_db = tmp_path / "test_ext_agent.db"
    router = GeminiFallbackRouter(
        client=mock_gemini_client,
        models=["gemini-2.5-flash"],
        external_provider=mock_external_provider,
    )
    agent = EmporioAgent(router=router, db_path=test_db)

    result = agent.chat("Como posso pagar um violão de 1000 reais?", session_id="ext_session")

    assert "R$ 950,00" in result["response"]
    assert result["model_used"] == "groq/llama-3.3-70b-versatile"
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0]["name"] == "calculate_payment_options"
    assert result["tool_calls"][0]["args"]["price_brl"] == 1000.0
    assert mock_external_provider.generate_content.call_count == 2
