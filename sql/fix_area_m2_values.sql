-- Fix malformed area_m2 values in the database
-- Some records have "200.0 m²" instead of just "200.0"
-- Run this in Supabase SQL Editor

-- First, check how many records need fixing
SELECT COUNT(*) as needs_fixing
FROM scrapped_data 
WHERE specs IS NOT NULL 
  AND specs->>'area_m2' IS NOT NULL
  AND specs->>'area_m2' ~ '[^0-9.]';

-- View some examples of malformed values
SELECT 
    external_id,
    source,
    specs->>'area_m2' as current_value,
    regexp_replace(specs->>'area_m2', '[^0-9.]', '', 'g') as cleaned_value
FROM scrapped_data 
WHERE specs IS NOT NULL 
  AND specs->>'area_m2' IS NOT NULL
  AND specs->>'area_m2' ~ '[^0-9.]'
LIMIT 20;

-- Fix the malformed area_m2 values
-- This will strip everything except digits and decimal points
UPDATE scrapped_data
SET specs = jsonb_set(
    specs,
    '{area_m2}',
    to_jsonb(regexp_replace(specs->>'area_m2', '[^0-9.]', '', 'g'))
)
WHERE specs IS NOT NULL 
  AND specs->>'area_m2' IS NOT NULL
  AND specs->>'area_m2' ~ '[^0-9.]';

-- Verify the fix
SELECT COUNT(*) as still_malformed
FROM scrapped_data 
WHERE specs IS NOT NULL 
  AND specs->>'area_m2' IS NOT NULL
  AND specs->>'area_m2' ~ '[^0-9.]';
