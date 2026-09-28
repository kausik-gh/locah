"""Render invoices, credit notes, receipts, quotes, certificates and report
cards from structured data (Capability Universe §24 #7, §14.4 outputs).

* One spec, three layouts: A4, and 80 mm / 58 mm thermal receipts.
* Deterministic: the same spec renders byte-identical PDFs (reportlab
  `invariant`), so a stored hash proves a document was not altered.
* Money and numbers arrive already formatted by the caller; the renderer
  never computes tax or totals.
* Fonts are bundled (DejaVu Sans, with the ₹ sign) so output does not depend
  on the host. Known limit: reportlab does not shape Indic scripts, so Tamil
  or Hindi text in a PDF is not rendered correctly (ledger note).
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_FONT_DIR = Path(__file__).with_name("fonts")
_REGISTERED = False


def _fonts() -> None:
    global _REGISTERED
    if not _REGISTERED:
        pdfmetrics.registerFont(TTFont("LocahSans", str(_FONT_DIR / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("LocahSans-Bold", str(_FONT_DIR / "DejaVuSans-Bold.ttf")))
        _REGISTERED = True


@dataclass
class DocSpec:
    title: str  # "Tax invoice", "Bill of supply", "Credit note", "Receipt"...
    issuer: list[str]  # business name first, then address / GSTIN / phone lines
    number: str = ""
    date: str = ""
    party_label: str = "Bill to"
    party: list[str] = field(default_factory=list)
    meta: list[tuple[str, str]] = field(default_factory=list)  # ("Place of supply", "Tamil Nadu (33)")
    columns: list[str] = field(default_factory=list)
    align: list[str] = field(default_factory=list)  # "l" | "r" per column
    rows: list[list[str]] = field(default_factory=list)
    totals: list[tuple[str, str]] = field(default_factory=list)  # last row is the grand total
    notes: list[str] = field(default_factory=list)
    footer: str = ""
    status_banner: str = ""  # e.g. "CANCELLED" — a cancelled invoice keeps its number, marked


def _styles(size: float) -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName="LocahSans", fontSize=size, leading=size * 1.35)
    return {
        "base": base,
        "bold": ParagraphStyle("bold", parent=base, fontName="LocahSans-Bold"),
        "title": ParagraphStyle("title", parent=base, fontName="LocahSans-Bold", fontSize=size * 1.6,
                                leading=size * 2.0),
        "right": ParagraphStyle("right", parent=base, alignment=TA_RIGHT),
        "center": ParagraphStyle("center", parent=base, alignment=TA_CENTER),
        "muted": ParagraphStyle("muted", parent=base, textColor=colors.HexColor("#555555"), fontSize=size * 0.9),
        "banner": ParagraphStyle("banner", parent=base, fontName="LocahSans-Bold", textColor=colors.HexColor("#b91c1c"),
                                 fontSize=size * 1.3, alignment=TA_CENTER),
    }


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    safe = (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def render_pdf(spec: DocSpec, layout: str = "a4") -> bytes:
    _fonts()
    thermal = layout in ("thermal_80", "thermal_58")
    width = {"thermal_80": 80 * mm, "thermal_58": 58 * mm}.get(layout, A4[0])
    margin = 3 * mm if thermal else 16 * mm
    size = 7.5 if layout == "thermal_58" else 8.5 if thermal else 9.5
    st = _styles(size)
    story: list[Flowable] = []

    if spec.status_banner:
        story += [_p(spec.status_banner, st["banner"]), Spacer(1, 4)]
    head_style = st["center"] if thermal else st["base"]
    story.append(_p(spec.issuer[0] if spec.issuer else "", ParagraphStyle("iss", parent=st["title"],
                                                                           alignment=TA_CENTER if thermal else 0)))
    for line in spec.issuer[1:]:
        story.append(_p(line, ParagraphStyle("il", parent=st["muted"], alignment=TA_CENTER if thermal else 0)))
    story.append(Spacer(1, 6))
    title_line = spec.title + (f"  ·  {spec.number}" if spec.number else "")
    story.append(_p(title_line, ParagraphStyle("t", parent=st["bold"], fontSize=size * 1.2,
                                               alignment=TA_CENTER if thermal else 0)))
    if spec.date:
        story.append(_p(spec.date, head_style))
    story.append(Spacer(1, 6))

    usable = width - 2 * margin
    if spec.party or spec.meta:
        left = [_p(spec.party_label, st["bold"])] + [_p(x, st["base"]) for x in spec.party] if spec.party else []
        right = [_p(f"{k}: {v}", st["base"]) for k, v in spec.meta]
        if thermal:
            story += left + right + [Spacer(1, 4)]
        else:
            t = Table([[left or "", right or ""]], colWidths=[usable * 0.55, usable * 0.45])
            t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
            story += [t, Spacer(1, 8)]

    if spec.columns:
        n = len(spec.columns)
        align = spec.align or ["l"] + ["r"] * (n - 1)

        def cell(text: str, i: int, bold: bool = False) -> Paragraph:
            return _p(text, st["bold"] if bold else (st["right"] if align[i] == "r" else st["base"]))

        data = [[cell(c, i, True) for i, c in enumerate(spec.columns)]]
        data += [[cell(v, i) for i, v in enumerate(row)] for row in spec.rows]
        first = usable * (0.34 if thermal else 0.40)
        rest = (usable - first) / max(n - 1, 1)
        table = Table(data, colWidths=[first] + [rest] * (n - 1), repeatRows=1)
        table.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
            ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.HexColor("#999999")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ]))
        story += [table, Spacer(1, 6)]

    if spec.totals:
        rows = [[_p(k, st["base"]), _p(v, st["right"])] for k, v in spec.totals[:-1]]
        k, v = spec.totals[-1]
        rows.append([_p(k, st["bold"]), _p(v, ParagraphStyle("tv", parent=st["right"], fontName="LocahSans-Bold"))])
        tw = usable if thermal else usable * 0.5
        t = Table(rows, colWidths=[tw * 0.6, tw * 0.4], hAlign="RIGHT")
        t.setStyle(TableStyle([("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.black),
                               ("LEFTPADDING", (0, 0), (-1, -1), 1.5), ("RIGHTPADDING", (0, 0), (-1, -1), 1.5)]))
        story += [t, Spacer(1, 8)]

    for note in spec.notes:
        story.append(_p(note, st["muted"]))
    if spec.footer:
        story += [Spacer(1, 6), _p(spec.footer, st["center"] if thermal else st["muted"])]

    buf = io.BytesIO()
    height = A4[1] if not thermal else max(120 * mm, (60 + 7 * (len(spec.rows) + len(spec.totals) + len(spec.issuer)
                                                               + len(spec.party) + len(spec.meta) + len(spec.notes))) * mm)
    doc = SimpleDocTemplate(buf, pagesize=(width, height), leftMargin=margin, rightMargin=margin,
                            topMargin=margin, bottomMargin=margin, title=f"{spec.title} {spec.number}".strip(),
                            author=spec.issuer[0] if spec.issuer else "", invariant=1)
    doc.build(story)
    return buf.getvalue()
