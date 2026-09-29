# CURSOR-QUOTES-HANDOFF

Branch `parallel/cursor-quotes`. Started from `origin/main` (`1cb02e1`). Migration `20260930210000_quotes_finish.sql`.

The existing quotes kernel is finished in place. Revisions, share links, staff decisions, and `ProjectService.create_from_quote` are unchanged in role. This lane does not add an orders, projects, invoicing, payments, or documents engine.

## In place

- Website `purpose=quote_request` opens one draft when the quotes module is enabled, ready, or active. The lead is still created. Quotes off leaves the lead only.
- WhatsApp (and a staff replay) is `POST /v1/platform/businesses/{id}/quotes/intake`. The same `(business, channel, idempotency_key)` returns the same draft. Event `quote.rfq_received`.
- A new revision is still a new row with the same quote number. An accepted quote cannot be revised.
- Issue with no date and no `valid_days` is valid for 7 days.
- The customer page is still `GET/POST /v1/public/quotes/{token}`, proxied at `/q/{token}`. Each open of an issued version writes `quotes_views`, `open_count`, and `quote.viewed`.
- Accept needs the customer's name and a 6-digit code. The code is only on `quote.acceptance_code_issued` for messaging. Decline needs the name. Staff can still record an offline decision without a code. A lapsed quote is refused before those checks.
- Discount above the business limit (default 5%, owner-set on `quotes_settings`) stays a draft with `approval_status=pending` until someone with `quotes.approve` approves it. The owner has that permission. A sales executive can send a quote inside the limit.
- Accepting sets `price_locked_at`. A database trigger refuses later changes to the quote's money columns and to its lines, charges, and payment-plan rows.
- Lines carry quantity breaks, MOQ, lead time, BOQ section, and a size matrix. A size matrix's quantity is the sum of its sizes. A quantity under the MOQ is refused.
- Accept publishes `quote.payment_handoff` (`locah.quote.payment_handoff.v1`): token amount is the quote deposit, and plan percents are resolved against the locked total. No payment row is created.
- `POST .../quotes/{id}/conversion` with `order`, `project`, or `invoice` publishes `quote.conversion_requested` (`locah.quote.conversion.v1`) once. It stores `conversion_target` and does not set `converted_to_id` or insert an order, project, or invoice.
- Merchant quote pages edit those line facts and the payment plan, show opens, ask the owner to approve a discount, and hand the locked quote on. The existing "Create the project" action is still the old project path.

The follow-up integration commit grants `quotes.issue` on the sales executive template and on assignment roles. `quotes.approve` stays off assignment roles. `packages/permissions` exports `quotes.approve`. `main.py` and workspace nav were already wired and were not edited.

## For the other lanes

- Orders, Projects, Invoicing: consume `quote.conversion_requested`. The payload is the locked version (totals, lines, charges, payment plan, token). Do not read mutable draft rows.
- Payments: consume `quote.payment_handoff`. `token_amount` is what the customer is asked to pay on acceptance.
- WhatsApp: call the intake route with the inbound message id, and send `quote.acceptance_code_issued.code` to the customer. This lane does not send the message.

## Not in this lane

- Sales follow-up nudges (QT-09).
- Real-estate unit hold.
- A second payments, orders, projects, or documents implementation.

## Local proof

Database `postgresql://postgres@localhost:54329/locah_quotes` only.

`uv run --extra test pytest tests/test_quotes.py tests/test_quotes_finish.py tests/test_module_aware_site.py tests/test_assignment_scope.py` from `apps/api`: **48 passed**.

`node tools/acceptance/phase_b/p2_quotes.mjs` against API `8014`, workspace `3105`, web `3106`, database `locah_quotes`: **14/14 passed**. Website RFQ draft, price, revision, customer code and accept, locked total `42000.00`, conversion contract `locah.quote.conversion.v1`, and zero new order, project, and invoice rows.

READY_TO_INTEGRATE
