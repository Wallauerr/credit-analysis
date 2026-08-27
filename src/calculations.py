"""
Calculations module that replicates the Excel spreadsheet
'Análise de Crédito - Clientes B2B' formulas.

Faithful replication of the 'Análise' and 'Parâmetros' sheets.
"""

# Parameters (defaults aligned to the Parâmetros sheet of the Excel)
DEFAULT_PARAMS = {
    'weight_financial': 0.4,
    'weight_payment_history': 0.3,
    'weight_operational': 0.2,
    'weight_legal': 0.1,
    'low_risk_min_internal': 80,
    'moderate_min_internal': 60,
    'limit_pct_low': 0.2,
    'limit_pct_moderate': 0.1,
    'limit_pct_high': 0.0,
    'exposure_alert': 1.0,
    'exposure_critical': 2.0,
    'serasa_low_min': 700,
    'serasa_moderate_min': 400,
    'serasa_high_min': 0,
}

try:
    from config_handler import load_params

    _user_params = load_params()
    PARAMS = dict(DEFAULT_PARAMS)
    PARAMS.update({k: v for k, v in _user_params.items() if k in DEFAULT_PARAMS})
except Exception:
    PARAMS = dict(DEFAULT_PARAMS)

LOW_RISK = 'Low risk'
MODERATE_RISK = 'Moderate risk'
HIGH_RISK = 'High risk'


def internal_score(scores, params=None):
    """Internal score (0-100) = weighted average of scores (1-5) * 100."""
    p = params if params else PARAMS
    fin, hist, op, legal = scores
    score = ((fin / 5) * p['weight_financial']
             + (hist / 5) * p['weight_payment_history']
             + (op / 5) * p['weight_operational']
             + (legal / 5) * p['weight_legal']) * 100
    return round(score)


def classify_internal(score, params=None):
    """Internal classification by score range (0-100)."""
    p = params if params else PARAMS
    if score >= p['low_risk_min_internal']:
        return LOW_RISK
    if score >= p['moderate_min_internal']:
        return MODERATE_RISK
    return HIGH_RISK


def classify_serasa(score, params=None):
    """SERASA classification by range (0-1000)."""
    p = params if params else PARAMS
    if score >= p['serasa_low_min']:
        return LOW_RISK
    if score >= p['serasa_moderate_min']:
        return MODERATE_RISK
    return HIGH_RISK


def classify_final(internal, serasa):
    """Final classification = worst between internal and SERASA."""
    if internal == HIGH_RISK or serasa == HIGH_RISK:
        return HIGH_RISK
    if internal == MODERATE_RISK or serasa == MODERATE_RISK:
        return MODERATE_RISK
    return LOW_RISK


def limit_pct_by_class(cls, params=None):
    """Revenue percentage applicable according to the final class."""
    p = params if params else PARAMS
    if cls == LOW_RISK:
        return p['limit_pct_low']
    if cls == MODERATE_RISK:
        return p['limit_pct_moderate']
    return p['limit_pct_high']


def calculate(pdf_data, scores, requested_limit, params=None):
    """
    Execute the whole calculation logic.

    pdf_data: dict with at least monthly_revenue, share_capital, serasa_score
    scores: tuple (financial, payment_history, operational, legal) 1-5
    requested_limit: float
    """
    monthly_rev = pdf_data.get('monthly_revenue')
    capital = pdf_data.get('share_capital')
    serasa_score = pdf_data.get('serasa_score')

    result = {}

    # scores
    result['scores'] = {
        'financial': scores[0],
        'payment_history': scores[1],
        'operational': scores[2],
        'legal': scores[3],
    }

    # internal score and classifications
    si = internal_score(scores, params)
    result['internal_score'] = si
    internal_cls = classify_internal(si, params)
    result['internal_class'] = internal_cls

    result['serasa_score'] = serasa_score
    serasa_cls = classify_serasa(serasa_score, params) if serasa_score is not None else HIGH_RISK
    result['serasa_class'] = serasa_cls

    final_cls = classify_final(internal_cls, serasa_cls)
    result['final_class'] = final_cls

    # suggested limit
    pct = limit_pct_by_class(final_cls, params)
    result['limit_pct'] = pct
    suggested_limit = (monthly_rev * pct) if monthly_rev and pct is not None else None
    result['suggested_limit'] = suggested_limit

    # coverage
    if requested_limit and suggested_limit:
        result['coverage'] = 'Within limit' if requested_limit <= suggested_limit else 'Above suggested limit'
    else:
        result['coverage'] = ''

    # exposure index
    if requested_limit and capital:
        result['exposure_index'] = requested_limit / capital
    else:
        result['exposure_index'] = None

    # capital alert
    ei = result['exposure_index']
    if ei is None:
        result['capital_alert'] = None
    else:
        p = params if params else PARAMS
        if ei > p['exposure_critical']:
            result['capital_alert'] = 'Exposure too high'
        elif ei > p['exposure_alert']:
            result['capital_alert'] = 'Above share capital'
        else:
            result['capital_alert'] = 'Within share capital'

    # recommendation
    ca = result['capital_alert']
    if final_cls == HIGH_RISK or ca == 'Exposure too high':
        result['recommendation'] = 'Deny or require collateral'
    elif (final_cls == MODERATE_RISK
          or result['coverage'] == 'Above suggested limit'
          or ca == 'Above share capital'):
        result['recommendation'] = 'Approve with limit/down payment'
    else:
        result['recommendation'] = 'Approve'

    return result
