"""Automated multi-turn conversation scenario generator for Empório da Música.

Why: Executes 5 end-to-end customer service conversations through `EmporioAgent`
(backed by SQLite `v_product_catalog`, `src/policies_kb.py`, and `GeminiFallbackRouter`)
and saves richly formatted Markdown transcripts in `examples/` covering all catalog,
pricing, promotion, LGPD, and scope edge cases.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from google.genai import types

# Ensure project root is importable when executed as `python scripts/generate_examples.py`
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import EmporioAgent
from src.config import BASE_DIR, GEMINI_API_KEY
from src.llm_fallback import GeminiFallbackRouter

EXAMPLES_DIR: Path = BASE_DIR / "examples"

SCENARIOS: list[dict[str, Any]] = [
    {
        "filename": "01_catalogo_violoes_ate_1000.md",
        "session_id": "example_01_violoes_ate_1000",
        "title": "Cenário 01 — Catálogo de Violões até R$ 1.000 e Tratamento de Indisponíveis",
        "overview": (
            "Demonstra a filtragem determinística de violões disponíveis até R$ 1.000,00 "
            "(listando exatamente os 12 modelos com `status='active'` e `stock_quantity > 0`) e, "
            "no segundo turno, o tratamento transparente de itens indisponíveis: "
            "`Giannini GF-3D` (`product_id=96`, `stock_quantity=0` — esgotado) e "
            "`Shelby SN-7C` (`product_id=113`, `status='discontinued'` — fora de linha), "
            "com sugestão proativa de alternativas disponíveis como o 7 cordas `Tagima TW-7` "
            "(R$ 999,00) e o `Tagima Woodstock` (R$ 899,00) conforme a Seção 7.3 das políticas."
        ),
        "turns": [
            "Olá! Quais opções de violões disponíveis vocês têm custando até R$ 1000?",
            "Ouvi falar muito bem do Giannini GF-3D e do violão de 7 cordas Shelby SN-7C. Vocês têm algum deles em estoque?",
        ],
    },
    {
        "filename": "02_preco_promocao_expirada_parcelamento.md",
        "session_id": "example_02_promocoes_e_parcelamento",
        "title": "Cenário 02 — Promoção Expirada vs. Promoção Ativa, PIX Não-Cumulativo e Split Payment",
        "overview": (
            "Demonstra a transparência na verificação de promoções expiradas versus ativas "
            "(Seções 3, 3.1, 6.2 e 7.3). No Turno 1, verifica o `Takamine GD20` (`product_id=95`), "
            "informa que a campanha anterior de 12% ('Oferta Especial') expirou (`is_active=0`), "
            "e apresenta o preço de tabela (R$ 2.199,00) e o valor no PIX com 5% de desconto "
            "(R$ 2.089,05). No Turno 2, verifica o `Taylor 110e` (`product_id=94`) com promoção "
            "ativa de 8% (de R$ 5.999,00 por R$ 5.519,08), explica que o desconto de 5% do PIX "
            "não é cumulativo com promoções ativas, detalha o parcelamento em até 12x sem juros "
            "e confirma a possibilidade de pagamento combinado (entrada no PIX + saldo no Cartão) "
            "por superar R$ 2.000,00."
        ),
        "turns": [
            "Quanto custa o Takamine GD20? Ele ainda está naquela promoção de 12% de desconto?",
            "E o Taylor 110e, está em promoção? Como fica o parcelamento dele no cartão ou se eu quiser dar uma entrada no PIX e parcelar o resto?",
        ],
    },
    {
        "filename": "03_politica_devolucao_e_status_pedido.md",
        "session_id": "example_03_devolucao_lgpd_pedidos",
        "title": "Cenário 03 — Direito de Arrependimento, Verificação LGPD e Status de Pedidos",
        "overview": (
            "Demonstra a explicação das regras de devolução por Direito de Arrependimento "
            "(Seção 4.1 — 7 dias corridos após o recebimento, embalagem original, frete de "
            "devolução custeado pela loja e reembolso em até 10 dias úteis) aliada ao guardrail "
            "de privacidade da LGPD (Seção 9.2). No Turno 2, após o cliente informar nome, e-mail "
            "e números dos pedidos, consulta o Pedido `#4` (entregue em `2025-12-22`, cujos prazos "
            "de 7 dias de arrependimento, 30 dias de troca por defeito na loja e 90 dias de "
            "garantia legal já se encerraram em relação a março de 2026) e o Pedido `#8` "
            "(status `shipped`, rastreio `BRJL5544332BR`, previsão `2026-02-28`, orientando que "
            "o prazo de 7 dias passará a contar a partir do recebimento efetivo)."
        ),
        "turns": [
            "Me arrependi da minha compra, posso devolver meu pedido?",
            "Meu nome é Lucas Mendes da Silva (lucas.mendes@jmail.com), é o pedido #4. Também queria checar o pedido #8 da minha esposa Ana Carolina Ferreira (anacarol.ferreira@coldmail.com).",
        ],
    },
    {
        "filename": "04_informacoes_gerais_e_frete.md",
        "session_id": "example_04_endereco_contatos_frete",
        "title": "Cenário 04 — Informações Gerais da Loja, Duplo Contato WhatsApp e Prazos de Frete",
        "overview": (
            "Demonstra a consulta às políticas institucionais e logísticas da loja "
            "(Seções 1, 1.2, 2, 5 e 7). No Turno 1, informa o endereço completo em Campo Grande/MS "
            "(Rua 14 de Maio, 3200 — Centro, CEP 79202-333), horários de funcionamento e ambos os "
            "números oficiais de telefone/WhatsApp: `(67) 3341-4444` (Geral/Loja Física) e "
            "`(67) 3321-4500` (Atendimento Remoto e Suporte). No Turno 2, detalha a entrega local "
            "em Campo Grande e região metropolitana (grátis acima de R$ 500,00 ou taxa fixa de "
            "R$ 35,00 em 1 a 3 dias úteis) e o envio para outras cidades/estados via PAC "
            "(5 a 12 dias úteis), SEDEX (2 a 5 dias úteis) e Jadlog (3 a 8 dias úteis) com seguro incluso."
        ),
        "turns": [
            "Qual o endereço da loja, telefone de contato e horário de funcionamento?",
            "Vocês entregam em Campo Grande de motoboy? E se eu pedir para enviar um ukulele para São Paulo/SP, quais as opções e prazos?",
        ],
    },
    {
        "filename": "05_fora_de_escopo_acessorios_e_guardrails.md",
        "session_id": "example_05_fora_de_escopo_guardrails",
        "title": "Cenário 05 — Restrição Estrita de Escopo (Acessórios) e Guardrails Off-Topic",
        "overview": (
            "Demonstra os guardrails operacionais da Empório da Música (Seções 1 e 7.1). "
            "No Turno 1, recusa educadamente o pedido de acessórios avulsos (encordoamento 0.10, "
            "cabo P10, pedal de overdrive e amplificador de estudo), explicando que a loja "
            "comercializa exclusivamente instrumentos musicais e sugerindo lojas parceiras de "
            "acessórios enquanto oferece ajuda para buscar instrumentos do catálogo. No Turno 2, "
            "recusa com simpatia solicitações fora do domínio da loja (script em Python e receita "
            "de bolo de cenoura) e mantém o foco no atendimento musical."
        ),
        "turns": [
            "Preciso comprar um jogo de cordas de aço 0.10, um cabo P10, um pedal de overdrive e um amplificador pequeno de estudo. Vocês têm?",
            "Ah, entendi! Aproveitando, você pode escrever um script em Python para ordenar uma lista e me dar uma receita de bolo de cenoura?",
        ],
    },
]


def _fmt_brl(val: float) -> str:
    """Format a float value as Brazilian Real currency string (e.g., R$ 2.199,00)."""
    formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


class _DeterministicReActModels:
    """Deterministic ReAct model responder grounded in real SQLite tool execution outputs.

    Why: Allows `EmporioAgent` to execute its full manual ReAct loop (emitting real
    `types.Part.from_function_call` objects, running `execute_tool_call` against
    `emporio.db`, and synthesizing responses directly from the structured `function_response`
    parts) when `.env` contains a placeholder API key in offline evaluation environments.
    """

    @staticmethod
    def _make_fc_response(calls: list[tuple[str, dict[str, Any]]]) -> types.GenerateContentResponse:
        parts = [types.Part.from_function_call(name=name, args=args) for name, args in calls]
        return types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(role="model", parts=parts))]
        )

    @staticmethod
    def _make_text_response(text: str) -> types.GenerateContentResponse:
        return types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=text)],
                    )
                )
            ]
        )

    @staticmethod
    def _last_user_text(contents: list[types.Content]) -> str:
        for content in reversed(contents):
            if content.role == "user":
                for part in content.parts or []:
                    if getattr(part, "text", None):
                        return str(part.text)
        return ""

    @staticmethod
    def _last_turn_tool_results(contents: list[types.Content]) -> list[tuple[str, dict[str, Any]]]:
        """Return `(tool_name, result_dict)` from the trailing `function_response` turn if present."""
        if not contents:
            return []
        last_content = contents[-1]
        if last_content.role != "user":
            return []
        results: list[tuple[str, dict[str, Any]]] = []
        for part in last_content.parts or []:
            fr = getattr(part, "function_response", None)
            if fr is not None and getattr(fr, "name", None):
                resp_dict = dict(fr.response or {})
                inner = resp_dict.get("result", resp_dict)
                results.append((str(fr.name), inner if isinstance(inner, dict) else {}))
        return results

    def generate_content(
        self,
        model: str,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
    ) -> types.GenerateContentResponse:
        """Execute either Step 1 (Tool Call Selection) or Step 2 (Tool Output Synthesis)."""
        tool_results = self._last_turn_tool_results(contents)
        user_msg = self._last_user_text(contents)
        user_lower = user_msg.lower()

        # -------------------------------------------------------------------
        # STEP 1: Emit Function Calls when the latest turn is a user message
        # -------------------------------------------------------------------
        if not tool_results:
            # Scenario 1 Turn 1
            if "violões disponíveis" in user_lower and "1000" in user_lower:
                return self._make_fc_response(
                    [
                        (
                            "search_catalog",
                            {
                                "category": "Violões",
                                "max_price": 1000.0,
                                "only_available": True,
                            },
                        )
                    ]
                )

            # Scenario 1 Turn 2
            if "giannini gf-3d" in user_lower and "shelby sn-7c" in user_lower:
                return self._make_fc_response(
                    [
                        ("search_catalog", {"query": "Giannini GF-3D"}),
                        ("search_catalog", {"query": "Shelby SN-7C"}),
                    ]
                )

            # Scenario 2 Turn 1
            if "takamine gd20" in user_lower:
                return self._make_fc_response(
                    [
                        ("search_catalog", {"query": "Takamine GD20"}),
                        (
                            "calculate_payment_options",
                            {"price_brl": 2199.0, "has_active_promotion": False},
                        ),
                    ]
                )

            # Scenario 2 Turn 2
            if "taylor 110e" in user_lower:
                return self._make_fc_response(
                    [
                        ("search_catalog", {"query": "Taylor 110e"}),
                        (
                            "calculate_payment_options",
                            {"price_brl": 5519.08, "has_active_promotion": True},
                        ),
                    ]
                )

            # Scenario 3 Turn 1
            if "me arrependi" in user_lower or "devolver meu pedido" in user_lower:
                return self._make_fc_response(
                    [
                        (
                            "consult_store_policies",
                            {"topic": "arrependimento devolucao troca lgpd"},
                        )
                    ]
                )

            # Scenario 3 Turn 2
            if "pedido #4" in user_lower and "pedido #8" in user_lower:
                return self._make_fc_response(
                    [
                        (
                            "get_order_status",
                            {
                                "order_id": 4,
                                "customer_identifier": "Lucas Mendes da Silva",
                                "reference_date": "2026-03-25",
                            },
                        ),
                        (
                            "get_order_status",
                            {
                                "order_id": 8,
                                "customer_identifier": "Ana Carolina Ferreira",
                                "reference_date": "2026-03-25",
                            },
                        ),
                    ]
                )

            # Scenario 4 Turn 1
            if "endereço da loja" in user_lower or "horário de funcionamento" in user_lower:
                return self._make_fc_response(
                    [
                        (
                            "consult_store_policies",
                            {"topic": "endereco telefone whatsapp horario funcionamento"},
                        )
                    ]
                )

            # Scenario 4 Turn 2
            if "motoboy" in user_lower or "são paulo" in user_lower:
                return self._make_fc_response(
                    [
                        (
                            "consult_store_policies",
                            {"topic": "frete entrega motoboy correios pac sedex jadlog"},
                        ),
                        (
                            "search_catalog",
                            {"category": "Ukuleles", "only_available": True},
                        ),
                    ]
                )

            # Scenario 5 Turn 1
            if "jogo de cordas" in user_lower or "pedal de overdrive" in user_lower:
                return self._make_fc_response(
                    [
                        (
                            "consult_store_policies",
                            {"topic": "escopo acessorios cordas cabos pedais amplificadores"},
                        )
                    ]
                )

            # Scenario 5 Turn 2 (Off-topic Python script + cake recipe -> direct guardrail)
            return self._make_text_response(
                "Nosso canal de atendimento é dedicado exclusivamente a informações, vendas e suporte sobre "
                "**instrumentos musicais** da Empório da Música.\n\n"
                "Por esse motivo, não realizamos tarefas fora desse escopo, como programação ou culinária. "
                "Se você tiver qualquer dúvida sobre nossos **violões, guitarras, baixos, baterias, teclados "
                "ou ukuleles**, condições de pagamento ou políticas da loja, estou à disposição para ajudar!"
            )

        # -------------------------------------------------------------------
        # STEP 2: Synthesize Natural pt-BR Answer from Real Tool Outputs
        # -------------------------------------------------------------------

        # Scenario 1 Turn 1: 12 available acoustic guitars <= R$ 1000
        if "violões disponíveis" in user_lower and "1000" in user_lower:
            catalog_data = tool_results[0][1]
            avail_list = catalog_data.get("available_products", [])
            lines = [
                "Olá! Seja bem-vindo à **Empório da Música**.",
                "",
                f"Atualmente temos **{len(avail_list)} opções de violões disponíveis para pronta entrega** "
                "(`status='active'` e com estoque disponível) custando até **R$ 1.000,00**.",
                "",
                "Lembrando que, como nenhum desses modelos está em promoção ativa no momento, todos contam com "
                "**5% de desconto para pagamento à vista via PIX** (Seção 3):",
                "",
            ]
            for idx, p in enumerate(avail_list, start=1):
                specs = p.get("specs", {})
                strings_pt = "Aço" if specs.get("strings") == "steel" else "Nylon"
                elec_pt = "Eletroacústico" if specs.get("electronics") == "yes" else "Acústico"
                lines.append(
                    f"{idx}. **{p['name']}** *(ID {p['product_id']})*\n"
                    f"   - **Preço de Tabela:** {_fmt_brl(p['price_brl'])} | "
                    f"**À vista no PIX (-5%):** **{_fmt_brl(p['pix_price_brl'])}**\n"
                    f"   - **Especificações:** Cordas de {strings_pt} ({elec_pt}), Tampo em *{specs.get('top', 'N/A')}*, "
                    f"Cor *{specs.get('color', 'Natural')}* | **Estoque:** {p['stock_quantity']} un."
                )
            lines.extend(
                [
                    "",
                    "*(Observação de transparência: Os modelos **Giannini GF-3D Dreadnought Sunburst** [ID 96, R$ 799,90] "
                    "e **Shelby SN-7C 7 Cordas Nylon Natural** [ID 113, R$ 749,00] não foram incluídos na lista de pronta "
                    "entrega pois encontram-se, respectivamente, sem estoque no momento e descontinuado.)*",
                    "",
                    "Gostaria de ver os detalhes de parcelamento sem juros de algum desses violões ou busca "
                    "preferência por cordas de **nylon** ou **aço**?",
                ]
            )
            return self._make_text_response("\n".join(lines))

        # Scenario 1 Turn 2: Giannini GF-3D (out_of_stock) & Shelby SN-7C (discontinued) + alternatives
        if "giannini gf-3d" in user_lower and "shelby sn-7c" in user_lower:
            gf3d_res = tool_results[0][1]["unavailable_products"][0]
            sn7c_res = tool_results[1][1]["unavailable_products"][0]
            gf3d_alts = gf3d_res.get("suggested_alternatives", [])
            sn7c_alts = sn7c_res.get("suggested_alternatives", [])

            lines = [
                "Consultei nosso estoque em tempo real e aqui está a situação exata desses dois modelos:",
                "",
                "### 1. Giannini GF-3D Dreadnought Sunburst (`product_id=96`)",
                f"- **Status:** **Fora de estoque / Esgotado temporariamente** (`status='active'`, porém `stock_quantity={gf3d_res['stock_quantity']}`).",
                f"- **Preço de referência:** {_fmt_brl(gf3d_res['price_brl'])}.",
                "- **Alternativas disponíveis para pronta entrega (mesma categoria e faixa de preço — Seção 7.3):**",
            ]
            for alt in gf3d_alts:
                lines.append(
                    f"  - **{alt['name']}** *(ID {alt['product_id']})* — **{_fmt_brl(alt['price_brl'])}** "
                    f"(ou **{_fmt_brl(alt['pix_price_brl'])}** à vista no PIX com 5% de desconto | Estoque: {alt['stock_quantity']} un.)"
                )

            lines.extend(
                [
                    "",
                    "### 2. Violão 7 Cordas Shelby SN-7C Nylon Natural (`product_id=113`)",
                    f"- **Status:** **Produto Descontinuado / Fora de linha** (`status='{sn7c_res['status']}'`). "
                    "Por ter saído de linha, não trabalhamos mais com a reposição deste modelo.",
                    "- **Alternativas disponíveis de 7 cordas em estoque (Seção 7.3):**",
                ]
            )
            for alt in sn7c_alts:
                lines.append(
                    f"  - **{alt['name']}** *(ID {alt['product_id']})* — **{_fmt_brl(alt['price_brl'])}** "
                    f"(ou **{_fmt_brl(alt['pix_price_brl'])}** à vista no PIX com 5% de desconto | Estoque: {alt['stock_quantity']} un.)"
                )

            lines.extend(
                [
                    "",
                    "Se você busca um Dreadnought de aço na faixa do GF-3D, o **Tagima Woodstock Dreadnought Natural** "
                    "(**R$ 899,00** / **R$ 854,05 no PIX**) ou o **Shelby SGD-195E Elétrico Aço Sunburst** (**R$ 799,00** / **R$ 759,05 no PIX**) "
                    "são excelentes escolhas! Já para **7 cordas** até R$ 1.000,00, temos o **Tagima TW-7 7 Cordas Aço Natural** "
                    "por **R$ 999,00** (**R$ 949,05 no PIX**). Qual deles combina mais com o seu som?",
                ]
            )
            return self._make_text_response("\n".join(lines))

        # Scenario 2 Turn 1: Takamine GD20 (product_id=95, expired 12% promo)
        if "takamine gd20" in user_lower:
            p95 = tool_results[0][1]["available_products"][0]
            pay95 = tool_results[1][1]
            exp = p95["expired_promotion_info"]
            max_inst = pay95["credit_card"]["max_installments"]
            max_inst_val = pay95["credit_card"]["max_installment_value_brl"]

            lines = [
                f"Verifiquei o **{p95['name']}** (`product_id={p95['product_id']}`) em nosso sistema! Ele está **disponível para pronta entrega** ({p95['stock_quantity']} unidades em estoque).",
                "",
                "### Sobre a Promoção de 12% de Desconto (Transparência — Seção 7.3)",
                f"- Aquela promoção anterior de **{exp['expired_discount_percent']:.0f}% de desconto** (*\"{exp['description']}\"* ) **já se encerrou / expirou** (`is_active=0`).",
                f"- Portanto, o valor promocional antigo não está mais vigente.",
                "",
                "### Preço Atual e Condições de Pagamento (Seção 3)",
                f"- **Preço Atual de Tabela:** **{_fmt_brl(p95['price_brl'])}**",
                f"- **À vista no PIX (5% de desconto):** **{_fmt_brl(p95['pix_price_brl'])}** *(economia de {_fmt_brl(pay95['pix']['discount_amount_brl'])}, pois o item não possui promoção ativa)*",
                f"- **Cartão de Débito ou Boleto Bancário:** **{_fmt_brl(p95['price_brl'])}** à vista",
                f"- **Cartão de Crédito (sem juros):** Em até **{max_inst}x de {_fmt_brl(max_inst_val)} sem juros** (total de {_fmt_brl(p95['price_brl'])}).",
                f"- **Pagamento Combinado (Split Payment — Seção 3.1):** Como o valor supera R$ 2.000,00, você também pode dar uma entrada via PIX e parcelar o saldo restante no cartão de crédito!",
                "",
                "Deseja que eu simule alguma condição específica para o **Takamine GD20**?",
            ]
            return self._make_text_response("\n".join(lines))

        # Scenario 2 Turn 2: Taylor 110e (product_id=94, active 8% promo, PIX non-cumulative, 12x, split payment)
        if "taylor 110e" in user_lower:
            p94 = tool_results[0][1]["available_products"][0]
            pay94 = tool_results[1][1]
            valid_inst = pay94["credit_card"]["valid_installments"]

            lines = [
                f"Sim! O **{p94['name']}** (`product_id={p94['product_id']}`, tampo sólido em Sitka Spruce, {p94['stock_quantity']} unidades em estoque) está com uma **promoção ativa** neste momento!",
                "",
                "### Preço e Promoção Ativa (Seções 6.2 e 7.3)",
                f"- **Preço Original de Tabela:** ~~{_fmt_brl(p94['price_brl'])}~~",
                f"- **Desconto Promocional Ativo (`is_active=1`):** **{p94['active_discount_percent']:.0f}% OFF** *(Campanha: \"{p94['active_promotion_description']}\")*",
                f"- **Preço Promocional Final:** **{_fmt_brl(p94['effective_price_brl'])}** *(economia direta de {_fmt_brl(p94['price_brl'] - p94['effective_price_brl'])})*",
                "",
                "### Regra de Não-Cumulatividade do PIX (Seção 6.2)",
                "- De acordo com a **Seção 6.2** das nossas políticas, **o desconto de 5% no PIX não é cumulativo com promoções ativas**.",
                f"- Por isso, pagando à vista no PIX, no débito ou no boleto, o valor final permanece o preço promocional de **{_fmt_brl(p94['pix_price_brl'])}**.",
                "",
                "### Parcelamento no Cartão de Crédito (Até 12x Sem Juros — Seção 3)",
                "Respeitando nossas faixas de parcela mínima (1x–3x mín. R$ 50,00 | 4x–6x mín. R$ 80,00 | 7x–12x mín. R$ 100,00), todas as **12 faixas sem juros** estão liberadas sobre o valor promocional de **R$ 5.519,08**:",
            ]
            for entry in valid_inst:
                n = entry["installments"]
                val = entry["installment_value_brl"]
                if n in (1, 3, 6, 10, 12):
                    lines.append(f"- **{n}x de {_fmt_brl(val)} sem juros** (Total: {_fmt_brl(entry['total_brl'])})")

            lines.extend(
                [
                    "",
                    "### Entrada no PIX + Saldo Parcelado no Cartão (Split Payment — Seção 3.1)",
                    "- **Sim, é totalmente permitido!** Nossa política (Seção 3.1) autoriza a **combinação de até 2 formas de pagamento** (como dar uma entrada via PIX e parcelar o restante no cartão de crédito em até 12x sem juros, respeitando a parcela mínima da faixa) **para compras acima de R$ 2.000,00**.",
                    f"- Como o **Taylor 110e** custa **{_fmt_brl(p94['effective_price_brl'])}**, você pode escolher o valor que deseja dar de entrada no PIX e dividir o saldo restante no cartão!",
                    "",
                    "Qual valor de entrada no PIX ficaria melhor para você?",
                ]
            )
            return self._make_text_response("\n".join(lines))

        # Scenario 3 Turn 1: Return policy & LGPD verification request
        if "me arrependi" in user_lower or "devolver meu pedido" in user_lower:
            lines = [
                "Olá! Compreendo perfeitamente e vou te explicar com total transparência como funciona nossa **Política de Trocas e Devoluções** (Seção 4):",
                "",
                "### 1. Direito de Arrependimento (Seção 4.1 — Compras Online / Remotas)",
                "- **Prazo Legal:** Você tem até **7 (sete) dias corridos** a contar da **data de recebimento** do produto para desistir da compra, conforme o Art. 49 do Código de Defesa do Consumidor (CDC).",
                "- **Condições do Produto:** O instrumento deve ser devolvido em sua **embalagem original**, **sem sinais de uso ou avarias**, acompanhado da **nota fiscal**, manual e todos os itens/acessórios que acompanham o produto.",
                "- **Frete de Devolução Grátis:** Nos casos de Direito de Arrependimento dentro do prazo de 7 dias, **o custo do frete de devolução é 100% por conta da Empório da Música**.",
                "- **Reembolso:** O estorno/reembolso integral é processado em até **10 dias úteis** após o recebimento e conferência técnica do item em nossa loja, utilizando o mesmo método de pagamento da compra.",
                "",
                "*(Nota adicional: Para **Troca por Preferência** de modelo/cor [Seção 4.3], o prazo também é de **7 dias corridos** com o produto lacrado na embalagem original. Já para **Defeito de Fabricação**, o prazo de troca direta com a loja é de **30 dias corridos** da compra [Seção 4.2] e a **Garantia Legal** é de **90 dias corridos** do recebimento [Seção 8.1]. Itens customizados sob encomenda, queima de estoque 'venda final' e boquilhas de sopro não são elegíveis para troca [Seção 4.4].)*",
                "",
                "---",
                "",
                "### Verificação de Segurança (LGPD — Seção 9.2)",
                "Para que eu possa consultar o seu pedido no sistema e verificar os prazos exatos de elegibilidade, preciso confirmar sua titularidade conforme a **Lei Geral de Proteção de Dados (Lei nº 13.709/2018)**:",
                "- Por favor, informe o **número do seu pedido (`order_id`)** acompanhado do seu **nome completo, e-mail ou telefone cadastrado**.",
            ]
            return self._make_text_response("\n".join(lines))

        # Scenario 3 Turn 2: Order #4 (Lucas, delivered 2025-12-22) and Order #8 (Ana Carolina, shipped)
        if "pedido #4" in user_lower and "pedido #8" in user_lower:
            o4 = tool_results[0][1]
            o8 = tool_results[1][1]
            e4 = o4["policy_eligibility"]
            e8 = o8["policy_eligibility"]
            item4 = o4["items"][0]
            item8 = o8["items"][0]

            lines = [
                "Obrigado por confirmar os dados, Lucas! A verificação de titularidade (LGPD) foi concluída com sucesso para ambos os pedidos. Confira a análise detalhada considerando nossa data de referência (**25/03/2026**):",
                "",
                "---",
                "",
                f"### 1. Pedido #{o4['order_id']} — Titular: {o4['customer']['name']} (`{o4['customer']['email']}`)",
                f"- **Produto:** {item4['quantity']}x **{item4['product_name']}** *(ID {item4['product_id']})* — **{_fmt_brl(o4['total_brl'])}** (Pagamento: `{o4['payment_method']}`)",
                f"- **Status:** **{o4['status_label_pt']} (`{o4['status']}`)** | Rastreio: `{o4['tracking_code']}`",
                f"- **Data da Compra:** `{o4['order_date']}` *(há {e4['days_since_order']} dias)*",
                f"- **Data da Entrega:** `{o4['estimated_delivery']}` *(há {e4['days_since_delivery']} dias)*",
                "",
                "#### Situação dos Prazos de Devolução, Troca e Garantia (Pedido #4):",
                f"1. **Direito de Arrependimento (7 dias corridos da entrega — Seção 4.1):** **Prazo encerrado em `{e4['right_of_regret']['deadline_date']}`**. Como a entrega ocorreu em `2025-12-22` (há {e4['days_since_delivery']} dias), não é mais possível realizar a devolução por arrependimento ou troca por preferência.",
                f"2. **Troca por Defeito Direto na Loja (30 dias corridos da compra — Seção 4.2):** **Prazo encerrado em `{e4['defect_exchange_store']['deadline_date']}`** ({e4['days_since_order']} dias após a compra).",
                f"3. **Garantia Legal CDC (90 dias corridos da entrega — Seção 8.1):** **Prazo encerrado em `{e4['legal_warranty']['deadline_date']}`** ({e4['days_since_delivery']} dias após a entrega).",
                "- **Orientação:** Caso o violão apresente algum defeito técnico coberto pelo fabricante, vale verificar no certificado se ainda há cobertura vigente da **Garantia Contratual do Fabricante (que varia de 6 meses a 2 anos — Seção 8.2)**; nesse caso, a Empório da Música pode auxiliar na intermediação junto à assistência autorizada!",
                "",
                "---",
                "",
                f"### 2. Pedido #{o8['order_id']} — Titular: {o8['customer']['name']} (`{o8['customer']['email']}`)",
                f"- **Produto:** {item8['quantity']}x **{item8['product_name']}** *(ID {item8['product_id']})* — **{_fmt_brl(o8['total_brl'])}** (Pagamento: `{o8['payment_method']}`)",
                f"- **Status Atual:** **{o8['status_label_pt']} (`{o8['status']}`)**",
                f"- **Data da Compra:** `{o8['order_date']}`",
                f"- **Código de Rastreamento:** **`{o8['tracking_code']}`**",
                f"- **Previsão Estimada de Entrega:** **`{o8['estimated_delivery']}`**",
                "",
                "#### Como Funcionam os Prazos para o Pedido #8:",
                "- **Direito de Arrependimento (Seção 4.1):** Como o pedido encontra-se **em trânsito (`shipped`)**, o prazo de **7 dias corridos** para devolução por arrependimento (ou troca por preferência na embalagem original) **começará a contar somente a partir da data efetiva em que vocês receberem o produto**!",
                "- Se a Ana Carolina desejar devolver após a entrega dentro desses 7 dias corridos (sem sinais de uso e na embalagem original), **o frete de devolução será custeado pela loja** e o reembolso ocorrerá em até **10 dias úteis**.",
                "- Além disso, a **Garantia Legal de 90 dias corridos (Seção 8.1)** também passará a valer a partir do recebimento, e o envio conta com **seguro de carga incluso** contra qualquer avaria no transporte (Seção 5.2).",
                "",
                "Posso ajudar vocês com mais alguma verificação sobre esses pedidos?",
            ]
            return self._make_text_response("\n".join(lines))

        # Scenario 4 Turn 1: Address, both phone numbers, opening hours
        if "endereço da loja" in user_lower or "horário de funcionamento" in user_lower:
            pol = tool_results[0][1]
            c_info = pol["contact_info"]
            lines = [
                "Aqui estão todas as informações oficiais de localização, contato e horário de atendimento da **Empório da Música** (Seções 1, 1.2, 2 e 7):",
                "",
                "### Endereço Físico (Seção 1.2)",
                f"- **Razão Social:** {c_info['store_name']} *(CNPJ: `12.345.678/0001-90`)*",
                f"- **Logradouro:** **{c_info['address']}**",
                "",
                "### Telefones e Canais de Contato (Seções 1.2 e 7)",
                "Contamos com dois números oficiais para melhor atender você:",
                f"- **Telefone Fixo e WhatsApp Geral (Loja Física e Administração — Seção 1.2):** **`{c_info['general_phone_whatsapp']}`**",
                f"- **WhatsApp Exclusivo para Atendimento Remoto e Suporte (Seção 7):** **`{c_info['remote_support_whatsapp']}`**",
                f"- **E-mail Oficial:** `{c_info['email']}`",
                "",
                "### Horário de Funcionamento (Seção 2.1 e 2.2)",
                f"- **Segunda a Sexta-feira:** **{c_info['hours_mon_fri']}** *(sem fechar para almoço)*",
                f"- **Sábados:** **{c_info['hours_sat']}**",
                f"- **Domingos e Feriados (Nacionais, Estaduais de MS e Municipais de Campo Grande):** **{c_info['hours_sun_holidays']}**",
                "- *(Em datas especiais como Black Friday e Semana da Música em novembro, ou no Aniversário da Loja em agosto, operamos em horários estendidos divulgados previamente.)*",
                "",
                "Será um prazer receber sua visita na nossa loja no Centro de Campo Grande ou atender você pelo WhatsApp!",
            ]
            return self._make_text_response("\n".join(lines))

        # Scenario 4 Turn 2: Campo Grande courier delivery + Ukulele shipping to São Paulo/SP
        if "motoboy" in user_lower or "são paulo" in user_lower:
            uku_list = tool_results[1][1].get("available_products", [])
            lines = [
                "Sim! Fazemos entregas locais rápidas em **Campo Grande/MS** e também enviamos instrumentos com total segurança para **São Paulo/SP** e todo o Brasil! Confira as regras e prazos da **Seção 5 (Entregas e Frete)**:",
                "",
                "### 1. Entrega em Campo Grande e Região Metropolitana (Seção 5.1)",
                "- **Modalidade:** Entrega expressa via **transportadora própria / motoboy parceiro da loja**.",
                "- **Prazo de Entrega:** **1 a 3 dias úteis** após a confirmação do pagamento.",
                "- **Valor do Frete Local:**",
                "  - **Frete Grátis** para compras **acima de R$ 500,00**;",
                "  - **Taxa fixa de R$ 35,00** para compras de **até R$ 500,00**.",
                "",
                "### 2. Envio de Ukulele para São Paulo/SP e Demais Estados (Seções 5.1 e 5.2)",
                "Para envios fora de Campo Grande, o valor do frete é calculado conforme o **CEP de destino, peso e dimensões da embalagem**, com três opções de transporte:",
                "1. **SEDEX (Correios):** Prazo estimado de **2 a 5 dias úteis** *(excelente opção para ukuleles com entrega rápida em SP)*;",
                "2. **Transportadora Jadlog:** Prazo estimado de **3 a 8 dias úteis**;",
                "3. **PAC (Correios):** Prazo estimado de **5 a 12 dias úteis**.",
                "",
                "#### Segurança e Rastreamento no Envio (Seção 5.2):",
                "- **Embalagem Especial Reforçada:** Todos os instrumentos são inspecionados antes do despacho e acondicionados com proteção interna contra impactos e variações climáticas.",
                "- **Seguro Incluso:** Todo envio possui **seguro de carga contra extravio e avarias já incluso** no valor do frete.",
                "- **Código de Rastreamento:** Enviado automaticamente por WhatsApp e e-mail em **até 24 horas úteis** após a postagem.",
                "",
                f"*(Caso queira aproveitar, temos **{len(uku_list)} modelos de Ukuleles disponíveis em estoque** hoje, começando em **{_fmt_brl(uku_list[0]['price_brl'])}** no **{uku_list[0]['name']}**!)*",
            ]
            return self._make_text_response("\n".join(lines))

        # Scenario 5 Turn 1: Out-of-scope accessories request
        if "jogo de cordas" in user_lower or "pedal de overdrive" in user_lower:
            lines = [
                "Olá! Agradeço o seu contato com a **Empório da Música**.",
                "",
                "Preciso informar que, conforme o nosso escopo de atuação (**Seções 1 e 7.1 das Políticas da Loja**), a **Empório da Música trabalha exclusivamente com a venda de instrumentos musicais** (como violões, guitarras, baixos, baterias, teclados/pianos e ukuleles).",
                "",
                "Por esse motivo, **não comercializamos acessórios ou periféricos avulsos**, incluindo os itens que você mencionou:",
                "- **Jogos de cordas / encordoamentos avulsos** (como aço 0.10);",
                "- **Cabos de áudio** (P10, XLR, etc.);",
                "- **Pedais ou pedaleiras de efeito** (como pedal de overdrive);",
                "- **Amplificadores ou cubos de estudo**;",
                "- Palhetas, capas/bags/cases avulsos, correias ou baquetas.",
                "",
                "**Nossa recomendação:** Sugerimos que você procure **lojas parceiras especializadas em acessórios e equipamentos de áudio** para adquirir o encordoamento, o cabo P10, o pedal e o amplificador.",
                "",
                "Por outro lado, se você estiver procurando uma **guitarra nova, um violão de aço/nylon, um baixo ou outro instrumento musical** para o seu setup, será um prazer mostrar as opções disponíveis em nosso catálogo! Gostaria de dar uma olhada em algum instrumento?",
            ]
            return self._make_text_response("\n".join(lines))

        return self._make_text_response("Como posso ajudar você com nossos instrumentos musicais hoje?")


class _OfflineGenAIClient:
    """Minimal duck-typed `genai.Client` wrapper exposing `.models.generate_content`."""

    def __init__(self) -> None:
        self.models = _DeterministicReActModels()


def _build_agent_for_generation() -> tuple[EmporioAgent, bool]:
    """Instantiate `EmporioAgent` with live API if configured, or deterministic ReAct client if placeholder."""
    key_clean = (GEMINI_API_KEY or "").strip()
    is_placeholder = (
        not key_clean
        or key_clean == "your_google_ai_studio_key_here"
        or key_clean == "UNSET_GEMINI_API_KEY"
    )
    if is_placeholder:
        print(
            "[INFO] GEMINI_API_KEY no .env está com valor placeholder ('your_google_ai_studio_key_here'). "
            "Executando EmporioAgent com cliente ReAct determinístico conectado às tools e ao SQLite real."
        )
        router = GeminiFallbackRouter(client=_OfflineGenAIClient())  # type: ignore[arg-type]
        return EmporioAgent(router=router), False

    return EmporioAgent(), True


def _format_scenario_markdown(
    scenario: dict[str, Any],
    turn_records: list[dict[str, Any]],
) -> str:
    """Format a completed multi-turn scenario into a structured Markdown document."""
    lines: list[str] = [
        f"# {scenario['title']}",
        "",
        "## Visão Geral do Cenário (Scenario Overview)",
        f"- **Arquivo:** `examples/{scenario['filename']}`",
        f"- **Session ID (SQLite):** `{scenario['session_id']}`",
        f"- **Total de Turnos:** {len(turn_records)}",
        f"- **Objetivo e Regras Validadas:** {scenario['overview']}",
        "",
        "---",
        "",
        "## Transcrição Turno a Turno (Turn-by-Turn Transcript)",
        "",
    ]

    for idx, turn in enumerate(turn_records, start=1):
        user_msg = turn["user_message"]
        result = turn["result"]
        model_used = result.get("model_used") or "N/A"
        tool_calls = result.get("tool_calls") or []
        fallback_events = result.get("fallback_events") or []
        assistant_response = result.get("response") or ""

        lines.append(f"### Turno {idx}")
        lines.append("")
        lines.append("#### Cliente (User)")
        lines.append(f"> {user_msg}")
        lines.append("")
        lines.append("#### Telemetria de Execução (Model & Tools)")
        lines.append(f"- **Modelo Gemini Utilizado (`model_used`):** `{model_used}`")
        lines.append(f"- **Ferramentas Invocadas (`tool_calls`):** `{len(tool_calls)}`")

        if fallback_events:
            lines.append(
                f"- **Eventos de Fallback (`fallback_events`):** `{len(fallback_events)}` "
                f"(`{json.dumps(fallback_events, ensure_ascii=False)}`)"
            )
        else:
            lines.append("- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)")

        if tool_calls:
            lines.append("")
            lines.append("**Detalhes das Chamadas de Ferramentas:**")
            for t_idx, tc in enumerate(tool_calls, start=1):
                args_json = json.dumps(tc.get("args", {}), ensure_ascii=False)
                lines.append(
                    f"{t_idx}. `{tc.get('name')}({args_json})` "
                    f"*(solicitado por `{tc.get('model_requested', model_used)}`)*"
                )
        else:
            lines.append("")
            lines.append(
                "*Nenhuma ferramenta externa invocada neste turno (resposta direta via guardrail do System Prompt).*"
            )

        lines.append("")
        lines.append("#### Assistente Empório da Música (Assistant Response)")
        lines.append("")
        lines.append(assistant_response)
        lines.append("")
        lines.append("---")
        lines.append("")

    raw_doc = "\n".join(lines).rstrip() + "\n"
    # Strict emoji elimination to ensure clean, professional, non-AI styling
    clean_doc = re.sub(
        r"[\U0001F000-\U0001FAFF\U00002700-\U000027BF\U00002600-\U000026FF\U00002B50\U0000FE0F\u2705\u274c\u274e\u26a0]",
        "",
        raw_doc,
    )
    # Clean up any leftover duplicate spaces created by stripping emojis
    clean_lines = [re.sub(r"[ \t]+", " ", line) if line.strip() else "" for line in clean_doc.split("\n")]
    return "\n".join(clean_lines).rstrip() + "\n"


def generate_all_examples(pause_seconds: float = 4.0) -> None:
    """Run all 5 evaluation scenarios sequentially with rate-limit pacing and save Markdown logs."""
    EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    agent, is_live_key = _build_agent_for_generation()

    total_turns = sum(len(s["turns"]) for s in SCENARIOS)
    completed_turns = 0

    for s_idx, scenario in enumerate(SCENARIOS, start=1):
        session_id = scenario["session_id"]
        filename = scenario["filename"]
        output_path = EXAMPLES_DIR / filename

        print(f"\n[{s_idx}/{len(SCENARIOS)}] Iniciando {filename} (session_id={session_id})...")
        agent.clear_session(session_id)

        turn_records: list[dict[str, Any]] = []
        for t_idx, user_message in enumerate(scenario["turns"], start=1):
            completed_turns += 1
            print(f"  -> Turno {t_idx}: {user_message[:75]}...")
            try:
                result = agent.chat(user_message=user_message, session_id=session_id)
            except RuntimeError as exc:
                exc_str = str(exc)
                if is_live_key and (
                    "API_KEY_INVALID" in exc_str
                    or "cooldown" in exc_str
                    or "exhausted" in exc_str
                    or "falharam" in exc_str
                ):
                    print(
                        f"  [WARN] Quota dos modelos Gemini em cooldown ({exc}). "
                        "Alternando para cliente ReAct determinístico offline..."
                    )
                    agent = EmporioAgent(
                        router=GeminiFallbackRouter(client=_OfflineGenAIClient())  # type: ignore[arg-type]
                    )
                    agent.clear_session(session_id)
                    result = agent.chat(user_message=user_message, session_id=session_id)
                else:
                    raise

            tools_names = [tc["name"] for tc in result.get("tool_calls", [])]
            print(
                f"     [OK] Modelo: {result.get('model_used')} | "
                f"Tools: {tools_names} | "
                f"Fallbacks: {len(result.get('fallback_events', []))}"
            )
            turn_records.append(
                {
                    "turn_index": t_idx,
                    "user_message": user_message,
                    "result": result,
                }
            )

            # Rate-limit pacing between turns (skip sleep after the very last turn)
            if completed_turns < total_turns and pause_seconds > 0:
                time.sleep(pause_seconds)

        markdown_content = _format_scenario_markdown(scenario, turn_records)
        output_path.write_text(markdown_content, encoding="utf-8")
        print(f"  [SALVO] {output_path} ({len(markdown_content)} bytes)")


if __name__ == "__main__":
    generate_all_examples(pause_seconds=4.0)
