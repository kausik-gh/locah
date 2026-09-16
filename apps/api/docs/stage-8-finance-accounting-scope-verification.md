# Stage 8 — Finance & Accounting Kernel

## Scope Verification Decision

**STOP — Do not implement Stage 8 as specified.**

Finance & Accounting (invoicing suite, ledger foundation, credit notes, full receivables lifecycle) is **explicitly deferred** from First Launch. The canonical First Launch financial module is **`payments`**, not a Finance & Accounting kernel.

No migration, services, APIs, or tests were created for Stage 8.

---

# Stage 8 Engineering Report (Scope Verification Only)

## 1. Executive Summary

After reading Documents 11 and 12, **Stage 8 — Finance & Accounting Kernel is outside First Launch scope** and must not be implemented now. Document 11 classifies **`invoicing`** as **“C — Later Release”**, defers **full accounting suite depth**, and limits First Launch financial proof to the separate **`payments`** module (Full/Launch-Ready). Document 12 defines `payments_payment_attempts` as the payments-module table — not finance/ledger/accounting tables.

Implementing Invoice, Credit Note, Ledger foundation, or accounting workflows in Stage 8 would violate Doc 11 §3.2, §608, §9.4, and §11.1.

## 2. Implemented Components

**None.** Scope gate failed; no code shipped.

## 3. Database Changes

**None.**

## 4. Domain Models

**None.**

## 5. Services

**None.**

## 6. APIs

**None.**

## 7. Authorization Integration

N/A — no implementation. Existing `payments.*` permissions (Doc 12) belong to the future **Payments** stage/module, not Finance & Accounting.

## 8. Audit Integration

N/A.

## 9. Outbox Integration

N/A. Canonical invoice events (`invoice.created`, `credit_note.created`, etc.) in Document 04 belong to the deferred **`invoicing`** module, not First Launch.

## 10. Resolver Design

N/A.

## 11. Validation Rules

N/A.

## 12. Performance

N/A.

## 13. Testing Summary

**None.**

## 14. Files Created

| Path | Purpose |
|------|---------|
| `apps/api/docs/stage-8-finance-accounting-scope-verification.md` | Scope verification report only |

## 15. Files Modified

**None.**

## 16. Architectural Compliance

| Decision | Justification |
|----------|---------------|
| Do not implement Finance & Accounting kernel | Doc 11 §608, §267, §286, §9.4 |
| Do not conflate with Payments module | Doc 11 §607, §9.4 — separate Full/Launch-Ready module |
| Orders keep payment_status placeholders only | Doc 11 §9.4 — payment linkage via `payments`, not order-embedded accounting |
| No ledger/invoicing tables in platform core | Doc 12 §569–575 lists `payments_*`, not finance/ledger tables |

## 17. Implementation Decisions

1. **Stage 8 prompt entities map to deferred `invoicing`, not First Launch.** Invoice, Credit Note, receivables, and accounting policy are Doc 11 §11.1 Later depth.
2. **First Launch financial minimum is `payments`.** Payment attempts, refunds, reconciliation, and receipt visibility — Doc 11 §9.4, Doc 12 `payments_payment_attempts`.
3. **Stage numbering correction:** The next financial implementation stage should be **Payments Kernel** (`payments`), not Finance & Accounting.

## 18. Future Dependencies

| Module | When | Doc reference |
|--------|------|---------------|
| **Payments** (`payments`) | Next eligible financial stage for First Launch | Doc 11 §607, §9.4; Doc 12 §570 |
| **Invoicing** (`invoicing`) | Later Release | Doc 11 §608, §11.1 |
| **Payroll** (`payroll`) | Future Ecosystem | Doc 11 §613, §11.2 |
| **AI Finance Assistant** | Future (H3) | Doc 04 — depends on invoicing + payments |

## 19. Risks

| Risk if Stage 8 were built now | Mitigation |
|--------------------------------|------------|
| Duplicate/conflicting financial model vs upcoming `payments` module | Defer; implement `payments` per Doc 11 §9.4 |
| Premature invoice/receivables complexity | Doc 11 §608 — not required for launch proof |
| Orders contaminated with accounting logic | User guard + Doc 11 §9.2/§9.4 separation |

## 20. Verification Checklist

- [x] Documents 11 and 12 reviewed for First Launch financial scope
- [x] Confirmed `invoicing` = Later Release
- [x] Confirmed full accounting = explicitly deferred
- [x] Confirmed `payments` = Full/Launch-Ready (separate stage)
- [x] No Stage 8 code written

## 21. Integration Matrix

| Engine | Stage 8 status |
|--------|----------------|
| Orders (Stage 6) | Keeps lightweight `payment_method` / `payment_status` fields; no accounting logic added |
| Bookings (Stage 7) | Same — payment linkage deferred to `payments` module |
| Customer (Stage 4) | No finance kernel to integrate yet |
| Audit / Outbox | Unchanged |

---

## 22. Scope Verification (Primary Deliverable)

### Decision

**Finance & Accounting Kernel — DEFERRED. Do not implement.**

### What the user prompt asked for vs canonical platform

| Stage 8 prompt entity | Canonical home | First Launch? |
|----------------------|----------------|---------------|
| Invoice | `invoicing` module | **No** — Later Release |
| Credit Note | `invoicing` module | **No** |
| Payment Record / Allocation | `payments` module | **Yes** — but separate module, not “Finance & Accounting” |
| Refund Record | `payments` module | **Yes** — via payments refunds (Doc 11 §9.4) |
| Ledger foundation | Not defined for First Launch | **No** — Doc 11 §9.4 excludes “accounting-ledger depth” |
| Financial Status (ERP-style) | N/A | **No** |

There is **no canonical module** named “Finance & Accounting” in Documents 08, 11, or 12. Financial concerns split into **`payments`** (First Launch Full), **`invoicing`** (Later), and **`payroll`** (Future).

### Document 11 — direct quotes

**§3.2 Explicitly Deferred:**
> “full `invoicing`; … complete PMS, ERP, LMS, HIMS, **accounting**, or payroll depth;”

**§3.3 Deferred Does Not Mean Absent:**

| Deferred full module | Required First Launch function that remains |
|---|---|
| `invoicing` | **Payment receipts and transaction records where required; not a full invoice lifecycle** |

**§608 Module roster:**

> | 8 | Payments | `payments` | **A — Full/Launch-Ready** | Required for real online/deposit/refund flows … |
> | 9 | Invoicing | `invoicing` | **C — Later Release** | **Full receivables/invoice lifecycle is not required for launch proof** |

**§9.4 Payments — Explicitly not included:**
> “accounting-ledger or invoicing-suite depth.”

**§11.1 Later Release — Invoicing:**

> “Full invoice/receivable lifecycle adds tax, numbering, and accounting policy” — deferred; First Launch keeps “Payment receipts and transaction records.”

**§1342 (repair/home services):**
> “Post-service online payment links or invoices are **Later with `invoicing`**; First Launch must not imply that deferred flow.”

### Document 12 — direct quotes

**§569 Module table naming:**
> `payments_payment_attempts <- Module: payments`

No `finance_*`, `accounting_*`, `invoicing_*`, or `ledger_*` tables appear in the First Launch platform table inventory.

**§951–952 Permissions:**
> `# Module: payments` — `payments.read`, `payments.refund`, …

Permissions exist for **payments**, not for a finance/accounting kernel.

### What should be built instead (not Stage 8)

When the platform is ready for the next financial stage, implement:

**Stage N — Payments Kernel (`payments`)** per Doc 11 §9.4:
- Payment attempts and status lifecycle
- Refunds and canonical refund state
- Merchant connection/onboarding state
- Linkage to Orders, Bookings, Memberships via public contracts
- Provider abstraction and durable webhooks
- **Without** accounting-ledger or invoicing-suite depth

**Later — Invoicing Kernel (`invoicing`)** per Doc 11 §11.1:
- Invoice creation, numbering, templates, receivables
- Credit notes
- Full invoice lifecycle (post-launch)

### Conclusion

Stage 8 as “Finance & Accounting Kernel” **does not belong in First Launch**. Implementation was **correctly stopped** at scope verification. Proceed with **Payments** when scheduling the next financial stage.
