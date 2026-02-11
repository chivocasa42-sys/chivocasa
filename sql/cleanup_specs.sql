-- =====================================================
-- MIGRATION: Clean up noisy specs in scrapped_data
-- =====================================================
-- Normalizes specs JSONB to contain ONLY these 4 keys:
--   area_m2, bedrooms, bathrooms, parking
--
-- Handles legacy key aliases:
--   bedrooms:   habitaciones, recamaras, dormitorios, hab
--   bathrooms:  baños, banos, baths
--   parking:    parqueo, parqueos, estacionamientos, cocheras, garaje
--   area_m2:    area, terreno, construcción, Área construida (m²), etc.
--
-- Run this ONCE to clean existing data. New scrapes already produce clean output.
-- =====================================================

-- Preview first (dry run) - uncomment to check before applying:
-- SELECT
--   external_id,
--   specs AS old_specs,
--   jsonb_strip_nulls(jsonb_build_object(
--     'area_m2',   COALESCE(specs->>'area_m2', NULL),
--     'bedrooms',  COALESCE(specs->>'bedrooms',
--                    regexp_replace(COALESCE(specs->>'habitaciones', specs->>'recamaras', specs->>'dormitorios', specs->>'hab'), '[^0-9.]', '', 'g')),
--     'bathrooms', COALESCE(specs->>'bathrooms',
--                    regexp_replace(COALESCE(specs->>'baños', specs->>'banos', specs->>'baths'), '[^0-9.]', '', 'g')),
--     'parking',   COALESCE(specs->>'parking',
--                    regexp_replace(COALESCE(specs->>'parqueo', specs->>'parqueos', specs->>'estacionamientos', specs->>'cocheras', specs->>'garaje'), '[^0-9.]', '', 'g'))
--   )) AS new_specs
-- FROM scrapped_data
-- WHERE specs IS NOT NULL
--   AND specs != '{}'::jsonb
-- LIMIT 20;

-- =========================
-- APPLY THE CLEANUP
-- =========================
UPDATE scrapped_data
SET specs = jsonb_strip_nulls(jsonb_build_object(
  'area_m2',
    COALESCE(
      -- Prefer existing area_m2 (already normalized)
      NULLIF(specs->>'area_m2', ''),
      -- Fallback: extract numeric from raw area keys (e.g. "200.0 m²" → "200.0")
      NULLIF(regexp_replace(
        COALESCE(
          specs->>'area',
          specs->>'Área construida (m²)',
          specs->>'Área de construcción',
          specs->>'Área de terreno',
          specs->>'construcción',
          specs->>'terreno'
        ),
        '[^0-9.]', '', 'g'
      ), ''),
      NULL
    ),
  'bedrooms',
    COALESCE(
      NULLIF(regexp_replace(COALESCE(specs->>'bedrooms', specs->>'habitaciones', specs->>'recamaras', specs->>'dormitorios', specs->>'hab'), '[^0-9.]', '', 'g'), ''),
      NULL
    ),
  'bathrooms',
    COALESCE(
      NULLIF(regexp_replace(COALESCE(specs->>'bathrooms', specs->>'baños', specs->>'banos', specs->>'baths'), '[^0-9.]', '', 'g'), ''),
      NULL
    ),
  'parking',
    COALESCE(
      NULLIF(regexp_replace(COALESCE(specs->>'parking', specs->>'parqueo', specs->>'parqueos', specs->>'estacionamientos', specs->>'cocheras', specs->>'garaje'), '[^0-9.]', '', 'g'), ''),
      NULL
    )
))
WHERE specs IS NOT NULL
  AND specs != '{}'::jsonb;
