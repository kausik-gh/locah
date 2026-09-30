-- P1-10D2: dated pre-orders (MD §6.1 "pre-orders with a date", §21.1 bakeries
-- and home kitchens; Founder refinement — Orders & Customer Transactions,
-- "Pre-orders / scheduled orders").
--
-- An offering may carry pre-order rules (needs a date or may take one, notice,
-- next-day cutoff, ready times, festival window, daily limit, advance, cancel
-- window). An order keeps the date and time it is wanted for, the advance its
-- items asked for, and a snapshot of the terms the customer confirmed, so a
-- later change to the rules never rewrites an order already taken. There is
-- still one order table for every channel.

ALTER TABLE offerings_catalog_offerings
    ADD COLUMN IF NOT EXISTS preorder JSONB;
-- "No rules" is SQL NULL, never a JSON null.
UPDATE offerings_catalog_offerings SET preorder = NULL WHERE preorder = 'null'::jsonb;

ALTER TABLE orders_orders
    ADD COLUMN IF NOT EXISTS due_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS preorder BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS advance_amount NUMERIC(12, 2) CHECK (advance_amount IS NULL OR advance_amount >= 0),
    ADD COLUMN IF NOT EXISTS preorder_terms JSONB NOT NULL DEFAULT '{}'::jsonb;

-- The pre-order board and the production list read orders by the day they are wanted.
CREATE INDEX IF NOT EXISTS orders_orders_business_due_idx
    ON orders_orders (business_id, due_at)
    WHERE due_at IS NOT NULL AND deleted_at IS NULL;

-- A cancelled order that had money taken on it shows "refund due" in Payments
-- until the owner refunds it (Founder: Orders — cancellation handles the refund
-- through Payments).
ALTER TABLE payments_payment_attempts DROP CONSTRAINT IF EXISTS payments_payment_attempts_attention_check;
ALTER TABLE payments_payment_attempts ADD CONSTRAINT payments_payment_attempts_attention_check
    CHECK (attention IS NULL OR attention IN ('paid_twice', 'not_received', 'refund_due'));
