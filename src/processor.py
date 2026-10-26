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
from auto_scores import calculate_auto_scores, check_hard_blocks
from pdf_report import generate_report
from history import add_to_history
from paths import reports_dir

OUTPUT_DIR = reports_dir()


def process_analysis(pdf_path, inputs, report_path=None, pdf_data=None):
    """
    Run the full analysis flow.

    pdf_path: str or None, path to the Serasa PDF. May be None when
        pdf_data is provided (e.g. data fetched from the Serasa API).
    inputs: dict with:
        - requested_limit (float)
        - scores (tuple 4x, 1-5) or None if auto
        - auto_scores (bool, optional) - True to use automatic scoring
        - manual_overrides (dict, optional) - keys: financial/payment_history/
          operational/legal with manual score values
        - references (str 'Sim'/'Nao')
        - analyst (str)
        - notes (str)
    report_path: str, optional path for the generated PDF
    pdf_data: dict, optional pre-extracted data. When provided, the PDF is not
        re-extracted (preserves any manual edits made in the GUI modal).
        Also allows running the analysis without a PDF (API integration).

    Returns a dict with 'pdf_data', 'calcs', 'report_path', 'history_path',
    'auto_scores_details'.
    Raises FileNotFoundError if the PDF is missing and no pdf_data is given.
    """
    if pdf_data is None and (not pdf_path or not os.path.exists(pdf_path)):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    # 1. Extract PDF data (or reuse pre-extracted/manually edited data)
    if pdf_data is None:
        pdf_data = extract_pdf_data(pdf_path)

    # 2. Determine scores (auto or manual)
    auto_scores_enabled = inputs.get("auto_scores", False)
    manual_overrides = inputs.get("manual_overrides", {})
    requested_limit = inputs.get("requested_limit")

    if auto_scores_enabled:
        auto_details = calculate_auto_scores(pdf_data, requested_limit)
        scores = (
            manual_overrides.get("financial", auto_details["financial"][0]),
            manual_overrides.get("payment_history", auto_details["payment_history"][0]),
            manual_overrides.get("operational", auto_details["operational"][0]),
            manual_overrides.get("legal", auto_details["legal"][0]),
        )
    else:
        scores = inputs.get("scores", (3, 3, 3, 3))
        auto_details = None

    # 3. Calculate (uses editable PARAMS from config)
    calcs = calculate(pdf_data, scores, requested_limit)

    # 4. Check hard blocks (override recommendation if needed)
    blocked, override_rec, block_reason = check_hard_blocks(
        pdf_data, requested_limit
    )
    if blocked and override_rec:
        calcs["recommendation"] = override_rec
        calcs["block_reason"] = block_reason

    # 5. Generate formatted PDF report
    report_inputs = dict(inputs)
    if auto_scores_enabled and auto_details:
        report_inputs["auto_scores"] = True
        report_inputs["auto_scores_details"] = auto_details
        report_inputs["scores"] = scores
    output_path = generate_report(pdf_data, report_inputs, calcs, output_path=report_path)

    # 6. Record JSON history
    final_history = add_to_history(pdf_data, inputs, calcs, output_path)

    result = {
        "pdf_data": pdf_data,
        "calcs": calcs,
        "report_path": output_path,
        "history_path": final_history,
    }

    if auto_scores_enabled:
        result["auto_scores_details"] = auto_details
        result["scores_used"] = scores

    return result
