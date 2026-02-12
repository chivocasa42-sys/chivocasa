-- =====================================================
-- FUNCTION: search_colonias
-- =====================================================
-- Fuzzy search sv_loc_group2 by name, returning coords
-- and parent municipio/departamento for context.
-- Used by the Valuador autocomplete input.
-- =====================================================

CREATE OR REPLACE FUNCTION public.search_colonias(
  p_query text
)
RETURNS TABLE (
  id integer,
  name text,
  latitude double precision,
  longitude double precision,
  municipio text,
  departamento text
)
LANGUAGE sql
STABLE
AS $function$
SELECT
  g2.id,
  g2.loc_name AS name,
  (g2.cords->>'latitude')::double precision AS latitude,
  (g2.cords->>'longitude')::double precision AS longitude,
  g3.loc_name AS municipio,
  g5.loc_name AS departamento
FROM public.sv_loc_group2 g2
LEFT JOIN public.sv_loc_group3 g3 ON g2.parent_loc_group = g3.id
LEFT JOIN public.sv_loc_group4 g4 ON g3.parent_loc_group = g4.id
LEFT JOIN public.sv_loc_group5 g5 ON g4.parent_loc_group = g5.id
WHERE g2.cords IS NOT NULL
  AND (g2.cords->>'latitude') IS NOT NULL
  AND g2.loc_name ILIKE '%' || p_query || '%'
ORDER BY
  -- Exact start match first, then contains
  CASE WHEN g2.loc_name ILIKE p_query || '%' THEN 0 ELSE 1 END,
  g2.loc_name
LIMIT 15;
$function$;

-- Grant access
GRANT EXECUTE ON FUNCTION public.search_colonias(text) TO anon;
GRANT EXECUTE ON FUNCTION public.search_colonias(text) TO authenticated;

-- =====================================================
-- TEST
-- =====================================================
-- SELECT * FROM search_colonias('escal');
-- SELECT * FROM search_colonias('montserrat');
