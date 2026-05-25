#!/usr/bin/env python3
"""Generate English translation PDF of The Primal Race."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib import colors

W, H = A4

def build_styles():
    base = getSampleStyleSheet()
    def s(name, parent="Normal", **kw):
        return ParagraphStyle(name, parent=base[parent], **kw)
    return {
        "cover_title_zh": s("ctz", fontSize=32, leading=40, alignment=TA_CENTER,
            spaceAfter=6, textColor=colors.HexColor("#1a1109")),
        "cover_title_en": s("cte", fontSize=18, leading=24, alignment=TA_CENTER,
            spaceAfter=24, textColor=colors.HexColor("#8b1a1a"), fontName="Times-Italic"),
        "cover_meta": s("cm", fontSize=11, leading=18, alignment=TA_CENTER,
            textColor=colors.HexColor("#6b5c47")),
        "cover_note": s("cn", fontSize=9, leading=14, alignment=TA_CENTER,
            textColor=colors.HexColor("#9a8c7a"), fontName="Times-Italic"),
        "chapter": s("ch", "Heading1", fontSize=16, leading=22, spaceBefore=0,
            spaceAfter=14, textColor=colors.HexColor("#8b1a1a"), fontName="Times-Bold"),
        "section": s("sec", "Heading2", fontSize=13, leading=18, spaceBefore=14,
            spaceAfter=8, textColor=colors.HexColor("#1a1109"), fontName="Times-Bold"),
        "subsec": s("ss", fontSize=11, leading=16, spaceBefore=10, spaceAfter=6,
            textColor=colors.HexColor("#1a1109"), fontName="Times-BoldItalic"),
        "body": s("body", fontSize=10.5, leading=17, alignment=TA_JUSTIFY,
            spaceAfter=8, firstLineIndent=18),
        "body_ni": s("bodyni", fontSize=10.5, leading=17, alignment=TA_JUSTIFY, spaceAfter=8),
        "quote": s("q", fontSize=10, leading=16, alignment=TA_JUSTIFY,
            leftIndent=24, rightIndent=12, spaceAfter=8, spaceBefore=4,
            textColor=colors.HexColor("#3a2f20"), fontName="Times-Italic"),
        "bullet": s("bul", fontSize=10, leading=16, leftIndent=20, spaceAfter=5, bulletIndent=8),
        "toc": s("toc", fontSize=11, leading=18, spaceAfter=4),
        "footnote": s("fn", fontSize=8.5, leading=13, textColor=colors.HexColor("#6b5c47")),
        "abrupt": s("ab", fontSize=10.5, leading=17, alignment=TA_JUSTIFY,
            spaceAfter=8, firstLineIndent=18,
            textColor=colors.HexColor("#8b1a1a"), fontName="Times-Italic"),
    }

def p(text, style):
    return Paragraph(text, style)

def hr():
    return HRFlowable(width="60%", thickness=0.5,
                      color=colors.HexColor("#c9bfad"),
                      hAlign="CENTER", spaceAfter=12, spaceBefore=12)

