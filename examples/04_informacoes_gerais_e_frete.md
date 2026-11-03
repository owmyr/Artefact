# Cenário 04 — Informações Gerais da Loja, Duplo Contato WhatsApp e Prazos de Frete

## Visão Geral do Cenário (Scenario Overview)
- **Arquivo:** `examples/04_informacoes_gerais_e_frete.md`
- **Session ID (SQLite):** `example_04_endereco_contatos_frete`
- **Total de Turnos:** 2
- **Objetivo e Regras Validadas:** Demonstra a consulta às políticas institucionais e logísticas da loja (Seções 1, 1.2, 2, 5 e 7). No Turno 1, informa o endereço completo em Campo Grande/MS (Rua 14 de Maio, 3200 — Centro, CEP 79202-333), horários de funcionamento e ambos os números oficiais de telefone/WhatsApp: `(67) 3341-4444` (Geral/Loja Física) e `(67) 3321-4500` (Atendimento Remoto e Suporte). No Turno 2, detalha a entrega local em Campo Grande e região metropolitana (grátis acima de R$ 500,00 ou taxa fixa de R$ 35,00 em 1 a 3 dias úteis) e o envio para outras cidades/estados via PAC (5 a 12 dias úteis), SEDEX (2 a 5 dias úteis) e Jadlog (3 a 8 dias úteis) com seguro incluso.

---

## Transcrição Turno a Turno (Turn-by-Turn Transcript)

### Turno 1

#### Cliente (User)
> Qual o endereço da loja, telefone de contato e horário de funcionamento?

#### Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-3.8-flash`
- **Ferramentas Invocadas (`tool_calls`):** `1`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

**Detalhes das Chamadas de Ferramentas:**
1. `consult_store_policies({"topic": "endereco telefone whatsapp horario funcionamento"})` *(solicitado por `gemini-3.8-flash`)*

#### Assistente Empório da Música (Assistant Response)

Aqui estão todas as informações oficiais de localização, contato e horário de atendimento da **Empório da Música** (Seções 1, 1.2, 2 e 7):

### Endereço Físico (Seção 1.2)
- **Razão Social:** Empório da Música Instrumentos Musicais Ltda. *(CNPJ: `12.345.678/0001-90`)*
- **Logradouro:** **Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, CEP 79202-333**

### Telefones e Canais de Contato (Seções 1.2 e 7)
Contamos com dois números oficiais para melhor atender você:
- **Telefone Fixo e WhatsApp Geral (Loja Física e Administração — Seção 1.2):** **`(67) 3341-4444`**
- **WhatsApp Exclusivo para Atendimento Remoto e Suporte (Seção 7):** **`(67) 3321-4500`**
- **E-mail Oficial:** `contato@emporiodamusica.com.br`

### Horário de Funcionamento (Seção 2.1 e 2.2)
- **Segunda a Sexta-feira:** **09:00 às 18:00** *(sem fechar para almoço)*
- **Sábados:** **09:00 às 13:00**
- **Domingos e Feriados (Nacionais, Estaduais de MS e Municipais de Campo Grande):** **Fechado**
- *(Em datas especiais como Black Friday e Semana da Música em novembro, ou no Aniversário da Loja em agosto, operamos em horários estendidos divulgados previamente.)*

Será um prazer receber sua visita na nossa loja no Centro de Campo Grande ou atender você pelo WhatsApp!

---

### Turno 2

#### Cliente (User)
> Vocês entregam em Campo Grande de motoboy? E se eu pedir para enviar um ukulele para São Paulo/SP, quais as opções e prazos?

#### Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-3.8-flash`
- **Ferramentas Invocadas (`tool_calls`):** `2`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

**Detalhes das Chamadas de Ferramentas:**
1. `consult_store_policies({"topic": "frete entrega motoboy correios pac sedex jadlog"})` *(solicitado por `gemini-3.8-flash`)*
2. `search_catalog({"category": "Ukuleles", "only_available": true})` *(solicitado por `gemini-3.8-flash`)*

#### Assistente Empório da Música (Assistant Response)

Sim! Fazemos entregas locais rápidas em **Campo Grande/MS** e também enviamos instrumentos com total segurança para **São Paulo/SP** e todo o Brasil! Confira as regras e prazos da **Seção 5 (Entregas e Frete)**:

### 1. Entrega em Campo Grande e Região Metropolitana (Seção 5.1)
- **Modalidade:** Entrega expressa via **transportadora própria / motoboy parceiro da loja**.
- **Prazo de Entrega:** **1 a 3 dias úteis** após a confirmação do pagamento.
- **Valor do Frete Local:**
 - **Frete Grátis** para compras **acima de R$ 500,00**;
 - **Taxa fixa de R$ 35,00** para compras de **até R$ 500,00**.

### 2. Envio de Ukulele para São Paulo/SP e Demais Estados (Seções 5.1 e 5.2)
Para envios fora de Campo Grande, o valor do frete é calculado conforme o **CEP de destino, peso e dimensões da embalagem**, com três opções de transporte:
1. **SEDEX (Correios):** Prazo estimado de **2 a 5 dias úteis** *(excelente opção para ukuleles com entrega rápida em SP)*;
2. **Transportadora Jadlog:** Prazo estimado de **3 a 8 dias úteis**;
3. **PAC (Correios):** Prazo estimado de **5 a 12 dias úteis**.

#### Segurança e Rastreamento no Envio (Seção 5.2):
- **Embalagem Especial Reforçada:** Todos os instrumentos são inspecionados antes do despacho e acondicionados com proteção interna contra impactos e variações climáticas.
- **Seguro Incluso:** Todo envio possui **seguro de carga contra extravio e avarias já incluso** no valor do frete.
- **Código de Rastreamento:** Enviado automaticamente por WhatsApp e e-mail em **até 24 horas úteis** após a postagem.

*(Caso queira aproveitar, temos **14 modelos de Ukuleles disponíveis em estoque** hoje, começando em **R$ 159,90** no **Shelby SU-21S Soprano Sunburst**!)*

---
