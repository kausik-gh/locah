-- Booking modes: site visit and event date (Founder refinement — Bookings
-- §13–§14; Master Doc §6.1 BK-07/BK-08). One engine, two more modes:
--
-- * site_visit — a slot with a sales person (provider) at a project or
--   property; the sales relationship stays in Leads, linked by lead_id.
-- * event_date — the date (and the hall/resource) is what is scarce: booked
--   for the whole local day.

ALTER TABLE bookings_bookings DROP CONSTRAINT bookings_bookings_reservation_mode_check;
ALTER TABLE bookings_bookings ADD CONSTRAINT bookings_bookings_reservation_mode_check
    CHECK (reservation_mode IN (
        'appointment', 'accommodation', 'table', 'class_session', 'rental', 'site_visit', 'event_date'
    ));

ALTER TABLE bookings_bookings ADD COLUMN lead_id UUID REFERENCES leads_leads(id);
CREATE INDEX bookings_bookings_lead ON bookings_bookings (lead_id) WHERE lead_id IS NOT NULL;
