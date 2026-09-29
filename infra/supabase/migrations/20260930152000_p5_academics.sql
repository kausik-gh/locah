-- P5 academics owns teaching structure, not fees, attendance or file storage.
CREATE TABLE academics_courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
    title TEXT NOT NULL CHECK (length(trim(title)) > 0), description TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, title)
);
CREATE TABLE academics_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
    course_id UUID NOT NULL REFERENCES academics_courses(id), name TEXT NOT NULL,
    location_id UUID REFERENCES business_locations(id), teacher_member_id UUID REFERENCES workforce_members(id),
    room TEXT, meeting_url TEXT, starts_on DATE, ends_on DATE,
    capacity INTEGER CHECK (capacity IS NULL OR capacity > 0),
    status TEXT NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','active','completed','cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, course_id, name), CHECK (ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on)
);
CREATE INDEX academics_batches_teacher ON academics_batches (business_id, teacher_member_id, status);
CREATE TABLE academics_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
    batch_id UUID NOT NULL REFERENCES academics_batches(id), teacher_member_id UUID REFERENCES workforce_members(id),
    location_id UUID REFERENCES business_locations(id), room TEXT, topic TEXT,
    starts_at TIMESTAMPTZ NOT NULL, ends_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','completed','cancelled')),
    meeting_url TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (ends_at > starts_at)
);
CREATE INDEX academics_sessions_by_batch ON academics_sessions (business_id, batch_id, starts_at);
CREATE INDEX academics_sessions_by_teacher ON academics_sessions (business_id, teacher_member_id, starts_at);
CREATE TABLE academics_enrolments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
    batch_id UUID NOT NULL REFERENCES academics_batches(id),
    student_contact_id UUID NOT NULL REFERENCES customer_relationships_contacts(id),
    guardian_contact_id UUID REFERENCES customer_relationships_contacts(id),
    is_minor BOOLEAN NOT NULL DEFAULT false,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','transferred','completed','withdrawn')),
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (business_id, batch_id, student_contact_id),
    CHECK (NOT is_minor OR guardian_contact_id IS NOT NULL),
    CHECK (guardian_contact_id IS NULL OR guardian_contact_id <> student_contact_id)
);
CREATE INDEX academics_enrolments_by_student ON academics_enrolments (business_id, student_contact_id);
CREATE INDEX academics_enrolments_by_guardian ON academics_enrolments (business_id, guardian_contact_id);
CREATE TABLE academics_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
    batch_id UUID NOT NULL REFERENCES academics_batches(id), title TEXT NOT NULL,
    held_on DATE, maximum NUMERIC(8,2) NOT NULL CHECK (maximum > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE academics_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
    assessment_id UUID NOT NULL REFERENCES academics_assessments(id),
    enrolment_id UUID NOT NULL REFERENCES academics_enrolments(id),
    marks NUMERIC(8,2) NOT NULL CHECK (marks >= 0), teacher_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (assessment_id, enrolment_id)
);
CREATE TABLE academics_announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), business_id UUID NOT NULL REFERENCES businesses(id),
    batch_id UUID NOT NULL REFERENCES academics_batches(id), title TEXT NOT NULL, body TEXT NOT NULL,
    created_by UUID REFERENCES platform_identities(id), created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

DO $$ DECLARE name TEXT; BEGIN
    FOREACH name IN ARRAY ARRAY['academics_courses','academics_batches','academics_sessions',
                                   'academics_enrolments','academics_assessments','academics_results',
                                   'academics_announcements'] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', name);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', name);
        EXECUTE format('REVOKE ALL ON %I FROM anon, authenticated', name);
        EXECUTE format('CREATE POLICY %I ON %I FOR ALL TO platform_api USING (business_id = current_business_id()) WITH CHECK (business_id = current_business_id())',
                       name || '_api_scope', name);
        EXECUTE format('GRANT SELECT, INSERT, UPDATE ON %I TO platform_api', name);
    END LOOP;
END $$;

CREATE FUNCTION academics_scope_allows_batch(target_batch UUID) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT EXISTS (SELECT 1 FROM academics_batches b WHERE b.id=target_batch
                   AND b.business_id=current_business_id()
                   AND assignment_scope_allows_member(b.teacher_member_id)
                   AND location_scope_allows(b.location_id));
$$;
CREATE FUNCTION academics_scope_allows_assessment(target_assessment UUID) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT EXISTS (SELECT 1 FROM academics_assessments a WHERE a.id=target_assessment
                   AND a.business_id=current_business_id()
                   AND academics_scope_allows_batch(a.batch_id));
$$;
REVOKE ALL ON FUNCTION academics_scope_allows_batch(UUID), academics_scope_allows_assessment(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION academics_scope_allows_batch(UUID), academics_scope_allows_assessment(UUID) TO platform_api;
CREATE POLICY academics_batch_assignment ON academics_batches AS RESTRICTIVE FOR ALL TO platform_api
    USING (assignment_scope_allows_member(teacher_member_id) AND location_scope_allows(location_id))
    WITH CHECK (assignment_scope_allows_member(teacher_member_id) AND location_scope_allows(location_id));
CREATE POLICY academics_session_assignment ON academics_sessions AS RESTRICTIVE FOR ALL TO platform_api
    USING (academics_scope_allows_batch(batch_id)) WITH CHECK (academics_scope_allows_batch(batch_id));
CREATE POLICY academics_enrolment_assignment ON academics_enrolments AS RESTRICTIVE FOR ALL TO platform_api
    USING (academics_scope_allows_batch(batch_id)) WITH CHECK (academics_scope_allows_batch(batch_id));
CREATE POLICY academics_assessment_assignment ON academics_assessments AS RESTRICTIVE FOR ALL TO platform_api
    USING (academics_scope_allows_batch(batch_id)) WITH CHECK (academics_scope_allows_batch(batch_id));
CREATE POLICY academics_result_assignment ON academics_results AS RESTRICTIVE FOR ALL TO platform_api
    USING (academics_scope_allows_assessment(assessment_id))
    WITH CHECK (academics_scope_allows_assessment(assessment_id));
CREATE POLICY academics_announcement_assignment ON academics_announcements AS RESTRICTIVE FOR ALL TO platform_api
    USING (academics_scope_allows_batch(batch_id)) WITH CHECK (academics_scope_allows_batch(batch_id));

-- A guardian's platform identity is checked by the API against the nominated
-- customer contact. Do not grant direct table reads for children's records.
CREATE FUNCTION academics_guardian_portal(target_business UUID) RETURNS JSONB
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'enrolment_id', e.id, 'student_name', student.display_name,
        'batch_id', b.id, 'batch_name', b.name, 'course_title', c.title,
        'sessions', COALESCE((SELECT jsonb_agg(jsonb_build_object(
            'id', s.id, 'topic', s.topic, 'starts_at', s.starts_at, 'ends_at', s.ends_at,
            'meeting_url', s.meeting_url) ORDER BY s.starts_at)
            FROM academics_sessions s WHERE s.batch_id=b.id AND s.business_id=target_business
              AND s.status='scheduled'), '[]'::jsonb),
        'results', COALESCE((SELECT jsonb_agg(jsonb_build_object(
            'title', a.title, 'maximum', a.maximum, 'marks', r.marks,
            'teacher_note', r.teacher_note) ORDER BY a.created_at)
            FROM academics_results r JOIN academics_assessments a ON a.id=r.assessment_id
            WHERE r.enrolment_id=e.id AND r.business_id=target_business), '[]'::jsonb),
        'announcements', COALESCE((SELECT jsonb_agg(jsonb_build_object(
            'id', n.id, 'title', n.title, 'body', n.body, 'created_at', n.created_at)
            ORDER BY n.created_at DESC) FROM academics_announcements n
            WHERE n.batch_id=b.id AND n.business_id=target_business), '[]'::jsonb)
    ) ORDER BY e.enrolled_at), '[]'::jsonb)
    FROM academics_enrolments e
    JOIN academics_batches b ON b.id=e.batch_id AND b.business_id=target_business
    JOIN academics_courses c ON c.id=b.course_id AND c.business_id=target_business
    JOIN customer_relationships_contacts student ON student.id=e.student_contact_id
        AND student.business_id=target_business
    LEFT JOIN customer_relationships_contacts guardian ON guardian.id=e.guardian_contact_id
        AND guardian.business_id=target_business
    WHERE e.business_id=target_business AND e.status='active'
      AND current_identity_id() IS NOT NULL
      AND ((guardian.identity_id=current_identity_id() AND guardian.deleted_at IS NULL)
           OR (NOT e.is_minor AND student.identity_id=current_identity_id()
               AND student.deleted_at IS NULL));
$$;
REVOKE ALL ON FUNCTION academics_guardian_portal(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION academics_guardian_portal(UUID) TO platform_api;

INSERT INTO module_definitions (id, name, module_class, description, dependencies, is_available)
VALUES ('academics', 'Courses & batches', 'optional', 'Teaching structure, cohorts, sessions and results',
        '{offerings-catalog}', true)
ON CONFLICT (id) DO NOTHING;
