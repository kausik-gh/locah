"""Scanning and labels at the counter (Capability Universe §14.3).

* Packaged goods scan their GTIN (checked with the GS1 check digit).
* Loose goods without a barcode get an in-store code: EAN-13 starting "20"
  (GS1's range for restricted in-store circulation; verify at build, VB-21),
  printed on a label sheet or a label printer.
* Weighed goods: a label-printing scale prints a barcode carrying the item
  code and the weight or price. The layout differs between scales, so it is a
  per-business format set during the pilot (VB-16) — never assumed.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from platform_core.catalog.offering_kinds import gtin_ok
from platform_core.exceptions import ValidationError

IN_STORE_PREFIX = "20"


def check_digit(body: str) -> str:
    total = sum(int(d) * (3 if i % 2 == 0 else 1) for i, d in enumerate(reversed(body)))
    return str((10 - total % 10) % 10)


def in_store_code(serial: int) -> str:
    """The n-th in-store code: 20 + ten digits + check digit."""
    if not 1 <= serial <= 9_999_999_999:
        raise ValidationError("In-store code serial out of range")
    body = f"{IN_STORE_PREFIX}{serial:010d}"
    return body + check_digit(body)


@dataclass(frozen=True)
class WeighedFormat:
    prefix: str
    item_digits: int
    value: str  # "weight" (grams) or "price" (paise)
    value_digits: int
    value_decimals: int  # how many of the value digits are after the decimal point (kg or rupees)

    @property
    def length(self) -> int:
        return len(self.prefix) + self.item_digits + self.value_digits + 1

    def as_dict(self) -> dict[str, Any]:
        return {"prefix": self.prefix, "item_digits": self.item_digits, "value": self.value,
                "value_digits": self.value_digits, "value_decimals": self.value_decimals}


def clean_weighed_format(raw: dict[str, Any] | None) -> WeighedFormat | None:
    if not raw:
        return None
    prefix = str(raw.get("prefix") or "").strip()
    try:
        item_digits = int(raw.get("item_digits"))  # type: ignore[arg-type]
        value_digits = int(raw.get("value_digits"))  # type: ignore[arg-type]
        decimals = int(raw.get("value_decimals", 3 if raw.get("value") == "weight" else 2))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Weighed label: digits must be numbers", details={"field": "weighed_label"}) from exc
    value = raw.get("value")
    if not prefix.isdigit() or not 1 <= len(prefix) <= 3:
        raise ValidationError("Weighed label: the prefix is 1–3 digits", details={"field": "weighed_label"})
    if IN_STORE_PREFIX.startswith(prefix) or prefix.startswith(IN_STORE_PREFIX):
        raise ValidationError("Weighed label: that prefix clashes with in-store codes (20…)",
                              details={"field": "weighed_label"})
    if value not in ("weight", "price"):
        raise ValidationError("Weighed label: the value is the weight or the price", details={"field": "weighed_label"})
    fmt = WeighedFormat(prefix, item_digits, value, value_digits, decimals)
    if not 1 <= item_digits <= 7 or not 3 <= value_digits <= 7 or not 0 <= decimals <= value_digits \
            or fmt.length != 13:
        raise ValidationError("Weighed label: prefix + item + value + check digit must make 13 digits",
                              details={"field": "weighed_label"})
    return fmt


@dataclass(frozen=True)
class WeighedScan:
    item_code: str
    value: Decimal  # kg for weight, rupees for price
    kind: str


def decode_weighed(code: str, fmt: WeighedFormat | None) -> WeighedScan | None:
    """The item and weight/price in a scale label, or None if it is not one."""
    if fmt is None or len(code) != fmt.length or not code.isdigit() or not code.startswith(fmt.prefix):
        return None
    if not gtin_ok(code):
        raise ValidationError("That label did not scan cleanly — scan it again")
    start = len(fmt.prefix)
    item = code[start:start + fmt.item_digits]
    raw = code[start + fmt.item_digits:start + fmt.item_digits + fmt.value_digits]
    value = Decimal(int(raw)).scaleb(-fmt.value_decimals)
    return WeighedScan(item, value, fmt.value)


def label_sheet(labels: list[dict[str, Any]], *, layout: str = "a4") -> bytes:
    """Printable labels: an A4 sheet (3 × 8) or one 50 × 25 mm label per page.
    Each label: name, price line, EAN-13 barcode."""
    from reportlab.graphics.barcode.eanbc import Ean13BarcodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    from platform_core.documents.renderer import _fonts

    _fonts()
    buf = io.BytesIO()
    if layout == "label_50x25":
        size = (50 * mm, 25 * mm)
        c = canvas.Canvas(buf, pagesize=size, invariant=1)
        for lab in labels:
            _draw_label(c, lab, 0, 0, size[0], size[1], Ean13BarcodeWidget, Drawing, mm)
            c.showPage()
    else:
        c = canvas.Canvas(buf, pagesize=A4, invariant=1)
        cols, rows = 3, 8
        w, h = (A4[0] - 16 * mm) / cols, (A4[1] - 20 * mm) / rows
        for i, lab in enumerate(labels):
            slot = i % (cols * rows)
            if i and slot == 0:
                c.showPage()
            x = 8 * mm + (slot % cols) * w
            y = A4[1] - 10 * mm - (slot // cols + 1) * h
            _draw_label(c, lab, x, y, w, h, Ean13BarcodeWidget, Drawing, mm)
    c.save()
    return buf.getvalue()


def _draw_label(c: Any, lab: dict[str, Any], x: float, y: float, w: float, h: float,
                widget: Any, drawing: Any, mm: float) -> None:
    from reportlab.graphics import renderPDF

    c.setFont("LocahSans-Bold", 7.5)
    c.drawString(x + 2 * mm, y + h - 4 * mm, str(lab.get("title", ""))[:34])
    c.setFont("LocahSans", 7)
    if lab.get("price"):
        c.drawString(x + 2 * mm, y + h - 7.5 * mm, str(lab["price"]))
    code = str(lab["code"])
    bc = widget()
    bc.value = code[:12]
    bc.barHeight = max(h - 14 * mm, 6 * mm)
    bc.fontName = "LocahSans"
    bc.fontSize = 6
    x0, y0, x1, y1 = bc.getBounds()
    bw, bh = x1 - x0, y1 - y0
    scale = min((w - 4 * mm) / bw, 1.0)
    d = drawing(bw * scale, bh * scale)
    bc.x, bc.y = 0, 0
    d.add(bc)
    d.scale(scale, scale)
    renderPDF.draw(d, c, x + 2 * mm, y + 1.5 * mm)
