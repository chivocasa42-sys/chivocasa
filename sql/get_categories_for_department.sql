-- =====================================================
-- FUNCTION: get_categories_for_department
-- =====================================================
-- Returns distinct property-type tags that exist for a given department.
-- Used by the department API to populate the dynamic Categoría filter.
--
-- Usage:
--   SELECT * FROM get_categories_for_department('La Libertad');
--   SELECT * FROM get_categories_for_department('San Salvador', 'sale');

CREATE OR REPLACE FUNCTION public.get_categories_for_department(
  p_departamento text,
  p_listing_type text DEFAULT NULL
)
RETURNS TABLE (category text)
LANGUAGE sql
STABLE
AS $$
  SELECT DISTINCT t.tag AS category
  FROM public.scrapped_data sd
  INNER JOIN listing_location_match llm ON sd.external_id = llm.external_id
  INNER JOIN sv_loc_group5 g5 ON llm.loc_group5_id = g5.id
  CROSS JOIN LATERAL jsonb_array_elements_text(sd.tags) AS t(tag)
  WHERE sd.active IS TRUE
    AND g5.loc_name = p_departamento
    AND (p_listing_type IS NULL OR sd.listing_type = p_listing_type)
    AND t.tag IN ('Casa', 'Apartamento', 'Terreno', 'Local', 'Oficina', 'Bodega', 'Proyecto', 'Edificio', 'Finca', 'Lote')
  ORDER BY category;
$$;

-- Grant access
GRANT EXECUTE ON FUNCTION public.get_categories_for_department(text, text) TO anon;
GRANT EXECUTE ON FUNCTION public.get_categories_for_department(text, text) TO authenticated;

-- =====================================================
-- TEST QUERIES
-- =====================================================
-- All categories in La Libertad:
-- SELECT * FROM get_categories_for_department('La Libertad');
-- Only sale categories in San Salvador:
-- SELECT * FROM get_categories_for_department('San Salvador', 'sale');
