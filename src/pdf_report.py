"""
PDF report generator: creates a formatted, pleasant-ready credit analysis
report with the company logo, client data, scores and recommendation.

Uses ReportLab. The Excel model is no longer needed - all logic lives here
and the output is a professional PDF + a JSON history record.

Presentation styles and helpers live in `pdf_styles`; this module assembles
the document from per-section builders.
"""

import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from paths import assets_dir, reports_dir

from pdf_styles import (
    DARK,
    MID,
    PRIMARY,
    RECOMMENDATION_COLORS,
    ReportStyles,
    fmt_brl,
    fmt_cnpj_br,
)

OUTPUT_DIR = reports_dir()
ASSETS_DIR = assets_dir()


def _cover_banner(styles):
    """Return the header banner flowables (logo + title)."""
    logo_path = os.path.join(ASSETS_DIR, "credit-analysis.png")
    logo = (
        Image(logo_path, width=34 * mm, height=34 * mm)
        if os.path.exists(logo_path)
        else None
    )

    banner = []
    if logo:
        logo.hAlign = "CENTER"
        banner.append(logo)
    banner.append(Spacer(1, 4 * mm))

    title_style = ParagraphStyle(
        "Title",
        parent=styles.base["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=PRIMARY,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles.base["Normal"],
        fontName="Helvetica",
        fontSize=11,
        textColor=MID,
        alignment=TA_CENTER,
    )
    banner.append(Paragraph("RELATÓRIO DE ANÁLISE DE CRÉDITO", title_style))
    banner.append(
        Paragraph(
            "PDF Serasa Experian &nbsp;•&nbsp; Avaliação de crédito B2B",
            subtitle_style,
        )
    )
    banner.append(Spacer(1, 6 * mm))
    return banner


def _kv_table(title, header, rows, col_widths, styles, data_value=False):
    """Build a labeled-header table (title section + rows) as flowables."""
    elements = [Paragraph(title, styles.section)]
    head = [Paragraph(h, styles.kv_bold) for h in header]
    value_style = styles.data if data_value else styles.kv
    table_rows = [head] + [
        [Paragraph(k, styles.kv), Paragraph(f"<b>{v}</b>", value_style)]
        for k, v in rows
    ]
    table = Table(table_rows, colWidths=col_widths)
    table.setStyle(styles.table(col_widths, center_column=data_value))
    elements.append(table)
    return elements


def _recommendation_box(rec, styles):
    rec_color = RECOMMENDATION_COLORS.get(rec, DARK)
    rec_style = ParagraphStyle(
        "Rec",
        parent=styles.normal,
        fontName="Helvetica-Bold",
        fontSize=15,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    box = Table([[Paragraph(f"<b>RECOMENDAÇÃO: {rec}</b>", rec_style)]],
                colWidths=[178 * mm])
    box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), rec_color),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    return [Spacer(1, 6 * mm), box]


def _footer(analyst, notes, styles):
    footer_lines = [f"Responsável pela análise: <b>{analyst or '-'}</b>"]
    if notes:
        footer_lines.append(f"Observações: {notes}")
    foot_style = ParagraphStyle(
        "Foot", parent=styles.normal, fontSize=9.5, textColor=MID
    )
    gen_style = ParagraphStyle(
        "Gen", parent=styles.normal, fontSize=8.5, textColor=MID
    )
    return [
        Spacer(1, 5 * mm),
        Paragraph("<br/>".join(footer_lines), foot_style),
        Spacer(1, 3 * mm),
        Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')} pelo "
            "sistema de análise de crédito.",
            gen_style,
        ),
    ]


def _build_pdf(pdf_data, inputs, calcs, output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title="Relatório de Análise de Crédito",
        author="Sulmag - Análise de Crédito",
    )

    styles = ReportStyles()
    elements = _cover_banner(styles)

    # ---------- Dados da empresa ----------
    elements += _kv_table(
        "Dados da Empresa",
        ("Campo", "Valor"),
        [
            ("CNPJ", fmt_cnpj_br(pdf_data.get("cnpj"))),
            ("Razão social", pdf_data.get("legal_name", "-")),
            ("Segmento", pdf_data.get("segment", "-")),
            (
                "Cidade/UF",
                f"{pdf_data.get('city', '-')}/{pdf_data.get('state', '-')}",
            ),
            ("Tempo de mercado", f"{pdf_data.get('market_years', '-')} anos"),
            ("Situação cadastral", pdf_data.get("registration_status", "-")),
        ],
        [40 * mm, 138 * mm],
        styles,
    )

    # ---------- Métricas / enquadramento ----------
    elements += _kv_table(
        "Enquadramento e Metodologia",
        ("Métrica", "Resultado"),
        [
            ("Score Serasa (0-1000)", str(calcs.get("serasa_score", "-"))),
            ("Capital social", fmt_brl(pdf_data.get("share_capital"))),
            ("Faturamento mensal estimado", fmt_brl(pdf_data.get("monthly_revenue"))),
            ("Limite solicitado", fmt_brl(inputs.get("requested_limit"))),
            ("Score interno", str(calcs.get("internal_score"))),
            ("Classificação interna", str(calcs.get("internal_class", "-"))),
            ("Classificação Serasa", str(calcs.get("serasa_class", "-"))),
            ("Classificação final", str(calcs.get("final_class", "-"))),
            ("Limite sugerido", fmt_brl(calcs.get("suggested_limit"))),
            ("Cobertura do pedido", str(calcs.get("coverage", "-"))),
            ("Índice de exposição", f"{calcs.get('exposure_index', 0):.3f}"),
            ("Alerta de capital", str(calcs.get("capital_alert", "-"))),
        ],
        [78 * mm, 100 * mm],
        styles,
    )

    # ---------- Notas (1-5) ----------
    notas = inputs.get("scores", (0, 0, 0, 0))
    elements += _kv_table(
        "Avaliação (notas de 1 a 5)",
        ("Critério", "Nota"),
        [
            ("Capacidade financeira", notas[0]),
            ("Histórico de pagamento", notas[1]),
            ("Perfil operacional", notas[2]),
            ("Risco jurídico", notas[3]),
        ],
        [138 * mm, 40 * mm],
        styles,
        data_value=True,
    )

    # ---------- Recomendação ----------
    elements += _recommendation_box(str(calcs.get("recommendation", "-")), styles)

    # ---------- Rodapé ----------
    elements += _footer(inputs.get("analyst", ""), inputs.get("notes", ""), styles)

    doc.build(elements)
    return output_path


def generate_report(pdf_data, inputs, calcs, output_path=None):
    """Generate the formatted PDF report and return its path."""
    if output_path is None:
        safe_name = (
            str(pdf_data.get("legal_name", "empresa"))
            .replace("/", "_")
            .replace(" ", "_")
        )
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        output_path = os.path.join(
            OUTPUT_DIR,
            f"Relatorio_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )
    return _build_pdf(pdf_data, inputs, calcs, output_path)
