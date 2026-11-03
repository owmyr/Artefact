# Cenário 05 — Restrição Estrita de Escopo (Acessórios) e Guardrails Off-Topic

## Visão Geral do Cenário (Scenario Overview)
- **Arquivo:** `examples/05_fora_de_escopo_acessorios_e_guardrails.md`
- **Session ID (SQLite):** `example_05_fora_de_escopo_guardrails`
- **Total de Turnos:** 2
- **Objetivo e Regras Validadas:** Demonstra os guardrails operacionais da Empório da Música (Seções 1 e 7.1). No Turno 1, recusa educadamente o pedido de acessórios avulsos (encordoamento 0.10, cabo P10, pedal de overdrive e amplificador de estudo), explicando que a loja comercializa exclusivamente instrumentos musicais e sugerindo lojas parceiras de acessórios enquanto oferece ajuda para buscar instrumentos do catálogo. No Turno 2, recusa com simpatia solicitações fora do domínio da loja (script em Python e receita de bolo de cenoura) e mantém o foco no atendimento musical.

---

## Transcrição Turno a Turno (Turn-by-Turn Transcript)

### Turno 1

#### Cliente (User)
> Preciso comprar um jogo de cordas de aço 0.10, um cabo P10, um pedal de overdrive e um amplificador pequeno de estudo. Vocês têm?

#### Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-3.8-flash`
- **Ferramentas Invocadas (`tool_calls`):** `1`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

**Detalhes das Chamadas de Ferramentas:**
1. `consult_store_policies({"topic": "escopo acessorios cordas cabos pedais amplificadores"})` *(solicitado por `gemini-3.8-flash`)*

#### Assistente Empório da Música (Assistant Response)

Olá! Agradeço o seu contato com a **Empório da Música**.

Preciso informar que, conforme o nosso escopo de atuação (**Seções 1 e 7.1 das Políticas da Loja**), a **Empório da Música trabalha exclusivamente com a venda de instrumentos musicais** (como violões, guitarras, baixos, baterias, teclados/pianos e ukuleles).

Por esse motivo, **não comercializamos acessórios ou periféricos avulsos**, incluindo os itens que você mencionou:
- **Jogos de cordas / encordoamentos avulsos** (como aço 0.10);
- **Cabos de áudio** (P10, XLR, etc.);
- **Pedais ou pedaleiras de efeito** (como pedal de overdrive);
- **Amplificadores ou cubos de estudo**;
- Palhetas, capas/bags/cases avulsos, correias ou baquetas.

**Nossa recomendação:** Sugerimos que você procure **lojas parceiras especializadas em acessórios e equipamentos de áudio** para adquirir o encordoamento, o cabo P10, o pedal e o amplificador.

Por outro lado, se você estiver procurando uma **guitarra nova, um violão de aço/nylon, um baixo ou outro instrumento musical** para o seu setup, será um prazer mostrar as opções disponíveis em nosso catálogo! Gostaria de dar uma olhada em algum instrumento?

---

### Turno 2

#### Cliente (User)
> Ah, entendi! Aproveitando, você pode escrever um script em Python para ordenar uma lista e me dar uma receita de bolo de cenoura?

#### Telemetria de Execução (Model & Tools)
- **Modelo Gemini Utilizado (`model_used`):** `gemini-3.8-flash`
- **Ferramentas Invocadas (`tool_calls`):** `0`
- **Eventos de Fallback (`fallback_events`):** Nenhum (`0`)

*Nenhuma ferramenta externa invocada neste turno (resposta direta via guardrail do System Prompt).*

#### Assistente Empório da Música (Assistant Response)

Nosso canal de atendimento é dedicado exclusivamente a informações, vendas e suporte sobre **instrumentos musicais** da Empório da Música.

Por esse motivo, não realizamos tarefas fora desse escopo, como programação ou culinária. Se você tiver qualquer dúvida sobre nossos **violões, guitarras, baixos, baterias, teclados ou ukuleles**, condições de pagamento ou políticas da loja, estou à disposição para ajudar!

---
