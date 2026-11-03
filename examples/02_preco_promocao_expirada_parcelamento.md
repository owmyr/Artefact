# Cenário 02 — Promoção Expirada vs. Promoção Ativa, PIX Não-Cumulativo e Split Payment

## Visão Geral do Cenário (Scenario Overview)
- **Arquivo:** `examples/02_preco_promocao_expirada_parcelamento.md`
- **Session ID (SQLite):** `example_02_promocoes_e_parcelamento`
- **Total de Turnos:** 2
- **Objetivo e Regras Validadas:** Demonstra a transparência na verificação de promoções expiradas versus ativas (Seções 3, 3.1, 6.2 e 7.3). No Turno 1, verifica o `Takamine GD20` (`product_id=95`), informa que a campanha anterior de 12% ('Oferta Especial') expirou (`is_active=0`), e apresenta o preço de tabela (R$ 2.199,00) e o valor no PIX com 5% de desconto (R$ 2.089,05). No Turno 2, verifica o `Taylor 110e` (`product_id=94`) com promoção ativa de 8% (de R$ 5.999,00 por R$ 5.519,08), explica que o desconto de 5% do PIX não é cumulativo com promoções ativas, detalha o parcelamento em até 12x sem juros e confirma a possibilidade de pagamento combinado (entrada no PIX + saldo no Cartão) por superar R$ 2.000,00.

---

## Transcrição Turno a Turno (Turn-by-Turn Transcript)

### Turno 1

#### Cliente (User)
> Quanto custa o Takamine GD20? Ele ainda está naquela promoção de 12% de desconto?

#### Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-3.5-flash-lite`
- **Ferramentas Invocadas (`tool_calls`):** `2`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

**Detalhes das Chamadas de Ferramentas:**
1. `search_catalog({"query": "Takamine GD20"})` *(solicitado por `gemini-3.5-flash-lite`)*
2. `calculate_payment_options({"price_brl": 2199, "has_active_promotion": false})` *(solicitado por `gemini-3.5-flash-lite`)*

#### Assistente Empório da Música (Assistant Response)

O violão **Takamine GD20 Dreadnought Natural** está atualmente com o preço de tabela de **R$ 2.199,00** e conta com **5 unidades disponíveis** para pronta entrega em nossa loja.

Sobre a promoção de 12% de desconto citada, ela **já expirou**. O valor atual é o preço de tabela vigente.

Para facilitar a sua compra, disponibilizamos as seguintes condições de pagamento:

- **À vista no PIX**: Com 5% de desconto, sai por **R$ 2.089,05**.
- **Cartão de Crédito**: Parcelamento em até **12x sem juros** (parcelas mínimas aplicáveis conforme a faixa escolhida, por exemplo, em até 12x de R$ 183,25).
- **Split Payment**: Como o valor do instrumento é superior a R$ 2.000,00, você também pode optar por combinar o pagamento (por exemplo, uma entrada no PIX e o saldo restante parcelado no cartão de crédito).

Estamos à disposição caso queira tirar dúvidas sobre especificações técnicas ou realizar o seu pedido.

---

### Turno 2

#### Cliente (User)
> E o Taylor 110e, está em promoção? Como fica o parcelamento dele no cartão ou se eu quiser dar uma entrada no PIX e parcelar o resto?

#### Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-3.5-flash-lite`
- **Ferramentas Invocadas (`tool_calls`):** `2`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

**Detalhes das Chamadas de Ferramentas:**
1. `search_catalog({"query": "Taylor 110e"})` *(solicitado por `gemini-3.5-flash-lite`)*
2. `calculate_payment_options({"price_brl": 5519.08, "has_active_promotion": true})` *(solicitado por `gemini-3.5-flash-lite`)*

#### Assistente Empório da Música (Assistant Response)

Sim, o violão **Taylor 110e Dreadnought Natural** está atualmente com uma promoção ativa em nossa loja! 

Abaixo estão os detalhes de preço e valores promocionais:
- **Preço de Tabela original**: R$ 5.999,00
- **Campanha**: Desconto Exclusivo (8% de desconto)
- **Preço Promocional Final / Valor à vista**: **R$ 5.519,08** (temos 4 unidades disponíveis para pronta entrega).
- *Observação sobre o PIX*: Como o violão já se encontra em promoção ativa, o desconto adicional de 5% no PIX não é acumulativo, sendo o valor à vista o próprio preço promocional de R$ 5.519,08.

### Condições de Parcelamento no Cartão de Crédito
O Taylor 110e pode ser parcelado em **até 12x sem juros** no cartão de crédito, respeitando os valores mínimos por parcela. Exemplos:
- **3x de R$ 1.839,69** sem juros
- **6x de R$ 919,85** sem juros
- **12x de R$ 459,92** sem juros

### Entrada no PIX + Parcelamento do Saldo (*Split Payment*)
Como o valor total do instrumento supera R$ 2.000,00, **é totalmente permitida** a modalidade de pagamento combinado (*split payment*). 

Você pode dar uma valor de entrada via PIX (ou dinheiro/débito) e passar o saldo remanescente no cartão de crédito em até 12x sem juros (desde que cada parcela do cartão atinja os valores mínimos exigidos de R$ 50 para 1x-3x, R$ 80 para 4x-6x, ou R$ 100 para 7x-12x).

Caso queira simular um valor específico de entrada para verificarmos como ficariam as parcelas restantes, basta me avisar. Estamos à disposição!

---
