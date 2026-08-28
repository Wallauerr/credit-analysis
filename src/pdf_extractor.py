"""
Module for extracting data from the Serasa PDF report.
Extracts the relevant fields for the credit analysis.
"""

import re
from datetime import datetime


def parse_money(value):
    """Convert 'R$ 1.234,56' or 'R$ 5,76 milhões' to a float number."""
    if value is None:
        return None
    text = str(value).strip()

    # Remove R$ prefix
    text = text.replace("R$", "").replace("r$", "").strip()

    # Handle millions/thousands
    mult = 1
    if "milh" in text.lower():
        mult = 1_000_000
        text = (
            text.lower()
            .replace("milhões", "")
            .replace("milhao", "")
            .replace("milhões", "")
        )
    elif "bilh" in text.lower():
        mult = 1_000_000_000
        text = (
            text.lower()
            .replace("bilhões", "")
            .replace("bilhao", "")
            .replace("bilhões", "")
        )
    elif "mil" in text.lower() and "milh" not in text.lower():
        # Careful: avoid 'milhão'
        mult = 1000
        text = text.lower().replace("mil", "").replace("mil", "")

    # Remove extra currency symbols
    text = text.replace(".", "").replace(",", ".").strip()
    text = re.sub(r"[^0-9.]", "", text)

    try:
        return float(text) * mult
    except (ValueError, TypeError):
        return None


def extract_pdf_data(pdf_path):
    """
    Extract the relevant fields from the Serasa PDF.
    Returns a dictionary with the fields.
    """
    import pdfplumber

    all_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text += text + "\n"

    return parse_serasa_text(all_text)


def parse_serasa_text(text):
    """
    Extract structured fields from the raw Serasa text.
    """
    data = {}

    # --- CNPJ ---
    cnpj_match = re.search(r"CNPJ:\s*([\d.\/-]+)", text)
    if cnpj_match:
        data["cnpj"] = cnpj_match.group(1).strip()

    # --- Legal name (line after CNPJ) ---
    legal_match = re.search(r"CNPJ:\s*[\d.\/-]+\s*\|\s*([^\n]+)", text)
    if legal_match:
        data["legal_name"] = legal_match.group(1).strip()
        data["legal_name"] = re.sub(r"\s*\|.*$", "", data["legal_name"]).strip()

    # --- Serasa Score ---
    score_match = re.search(
        r"Serasa Score Empresas\s*\n.*?(\d{3})\s*\n?\s*(?:Risco mínimo|Baixo risco|Risco moderado|Alto risco)",
        text,
    )
    if not score_match:
        score_match = re.search(
            r"probabilidade da empresa pagar suas contas em dia nos próximos 6 meses\s*\n\s*(\d{3})",
            text,
        )
    if not score_match:
        score_match = re.search(
            r"\n(\d{3})\s*(?:Risco mínimo|Risco baixo)\s*\n0\s+500\s+1000", text
        )
    if score_match:
        data["serasa_score"] = int(score_match.group(1))

    # --- Share capital ---
    capital_match = re.search(r"Capital social[\s\S]{0,120}?R\$\s*([\d\.,]{2,})", text)
    if capital_match:
        data["share_capital"] = parse_money(f"R$ {capital_match.group(1)}")
    if "share_capital" not in data:
        capital_match2 = re.search(r"Capital social\s*\n?\s*R\$\s*([\d\.,]+)", text)
        if capital_match2:
            data["share_capital"] = parse_money(f"R$ {capital_match2.group(1)}")

    # --- Estimated monthly revenue ---
    # Pattern: "R$ 5,76 milhões ao ano" (annual revenue)
    rev_match = re.search(
        r"R\$\s*([\d\.,]+\s*(?:milhões|milhão|milhao|milhes|bilhões|bilhão|mil))\s*ao\s*ano",
        text,
    )
    if rev_match:
        annual_rev = parse_money(f"R$ {rev_match.group(1)}")
        if annual_rev:
            data["annual_revenue"] = annual_rev
            data["monthly_revenue"] = round(annual_rev / 12, 2)
    else:
        rev_match2 = re.search(r"Faturamento\s*(?:mensal)?\s*R\$\s*([\d\.,]+)", text)
        if rev_match2:
            data["monthly_revenue"] = parse_money(f"R$ {rev_match2.group(1)}")

    # --- Registration status ---
    status_match = re.search(
        r"Situa[çc][ãa]o Cadastral\s*\n?\s*\n?\s*(ATIVA|INATIVA|SUSPENSA|BAIXADA)", text
    )
    if not status_match:
        status_match = re.search(r"\b(ATIVA|INATIVA|SUSPENSA|BAIXADA)\b", text)
    if status_match:
        data["registration_status"] = status_match.group(1)

    # --- Restrictions/protests ---
    if "Sem registros" in text:
        data["has_restrictions"] = False
    elif "Total de dívidas" in text:
        debt_match = re.search(r"Total de d[eê]vidas:\s*R\$\s*([\d\.,]+)", text)
        if debt_match:
            data["total_debt"] = parse_money(f"R$ {debt_match.group(1)}")
            data["has_restrictions"] = data["total_debt"] > 0

    # --- Serasa recommendation ---
    rec_match = re.search(
        r"(Baixíssimo Risco|Baixo Risco|Risco Moderado|Alto Risco)", text
    )
    if rec_match:
        data["serasa_recommendation"] = rec_match.group(1)

    # --- Serasa suggested monthly limit ---
    limit_match = re.search(r"Limite mensal sugerido\*\*\s*\n\s*R\$\s*([\d\.,]+)", text)
    if not limit_match:
        limit_match = re.search(r"Limite mensal sugerido\s*\nR\$\s*([\d\.,]+)", text)
    if limit_match:
        data["serasa_suggested_limit"] = parse_money(f"R$ {limit_match.group(1)}")

    # --- Market time (years) ---
    founded_match = re.search(r"Fund[açã]ao em\s*\n?\s*(\d{2}/\d{2}/\d{4})", text)
    if not founded_match:
        founded_match = re.search(r"Cadastral\s*(\d{2}/\d{2}/\d{4})", text)
    if founded_match:
        try:
            founded = datetime.strptime(founded_match.group(1), "%d/%m/%Y")
            today = datetime.now()
            years = today.year - founded.year
            if (today.month, today.day) < (founded.month, founded.day):
                years -= 1
            data["market_years"] = max(years, 0)
        except ValueError:
            pass
    if "market_years" not in data:
        years_match = re.search(r"(\d{1,2})\s*anos\s*$", text, re.MULTILINE)
        if years_match:
            data["market_years"] = int(years_match.group(1))

    # --- City/State ---
    city_match = re.search(
        r"(?:INDUSTRIAL|CENTRO|QUALQUER\s+BAIRRO)[^,]*,\s*([A-ZÇÁÉÍÓÚÃÕ\- ]+)\s*-\s*([A-Z]{2})",
        text,
    )
    if not city_match:
        addr_match = re.search(
            r"Endereço:.*?,\s*([A-ZÇÁÉÍÓÚÃÕ\- ]+)\s*-\s*([A-Z]{2}),", text
        )
        if addr_match:
            data["city"] = addr_match.group(1).strip()
            data["state"] = addr_match.group(2)
    else:
        data["city"] = city_match.group(1).strip()
        data["state"] = city_match.group(2)

    # --- Segment / business activity ---
    seg_match = re.search(r"Ramo de atividade econômica:\s*([^\n]+)", text)
    if seg_match:
        data["segment"] = seg_match.group(1).strip()

    return data


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    data = extract_pdf_data(pdf_path)
    print("=== Extracted PDF data ===")
    for k, v in data.items():
        print(f"  {k}: {v}")
