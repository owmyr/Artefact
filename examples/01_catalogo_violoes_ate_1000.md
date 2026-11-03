# Cenário 01 — Catálogo de Violões até R$ 1.000 e Tratamento de Indisponíveis

## 📋 Visão Geral do Cenário (Scenario Overview)
- **Arquivo:** `examples/01_catalogo_violoes_ate_1000.md`
- **Session ID (SQLite):** `example_01_violoes_ate_1000`
- **Total de Turnos:** 2
- **Objetivo e Regras Validadas:** Demonstra a filtragem determinística de violões disponíveis até R$ 1.000,00 (listando exatamente os 12 modelos com `status='active'` e `stock_quantity > 0`) e, no segundo turno, o tratamento transparente de itens indisponíveis: `Giannini GF-3D` (`product_id=96`, `stock_quantity=0` — esgotado) e `Shelby SN-7C` (`product_id=113`, `status='discontinued'` — fora de linha), com sugestão proativa de alternativas disponíveis como o 7 cordas `Tagima TW-7` (R$ 999,00) e o `Tagima Woodstock` (R$ 899,00) conforme a Seção 7.3 das políticas.

---

## 💬 Transcrição Turno a Turno (Turn-by-Turn Transcript)

### Turno 1

#### 🧑‍🎤 Cliente (User)
> Olá! Quais opções de violões disponíveis vocês têm custando até R$ 1000?

#### 🔍 Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-2.5-flash`
- **Ferramentas Invocadas (`tool_calls`):** `1`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

**Detalhes das Chamadas de Ferramentas:**
1. `search_catalog({"category": "Violões", "max_price": 1000.0, "only_available": true})` *(solicitado por `gemini-2.5-flash`)*

#### 🎸 Assistente Empório da Música (Assistant Response)

Olá! Seja muito bem-vindo(a) à **Empório da Música**! 🎸🎶

Atualmente temos **12 opções de violões disponíveis para pronta entrega** (`status='active'` e com estoque disponível) custando até **R$ 1.000,00**.

Lembrando que, como nenhum desses modelos está em promoção ativa no momento, todos contam com **5% de desconto para pagamento à vista via PIX** (Seção 3):

1. **Tagima Memphis AC-39 Nylon Natural** *(ID 83)*
   - **Preço de Tabela:** R$ 429,90 | **À vista no PIX (-5%):** **R$ 408,40**
   - **Especificações:** Cordas de Nylon (Acústico), Tampo em *Linden*, Cor *Natural* | **Estoque:** 15 un.
2. **Rozini RC-104 Nylon Estudante** *(ID 85)*
   - **Preço de Tabela:** R$ 459,90 | **À vista no PIX (-5%):** **R$ 436,90**
   - **Especificações:** Cordas de Nylon (Acústico), Tampo em *Spruce*, Cor *Natural* | **Estoque:** 10 un.
3. **Shelby SN-100 Folk Aço Preto** *(ID 89)*
   - **Preço de Tabela:** R$ 549,00 | **À vista no PIX (-5%):** **R$ 521,55**
   - **Especificações:** Cordas de Aço (Acústico), Tampo em *Linden*, Cor *Preto* | **Estoque:** 5 un.
4. **Giannini GF-1R Aço Folk Sunburst** *(ID 88)*
   - **Preço de Tabela:** R$ 579,90 | **À vista no PIX (-5%):** **R$ 550,90**
   - **Especificações:** Cordas de Aço (Acústico), Tampo em *Spruce*, Cor *Sunburst* | **Estoque:** 7 un.
5. **Yamaha C40 Nylon Natural** *(ID 81)*
   - **Preço de Tabela:** R$ 599,90 | **À vista no PIX (-5%):** **R$ 569,90**
   - **Especificações:** Cordas de Nylon (Acústico), Tampo em *Spruce*, Cor *Natural* | **Estoque:** 12 un.
6. **Giannini GN-15 Nylon Cedr Natural** *(ID 84)*
   - **Preço de Tabela:** R$ 689,00 | **À vista no PIX (-5%):** **R$ 654,55**
   - **Especificações:** Cordas de Nylon (Acústico), Tampo em *Cedro*, Cor *Natural* | **Estoque:** 6 un.
7. **Yamaha F310 Aço Natural** *(ID 87)*
   - **Preço de Tabela:** R$ 699,90 | **À vista no PIX (-5%):** **R$ 664,90**
   - **Especificações:** Cordas de Aço (Acústico), Tampo em *Spruce*, Cor *Natural* | **Estoque:** 14 un.
8. **Tagima Dallas Tuner Aço Natural** *(ID 86)*
   - **Preço de Tabela:** R$ 749,00 | **À vista no PIX (-5%):** **R$ 711,55**
   - **Especificações:** Cordas de Aço (Acústico), Tampo em *Spruce*, Cor *Natural* | **Estoque:** 9 un.
9. **Shelby SGD-195E Elétrico Aço Sunburst** *(ID 107)*
   - **Preço de Tabela:** R$ 799,00 | **À vista no PIX (-5%):** **R$ 759,05**
   - **Especificações:** Cordas de Aço (Eletroacústico), Tampo em *Spruce*, Cor *Sunburst* | **Estoque:** 6 un.
10. **Yamaha C70 Nylon Natural** *(ID 82)*
   - **Preço de Tabela:** R$ 849,00 | **À vista no PIX (-5%):** **R$ 806,55**
   - **Especificações:** Cordas de Nylon (Acústico), Tampo em *Spruce Sólido*, Cor *Natural* | **Estoque:** 8 un.
11. **Tagima Woodstock Dreadnought Natural** *(ID 91)*
   - **Preço de Tabela:** R$ 899,00 | **À vista no PIX (-5%):** **R$ 854,05**
   - **Especificações:** Cordas de Aço (Acústico), Tampo em *Spruce*, Cor *Natural* | **Estoque:** 11 un.
12. **Tagima TW-7 7 Cordas Aço Natural** *(ID 112)*
   - **Preço de Tabela:** R$ 999,00 | **À vista no PIX (-5%):** **R$ 949,05**
   - **Especificações:** Cordas de Aço (Acústico), Tampo em *Spruce*, Cor *Natural* | **Estoque:** 6 un.

*(Observação de transparência: Os modelos **Giannini GF-3D Dreadnought Sunburst** [ID 96, R$ 799,90] e **Shelby SN-7C 7 Cordas Nylon Natural** [ID 113, R$ 749,00] não foram incluídos na lista de pronta entrega pois encontram-se, respectivamente, sem estoque no momento e descontinuado.)*

Gostaria de ver os detalhes de parcelamento sem juros de algum desses violões ou busca preferência por cordas de **nylon** ou **aço**?

---

### Turno 2

#### 🧑‍🎤 Cliente (User)
> Ouvi falar muito bem do Giannini GF-3D e do violão de 7 cordas Shelby SN-7C. Vocês têm algum deles em estoque?

#### 🔍 Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-2.5-flash`
- **Ferramentas Invocadas (`tool_calls`):** `2`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

**Detalhes das Chamadas de Ferramentas:**
1. `search_catalog({"query": "Giannini GF-3D"})` *(solicitado por `gemini-2.5-flash`)*
2. `search_catalog({"query": "Shelby SN-7C"})` *(solicitado por `gemini-2.5-flash`)*

#### 🎸 Assistente Empório da Música (Assistant Response)

Consultei nosso estoque em tempo real e aqui está a situação exata desses dois modelos:

### 1. Giannini GF-3D Dreadnought Sunburst (`product_id=96`)
- **Status:** **Fora de estoque / Esgotado temporariamente** (`status='active'`, porém `stock_quantity=0`).
- **Preço de referência:** R$ 799,90.
- **Alternativas disponíveis para pronta entrega (mesma categoria e faixa de preço — Seção 7.3):**
  - **Tagima Woodstock Dreadnought Natural** *(ID 91)* — **R$ 899,00** (ou **R$ 854,05** à vista no PIX com 5% de desconto | Estoque: 11 un.)
  - **Shelby SGD-195E Elétrico Aço Sunburst** *(ID 107)* — **R$ 799,00** (ou **R$ 759,05** à vista no PIX com 5% de desconto | Estoque: 6 un.)
  - **Yamaha C70 Nylon Natural** *(ID 82)* — **R$ 849,00** (ou **R$ 806,55** à vista no PIX com 5% de desconto | Estoque: 8 un.)

### 2. Violão 7 Cordas Shelby SN-7C Nylon Natural (`product_id=113`)
- **Status:** **Produto Descontinuado / Fora de linha** (`status='discontinued'`). Por ter saído de linha, não trabalhamos mais com a reposição deste modelo.
- **Alternativas disponíveis de 7 cordas em estoque (Seção 7.3):**
  - **Tagima TW-7 7 Cordas Aço Natural** *(ID 112)* — **R$ 999,00** (ou **R$ 949,05** à vista no PIX com 5% de desconto | Estoque: 6 un.)
  - **Giannini GWNE-7 7 Cordas Nylon Natural** *(ID 110)* — **R$ 1.149,00** (ou **R$ 1.091,55** à vista no PIX com 5% de desconto | Estoque: 4 un.)
  - **Rozini RV-174 7 Cordas Nylon Natural** *(ID 109)* — **R$ 1.299,00** (ou **R$ 1.234,05** à vista no PIX com 5% de desconto | Estoque: 5 un.)

Se você busca um Dreadnought de aço na faixa do GF-3D, o **Tagima Woodstock Dreadnought Natural** (**R$ 899,00** / **R$ 854,05 no PIX**) ou o **Shelby SGD-195E Elétrico Aço Sunburst** (**R$ 799,00** / **R$ 759,05 no PIX**) são excelentes escolhas! Já para **7 cordas** até R$ 1.000,00, temos o **Tagima TW-7 7 Cordas Aço Natural** por **R$ 999,00** (**R$ 949,05 no PIX**). Qual deles combina mais com o seu som?

---
