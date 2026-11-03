"""Structured policy knowledge base extractor and query interface for Empório da Música.

Why: Transforms the unstructured 8-page PDF policy manual into a section-indexed,
structured Markdown knowledge base. Preserves critical contractual SLA tables,
installment tier matrices, and distinct phone contact channels for grounded LLM retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pypdf

from src.config import POLICIES_PDF

logger = logging.getLogger(__name__)

# Structured representation of all 10 store policy sections with preserved Markdown tables
STORE_POLICY_SECTIONS: dict[int, dict[str, Any]] = {
    1: {
        "section_id": 1,
        "title": "1. Sobre a Empório da Música",
        "keywords": ["historia", "loja", "sobre", "contato", "telefone", "cnpj", "endereco", "escopo", "acessorios"],
        "content_markdown": """### 1. Sobre a Empório da Música

A **Empório da Música** é uma loja especializada em instrumentos musicais, fundada em 2008 em Campo Grande, Mato Grosso do Sul. Com mais de 15 anos de atuação no mercado, somos referência regional na venda de instrumentos para músicos iniciantes, intermediários e profissionais.

Nosso catálogo abrange mais de 300 instrumentos de marcas nacionais e internacionais, incluindo guitarras, baixos, violões, baterias, teclados, instrumentos de sopro, cordas orquestrais e ukuleles.

> **Importante (Escopo Exclusivo)**: Trabalhamos **exclusivamente com instrumentos musicais**. Não comercializamos acessórios avulsos como cordas, palhetas, cabos, cases, pedais ou amplificadores. Pedidos de acessórios devem ser educadamente redirecionados para lojas parceiras.

#### 1.1 Missão
Democratizar o acesso a instrumentos musicais de qualidade na região Centro-Oeste, oferecendo atendimento especializado e preços competitivos, contribuindo para o desenvolvimento cultural e musical da comunidade.

#### 1.2 Dados da Empresa

| Campo | Informação |
|---|---|
| **Razão Social** | Empório da Música Instrumentos Musicais Ltda. |
| **Nome Fantasia** | Empório da Música |
| **CNPJ** | 12.345.678/0001-90 |
| **Endereço** | Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, CEP 79202-333 |
| **Telefone / WhatsApp Geral** | **(67) 3341-4444** |
| **E-mail Geral** | contato@emporiodamusica.com.br |
| **Fundação** | 2008 |
""",
    },
    2: {
        "section_id": 2,
        "title": "2. Horário de Funcionamento",
        "keywords": ["horario", "funcionamento", "aberto", "fechado", "domingo", "sabado", "feriado", "expediente"],
        "content_markdown": """### 2. Horário de Funcionamento

O atendimento presencial na loja física segue os horários abaixo. O atendimento via WhatsApp segue o mesmo horário, com respostas automáticas fora do expediente:

| Dia | Horário |
|---|---|
| **Segunda a Sexta-feira** | 09:00 às 18:00 |
| **Sábado** | 09:00 às 13:00 |
| **Domingo e Feriados** | Fechado |

*Em datas especiais (Black Friday, Aniversário da Loja, Natal), o horário de funcionamento pode ser estendido com aviso prévio em redes sociais e canais de atendimento.*
""",
    },
    3: {
        "section_id": 3,
        "title": "3. Formas de Pagamento e Parcelamento",
        "keywords": ["pagamento", "pix", "cartao", "credito", "debito", "boleto", "parcelamento", "parcelas", "juros", "split"],
        "content_markdown": """### 3. Formas de Pagamento

Aceitamos as seguintes formas de pagamento para compras presenciais e online:

| Forma de Pagamento | Condições | Observações |
|---|---|---|
| **PIX** | Pagamento à vista | **5% de desconto** sobre o preço de tabela (não-cumulativo com outras promoções) |
| **Cartão de Débito** | Pagamento à vista | Todas as principais bandeiras aceitas |
| **Cartão de Crédito** | Até 12x sem juros | Parcela mínima escalonada conforme faixa de parcelas |
| **Boleto Bancário** | Pagamento à vista | Compensação bancária em até 3 dias úteis |

#### 3.1 Regras de Parcelamento (Cartão de Crédito sem Juros)

| Faixa de Parcelas | Taxa de Juros | Parcela Mínima Exigida |
|---|---|---|
| **1x a 3x** | Sem juros (0%) | Mínimo de **R$ 50,00** por parcela |
| **4x a 6x** | Sem juros (0%) | Mínimo de **R$ 80,00** por parcela |
| **7x a 12x** | Sem juros (0%) | Mínimo de **R$ 100,00** por parcela |

- **Combinação de Formas de Pagamento (Split Payment)**: É permitida a divisão de pagamento (exemplo: entrada no PIX + saldo restante no Cartão de Crédito em até 12x) **exclusivamente para compras com valor total acima de R$ 2.000,00**.
""",
    },
    4: {
        "section_id": 4,
        "title": "4. Política de Trocas e Devoluções",
        "keywords": ["troca", "devolucao", "arrependimento", "defeito", "prazo", "reembolso", "estorno", "nao elegiveis", "boquilha"],
        "content_markdown": """### 4. Política de Trocas e Devoluções

A Empório da Música segue rigorosamente as diretrizes do Código de Defesa do Consumidor (Lei nº 8.078/90).

#### 4.1 Direito de Arrependimento (Compras Online)
- **Prazo**: Até **7 (sete) dias corridos** após a data de recebimento do produto (`estimated_delivery`/entrega). Não exige justificativa prévia.
- **Condições**: O produto deve estar em sua embalagem original, sem quaisquer sinais de uso ou desgaste, acompanhado de todos os acessórios, manuais e nota fiscal.
- **Custo de Envio**: O frete de devolução por arrependimento é **totalmente custeado pela loja**.
- **Reembolso**: Efetuado na mesma forma de pagamento original em até **10 dias úteis** após a recepção e conferência do item.

#### 4.2 Trocas por Defeito de Fabricação
- **Prazo com a Loja**: Até **30 (trinta) dias corridos** a contar da data da compra (`order_date`).
- **Após 30 dias**: O cliente deve acionar diretamente a assistência técnica autorizada do fabricante. A Empório da Música pode intermediar o processo mediante solicitação.
- **Exclusões**: Danos causados por mau uso, quedas, exposição a umidade excessiva ou regulagens/modificações não autorizadas não possuem cobertura.

#### 4.3 Trocas por Preferência (Cor, Modelo, Tamanho)
- **Prazo**: Até **7 (sete) dias corridos** da entrega, sujeito à disponibilidade de estoque do produto desejado.
- Produto deve estar em perfeito estado e na embalagem original lacrada. Diferenças de valor serão ajustadas (cobrança ou reembolso).

#### 4.4 Itens Não Elegíveis para Troca
- Instrumentos com personalização ou ajustes sob encomenda (setup de luthieria específico, regulagem customizada solicitada pelo cliente).
- Produtos adquiridos em queimas de estoque/liquidação com aviso explícito de *"venda final / sem troca"*.
- **Boquilhas de instrumentos de sopro**, por rígidas questões sanitárias e de higiene pessoal.
""",
    },
    5: {
        "section_id": 5,
        "title": "5. Política de Frete e Entregas",
        "keywords": ["frete", "entrega", "prazo", "correios", "pac", "sedex", "jadlog", "rastreamento", "campo grande", "motoboy"],
        "content_markdown": """### 5. Política de Frete e Entregas

#### 5.1 Entregas na Região Metropolitana de Campo Grande
- **Frete Grátis**: Para todos os pedidos com valor **acima de R$ 500,00**.
- **Taxa Fixa**: Para pedidos abaixo de R$ 500,00, aplica-se uma taxa fixa de entrega de **R$ 35,00**.
- **Prazo de Entrega**: De **1 a 3 dias úteis**.
- **Operação**: Entrega realizada por motoboy próprio da loja. O cliente é contatado por telefone/WhatsApp antes da saída para entrega.

#### 5.2 Entregas para Outras Cidades (Prazos e SLAs)

Para envios fora da Grande Campo Grande, utilizamos os Correios e transportadoras parceiras:

| Modalidade de Envio | Prazo Estimado | Rastreamento Online | Seguro de Carga |
|---|---|---|---|
| **PAC (Correios)** | 5 a 12 dias úteis | Sim (rastreamento total) | Incluído contra extravio/avaria |
| **SEDEX (Correios)** | 2 a 5 dias úteis | Sim (rastreamento expresso) | Incluído contra extravio/avaria |
| **Jadlog (.package)** | 3 a 8 dias úteis | Sim (rastreamento rodoviário) | Incluído contra extravio/avaria |

- Instrumentos de grande porte (baterias acústicas, pianos digitais de gabinete, contrabaixos acústicos) podem exigir cotação especial de frete rodoviário dedicado.
- Em caso de avaria aparente na embalagem no ato da entrega, o cliente deve recusar imediatamente o recebimento e notificar a loja.

#### 5.3 Código de Rastreamento
- O código de rastreamento é gerado e enviado automaticamente por e-mail e WhatsApp assim que o pedido é despachado.
- Formato padrão: `BR` seguido de 9 caracteres alfanuméricos e final `BR` (exemplo: `BRAB1234567BR`, `BRCX9876543BR`).
""",
    },
    6: {
        "section_id": 6,
        "title": "6. Promoções e Descontos",
        "keywords": ["promocao", "desconto", "black friday", "aniversario", "pix", "cumulativo", "regras", "tabela"],
        "content_markdown": """### 6. Promoções e Descontos

#### 6.1 Campanhas Promocionais Periódicas
- **Aniversário da Loja (Agosto)**: Descontos de 10% a 25% em instrumentos selecionados.
- **Black Friday (Novembro)**: Descontos de 15% a 30% em produtos destacados.
- **Volta às Aulas (Fevereiro)**: Condições facilitadas em violões e teclados estudantis.
- **Semana do Músico (Novembro)**: Promoções comemorativas ao Dia do Músico (22 de novembro).
- **Queima de Estoque**: Descontos pontuais para renovação de mostruário.

#### 6.2 Regras Estritas de Promoções (Não-Cumulatividade)
- **Não-Cumulatividade do Desconto PIX**: O desconto de 5% à vista via PIX **não se acumula** com itens em promoção ativa (`is_active = 1`). Para produtos em promoção, o preço promocional já representa a condição final à vista.
- **Promoções Expiradas**: Se uma promoção estiver inativa (`is_active = 0`), o desconto anterior não pode ser concedido. O cliente deve ser informado com transparência sobre o término da campanha e receber a cotação do **preço de tabela atual** com o desconto padrão de 5% no PIX.
- **Disponibilidade**: Promoções são válidas enquanto durarem os estoques físicos. Produtos esgotados não geram direito a reserva de preço promocional (*rain check*).
- **Transparência**: Toda cotação promocional deve expor claramente o preço original de tabela, o percentual de desconto e o valor final.
""",
    },
    7: {
        "section_id": 7,
        "title": "7. Atendimento via WhatsApp",
        "keywords": ["whatsapp", "atendimento", "suporte", "contato", "fluxo", "diretrizes", "fora de estoque", "descontinuado", "reclamacao"],
        "content_markdown": """### 7. Atendimento via WhatsApp

O canal exclusivo de WhatsApp para atendimento remoto, dúvidas e televendas é:
- **WhatsApp Suporte Remoto**: **(67) 3321-4500**

*(Nota: Para contato com a loja física ou administração geral, utilize também o telefone fixo/WhatsApp principal: **(67) 3341-4444**).*

#### 7.1 Diretrizes de Atendimento
- **Tom de Voz**: Informal mas profissional. Amigável, acolhedor e conhecedor do universo musical — como conversar com um amigo especialista em música. Sem robotização.
- **Tempo de Resposta**: Até 5 minutos no horário de funcionamento comercial. Fora do expediente, fornecer mensagem automática com previsão de abertura.
- **Informações Precisas**: Nunca estimar preços ou estoque de cabeça; sempre consultar o catálogo e a base de pedidos oficial.
- **Escopo Exclusivo**: Informar com clareza que a loja trabalha exclusivamente com instrumentos musicais. Pedidos de acessórios (cordas, cabos, palhetas, pedais, amplificadores, cases) devem ser educadamente recusados e redirecionados para lojas parceiras quando possível.

#### 7.2 Fluxo de Atendimento Padrão
1. **Saudação**: Cumprimentar pelo nome (quando disponível) e acolher cordialmente.
2. **Entendimento**: Identificar precisamente a intenção do cliente (compra, especificações técnicas, status de pedido, suporte a troca).
3. **Consulta**: Executar a busca oficial nos sistemas de inventário ou pedidos.
4. **Resposta**: Apresentar alternativas, preços à vista e parcelados com total clareza.
5. **Fechamento**: Checar se restam dúvidas e encerrar cordialmente.

#### 7.3 Tratamento de Situações Especiais
- **Produto Fora de Estoque (`stock_quantity == 0`)**: Informar que está temporariamente esgotado e sugerir proativamente **até 3 alternativas disponíveis** na mesma categoria e faixa de preço similar.
- **Produto Descontinuado (`status == 'discontinued'`)**: Informar com clareza que o modelo saiu de linha e sugerir modelos sucessores ou equivalentes disponíveis.
- **Promoção Vencida / Expirada**: Agir com total transparência informando que a campanha encerrou. Apresentar o preço de tabela atual e destacar o benefício do desconto de 5% no PIX.
- **Reclamações ou Avarias**: Demonstrar empatia imediata, abrir registro interno de suporte e estipular o prazo formal de retorno de até **24 horas úteis**.
""",
    },
    8: {
        "section_id": 8,
        "title": "8. Garantia",
        "keywords": ["garantia", "legal", "fabricante", "defeito", "90 dias", "cobertura", "mau uso"],
        "content_markdown": """### 8. Garantia

#### 8.1 Garantia Legal
Em cumprimento ao Código de Defesa do Consumidor (CDC), todos os instrumentos musicais comercializados pela Empório da Música contam com **garantia legal de 90 (noventa) dias corridos** contra quaisquer defeitos de fabricação, contados a partir da data de entrega ao cliente.

#### 8.2 Garantia Contratual do Fabricante
Além da garantia legal obrigatória, as marcas parceiras oferecem garantias complementares que geralmente variam de **6 meses a 2 anos** (conforme certificado que acompanha o instrumento). A loja fornece suporte no direcionamento à rede autorizada de assistência.

#### 8.3 O que NÃO é coberto pela Garantia
- Desgaste natural decorrente do uso regular (fricção em trastes, oxidação de cordas, feltros de bateria, palhetas de madeira de instrumentos de sopro).
- Danos causados por quedas, choques mecânicos, acondicionamento em locais sob calor ou umidade extremos.
- Danos causados por manutenções ou modificações de circuito/luthieria realizadas por pessoas não autorizadas.
- Danos puramente estéticos posteriores ao recebimento sem ressalva na entrega.
""",
    },
    9: {
        "section_id": 9,
        "title": "9. Privacidade e Proteção de Dados (LGPD)",
        "keywords": [
            "lgpd",
            "privacidade",
            "dados",
            "exclusao",
            "seguranca",
            "cpf",
            "email",
            "telefone",
            "consulta pedido",
        ],
        "content_markdown": """### 9. Privacidade e Proteção de Dados (LGPD)

A Empório da Música atua em estrita conformidade com a Lei Geral de Proteção de Dados Pessoais (LGPD — Lei nº 13.709/2018).

#### 9.1 Finalidade do Tratamento
Os dados cadastrais de clientes (nome completo, telefone, e-mail, CPF e endereço) são tratados única e exclusivamente para:
- Processamento, faturamento fiscal e envio logístico de pedidos.
- Notificações transacionais sobre o andamento e rastreamento de entregas.
- Comunicação de promoções (somente quando expressamente autorizada pelo titular).
- Cumprimento de obrigações legais e regulatórias perante órgãos fiscais.

#### 9.2 Segurança, Sigilo e Exclusão de Dados
- Os dados jamais são comercializados ou cedidos a terceiros para publicidade ou marketing não solicitado.
- Para consultas a detalhes de pedidos anteriores ou status de entrega, é **obrigatória a validação de segurança**: o cliente deve fornecer o número do pedido (`order_id`) associado a uma confirmação de identidade (nome completo, e-mail ou telefone cadastrado).
- **Direito de Exclusão de Dados**: O cliente pode solicitar a exclusão de seus dados pessoais a qualquer momento entrando em contato pelo WhatsApp ou e-mail oficial da loja.
""",
    },
    10: {
        "section_id": 10,
        "title": "10. Disposições Finais",
        "keywords": ["disposicoes finais", "regras", "validade", "governanca", "atualizacao", "versao"],
        "content_markdown": """### 10. Disposições Finais

Este manual constitui o documento oficial de diretrizes operacionais e de relacionamento com clientes da Empório da Música. Suas regras devem ser rigorosamente seguidas por atendentes humanos e pelo assistente virtual de inteligência artificial.

- **Atualizações**: As diretrizes são revisadas periodicamente pela diretoria comercial da empresa.
- **Dúvidas Operacionais**: Casos omissos ou situações atípicas devem ser escalados para a gerência de atendimento antes de qualquer promessa ao consumidor.
- **Versão Atual**: Versão 2.1 — Junho de 2025.
- **Lema**: *Empório da Música — Sua música começa aqui.*
""",
    },
}


def extract_raw_pdf_text(pdf_path: Path | str | None = None) -> str:
    """Extract and concatenate text from all pages of the store policies PDF.

    Why: Serves as a diagnostic and verification function to ensure the source PDF
    is readable by pypdf and accessible in the file environment.
    """
    path = Path(pdf_path) if pdf_path is not None else POLICIES_PDF
    if not path.exists():
        logger.warning(f"PDF policies file not found at: {path}")
        return ""

    try:
        reader = pypdf.PdfReader(str(path))
        extracted_pages: list[str] = []
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            # Clean up tokenized spaces between words
            cleaned = " ".join(line.strip() for line in text.split("\n") if line.strip())
            extracted_pages.append(f"--- Página {idx + 1} ---\n{cleaned}")
        return "\n\n".join(extracted_pages)
    except Exception as exc:
        logger.error(f"Error extracting PDF text from {path}: {exc}")
        return ""


def get_all_policies() -> dict[int, dict[str, Any]]:
    """Retrieve the entire collection of 10 structured policy sections.

    Why: Gives tools and LLM prompt constructors direct access to the indexed
    markdown policy corpus.
    """
    return STORE_POLICY_SECTIONS


def get_policy_section(section_id: int | str) -> str:
    """Retrieve the markdown content of a specific policy section by number.

    Why: Allows deterministic retrieval of individual policy sections (e.g. 3 for payment,
    4 for returns, 5 for shipping) without token bloat in LLM contexts.
    """
    try:
        sec_num = int(section_id)
    except (ValueError, TypeError):
        return f"Seção inválida: {section_id}. As seções disponíveis são de 1 a 10."

    section = STORE_POLICY_SECTIONS.get(sec_num)
    if not section:
        return f"Seção {sec_num} não encontrada. As seções disponíveis são de 1 a 10."

    return section["content_markdown"]


def search_policies(query: str) -> list[dict[str, Any]]:
    """Search policy sections by matching terms against titles, keywords, and content.

    Why: Empowers the agent ReAct tool to query policy rules by topic (e.g., 'frete',
    'devolução', 'garantia', 'parcelamento') with fast local indexing.
    """
    q = query.lower().strip()
    if not q:
        return []

    tokens = [t for t in q.split() if len(t) > 2]
    results: list[dict[str, Any]] = []

    for sec_id, data in STORE_POLICY_SECTIONS.items():
        title = data["title"].lower()
        content = data["content_markdown"].lower()
        keywords = [k.lower() for k in data["keywords"]]

        score = 0
        # Direct keyword matches
        for kw in keywords:
            if kw in q or any(t in kw for t in tokens):
                score += 5

        # Title match
        if any(t in title for t in tokens):
            score += 4

        # Content matches
        for t in tokens:
            count = content.count(t)
            score += min(count, 3)

        if score > 0:
            results.append({
                "section_id": sec_id,
                "title": data["title"],
                "score": score,
                "content_markdown": data["content_markdown"],
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def get_contact_info() -> dict[str, str]:
    """Return explicit store contact information preserving both official channels.

    Why: Satisfies the requirement in AGENTS.md Section 4.5 to clearly distinguish
    the general store contact (67) 3341-4444 from the dedicated remote WhatsApp (67) 3321-4500.
    """
    return {
        "store_name": "Empório da Música Instrumentos Musicais Ltda.",
        "general_phone_whatsapp": "(67) 3341-4444",
        "remote_support_whatsapp": "(67) 3321-4500",
        "email": "contato@emporiodamusica.com.br",
        "address": "Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, CEP 79202-333",
        "hours_mon_fri": "09:00 às 18:00",
        "hours_sat": "09:00 às 13:00",
        "hours_sun_holidays": "Fechado",
    }


if __name__ == "__main__":
    print("Verifying Policy Knowledge Base...")
    raw_pdf = extract_raw_pdf_text()
    print(f"Extracted PDF characters: {len(raw_pdf)}")
    assert len(raw_pdf) > 1000, "PDF extraction failed or file empty"

    sections = get_all_policies()
    print(f"Total structured sections: {len(sections)} (Expected: 10)")
    assert len(sections) == 10, f"Expected 10 sections, got {len(sections)}"

    # Check Markdown tables in Section 3 and Section 5
    sec3 = get_policy_section(3)
    assert "| 1x a 3x |" in sec3 or "R$ 50,00" in sec3, "Section 3 installment tier missing"
    assert "R$ 80,00" in sec3 and "R$ 100,00" in sec3, "Installment thresholds missing"

    sec5 = get_policy_section(5)
    assert "PAC (Correios)" in sec5 and "SEDEX (Correios)" in sec5 and "Jadlog" in sec5, "Shipping SLAs missing"

    # Check both contact numbers
    contacts = get_contact_info()
    print("Store Contacts:")
    print(f"  General Phone: {contacts['general_phone_whatsapp']}")
    print(f"  Remote WhatsApp: {contacts['remote_support_whatsapp']}")
    assert contacts["general_phone_whatsapp"] == "(67) 3341-4444"
    assert contacts["remote_support_whatsapp"] == "(67) 3321-4500"

    # Test policy search
    pix_results = search_policies("pix parcelamento desconto")
    print(f"Search 'pix parcelamento desconto' found {len(pix_results)} matching sections:")
    for res in pix_results[:2]:
        print(f"  - Section {res['section_id']}: {res['title']} (score {res['score']})")

    print("\nAll Policy Knowledge Base verifications passed successfully!")
