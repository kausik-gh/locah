# Cursor handoff — Kitchen, KOT, KDS

Branch: `parallel/cursor-kitchen` (from `origin/main`). Main was not updated.

This lane owns preparation. The sales order stays the commercial record. Kitchen does not write order status, does not decrement stock, and does not read or write recipe or BOM tables.

## What the pass is

An accepted or confirmed order that has something to cook becomes one kitchen ticket. The ticket number is `KOT-0001` for that business. It is not an order number.

A line is a preparation snapshot: title, quantity, station, and the choices and notes. Prices, phone numbers, and the customer name are not on the ticket and not on the board.

Stations are whatever the business turns on. The suggested keys are grill, fryer, beverages, bakery, and general. A business can name its own. Nothing is created for every restaurant. An item can go to more than one station; that is more than one line on the same ticket, not a second ticket.

An unrouted menu item lands on General, which is created the first time it is needed. An unrouted retail product does not. A delivery-fee line never does.

Flow on the pass: New, Preparing, Ready. Served leaves the board. The ticket then is completed.

## When the order changes

Before anyone starts the ticket, a still-new line follows the order. Nothing has been cooked.

After start, title, quantity, modifiers, and timestamps stay. The pass shows an event instead:

- A larger quantity arrives as its own new line (`line_added`).
- A smaller quantity is `quantity_changed`. The kitchen quantity stays.
- A choice change is `modifier_changed`. The snapshot stays.
- A cancel before start takes the ticket off the pass.
- A cancel after start leaves the ticket up with attention `cancel`. Started lines keep their facts. "Taken off" clears those lines without rewriting them.

Replaying the same order event does not open a second ticket. `kitchen_intakes` is keyed by the outbox event id, and `(business_id, order_id)` is unique.

## Cursor Supply — call this after the branches combine

Subscribe to `kitchen.preparation.completed`.

Kitchen publishes it once, when the ticket becomes completed (served). `consumption_published` stops a second publish. Kitchen does not emit `inventory.stock.updated` and does not call inventory.

Payload:

```json
{
  "business_id": "uuid",
  "location_id": "uuid",
  "order_id": "uuid",
  "ticket_id": "uuid",
  "ticket_number": "KOT-0001",
  "completed_at": "ISO-8601",
  "lines": [
    {
      "order_line_id": "uuid",
      "offering_id": "uuid",
      "variant_id": "uuid or null",
      "quantity": 1,
      "modifiers": { "choices": { "Spice": ["Mild"] }, "notes": { "Note": "no onion" } }
    }
  ]
}
```

`quantity` is what the kitchen cooked, including a line added after the order grew. Lines the kitchen was told to cancel are omitted. `modifiers` is the preparation snapshot, not a price.

Recipe and BOM consumption belongs on the subscriber. Decrement stock from that payload. Do not read `kitchen_ticket_lines` to decide the deduction.

Also published, with notifications skipped: `kitchen.ticket.created`, `kitchen.ticket.started`, `kitchen.ticket.ready`, `kitchen.ticket.cancelled` (`after_start` true or false).

Orders may later subscribe to `kitchen.ticket.ready` or `kitchen.preparation.completed` if fulfilment should move when the pass does. Kitchen must not transition the order.

## What this lane does not do

- No stock decrement and no recipe explosion.
- No write to order status, totals, or line prices.
- No printer fallback (KT-03). The pass is the screen: bump, elapsed time, rush.
- No QR order type. A table is `internal_reference` that says table. Pickup and delivery come from the fulfilment job's mode. The delivery label is city or area only.

## Routes

- `GET /v1/platform/businesses/{id}/kitchen/board?station_id=`
- `GET/POST /v1/platform/businesses/{id}/kitchen/stations`
- `PUT /v1/platform/businesses/{id}/kitchen/routes`
- `POST /v1/platform/businesses/{id}/kitchen/tickets/{ticket_id}/start|ready|serve|clear`
- `POST /v1/platform/businesses/{id}/kitchen/tickets/{ticket_id}/priority`

Permissions: `kitchen.read`, `kitchen.advance`, `kitchen.configure`. The Kitchen role sees the pass and does not get `orders.read`.

Screens: `/kds/{businessId}` is the full-screen pass. `/b/{businessId}/kitchen` is stations and routes.
