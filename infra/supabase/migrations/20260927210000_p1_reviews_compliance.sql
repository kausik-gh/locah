-- P1-09 Reviews and compliance (Capability Universe §17, §6.2 `compliance`, §25.1; §26.3 P1-09).
--
-- Reviews come only from real transactions: a completed order or booking
-- gets one invitation (its link is the credential, hash only), and one
-- review. The business replies, reports and features; it never deletes or
-- edits. Only a LOCAH moderator removes a review, for a listed violation with
-- a reason, and may only redact personal data. Those rules are enforced here as
-- well as in the service (RLS is defence in depth):
--   * no DELETE on any review table, for any role;
--   * rating and text change only on the reviewer's own path, text also on
--     the moderator's redaction path; status and appeals only on the
--     moderator's path — each path identifies itself for the transaction
--     with app.review_actor;
--   * the moderation log is append-only.
-- Photos (up to 3, ≤ 1.5 MB, JPEG/PNG/WebP) are kept with the review so they
-- are shown, hidden and redacted with it.
--
-- Compliance: licences and filings with their due dates, reminded on the
-- compliance.due ladder until renewed or filed; a licence number the owner
-- marks "show on website" appears on their own site (FSSAI, RERA,
-- accreditation). Dates are the owner's (or their CA's) — LOCAH does not
-- invent statutory due dates.

-- ---------------------------------------------------------------- reviews
CREATE TABLE reviews_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    source_type TEXT NOT NULL CHECK (source_type IN ('order', 'booking', 'membership', 'job')),
    source_id UUID NOT NULL,
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    label TEXT NOT NULL CHECK (char_length(label) <= 200),
    completed_at TIMESTAMPTZ NOT NULL,
    -- §17.1: 30 days after completion to write the review.
    expires_at TIMESTAMPTZ NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    declined_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, source_type, source_id)
);
CREATE INDEX reviews_invitations_contact ON reviews_invitations (business_id, customer_contact_id);

CREATE TABLE reviews_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    invitation_id UUID NOT NULL UNIQUE REFERENCES reviews_invitations(id),
    source_type TEXT NOT NULL,
    source_id UUID NOT NULL,
    customer_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    reviewer_name TEXT NOT NULL CHECK (char_length(reviewer_name) <= 60),
    rating SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    body TEXT CHECK (char_length(body) <= 2000),
    status TEXT NOT NULL DEFAULT 'published' CHECK (status IN ('published', 'removed')),
    featured BOOLEAN NOT NULL DEFAULT false,
    featured_at TIMESTAMPTZ,
    reply_body TEXT CHECK (char_length(reply_body) <= 1000),
    reply_at TIMESTAMPTZ,
    reply_by UUID,
    removed_reason TEXT CHECK (removed_reason IN ('fake', 'abuse', 'personal_data', 'off_topic',
                                                  'conflict_of_interest', 'illegal')),
    removed_note TEXT CHECK (char_length(removed_note) <= 500),
    removed_at TIMESTAMPTZ,
    removed_by UUID,
    appeal_status TEXT CHECK (appeal_status IN ('open', 'upheld', 'rejected')),
    appeal_note TEXT CHECK (char_length(appeal_note) <= 1000),
    appealed_at TIMESTAMPTZ,
    appeal_decided_at TIMESTAMPTZ,
    appeal_decided_by UUID,
    redacted_at TIMESTAMPTZ,
    reviewer_updated_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    UNIQUE (business_id, source_type, source_id),
    CHECK (status <> 'removed' OR (removed_reason IS NOT NULL AND removed_at IS NOT NULL))
);
CREATE INDEX reviews_reviews_listing ON reviews_reviews (business_id, status, published_at DESC);
CREATE INDEX reviews_reviews_low ON reviews_reviews (business_id, rating) WHERE status = 'published' AND rating <= 2;

CREATE TABLE reviews_photos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    review_id UUID NOT NULL REFERENCES reviews_reviews(id),
    media_type TEXT NOT NULL CHECK (media_type IN ('image/jpeg', 'image/png', 'image/webp')),
    size_bytes INTEGER NOT NULL CHECK (size_bytes BETWEEN 1 AND 1500000),
    sha256 TEXT NOT NULL,
    content BYTEA NOT NULL,
    sort_order SMALLINT NOT NULL DEFAULT 0,
    removed_at TIMESTAMPTZ,
    removed_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX reviews_photos_review ON reviews_photos (review_id);

CREATE TABLE reviews_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    review_id UUID NOT NULL REFERENCES reviews_reviews(id),
    reason TEXT NOT NULL CHECK (reason IN ('fake', 'abuse', 'personal_data', 'off_topic',
                                           'conflict_of_interest', 'illegal')),
    note TEXT CHECK (char_length(note) <= 500),
    reported_by UUID NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'upheld', 'dismissed')),
    decided_by UUID,
    decided_at TIMESTAMPTZ,
    decision_note TEXT CHECK (char_length(decision_note) <= 500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX reviews_reports_one_open ON reviews_reports (review_id) WHERE status = 'open';
CREATE INDEX reviews_reports_queue ON reviews_reports (status, created_at);

CREATE TABLE reviews_moderation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    review_id UUID NOT NULL REFERENCES reviews_reviews(id),
    action TEXT NOT NULL CHECK (action IN ('report_dismissed', 'removed', 'redacted', 'photo_removed',
                                           'appeal_opened', 'appeal_upheld', 'appeal_rejected')),
    reason TEXT,
    note TEXT,
    actor_identity_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX reviews_moderation_log_review ON reviews_moderation_log (review_id, created_at);

-- Nothing about a review is ever deleted.
CREATE OR REPLACE FUNCTION reviews_never_deleted() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'reviews are never deleted; a LOCAH moderator removes a review from display'
        USING ERRCODE = 'insufficient_privilege';
END
$$;
CREATE TRIGGER reviews_reviews_no_delete BEFORE DELETE ON reviews_reviews
    FOR EACH ROW EXECUTE FUNCTION reviews_never_deleted();
CREATE TRIGGER reviews_photos_no_delete BEFORE DELETE ON reviews_photos
    FOR EACH ROW EXECUTE FUNCTION reviews_never_deleted();
CREATE TRIGGER reviews_invitations_no_delete BEFORE DELETE ON reviews_invitations
    FOR EACH ROW EXECUTE FUNCTION reviews_never_deleted();
CREATE TRIGGER reviews_reports_no_delete BEFORE DELETE ON reviews_reports
    FOR EACH ROW EXECUTE FUNCTION reviews_never_deleted();

CREATE OR REPLACE FUNCTION reviews_moderation_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'the moderation log is append-only' USING ERRCODE = 'insufficient_privilege';
END
$$;
CREATE TRIGGER reviews_moderation_log_immutable BEFORE UPDATE OR DELETE ON reviews_moderation_log
    FOR EACH ROW EXECUTE FUNCTION reviews_moderation_log_append_only();

-- Who may change what (§17.2): the business may reply and feature; only the
-- reviewer changes the rating and text; only a moderator removes, restores,
-- decides an appeal or redacts. Where a review came from never changes.
CREATE OR REPLACE FUNCTION reviews_reviews_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    who TEXT := COALESCE(NULLIF(current_setting('app.review_actor', true), ''), 'business');
BEGIN
    IF NEW.business_id IS DISTINCT FROM OLD.business_id OR NEW.invitation_id IS DISTINCT FROM OLD.invitation_id
       OR NEW.source_type IS DISTINCT FROM OLD.source_type OR NEW.source_id IS DISTINCT FROM OLD.source_id
       OR NEW.customer_contact_id IS DISTINCT FROM OLD.customer_contact_id
       OR NEW.published_at IS DISTINCT FROM OLD.published_at OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'where a review came from never changes' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.rating IS DISTINCT FROM OLD.rating AND who <> 'reviewer' THEN
        RAISE EXCEPTION 'only the reviewer changes a rating' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.body IS DISTINCT FROM OLD.body AND who NOT IN ('reviewer', 'moderator') THEN
        RAISE EXCEPTION 'review text is never edited by the business' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.reviewer_name IS DISTINCT FROM OLD.reviewer_name AND who NOT IN ('reviewer', 'moderator') THEN
        RAISE EXCEPTION 'the reviewer''s name is never edited by the business' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF (NEW.status IS DISTINCT FROM OLD.status OR NEW.removed_reason IS DISTINCT FROM OLD.removed_reason
        OR NEW.removed_at IS DISTINCT FROM OLD.removed_at OR NEW.redacted_at IS DISTINCT FROM OLD.redacted_at
        OR NEW.appeal_decided_at IS DISTINCT FROM OLD.appeal_decided_at
        OR (NEW.appeal_status IS DISTINCT FROM OLD.appeal_status AND NEW.appeal_status <> 'open'))
       AND who <> 'moderator' THEN
        RAISE EXCEPTION 'only a LOCAH moderator removes or restores a review' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.appeal_status IS DISTINCT FROM OLD.appeal_status AND NEW.appeal_status = 'open' AND who <> 'reviewer' THEN
        RAISE EXCEPTION 'only the reviewer appeals' USING ERRCODE = 'insufficient_privilege';
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END
$$;
CREATE TRIGGER reviews_reviews_guard BEFORE UPDATE ON reviews_reviews
    FOR EACH ROW EXECUTE FUNCTION reviews_reviews_guard();

CREATE OR REPLACE FUNCTION reviews_photos_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.content IS DISTINCT FROM OLD.content OR NEW.review_id IS DISTINCT FROM OLD.review_id
       OR NEW.business_id IS DISTINCT FROM OLD.business_id THEN
        RAISE EXCEPTION 'a review photo never changes' USING ERRCODE = 'insufficient_privilege';
    END IF;
    IF NEW.removed_at IS DISTINCT FROM OLD.removed_at
       AND COALESCE(NULLIF(current_setting('app.review_actor', true), ''), 'business') NOT IN ('moderator', 'reviewer') THEN
        RAISE EXCEPTION 'only the reviewer or a LOCAH moderator removes a photo' USING ERRCODE = 'insufficient_privilege';
    END IF;
    RETURN NEW;
END
$$;
CREATE TRIGGER reviews_photos_guard BEFORE UPDATE ON reviews_photos
    FOR EACH ROW EXECUTE FUNCTION reviews_photos_guard();

-- ---------------------------------------------------------------- compliance
CREATE TABLE compliance_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID REFERENCES business_locations(id),
    item_type TEXT NOT NULL CHECK (item_type IN ('licence', 'filing')),
    kind TEXT NOT NULL CHECK (kind IN ('fssai', 'trade_licence', 'shop_establishment', 'drug_licence', 'fire_noc',
                                       'bar_licence', 'pollution', 'gst_registration', 'gst_filing', 'income_tax',
                                       'tds', 'professional_tax', 'rera', 'accreditation', 'other')),
    title TEXT NOT NULL CHECK (char_length(title) BETWEEN 1 AND 120),
    licence_number TEXT CHECK (char_length(licence_number) <= 60),
    authority TEXT CHECK (char_length(authority) <= 120),
    issued_on DATE,
    -- A licence's expiry date, or a filing's next due date.
    due_on DATE NOT NULL,
    recurrence TEXT NOT NULL DEFAULT 'none' CHECK (recurrence IN ('none', 'monthly', 'quarterly', 'yearly')),
    document_url TEXT CHECK (document_url ~ '^https://' AND char_length(document_url) <= 500),
    show_on_site BOOLEAN NOT NULL DEFAULT false,
    notes TEXT CHECK (char_length(notes) <= 1000),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived')),
    last_done_on DATE,
    created_by UUID,
    updated_by UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1,
    CHECK (show_on_site = false OR licence_number IS NOT NULL)
);
CREATE INDEX compliance_items_due ON compliance_items (business_id, status, due_on);

CREATE TABLE compliance_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    item_id UUID NOT NULL REFERENCES compliance_items(id),
    action TEXT NOT NULL CHECK (action IN ('created', 'updated', 'renewed', 'filed', 'archived', 'restored')),
    from_due DATE,
    to_due DATE,
    note TEXT CHECK (char_length(note) <= 500),
    actor_identity_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX compliance_history_item ON compliance_history (item_id, created_at);
CREATE TRIGGER compliance_history_immutable BEFORE UPDATE OR DELETE ON compliance_history
    FOR EACH ROW EXECUTE FUNCTION reviews_moderation_log_append_only();

-- The Marketplace card shows the verified average (§17.2), from the projection.
ALTER TABLE marketplace_business_projections
    ADD COLUMN rating_average NUMERIC(3, 2),
    ADD COLUMN rating_count INTEGER NOT NULL DEFAULT 0;

-- ---------------------------------------------------------------- RLS
DO $$
DECLARE t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY['reviews_invitations', 'reviews_reviews', 'reviews_photos', 'reviews_reports',
                             'reviews_moderation_log', 'compliance_items', 'compliance_history'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR SELECT TO public USING (business_id = current_business_id())',
                       t || '_member_read', t);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) '
                       'WITH CHECK (business_id = current_business_id())', t || '_api_write', t);
        -- No DELETE for the API role on anything here (§17.5).
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I TO platform_api', t);
        EXECUTE format('REVOKE DELETE ON %I FROM platform_api', t);
        EXECUTE format('REVOKE ALL PRIVILEGES ON TABLE %I FROM anon', t);
    END LOOP;
END
$$;

-- The review link is the reviewer's credential (hash only), like bills and
-- khata statements: it opens that one invitation and the review written from it.
CREATE POLICY reviews_invitations_token_read ON reviews_invitations FOR SELECT TO platform_api
    USING (token_hash = (SELECT NULLIF(current_setting('app.current_review_token', true), '')));
CREATE POLICY reviews_invitations_token_write ON reviews_invitations FOR UPDATE TO platform_api
    USING (token_hash = (SELECT NULLIF(current_setting('app.current_review_token', true), '')))
    WITH CHECK (token_hash = (SELECT NULLIF(current_setting('app.current_review_token', true), '')));
CREATE POLICY reviews_reviews_token_rw ON reviews_reviews FOR ALL TO platform_api
    USING (EXISTS (SELECT 1 FROM reviews_invitations i WHERE i.id = invitation_id
                   AND i.token_hash = (SELECT NULLIF(current_setting('app.current_review_token', true), ''))))
    WITH CHECK (EXISTS (SELECT 1 FROM reviews_invitations i WHERE i.id = invitation_id
                        AND i.token_hash = (SELECT NULLIF(current_setting('app.current_review_token', true), ''))));
CREATE POLICY reviews_photos_token_rw ON reviews_photos FOR ALL TO platform_api
    USING (EXISTS (SELECT 1 FROM reviews_reviews r JOIN reviews_invitations i ON i.id = r.invitation_id
                   WHERE r.id = review_id
                     AND i.token_hash = (SELECT NULLIF(current_setting('app.current_review_token', true), ''))))
    WITH CHECK (EXISTS (SELECT 1 FROM reviews_reviews r JOIN reviews_invitations i ON i.id = r.invitation_id
                        WHERE r.id = review_id
                          AND i.token_hash = (SELECT NULLIF(current_setting('app.current_review_token', true), ''))));
CREATE POLICY reviews_moderation_log_token_insert ON reviews_moderation_log FOR INSERT TO platform_api
    WITH CHECK (EXISTS (SELECT 1 FROM reviews_reviews r JOIN reviews_invitations i ON i.id = r.invitation_id
                        WHERE r.id = review_id
                          AND i.token_hash = (SELECT NULLIF(current_setting('app.current_review_token', true), ''))));

-- ---------------------------------------------------------------- WhatsApp template categories
-- Meta decides a template's category when it approves it (§17.1: the review
-- request's category is "decided by Meta at approval"). The category Meta
-- returns is kept per business and language and is what LOCAH sends under —
-- a template Meta calls marketing then needs the customer's marketing opt-in.
ALTER TABLE messaging_templates ADD COLUMN category TEXT
    CHECK (category IN ('utility', 'marketing', 'authentication'));

-- Template status and category updates arrive per WhatsApp Business Account,
-- not per phone number; the account id is their credential, like the number's.
CREATE POLICY messaging_channels_webhook_waba_read ON messaging_channels FOR SELECT TO platform_api
    USING (status = 'connected'
           AND waba_id = (SELECT NULLIF(current_setting('app.current_waba_id', true), '')));
