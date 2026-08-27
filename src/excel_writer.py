"""
Module that fills in the Excel model with the analysis data
and saves it as a new file (history).

Strategy:
- Keeps the original Excel formulas intact.
- Fills in the 'Cadastro' sheet with data extracted from the PDF + user inputs.
- Fills in the scores (1-5) on the 'Análise' sheet.
- When opened in Excel, the formulas recalculate automatically.
"""
import os
import re
from datetime import datetime

from openpyxl import load_workbook


def safe_filename(legal_name, cnpj):
    """Generate a safe filename with CNPJ and date."""
    name = re.sub(r'[\\/:*?"<>|]', '', legal_name or '')
    name = re.sub(r'\s+', '_', name.strip()).upper()[:50]
    cnpj_digits = re.sub(r'\D', '', cnpj or '')
    date = datetime.now().strftime('%Y%m%d')
    return f"Credit_Analysis_{name}_{cnpj_digits}_{date}.xlsx"


def fill_excel(model_path, output_path, pdf_data, inputs, calcs):
    """
    Fill in the Excel model and save it to output_path.

    pdf_data: dict extracted from the PDF (pdf_extractor.extract_pdf_data)
    inputs: dict with manual user fields:
        - requested_limit (float)
        - scores (tuple 4x, 1-5)
        - references (str 'Sim'/'Nao')
        - analyst (str)
        - notes (str)
    calcs: dict returned by calculations.calculate
    """
    wb = load_workbook(model_path)

    # --- Cadastro sheet ---
    ws_cad = wb['Cadastro']
    now = datetime.now()

    # Columns: A=Date, B=CNPJ, C=Legal name, D=Trading name, E=City/State, F=Segment,
    #          G=Market years, H=Monthly revenue, I=Capital, J=Requested limit,
    #          K=Score, L=Restrictions, M=References, N=Analyst, O=Notes
    ws_cad['A2'] = now
    ws_cad['B2'] = pdf_data.get('cnpj', '')
    legal_name = pdf_data.get('legal_name', '')
    ws_cad['C2'] = legal_name
    city = pdf_data.get('city', '')
    state = pdf_data.get('state', '')
    ws_cad['E2'] = f"{city}/{state}" if (city and state) else ''
    ws_cad['F2'] = pdf_data.get('segment', '')
    ws_cad['G2'] = pdf_data.get('market_years')
    ws_cad['H2'] = pdf_data.get('monthly_revenue')
    ws_cad['I2'] = pdf_data.get('share_capital')
    ws_cad['J2'] = inputs.get('requested_limit')
    ws_cad['K2'] = pdf_data.get('serasa_score')
    has_rest = pdf_data.get('has_restrictions')
    ws_cad['L2'] = 'Sim' if has_rest else 'Não'
    ws_cad['M2'] = inputs.get('references', 'Não')
    ws_cad['N2'] = inputs.get('analyst', '')
    ws_cad['O2'] = inputs.get('notes', '')

    # --- Análise sheet ---
    ws_ana = wb['Análise']
    ws_ana['B4'] = legal_name
    ws_ana['B8'] = inputs.get('requested_limit')
    scores = inputs.get('scores', (3, 3, 3, 3))
    ws_ana['B16'] = scores[0]
    ws_ana['B17'] = scores[1]
    ws_ana['B18'] = scores[2]
    ws_ana['B19'] = scores[3]

    # Ensure output directory exists
    output_dir = os.path.dirname(os.path.abspath(output_path))
    os.makedirs(output_dir, exist_ok=True)

    wb.save(output_path)
    return output_path
