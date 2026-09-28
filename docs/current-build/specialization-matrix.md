# Source-derived specialization matrix

One shared domain per module; the *experience* is chosen from the business's
operating traits (Capability Universe §4.3), the inventory/booking/membership
hints its §21 playbook family names, and what it has actually configured —
never from the business's name alone. Each module gets its entry when it is
built or deepened; an entry records what changes, what never changes, and the
browser scenario that proves it.

Status of this document: entries exist for the modules deepened so far in
Phase B. Modules without an entry have not yet been given their specialised
experience and must not be claimed as specialised.

## inventory (P1-10A)

| | |
|---|---|
| Sources | MD §15.1 (capability table), §6.1 `inventory`, §21 rows naming `inventory (yield)`, `(batches, expiry)`, `(serials)`, `(lots)`, `(perishable)`, `(van stock)`, `(parts)`, `(client-owned stock)`; PDF §11 |
| Decided by | traits `weight_based`, `perishable`, `serialised`, `variant_based`, `ingredient_based`, `stock_tracked`; family hints via `family_key_for`; configured counts (weighed items, batch-tracked, serial-tracked, with variants, yields) — `platform_core/stock/profile.py`, fixture-tested |
| Offering kinds | `product`, `weighed_product`, `menu_item` (ingredients), variants on `product` |
| Roles | owner (all + value), manager (approve counts, value), store keeper (receive, wastage, blind counts, no value, no approval, own locations only), accountant (value), cashier (serial capture at the counter) |
| Shared, never changes | one `inventory_records` row per item × variant × location; every change an `inventory_movements` row under that row's lock; reservations by orders; weighted-average value; location-scope RLS |

| Lens | Who (source) | Terminology | Hierarchy / primary action | Workflow | Data shown | Empty state |
|---|---|---|---|---|---|---|
| Counter by weight | meat, chicken, fish, sweets, produce (`weight_based`; §21.1 `inventory (yield)`) | kg, cuts, trim, yield | kilos on the counter first; "Record today's arrival"; Cut and portion | cut whole → weigh each cut → live trim → cost carried into cuts; wastage reasons start with trim loss | kg per item, free vs held for orders, usual vs actual yield, recent cuts, 30-day trim % | "Add the items and cuts you actually sell by weight…" |
| Batches & expiry | pharmacy, cosmetics, grocery/kirana, packaged food (§21.1/21.2/21.4 `inventory (batches…)`, `perishable` non-weighed) | batch number, expiry, write off | expired / ≤7 days / ≤30 days first; "Receive a batch" | FEFO on every sale path; expiry ladder 30/7/0; write-off early or when expired; returns to the same batch | batches per item, next expiry, expired stock | "Receive stock with its batch number and expiry date…" |
| Serials & warranty | electronics, mobile stores, appliances (`serialised`; §21.2 `inventory (serials)`) | serial / IMEI, warranty | warranty lookup first; "Receive with serial numbers" | one serial per unit on receipt; captured at sale (counter scan adds the phone); returned serial back in stock | units by serial vs record, warranty months, sold/bill/customer on lookup | "Receive each unit with its serial or IMEI number…" |
| Sizes & colours | clothing, footwear, fashion (`variant_based`) | size, colour | size × colour grid per product | receive per combination | free quantity per cell; never-arrived combinations marked | "Give a product its sizes and colours…" |
| Ingredients | restaurants, bakeries (`ingredient_based`) | ingredients, arrivals | arrivals and wastage | receive, record wastage; recipe consumption stated as arriving with Recipes (P4) | ingredient stock | "Add the ingredients you buy…" |
| Reorder (always) | every stock-keeping business | reorder at, fill up to | to-reorder list first | min/max per line; suggested quantity; counts; requisition draft P4 | free now, reorder level, suggestion | "Record opening stock… LOCAH tells you what is running low." |

Proof: `apps/api/tests/test_stock_depth.py` (per-subcategory lens fixtures, meat cutting/value/trim, pharmacy FEFO + expiry ladder, electronics serials/warranty, blind count + approval + role limits, RLS isolation for every new table); browser `tools/acceptance/phase_b/p1_10a_stock.mjs` (meat, pharmacy, mobile store, clothing; desktop + 390 px) and `p1_10a_counter_serials.mjs` (IMEI at the counter). Not yet specialised: `lots`, `van stock`, `parts`, `client-owned stock`, `harvest lots` lenses (P2–P5 with transfers, jobs and warehousing).
