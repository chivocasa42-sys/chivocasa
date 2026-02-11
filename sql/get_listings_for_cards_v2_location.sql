-- =====================================================
-- FUNCTION: get_listings_for_cards (v2 - Location Hierarchy)
-- =====================================================
-- Updated to use listing_location_match instead of location JSON.
-- Filters by department via L5 join, supports optional L3 municipality filter.
--
-- Changes from previous version:
-- 1. Joins to listing_location_match + sv_loc_group5 for department filtering
-- 2. Optional joins to sv_loc_group3 (municipality) and sv_loc_group2 (colonia)
-- 3. New p_municipio parameter to filter by specific municipality
-- 4. Removed tags from return (no longer needed for zone filtering)
-- 5. municipio now comes from L3 hierarchy
--
-- Usage:
--   SELECT * FROM get_listings_for_cards('San Salvador', NULL, 24, 0, 'recent', NULL);
--   SELECT * FROM get_listings_for_cards('San Salvador', 'sale', 24, 0, 'price_asc', 'Antiguo Cuscatlán');

-- Drop old function signatures to avoid conflicts
DROP FUNCTION IF EXISTS public.get_listings_for_cards(text, text, integer, integer, text);
DROP FUNCTION IF EXISTS public.get_listings_for_cards(text, text, integer, integer, text, text);

CREATE OR REPLACE FUNCTION public.get_listings_for_cards(
  p_departamento text,
  p_listing_type text DEFAULT NULL,
  p_limit integer DEFAULT 48,
  p_offset integer DEFAULT 0,
  p_sort_by text DEFAULT 'recent',
  p_municipio text DEFAULT NULL  -- NEW: filter by L3 municipality name
)
RETURNS TABLE (
  external_id bigint,
  title text,
  price numeric,
  listing_type text,
  first_image text,
  bedrooms integer,
  bathrooms numeric,
  area numeric,
  parking integer,
  municipio text,
  latitude double precision,
  longitude double precision,
  total_count bigint
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  WITH filtered AS (
    SELECT DISTINCT ON (sd.external_id)
      sd.*,
      g3.loc_name AS municipio_match,
      g2.loc_name AS colonia_match,
      g2.cords AS g2_cords
    FROM public.scrapped_data sd
    -- Join to location hierarchy via listing_location_match
    INNER JOIN listing_location_match llm ON sd.external_id = llm.external_id
    INNER JOIN sv_loc_group5 g5 ON llm.loc_group5_id = g5.id
    -- Optional joins for lower levels
    LEFT JOIN sv_loc_group4 g4 ON llm.loc_group4_id = g4.id
    LEFT JOIN sv_loc_group3 g3 ON llm.loc_group3_id = g3.id
    LEFT JOIN sv_loc_group2 g2 ON llm.loc_group2_id = g2.id
    WHERE sd.active IS TRUE
      -- Filter by department using L5 hierarchy
      AND g5.loc_name = p_departamento
      AND (p_listing_type IS NULL OR sd.listing_type = p_listing_type)
      -- Filter by municipality if specified
      AND (p_municipio IS NULL OR g3.loc_name = p_municipio)
    ORDER BY sd.external_id
  )
  SELECT
    f.external_id,
    f.title,
    f.price::numeric AS price,
    f.listing_type,
    CASE
      WHEN f.images IS NULL THEN NULL
      WHEN jsonb_typeof(f.images->0) = 'object' THEN f.images->0->>'url'
      ELSE f.images->>0
    END AS first_image,
    NULLIF(regexp_replace(f.specs->>'bedrooms', '[^0-9.]', '', 'g'), '')::numeric::int AS bedrooms,
    NULLIF(regexp_replace(f.specs->>'bathrooms', '[^0-9.]', '', 'g'), '')::numeric AS bathrooms,
    (f.specs->>'area_m2')::numeric AS area,
    NULLIF(regexp_replace(f.specs->>'parking', '[^0-9.]', '', 'g'), '')::numeric::int AS parking,
    -- Use L3 (municipality) from hierarchy, fallback to L2 (colonia), then to JSON
    COALESCE(f.municipio_match, f.colonia_match, f.location->>'municipio_detectado') AS municipio,
    -- Effective coordinates: prefer listing's own coords, fallback to L2 colonia centroid
    COALESCE(
      NULLIF(f.location->>'latitude', 'null')::double precision,
      (f.g2_cords->>'latitude')::double precision
    ) AS latitude,
    COALESCE(
      NULLIF(f.location->>'longitude', 'null')::double precision,
      (f.g2_cords->>'longitude')::double precision
    ) AS longitude,
    COUNT(*) OVER() AS total_count
  FROM filtered f
  ORDER BY
    CASE WHEN p_sort_by = 'price_asc'  THEN f.price END ASC NULLS LAST,
    CASE WHEN p_sort_by = 'price_desc' THEN f.price END DESC NULLS LAST,
    CASE WHEN p_sort_by = 'recent' OR p_sort_by IS NULL THEN f.last_updated END DESC NULLS LAST,
    f.external_id DESC
  LIMIT GREATEST(p_limit, 0)
  OFFSET GREATEST(p_offset, 0);
END;
$$;

-- Grant access
GRANT EXECUTE ON FUNCTION public.get_listings_for_cards(text, text, integer, integer, text, text) TO anon;
GRANT EXECUTE ON FUNCTION public.get_listings_for_cards(text, text, integer, integer, text, text) TO authenticated;

-- =====================================================
-- TEST QUERIES
-- =====================================================
-- All listings in San Salvador:
-- SELECT * FROM get_listings_for_cards('San Salvador', NULL, 10, 0, 'recent', NULL);

-- Only sales in Antiguo Cuscatlán:
-- SELECT * FROM get_listings_for_cards('San Salvador', 'sale', 10, 0, 'price_asc', 'Antiguo Cuscatlán');

-- Count municipalities:
-- SELECT * FROM get_municipalities_for_department('San Salvador');
