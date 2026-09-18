"""The quote as the customer receives it.

Rendered as a self-contained, print-ready HTML document rather than a PDF.
That is a deliberate choice, not a shortcut: a link works in WhatsApp, which is
how an Indian SMB actually sends a quote, it opens on any phone without a
download, the customer can accept or decline from the same page, and the browser
prints it to PDF when a paper copy is genuinely needed. Server-side PDF would add
a native rendering dependency (cairo/pango) to the API image for a file most
recipients would never open twice.

Every figure here comes from the stored quote row, never recomputed. A document
reprinted in two years has to show what was sent, even if the pricing rules have
moved on since.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from typing import Any

INK = "#1b1f3b"
ACCENT = "#e8622c"
CREAM = "#f7f4ef"
MUTED = "#6b6862"
RULE = "#e9e6e0"


def _fmt(amount: Any, currency: str) -> str:
    symbol = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}.get(
        currency.upper(), f"{escape(currency)} "
    )
    try:
        value = float(amount or 0)
    except (TypeError, ValueError):
        value = 0.0
    # Indian grouping: 12,34,567.89 rather than 1,234,567.89. Getting this wrong
    # on a document someone signs reads as carelessness about their money.
    if currency.upper() == "INR":
        whole, _, frac = f"{value:.2f}".partition(".")
        sign = "-" if whole.startswith("-") else ""
        whole = whole.lstrip("-")
        if len(whole) > 3:
            head, tail = whole[:-3], whole[-3:]
            parts: list[str] = []
            while len(head) > 2:
                parts.insert(0, head[-2:])
                head = head[:-2]
            if head:
                parts.insert(0, head)
            whole = ",".join([*parts, tail])
        return f"{symbol}{sign}{whole}.{frac}"
    return f"{symbol}{value:,.2f}"


def _date(value: str | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d %b %Y")
    except ValueError:
        return value


def _status_chip(status: str) -> str:
    palette = {
        "issued": ("#1d4ed8", "#eff6ff"),
        "accepted": ("#15803d", "#f0fdf4"),
        "rejected": ("#b91c1c", "#fef2f2"),
        "expired": ("#b45309", "#fffbeb"),
        "cancelled": ("#6b6862", "#f4f2ee"),
        "superseded": ("#6b6862", "#f4f2ee"),
    }
    fg, bg = palette.get(status, (MUTED, "#f4f2ee"))
    label = {"issued": "Awaiting your response"}.get(status, status.replace("_", " ").title())
    return (
        f'<span style="display:inline-block;padding:5px 12px;border-radius:999px;'
        f"background:{bg};color:{fg};font-size:12.5px;font-weight:600;"
        f'letter-spacing:.02em;">{escape(label)}</span>'
    )


def render_quote_document(
    *,
    quote: dict[str, Any],
    business_name: str,
    business_tagline: str | None = None,
    can_decide: bool = False,
) -> str:
    currency = str(quote.get("currency") or "INR")
    status = str(quote.get("status") or "draft")
    items = quote.get("items") or []
    charges = quote.get("charges") or []

    rows = []
    for item in items:
        desc = (
            f'<div style="color:{MUTED};font-size:13px;margin-top:3px;">'
            f"{escape(str(item.get('description') or ''))}</div>"
            if item.get("description")
            else ""
        )
        qty = str(item.get("quantity") or "1")
        unit = f" {escape(str(item['unit_label']))}" if item.get("unit_label") else ""
        discount_note = ""
        if item.get("line_discount") and float(item["line_discount"]) > 0:
            discount_note = (
                f'<div style="color:{MUTED};font-size:12px;">'
                f"less {_fmt(item['line_discount'], currency)}</div>"
            )
        rows.append(
            f"""<tr>
  <td style="padding:14px 0;border-bottom:1px solid {RULE};vertical-align:top;">
    <div style="font-weight:600;color:{INK};">{escape(str(item.get("title") or ""))}</div>{desc}
  </td>
  <td style="padding:14px 0;border-bottom:1px solid {RULE};text-align:right;
             white-space:nowrap;font-variant-numeric:tabular-nums;">{escape(qty)}{unit}</td>
  <td style="padding:14px 0;border-bottom:1px solid {RULE};text-align:right;
             white-space:nowrap;font-variant-numeric:tabular-nums;">
    {_fmt(item.get("unit_price"), currency)}{discount_note}</td>
  <td style="padding:14px 0;border-bottom:1px solid {RULE};text-align:right;
             white-space:nowrap;font-weight:600;font-variant-numeric:tabular-nums;">
    {_fmt(item.get("line_total"), currency)}</td>
</tr>"""
        )

    for charge in charges:
        rows.append(
            f"""<tr>
  <td style="padding:14px 0;border-bottom:1px solid {RULE};color:{MUTED};">
    {escape(str(charge.get("label") or "Charge"))}</td>
  <td style="border-bottom:1px solid {RULE};"></td>
  <td style="border-bottom:1px solid {RULE};"></td>
  <td style="padding:14px 0;border-bottom:1px solid {RULE};text-align:right;
             white-space:nowrap;font-variant-numeric:tabular-nums;">
    {_fmt(charge.get("amount"), currency)}</td>
</tr>"""
        )

    def total_row(label: str, value: Any, *, strong: bool = False) -> str:
        weight = "700" if strong else "400"
        size = "17px" if strong else "14px"
        colour = INK if strong else MUTED
        return (
            f'<tr><td style="padding:6px 0;color:{colour};font-size:{size};">{escape(label)}</td>'
            f'<td style="padding:6px 0;text-align:right;font-weight:{weight};font-size:{size};'
            f'color:{INK};white-space:nowrap;font-variant-numeric:tabular-nums;">'
            f"{_fmt(value, currency)}</td></tr>"
        )

    totals = [total_row("Subtotal", quote.get("subtotal"))]
    if float(quote.get("discount_amount") or 0) > 0:
        totals.append(total_row("Discount", quote.get("discount_amount")))
    if float(quote.get("charges_amount") or 0) > 0:
        totals.append(total_row("Charges", quote.get("charges_amount")))
    if float(quote.get("tax_amount") or 0) > 0:
        totals.append(total_row("Tax", quote.get("tax_amount")))
    totals.append(
        f'<tr><td colspan="2" style="padding-top:10px;border-top:1px solid {RULE};"></td></tr>'
    )
    totals.append(total_row("Total", quote.get("total"), strong=True))
    if float(quote.get("deposit_amount") or 0) > 0:
        totals.append(total_row("Deposit due now", quote.get("deposit_amount")))

    validity = ""
    if quote.get("valid_until"):
        note = (
            "This quote has expired."
            if status == "expired"
            else f"Valid until {_date(quote.get('valid_until'))}"
        )
        validity = f'<p style="margin:0;color:{MUTED};font-size:13px;">{escape(note)}</p>'

    terms_block = ""
    if quote.get("terms"):
        terms_block = f"""
<section style="margin-top:34px;padding-top:22px;border-top:1px solid {RULE};">
  <h2 style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;
             color:{MUTED};margin:0 0 10px;">Terms</h2>
  <div style="color:{INK};font-size:14px;line-height:1.7;white-space:pre-wrap;">{
            escape(str(quote["terms"]))
        }</div>
</section>"""

    notes_block = ""
    if quote.get("notes"):
        notes_block = f"""
<section style="margin-top:24px;">
  <div style="color:{MUTED};font-size:14px;line-height:1.7;white-space:pre-wrap;">{
            escape(str(quote["notes"]))
        }</div>
</section>"""

    # Only rendered while the offer is actually open. Showing dead buttons on an
    # expired or already-answered quote invites a click that cannot work.
    actions = ""
    if can_decide and status == "issued":
        actions = f"""
<section class="no-print" style="margin-top:32px;padding-top:24px;border-top:1px solid {RULE};">
  <p style="margin:0 0 14px;color:{MUTED};font-size:14px;">
    Let {escape(business_name)} know how you would like to proceed.</p>
  <form method="post" style="display:flex;gap:10px;flex-wrap:wrap;">
    <button name="decision" value="accepted" type="submit"
      style="background:{ACCENT};color:#fff;border:0;border-radius:8px;padding:13px 26px;
             font-size:15px;font-weight:600;cursor:pointer;">Accept this quote</button>
    <button name="decision" value="rejected" type="submit"
      style="background:#fff;color:{INK};border:1px solid {RULE};border-radius:8px;
             padding:13px 26px;font-size:15px;font-weight:600;cursor:pointer;">Decline</button>
  </form>
</section>"""

    decided = ""
    if status in {"accepted", "rejected"}:
        when = _date(quote.get("accepted_at") or quote.get("rejected_at"))
        word = "accepted" if status == "accepted" else "declined"
        decided = (
            f'<section style="margin-top:28px;padding:16px 18px;border-radius:10px;'
            f'background:{CREAM};color:{INK};font-size:14px;">'
            f"You {escape(word)} this quote on {escape(when)}.</section>"
        )

    title = escape(str(quote.get("title") or "Quotation"))
    number = escape(str(quote.get("quote_number") or ""))
    revision = int(quote.get("revision") or 1)
    rev_label = f" &middot; Revision {revision}" if revision > 1 else ""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{number} &mdash; {escape(business_name)}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ margin:0; background:{CREAM}; color:{INK};
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;
         -webkit-font-smoothing:antialiased; }}
  .sheet {{ max-width:720px; margin:0 auto; padding:28px 16px 64px; }}
  .card {{ background:#fff; border:1px solid {RULE}; border-radius:14px; padding:38px 34px; }}
  table {{ width:100%; border-collapse:collapse; }}
  @media print {{
    body {{ background:#fff; }}
    .card {{ border:0; padding:0; }}
    .sheet {{ padding:0; max-width:none; }}
    .no-print {{ display:none !important; }}
  }}
  @media (max-width:560px) {{
    .card {{ padding:24px 18px; }}
    .hide-sm {{ display:none; }}
  }}
</style>
</head>
<body>
<div class="sheet">
  <div style="display:flex;justify-content:space-between;align-items:baseline;
              margin-bottom:18px;padding:0 4px;">
    <span style="font-weight:700;letter-spacing:.14em;font-size:15px;">
      {escape(business_name).upper()}</span>
    <span class="no-print" style="color:{MUTED};font-size:13px;">{_status_chip(status)}</span>
  </div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap;
                align-items:flex-start;margin-bottom:26px;">
      <div>
        <h1 style="margin:0 0 6px;font-size:23px;font-weight:650;">{title}</h1>
        <div style="color:{MUTED};font-size:14px;">{number}{rev_label}</div>
        {f'<div style="color:{MUTED};font-size:13px;margin-top:4px;">{escape(business_tagline)}</div>' if business_tagline else ""}
      </div>
      <div style="text-align:right;">{validity}</div>
    </div>

    <table>
      <thead>
        <tr style="color:{MUTED};font-size:12px;letter-spacing:.06em;text-transform:uppercase;">
          <th style="text-align:left;padding-bottom:10px;font-weight:600;">Item</th>
          <th style="text-align:right;padding-bottom:10px;font-weight:600;">Qty</th>
          <th style="text-align:right;padding-bottom:10px;font-weight:600;" class="hide-sm">Rate</th>
          <th style="text-align:right;padding-bottom:10px;font-weight:600;">Amount</th>
        </tr>
      </thead>
      <tbody>{"".join(rows)}</tbody>
    </table>

    <table style="margin-top:22px;margin-left:auto;max-width:330px;">
      {"".join(totals)}
    </table>
    {notes_block}{terms_block}{decided}{actions}
  </div>

  <p style="text-align:center;color:{MUTED};font-size:12px;margin-top:22px;">
    Sent by {escape(business_name)} &middot; powered by LOCAH
  </p>
</div>
</body>
</html>"""


def rendered_at() -> str:
    return datetime.now(timezone.utc).isoformat()
