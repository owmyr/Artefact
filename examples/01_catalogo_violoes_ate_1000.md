# Cenário 01 — Catálogo de Violões até R$ 1.000 e Tratamento de Indisponíveis

## Visão Geral do Cenário (Scenario Overview)
- **Arquivo:** `examples/01_catalogo_violoes_ate_1000.md`
- **Session ID (SQLite):** `example_01_violoes_ate_1000`
- **Total de Turnos:** 2
- **Objetivo e Regras Validadas:** Demonstra a filtragem determinística de violões disponíveis até R$ 1.000,00 (listando exatamente os 12 modelos com `status='active'` e `stock_quantity > 0`) e, no segundo turno, o tratamento transparente de itens indisponíveis: `Giannini GF-3D` (`product_id=96`, `stock_quantity=0` — esgotado) e `Shelby SN-7C` (`product_id=113`, `status='discontinued'` — fora de linha), com sugestão proativa de alternativas disponíveis como o 7 cordas `Tagima TW-7` (R$ 999,00) e o `Tagima Woodstock` (R$ 899,00) conforme a Seção 7.3 das políticas.

---

## Transcrição Turno a Turno (Turn-by-Turn Transcript)

### Turno 1

#### Cliente (User)
> Olá! Quais opções de violões disponíveis vocês têm custando até R$ 1000?

#### Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-3.5-flash-lite`
- **Ferramentas Invocadas (`tool_calls`):** `1`
- **Eventos de Fallback (`fallback_events`):** `3` (`gemini-3.8-flash [HTTP 429: daily_quota_exhausted] -> gemini-3.6-flash [HTTP 429: daily_quota_exhausted] -> gemini-3-flash-preview [HTTP 429: daily_quota_exhausted] -> gemini-3.5-flash-lite [OK]`)

**Detalhes das Chamadas de Ferramentas:**
1. `search_catalog({"max_price": 1000, "only_available": true, "category": "Violões"})` *(solicitado por `gemini-3-flash-preview`)*

#### Assistente Empório da Música (Assistant Response)

Temos excelentes opções de violões disponíveis para pronta entrega custando até R$ 1.000,00 na Empório da Música. Abaixo estão todos os modelos em estoque, organizados por faixa de preço:

1. **Tagima Memphis AC-39 Nylon Natural**
 - **Descrição**: Violão clássico com cordas de nylon, ideal para iniciantes, com corpo leve e confortável.
 - **Preço**: R$ 429,90 (ou R$ 408,40 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 8x sem juros de R$ 53,74 no cartão de crédito.

2. **Rozini RC-104 Nylon Estudante**
 - **Descrição**: Violão clássico de estudo da Rozini, feito com madeiras nacionais e excelente acabamento para iniciantes.
 - **Preço**: R$ 459,90 (ou R$ 436,90 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 9x sem juros de R$ 51,10 no cartão de crédito.

3. **Shelby SN-100 Folk Aço Preto**
 - **Descrição**: Violão folk com cordas de aço, visual moderno em acabamento preto e boa relação custo-benefício.
 - **Preço**: R$ 549,00 (ou R$ 521,55 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 10x sem juros de R$ 54,90 no cartão de crédito.

4. **Giannini GF-1R Aço Folk Sunburst**
 - **Descrição**: Violão folk com tampo em Spruce e acabamento Sunburst, oferecendo som equilibrado.
 - **Preço**: R$ 579,90 (ou R$ 550,90 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 11x sem juros de R$ 52,72 no cartão de crédito.

5. **Yamaha C40 Nylon Natural**
 - **Descrição**: Violão clássico mundialmente conhecido, com tampo em Spruce e ótima projeção sonora para estudantes.
 - **Preço**: R$ 599,90 (ou R$ 569,90 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 11x sem juros de R$ 54,54 no cartão de crédito.

6. **Giannini GN-15 Nylon Cedro Natural**
 - **Descrição**: Violão clássico com tampo em cedro, proporcionando sonoridade quente e encorpada.
 - **Preço**: R$ 689,00 (ou R$ 654,55 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 12x sem juros de R$ 57,42 no cartão de crédito.

7. **Yamaha F310 Aço Natural**
 - **Descrição**: Violão folk com cordas de aço, corpo robusto e timbre encorpado, muito procurado por iniciantes e intermediários.
 - **Preço**: R$ 699,90 (ou R$ 664,90 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 12x sem juros de R$ 58,33 no cartão de crédito.

8. **Tagima Dallas Tuner Aço Natural**
 - **Descrição**: Violão folk com cordas de aço e afinador integrado, oferecendo som brilhante para acompanhamento.
 - **Preço**: R$ 749,00 (ou R$ 711,55 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 12x sem juros de R$ 62,42 no cartão de crédito.

9. **Shelby SGD-195E Elétrico Aço Sunburst**
 - **Descrição**: Violão eletroacústico dreadnought com captação e afinador integrado, ideal para quem precisa de amplificação.
 - **Preço**: R$ 799,00 (ou R$ 759,05 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 12x sem juros de R$ 66,58 no cartão de crédito.

10. **Yamaha C70 Nylon Natural**
 - **Descrição**: Violão clássico de nível intermediário com tampo em Spruce sólido e acabamento de alta qualidade.
 - **Preço**: R$ 849,00 (ou R$ 806,55 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 12x sem juros de R$ 70,75 no cartão de crédito.

11. **Tagima Woodstock Dreadnought Natural**
 - **Descrição**: Violão dreadnought com corpo amplo, som potente e excelente projeção para fingerpicking e strumming. *(Nota: A campanha anterior de Black Friday encerrou-se, valendo o preço de tabela atual)*.
 - **Preço**: R$ 899,00 (ou R$ 854,05 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 12x sem juros de R$ 74,92 no cartão de crédito.

12. **Tagima TW-7 7 Cordas Aço Natural**
 - **Descrição**: Violão de 7 cordas com cordas de aço para estilos que exigem projeção extra e braço confortável com tensor regulável.
 - **Preço**: R$ 999,00 (ou R$ 949,05 à vista no PIX com 5% de desconto).
 - **Parcelamento**: Em até 12x sem juros de R$ 83,25 no cartão de crédito.

Caso queira conhecer algum desses modelos mais de perto ou tirar dúvidas sobre as especificações (como tipo de madeira ou escala), estamos à disposição em nossa loja física na Rua 14 de Maio, 3200 — Centro, Campo Grande/MS, ou pelos nossos canais de atendimento. Como podemos ajudar na sua escolha?

---

### Turno 2

#### Cliente (User)
> Ouvi falar muito bem do Giannini GF-3D e do violão de 7 cordas Shelby SN-7C. Vocês têm algum deles em estoque?

#### Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-3.5-flash-lite`
- **Ferramentas Invocadas (`tool_calls`):** `2`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

**Detalhes das Chamadas de Ferramentas:**
1. `search_catalog({"category": "Violões", "query": "Giannini GF-3D"})` *(solicitado por `gemini-3.5-flash-lite`)*
2. `search_catalog({"query": "Shelby SN-7C", "category": "Violões"})` *(solicitado por `gemini-3.5-flash-lite`)*

#### Assistente Empório da Música (Assistant Response)

Sobre os dois modelos que você mencionou:

1. **Giannini GF-3D Dreadnought Sunburst**: 
 Este modelo encontra-se atualmente **temporariamente esgotado** em nosso estoque. Como alternativa com proposta similar (corpo dreadnought e ótima projeção sonora), temos disponível para pronta entrega o **Tagima Woodstock Dreadnought Natural** por R$ 899,00 (ou R$ 854,05 à vista no PIX), parcelável em até 12x sem juros de R$ 74,92, além do **Shelby SGD-195E Elétrico Aço Sunburst** por R$ 799,00 (ou R$ 759,05 à vista no PIX) em até 12x sem juros de R$ 66,58.

2. **Shelby SN-7C 7 Cordas Nylon Natural**: 
 Este modelo foi **descontinuado (saiu de linha)** pelo fabricante e não possui mais reposição em nosso estoque. Como alternativa de 7 cordas disponível para pronta entrega, contamos com o **Tagima TW-7 7 Cordas Aço Natural** por R$ 999,00 (ou R$ 949,05 à vista no PIX), que pode ser parcelado em até 12x sem juros de R$ 83,25.

Caso queira conhecer essas alternativas ou verificar outros instrumentos disponíveis, estamos à inteira disposição em nossa loja na Rua 14 de Maio, 3200 — Centro, Campo Grande/MS.

---
