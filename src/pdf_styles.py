"""
Shared presentation styles and formatting helpers for the PDF report.

Centralizes colors, fonts, paragraph styles and table styles so the report
builder stays focused on assembling the document structure.
"""

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import TableStyle

PRIMARY = colors.HexColor("#c8102e")  # Sulmag red
DARK = colors.HexColor("#1f2430")
LIGHT = colors.HexColor("#f4f5f7")
MID = colors.HexColor("#6b7280")
GRID = colors.HexColor("#d3d6da")

RECOMMENDATION_COLORS = {
    "Aprovar": colors.HexColor("#1a7f37"),
    "Aprovar com limite/entrada": colors.HexColor("#b45309"),
    "Negar ou exigir garantia": colors.HexColor("#c8102e"),
}


class ReportStyles:
    """Factory for the report's paragraph and table styles."""

    def __init__(self, base=None):
        base = base or getSampleStyleSheet()
        self.base = base
        self.normal = base["Normal"]
        self.kv = ParagraphStyle(
            "KV", parent=self.normal, fontName="Helvetica", fontSize=10.5
        )
        self.kv_bold = ParagraphStyle(
            "KVBold",
            parent=self.normal,
            fontName="Helvetica-Bold",
            fontSize=10.5,
        )
        self.data = ParagraphStyle(
            "Data",
            parent=self.normal,
            fontName="Helvetica",
            fontSize=10.5,
            alignment=TA_CENTER,
            textColor=DARK,
        )
        self.section = ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=DARK,
            spaceBefore=8 * mm,
            spaceAfter=3 * mm,
        )

    def table(self, col_widths, center_column=False):
        """Default bordered KV table style."""
        commands = [
            ("BACKGROUND", (0, 0), (-1, 0), LIGHT),
            ("TEXTCOLOR", (0, 0), (-1, -1), DARK),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, GRID),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        if center_column:
            commands.append(("ALIGN", (1, 1), (1, -1), "CENTER"))
        return TableStyle(commands)


def fmt_brl(value):
    if value is None:
        return "-"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_cnpj_br(cnpj):
    return cnpj or "-"
