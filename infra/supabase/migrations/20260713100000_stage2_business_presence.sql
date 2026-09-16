-- Stage 2: Business Presence
-- Scope: Business Profile, Offerings foundation, structured Website model,
--         media foundation, AI generation jobs, website section types
-- Authority: Doc 11 §17.2, Doc 12 §11–12

-- ============================================================
-- MEDIA FOUNDATION (svc-media)
-- ============================================================
CREATE TABLE media_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID REFERENCES businesses(id),   -- NULL = platform asset
    uploader_identity_id UUID REFERENCES platform_identities(id),
    original_filename TEXT,
    mime_type TEXT NOT NULL,
    size_bytes BIGINT,
    storage_key TEXT NOT NULL,       -- provider-internal key
    public_url TEXT,                 -- pre-signed or CDN URL (may be null until processed)
    alt_text TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'ready', 'failed', 'deleted')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_media_assets_business ON media_assets(business_id) WHERE business_id IS NOT NULL;
CREATE INDEX idx_media_assets_status ON media_assets(status);

-- ============================================================
-- BUSINESS PROFILE (core-business-profile)
-- ============================================================
CREATE TABLE business_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID UNIQUE NOT NULL REFERENCES businesses(id),
    description TEXT,
    tagline TEXT,
    logo_asset_id UUID REFERENCES media_assets(id),
    cover_asset_id UUID REFERENCES media_assets(id),
    -- Contact details (structured, not raw HTML)
    contact JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Additional public profile fields
    website_url TEXT,    -- external website link if provided (optional, not the platform website)
    social_links JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Completeness signals for onboarding gate
    completeness_score INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_business_profiles_business ON business_profiles(business_id);

-- ============================================================
-- WEBSITE SECTION TYPES (static registry)
-- Core section types for Stage 2 structured Website
-- ============================================================
CREATE TABLE website_section_types (
    id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT,
    content_schema JSONB NOT NULL,    -- JSON Schema for content JSONB field
    allowed_variants TEXT[] NOT NULL DEFAULT '{}',
    contributing_module TEXT,         -- module that provides this section (NULL = core)
    requires_module TEXT,             -- module that must be active to use this section
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- WEBSITES (core-website)
-- One website record per business
-- ============================================================
CREATE TABLE websites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID UNIQUE NOT NULL REFERENCES businesses(id),
    published_version_id UUID,  -- FK added below after website_versions is created
    custom_domain TEXT,
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'published', 'unpublished')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_websites_business ON websites(business_id);

-- ============================================================
-- WEBSITE VERSIONS
-- Draft and published snapshots (Doc 12 §11.1)
-- ============================================================
CREATE TABLE website_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_id UUID NOT NULL REFERENCES websites(id),
    business_id UUID NOT NULL REFERENCES businesses(id),
    version_type TEXT NOT NULL CHECK (version_type IN ('draft', 'published')),
    navigation JSONB NOT NULL DEFAULT '[]'::jsonb,
    theme JSONB NOT NULL DEFAULT '{}'::jsonb,
    generated_by TEXT,       -- 'ai_generation' | 'deterministic_fallback' | 'manual' | null
    generation_job_id UUID,  -- FK to website_generation_jobs (added later)
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_website_versions_website ON website_versions(website_id);
CREATE INDEX idx_website_versions_business ON website_versions(business_id);

-- Add FK from websites to website_versions now that versions table exists
ALTER TABLE websites ADD CONSTRAINT fk_websites_published_version
    FOREIGN KEY (published_version_id) REFERENCES website_versions(id);

-- ============================================================
-- WEBSITE PAGES (Doc 12 §11.1)
-- ============================================================
CREATE TABLE website_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    website_version_id UUID NOT NULL REFERENCES website_versions(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES businesses(id),
    slug TEXT NOT NULL,
    title TEXT NOT NULL,
    page_type TEXT NOT NULL CHECK (page_type IN (
        'home', 'about', 'contact', 'locations', 'offerings',
        'services', 'menu', 'rooms', 'plans', 'classes', 'enquire',
        'custom'
    )),
    seo_title TEXT,
    seo_description TEXT,
    og_image_asset_id UUID REFERENCES media_assets(id),
    is_published BOOLEAN NOT NULL DEFAULT true,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (website_version_id, slug)
);

CREATE INDEX idx_website_pages_version ON website_pages(website_version_id);
CREATE INDEX idx_website_pages_business ON website_pages(business_id);

-- ============================================================
-- WEBSITE SECTIONS (Doc 12 §11.1)
-- Safe structured content only — no arbitrary code
-- ============================================================
CREATE TABLE website_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    page_id UUID NOT NULL REFERENCES website_pages(id) ON DELETE CASCADE,
    business_id UUID NOT NULL REFERENCES businesses(id),
    section_type_id TEXT NOT NULL REFERENCES website_section_types(id),
    layout_variant TEXT,
    -- Content is structured JSONB validated against SectionType.content_schema
    -- No raw HTML, no script tags, no external URLs as permanent values
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- Optional module binding (resolved at render time via public contract)
    module_binding JSONB,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_visible BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_website_sections_page ON website_sections(page_id);
CREATE INDEX idx_website_sections_business ON website_sections(business_id);

-- ============================================================
-- WEBSITE GENERATION JOBS (Doc 12 §12.4)
-- ============================================================
CREATE TABLE website_generation_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'fallback_used')),
    ai_provider TEXT,
    model_name TEXT,
    prompt_version TEXT NOT NULL DEFAULT 'v1',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    error_detail TEXT,
    fallback_reason TEXT,
    result_version_id UUID REFERENCES website_versions(id),
    triggered_by UUID NOT NULL REFERENCES platform_identities(id),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_website_gen_jobs_business ON website_generation_jobs(business_id);
CREATE INDEX idx_website_gen_jobs_status ON website_generation_jobs(status)
    WHERE status IN ('pending', 'running');

-- Add FK from website_versions to generation jobs
ALTER TABLE website_versions ADD CONSTRAINT fk_website_versions_gen_job
    FOREIGN KEY (generation_job_id) REFERENCES website_generation_jobs(id);

-- ============================================================
-- UPDATED_AT TRIGGERS
-- ============================================================
CREATE TRIGGER trg_media_assets_updated_at BEFORE UPDATE ON media_assets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_business_profiles_updated_at BEFORE UPDATE ON business_profiles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_websites_updated_at BEFORE UPDATE ON websites
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_website_versions_updated_at BEFORE UPDATE ON website_versions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_website_pages_updated_at BEFORE UPDATE ON website_pages
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
CREATE TRIGGER trg_website_sections_updated_at BEFORE UPDATE ON website_sections
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE media_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE website_section_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE websites ENABLE ROW LEVEL SECURITY;
ALTER TABLE website_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE website_pages ENABLE ROW LEVEL SECURITY;
ALTER TABLE website_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE website_generation_jobs ENABLE ROW LEVEL SECURITY;

-- Business-scoped: only members of the current business can read
CREATE POLICY business_profiles_member_read ON business_profiles
    FOR SELECT USING (business_id = current_business_id());

CREATE POLICY business_profiles_member_write ON business_profiles
    FOR ALL USING (business_id = current_business_id());

CREATE POLICY websites_member_read ON websites
    FOR SELECT USING (business_id = current_business_id());

CREATE POLICY websites_member_write ON websites
    FOR ALL USING (business_id = current_business_id());

CREATE POLICY website_versions_member_read ON website_versions
    FOR SELECT USING (business_id = current_business_id());

CREATE POLICY website_versions_member_write ON website_versions
    FOR ALL USING (business_id = current_business_id());

CREATE POLICY website_pages_member_read ON website_pages
    FOR SELECT USING (business_id = current_business_id());

CREATE POLICY website_pages_member_write ON website_pages
    FOR ALL USING (business_id = current_business_id());

CREATE POLICY website_sections_member_read ON website_sections
    FOR SELECT USING (business_id = current_business_id());

CREATE POLICY website_sections_member_write ON website_sections
    FOR ALL USING (business_id = current_business_id());

CREATE POLICY website_gen_jobs_member_read ON website_generation_jobs
    FOR SELECT USING (business_id = current_business_id());

CREATE POLICY website_gen_jobs_member_write ON website_generation_jobs
    FOR ALL USING (business_id = current_business_id());

-- Section types are read-only for authenticated users (seeded by platform)
CREATE POLICY website_section_types_read ON website_section_types
    FOR SELECT USING (true);

-- Media assets: business member can read their own business assets
CREATE POLICY media_assets_member_read ON media_assets
    FOR SELECT USING (
        business_id IS NULL
        OR business_id = current_business_id()
    );
CREATE POLICY media_assets_member_write ON media_assets
    FOR ALL USING (business_id = current_business_id());
