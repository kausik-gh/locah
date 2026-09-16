-- Stage 2D: Business invitation lifecycle (core-team-access)

CREATE TABLE business_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    invited_email TEXT NOT NULL,
    invited_identity_id UUID REFERENCES platform_identities(id),
    invited_role TEXT NOT NULL CHECK (invited_role IN ('manager', 'member')),
    location_scope UUID[],
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'accepted', 'declined', 'revoked', 'expired')),
    expires_at TIMESTAMPTZ NOT NULL,
    invited_by UUID NOT NULL REFERENCES platform_identities(id),
    accepted_at TIMESTAMPTZ,
    declined_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ,
    membership_id UUID REFERENCES business_memberships(id),
    last_resent_at TIMESTAMPTZ,
    resend_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX idx_business_invitations_business_id ON business_invitations(business_id);
CREATE INDEX idx_business_invitations_invited_email ON business_invitations(lower(invited_email));
CREATE INDEX idx_business_invitations_pending_expires
    ON business_invitations(expires_at)
    WHERE status = 'pending';

-- One pending invitation per business + email (case-insensitive).
CREATE UNIQUE INDEX idx_business_invitations_pending_unique
    ON business_invitations(business_id, lower(invited_email))
    WHERE status = 'pending';

CREATE TRIGGER business_invitations_set_updated_at
    BEFORE UPDATE ON business_invitations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
