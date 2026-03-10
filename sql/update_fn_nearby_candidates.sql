-- =====================================================
-- FUNCTIONS: fn_nearby_candidates + fn_listings_nearby_page
-- =====================================================
-- Purpose:
-- 1. Expose published_date to nearby listings so the map cards can display
--    "Hace X..." based on the original publish date first.
-- 2. Keep last_updated available as the fallback timestamp.
-- 3. Preserve the existing sort behavior for nearby listings.

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
  published_date text,
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
    sd.published_date::text AS published_date,
    sd.last_updated,
    sd.title,
    sd.url,
    sd.source,
    sd.specs,
    sd.tags,
    sd.images,
    COALESCE(
      nullif(sd.location->>'latitude', 'null')::double precision,
      (g2.cords->>'latitude')::double precision
    ) AS eff_lat,
    COALESCE(
      nullif(sd.location->>'longitude', 'null')::double precision,
      (g2.cords->>'longitude')::double precision
    ) AS eff_lng
  FROM public.scrapped_data sd
  LEFT JOIN public.listing_location_match llm ON sd.external_id = llm.external_id
  LEFT JOIN public.sv_loc_group2 g2 ON llm.loc_group2_id = g2.id AND g2.cords IS NOT NULL
  WHERE (NOT p_active_only OR sd.active IS TRUE)
    AND (p_listing_types IS NULL OR sd.listing_type = ANY(p_listing_types))
    AND sd.price IS NOT NULL
  ORDER BY sd.external_id
)
SELECT
  r.external_id,
  r.listing_type,
  r.price,
  r.published_date,
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

CREATE OR REPLACE FUNCTION public.fn_listings_nearby_page(
  p_lat double precision,
  p_lng double precision,
  p_radius_km double precision,
  p_listing_types text[] DEFAULT ARRAY['rent'::text, 'sale'::text],
  p_active_only boolean DEFAULT true,
  p_sort_by text DEFAULT 'distance_asc',
  p_limit integer DEFAULT 5,
  p_offset integer DEFAULT 0
)
RETURNS TABLE(
  external_id bigint,
  listing_type text,
  price double precision,
  published_date text,
  last_updated timestamp with time zone,
  title text,
  url text,
  source text,
  specs jsonb,
  tags jsonb,
  first_image text,
  lat double precision,
  lng double precision,
  distance_km numeric,
  total_count bigint
)
LANGUAGE sql
STABLE
AS $function$
WITH nearby AS (
  SELECT *
  FROM public.fn_nearby_candidates(
    p_lat,
    p_lng,
    p_radius_km,
    p_listing_types,
    p_active_only
  )
)
SELECT
  n.external_id,
  n.listing_type,
  n.price,
  n.published_date,
  n.last_updated,
  n.title,
  n.url,
  n.source,
  n.specs,
  n.tags,
  n.first_image,
  n.lat,
  n.lng,
  n.distance_km,
  COUNT(*) OVER() AS total_count
FROM nearby n
ORDER BY
  CASE WHEN p_sort_by = 'distance_asc' OR p_sort_by IS NULL THEN n.distance_km END ASC NULLS LAST,
  CASE WHEN p_sort_by = 'recent' THEN n.last_updated END DESC NULLS LAST,
  CASE WHEN p_sort_by = 'price_asc' THEN n.price END ASC NULLS LAST,
  CASE WHEN p_sort_by = 'price_desc' THEN n.price END DESC NULLS LAST,
  n.external_id DESC
LIMIT GREATEST(p_limit, 0)
OFFSET GREATEST(p_offset, 0);
$function$;
