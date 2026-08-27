"""
History module: records each analysis as a JSON record (with the generated
PDF path) so past analyses can be browsed and reopened inside the app.
"""
import json
import os
from datetime import datetime

from paths import project_file

HISTORY_FILENAME = 'analysis_history.json'


def _history_path():
    return project_file(HISTORY_FILENAME)


def add_to_history(pdf_data, inputs, calcs, report_path):
    """Append a record to the JSON history and return the history path."""
    history_path = _history_path()

    record = {
        'analysis_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'cnpj': pdf_data.get('cnpj', ''),
        'legal_name': pdf_data.get('legal_name', ''),
        'serasa_score': calcs.get('serasa_score'),
        'share_capital': pdf_data.get('share_capital'),
        'monthly_revenue': pdf_data.get('monthly_revenue'),
        'requested_limit': inputs.get('requested_limit'),
        'scores': list(inputs.get('scores', ())),
        'final_class': calcs.get('final_class'),
        'internal_score': calcs.get('internal_score'),
        'suggested_limit': calcs.get('suggested_limit'),
        'exposure_index': calcs.get('exposure_index'),
        'recommendation': calcs.get('recommendation'),
        'analyst': inputs.get('analyst', ''),
        'notes': inputs.get('notes', ''),
        'report_path': report_path,
    }

    records = load_history()
    records.append(record)
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    return history_path


def load_history():
    """Load all history records (oldest first). Returns a list of dicts."""
    history_path = _history_path()
    if not os.path.exists(history_path):
        return []
    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []
