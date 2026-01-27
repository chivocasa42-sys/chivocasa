-- =====================================================
-- SUPABASE RPC FUNCTIONS FOR TAG-BASED SEARCH
-- =====================================================
-- These functions need to be created in Supabase SQL Editor

-- =====================================================
-- Function: get_available_tags
-- Purpose: Get all unique tags from active listings, optionally filtered by search query
-- =====================================================
CREATE OR REPLACE FUNCTION get_available_tags(search_query TEXT DEFAULT '')
RETURNS TABLE (tag TEXT) 
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT DISTINCT jsonb_array_elements_text(tags) as tag
    FROM scrappeddata_ingest
    WHERE 
        active = true 
        AND tags IS NOT NULL
        AND (
            search_query = '' 
            OR LOWER(jsonb_array_elements_text(tags)) LIKE '%' || LOWER(search_query) || '%'
        )
    ORDER BY tag
    LIMIT 50;
END;
$$;

-- =====================================================
-- Function: get_listings_by_tag
-- Purpose: Get paginated listings that have a specific tag (using JSONB @> operator)
-- =====================================================
CREATE OR REPLACE FUNCTION get_listings_by_tag(
    p_tag TEXT,
    p_listing_type TEXT DEFAULT NULL,
    p_limit INTEGER DEFAULT 24,
    p_offset INTEGER DEFAULT 0
)
RETURNS TABLE (
    external_id INTEGER,
    title TEXT,
    price NUMERIC,
    listing_type TEXT,
    first_image TEXT,
    bedrooms INTEGER,
    bathrooms INTEGER,
    area NUMERIC,
    municipio TEXT,
    total_count BIGINT
) 
LANGUAGE plpgsql
AS $$
DECLARE
    v_total_count BIGINT;
BEGIN
    -- Get total count first
    SELECT COUNT(*)
    INTO v_total_count
    FROM scrappeddata_ingest
    WHERE 
        active = true
        AND tags @> jsonb_build_array(p_tag)
        AND (p_listing_type IS NULL OR listing_type = p_listing_type);

    -- Return paginated results with total count
    RETURN QUERY
    SELECT 
        si.external_id,
        si.title,
        si.price,
        si.listing_type,
        (si.images->0->>'url')::TEXT as first_image,
        (si.specs->>'bedrooms')::INTEGER as bedrooms,
        (si.specs->>'bathrooms')::INTEGER as bathrooms,
        (si.specs->>'Área construida (m²)')::NUMERIC as area,
        (si.location->>'municipio_detectado')::TEXT as municipio,
        v_total_count as total_count
    FROM scrappeddata_ingest si
    WHERE 
        si.active = true
        AND si.tags @> jsonb_build_array(p_tag)
        AND (p_listing_type IS NULL OR si.listing_type = p_listing_type)
    ORDER BY si.last_updated DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$;

-- =====================================================
-- USAGE EXAMPLES
-- =====================================================

-- Get all tags containing "santa"
-- SELECT * FROM get_available_tags('santa');

-- Get all tags
-- SELECT * FROM get_available_tags('');

-- Get listings with "Santa Tecla" tag
-- SELECT * FROM get_listings_by_tag('Santa Tecla', NULL, 24, 0);

-- Get sale listings with "San Salvador" tag
-- SELECT * FROM get_listings_by_tag('San Salvador', 'sale', 24, 0);
