-- Stage 1D: Canonical identity model (Doc 12 §6.2)
-- Migrates platform_profiles -> platform_identities without data loss.

CREATE TABLE platform_identities (
    id UUID PRIMARY KEY,
    supabase_user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    phone_verified BOOLEAN NOT NULL DEFAULT false,
    email_verified BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE consumer_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id UUID NOT NULL UNIQUE REFERENCES platform_identities(id) ON DELETE CASCADE,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE platform_admin_grants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_id UUID NOT NULL REFERENCES platform_identities(id) ON DELETE CASCADE,
    granted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    granted_by UUID NOT NULL REFERENCES platform_identities(id),
    revoked_at TIMESTAMPTZ,
    reason TEXT NOT NULL,
    is_active BOOLEAN GENERATED ALWAYS AS (revoked_at IS NULL) STORED
);

-- Migrate existing Stage 1C profiles
INSERT INTO platform_identities (id, supabase_user_id, email, display_name, avatar_url, created_at, updated_at)
SELECT auth_user_id, auth_user_id, email, display_name, avatar_url, created_at, updated_at
FROM platform_profiles;

INSERT INTO consumer_profiles (identity_id, created_at, updated_at)
SELECT id, created_at, updated_at FROM platform_identities;

DROP TABLE platform_profiles;

ALTER TABLE platform_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE consumer_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_admin_grants ENABLE ROW LEVEL SECURITY;
