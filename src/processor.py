"""
Processor module: orchestrates the complete credit analysis flow,
decoupled from the user interface (works for both CLI and GUI).

Flow:
1. Extract the Serasa PDF data (no Excel model needed anymore).
2. Calculate internal score, final classification and recommendation.
3. Generate a formatted PDF report with the company logo.
4. Record the analysis in the JSON history (for in-app browsing).
"""

import os

from pdf_extractor import extract_pdf_data
from calculations import calculate
from pdf_report import generate_report
from history import add_to_history
from paths import reports_dir

OUTPUT_DIR = reports_dir()


def process_analysis(pdf_path, inputs, report_path=None):
    """
    Run the full analysis flow.

    pdf_path: str, path to the Serasa PDF
    inputs: dict with:
        - requested_limit (float)
        - scores (tuple 4x, 1-5)
        - references (str 'Sim'/'Nao')
        - analyst (str)
        - notes (str)
    report_path: str, optional path for the generated PDF

    Returns a dict with 'pdf_data', 'calcs', 'report_path', 'history_path'.
    Raises FileNotFoundError if the PDF is missing.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # 1. Extract PDF data
    pdf_data = extract_pdf_data(pdf_path)

    # 2. Calculate (uses editable PARAMS from config)
    scores = inputs.get("scores", (3, 3, 3, 3))
    calcs = calculate(pdf_data, scores, inputs.get("requested_limit"))

    # 3. Generate formatted PDF report
    output_path = generate_report(pdf_data, inputs, calcs, output_path=report_path)

    # 4. Record JSON history
    final_history = add_to_history(pdf_data, inputs, calcs, output_path)

    return {
        "pdf_data": pdf_data,
        "calcs": calcs,
        "report_path": output_path,
        "history_path": final_history,
    }
