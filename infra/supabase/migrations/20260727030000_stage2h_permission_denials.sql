-- Stage 2H: membership permission denials for override layer
CREATE TABLE business_membership_permission_denials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    membership_id UUID NOT NULL REFERENCES business_memberships(id),
    permission TEXT NOT NULL,
    denied_by UUID NOT NULL REFERENCES platform_identities(id),
    denied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (membership_id, permission)
);

CREATE INDEX idx_membership_permission_denials_membership
    ON business_membership_permission_denials(membership_id);

ALTER TABLE business_membership_permission_denials ENABLE ROW LEVEL SECURITY;
