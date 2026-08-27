"""
History module: records each analysis in a CSV file (append-only),
ensuring access to past analyses is never lost.
"""
import csv
import os
from datetime import datetime


HISTORY_FILENAME = 'analysis_history.csv'


def _flatten(d):
    """Convert a nested dict (e.g.: scores) into flat key-value pairs."""
    flat = {}
    for k, v in d.items():
        if isinstance(v, dict):
            for subk, subv in v.items():
                flat[f'{k}_{subk}'] = subv
        else:
            flat[k] = v
    return flat


def add_to_history(pdf_data, inputs, calcs, excel_path, history_path=None):
    """Add a record to the CSV history in the project root."""
    if history_path is None:
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        history_path = os.path.join(project_dir, HISTORY_FILENAME)

    fields = {
        'analysis_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
        'cnpj': pdf_data.get('cnpj', ''),
        'legal_name': pdf_data.get('legal_name', ''),
        'serasa_score': calcs.get('serasa_score'),
        'share_capital': pdf_data.get('share_capital'),
        'monthly_revenue': pdf_data.get('monthly_revenue'),
        'requested_limit': inputs.get('requested_limit'),
        'final_class': calcs.get('final_class'),
        'internal_score': calcs.get('internal_score'),
        'suggested_limit': calcs.get('suggested_limit'),
        'exposure_index': calcs.get('exposure_index'),
        'recommendation': calcs.get('recommendation'),
        'analyst': inputs.get('analyst', ''),
        'excel_file': excel_path,
    }

    flat_fields = _flatten(fields)

    is_new = not os.path.exists(history_path)
    with open(history_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(flat_fields.keys()))
        if is_new:
            writer.writeheader()
        writer.writerow(flat_fields)

    return history_path
