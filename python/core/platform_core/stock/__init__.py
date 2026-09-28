"""Stock depth (Capability Universe §15.1; Business OS Guide §11) — P1-10A.

One stock truth: every change is an `inventory_movements` row against one
`inventory_records` row, whichever surface caused it (counter, website,
WhatsApp, a Workspace bill, a count, a cutting run). This package keeps the
detail behind that one number honest — the value on hand, the batches and
their expiry, the serial numbers — and decides how a business *sees* its
stock (`profile`), from its traits, its playbook and what it has configured.
"""
