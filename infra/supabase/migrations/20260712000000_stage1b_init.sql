-- Migration: Stage 1B Infrastructure Foundation
-- This is a baseline migration to verify the Supabase CLI toolchain, migration directory structure,
-- and apply/reset workflows. 

-- We do NOT create any Business, Identity, or Domain tables prematurely in Stage 1B.
-- PostgreSQL 13+ natively supports gen_random_uuid(), so we do not need the uuid-ossp extension.

SELECT 1;
