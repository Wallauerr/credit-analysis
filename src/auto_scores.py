"""
Automatic scoring module.
Calculates the 4 analysis scores (1-5) from Serasa PDF data,
following the structured approach proposed for B2B credit analysis.
"""

from calculations import HIGH_RISK


def auto_score_financial(pdf_data, requested_limit):
    """Capacidade financeira (1-5).

    Based on three indices:
    - Crédito solicitado / Faturamento mensal (primary)
    - Crédito solicitado / Capital social (secondary)
    - Dívidas negativas / Faturamento anual (penalty)
    """
    monthly_rev = pdf_data.get("monthly_revenue")
    annual_rev = pdf_data.get("annual_revenue")
    capital = pdf_data.get("share_capital")
    total_debt = pdf_data.get("total_debt") or 0

    if not monthly_rev or not requested_limit:
        return 3, "Dados insuficientes para cálculo financeiro"

    # Primary index: requested_limit / monthly_revenue
    ratio_limit_rev = requested_limit / monthly_rev

    if ratio_limit_rev < 0.20:
        score = 5
    elif ratio_limit_rev < 0.40:
        score = 4
    elif ratio_limit_rev < 0.60:
        score = 3
    elif ratio_limit_rev < 0.80:
        score = 2
    else:
        score = 1

    # Secondary index: requested_limit / share_capital
    extra = ""
    if capital and capital > 0:
        ratio_limit_cap = requested_limit / capital
        if ratio_limit_cap > 2.0:
            score = max(score - 1, 1)
            extra = f", crédito/capital ({ratio_limit_cap:.1f}x) alto"

    # Penalty: if debt/revenue > 50%, max = 3
    if annual_rev and total_debt and annual_rev > 0:
        ratio_debt_rev = total_debt / annual_rev
        if ratio_debt_rev > 0.50:
            score = min(score, 3)
            extra += f", endividamento ({ratio_debt_rev:.0%}) alto"
    else:
        ratio_debt_rev = 0

    reason = f"crédito/faturamento mensal = {ratio_limit_rev:.0%}"
    if extra:
        reason += extra

    return score, reason


def auto_score_payment(pdf_data):
    """Histórico de pagamento (1-5).

    Based on:
    - Serasa Score (primary)
    - PEFIN, REFIN, dívidas vencidas, cheques (penalties)
    - Probabilidade de inadimplência (context)
    """
    serasa_score = pdf_data.get("serasa_score") or 0
    has_restrictions = pdf_data.get("has_restrictions", False)
    pefin = pdf_data.get("pefin_has_records", False)
    refin = pdf_data.get("refin_has_records", False)
    overdue = pdf_data.get("overdue_debts_has_records", False)
    bounced = pdf_data.get("bounced_checks_has_records", False)
    prob = pdf_data.get("default_probability")

    # Base on serasa_score
    if serasa_score >= 700:
        score = 5
    elif serasa_score >= 500:
        score = 4
    elif serasa_score >= 300:
        score = 3
    elif serasa_score >= 100:
        score = 2
    else:
        score = 1

    penalties = []
    # Penalty: has_restrictions → -1
    if has_restrictions:
        score = max(score - 1, 1)
        penalties.append("dívidas informadas")

    # Penalty: PEFIN → -1
    if pefin:
        score = max(score - 1, 1)
        penalties.append("PEFIN")

    # Penalty: REFIN → -1
    if refin:
        score = max(score - 1, 1)
        penalties.append("REFIN")

    # Penalty: dívidas vencidas → -1
    if overdue:
        score = max(score - 1, 1)
        penalties.append("dívidas vencidas")

    # Penalty: cheques → -1
    if bounced:
        score = max(score - 1, 1)
        penalties.append("cheques sustados")

    reason = f"Score Serasa {serasa_score}"
    if prob is not None:
        reason += f", inadimplência {prob:.2%}"
    if penalties:
        reason += f" | penalidades: {', '.join(penalties)}"

    return score, reason


def auto_score_operational(pdf_data):
    """Perfil operacional (1-5).

    Based on:
    - Tempo de mercado (primary)
    - Situação cadastral (hard block)
    - Consultas nos últimos 13 meses (penalty if excessive)
    - Número de filiais (bonus indicator)
    """
    market_years = pdf_data.get("market_years") or 0
    status = pdf_data.get("registration_status", "")
    queries_13m = pdf_data.get("queries_last_13_months") or 0

    # Hard block: not active → 1
    if status != "ATIVA":
        return 1, f"Situação cadastral: {status}"

    # Score by market years
    if market_years >= 10:
        score = 5
    elif market_years >= 5:
        score = 4
    elif market_years >= 3:
        score = 3
    elif market_years >= 1:
        score = 2
    else:
        score = 1

    # Penalty: excessive queries (>50 in 13 months) → -1
    extra = ""
    if queries_13m > 50:
        score = max(score - 1, 1)
        extra = f", {queries_13m} consultas (muitas)"

    reason = f"{market_years} anos, {status}"
    if extra:
        reason += extra

    return score, reason


def auto_score_legal(pdf_data):
    """Risco jurídico (1-5).

    Based on:
    - Falência/Recuperação judicial (hard block → 1)
    - Ações judiciais (hard block → 1)
    - Has restrictions + Serasa score (primary)
    - Protestos (penalty)
    - Anotações de sócios/administradores (penalty)
    """
    has_restrictions = pdf_data.get("has_restrictions", False)
    serasa_score = pdf_data.get("serasa_score") or 0
    bankruptcy = pdf_data.get("bankruptcy_recovery", False)
    judicial = pdf_data.get("judicial_actions", False)
    protests = pdf_data.get("protests_has_records", False)
    sh_restrictions = pdf_data.get("shareholders_with_restrictions", False)

    # Hard block: bankruptcy → 1
    if bankruptcy:
        return 1, "Falência/Recuperação judicial registrada"

    # Hard block: judicial actions → 1
    if judicial:
        return 1, "Ações judiciais registradas"

    # Base on restrictions + score
    if not has_restrictions:
        if serasa_score >= 600:
            score = 5
        elif serasa_score >= 400:
            score = 4
        else:
            score = 3
    else:
        if serasa_score >= 400:
            score = 2
        else:
            score = 1

    penalties = []
    # Penalty: protests → -1
    if protests:
        score = max(score - 1, 1)
        penalties.append("protestos")

    # Penalty: shareholder restrictions → -1
    if sh_restrictions:
        score = max(score - 1, 1)
        penalties.append("anotações em sócios")

    reason = f"Score {serasa_score}"
    if penalties:
        reason += f" | penalidades: {', '.join(penalties)}"

    return score, reason


def calculate_auto_scores(pdf_data, requested_limit):
    """Calculate all 4 automatic scores from PDF data.

    Returns a dict with (score, reason) for each category.
    """
    fin_score, fin_reason = auto_score_financial(pdf_data, requested_limit)
    pay_score, pay_reason = auto_score_payment(pdf_data)
    op_score, op_reason = auto_score_operational(pdf_data)
    leg_score, leg_reason = auto_score_legal(pdf_data)

    return {
        "financial": (fin_score, fin_reason),
        "payment_history": (pay_score, pay_reason),
        "operational": (op_score, op_reason),
        "legal": (leg_score, leg_reason),
    }


def check_hard_blocks(pdf_data, requested_limit):
    """Check for hard block conditions that override the recommendation.

    Returns (block_active, reason) or (False, None) if no block.
    """
    status = pdf_data.get("registration_status", "")
    serasa_score = pdf_data.get("serasa_score") or 0
    capital = pdf_data.get("share_capital") or 0
    total_debt = pdf_data.get("total_debt") or 0
    annual_rev = pdf_data.get("annual_revenue")
    bankruptcy = pdf_data.get("bankruptcy_recovery", False)
    judicial = pdf_data.get("judicial_actions", False)

    # Hard block: bankruptcy/judicial → Negar
    if bankruptcy:
        return True, HIGH_RISK, "Falência ou recuperação judicial registrada"
    if judicial:
        return True, HIGH_RISK, "Ações judiciais registradas"

    # Hard block: registration not active → Negar
    if status and status != "ATIVA":
        return True, HIGH_RISK, f"Situação cadastral: {status}"

    # Hard block: serasa score very low → Negar
    if serasa_score < 200:
        return True, HIGH_RISK, f"Score Serasa muito baixo ({serasa_score})"

    # Alert: credit > 2x capital → exigir garantia
    if capital and capital > 0 and requested_limit and requested_limit > 2 * capital:
        return True, "Aprovar com limite/entrada", (
            f"Crédito solicitado ({requested_limit:,.0f}) excede 2x o capital social ({capital:,.0f})"
        )

    # Alert: total debt > annual revenue → bloqueia
    if annual_rev and annual_rev > 0 and total_debt and total_debt > annual_rev:
        return True, HIGH_RISK, (
            f"Endividamento total ({total_debt:,.0f}) excede faturamento anual ({annual_rev:,.0f})"
        )

    return False, None, None
