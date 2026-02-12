-- =====================================================
-- FUNCTION: fn_valuador_comps (v2)
-- =====================================================
-- Returns comparable sale/rent listings within a radius
-- for property valuation. Uses COALESCE coord pattern
-- (listing coords → L2 centroid fallback).
--
-- v2 changes:
--   - Includes BOTH active and inactive listings
--   - Excludes listings older than 6 months
--   - Returns url, active status, and coordinates
-- =====================================================

CREATE OR REPLACE FUNCTION public.fn_valuador_comps(
  p_lat double precision,
  p_lng double precision,
  p_radius_km double precision DEFAULT 1.5,
  p_listing_type text DEFAULT 'sale',
  p_property_type text DEFAULT NULL  -- 'casa','apartamento','lote','local' or NULL for all
)
RETURNS TABLE (
  external_id bigint,
  price double precision,
  area_m2 double precision,
  bedrooms integer,
  bathrooms numeric,
  parking integer,
  distance_km numeric,
  title text,
  url text,
  active boolean,
  lat double precision,
  lng double precision
)
LANGUAGE sql
STABLE
AS $function$
WITH resolved AS (
  SELECT DISTINCT ON (sd.external_id)
    sd.external_id,
    sd.price,
    sd.title,
    sd.url,
    sd.active,
    sd.specs,
    -- Effective coordinates: prefer listing's own, fallback to colonia centroid
    COALESCE(
      NULLIF(sd.location->>'latitude', 'null')::double precision,
      (g2.cords->>'latitude')::double precision
    ) AS eff_lat,
    COALESCE(
      NULLIF(sd.location->>'longitude', 'null')::double precision,
      (g2.cords->>'longitude')::double precision
    ) AS eff_lng
  FROM public.scrapped_data sd
  LEFT JOIN public.listing_location_match llm ON sd.external_id = llm.external_id
  LEFT JOIN public.sv_loc_group2 g2 ON llm.loc_group2_id = g2.id AND g2.cords IS NOT NULL
  WHERE sd.listing_type = p_listing_type
    AND sd.price IS NOT NULL
    AND sd.price > 0
    -- Include both active and inactive, but exclude listings older than 6 months
    AND sd.last_updated >= (now() - interval '6 months')
    -- Require area_m2 to be present and numeric > 0
    AND sd.specs IS NOT NULL
    AND sd.specs->>'area_m2' IS NOT NULL
    AND NULLIF(regexp_replace(sd.specs->>'area_m2', '[^0-9.]', '', 'g'), '') IS NOT NULL
    -- Property type filter via title keyword
    AND (
      p_property_type IS NULL
      OR sd.title ILIKE '%' || p_property_type || '%'
    )
  ORDER BY sd.external_id
)
SELECT
  r.external_id,
  r.price,
  NULLIF(regexp_replace(r.specs->>'area_m2', '[^0-9.]', '', 'g'), '')::double precision AS area_m2,
  NULLIF(regexp_replace(COALESCE(r.specs->>'bedrooms', ''), '[^0-9.]', '', 'g'), '')::numeric::integer AS bedrooms,
  NULLIF(regexp_replace(COALESCE(r.specs->>'bathrooms', ''), '[^0-9.]', '', 'g'), '')::numeric AS bathrooms,
  NULLIF(regexp_replace(COALESCE(r.specs->>'parking', ''), '[^0-9.]', '', 'g'), '')::numeric::integer AS parking,
  round(
    (
      st_distance(
        st_setsrid(st_makepoint(r.eff_lng, r.eff_lat), 4326)::geography,
        st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography
      ) / 1000.0
    )::numeric,
    3
  ) AS distance_km,
  r.title,
  r.url,
  r.active,
  r.eff_lat AS lat,
  r.eff_lng AS lng
FROM resolved r
WHERE r.eff_lat IS NOT NULL
  AND r.eff_lng IS NOT NULL
  AND st_dwithin(
    st_setsrid(st_makepoint(r.eff_lng, r.eff_lat), 4326)::geography,
    st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography,
    p_radius_km * 1000.0
  )
  -- Double-check area parsed correctly
  AND NULLIF(regexp_replace(r.specs->>'area_m2', '[^0-9.]', '', 'g'), '')::double precision > 0
ORDER BY distance_km;
$function$;

-- Grant access
GRANT EXECUTE ON FUNCTION public.fn_valuador_comps(double precision, double precision, double precision, text, text) TO anon;
GRANT EXECUTE ON FUNCTION public.fn_valuador_comps(double precision, double precision, double precision, text, text) TO authenticated;

-- =====================================================
-- TEST QUERIES
-- =====================================================
-- Comps near Escalón (sale, casas, 1.5km):
-- SELECT * FROM fn_valuador_comps(13.7034, -89.2368, 1.5, 'sale', 'casa');

-- All sale comps near San Salvador centro (2km):
-- SELECT * FROM fn_valuador_comps(13.6989, -89.1914, 2.0, 'sale', NULL);

-- Rent comps for apartments:
-- SELECT * FROM fn_valuador_comps(13.7034, -89.2368, 1.5, 'rent', 'apartamento');
