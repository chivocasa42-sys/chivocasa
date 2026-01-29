-- Update get_listings_by_tag to support sorting
-- Run this in Supabase SQL Editor

CREATE OR REPLACE FUNCTION public.get_listings_by_tag(
  p_tag text,
  p_listing_type text DEFAULT NULL,
  p_limit integer DEFAULT 48,
  p_offset integer DEFAULT 0,
  p_sort_by text DEFAULT 'recent'  -- NEW: 'recent', 'price_asc', 'price_desc'
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
  municipio text,
  total_count bigint
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  WITH filtered AS (
    SELECT sd.*
    FROM public.scrapped_data sd
    WHERE sd.active IS TRUE
      AND sd.tags IS NOT NULL
      AND jsonb_typeof(sd.tags) = 'array'
      AND public.normalize_tag(p_tag) <> ''
      AND (p_listing_type IS NULL OR sd.listing_type = p_listing_type)

      -- Fast prefilter (uses trigram index)
      AND public.normalize_tag(sd.tags::text) LIKE '%' || public.normalize_tag(p_tag) || '%'

      -- Exact tag match (accent-insensitive) against array elements
      AND EXISTS (
        SELECT 1
        FROM jsonb_array_elements_text(sd.tags) e(elem)
        WHERE public.normalize_tag(e.elem) = public.normalize_tag(p_tag)
      )
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
    NULLIF(regexp_replace(f.specs->>'Área construida (m²)', '[^0-9.]', '', 'g'), '')::numeric AS area,

    f.location->>'municipio_detectado' AS municipio,

    COUNT(*) OVER() AS total_count
  FROM filtered f
  ORDER BY
    CASE 
      WHEN p_sort_by = 'price_asc' THEN f.price
    END ASC NULLS LAST,
    CASE 
      WHEN p_sort_by = 'price_desc' THEN f.price
    END DESC NULLS LAST,
    CASE 
      WHEN p_sort_by = 'recent' OR p_sort_by IS NULL THEN f.last_updated
    END DESC NULLS LAST,
    f.external_id DESC
  LIMIT GREATEST(p_limit, 0)
  OFFSET GREATEST(p_offset, 0);
END;
$$;

-- Test the function with price sorting:
-- SELECT * FROM get_listings_by_tag('apartamento', NULL, 10, 0, 'price_asc');
-- SELECT * FROM get_listings_by_tag('apartamento', NULL, 10, 0, 'price_desc');
-- SELECT * FROM get_listings_by_tag('apartamento', NULL, 10, 0, 'recent');
