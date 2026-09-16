-- Stage 1C Identity Foundation
-- Creates the canonical platform profile model representing one authenticated human.

CREATE TABLE platform_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enable RLS
ALTER TABLE platform_profiles ENABLE ROW LEVEL SECURITY;

-- API service accesses the DB using service role, bypassing RLS.
-- Therefore, we don't need any RLS policies for now.
