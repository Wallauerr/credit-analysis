"""
Main program for Automated Credit Analysis.

Flow:
1. User provides the path of the Serasa PDF.
2. Extracts the PDF data automatically.
3. User enters the 4 scores (1-5) and the requested limit.
4. Calculates internal score, final classification and recommendation.
5. Fills in the Excel model and saves it as a new file.
6. Records it in the CSV history.
"""
import os
import sys
import traceback

from pdf_extractor import extract_pdf_data
from calculations import calculate
from excel_writer import fill_excel, safe_filename
from history import add_to_history


def find_model():
    """Try to locate the xlsx model file."""
    candidates = [
        'pICOLI E DENEGA.xlsx',
        'credit_analysis_model.xlsx',
    ]
    for name in candidates:
        for base in (os.path.dirname(os.path.abspath(__file__)), os.getcwd()):
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
    return None


def get_number(prompt, default=None, value_type=int, minimum=None, maximum=None):
    """Read a number from the user with validation."""
    while True:
        suffix = f' [{default}]' if default is not None else ''
        val = input(f'{prompt}{suffix}: ').strip()
        if val == '' and default is not None:
            return default
        try:
            num = value_type(val)
        except ValueError:
            print('  Invalid value. Please enter a number.')
            continue
        if minimum is not None and num < minimum:
            print(f'  Must be >= {minimum}.')
            continue
        if maximum is not None and num > maximum:
            print(f'  Must be <= {maximum}.')
            continue
        return num


def get_float(prompt, default=None, minimum=None):
    """Read a float number (accepts comma as decimal separator)."""
    while True:
        suffix = f' [{default}]' if default is not None else ''
        val = input(f'{prompt}{suffix}: ').strip()
        if val == '' and default is not None:
            return default
        val = val.replace('.', '').replace(',', '.')
        try:
            num = float(val)
        except ValueError:
            print('  Invalid value.')
            continue
        if minimum is not None and num < minimum:
            print(f'  Must be >= {minimum}.')
            continue
        return num


def run():
    print('=' * 60)
    print('  AUTOMATED CREDIT ANALYSIS - SERASA')
    print('=' * 60)

    # 1. Excel model
    model = find_model()
    if not model:
        print('\n[ERROR] Could not find the model file "pICOLI E DENEGA.xlsx".')
        print('Place this program in the same folder as the Excel model.')
        input('\nPress Enter to exit...')
        sys.exit(1)

    # 2. Serasa PDF
    pdf_path = input('\nSerasa PDF path (or drag the file here): ').strip().strip('"')
    if not pdf_path:
        print('No file provided.')
        sys.exit(1)
    if not os.path.exists(pdf_path):
        print(f'[ERROR] File not found: {pdf_path}')
        input('\nPress Enter to exit...')
        sys.exit(1)

    print('\n[1/4] Extracting PDF data...')
    try:
        pdf_data = extract_pdf_data(pdf_path)
    except Exception as e:
        print(f'[ERROR] Failed to read PDF: {e}')
        input('\nPress Enter to exit...')
        sys.exit(1)

    # Show extracted data
    print('\n--- Extracted PDF data ---')
    print(f'  CNPJ:            {pdf_data.get("cnpj", "-")}')
    print(f'  Legal name:      {pdf_data.get("legal_name", "-")}')
    print(f'  Serasa score:    {pdf_data.get("serasa_score", "-")}')
    print(f'  Share capital:   R$ {pdf_data.get("share_capital", "-"):,.2f}')
    print(f'  Monthly revenue: R$ {pdf_data.get("monthly_revenue", "-"):,.2f}')
    print(f'  Restrictions:    {"Yes" if pdf_data.get("has_restrictions") else "No"}')
    print(f'  Segment:         {pdf_data.get("segment", "-")}')
    print(f'  City/State:      {pdf_data.get("city", "-")}/{pdf_data.get("state", "-")}')
    print(f'  Market time:     {pdf_data.get("market_years", "-")} years')

    # 3. User inputs
    print('\n[2/4] Enter the analysis data:')
    requested_limit = get_float('\n  Requested limit (R$)', default=None, minimum=0)

    print('\n  Scores (1 = very poor ... 5 = excellent):')
    fin = get_number('    Financial capacity (1-5)', value_type=float, minimum=1, maximum=5)
    hist = get_number('    Payment history (1-5)', value_type=float, minimum=1, maximum=5)
    op = get_number('    Operational profile (1-5)', value_type=float, minimum=1, maximum=5)
    legal = get_number('    Legal risk (1-5)', value_type=float, minimum=1, maximum=5)

    references = input('  Commercial references OK? (Yes/No) [No]: ').strip() or 'No'
    if references.lower() in ('yes', 'y'):
        references = 'Sim'
    else:
        references = 'Não'

    analyst = input('  Analyst: ').strip() or ''
    notes = input('  Notes (optional): ').strip() or ''

    # 4. Calculations
    print('\n[3/4] Calculating...')
    calcs = calculate(pdf_data, (fin, hist, op, legal), requested_limit)

    print('\n--- Analysis result ---')
    print(f'  Internal score:      {calcs["internal_score"]}')
    print(f'  Internal class:      {calcs["internal_class"]}')
    print(f'  Serasa class:        {calcs["serasa_class"]}')
    print(f'  Final class:         {calcs["final_class"]}')
    print(f'  Suggested limit:     R$ {calcs["suggested_limit"]:,.2f}')
    print(f'  Coverage:            {calcs["coverage"]}')
    print(f'  Exposure index:      {calcs["exposure_index"]:.3f}')
    print(f'  Capital alert:       {calcs["capital_alert"]}')
    print(f'  >>> RECOMMENDATION:  {calcs["recommendation"]}')

    # 5. Fill Excel and save
    print('\n[4/4] Generating Excel file...')
    filename = safe_filename(pdf_data.get('legal_name', ''), pdf_data.get('cnpj', ''))
    export_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')
    os.makedirs(export_dir, exist_ok=True)
    output = os.path.join(export_dir, filename)

    inputs = {
        'requested_limit': requested_limit,
        'scores': (fin, hist, op, legal),
        'references': references,
        'analyst': analyst,
        'notes': notes,
    }

    try:
        fill_excel(model, output, pdf_data, inputs, calcs)
        add_to_history(pdf_data, inputs, calcs, output)
    except Exception as e:
        print(f'[ERROR] Failed to generate Excel: {e}')
        traceback.print_exc()

    print(f'\n✅ File saved at: {output}')
    print('   History updated in: analysis_history.csv')
    print('\nAnalysis completed successfully!')
    input('\nPress Enter to exit...')


if __name__ == '__main__':
    try:
        run()
    except EOFError:
        print()
    except KeyboardInterrupt:
        print('\nAnalysis cancelled.')
