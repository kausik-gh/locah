-- P5: work phases are not configurable lifecycle steps. A milestone may have
-- one responsible workforce member and an invoice reference; money stays in Invoicing.
ALTER TABLE projects_phases
    ADD COLUMN responsible_member_id UUID REFERENCES workforce_members(id),
    ADD COLUMN invoice_id UUID REFERENCES invoicing_documents(id),
    ADD COLUMN completion_note TEXT;
CREATE INDEX projects_phases_responsible ON projects_phases (business_id, responsible_member_id)
    WHERE responsible_member_id IS NOT NULL;
