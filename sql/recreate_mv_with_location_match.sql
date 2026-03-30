-- =====================================================
-- MATERIALIZED VIEW: mv_sd_depto_stats (USING LOCATION MATCH)
-- =====================================================
-- This recreates the materialized view to use the location_match join
-- instead of the location JSON field. This provides more accurate
-- department data based on the improved matching algorithm.
-- It only includes residential listings tagged as Casa or Apartamento.
-- It also creates the source indexes that help the MV refresh faster.
-- Run this in your Supabase SQL Editor

-- Supporting indexes for the MV source query
CREATE INDEX IF NOT EXISTS idx_scrapped_data_tags_gin
    ON public.scrapped_data USING GIN (tags);

CREATE INDEX IF NOT EXISTS idx_listing_location_match_external_id
    ON public.listing_location_match(external_id);

-- Drop existing view if it exists
DROP MATERIALIZED VIEW IF EXISTS mv_sd_depto_stats;

-- Create new view joining with location match and sv_loc_group5
CREATE MATERIALIZED VIEW mv_sd_depto_stats AS
SELECT 
    g5.loc_name as departamento,
    sd.listing_type,
    MIN(sd.price) as min_price,
    MAX(sd.price) as max_price,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY sd.price) as avg_price,  -- Keep column name for backwards compatibility
    COUNT(*) as count
FROM scrapped_data sd
INNER JOIN listing_location_match llm ON sd.external_id = llm.external_id
INNER JOIN sv_loc_group5 g5 ON llm.loc_group5_id = g5.id
WHERE 
    sd.active = true
    AND sd.price IS NOT NULL
    AND sd.listing_type IN ('sale', 'rent')
    AND llm.loc_group5_id IS NOT NULL
    AND COALESCE(sd.tags, '[]'::jsonb) ?| ARRAY['Casa', 'Apartamento']
GROUP BY 
    g5.loc_name,
    sd.listing_type
ORDER BY count DESC;

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_mv_sd_depto_stats_departamento 
    ON mv_sd_depto_stats(departamento);

-- =====================================================
-- RPC FUNCTION: refresh_mv_sd_depto_stats
-- =====================================================
-- This function refreshes the materialized view
-- Called by the scraper after inserting new data

CREATE OR REPLACE FUNCTION refresh_mv_sd_depto_stats()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW mv_sd_depto_stats;
END;
$$;

-- =====================================================
-- USAGE
-- =====================================================
-- Manually refresh the view:
-- SELECT refresh_mv_sd_depto_stats();

-- Query the view:
-- SELECT * FROM mv_sd_depto_stats ORDER BY count DESC;
