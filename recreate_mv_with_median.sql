-- =====================================================
-- MATERIALIZED VIEW: mv_sd_depto_stats (WITH MEDIAN)
-- =====================================================
-- This recreates the materialized view to use MEDIAN instead of AVG
-- Run this in your Supabase SQL Editor

-- Drop existing view if it exists
DROP MATERIALIZED VIEW IF EXISTS mv_sd_depto_stats;

-- Create new view with median calculation
CREATE MATERIALIZED VIEW mv_sd_depto_stats AS
SELECT 
    (location->>'departamento') as departamento,
    listing_type,
    MIN(price) as min_price,
    MAX(price) as max_price,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) as median_price,
    COUNT(*) as count
FROM scrappeddata_ingest
WHERE 
    active = true 
    AND price IS NOT NULL
    AND listing_type IN ('sale', 'rent')
    AND (location->>'departamento') IS NOT NULL
    AND (location->>'departamento') != ''
GROUP BY 
    (location->>'departamento'),
    listing_type
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
