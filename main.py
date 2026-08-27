"""
Command-line interface for the Automated Credit Analysis.

Alternative to the GUI (src/app.py). Run: python main.py
"""
import os
import sys

SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
sys.path.insert(0, SRC_DIR)

from processor import process_analysis  # noqa: E402


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


def get_number(prompt, default=None, minimum=None, maximum=None):
    """Read a number between minimum and maximum."""
    while True:
        val = get_float(prompt, default, minimum)
        if maximum is not None and val > maximum:
            print(f'  Must be <= {maximum}.')
            continue
        return val


def run():
    print('=' * 60)
    print('  AUTOMATED CREDIT ANALYSIS - SERASA (CLI)')
    print('=' * 60)

    pdf_path = input('\nSerasa PDF path (or drag the file here): ').strip().strip('"')
    if not pdf_path:
        print('No file provided.')
        return
    if not os.path.exists(pdf_path):
        print(f'[ERROR] File not found: {pdf_path}')
        input('Press Enter to exit...')
        return

    requested_limit = get_float('\nRequested limit (R$)', default=None, minimum=0)

    print('\nScores (1 = very poor ... 5 = excellent):')
    fin = get_number('  Financial capacity (1-5)', minimum=1, maximum=5)
    hist = get_number('  Payment history (1-5)', minimum=1, maximum=5)
    op = get_number('  Operational profile (1-5)', minimum=1, maximum=5)
    legal = get_number('  Legal risk (1-5)', minimum=1, maximum=5)

    references = input('  Commercial references OK? (Yes/No) [No]: ').strip() or 'No'
    references = 'Sim' if references.lower() in ('yes', 'y') else 'Não'
    analyst = input('  Analyst: ').strip() or ''
    notes = input('  Notes (optional): ').strip() or ''

    inputs = {
        'requested_limit': requested_limit,
        'scores': (fin, hist, op, legal),
        'references': references,
        'analyst': analyst,
        'notes': notes,
    }

    print('\nProcessing...')
    result = process_analysis(pdf_path, inputs)
    calcs = result['calcs']

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

    print(f'\n  Report PDF: {result["report_path"]}')
    print(f'  History: {result["history_path"]}')
    input('\nPress Enter to exit...')


if __name__ == '__main__':
    try:
        run()
    except EOFError:
        print()
    except KeyboardInterrupt:
        print('\nAnalysis cancelled.')
