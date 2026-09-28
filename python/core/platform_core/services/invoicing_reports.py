"""For the CA (Capability Universe §14.4): sales register, HSN summary,
tax-by-rate summary and a GSTR-1-ready worksheet, each also as CSV.

Every figure is read from issued documents — the amounts stored when each bill
was issued — never recomputed. Cancelled bills appear in the register marked
cancelled and count nowhere else. Credit notes reduce, debit notes add.

The GSTR-1 worksheet groups bills the way the return is organised (B2B, B2C,
credit/debit notes, HSN, documents issued). The exact portal / offline-tool
column format is to be verified at build (VB-21); thresholds that move bills
between sections are left to the CA and are not applied here.
"""

from __future__ import annotations

import csv
import io
import uuid
from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from platform_core.invoicing.states import state_label
from platform_core.invoicing.tax_engine import ZERO, dec
from platform_core.models import InvoicingDocument, InvoicingDocumentLine, InvoicingRegistration
from platform_core.services.invoicing import INVOICE_KINDS, KIND_LABEL

REPORTS = {
    "sales_register": "Sales register",
    "hsn_summary": "HSN / SAC summary",
    "tax_by_rate": "Tax by rate",
    "gstr1": "GSTR-1 worksheet",
    "documents": "Documents issued",
}


def _rate(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _sign(kind: str) -> int:
    return -1 if kind == "credit_note" else 1


def _f(v: Decimal) -> float:
    return float(v.quantize(Decimal("0.01")))


async def _docs(session: AsyncSession, business_id: uuid.UUID, start: date, end: date,
                *, include_cancelled: bool = False) -> list[tuple[InvoicingDocument, str]]:
    q = (select(InvoicingDocument, InvoicingRegistration.scheme)
         .join(InvoicingRegistration, InvoicingRegistration.id == InvoicingDocument.registration_id)
         .where(InvoicingDocument.business_id == business_id, InvoicingDocument.issue_date >= start,
                InvoicingDocument.issue_date <= end,
                InvoicingDocument.status.in_(("issued", "cancelled") if include_cancelled else ("issued",)))
         .order_by(InvoicingDocument.issue_date, InvoicingDocument.series_key, InvoicingDocument.seq))
    return [(d, s) for d, s in (await session.execute(q)).all()]


async def _lines(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[InvoicingDocumentLine]]:
    out: dict[uuid.UUID, list[InvoicingDocumentLine]] = defaultdict(list)
    if not ids:
        return out
    for row in (await session.execute(select(InvoicingDocumentLine).where(
            InvoicingDocumentLine.document_id.in_(ids)).order_by(InvoicingDocumentLine.sort_order))).scalars():
        out[row.document_id].append(row)
    return out


def _table(columns: list[tuple[str, str]], rows: list[dict[str, Any]], totals: dict[str, Any] | None = None,
           note: str | None = None) -> dict[str, Any]:
    return {"columns": [{"key": k, "label": label} for k, label in columns], "rows": rows,
            "totals": totals, "note": note}


async def sales_register(session: AsyncSession, business_id: uuid.UUID, start: date, end: date) -> dict[str, Any]:
    docs = await _docs(session, business_id, start, end, include_cancelled=True)
    rows = []
    t: defaultdict[str, Decimal] = defaultdict(lambda: ZERO)
    for d, _scheme in docs:
        s = _sign(d.doc_kind)
        live = d.status == "issued"
        row = {
            "date": d.issue_date.isoformat(), "number": d.number, "kind": KIND_LABEL[d.doc_kind],
            "status": "Cancelled" if not live else "Issued", "buyer": (d.buyer or {}).get("name") or "",
            "buyer_gstin": (d.buyer or {}).get("gstin") or "", "place_of_supply": state_label(d.place_of_supply),
            "taxable": _f(s * dec(d.taxable_total)), "cgst": _f(s * dec(d.cgst_total)),
            "sgst": _f(s * dec(d.sgst_total)), "igst": _f(s * dec(d.igst_total)),
            "round_off": _f(s * dec(d.round_off)), "total": _f(s * dec(d.grand_total)),
            "reverse_charge": "Yes" if d.reverse_charge else "No",
        }
        rows.append(row)
        if live:
            for k in ("taxable", "cgst", "sgst", "igst", "round_off", "total"):
                t[k] += Decimal(str(row[k]))
    return _table(
        [("date", "Date"), ("number", "Number"), ("kind", "Document"), ("status", "Status"), ("buyer", "Buyer"),
         ("buyer_gstin", "Buyer GSTIN"), ("place_of_supply", "Place of supply"), ("taxable", "Taxable value"),
         ("cgst", "CGST"), ("sgst", "SGST"), ("igst", "IGST"), ("round_off", "Round-off"), ("total", "Total"),
         ("reverse_charge", "Reverse charge")],
        rows, {k: _f(v) for k, v in t.items()},
        "Cancelled documents keep their numbers and are listed, but are not counted in the totals.")


async def _gst_lines(session: AsyncSession, business_id: uuid.UUID, start: date, end: date
                     ) -> list[tuple[InvoicingDocument, InvoicingDocumentLine]]:
    docs = [d for d, scheme in await _docs(session, business_id, start, end) if scheme == "regular"]
    by_doc = await _lines(session, [d.id for d in docs])
    return [(d, ln) for d in docs for ln in by_doc[d.id]]


async def hsn_summary(session: AsyncSession, business_id: uuid.UUID, start: date, end: date) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for d, ln in await _gst_lines(session, business_id, start, end):
        s = _sign(d.doc_kind)
        rate = _rate(dec(ln.tax_rate)) if ln.tax_rate is not None else ""
        key = (ln.hsn_sac or "Not set", ln.unit_label or "", rate)
        g = groups.setdefault(key, {"description": ln.title, "qty": ZERO, "taxable": ZERO, "cgst": ZERO,
                                    "sgst": ZERO, "igst": ZERO, "value": ZERO})
        if d.doc_kind in INVOICE_KINDS or d.note_reason == "return":
            g["qty"] += s * dec(ln.quantity)  # value-only notes change no quantity
        g["taxable"] += s * dec(ln.taxable_value)
        g["cgst"] += s * dec(ln.cgst)
        g["sgst"] += s * dec(ln.sgst)
        g["igst"] += s * dec(ln.igst)
        g["value"] += s * dec(ln.line_total)
    rows = [{"hsn_sac": k[0], "description": g["description"], "unit": k[1], "rate": k[2],
             "quantity": float(g["qty"]), "taxable": _f(g["taxable"]), "cgst": _f(g["cgst"]),
             "sgst": _f(g["sgst"]), "igst": _f(g["igst"]), "value": _f(g["value"])}
            for k, g in sorted(groups.items())]
    return _table(
        [("hsn_sac", "HSN / SAC"), ("description", "Description"), ("unit", "Unit"), ("rate", "GST %"),
         ("quantity", "Quantity"), ("taxable", "Taxable value"), ("cgst", "CGST"), ("sgst", "SGST"),
         ("igst", "IGST"), ("value", "Total value")], rows,
        note="Tax invoices and notes under regular GST registrations. Lines without an HSN/SAC show 'Not set'.")


async def tax_by_rate(session: AsyncSession, business_id: uuid.UUID, start: date, end: date) -> dict[str, Any]:
    groups: dict[Decimal, dict[str, Decimal]] = {}
    for d, ln in await _gst_lines(session, business_id, start, end):
        if ln.tax_rate is None:
            continue
        s = _sign(d.doc_kind)
        g = groups.setdefault(dec(ln.tax_rate), defaultdict(lambda: ZERO))
        g["taxable"] += s * dec(ln.taxable_value)
        g["cgst"] += s * dec(ln.cgst)
        g["sgst"] += s * dec(ln.sgst)
        g["igst"] += s * dec(ln.igst)
    rows = [{"rate": _rate(k), "taxable": _f(g["taxable"]), "cgst": _f(g["cgst"]), "sgst": _f(g["sgst"]),
             "igst": _f(g["igst"]), "tax": _f(g["cgst"] + g["sgst"] + g["igst"])}
            for k, g in sorted(groups.items())]
    totals = {k: _f(sum((Decimal(str(r[k])) for r in rows), ZERO)) for k in ("taxable", "cgst", "sgst", "igst", "tax")}
    return _table([("rate", "GST %"), ("taxable", "Taxable value"), ("cgst", "CGST"), ("sgst", "SGST"),
                   ("igst", "IGST"), ("tax", "Total tax")], rows, totals)


async def documents_issued(session: AsyncSession, business_id: uuid.UUID, start: date, end: date) -> dict[str, Any]:
    series: dict[tuple[str, str], dict[str, Any]] = {}
    for d, _ in await _docs(session, business_id, start, end, include_cancelled=True):
        key = (d.series_key or "", d.fy or "")
        g = series.setdefault(key, {"kind": KIND_LABEL[d.doc_kind] if d.doc_kind not in INVOICE_KINDS else "Bills",
                                    "first": d, "last": d, "seqs": [], "cancelled": 0})
        if (d.seq or 0) < (g["first"].seq or 0):
            g["first"] = d
        if (d.seq or 0) > (g["last"].seq or 0):
            g["last"] = d
        g["seqs"].append(d.seq or 0)
        g["cancelled"] += d.status == "cancelled"
    rows = []
    for g in series.values():
        seqs = sorted(g["seqs"])
        expected = seqs[-1] - seqs[0] + 1 if seqs else 0
        rows.append({"series": g["kind"], "from": g["first"].number, "to": g["last"].number, "total": len(seqs),
                     "cancelled": g["cancelled"], "net": len(seqs) - g["cancelled"],
                     "gaps": "None" if expected == len(seqs) else f"{expected - len(seqs)} missing"})
    return _table([("series", "Series"), ("from", "From"), ("to", "To"), ("total", "Issued"),
                   ("cancelled", "Cancelled"), ("net", "Net"), ("gaps", "Gaps")], rows,
                  note="Numbers are gapless per GSTIN × financial year × register; cancelled bills keep theirs.")


async def gstr1(session: AsyncSession, business_id: uuid.UUID, start: date, end: date) -> dict[str, Any]:
    b2b: list[dict[str, Any]] = []
    b2c: dict[tuple[str, str], dict[str, Decimal]] = {}
    b2c_inter: list[dict[str, Any]] = []
    notes: list[dict[str, Any]] = []
    docs = [d for d, scheme in await _docs(session, business_id, start, end) if scheme == "regular"]
    by_doc = await _lines(session, [d.id for d in docs])
    for d in docs:
        rates: dict[Decimal, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
        for ln in by_doc[d.id]:
            r = dec(ln.tax_rate) if ln.tax_rate is not None else ZERO
            rates[r]["taxable"] += dec(ln.taxable_value)
            rates[r]["cgst"] += dec(ln.cgst)
            rates[r]["sgst"] += dec(ln.sgst)
            rates[r]["igst"] += dec(ln.igst)
        gstin = (d.buyer or {}).get("gstin")
        for rate, g in sorted(rates.items()):
            base = {"rate": _rate(rate), "taxable": _f(g["taxable"]), "igst": _f(g["igst"]),
                    "cgst": _f(g["cgst"]), "sgst": _f(g["sgst"])}
            if d.doc_kind in ("credit_note", "debit_note"):
                notes.append({"section": "CDNR" if gstin else "CDNUR", "buyer_gstin": gstin or "",
                              "buyer": (d.buyer or {}).get("name") or "", "number": d.number,
                              "date": d.issue_date.isoformat(), "type": "Credit" if d.doc_kind == "credit_note" else "Debit",
                              "place_of_supply": d.place_of_supply or "", "value": _f(dec(d.grand_total)), **base})
            elif gstin:
                b2b.append({"buyer_gstin": gstin, "buyer": (d.buyer or {}).get("name") or "", "number": d.number,
                            "date": d.issue_date.isoformat(), "value": _f(dec(d.grand_total)),
                            "place_of_supply": d.place_of_supply or "",
                            "reverse_charge": "Y" if d.reverse_charge else "N", **base})
            else:
                key = (d.place_of_supply or "", _rate(rate))
                agg = b2c.setdefault(key, defaultdict(lambda: ZERO))
                for k in ("taxable", "igst", "cgst", "sgst"):
                    agg[k] += g[k]
                if d.intra_state is False:
                    b2c_inter.append({"number": d.number, "date": d.issue_date.isoformat(),
                                      "value": _f(dec(d.grand_total)), "place_of_supply": d.place_of_supply or "",
                                      **base})
    b2c_rows = [{"place_of_supply": k[0], "rate": k[1], **{n: _f(v) for n, v in g.items()}}
                for k, g in sorted(b2c.items())]
    return {
        "sections": {
            "b2b": _table([("buyer_gstin", "Buyer GSTIN"), ("buyer", "Buyer"), ("number", "Invoice number"),
                           ("date", "Date"), ("value", "Invoice value"), ("place_of_supply", "Place of supply"),
                           ("reverse_charge", "Reverse charge"), ("rate", "Rate"), ("taxable", "Taxable value"),
                           ("igst", "IGST"), ("cgst", "CGST"), ("sgst", "SGST")], b2b),
            "b2c": _table([("place_of_supply", "Place of supply"), ("rate", "Rate"), ("taxable", "Taxable value"),
                           ("igst", "IGST"), ("cgst", "CGST"), ("sgst", "SGST")], b2c_rows,
                          note="Consumer sales grouped by place of supply and rate."),
            "b2c_inter_state": _table([("number", "Invoice number"), ("date", "Date"), ("value", "Invoice value"),
                                       ("place_of_supply", "Place of supply"), ("rate", "Rate"),
                                       ("taxable", "Taxable value"), ("igst", "IGST")], b2c_inter,
                                      note="Inter-state consumer invoices, listed so your CA can apply the "
                                           "large-invoice threshold. LOCAH does not apply it."),
            "notes": _table([("section", "Section"), ("buyer_gstin", "Buyer GSTIN"), ("buyer", "Buyer"),
                             ("number", "Note number"), ("date", "Date"), ("type", "Type"),
                             ("place_of_supply", "Place of supply"), ("value", "Note value"), ("rate", "Rate"),
                             ("taxable", "Taxable value"), ("igst", "IGST"), ("cgst", "CGST"), ("sgst", "SGST")], notes),
            "hsn": await hsn_summary(session, business_id, start, end),
            "documents": await documents_issued(session, business_id, start, end),
        },
        "note": "Grouped the way GSTR-1 is organised. Confirm the upload format with your CA before filing.",
    }


RUNNERS = {"sales_register": sales_register, "hsn_summary": hsn_summary, "tax_by_rate": tax_by_rate,
           "documents": documents_issued}


async def run(session: AsyncSession, business_id: uuid.UUID, kind: str, start: date, end: date) -> dict[str, Any]:
    if kind == "gstr1":
        return await gstr1(session, business_id, start, end)
    return await RUNNERS[kind](session, business_id, start, end)


def to_csv(table: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = table["columns"]
    w.writerow([c["label"] for c in cols])
    for row in table["rows"]:
        w.writerow([row.get(c["key"], "") for c in cols])
    if table.get("totals"):
        w.writerow(["Total"] + [table["totals"].get(c["key"], "") for c in cols[1:]])
    return buf.getvalue()


def gstr1_csv(data: dict[str, Any]) -> str:
    parts = []
    for name, table in data["sections"].items():
        parts.append(f"# {name}\n" + to_csv(table))
    return "\n".join(parts)
