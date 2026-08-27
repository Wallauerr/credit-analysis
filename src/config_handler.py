import json
import os

CONFIG_FILE = "credit_analysis_config.json"


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as file:
                return json.load(file)
        except (json.JSONDecodeError, OSError):
            pass
    return {"last_pdf_path": "", "last_analyst": ""}


def save_config(last_pdf_path="", last_analyst=""):
    config = {"last_pdf_path": last_pdf_path, "last_analyst": last_analyst}
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file)
