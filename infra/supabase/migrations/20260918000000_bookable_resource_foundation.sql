-- Bookable resources: the primitive that lets one booking engine represent a
-- salon chair, a restaurant table, a hotel room, a hire car and a yoga class.
--
-- What the existing model could not say
-- -------------------------------------
-- A booking pointed at an offering, a provider (a person) and a location, and
-- capacity was an integer the *caller* passed in. So a restaurant could say
-- "this location seats 40 across bookings tagged table" but could not say
-- "table 7 is taken": two parties of four fit inside 40 while both wanting the
-- one eight-top. A hotel could not answer "which room am I in?" at all, because
-- accommodation was a pool with no members. And because capacity arrived on the
-- request, a client could send a large one and pass any check.
--
-- What is actually common across those businesses
-- -----------------------------------------------
-- Every booking consumes some constrained thing for an interval. The thing is
-- either a person's time, an asset's time, or a seat out of a shared pool. The
-- axis that matters is therefore not the industry but whether a subject admits
-- one booking at a time or several:
--
--   exclusive - room, table, court, vehicle, a person. capacity 1.
--   pooled    - seats in a class or a workshop. capacity N.
--
-- A table is exclusive, not pooled: a party of two occupying a four-top takes
-- the whole table. Its seat count is a *fit* constraint (min/max party size),
-- not a pool to sell from. Collapsing those two would silently sell the same
-- table twice.
--
-- People stay people
-- ------------------
-- A workforce member is not a resource: they have employment, skills, location
-- assignments and pay, none of which belong on a room. The two are kept as
-- separate entities and unified only where they genuinely behave alike - in an
-- allocation, which is the thing that can collide.

CREATE EXTENSION IF NOT EXISTS btree_gist;


CREATE TABLE bookings_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),
    location_id UUID NOT NULL REFERENCES business_locations(id),

    -- Deliberately open text, not an enum. A padel court, a darkroom and a
    -- mooring are all resources; the engine does not behave differently per
    -- type, and business-type configuration is what decides which vocabulary a
    -- given business is offered. Adding a vertical must not need a migration.
    resource_type TEXT NOT NULL,
    name TEXT NOT NULL,
    code TEXT,

    allocation_mode TEXT NOT NULL DEFAULT 'exclusive'
        CHECK (allocation_mode IN ('exclusive', 'pooled')),
    capacity INTEGER NOT NULL DEFAULT 1 CHECK (capacity >= 1),

    -- Fit, not supply: a four-top cannot seat six, and a double room should not
    -- be sold to one guest when singles exist.
    min_party_size INTEGER CHECK (min_party_size IS NULL OR min_party_size >= 1),
    max_party_size INTEGER CHECK (max_party_size IS NULL OR max_party_size >= 1),

    -- Turnaround the next guest cannot book into: cleaning a room, resetting a
    -- table, refuelling a car. Held on the resource because it is a property of
    -- the thing, not of whoever booked it.
    buffer_before_minutes INTEGER NOT NULL DEFAULT 0 CHECK (buffer_before_minutes >= 0),
    buffer_after_minutes INTEGER NOT NULL DEFAULT 0 CHECK (buffer_after_minutes >= 0),

    -- Whether this resource is sold by the minute or by the night. It changes
    -- how a request is normalised into a range, not how conflicts are detected.
    granularity TEXT NOT NULL DEFAULT 'slot'
        CHECK (granularity IN ('slot', 'date_range')),

    is_active BOOLEAN NOT NULL DEFAULT true,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    version INTEGER NOT NULL DEFAULT 1,

    -- An exclusive subject with capacity 2 is a contradiction that would make
    -- the allocation rules below silently wrong.
    CONSTRAINT bookings_resources_exclusive_is_single
        CHECK (allocation_mode <> 'exclusive' OR capacity = 1),
    CONSTRAINT bookings_resources_party_range
        CHECK (min_party_size IS NULL OR max_party_size IS NULL
               OR max_party_size >= min_party_size)
);

CREATE UNIQUE INDEX bookings_resources_code_key
    ON bookings_resources (business_id, location_id, lower(code))
    WHERE code IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX bookings_resources_location
    ON bookings_resources (business_id, location_id)
    WHERE deleted_at IS NULL AND is_active;


-- An allocation is a claim on one subject for one interval. It is the only
-- thing that can collide, which is what lets a single constraint cover a
-- stylist, a room and a hire car.
CREATE TABLE bookings_booking_allocations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id),

    -- A blackout is an allocation the business holds itself - maintenance, a
    -- public holiday, a car off the road. Modelling it as an allocation rather
    -- than a separate table means the exclusion constraint below already stops
    -- anyone booking into it, with no extra code on the booking path.
    kind TEXT NOT NULL DEFAULT 'booking' CHECK (kind IN ('booking', 'blackout')),
    booking_id UUID REFERENCES bookings_bookings(id) ON DELETE CASCADE,

    resource_id UUID REFERENCES bookings_resources(id),
    provider_id UUID REFERENCES workforce_members(id),

    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity >= 1),

    -- Copied from the resource at write time. An exclusion constraint cannot
    -- read another table, and this is what its predicate tests.
    is_exclusive BOOLEAN NOT NULL DEFAULT true,

    -- Half-open [start, end). Checkout on the 17th and checkin on the 17th do
    -- not overlap, so nights and thirty-minute slots need no separate model.
    -- Buffers are already inside this range, which is why turnaround needs no
    -- special case on the booking path either.
    occupies TSTZRANGE NOT NULL,

    released_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT bookings_allocation_one_subject
        CHECK ((resource_id IS NOT NULL)::int + (provider_id IS NOT NULL)::int = 1),
    CONSTRAINT bookings_allocation_booking_present
        CHECK (kind = 'blackout' OR booking_id IS NOT NULL),
    CONSTRAINT bookings_allocation_range_nonempty
        CHECK (NOT isempty(occupies))
);

-- The invariant, in the database rather than in a service.
--
-- Two requests that both read availability before either commits cannot both
-- win: the second INSERT is rejected by Postgres, not by whichever application
-- process happened to look second. Released allocations drop out of the index,
-- so cancelling frees the slot without losing the history of who held it.
ALTER TABLE bookings_booking_allocations
    ADD CONSTRAINT bookings_allocation_resource_no_overlap
    EXCLUDE USING gist (resource_id WITH =, occupies WITH &&)
    WHERE (resource_id IS NOT NULL AND is_exclusive AND released_at IS NULL);

ALTER TABLE bookings_booking_allocations
    ADD CONSTRAINT bookings_allocation_provider_no_overlap
    EXCLUDE USING gist (provider_id WITH =, occupies WITH &&)
    WHERE (provider_id IS NOT NULL AND released_at IS NULL);

-- Pooled resources cannot be covered this way: "the seats sold across
-- overlapping bookings must not exceed capacity" is a sum, and an exclusion
-- constraint compares pairs. Those are serialised with an advisory lock keyed
-- on the resource and a sum check inside the same transaction. Stated plainly
-- because it is a real difference in strength between the two modes, not an
-- oversight.
CREATE INDEX bookings_allocation_pool_usage
    ON bookings_booking_allocations USING gist (resource_id, occupies)
    WHERE released_at IS NULL AND NOT is_exclusive;

CREATE INDEX bookings_allocation_booking
    ON bookings_booking_allocations (booking_id)
    WHERE booking_id IS NOT NULL;


ALTER TABLE bookings_resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings_resources FORCE ROW LEVEL SECURITY;
ALTER TABLE bookings_booking_allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings_booking_allocations FORCE ROW LEVEL SECURITY;

CREATE POLICY bookings_resources_member ON bookings_resources
    FOR SELECT TO public USING (deleted_at IS NULL AND business_id = current_business_id());
CREATE POLICY bookings_resources_api_write ON bookings_resources
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

CREATE POLICY bookings_allocations_member ON bookings_booking_allocations
    FOR SELECT TO public USING (business_id = current_business_id());
CREATE POLICY bookings_allocations_api_write ON bookings_booking_allocations
    FOR ALL TO platform_api USING (business_id = current_business_id())
    WITH CHECK (business_id = current_business_id());

GRANT SELECT, INSERT, UPDATE, DELETE ON bookings_resources TO platform_api;
GRANT SELECT, INSERT, UPDATE, DELETE ON bookings_booking_allocations TO platform_api;


-- Backfill provider allocations for bookings that are still live, so the
-- exclusion constraint governs the existing calendar rather than only whatever
-- is booked from now on. Verified beforehand that no active booking pair
-- already overlaps on a provider, so this cannot fail partway.
INSERT INTO bookings_booking_allocations
    (business_id, kind, booking_id, provider_id, quantity, is_exclusive, occupies)
SELECT b.business_id, 'booking', b.id, b.provider_id, 1, true,
       tstzrange(b.starts_at, b.ends_at)
FROM bookings_bookings b
WHERE b.deleted_at IS NULL
  AND b.provider_id IS NOT NULL
  AND b.status IN ('pending', 'confirmed', 'checked_in')
  AND b.starts_at < b.ends_at;
