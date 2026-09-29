-- P5 Documents: extend the existing rendered_documents PDF primitive with
-- structured forms, private bounded uploads and single-resource request links.
-- Uploaded bytes are deliberately private database objects (as rendered PDFs
-- already are), never assets in the public `media` bucket.
CREATE TABLE document_templates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES businesses(id),
    kind text NOT NULL CHECK (kind IN ('agreement','consent','intake','certificate','report','generic')),
    title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 160),
    description text NOT NULL DEFAULT '',
    traits jsonb NOT NULL DEFAULT '{}'::jsonb,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    content jsonb NOT NULL,
    created_by uuid NOT NULL REFERENCES platform_identities(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (business_id,id,version)
);
CREATE INDEX document_templates_recent ON document_templates (business_id,created_at DESC);

CREATE TABLE document_forms (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES businesses(id),
    title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 160),
    kind text NOT NULL CHECK (kind IN ('intake','consent','agreement','report','generic')),
    current_version integer NOT NULL DEFAULT 1 CHECK (current_version > 0),
    created_by uuid NOT NULL REFERENCES platform_identities(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (business_id,id)
);
CREATE INDEX document_forms_recent ON document_forms (business_id,created_at DESC);

CREATE TABLE document_form_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL,
    form_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    fields jsonb NOT NULL CHECK (jsonb_typeof(fields)='array'),
    consent_text text,
    guardian_required boolean NOT NULL DEFAULT false,
    definition_sha256 text NOT NULL CHECK (definition_sha256 ~ '^[0-9a-f]{64}$'),
    created_by uuid NOT NULL REFERENCES platform_identities(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id,form_id) REFERENCES document_forms(business_id,id),
    UNIQUE (business_id,form_id,version),
    UNIQUE (business_id,id)
);
CREATE INDEX document_form_versions_form ON document_form_versions (business_id,form_id,version DESC);

CREATE TABLE document_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES businesses(id),
    request_type text NOT NULL CHECK (request_type IN ('form','upload')),
    title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 160),
    form_version_id uuid,
    related_type text NOT NULL CHECK (related_type IN
        ('customer','quote','project','job','booking','membership','academic_student','order','supplier','general')),
    related_id uuid,
    customer_contact_id uuid REFERENCES customer_relationships_contacts(id),
    token_hash text NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    expires_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','fulfilled','revoked')),
    requested_by uuid NOT NULL REFERENCES platform_identities(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    fulfilled_at timestamptz,
    CHECK ((request_type='form')=(form_version_id IS NOT NULL)),
    CHECK (related_type='general' OR related_id IS NOT NULL),
    FOREIGN KEY (business_id,form_version_id) REFERENCES document_form_versions(business_id,id),
    UNIQUE (business_id,id)
);
CREATE INDEX document_requests_recent ON document_requests (business_id,status,created_at DESC);

CREATE TABLE document_submissions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL,
    request_id uuid NOT NULL,
    form_version_id uuid NOT NULL,
    answers jsonb NOT NULL CHECK (jsonb_typeof(answers)='object'),
    signer_name text NOT NULL CHECK (length(trim(signer_name)) BETWEEN 1 AND 160),
    declared_guardian_relationship text,
    age_confirmed boolean NOT NULL DEFAULT false,
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    submitted_at timestamptz NOT NULL DEFAULT now(),
    request_ip inet,
    request_user_agent text,
    FOREIGN KEY (business_id,request_id) REFERENCES document_requests(business_id,id),
    FOREIGN KEY (business_id,form_version_id) REFERENCES document_form_versions(business_id,id),
    UNIQUE (business_id,request_id),
    UNIQUE (business_id,id)
);
CREATE INDEX document_submissions_recent ON document_submissions (business_id,submitted_at DESC);

CREATE TABLE document_signatures (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL,
    submission_id uuid NOT NULL,
    kind text NOT NULL CHECK (kind IN ('typed','drawn')),
    value jsonb NOT NULL,
    signer_name text NOT NULL,
    signer_contact_id uuid REFERENCES customer_relationships_contacts(id),
    signed_at timestamptz NOT NULL DEFAULT now(),
    content_sha256 text NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    request_ip inet,
    request_user_agent text,
    FOREIGN KEY (business_id,submission_id) REFERENCES document_submissions(business_id,id),
    UNIQUE (business_id,submission_id)
);

CREATE TABLE document_files (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL,
    request_id uuid NOT NULL,
    field_key text NOT NULL CHECK (length(field_key) BETWEEN 1 AND 60),
    related_type text NOT NULL,
    related_id uuid,
    filename text NOT NULL CHECK (length(trim(filename)) BETWEEN 1 AND 160),
    content_type text NOT NULL CHECK (content_type IN ('application/pdf','image/jpeg','image/png','image/webp')),
    size_bytes integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 5242880),
    sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    content bytea NOT NULL CHECK (octet_length(content)=size_bytes),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id,request_id) REFERENCES document_requests(business_id,id),
    UNIQUE (business_id,request_id,field_key),
    UNIQUE (business_id,id)
);
CREATE INDEX document_files_recent ON document_files (business_id,created_at DESC);

CREATE TABLE document_access_links (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL,
    file_id uuid NOT NULL,
    token_hash text NOT NULL UNIQUE CHECK (token_hash ~ '^[0-9a-f]{64}$'),
    expires_at timestamptz NOT NULL,
    created_by uuid NOT NULL REFERENCES platform_identities(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id,file_id) REFERENCES document_files(business_id,id)
);
CREATE INDEX document_access_links_file ON document_access_links (business_id,file_id,expires_at DESC);

CREATE TABLE document_activity (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id uuid NOT NULL REFERENCES businesses(id),
    request_id uuid,
    event_type text NOT NULL CHECK (event_type IN
        ('document.created','document.requested','document.uploaded','form.submitted','document.signed')),
    actor_kind text NOT NULL CHECK (actor_kind IN ('merchant','request_link')),
    actor_identity_id uuid REFERENCES platform_identities(id),
    signer_name text,
    request_ip inet,
    request_user_agent text,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    occurred_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (business_id,request_id) REFERENCES document_requests(business_id,id),
    CHECK ((actor_kind='merchant')=(actor_identity_id IS NOT NULL))
);
CREATE INDEX document_activity_recent ON document_activity (business_id,occurred_at DESC);

-- The public API uses a hashed, expiring request token as a *single-resource*
-- credential. This narrow lookup reveals only a UUID tenant ID, not file data.
CREATE FUNCTION document_request_business(p_hash text) RETURNS uuid
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path=public AS $$
    SELECT business_id FROM document_requests
    WHERE token_hash=p_hash AND status IN ('open','fulfilled')
      AND expires_at>clock_timestamp()
    LIMIT 1;
$$;
REVOKE ALL ON FUNCTION document_request_business(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION document_request_business(text) TO platform_api;

CREATE FUNCTION document_request_token_hash() RETURNS text
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.document_request_token_hash',true),'');
$$;
REVOKE ALL ON FUNCTION document_request_token_hash() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION document_request_token_hash() TO platform_api;

CREATE FUNCTION document_access_business(p_hash text) RETURNS uuid
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path=public AS $$
    SELECT business_id FROM document_access_links
    WHERE token_hash=p_hash AND expires_at>clock_timestamp() LIMIT 1;
$$;
REVOKE ALL ON FUNCTION document_access_business(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION document_access_business(text) TO platform_api;

-- Platform records are private even when this schema is exposed by PostgREST.
-- Merchant actions require an authenticated identity; public token actions
-- receive only their request, its form version, and their one submission/file.
ALTER TABLE document_templates ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_forms ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_form_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_submissions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_signatures ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_files ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_access_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_activity ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON document_templates,document_forms,document_form_versions,
    document_requests,document_submissions,document_signatures,document_files,
    document_access_links,document_activity
    FROM anon,authenticated;

CREATE POLICY document_templates_merchant ON document_templates FOR ALL TO platform_api
    USING (business_id=current_business_id() AND current_identity_id() IS NOT NULL)
    WITH CHECK (business_id=current_business_id() AND current_identity_id() IS NOT NULL);
CREATE POLICY document_forms_merchant ON document_forms FOR ALL TO platform_api
    USING (business_id=current_business_id() AND current_identity_id() IS NOT NULL)
    WITH CHECK (business_id=current_business_id() AND current_identity_id() IS NOT NULL);
CREATE POLICY document_form_versions_merchant ON document_form_versions FOR ALL TO platform_api
    USING (business_id=current_business_id() AND current_identity_id() IS NOT NULL)
    WITH CHECK (business_id=current_business_id() AND current_identity_id() IS NOT NULL);
CREATE POLICY document_form_versions_request ON document_form_versions FOR SELECT TO platform_api
    USING (business_id=current_business_id() AND EXISTS (
        SELECT 1 FROM document_requests r
        WHERE r.business_id=document_form_versions.business_id
          AND r.form_version_id=document_form_versions.id
          AND r.token_hash=document_request_token_hash() AND r.status='open'
          AND r.expires_at>clock_timestamp()));
CREATE POLICY document_requests_merchant ON document_requests FOR ALL TO platform_api
    USING (business_id=current_business_id() AND current_identity_id() IS NOT NULL)
    WITH CHECK (business_id=current_business_id() AND current_identity_id() IS NOT NULL);
CREATE POLICY document_requests_token_read ON document_requests FOR SELECT TO platform_api
    USING (business_id=current_business_id() AND token_hash=document_request_token_hash()
           AND status IN ('open','fulfilled') AND expires_at>clock_timestamp());
CREATE POLICY document_requests_token_finish ON document_requests FOR UPDATE TO platform_api
    USING (business_id=current_business_id() AND token_hash=document_request_token_hash()
           AND status='open' AND expires_at>clock_timestamp())
    WITH CHECK (business_id=current_business_id() AND token_hash=document_request_token_hash()
           AND status='fulfilled');
CREATE POLICY document_submissions_merchant ON document_submissions FOR SELECT TO platform_api
    USING (business_id=current_business_id() AND current_identity_id() IS NOT NULL);
CREATE POLICY document_submissions_token_read ON document_submissions FOR SELECT TO platform_api
    USING (business_id=current_business_id() AND EXISTS (
        SELECT 1 FROM document_requests r WHERE r.business_id=document_submissions.business_id
          AND r.id=document_submissions.request_id
          AND r.token_hash=document_request_token_hash() AND r.expires_at>clock_timestamp()));
CREATE POLICY document_submissions_token ON document_submissions FOR INSERT TO platform_api
    WITH CHECK (business_id=current_business_id() AND EXISTS (
        SELECT 1 FROM document_requests r
        WHERE r.business_id=document_submissions.business_id
          AND r.id=document_submissions.request_id
          AND r.form_version_id=document_submissions.form_version_id
          AND r.token_hash=document_request_token_hash()
          AND r.status='open' AND r.expires_at>clock_timestamp()));
CREATE POLICY document_signatures_merchant ON document_signatures FOR SELECT TO platform_api
    USING (business_id=current_business_id() AND current_identity_id() IS NOT NULL);
CREATE POLICY document_signatures_token ON document_signatures FOR INSERT TO platform_api
    WITH CHECK (business_id=current_business_id() AND EXISTS (
        SELECT 1 FROM document_submissions s JOIN document_requests r ON r.id=s.request_id
        WHERE s.id=document_signatures.submission_id
          AND s.business_id=document_signatures.business_id
          AND r.token_hash=document_request_token_hash() AND r.status='open'
          AND r.expires_at>clock_timestamp()));
CREATE POLICY document_files_merchant ON document_files FOR SELECT TO platform_api
    USING (business_id=current_business_id() AND current_identity_id() IS NOT NULL);
CREATE POLICY document_files_request_read ON document_files FOR SELECT TO platform_api
    USING (business_id=current_business_id() AND EXISTS (
        SELECT 1 FROM document_requests r WHERE r.business_id=document_files.business_id
          AND r.id=document_files.request_id
          AND r.token_hash=document_request_token_hash() AND r.expires_at>clock_timestamp()));
CREATE POLICY document_files_token ON document_files FOR INSERT TO platform_api
    WITH CHECK (business_id=current_business_id() AND EXISTS (
        SELECT 1 FROM document_requests r
        WHERE r.business_id=document_files.business_id
          AND r.id=document_files.request_id
          AND r.token_hash=document_request_token_hash()
          AND r.status='open' AND r.expires_at>clock_timestamp()));
CREATE POLICY document_files_access ON document_files FOR SELECT TO platform_api
    USING (business_id=current_business_id() AND EXISTS (
        SELECT 1 FROM document_access_links l WHERE l.business_id=document_files.business_id
          AND l.file_id=document_files.id
          AND l.token_hash=NULLIF(current_setting('app.document_access_token_hash',true),'')
          AND l.expires_at>clock_timestamp()));
CREATE POLICY document_access_links_merchant ON document_access_links FOR ALL TO platform_api
    USING (business_id=current_business_id() AND current_identity_id() IS NOT NULL)
    WITH CHECK (business_id=current_business_id() AND current_identity_id() IS NOT NULL);
CREATE POLICY document_access_links_token ON document_access_links FOR SELECT TO platform_api
    USING (business_id=current_business_id()
      AND token_hash=NULLIF(current_setting('app.document_access_token_hash',true),'')
      AND expires_at>clock_timestamp());
CREATE POLICY document_activity_merchant ON document_activity FOR SELECT TO platform_api
    USING (business_id=current_business_id() AND current_identity_id() IS NOT NULL);
CREATE POLICY document_activity_merchant_insert ON document_activity FOR INSERT TO platform_api
    WITH CHECK (business_id=current_business_id() AND current_identity_id() IS NOT NULL
      AND actor_kind='merchant' AND actor_identity_id=current_identity_id());
CREATE POLICY document_activity_token_insert ON document_activity FOR INSERT TO platform_api
    WITH CHECK (business_id=current_business_id() AND actor_kind='request_link'
      AND request_id IS NOT NULL AND actor_identity_id IS NULL AND EXISTS (
        SELECT 1 FROM document_requests r WHERE r.business_id=document_activity.business_id
          AND r.id=document_activity.request_id
          AND r.token_hash=document_request_token_hash()
          AND r.status='open' AND r.expires_at>clock_timestamp()));

-- The platform bootstrap grants broad default table privileges. Narrow them
-- explicitly: immutable versions/submissions/signatures/files cannot UPDATE.
REVOKE ALL ON document_templates,document_forms,document_form_versions,
    document_requests,document_submissions,document_signatures,document_files,
    document_access_links,document_activity FROM platform_api;
GRANT SELECT,INSERT ON document_templates TO platform_api;
GRANT SELECT,INSERT ON document_forms TO platform_api;
GRANT UPDATE (current_version,updated_at) ON document_forms TO platform_api;
GRANT SELECT,INSERT ON document_form_versions TO platform_api;
GRANT SELECT,INSERT ON document_requests TO platform_api;
GRANT UPDATE (status,fulfilled_at) ON document_requests TO platform_api;
GRANT SELECT,INSERT ON document_submissions,document_signatures,document_files TO platform_api;
GRANT SELECT,INSERT ON document_access_links TO platform_api;
GRANT SELECT,INSERT ON document_activity TO platform_api;
