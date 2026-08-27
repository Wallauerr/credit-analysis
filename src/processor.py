"""
Processor module: orchestrates the complete credit analysis flow,
decoupled from the user interface (works for both CLI and GUI).

Flow:
1. Locate the Excel model file.
2. Extract the Serasa PDF data.
3. Calculate internal score, final classification and recommendation.
4. Fill in and save the Excel file.
5. Record it in the CSV history.
"""
import os

from pdf_extractor import extract_pdf_data
from calculations import calculate
from excel_writer import fill_excel, safe_filename
from history import add_to_history

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, 'outputs')

MODEL_CANDIDATES = [
    'pICOLI E DENEGA.xlsx',
    'credit_analysis_model.xlsx',
]


def find_model(base_dirs=None):
    """Try to locate the xlsx model file in the project root or given dirs."""
    dirs = base_dirs or [PROJECT_DIR, os.getcwd()]
    for name in MODEL_CANDIDATES:
        for base in dirs:
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
    return None


def process_analysis(pdf_path, inputs, model_path=None, history_path=None):
    """
    Run the full analysis flow.

    pdf_path: str, path to the Serasa PDF
    inputs: dict with:
        - requested_limit (float)
        - scores (tuple 4x, 1-5)
        - references (str 'Sim'/'Nao')
        - analyst (str)
        - notes (str)
    model_path: str, optional path to the xlsx model
    history_path: str, optional path for the history CSV (defaults to project root)

    Returns a dict with 'pdf_data', 'calcs', 'excel_path', 'history_path'.
    Raises FileNotFoundError if the model or PDF is missing.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f'PDF file not found: {pdf_path}')

    model = model_path or find_model()
    if not model:
        raise FileNotFoundError(
            'Excel model not found. Place it in the same folder as the program.'
        )

    # 1. Extract PDF data
    pdf_data = extract_pdf_data(pdf_path)

    # 2. Calculate
    scores = inputs.get('scores', (3, 3, 3, 3))
    calcs = calculate(pdf_data, scores, inputs.get('requested_limit'))

    # 3. Fill and save Excel
    filename = safe_filename(pdf_data.get('legal_name', ''), pdf_data.get('cnpj', ''))
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    excel_path = os.path.join(OUTPUT_DIR, filename)
    fill_excel(model, excel_path, pdf_data, inputs, calcs)

    # 4. Record history
    if history_path is None:
        history_path = None  # let history.py use its default (src folder)
    final_history = add_to_history(pdf_data, inputs, calcs, excel_path, history_path=history_path)

    return {
        'pdf_data': pdf_data,
        'calcs': calcs,
        'excel_path': excel_path,
        'history_path': final_history,
    }
