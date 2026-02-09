-- =====================================================
-- FUNCTION: get_price_estimate
-- =====================================================
-- Returns median price statistics for nearby similar listings.
--
-- TWO MODES:
--   A) Coordinate mode (default) — pass lat/lng, uses scrapped_data.location
--      JSONB directly. Expanding radius: 1.5 km → 3 km → 5 km until
--      enough comps are found. No L2-L5 tables involved.
--
--   B) Hierarchy mode — pass p_loc_group2_id (colonia ID). Uses
--      listing_location_match to find comps in:
--        1. Same L2 (colonia)
--        2. Same L3 (municipality) — all sibling L2s
--        3. Same L4 (district) — all sibling L3s
--      Expands until enough comps are found.
--      lat/lng are ignored in this mode.
--
-- Optional filters: bedrooms, bathrooms, listing_type (with tolerance).
-- Returns median price, min, max, count grouped by listing_type.
--
-- Usage:
--   -- Coordinate mode: just lat/lng
--   SELECT * FROM get_price_estimate(13.70, -89.22);
--   SELECT * FROM get_price_estimate(13.70, -89.22, p_bedrooms := 3, p_listing_type := 'sale');
--
--   -- Hierarchy mode: by colonia ID
--   SELECT * FROM get_price_estimate(0, 0, p_loc_group2_id := 42);
--   SELECT * FROM get_price_estimate(0, 0, p_loc_group2_id := 42, p_bedrooms := 3);

-- Drop ALL previous signatures (type changes = new overload, not replace)
DROP FUNCTION IF EXISTS public.get_price_estimate(
  double precision, double precision, integer, numeric, text, integer, integer, double precision, double precision, double precision, integer
);
DROP FUNCTION IF EXISTS public.get_price_estimate(
  double precision, double precision, integer, numeric, text, integer, integer, double precision, double precision, double precision, integer, integer
);
DROP FUNCTION IF EXISTS public.get_price_estimate(
  numeric, numeric, integer, numeric, text, integer, integer, numeric, numeric, numeric, integer, integer
);
DROP FUNCTION IF EXISTS public.get_price_estimate(
  numeric, numeric, integer, integer, text, integer, integer, numeric, numeric, numeric, integer, integer
);

CREATE OR REPLACE FUNCTION public.get_price_estimate(
  p_latitude       numeric,
  p_longitude      numeric,
  p_bedrooms       integer          DEFAULT NULL,
  p_bathrooms      integer          DEFAULT NULL,
  p_listing_type   text             DEFAULT NULL,   -- 'sale' | 'rent' | NULL (both)
  p_bed_tolerance  integer          DEFAULT 1,      -- ±N bedrooms
  p_bath_tolerance integer          DEFAULT 1,      -- ±N bathrooms
  p_radius_1_km    numeric          DEFAULT 1.5,    -- tier 1: same colonia
  p_radius_2_km    numeric          DEFAULT 3.0,    -- tier 2: adjacent colonias
  p_radius_3_km    numeric          DEFAULT 5.0,    -- tier 3: wider area
  p_min_comps      integer          DEFAULT 5,      -- minimum comps before expanding
  p_loc_group2_id  integer          DEFAULT NULL    -- optional: use L2-L5 hierarchy mode
)
RETURNS TABLE (
  listing_type        text,
  median_price        numeric,
  min_price           numeric,
  max_price           numeric,
  comparable_count    bigint,
  search_scope        text,
  median_price_per_m2 numeric,
  sample_external_ids bigint[]
)
LANGUAGE plpgsql
STABLE
AS $$
DECLARE
  v_radius   numeric;
  v_count    bigint;
  v_cos_lat  double precision;
  v_sin_lat  double precision;
  v_rad_lng  double precision;
  v_scope    text;
  v_l3_id    integer;
  v_l4_id    integer;
BEGIN

  -- =================================================================
  -- MODE B: Hierarchy mode (L2 → L3 → L4 expansion via listing_location_match)
  -- =================================================================
  IF p_loc_group2_id IS NOT NULL THEN

    -- Look up parent L3 and L4 for this L2
    SELECT g2.parent_loc_group INTO v_l3_id
    FROM sv_loc_group2 g2 WHERE g2.id = p_loc_group2_id;

    IF v_l3_id IS NOT NULL THEN
      SELECT g3.parent_loc_group INTO v_l4_id
      FROM sv_loc_group3 g3 WHERE g3.id = v_l3_id;
    END IF;

    -- Tier 1: same L2 (colonia)
    SELECT count(*) INTO v_count
    FROM scrapped_data sd
    INNER JOIN listing_location_match llm ON sd.external_id = llm.external_id
    WHERE sd.active IS TRUE AND sd.price IS NOT NULL AND sd.price > 0
      AND llm.loc_group2_id = p_loc_group2_id
      AND (p_listing_type IS NULL OR sd.listing_type = p_listing_type)
      AND (p_bedrooms IS NULL OR (
        sd.specs->>'bedrooms' IS NOT NULL
        AND NULLIF(regexp_replace(sd.specs->>'bedrooms', '[^0-9]', '', 'g'), '')::int
            BETWEEN (p_bedrooms - p_bed_tolerance) AND (p_bedrooms + p_bed_tolerance)
      ))
      AND (p_bathrooms IS NULL OR (
        sd.specs->>'bathrooms' IS NOT NULL
        AND NULLIF(regexp_replace(sd.specs->>'bathrooms', '[^0-9.]', '', 'g'), '')::numeric
            BETWEEN (p_bathrooms - p_bath_tolerance) AND (p_bathrooms + p_bath_tolerance)
      ));

    IF v_count >= p_min_comps THEN
      v_scope := 'L2 (same colonia)';
      RETURN QUERY
      SELECT * FROM _price_estimate_by_hierarchy(
        p_loc_group2_id, NULL, NULL,
        p_listing_type, p_bedrooms, p_bed_tolerance, p_bathrooms, p_bath_tolerance,
        v_scope
      );
      RETURN;
    END IF;

    -- Tier 2: same L3 (municipality — all sibling L2s)
    IF v_l3_id IS NOT NULL THEN
      SELECT count(*) INTO v_count
      FROM scrapped_data sd
      INNER JOIN listing_location_match llm ON sd.external_id = llm.external_id
      WHERE sd.active IS TRUE AND sd.price IS NOT NULL AND sd.price > 0
        AND llm.loc_group3_id = v_l3_id
        AND (p_listing_type IS NULL OR sd.listing_type = p_listing_type)
        AND (p_bedrooms IS NULL OR (
          sd.specs->>'bedrooms' IS NOT NULL
          AND NULLIF(regexp_replace(sd.specs->>'bedrooms', '[^0-9]', '', 'g'), '')::int
              BETWEEN (p_bedrooms - p_bed_tolerance) AND (p_bedrooms + p_bed_tolerance)
        ))
        AND (p_bathrooms IS NULL OR (
          sd.specs->>'bathrooms' IS NOT NULL
          AND NULLIF(regexp_replace(sd.specs->>'bathrooms', '[^0-9.]', '', 'g'), '')::numeric
              BETWEEN (p_bathrooms - p_bath_tolerance) AND (p_bathrooms + p_bath_tolerance)
        ));

      IF v_count >= p_min_comps THEN
        v_scope := 'L3 (same municipality)';
        RETURN QUERY
        SELECT * FROM _price_estimate_by_hierarchy(
          NULL, v_l3_id, NULL,
          p_listing_type, p_bedrooms, p_bed_tolerance, p_bathrooms, p_bath_tolerance,
          v_scope
        );
        RETURN;
      END IF;
    END IF;

    -- Tier 3: same L4 (district — all sibling L3s)
    IF v_l4_id IS NOT NULL THEN
      v_scope := 'L4 (same district)';
      RETURN QUERY
      SELECT * FROM _price_estimate_by_hierarchy(
        NULL, NULL, v_l4_id,
        p_listing_type, p_bedrooms, p_bed_tolerance, p_bathrooms, p_bath_tolerance,
        v_scope
      );
      RETURN;
    END IF;

    -- Fallback: return whatever we have at L3 level even if < min_comps
    v_scope := 'L3 (same municipality, < min_comps)';
    RETURN QUERY
    SELECT * FROM _price_estimate_by_hierarchy(
      NULL, v_l3_id, NULL,
      p_listing_type, p_bedrooms, p_bed_tolerance, p_bathrooms, p_bath_tolerance,
      v_scope
    );
    RETURN;
  END IF;

  -- =================================================================
  -- MODE A: Coordinate mode (expanding radius from scrapped_data.location)
  -- =================================================================
  v_cos_lat := cos(radians(p_latitude));
  v_sin_lat := sin(radians(p_latitude));
  v_rad_lng := radians(p_longitude);

  -- Try expanding radii until we get enough comparables
  FOREACH v_radius IN ARRAY ARRAY[p_radius_1_km, p_radius_2_km, p_radius_3_km]
  LOOP
    SELECT count(*) INTO v_count
    FROM public.scrapped_data sd
    WHERE sd.active IS TRUE
      AND sd.price IS NOT NULL
      AND sd.price > 0
      AND sd.location IS NOT NULL
      AND NULLIF(sd.location->>'latitude', 'null') IS NOT NULL
      AND NULLIF(sd.location->>'longitude', 'null') IS NOT NULL
      AND (p_listing_type IS NULL OR sd.listing_type = p_listing_type)
      AND (
        6371.0 * acos(
          LEAST(1.0, GREATEST(-1.0,
            v_cos_lat
            * cos(radians((sd.location->>'latitude')::double precision))
            * cos(radians((sd.location->>'longitude')::double precision) - v_rad_lng)
            + v_sin_lat
            * sin(radians((sd.location->>'latitude')::double precision))
          ))
        )
      ) <= v_radius
      AND (
        p_bedrooms IS NULL
        OR (
          sd.specs->>'bedrooms' IS NOT NULL
          AND NULLIF(regexp_replace(sd.specs->>'bedrooms', '[^0-9]', '', 'g'), '')::int
              BETWEEN (p_bedrooms - p_bed_tolerance) AND (p_bedrooms + p_bed_tolerance)
        )
      )
      AND (
        p_bathrooms IS NULL
        OR (
          sd.specs->>'bathrooms' IS NOT NULL
          AND NULLIF(regexp_replace(sd.specs->>'bathrooms', '[^0-9.]', '', 'g'), '')::numeric
              BETWEEN (p_bathrooms - p_bath_tolerance) AND (p_bathrooms + p_bath_tolerance)
        )
      );

    IF v_count >= p_min_comps THEN
      EXIT;
    END IF;
  END LOOP;

  v_scope := v_radius || ' km radius';

  RETURN QUERY
  WITH nearby AS (
    SELECT
      sd.external_id,
      sd.price,
      sd.listing_type AS lt,
      NULLIF(regexp_replace(COALESCE(sd.specs->>'area_m2', ''), '[^0-9.]', '', 'g'), '')::numeric AS area_m2,
      6371.0 * acos(
        LEAST(1.0, GREATEST(-1.0,
          v_cos_lat
          * cos(radians((sd.location->>'latitude')::double precision))
          * cos(radians((sd.location->>'longitude')::double precision) - v_rad_lng)
          + v_sin_lat
          * sin(radians((sd.location->>'latitude')::double precision))
        ))
      ) AS distance_km
    FROM public.scrapped_data sd
    WHERE sd.active IS TRUE
      AND sd.price IS NOT NULL
      AND sd.price > 0
      AND sd.location IS NOT NULL
      AND NULLIF(sd.location->>'latitude', 'null') IS NOT NULL
      AND NULLIF(sd.location->>'longitude', 'null') IS NOT NULL
      AND (p_listing_type IS NULL OR sd.listing_type = p_listing_type)
      AND (
        6371.0 * acos(
          LEAST(1.0, GREATEST(-1.0,
            v_cos_lat
            * cos(radians((sd.location->>'latitude')::double precision))
            * cos(radians((sd.location->>'longitude')::double precision) - v_rad_lng)
            + v_sin_lat
            * sin(radians((sd.location->>'latitude')::double precision))
          ))
        )
      ) <= v_radius
      AND (
        p_bedrooms IS NULL
        OR (
          sd.specs->>'bedrooms' IS NOT NULL
          AND NULLIF(regexp_replace(sd.specs->>'bedrooms', '[^0-9]', '', 'g'), '')::int
              BETWEEN (p_bedrooms - p_bed_tolerance) AND (p_bedrooms + p_bed_tolerance)
        )
      )
      AND (
        p_bathrooms IS NULL
        OR (
          sd.specs->>'bathrooms' IS NOT NULL
          AND NULLIF(regexp_replace(sd.specs->>'bathrooms', '[^0-9.]', '', 'g'), '')::numeric
              BETWEEN (p_bathrooms - p_bath_tolerance) AND (p_bathrooms + p_bath_tolerance)
        )
      )
  )
  SELECT
    n.lt                                                       AS listing_type,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY n.price)::numeric, 2) AS median_price,
    min(n.price)::numeric                                      AS min_price,
    max(n.price)::numeric                                      AS max_price,
    count(*)                                                   AS comparable_count,
    v_scope                                                    AS search_scope,
    round(
      percentile_cont(0.5) WITHIN GROUP (
        ORDER BY CASE WHEN n.area_m2 IS NOT NULL AND n.area_m2 > 0
                      THEN n.price / n.area_m2
                      ELSE NULL
                 END
      )::numeric, 2
    )                                                          AS median_price_per_m2,
    (array_agg(n.external_id ORDER BY n.distance_km))[1:5]     AS sample_external_ids
  FROM nearby n
  GROUP BY n.lt
  ORDER BY n.lt;
END;
$$;


-- =====================================================
-- HELPER: _price_estimate_by_hierarchy (internal)
-- =====================================================
-- Aggregates price stats for listings matched to a given L2, L3, or L4.
-- Exactly one of the three ID params should be non-null.
DROP FUNCTION IF EXISTS public._price_estimate_by_hierarchy(
  integer, integer, integer, text, integer, integer, numeric, integer, text
);
DROP FUNCTION IF EXISTS public._price_estimate_by_hierarchy(
  integer, integer, integer, text, integer, integer, integer, integer, text
);

CREATE OR REPLACE FUNCTION public._price_estimate_by_hierarchy(
  p_l2_id          integer,
  p_l3_id          integer,
  p_l4_id          integer,
  p_listing_type   text,
  p_bedrooms       integer,
  p_bed_tolerance  integer,
  p_bathrooms      integer,
  p_bath_tolerance integer,
  p_scope          text
)
RETURNS TABLE (
  listing_type        text,
  median_price        numeric,
  min_price           numeric,
  max_price           numeric,
  comparable_count    bigint,
  search_scope        text,
  median_price_per_m2 numeric,
  sample_external_ids bigint[]
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
  RETURN QUERY
  WITH comps AS (
    SELECT
      sd.external_id,
      sd.price,
      sd.listing_type AS lt,
      NULLIF(regexp_replace(COALESCE(sd.specs->>'area_m2', ''), '[^0-9.]', '', 'g'), '')::numeric AS area_m2
    FROM scrapped_data sd
    INNER JOIN listing_location_match llm ON sd.external_id = llm.external_id
    WHERE sd.active IS TRUE
      AND sd.price IS NOT NULL
      AND sd.price > 0
      AND (p_listing_type IS NULL OR sd.listing_type = p_listing_type)
      -- Hierarchy filter: exactly one of L2/L3/L4 is set
      AND (p_l2_id IS NULL OR llm.loc_group2_id = p_l2_id)
      AND (p_l3_id IS NULL OR llm.loc_group3_id = p_l3_id)
      AND (p_l4_id IS NULL OR llm.loc_group4_id = p_l4_id)
      AND (p_bedrooms IS NULL OR (
        sd.specs->>'bedrooms' IS NOT NULL
        AND NULLIF(regexp_replace(sd.specs->>'bedrooms', '[^0-9]', '', 'g'), '')::int
            BETWEEN (p_bedrooms - p_bed_tolerance) AND (p_bedrooms + p_bed_tolerance)
      ))
      AND (p_bathrooms IS NULL OR (
        sd.specs->>'bathrooms' IS NOT NULL
        AND NULLIF(regexp_replace(sd.specs->>'bathrooms', '[^0-9.]', '', 'g'), '')::numeric
            BETWEEN (p_bathrooms - p_bath_tolerance) AND (p_bathrooms + p_bath_tolerance)
      ))
  )
  SELECT
    c.lt                                                       AS listing_type,
    round(percentile_cont(0.5) WITHIN GROUP (ORDER BY c.price)::numeric, 2) AS median_price,
    min(c.price)::numeric                                      AS min_price,
    max(c.price)::numeric                                      AS max_price,
    count(*)                                                   AS comparable_count,
    p_scope                                                    AS search_scope,
    round(
      percentile_cont(0.5) WITHIN GROUP (
        ORDER BY CASE WHEN c.area_m2 IS NOT NULL AND c.area_m2 > 0
                      THEN c.price / c.area_m2
                      ELSE NULL
                 END
      )::numeric, 2
    )                                                          AS median_price_per_m2,
    (array_agg(c.external_id))[1:5]                            AS sample_external_ids
  FROM comps c
  GROUP BY c.lt
  ORDER BY c.lt;
END;
$$;


-- Grant access
GRANT EXECUTE ON FUNCTION public.get_price_estimate(
  numeric, numeric, integer, integer, text, integer, integer,
  numeric, numeric, numeric, integer, integer
) TO anon;
GRANT EXECUTE ON FUNCTION public.get_price_estimate(
  numeric, numeric, integer, integer, text, integer, integer,
  numeric, numeric, numeric, integer, integer
) TO authenticated;

-- =====================================================
-- EXAMPLES
-- =====================================================
--
-- === Coordinate mode (default, no L2-L5 involved) ===
--
-- 1. Basic price estimate for a location in San Salvador (Colonia Escalón area):
--    SELECT * FROM get_price_estimate(13.708, -89.245);
--
-- 2. 3-bedroom house sale estimate near Santa Tecla:
--    SELECT * FROM get_price_estimate(13.677, -89.297, p_bedrooms := 3, p_listing_type := 'sale');
--
-- 3. Rent estimate for 2-bed/1-bath in Soyapango area:
--    SELECT * FROM get_price_estimate(13.722, -89.136, p_bedrooms := 2, p_bathrooms := 1, p_listing_type := 'rent');
--
-- 4. Wider search with custom radius:
--    SELECT * FROM get_price_estimate(13.70, -89.22, p_radius_1_km := 2.0, p_radius_2_km := 5.0, p_radius_3_km := 10.0);
--
-- 5. Strict match (exact bedrooms, no tolerance):
--    SELECT * FROM get_price_estimate(13.70, -89.22, p_bedrooms := 3, p_bed_tolerance := 0);
--
-- === Hierarchy mode (uses L2-L5 via listing_location_match) ===
--
-- 6. Price estimate for a specific colonia (L2 ID = 42):
--    SELECT * FROM get_price_estimate(0, 0, p_loc_group2_id := 42);
--
-- 7. Same colonia, filtered to 3-bed sales:
--    SELECT * FROM get_price_estimate(0, 0, p_loc_group2_id := 42, p_bedrooms := 3, p_listing_type := 'sale');
