-- =====================================================
-- SQL UPDATE FOR BEST OPPORTUNITY IMAGES
-- =====================================================
-- This function needs to be updated in Supabase to include first_image

-- UPDATE the get_top_scored_listings function to return first_image
-- Add this to your existing function's SELECT statement:

/*
Add to the SELECT clause in get_top_scored_listings:

  CASE
    WHEN sd.images IS NULL THEN NULL
    WHEN jsonb_typeof(sd.images->0) = 'object' THEN sd.images->0->>'url'
    ELSE sd.images->>0
  END AS first_image,

This should be added after the 'url' field and before the closing FROM clause.
The function should now return first_image as part of the result set.

Example placement in the function:
SELECT
  sd.external_id,
  sd.title,
  sd.location,
  sd.location->>'departamento_detectado' AS departamento,
  sd.listing_type,
  sd.price::numeric,
  ...other fields...
  sd.url,
  CASE
    WHEN sd.images IS NULL THEN NULL
    WHEN jsonb_typeof(sd.images->0) = 'object' THEN sd.images->0->>'url'
    ELSE sd.images->>0
  END AS first_image,
  ...
FROM scrapped_data sd
...
*/

-- Alternatively, if you have full access to recreate the function, 
-- please provide the full function SQL and I can update it for you.
