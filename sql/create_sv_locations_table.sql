-- ============================================
-- El Salvador Locations Table (sv_locations)
-- ============================================
-- Canonical table to store urban locations and colonies in El Salvador.
-- DO NOT include id or created_at in the source JSON; these are auto-generated.
--
-- Run this in Supabase SQL Editor.

-- Drop existing table if needed (use this to reset/recreate)
DROP TABLE IF EXISTS sv_locations CASCADE;

-- Create the table
CREATE TABLE IF NOT EXISTS sv_locations (
    -- Database-generated fields (NOT from JSON source)
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Core location fields (from el_salvador_locations.json)
    name TEXT NOT NULL,
    department TEXT NOT NULL DEFAULT '',
    municipality TEXT,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    
    -- Additional fields from JSON source
    type TEXT,                    -- e.g., Barrio, Colonia, Residencial, etc.
    source TEXT                   -- e.g., "Verified Database", "OpenStreetMap"
);

-- Unique constraint for deduplication
-- This prevents inserting duplicate records based on the uniqueness key
CREATE UNIQUE INDEX IF NOT EXISTS idx_sv_locations_unique_key 
    ON sv_locations (
        LOWER(TRIM(name)), 
        LOWER(COALESCE(TRIM(municipality), '')), 
        LOWER(COALESCE(TRIM(department), ''))
    );

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sv_locations_department ON sv_locations(department);
CREATE INDEX IF NOT EXISTS idx_sv_locations_municipality ON sv_locations(municipality);
CREATE INDEX IF NOT EXISTS idx_sv_locations_name ON sv_locations(name);
CREATE INDEX IF NOT EXISTS idx_sv_locations_type ON sv_locations(type);

-- Full-text search index on name (Spanish)
CREATE INDEX IF NOT EXISTS idx_sv_locations_name_search 
    ON sv_locations USING GIN (to_tsvector('spanish', name));

-- Combined full-text search across name, municipality, department
CREATE INDEX IF NOT EXISTS idx_sv_locations_fulltext 
    ON sv_locations USING GIN (
        to_tsvector('spanish', 
            COALESCE(name, '') || ' ' || 
            COALESCE(municipality, '') || ' ' || 
            COALESCE(department, '')
        )
    );

-- Enable Row Level Security (optional - adjust as needed)
-- ALTER TABLE sv_locations ENABLE ROW LEVEL SECURITY;

-- Create a policy to allow public read access
-- CREATE POLICY "Allow public read access" ON sv_locations FOR SELECT USING (true);

-- ============================================
-- Table and Column Comments
-- ============================================
COMMENT ON TABLE sv_locations IS 
    'Urban locations, colonies, and neighborhoods in El Salvador. ' ||
    'Source of truth: el_salvador_locations.json';

COMMENT ON COLUMN sv_locations.id IS 
    'Auto-generated unique identifier (SERIAL). NOT from JSON source.';

COMMENT ON COLUMN sv_locations.created_at IS 
    'Auto-generated timestamp when record was inserted. NOT from JSON source.';

COMMENT ON COLUMN sv_locations.name IS 
    'Location name (e.g., Colonia San Benito). Stored in Title Case.';

COMMENT ON COLUMN sv_locations.department IS 
    'El Salvador department (14 total). Stored in Title Case.';

COMMENT ON COLUMN sv_locations.municipality IS 
    'Municipality within the department (e.g., Apopa, Santa Tecla). Stored in Title Case.';

COMMENT ON COLUMN sv_locations.latitude IS 
    'Geographic latitude coordinate (decimal degrees).';

COMMENT ON COLUMN sv_locations.longitude IS 
    'Geographic longitude coordinate (decimal degrees).';

COMMENT ON COLUMN sv_locations.type IS 
    'Location type: Barrio, Colonia, Residencial, Urbanización, Comunidad, etc.';

COMMENT ON COLUMN sv_locations.source IS 
    'Data source: "Verified Database", "OpenStreetMap", etc.';
