-- =====================================================
-- FUNCTION: get_municipalities_for_department
-- =====================================================
-- Returns all L3 (municipality) locations that belong to a given
-- department (L5), along with the count of active listings in each.
-- Optionally filters by listing type (sale/rent).
-- 
-- Usage:
--   SELECT * FROM get_municipalities_for_department('San Salvador');
--   SELECT * FROM get_municipalities_for_department('San Salvador', 'sale');

-- Drop old function signature to avoid conflicts
DROP FUNCTION IF EXISTS public.get_municipalities_for_department(text);
DROP FUNCTION IF EXISTS public.get_municipalities_for_department(text, text);

CREATE OR REPLACE FUNCTION public.get_municipalities_for_department(
  p_departamento text,
  p_listing_type text DEFAULT NULL  -- NEW: filter by 'sale' or 'rent'
)
RETURNS TABLE (
  municipio_id integer,
  municipio_name text,
  listing_count bigint
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  SELECT 
    g3.id AS municipio_id,
    g3.loc_name AS municipio_name,
    COUNT(sd.external_id) AS listing_count
  FROM sv_loc_group5 g5
  INNER JOIN sv_loc_group4 g4 ON g4.parent_loc_group = g5.id
  INNER JOIN sv_loc_group3 g3 ON g3.parent_loc_group = g4.id
  LEFT JOIN listing_location_match llm ON llm.loc_group3_id = g3.id
  LEFT JOIN scrapped_data sd ON sd.external_id = llm.external_id 
    AND sd.active = true
    AND (p_listing_type IS NULL OR sd.listing_type = p_listing_type)  -- Filter by type
  WHERE g5.loc_name = p_departamento
  GROUP BY g3.id, g3.loc_name
  HAVING COUNT(sd.external_id) > 0  -- Only return municipalities with listings
  ORDER BY listing_count DESC, g3.loc_name;
END;
$$;

-- Grant access to anonymous users (for API access)
GRANT EXECUTE ON FUNCTION public.get_municipalities_for_department(text, text) TO anon;
GRANT EXECUTE ON FUNCTION public.get_municipalities_for_department(text, text) TO authenticated;

-- =====================================================
-- TEST QUERY
-- =====================================================
-- SELECT * FROM get_municipalities_for_department('San Salvador');
