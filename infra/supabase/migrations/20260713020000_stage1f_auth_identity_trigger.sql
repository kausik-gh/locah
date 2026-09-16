-- Stage 1F: Auth user -> platform identity trigger

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;

CREATE OR REPLACE FUNCTION public.handle_new_auth_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    INSERT INTO platform_identities (id, supabase_user_id, email, display_name, email_verified)
    VALUES (
        NEW.id,
        NEW.id,
        COALESCE(NEW.email, NEW.id::text || '@local.invalid'),
        COALESCE(NEW.raw_user_meta_data->>'display_name', split_part(COALESCE(NEW.email, 'user'), '@', 1)),
        NEW.email_confirmed_at IS NOT NULL
    )
    ON CONFLICT (supabase_user_id) DO NOTHING;

    INSERT INTO consumer_profiles (identity_id)
    SELECT NEW.id
    WHERE NOT EXISTS (SELECT 1 FROM consumer_profiles WHERE identity_id = NEW.id);

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_auth_user();
