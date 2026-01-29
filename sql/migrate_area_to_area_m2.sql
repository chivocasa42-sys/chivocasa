-- Migrate old specs format to use standardized 'area_m2' key
-- Run this in Supabase SQL Editor to fix existing data

-- First, check how many records need migration
SELECT COUNT(*) as needs_migration
FROM scrapped_data 
WHERE specs IS NOT NULL 
  AND specs->>'area_m2' IS NULL
  AND (
    specs->>'Área construida (m²)' IS NOT NULL
    OR specs->>'area' IS NOT NULL
    OR specs->>'terreno' IS NOT NULL
  );

-- Migrate 'Área construida (m²)' to 'area_m2'
UPDATE scrapped_data
SET specs = specs || jsonb_build_object('area_m2', specs->>'Área construida (m²)')
WHERE specs IS NOT NULL
  AND specs->>'area_m2' IS NULL
  AND specs->>'Área construida (m²)' IS NOT NULL;

-- Migrate 'area' to 'area_m2' (if not already set)
UPDATE scrapped_data
SET specs = specs || jsonb_build_object('area_m2', specs->>'area')
WHERE specs IS NOT NULL
  AND specs->>'area_m2' IS NULL
  AND specs->>'area' IS NOT NULL;

-- Migrate 'terreno' to 'area_m2' (if not already set)
UPDATE scrapped_data
SET specs = specs || jsonb_build_object('area_m2', specs->>'terreno')
WHERE specs IS NOT NULL
  AND specs->>'area_m2' IS NULL
  AND specs->>'terreno' IS NOT NULL;

-- Verify migration
SELECT 
  COUNT(*) FILTER (WHERE specs->>'area_m2' IS NOT NULL) as has_area_m2,
  COUNT(*) FILTER (WHERE specs->>'area_m2' IS NULL AND specs->>'Área construida (m²)' IS NOT NULL) as still_needs_migration_1,
  COUNT(*) FILTER (WHERE specs->>'area_m2' IS NULL AND specs->>'area' IS NOT NULL) as still_needs_migration_2,
  COUNT(*) FILTER (WHERE specs->>'area_m2' IS NULL AND specs->>'terreno' IS NOT NULL) as still_needs_migration_3
FROM scrapped_data
WHERE specs IS NOT NULL;
