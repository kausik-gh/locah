"""How a supplier bill becomes money owed, without paying it here.

The shared ledger already has supplier accounts. A bill raises what the
business owes by a `purchase` entry. It becomes paid only when that same
ledger records `payment_made` for this bill. This module does not post either
entry and it does not change the bill's status.
"""

from __future__ import annotations

from typing import Any


def ledger_posting_intent(bill: dict[str, Any]) -> dict[str, Any]:
    return {
        "ledger": "shared",
        "party_type": "supplier",
        "supplier_id": str(bill["supplier_id"]) if bill.get("supplier_id") else None,
        "bill_id": str(bill["id"]),
        "kind": "purchase",
        "amount_paise": int(bill["amount_paise"]),
        "reference": bill["invoice_reference"],
        "settlement_kind": "payment_made",
        "status_until_settled": "open",
    }
