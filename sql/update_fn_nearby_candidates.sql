-- =====================================================
-- FUNCTION: fn_nearby_candidates (v2 - Location Fallback)
-- =====================================================
-- Updated to include listings with null lat/lng in scrapped_data.location
-- by falling back to sv_loc_group2.cords via listing_location_match.
--
-- Changes from previous version:
-- 1. LEFT JOIN to listing_location_match + sv_loc_group2 for coordinate fallback
-- 2. COALESCE(sd.location coords, sv_loc_group2.cords) for effective lat/lng
-- 3. DISTINCT ON to avoid duplicates from multiple location matches
-- 4. Both parent functions (fn_listings_nearby_page, fn_listing_price_stats_nearby)
--    automatically benefit since they delegate to this function
--
-- This means listings that were scraped without coordinates but were
-- matched to a known colonia (sv_loc_group2) will now appear on the map
-- using the colonia's centroid coordinates.

CREATE OR REPLACE FUNCTION public.fn_nearby_candidates(
  p_lat double precision,
  p_lng double precision,
  p_radius_km double precision,
  p_listing_types text[] DEFAULT ARRAY['rent'::text, 'sale'::text],
  p_active_only boolean DEFAULT true
)
RETURNS TABLE(
  external_id bigint,
  listing_type text,
  price double precision,
  last_updated timestamp with time zone,
  title text,
  url text,
  source text,
  specs jsonb,
  tags jsonb,
  first_image text,
  lat double precision,
  lng double precision,
  distance_km numeric
)
LANGUAGE sql
STABLE
AS $function$
WITH resolved AS (
  SELECT DISTINCT ON (sd.external_id)
    sd.external_id,
    sd.listing_type,
    sd.price,
    sd.last_updated,
    sd.title,
    sd.url,
    sd.source,
    sd.specs,
    sd.tags,
    sd.images,
    -- Effective coordinates: prefer scrapped_data.location, fallback to sv_loc_group2.cords
    COALESCE(
      nullif(sd.location->>'latitude','null')::double precision,
      (g2.cords->>'latitude')::double precision
    ) AS eff_lat,
    COALESCE(
      nullif(sd.location->>'longitude','null')::double precision,
      (g2.cords->>'longitude')::double precision
    ) AS eff_lng
  FROM public.scrapped_data sd
  LEFT JOIN public.listing_location_match llm ON sd.external_id = llm.external_id
  LEFT JOIN public.sv_loc_group2 g2 ON llm.loc_group2_id = g2.id AND g2.cords IS NOT NULL
  WHERE sd.active IS TRUE
    AND (p_listing_types IS NULL OR sd.listing_type = ANY(p_listing_types))
    AND sd.price IS NOT NULL
  ORDER BY sd.external_id
)
SELECT
  r.external_id,
  r.listing_type,
  r.price,
  r.last_updated,
  r.title,
  r.url,
  r.source,
  r.specs,
  r.tags,
  CASE
    WHEN jsonb_typeof(r.images) = 'array' AND jsonb_array_length(r.images) > 0
      THEN r.images->>0
    ELSE NULL
  END AS first_image,
  r.eff_lat AS lat,
  r.eff_lng AS lng,
  round(
    (
      st_distance(
        st_setsrid(st_makepoint(r.eff_lng, r.eff_lat), 4326)::geography,
        st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography
      ) / 1000.0
    )::numeric,
    3
  ) AS distance_km
FROM resolved r
WHERE r.eff_lat IS NOT NULL
  AND r.eff_lng IS NOT NULL
  AND st_dwithin(
    st_setsrid(st_makepoint(r.eff_lng, r.eff_lat), 4326)::geography,
    st_setsrid(st_makepoint(p_lng, p_lat), 4326)::geography,
    p_radius_km * 1000.0
  );
$function$;
