"""
PDF report generator: creates a formatted, pleasant-ready credit analysis
report with the company logo, client data, scores and recommendation.

Uses ReportLab. The Excel model is no longer needed - all logic lives here
and the output is a professional PDF + a JSON history record.
"""
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from paths import assets_dir, outputs_dir

OUTPUT_DIR = outputs_dir()
ASSETS_DIR = assets_dir()

PRIMARY = colors.HexColor('#c8102e')   # Sulmag red
DARK = colors.HexColor('#1f2430')
LIGHT = colors.HexColor('#f4f5f7')
MID = colors.HexColor('#6b7280')

RECOMMENDATION_COLORS = {
    'Aprovar': colors.HexColor('#1a7f37'),
    'Aprovar com limite/entrada': colors.HexColor('#b45309'),
    'Negar ou exigir garantia': colors.HexColor('#c8102e'),
}


def _fmt_brl(value):
    if value is None:
        return '-'
    return f'R$ {value:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def _fmt_cnpj_br(cnpj):
    """Format CNPJ with Brazilian punctuation (16/16 already includes)."""
    return cnpj or '-'


def _cover_banner(doc):
    """Return the header banner flowables (logo + title)."""
    logo_path = os.path.join(ASSETS_DIR, 'credit-analysis.png')
    logo = Image(logo_path, width=34 * mm, height=34 * mm) if os.path.exists(logo_path) else None

    banner = []
    if logo:
        logo.hAlign = 'CENTER'
        banner.append(logo)
    banner.append(Spacer(1, 4 * mm))

    title_style = ParagraphStyle(
        'Title',
        parent=getSampleStyleSheet()['Title'],
        fontName='Helvetica-Bold',
        fontSize=20,
        textColor=PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=getSampleStyleSheet()['Normal'],
        fontName='Helvetica',
        fontSize=11,
        textColor=MID,
        alignment=TA_CENTER,
    )
    banner.append(Paragraph('RELATÓRIO DE ANÁLISE DE CRÉDITO', title_style))
    banner.append(Paragraph('PDF Serasa Experian &nbsp;•&nbsp; Avaliação de crédito B2B', subtitle_style))
    banner.append(Spacer(1, 6 * mm))
    return banner


def _section_style():
    return ParagraphStyle(
        'Section',
        parent=getSampleStyleSheet()['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        textColor=DARK,
        spaceBefore=8 * mm,
        spaceAfter=3 * mm,
    )


def _build_pdf(pdf_data, inputs, calcs, output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title='Relatório de Análise de Crédito',
        author='Sulmag - Análise de Crédito',
    )

    styles = getSampleStyleSheet()
    kv_style = ParagraphStyle('KV', parent=styles['Normal'], fontName='Helvetica', fontSize=10.5)
    kv_bold_style = ParagraphStyle('KVBold', parent=styles['Normal'],
                                   fontName='Helvetica-Bold', fontSize=10.5)
    data_style = ParagraphStyle('Data', parent=styles['Normal'], fontName='Helvetica', fontSize=10.5,
                                alignment=TA_CENTER, textColor=DARK)

    elements = _cover_banner(doc)

    # ---------- Client data ----------
    elements.append(Paragraph('Dados da Empresa', _section_style()))
    client_rows = [
        ('CNPJ', pdf_data.get('cnpj', '-')),
        ('Razão social', pdf_data.get('legal_name', '-')),
        ('Segmento', pdf_data.get('segment', '-')),
        ('Cidade/UF', f"{pdf_data.get('city', '-')}/{pdf_data.get('state', '-')}"),
        ('Tempo de mercado', f"{pdf_data.get('market_years', '-')} anos"),
        ('Situação cadastral', pdf_data.get('registration_status', '-')),
    ]
    client_data = [
        [Paragraph('Campo', kv_bold_style), Paragraph('Valor', kv_bold_style)],
    ] + [[Paragraph(k, kv_style), Paragraph(f'<b>{v}</b>', kv_style)] for k, v in client_rows]
    client_table = Table(client_data, colWidths=[40 * mm, 138 * mm])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT),
        ('TEXTCOLOR', (0, 0), (-1, -1), DARK),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d3d6da')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(client_table)

    # ---------- Scores / metrics ----------
    elements.append(Paragraph('Enquadramento e Metodologia', _section_style()))
    metrics = [
        ('Score Serasa (0-1000)', str(calcs.get('serasa_score', '-'))),
        ('Capital social', _fmt_brl(pdf_data.get('share_capital'))),
        ('Faturamento mensal estimado', _fmt_brl(pdf_data.get('monthly_revenue'))),
        ('Limite solicitado', _fmt_brl(inputs.get('requested_limit'))),
        ('Score interno', str(calcs.get('internal_score'))),
        ('Classificação interna', str(calcs.get('internal_class', '-'))),
        ('Classificação Serasa', str(calcs.get('serasa_class', '-'))),
        ('Classificação final', str(calcs.get('final_class', '-'))),
        ('Limite sugerido', _fmt_brl(calcs.get('suggested_limit'))),
        ('Cobertura do pedido', str(calcs.get('coverage', '-'))),
        ('Índice de exposição', f"{calcs.get('exposure_index', 0):.3f}"),
        ('Alerta de capital', str(calcs.get('capital_alert', '-'))),
    ]
    metric_data = [
        [Paragraph('Métrica', kv_bold_style), Paragraph('Resultado', kv_bold_style)],
    ] + [[Paragraph(k, kv_style), Paragraph(f'<b>{v}</b>', kv_style)] for k, v in metrics]
    metric_table = Table(metric_data, colWidths=[78 * mm, 100 * mm])
    metric_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT),
        ('TEXTCOLOR', (0, 0), (-1, -1), DARK),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d3d6da')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(metric_table)

    # ---------- Scores breakdown (1-5) ----------
    elements.append(Paragraph('Avaliação (notas de 1 a 5)', _section_style()))
    notas = inputs.get('scores', (0, 0, 0, 0))
    nota_rows = [
        ('Capacidade financeira', notas[0]),
        ('Histórico de pagamento', notas[1]),
        ('Perfil operacional', notas[2]),
        ('Risco jurídico', notas[3]),
    ]
    nota_data = [
        [Paragraph('Critério', kv_bold_style), Paragraph('Nota', kv_bold_style)],
    ] + [[Paragraph(k, kv_style), Paragraph(f'<b>{v}</b>', data_style)] for k, v in nota_rows]
    nota_table = Table(nota_data, colWidths=[138 * mm, 40 * mm])
    nota_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d3d6da')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(nota_table)

    # ---------- Recommendation (highlight) ----------
    elements.append(Spacer(1, 6 * mm))
    rec = str(calcs.get('recommendation', '-'))
    rec_color = RECOMMENDATION_COLORS.get(rec, DARK)

    rec_box = Table(
        [[Paragraph(f'<b>RECOMENDAÇÃO: {rec}</b>',
                    ParagraphStyle('Rec', parent=styles['Normal'], fontName='Helvetica-Bold',
                                   fontSize=15, textColor=colors.white, alignment=TA_CENTER))]],
        colWidths=[178 * mm],
    )
    rec_box.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), rec_color),
        ('TOPPADDING', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
    ]))
    elements.append(rec_box)

    # ---------- Footer info ----------
    elements.append(Spacer(1, 5 * mm))
    analyst = inputs.get('analyst', '')
    notes = inputs.get('notes', '')
    footer_lines = [f"Responsável pela análise: <b>{analyst or '-'}</b>"]
    if notes:
        footer_lines.append(f"Observações: {notes}")
    footer_text = '<br/>'.join(footer_lines)
    elements.append(Paragraph(footer_text, ParagraphStyle('Foot', parent=styles['Normal'],
                                                          fontSize=9.5, textColor=MID)))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} pelo sistema de análise de crédito.",
        ParagraphStyle('Gen', parent=styles['Normal'], fontSize=8.5, textColor=MID)))

    doc.build(elements)
    return output_path


def generate_report(pdf_data, inputs, calcs, output_path=None):
    """Generate the formatted PDF report and return its path."""
    if output_path is None:
        safe_name = str(pdf_data.get('legal_name', 'empresa')).replace('/', '_').replace(' ', '_')
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(
            OUTPUT_DIR,
            f"Relatorio_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )
    return _build_pdf(pdf_data, inputs, calcs, output_path)
