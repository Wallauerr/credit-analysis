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
    pages_data = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text += text + "\n"
            words = page.extract_words(
                keep_blank_chars=True, x_tolerance=2, y_tolerance=2
            )
            pages_data.append(words)

    data = parse_serasa_text(all_text)
    data.update(_parse_annotations(pages_data))
    data.update(_parse_queries(pages_data))
    return data


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
    # Padrão do formato 2025+: "340 de 1000 Risco médio"
    score_match = re.search(
        r"(\d{1,3})\s*de\s*1000\s*\n?\s*Risco\s*(mínimo|baixo|moderado|médio|alto)",
        text,
    )
    if not score_match:
        # Padrão do formato 2026+: "Serasa Score Empresas\n...\n835 Risco mínimo"
        score_match = re.search(
            r"Serasa Score Empresas\s*\n.*?(\d{3})\s*\n?\s*(?:Risco mínimo|Baixo risco|Risco moderado|Alto risco)",
            text,
        )
    if not score_match:
        score_match = re.search(
            r"probabilidade da empresa pagar suas contas em dia nos próximos (?:6|12) meses\s*\n\s*(\d{3})",
            text,
        )
    if not score_match:
        score_match = re.search(
            r"\n(\d{3})\s*(?:Risco mínimo|Risco baixo|Risco médio)\s*\n?0\s*[0-9 ]*1000",
            text,
        )
    if not score_match:
        score_match = re.search(
            r"(\d{3})\s*\n?\s*Ris(?:co|k)\s*(?:baixo|mínimo|médio|moderado|alto)\s*\n?\s*A\s*pontua[çc][ãa]o\s*enquadra-se",
            text,
        )
    if score_match:
        data["serasa_score"] = int(score_match.group(1))

    # --- Share capital ---
    # Padrão 2026: "Capital social R$ 102.000,00" ou "Capital social\nR$"
    capital_match = re.search(r"Capital social[\s\S]{0,120}?R\$\s*([\d\.,]{2,})", text)
    if capital_match:
        data["share_capital"] = parse_money(f"R$ {capital_match.group(1)}")
    if "share_capital" not in data:
        capital_match2 = re.search(r"Capital social\s*\n?\s*R\$\s*([\d\.,]+)", text)
        if capital_match2:
            data["share_capital"] = parse_money(f"R$ {capital_match2.group(1)}")
    # Padrão 2025: valor antes do rótulo, ex.: "R$114.118.632,00 ... Capital social"
    if "share_capital" not in data:
        capital_match3 = re.search(
            r"R\$\s*([\d\.,]{4,})\s*[\s\S]{0,60}?Capital social", text
        )
        if capital_match3:
            data["share_capital"] = parse_money(f"R$ {capital_match3.group(1)}")

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

    # --- Restrictions / total debt ---
    # Formato 2026: "Total de dívidas: R$ X" ou "Sem registros"
    if "Total de dívidas" in text:
        debt_match = re.search(r"Total de d[eê]vidas:\s*R\$\s*([\d\.,]+)", text)
        if debt_match:
            data["total_debt"] = parse_money(f"R$ {debt_match.group(1)}")
            data["has_restrictions"] = (data["total_debt"] or 0) > 0
    if "has_restrictions" not in data:
        # Formato 2025: "Total em anotações negativas N ocorrência(s)"
        oc_match = re.search(r"Total em anotações negativas\s*\n?\s*(\d+)\s*ocorr", text)
        if oc_match:
            n = int(oc_match.group(1))
            data["has_restrictions"] = n > 0
    if "has_restrictions" not in data:
        if "Sem registros" in text or "Sem ocorrências" in text:
            data["has_restrictions"] = False

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
    # "N anos" literal (formato 2025+: "ATIVA 28 anos CACAPAVA/SP ...")
    years_literal = re.search(r"(\d{1,2})\s*anos\s*\n?[A-ZÁÉÍÓÚÇÀÂÃÔ]", text)
    if years_literal:
        data["market_years"] = int(years_literal.group(1))
    if "market_years" not in data:
        founded_match = re.search(r"Funda[çc][ãa]o em\s*\n?\s*(\d{2}/\d{2}/\d{4})", text)
        if not founded_match:
            founded_match = re.search(r"Funda[çc][ãa]o em\s*(\d{2}/\d{2}/\d{4})\s*\n?\s*Munic[íi]pio", text)
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

    # --- Default probability ---
    prob_match = re.search(r"([\d,]+)%\s*\n?(?:Mínimo|Baixo|Moderado|Médio|Alto)", text)
    if prob_match:
        data["default_probability"] = parse_money(f"R$ {prob_match.group(1)}")
        if data["default_probability"] is not None:
            data["default_probability"] = data["default_probability"] / 100

    # --- Queries (consultas) ---
    # O valor do mês é sempre menor/igual ao de 13 meses; usamos quando presentes.
    queries_all = re.findall(r"(\d+)\s*consultas?", text)
    if queries_all:
        vals = sorted(int(q) for q in queries_all)
        # Ignora o "Histórico das últimas N consultas" (geralmente o menor rótulo falso)
        if len(vals) >= 2:
            data["queries_last_13_months"] = vals[-1]

    # --- Branch count (filiais) ---
    filiais_match = re.search(
        r"Número de\s*\n?\s*Filiais\s*\n?\s*(?:funcionários\s*\n?)?(Sem dados|\d+)",
        text,
    )
    if filiais_match:
        val = filiais_match.group(1).strip()
        if val != "Sem dados":
            data["branch_count"] = int(val)
        else:
            data["branch_count"] = None

    # --- Total shareholders from "X | Y" pattern (before anotações) ---
    sh_match = re.search(r"(\d+)\s*\|\s*(\d+)\s*\n?\s*Sócios", text)
    if sh_match:
        data["total_shareholders"] = int(sh_match.group(1))
        data["total_administrators"] = int(sh_match.group(2))

    # --- Shareholder restrictions ---
    # Look for "Anotações" column in sócio/administrador tables
    # Count all "Sim" and "Não" values that appear after "Anotações" headers
    anotacoes_matches = re.findall(
        r"Anotações\s*\n(.*?)(?=\nSócios|\nAdministradores|\nConsultas|$)",
        text,
        re.DOTALL,
    )
    if anotacoes_matches:
        all_anotacoes = " ".join(anotacoes_matches)
        # Each "Não" or "Sim" is one entry per person
        nao_count = len(re.findall(r"\bNão\b", all_anotacoes))
        sim_count = len(re.findall(r"\bSim\b", all_anotacoes))
        data["shareholders_with_restrictions"] = sim_count > 0
        # Use total from "X | Y" pattern if available (avoids double-counting)
        if "total_shareholders" in data and "total_administrators" in data:
            data["shareholders_count"] = max(
                data["total_shareholders"], data["total_administrators"]
            )
        else:
            data["shareholders_count"] = nao_count + sim_count
    else:
        data["shareholders_with_restrictions"] = False

    return data


def _find_value_below(words, header_text, header_x0=None, max_dy=25):
    """Find the value word positioned below a header word by x0 proximity."""
    candidates = []
    for i, w in enumerate(words):
        if w["text"].strip() == header_text:
            h_top = w["top"]
            h_x0 = w["x0"]
            for vw in words:
                dy = vw["top"] - h_top
                if 5 < dy < max_dy:
                    dx = abs(vw["x0"] - h_x0)
                    if dx < 30:
                        candidates.append((dx, vw))
    if candidates:
        candidates.sort(key=lambda c: c[0])
        return candidates[0][1]["text"]
    return None


def _parse_annotations_value(val_text):
    """Parse an annotation value: return amount or None if 'Sem registros'."""
    if val_text is None:
        return None
    val_text = val_text.strip()
    if "Sem registros" in val_text or "Sem registro" in val_text:
        return None
    amt = parse_money(f"R$ {val_text}" if "R$" not in val_text else val_text)
    return amt


def _parse_queries(pages_data):
    """Extract query counts (current month / last 13 months) geometrically.

    Localizes the 'Consultas neste mês' and 'Consultas nos últimos 13 meses'
    labels and reads the count positioned above/near each one.
    """
    result = {}

    def count_near_label(words, label, dx_tol=30, dy_tol=16):
        best = None
        for w in words:
            if label in w["text"] or w["text"].startswith(label):
                lx = w["x0"]
                ly = w["top"]
                for vw in words:
                    if vw is w:
                        continue
                    # valor do tipo 'NN consultas' (uma palavra)
                    if re.fullmatch(r"\d+\s*consultas?", vw["text"]):
                        dist_y = abs(vw["top"] - ly)
                        dist_x = abs(vw["x0"] - lx)
                        if dist_y < dy_tol and dist_x < dx_tol + 40:
                            m = re.match(r"(\d+)", vw["text"])
                            if m is not None:
                                n = int(m.group(1))
                                if best is None or dist_y < best[0]:
                                    best = (dist_y, n)
        return best[1] if best else None

    for words in pages_data:
        cur = count_near_label(words, "Consultas neste mês")
        if cur is not None:
            result["queries_current_month"] = cur
        n13 = count_near_label(words, "Consultas nos últimos 13 meses")
        if n13 is not None:
            result["queries_last_13_months"] = n13

    return result


def _parse_annotations(pages_data):
    """Extract PEFIN, REFIN, overdue debts, bankruptcy, judicial actions,
    protests, and bounced checks from word-positioned page data."""
    data = {}

    if not pages_data:
        return data

    last_page_words = pages_data[-1]

    # --- Annotations grid (PEFIN, REFIN, etc.) ---
    header_map = {
        "PEFIN": "pefin",
        "REFIN": "refin",
        "Dívidas": "overdue_debts",
        "Protestos": "protests",
        "Cheque": "bounced_checks",
    }

    for header_text, key in header_map.items():
        val = _find_value_below(last_page_words, header_text)
        if key == "bounced_checks":
            data[f"{key}_has_records"] = val is not None and "Sem registros" not in (
                val or ""
            )
        else:
            parsed = _parse_annotations_value(val)
            data[f"{key}_has_records"] = parsed is not None
            if parsed is not None:
                data[f"{key}_amount"] = parsed

    # --- Bankruptcy / Recuperação judicial ---
    # The header "Falência / Rec." spans two lines with "judicial" below it
    falencia_val = _find_value_below(last_page_words, "judicial", max_dy=20)
    if falencia_val:
        data["bankruptcy_recovery"] = "Sem registros" not in falencia_val
    else:
        # Fallback: check if "Sem registros" follows "Falência" in text
        data["bankruptcy_recovery"] = False

    # --- Judicial actions ---
    aj_val = _find_value_below(last_page_words, "Ações Judiciais")
    if aj_val:
        data["judicial_actions"] = "Sem registros" not in aj_val
    else:
        data["judicial_actions"] = False

    # --- Total negative annotations (total_debt) ---
    # Already extracted by parse_serasa_text, but ensure it exists
    # (total_debt is parsed from "Total de dívidas: R$ X")

    return data


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pdf_extractor.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    data = extract_pdf_data(pdf_path)
    print("=== Extracted PDF data ===")
    for k, v in sorted(data.items()):
        print(f"  {k}: {v}")
