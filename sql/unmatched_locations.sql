-- =====================================================
-- TABLE: unmatched_locations
-- =====================================================
-- Stores listings where location matching failed, for manual review
-- and potential addition to the sv_loc_group hierarchy.
--
-- This table is populated by match_locations.py when a listing
-- cannot be matched to any level in the location hierarchy.

CREATE TABLE IF NOT EXISTS public.unmatched_locations (
    id SERIAL PRIMARY KEY,
    
    -- Listing reference
    external_id BIGINT NOT NULL,
    
    -- Original location data from listing (for analysis)
    title TEXT,
    location_data JSONB,  -- Full location object from scrapped_data
    url TEXT,
    
    -- Extracted text that was searched (for debugging matching)
    searched_text TEXT,
    
    -- Metadata
    source TEXT,              -- e.g., 'Encuentra24', 'MiCasaSV'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Status for tracking review
    status TEXT DEFAULT 'pending',  -- 'pending', 'reviewed', 'resolved', 'ignored'
    notes TEXT,                      -- Admin notes after review
    resolved_at TIMESTAMPTZ,
    
    -- Unique constraint to avoid duplicate entries for same listing
    CONSTRAINT uq_unmatched_external_id UNIQUE (external_id)
);

-- Index for quick lookup by status
CREATE INDEX IF NOT EXISTS idx_unmatched_status ON public.unmatched_locations(status);

-- Index for lookup by source
CREATE INDEX IF NOT EXISTS idx_unmatched_source ON public.unmatched_locations(source);

-- Grant access
GRANT SELECT, INSERT, UPDATE ON public.unmatched_locations TO anon;
GRANT SELECT, INSERT, UPDATE ON public.unmatched_locations TO authenticated;
GRANT USAGE ON SEQUENCE public.unmatched_locations_id_seq TO anon;
GRANT USAGE ON SEQUENCE public.unmatched_locations_id_seq TO authenticated;

-- =====================================================
-- UPSERT FUNCTION: insert_unmatched_location
-- =====================================================
-- Inserts or updates an unmatched location entry.
-- On conflict (same external_id), updates the data but preserves
-- existing status/notes if already reviewed.

CREATE OR REPLACE FUNCTION public.insert_unmatched_location(
    p_external_id BIGINT,
    p_title TEXT,
    p_location_data JSONB,
    p_url TEXT,
    p_searched_text TEXT,
    p_source TEXT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO public.unmatched_locations (
        external_id, title, location_data, url, searched_text, source
    ) VALUES (
        p_external_id, p_title, p_location_data, p_url, p_searched_text, p_source
    )
    ON CONFLICT (external_id) DO UPDATE SET
        title = EXCLUDED.title,
        location_data = EXCLUDED.location_data,
        url = EXCLUDED.url,
        searched_text = EXCLUDED.searched_text,
        source = EXCLUDED.source,
        -- Reset to pending if data changed and wasn't already resolved
        status = CASE 
            WHEN unmatched_locations.status = 'resolved' THEN unmatched_locations.status
            ELSE 'pending'
        END,
        created_at = NOW();  -- Update timestamp on re-insert
END;
$$;

-- Grant execute on function
GRANT EXECUTE ON FUNCTION public.insert_unmatched_location(BIGINT, TEXT, JSONB, TEXT, TEXT, TEXT) TO anon;
GRANT EXECUTE ON FUNCTION public.insert_unmatched_location(BIGINT, TEXT, JSONB, TEXT, TEXT, TEXT) TO authenticated;

-- =====================================================
-- VIEW: unmatched_locations_summary
-- =====================================================
-- Summarizes unmatched locations by source and status for quick overview.

CREATE OR REPLACE VIEW public.unmatched_locations_summary AS
SELECT 
    source,
    status,
    COUNT(*) as count,
    MIN(created_at) as oldest,
    MAX(created_at) as newest
FROM public.unmatched_locations
GROUP BY source, status
ORDER BY source, status;

-- Grant access to view
GRANT SELECT ON public.unmatched_locations_summary TO anon;
GRANT SELECT ON public.unmatched_locations_summary TO authenticated;

-- =====================================================
-- CLEANUP FUNCTION: remove_matched_from_unmatched
-- =====================================================
-- Call this after running location matching to clean up
-- entries that have been successfully matched.

CREATE OR REPLACE FUNCTION public.remove_matched_from_unmatched()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM public.unmatched_locations ul
    WHERE EXISTS (
        SELECT 1 FROM public.listing_location_match llm
        WHERE llm.external_id = ul.external_id
    );
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

GRANT EXECUTE ON FUNCTION public.remove_matched_from_unmatched() TO anon;
GRANT EXECUTE ON FUNCTION public.remove_matched_from_unmatched() TO authenticated;

-- =====================================================
-- TEST QUERIES
-- =====================================================
-- View pending unmatched listings:
-- SELECT * FROM unmatched_locations WHERE status = 'pending' ORDER BY created_at DESC;

-- View summary:
-- SELECT * FROM unmatched_locations_summary;

-- Mark as reviewed:
-- UPDATE unmatched_locations SET status = 'reviewed', notes = 'Need to add location X' WHERE id = 123;

-- Clean up matched entries:
-- SELECT remove_matched_from_unmatched();
