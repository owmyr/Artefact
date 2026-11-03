# Cenário 02 — Promoção Expirada vs. Promoção Ativa, PIX Não-Cumulativo e Split Payment

## 📋 Visão Geral do Cenário (Scenario Overview)
- **Arquivo:** `examples/02_preco_promocao_expirada_parcelamento.md`
- **Session ID (SQLite):** `example_02_promocoes_e_parcelamento`
- **Total de Turnos:** 2
- **Objetivo e Regras Validadas:** Demonstra a transparência na verificação de promoções expiradas versus ativas (Seções 3, 3.1, 6.2 e 7.3). No Turno 1, verifica o `Takamine GD20` (`product_id=95`), informa que a campanha anterior de 12% ('Oferta Especial') expirou (`is_active=0`), e apresenta o preço de tabela (R$ 2.199,00) e o valor no PIX com 5% de desconto (R$ 2.089,05). No Turno 2, verifica o `Taylor 110e` (`product_id=94`) com promoção ativa de 8% (de R$ 5.999,00 por R$ 5.519,08), explica que o desconto de 5% do PIX não é cumulativo com promoções ativas, detalha o parcelamento em até 12x sem juros e confirma a possibilidade de pagamento combinado (entrada no PIX + saldo no Cartão) por superar R$ 2.000,00.

---

## 💬 Transcrição Turno a Turno (Turn-by-Turn Transcript)

### Turno 1

#### 🧑‍🎤 Cliente (User)
> Quanto custa o Takamine GD20? Ele ainda está naquela promoção de 12% de desconto?

#### 🔍 Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-2.5-flash`
- **Ferramentas Invocadas (`tool_calls`):** `2`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

**Detalhes das Chamadas de Ferramentas:**
1. `search_catalog({"query": "Takamine GD20"})` *(solicitado por `gemini-2.5-flash`)*
2. `calculate_payment_options({"price_brl": 2199.0, "has_active_promotion": false})` *(solicitado por `gemini-2.5-flash`)*

#### 🎸 Assistente Empório da Música (Assistant Response)

Verifiquei o **Takamine GD20 Dreadnought Natural** (`product_id=95`) em nosso sistema! Ele está **disponível para pronta entrega** (5 unidades em estoque).

### ⚠️ Sobre a Promoção de 12% de Desconto (Transparência — Seção 7.3)
- Aquela promoção anterior de **12% de desconto** (*"Oferta Especial"* ) **já se encerrou / expirou** (`is_active=0`).
- Portanto, o valor promocional antigo não está mais vigente.

### 💰 Preço Atual e Condições de Pagamento (Seção 3)
- **Preço Atual de Tabela:** **R$ 2.199,00**
- **À vista no PIX (5% de desconto):** **R$ 2.089,05** *(economia de R$ 109,95, pois o item não possui promoção ativa)*
- **Cartão de Débito ou Boleto Bancário:** **R$ 2.199,00** à vista
- **Cartão de Crédito (sem juros):** Em até **12x de R$ 183,25 sem juros** (total de R$ 2.199,00).
- **Pagamento Combinado (Split Payment — Seção 3.1):** Como o valor supera R$ 2.000,00, você também pode dar uma entrada via PIX e parcelar o saldo restante no cartão de crédito!

Deseja que eu simule alguma condição específica para o **Takamine GD20**?

---

### Turno 2

#### 🧑‍🎤 Cliente (User)
> E o Taylor 110e, está em promoção? Como fica o parcelamento dele no cartão ou se eu quiser dar uma entrada no PIX e parcelar o resto?

#### 🔍 Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-2.5-flash`
- **Ferramentas Invocadas (`tool_calls`):** `2`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

**Detalhes das Chamadas de Ferramentas:**
1. `search_catalog({"query": "Taylor 110e"})` *(solicitado por `gemini-2.5-flash`)*
2. `calculate_payment_options({"price_brl": 5519.08, "has_active_promotion": true})` *(solicitado por `gemini-2.5-flash`)*

#### 🎸 Assistente Empório da Música (Assistant Response)

Sim! O **Taylor 110e Dreadnought Natural** (`product_id=94`, tampo sólido em Sitka Spruce, 4 unidades em estoque) está com uma **promoção ativa** neste momento! 🎉

### 🏷️ Preço e Promoção Ativa (Seções 6.2 e 7.3)
- **Preço Original de Tabela:** ~~R$ 5.999,00~~
- **Desconto Promocional Ativo (`is_active=1`):** **8% OFF** *(Campanha: "Desconto Exclusivo")*
- **Preço Promocional Final:** **R$ 5.519,08** *(economia direta de R$ 479,92)*

### ⚠️ Regra de Não-Cumulatividade do PIX (Seção 6.2)
- De acordo com a **Seção 6.2** das nossas políticas, **o desconto de 5% no PIX não é cumulativo com promoções ativas**.
- Por isso, pagando à vista no PIX, no débito ou no boleto, o valor final permanece o preço promocional de **R$ 5.519,08**.

### 💳 Parcelamento no Cartão de Crédito (Até 12x Sem Juros — Seção 3)
Respeitando nossas faixas de parcela mínima (1x–3x mín. R$ 50,00 | 4x–6x mín. R$ 80,00 | 7x–12x mín. R$ 100,00), todas as **12 faixas sem juros** estão liberadas sobre o valor promocional de **R$ 5.519,08**:
- **1x de R$ 5.519,08 sem juros** (Total: R$ 5.519,08)
- **3x de R$ 1.839,69 sem juros** (Total: R$ 5.519,08)
- **6x de R$ 919,85 sem juros** (Total: R$ 5.519,08)
- **10x de R$ 551,91 sem juros** (Total: R$ 5.519,08)
- **12x de R$ 459,92 sem juros** (Total: R$ 5.519,08)

### 🤝 Entrada no PIX + Saldo Parcelado no Cartão (Split Payment — Seção 3.1)
- **Sim, é totalmente permitido!** Nossa política (Seção 3.1) autoriza a **combinação de até 2 formas de pagamento** (como dar uma entrada via PIX e parcelar o restante no cartão de crédito em até 12x sem juros, respeitando a parcela mínima da faixa) **para compras acima de R$ 2.000,00**.
- Como o **Taylor 110e** custa **R$ 5.519,08**, você pode escolher o valor que deseja dar de entrada no PIX e dividir o saldo restante no cartão!

Qual valor de entrada no PIX ficaria melhor para você?

---
