"""
Serasa Experian API integration (Relatório Avançado PJ / "Relato").

Fetches a company's credit data directly from the Serasa API (by CNPJ) and
maps the JSON response into the *same* `pdf_data` dictionary schema used by
the PDF extractor. This lets the rest of the pipeline (calculations, auto
scores, PDF report) work unchanged, regardless of the data source.

Flow:
1. Obtain an IAM access token (client identity login).
2. POST a credit-report request with the CNPJ in the headers.
3. Map the returned JSON into `pdf_data`.
4. Save the raw JSON to the local cache (avoid duplicate paid queries).

Credentials/endpoints are read from `api_config.json` (see config_handler);
they are never hardcoded here.
"""

import base64
import json
import os
from datetime import datetime

import requests

from logger import logger
from paths import config_file, cache_dir

API_CONFIG_FILE = config_file("api_config.json")

# Default endpoints (production / homologation). Can be overridden in
# api_config.json once Serasa provides the exact URLs for your contract.
DEFAULT_TOKEN_URL_PROD = (
    "https://api.serasaexperian.com.br/security/iam/v1/client-identities/login"
)
DEFAULT_TOKEN_URL_UAT = (
    "https://uat-api.serasaexperian.com.br/security/iam/v1/client-identities/login"
)
DEFAULT_REPORT_URL_PROD = "https://api.serasaexperian.com.br/credit-reports/v1/credit-reports"
DEFAULT_REPORT_URL_UAT = (
    "https://uat-api.serasaexperian.com.br/credit-reports/v1/credit-reports"
)

# Report name for the "Relatório Avançado PJ". The TOP SCORE variant also
# returns the Score Positivo and the corporate structure. Change in config.
DEFAULT_REPORT_NAME = "RELATORIO_AVANCADO_TOP_SCORE_PJ"

DEFAULT_API_CONFIG = {
    "serasa_api_env": "homologacao",  # "homologacao" | "producao"
    # Leave blank to use the defaults below (they follow the official docs).
    "serasa_api_token_url": "",
    "serasa_api_report_url": "",
    "serasa_api_report_name": DEFAULT_REPORT_NAME,
    "serasa_api_client_id": "",
    "serasa_api_client_secret": "",
    # Optional: 'Centro de custo' / CNPJ consultante (pass-through headers).
    "serasa_api_cost_center": "",
    "serasa_api_retailer_document_id": "",
    # Override for the Authorization header in the token login (e.g. the
    # literal "Basic IAM" value supplied by Serasa). When empty, it is built
    # as "Basic base64(client_id:client_secret)".
    "serasa_api_auth_header": "",
    # Cache TTL in seconds; 0 disables the cache (default: 24h).
    "serasa_api_cache_ttl": 86400,
}

TIMEOUT_SECONDS = 60


class SerasaAPIError(Exception):
    """Raised when the Serasa API call fails."""


class SerasaAuthError(SerasaAPIError):
    """Raised when authentication fails (invalid/revoked credentials)."""


class SerasaQuotaError(SerasaAPIError):
    """Raised when the query quota is exhausted or the CNPJ is not authorized."""


class SerasaNotFoundError(SerasaAPIError):
    """Raised when the CNPJ is not found / invalid in the Serasa base."""


# --------------------------------------------------------------------------
# Config helpers
# --------------------------------------------------------------------------
def load_api_config():
    """Return the API configuration dict, merging defaults with saved values."""
    cfg = dict(DEFAULT_API_CONFIG)
    if os.path.exists(API_CONFIG_FILE):
        try:
            with open(API_CONFIG_FILE, "r", encoding="utf-8") as file:
                saved = json.load(file)
            if isinstance(saved, dict):
                cfg.update({k: v for k, v in saved.items() if k in cfg})
        except (json.JSONDecodeError, OSError):
            logger.warning("api_config.json inválido; usando configuração padrão.")
    return cfg


def save_api_config(cfg):
    """Persist the API configuration to api_config.json."""
    merged = dict(DEFAULT_API_CONFIG)
    merged.update({k: v for k, v in cfg.items() if k in merged})
    with open(API_CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(merged, file, ensure_ascii=False, indent=2)
    return merged


def is_api_configured(cfg=None):
    """True when there is enough configuration to attempt an API call."""
    cfg = cfg if cfg is not None else load_api_config()
    return bool(cfg.get("serasa_api_client_id")) or bool(
        cfg.get("serasa_api_client_secret")
    )


# --------------------------------------------------------------------------
# Low-level HTTP helpers
# --------------------------------------------------------------------------
def _token_url(cfg):
    return (cfg.get("serasa_api_token_url") or "").strip() or (
        DEFAULT_TOKEN_URL_UAT
        if cfg.get("serasa_api_env") != "producao"
        else DEFAULT_TOKEN_URL_PROD
    )


def _report_url(cfg):
    return (cfg.get("serasa_api_report_url") or "").strip() or (
        DEFAULT_REPORT_URL_UAT
        if cfg.get("serasa_api_env") != "producao"
        else DEFAULT_REPORT_URL_PROD
    )


def _request_headers(cfg):
    """Basic Authorization header used in the client-identity login."""
    auth = (cfg.get("serasa_api_auth_header") or "").strip()
    if auth:
        return {"Content-Type": "application/json", "Authorization": auth}
    client_id = (cfg.get("serasa_api_client_id") or "").strip()
    client_secret = (cfg.get("serasa_api_client_secret") or "").strip()
    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    return {"Content-Type": "application/json", "Authorization": f"Basic {encoded}"}


def _login(cfg):
    """Request an IAM access token. Returns the raw JSON response."""
    url = _token_url(cfg)
    client_id = (cfg.get("serasa_api_client_id") or "").strip()
    client_secret = (cfg.get("serasa_api_client_secret") or "").strip()
    if not client_id or not client_secret:
        raise SerasaAuthError(
            "Credenciais da API Serasa não configuradas. "
            "Preencha client_id e client_secret na aba Configuração."
        )

    payload = {"clientId": client_id, "clientSecret": client_secret}
    try:
        resp = requests.post(
            url, json=payload, headers=_request_headers(cfg), timeout=TIMEOUT_SECONDS
        )
    except requests.RequestException as exc:
        raise SerasaAPIError(f"Falha de conexão com a Serasa: {exc}") from exc

    if resp.status_code in (401, 403):
        raise SerasaAuthError(f"Credenciais inválidas (HTTP {resp.status_code}). {resp.text[:200]}")
    if resp.status_code != 200:
        raise SerasaAPIError(
            f"Falha ao obter token (HTTP {resp.status_code}). {resp.text[:300]}"
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise SerasaAPIError("Resposta de autenticação sem JSON válido.") from exc


def _get_access_token(cfg):
    """Return the access token, refreshing on demand (no persistent cache of
    the token itself; the Serasa docs say the token is valid for ~1h)."""
    data = _login(cfg)
    token = data.get("accessToken") or data.get("acessToken") or data.get("access_token")
    if not token:
        raise SerasaAuthError(f"Resposta de autenticação sem token. {str(data)[:200]}")
    return str(token)


def _post_report(cfg, cnpj_digits, token):
    """POST the credit-report request. Returns the parsed JSON (dict or list of dicts)."""
    url = _report_url(cfg)
    report_name = (cfg.get("serasa_api_report_name") or DEFAULT_REPORT_NAME).strip()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "X-Document-Id": cnpj_digits,
    }
    cost_center = (cfg.get("serasa_api_cost_center") or "").strip()
    if cost_center:
        headers["X-Cost-Center"] = cost_center
    retailer = (cfg.get("serasa_api_retailer_document_id") or "").strip()
    if retailer:
        headers["X-Retailer-Document-Id"] = retailer

    payload = {"reportName": report_name}

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise SerasaAPIError(f"Falha de conexão com a Serasa: {exc}") from exc

    body = resp.text or ""
    if resp.status_code in (401, 403) or "USER-NOT-AUTHORIZED" in body:
        raise SerasaAuthError(
            "Credencial sem acesso a esta funcionalidade (USER-NOT-AUTHORIZED). "
            "Confirme com a Serasa se o contrato inclui o produto/feature solicitado."
        )
    if resp.status_code in (404, 422) or "CNPJ" in body and resp.status_code in (404, 422):
        raise SerasaNotFoundError(
            f"CNPJ não encontrado/inválido no Serasa (HTTP {resp.status_code}). {body[:300]}"
        )
    if resp.status_code != 200:
        raise SerasaQuotaError(
            f"Falha na consulta (HTTP {resp.status_code}). {body[:300]}"
        )

    try:
        return resp.json()
    except ValueError as exc:
        raise SerasaAPIError("Resposta da consulta sem JSON válido.") from exc


# --------------------------------------------------------------------------
# CNPJ helpers
# --------------------------------------------------------------------------
def only_digits(value):
    """Return only the digits of a CNPJ string (handles masks like 12.345.678/0001-90)."""
    return "".join(ch for ch in str(value) if ch.isdigit())


def normalize_cnpj(cnpj):
    """Normalize a CNPJ to 14 digits; raises ValueError if invalid."""
    digits = only_digits(cnpj)
    if len(digits) != 14:
        raise ValueError(
            f"CNPJ inválido: esperado 14 dígitos, recebido {len(digits)}. "
            "Use o formato 00.000.000/0000-00."
        )
    return digits


# --------------------------------------------------------------------------
# JSON -> pdf_data mapping
# --------------------------------------------------------------------------
def _find(root, *paths):
    """Deep-find the first non-None value following a list of candidate paths.

    Each path is a tuple of string keys / list indices. Searches nested dicts
    (and lists of dicts) case-insensitively by key name where possible.
    Returns None when nothing is found.
    """
    if not isinstance(root, (dict, list)):
        return None
    for path in paths:
        node = root
        found = True
        for key in path:
            if isinstance(node, dict):
                if isinstance(key, str):
                    node = _dict_get_ci(node, key)
                else:
                    node = node.get(key)
            elif isinstance(node, list) and isinstance(key, int) and key < len(node):
                node = node[key]
            else:
                found = False
                break
            if node is None:
                found = False
                break
        if found and node not in (None, "", [], {}):
            return node
    return None


def _dict_get_ci(d, key):
    """Dict lookup, case-insensitive on keys (tries exact match first)."""
    if key in d:
        return d[key]
    low = key.lower()
    for k, v in d.items():
        if str(k).lower() == low:
            return v
    return None


def _first_in_list(root):
    """If root is a list, return its first dict element; otherwise root."""
    if isinstance(root, list):
        return root[0] if root else None
    return root


def _as_bool(value):
    """Coerce a value to a boolean the way the app expects (flags)."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in ("0", "nao", "não", "no", "false", "sem", "sem registros", "sem registro", "n/a"):
        return False
    if text in ("1", "sim", "yes", "true", "com", "com registro"):
        return True
    return bool(text)


def _as_number(value):
    """Coerce a string/number to float when possible; returns None otherwise."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in (
        "sem dados", "sem registros", "sem registro", "sem ocorrências", "-",
        "n/a", "nao informado", "não informado",
    ):
        return None
    try:
        cleaned = text.replace("R$", "").replace(" ", "").replace("%", "")
        has_comma = "," in cleaned
        has_dot = "." in cleaned
        if has_comma:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif has_dot:
            cleaned = cleaned.replace(",", "")
        return float(cleaned)
    except ValueError:
        return None


def _as_money(value):
    """Parse a currency value.

    Handles numeric floats (reais) as well as Brazilian ("1.234.567,89") and
    international ("102000.00") string formats. Returns float or None.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text.lower() in (
        "sem dados", "sem registros", "sem registro", "sem ocorrências", "-",
        "n/a", "nao informado", "não informado",
    ):
        return None
    cleaned = text.replace("R$", "").replace(" ", "")
    cleaned = cleaned.replace("\u00a0", "")
    if not cleaned:
        return None
    try:
        if "," in cleaned and "." in cleaned:
            # Brazilian: 1.234.567,89 (thousands with dots, decimal comma)
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        return float(cleaned)
    except ValueError:
        return None


def _as_int(value):
    num = _as_number(value)
    return int(num) if num is not None else None


def _map_cadastral(payload):
    """Map cadastral/business identity fields."""
    p = payload
    return {
        "cnpj": _find(p, ("cnpj",), ("cadastro", "cnpj"), ("dadosCadastrais", "cnpj"),
                       ("empresa", "cnpj")),
        "legal_name": _find(p, ("razaoSocial",), ("legalName",), ("nomeEmpresarial",),
                            ("dadosCadastrais", "razaoSocial"), ("empresa", "razaoSocial")),
        "city": _find(p, ("cidade",), ("city",), ("endereco", "cidade"),
                      ("dadosCadastrais", "cidade"), ("empresa", "cidade")),
        "state": _find(p, ("uf",), ("state",), ("endereco", "uf"),
                       ("dadosCadastrais", "uf"), ("empresa", "uf")),
        "segment": _find(p, ("cnae",), ("segmento",), ("atividadeEconomica",),
                         ("ramoAtividade",), ("dadosCadastrais", "cnae")),
        "registration_status": _find(p, ("situacaoCadastral",), ("statusCadastral",),
                                     ("situacao",), ("dadosCadastrais", "situacao")),
        "market_years": _find(p, ("anosMercado",), ("tempoMercado",),
                              ("dadosCadastrais", "anosMercado")),
        "branch_count": _find(p, ("numeroFiliais",), ("quantidadeFiliais",),
                              ("filiais",), ("dadosCadastrais", "numeroFiliais")),
        "share_capital": _find(p, ("capitalSocial",), ("share_capital",), ("capital",),
                               ("dadosCadastrais", "capitalSocial"), ("dadosCadastrais", "share_capital"),
                               ("empresa", "capitalSocial"), ("empresa", "share_capital")),
    }


def _map_financial(payload):
    """Map revenue/score fields."""
    p = payload
    annual = _find(p, ("faturamentoAnual",), ("faturamento",), ("revenue",),
                   ("receitaAnual",), ("dadosCadastrais", "faturamentoAnual"))
    monthly = _find(p, ("faturamentoMensal",), ("monthlyRevenue",),
                    ("receitaMensal",), ("dadosCadastrais", "faturamentoMensal"))
    annual_num = _as_money(annual)
    monthly_num = _as_money(monthly)
    if annual_num is None and monthly_num is not None:
        annual_num = round(monthly_num * 12, 2)
    if monthly_num is None and annual_num is not None:
        monthly_num = round(annual_num / 12, 2)

    serasa_score = _find(
        p, ("serasaScore",), ("score",), ("scoreSerasa",), ("serasaScore", "score"),
        ("scorePositivo", "score"), ("creditScore",), ("dadosScore", "score"),
    )

    return {
        "annual_revenue": annual_num,
        "monthly_revenue": monthly_num,
        "serasa_score": _as_int(serasa_score),
        "default_probability": _as_number(
            _find(p, ("probabilidadeInadimplencia",), ("defaultRate",),
                  ("probabilidade",), ("defaultProbability",))
        ),
    }


def _map_negatives(payload):
    """Map restriction/negative-annotation fields to *_has_records flags + amounts."""
    p = payload
    res = {}
    specs = {
        "pefin": ("pefin", "pendenciaFinanceira", "pendenciaInterna", "pefin"),
        "refin": ("refin", "restricaoFinanceira", "restricoes"),
        "overdue_debts": ("dividasVencidas", "overdueDebts", "dividaVencida"),
        "protests": ("protestos", "protests", "protesto"),
        "bounced_checks": ("chequesSemFundo", "cheques", "bouncedChecks", "ccf"),
    }
    for key, keys in specs.items():
        node = _find(p, *((k,) for k in keys))
        node = _first_in_list(node)
        if node is None:
            has_records = has_amount = False
            amount = None
        elif isinstance(node, (dict,)):
            # e.g. {"qtde": 2, "valor": 123.45} or {"quantidade": 2}
            qty = _find(node, ("qtde",), ("quantidade",), ("count",), ("qtd",))
            val = _find(node, ("valor",), ("value",), ("montante",))
            has_records = _as_bool(qty) or _as_bool(val)
            amount = _as_number(val)
        else:
            # Direct scalar: a number (count) or a string like "Sem registros"
            has_records = _as_bool(node)
            amount = _as_money(node) if isinstance(node, (int, float)) else None
        if has_records:
            res[f"{key}_has_records"] = True
            if amount is not None:
                res[f"{key}_amount"] = amount
        else:
            res[f"{key}_has_records"] = False

    # Bankruptcy / recuperação judicial
    res["bankruptcy_recovery"] = _as_bool(
        _find(p, ("falencia",), ("recuperacaoJudicial",), ("falenciaRecuperacao",),
              ("falenciaRecuperacaoJudicial",), ("negativos", "falencia"))
    )
    # Judicial actions
    res["judicial_actions"] = _as_bool(
        _find(p, ("acoesJudiciais",), ("judicialActions",), ("acoes"),
              ("negativos", "acoesJudiciais"))
    )
    # Total debt (sum of known negative amounts if not directly present)
    total = _find(p, ("totalDividas",), ("totalDebt",), ("totalAnotacoes",),
                  ("totalDividasVencidas",), ("negativos", "total"))
    if total is None:
        total = 0.0
        for key in ("pefin", "refin", "overdue_debts", "protests", "bounced_checks"):
            amount = res.get(f"{key}_amount")
            if amount is not None:
                total += amount
        total = total if total > 0 else None
    res["total_debt"] = _as_money(total)
    res["has_restrictions"] = _as_bool(
        _find(p, ("temRestricao",), ("hasRestrictions",), ("indicadorRestricao",))
    ) or any(res.get(f"{k}_has_records") for k in ("pefin", "refin", "overdue_debts", "protests", "bounced_checks"))
    return res


def _map_corporate(payload):
    """Map corporate structure / shareholders information."""
    p = payload
    shareholders = _find(p, ("quadroSocietario",), ("socios",), ("shareholders",),
                         ("quadroSocial",), ("dadosSocietarios",))
    shareholders = _first_in_list(shareholders)
    extras = {}
    if isinstance(shareholders, dict):
        qty = _find(shareholders, ("quantidade",), ("qtde",), ("count",))
        num_shareholders = _as_int(qty)
        if num_shareholders is not None:
            extras["total_shareholders"] = num_shareholders
            extras["shareholders_count"] = num_shareholders
        with_rest = _find(shareholders, ("sociosComRestricao",), ("shareholdersWithRestrictions",),
                          ("comRestricao",))
        if with_rest is not None:
            extras["shareholders_with_restrictions"] = _as_bool(with_rest)
    else:
        extras["total_shareholders"] = _as_int(shareholders)

    # Admin counts
    admins = _find(p, ("administradores",), ("administratorCount",), ("totalAdministradores",))
    if admins is not None:
        extras["total_administrators"] = _as_int(admins)
    return extras


def map_api_response(payload):
    """Convert a Serasa API JSON response into the `pdf_data` schema used by
    the app. Missing fields are simply absent; the GUI's 'missing essential
    data' flow can then ask the user to fill them manually."""
    payload = _first_in_list(payload) if isinstance(payload, list) else payload
    if not isinstance(payload, dict):
        raise SerasaAPIError("Resposta da API em formato inesperado.")

    data = {}
    data.update(_map_cadastral(payload))
    data.update(_map_financial(payload))
    data.update(_map_negatives(payload))
    data.update(_map_corporate(payload))

    # Query counts (less relevant for the pipeline)
    q_month = _find(payload, ("consultasMesAtual",), ("queriesCurrentMonth",))
    q_13m = _find(payload, ("consultasUltimos13Meses",), ("queriesLast13Months",),
                  ("consultas", "ultimos13Meses"))
    if q_13m is not None:
        data["queries_last_13_months"] = _as_int(q_13m)
    if q_month is not None:
        data["queries_current_month"] = _as_int(q_month)

    # Normalize numeric typing where the app expects floats
    for key in (
        "share_capital",
        "monthly_revenue",
        "annual_revenue",
        "total_debt",
    ):
        if data.get(key) is not None:
            data[key] = _as_money(data[key])
    if data.get("default_probability") is not None:
        data["default_probability"] = _as_number(data["default_probability"])

    for key in ("serasa_score", "market_years", "branch_count",
                "total_shareholders", "total_administrators", "shareholders_count"):
        if data.get(key) is not None:
            data[key] = _as_int(data[key])

    # Serasa "default_probability" typically comes as a fraction; if the API
    # returns a percentage (0-100), normalize to 0-1.
    prob = data.get("default_probability")
    if prob is not None and prob > 1:
        data["default_probability"] = prob / 100

    return data


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------
def _cache_path(cnpj_digits):
    return os.path.join(cache_dir(), f"{cnpj_digits}.json")


def load_cached(cnpj_digits, ttl=0):
    """Return a cached dict for the CNPJ if fresh enough; None otherwise."""
    if not ttl:
        return None
    path = _cache_path(cnpj_digits)
    if not os.path.exists(path):
        return None
    try:
        age = datetime.now().timestamp() - os.path.getmtime(path)
        if age > ttl:
            return None
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError):
        return None


def save_cached(cnpj_digits, data):
    """Persist the raw API response (dict) to the local cache."""
    try:
        path = _cache_path(cnpj_digits)
        with open(path, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.warning(f"Não foi possível salvar o cache da consulta: {exc}")


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def fetch_company_data(cnpj, cfg=None, use_cache=True):
    """
    Fetch a company's credit data by CNPJ and return a `pdf_data`-compatible dict.

    cnpj: string, CNPJ with or without mask.
    cfg: optional api config dict (defaults to api_config.json).
    use_cache: when True (default), reuse a fresh local cache entry instead of
               making another paid Serasa query.
    """
    cfg = cfg if cfg is not None else load_api_config()
    cnpj_digits = normalize_cnpj(cnpj)

    ttl = int(cfg.get("serasa_api_cache_ttl") or 0)
    if use_cache and ttl > 0:
        cached = load_cached(cnpj_digits, ttl=ttl)
        if cached is not None:
            logger.info(f"Usando cache local da consulta para o CNPJ {cnpj_digits}.")
            return map_api_response(cached)

    token = _get_access_token(cfg)
    payload = _post_report(cfg, cnpj_digits, token)

    if use_cache and ttl > 0:
        save_cached(cnpj_digits, payload)

    return map_api_response(payload)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python serasa_api.py <cnpj> [--no-cache]")
        sys.exit(1)
    cnpj_arg = sys.argv[1]
    use_cache_flag = "--no-cache" not in sys.argv
    data = fetch_company_data(cnpj_arg, use_cache=use_cache_flag)
    print("=== Mapped pdf_data ===")
    for k in sorted(data):
        print(f"  {k}: {data[k]}")