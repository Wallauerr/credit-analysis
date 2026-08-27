"""
Configuration handler: JSON persistence of both the UI settings
(last used PDF/analyst) and the editable calculation parameters.
"""
import json
import os

from paths import project_file

UI_CONFIG_FILE = project_file("credit_analysis_config.json")
PARAMS_CONFIG_FILE = project_file("params_config.json")


def _read_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            pass
    return default


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


# ---------- UI settings ----------
def load_config():
    return _read_json(
        UI_CONFIG_FILE,
        {"last_pdf_path": "", "last_analyst": ""},
    )


def save_config(last_pdf_path="", last_analyst=""):
    _write_json(UI_CONFIG_FILE, {"last_pdf_path": last_pdf_path, "last_analyst": last_analyst})


# ---------- Calculation parameters ----------
def load_params():
    """Return the editable calculation parameters (dict)."""
    return _read_json(PARAMS_CONFIG_FILE, {})


def save_params(params):
    _write_json(PARAMS_CONFIG_FILE, params)
