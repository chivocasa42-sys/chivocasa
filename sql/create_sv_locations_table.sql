-- ============================================
-- El Salvador Locations Table
-- ============================================
-- Table to store urban locations and colonies in El Salvador
-- Run this in Supabase SQL Editor

-- Drop existing table (use this to reset/recreate)
DROP TABLE IF EXISTS sv_locations CASCADE;

-- Create the table
CREATE TABLE IF NOT EXISTS sv_locations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    department TEXT NOT NULL,
    municipality TEXT,
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_sv_locations_department ON sv_locations(department);
CREATE INDEX IF NOT EXISTS idx_sv_locations_municipality ON sv_locations(municipality);
CREATE INDEX IF NOT EXISTS idx_sv_locations_name ON sv_locations(name);

-- Create a GIN index for full-text search on name
CREATE INDEX IF NOT EXISTS idx_sv_locations_name_search ON sv_locations USING GIN (to_tsvector('spanish', name));

-- Enable Row Level Security (optional - adjust as needed)
-- ALTER TABLE sv_locations ENABLE ROW LEVEL SECURITY;

-- Create a policy to allow public read access
-- CREATE POLICY "Allow public read access" ON sv_locations FOR SELECT USING (true);

-- Comment on table
COMMENT ON TABLE sv_locations IS 'Urban locations, colonies, and neighborhoods in El Salvador';
COMMENT ON COLUMN sv_locations.name IS 'Location name (e.g., Colonia San Benito)';
COMMENT ON COLUMN sv_locations.department IS 'El Salvador department (14 total)';
COMMENT ON COLUMN sv_locations.municipality IS 'Municipality within the department (e.g., Apopa, Santa Tecla)';
COMMENT ON COLUMN sv_locations.latitude IS 'Geographic latitude coordinate';
COMMENT ON COLUMN sv_locations.longitude IS 'Geographic longitude coordinate';
