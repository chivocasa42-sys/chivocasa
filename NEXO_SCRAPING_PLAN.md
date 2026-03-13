# Nexo Scraping Plan

Observed on March 13, 2026.

## Goal

Add `https://nexo.com.sv/` as a new source in the existing multi-source pipeline in `scraper_encuentra24.py`, using the current insert, location-match, and validation flow already used by the other sources.

## Site Recon

Public listing categories currently exposed:

- `https://nexo.com.sv/casas-en-venta-el-salvador/1`
- `https://nexo.com.sv/casas-en-alquiler-el-salvador/1`
- `https://nexo.com.sv/apartamentos-en-venta-el-salvador/1`
- `https://nexo.com.sv/apartamentos-en-alquiler-el-salvador/1`
- `https://nexo.com.sv/terrenos-en-venta-el-salvador/1`

Public counts seen on March 13, 2026:

- Houses for sale: 37 listings / 4 pages
- Houses for rent: 16 listings / 2 pages
- Apartments for sale: 4 listings / 1 page
- Apartments for rent: 10 listings / 1 page
- Land for sale: 9 listings / 1 page
- Total visible inventory: 76 listings

Important site characteristics:

- `robots.txt` does not block the public listing categories or detail pages.
- `sitemap.xml` lists the category entry pages, but not the individual property detail URLs.
- The site is server-rendered HTML. A browser automation stack is not needed for v1.
- Detail pages expose useful schema.org fields inline in the HTML.
- Pages declare `charset=iso-8859-1`. The scraper should set response encoding explicitly before parsing.
- Category pages beyond the real last page return HTTP 200 with `Existen 0 ... disponibles`, not a 404.
- Invalid detail URLs can return a ColdFusion error page instead of a clean 404. Validation for this source should not rely on 404 alone.
- I did not find usable latitude/longitude on the detail pages tested.
- I did not find a reliable published date on the detail pages tested.

## Recommended Scope

V1 should scrape only the five public categories above.

Do not add zone-filter crawling in v1. The zone filter is implemented through form options and is not needed for completeness because the paginated category pages already enumerate the live listings.

## Data Shape

The current insert path expects these core fields:

- `external_id`
- `title`
- `price`
- `listing_type`
- `url`
- `specs`
- `details`
- `description`
- `images`
- `source`
- `active`
- `last_updated`
- optional location fields for downstream matching: `municipio_detectado`, `departamento`, `latitude`, `longitude`

For Nexo, the field mapping should be:

| Output field | Nexo source |
| --- | --- |
| `title` | `article.titulo h1 span[itemprop="name"]` |
| `description` | `article.descripcion span[itemprop="description"]` |
| `price` | `itemprop="price"` block in the characteristics section |
| `url` | absolute detail URL |
| `listing_type` | category default, then pass through `correct_listing_type(...)` |
| `images` | main image plus gallery anchors inside `.gallery a[href]` |
| `source` | `"Nexo"` |
| `details` | `<li>` rows from the two details blocks under `.caracteristicas` |
| `specs.bedrooms` | `.cuarto2` or list-card fallback |
| `specs.bathrooms` | `.bano2` or list-card fallback |
| `specs.parking` | `.cochera2` or list-card fallback |
| `specs.floors` / `specs.level` | `.piso2` or apartment level row |
| `specs.area_lot` | `Tamano del Terreno` row |
| `specs.area_built` | `Tamano construccion` / `Area del apartamento` row |
| `location.departamento` | `itemprop="addressRegion"` |
| `location.municipio` | `itemprop="addressLocality"` |
| `location.zona` | `itemprop="streetAddress"` |
| `contact_info` | optional phase 2 from the agent block |

Notes:

- Run Nexo area values through `normalize_listing_specs(...)` after extracting raw labels.
- Run `detect_municipio(location, description, title)` to populate `municipio_detectado` and normalized `departamento`.
- Keep `latitude` and `longitude` as `None` unless a later pass finds a stable coordinate source.
- Keep `published_date` as `None` in v1. Nexo does not expose a reliable date on the tested pages.

## External ID Strategy

Do not use the raw numeric listing ID directly.

Reason:

- Nexo detail URLs contain small IDs like `510`, `64`, `42`.
- Those IDs are category-scoped and are not safe as a globally unique bigint across all sources.

Recommended approach:

- Build a deterministic source-specific key using the stable product code when present, for example:
  - `rv-1-510`
  - `ra-2-287`
  - `av-3-64`
  - `aa-4-111`
  - `tv-6-42`
- Convert that key to a numeric bigint using the same hashed approach already used for MiCasaSV slug IDs:
  - `slug_to_external_id(f"nexo:{product_code}")`

Fallback:

- If `cod_inmueble` / `productID` is missing, hash `nexo:{cod_tipo_inmueble}:{id_inmueble}:{path}`.

## Implementation Plan

### 1. Add source wiring

Update `scraper_encuentra24.py` to recognize a new source named `Nexo`.

Changes:

- Add `--Nexo` CLI flag.
- Add `"Nexo"` to:
  - default source list in normal mode
  - `all_sources` in `run_update_mode(...)`
  - `all_source_names` in `validate_all_active_listings(...)`
  - `active_sources` in `main(...)`

### 2. Define category config

Add a small source config, for example:

```python
NEXO_CATEGORIES = [
    {"url": "https://nexo.com.sv/casas-en-venta-el-salvador/{}", "listing_type": "sale", "property_type": "house", "type_code": "1"},
    {"url": "https://nexo.com.sv/casas-en-alquiler-el-salvador/{}", "listing_type": "rent", "property_type": "house", "type_code": "2"},
    {"url": "https://nexo.com.sv/apartamentos-en-venta-el-salvador/{}", "listing_type": "sale", "property_type": "apartment", "type_code": "3"},
    {"url": "https://nexo.com.sv/apartamentos-en-alquiler-el-salvador/{}", "listing_type": "rent", "property_type": "apartment", "type_code": "4"},
    {"url": "https://nexo.com.sv/terrenos-en-venta-el-salvador/{}", "listing_type": "sale", "property_type": "land", "type_code": "6"},
]
```

### 3. Build list-page collector

Add `get_nexo_listing_urls(max_listings=None)`.

Behavior:

- Iterate page numbers from `1` upward for each category.
- Parse all `VER DETALLES` links.
- Convert relative links to absolute URLs.
- Stop the category crawl when one of these is true:
  - page has zero detail links
  - page says `Existen 0`
  - page number is greater than the highest visible pagination number and yields no new URLs
- Deduplicate URLs across categories while preserving order.

Do not use aggressive concurrency here. One request at a time per category is enough.

### 4. Build detail parser

Add `scrape_nexo_listing(url, listing_type="auto")`.

Parsing rules:

- Fetch with the shared browser-like headers already used by the scraper.
- Set `resp.encoding = "iso-8859-1"` before `BeautifulSoup(...)`.
- Reject non-live/error pages when:
  - status is 404 or 410
  - visible text contains `Error Occurred While Processing Request`
  - visible text contains `The web site you are accessing has experienced an unexpected error`
  - expected title block is missing
- Extract:
  - title
  - description
  - price
  - `productID` / hidden form IDs
  - departamento / municipio / zona
  - bedrooms / bathrooms / parking / floors
  - detail rows and gallery images
  - optional agent name / phone / whatsapp from the sidebar
- Normalize:
  - `listing_type = correct_listing_type(...)`
  - `specs = normalize_listing_specs(specs)`
  - `municipio_info = detect_municipio(location, description, title)`

### 5. Build concurrent detail scrape

Add `scrape_nexo_listings_concurrent(urls, listing_type="auto", max_workers=4)`.

Recommendation:

- Start with `max_workers=4`.
- Nexo only has about 76 visible listings, so higher concurrency is unnecessary.

### 6. Add source orchestrator

Add `main_nexo(limit=None, max_days=None)`.

Behavior:

- Collect all URLs from the five public categories.
- Apply `limit` after URL collection.
- Ignore `max_days` in v1 because Nexo does not expose a trustworthy publish date.
- Split results into sale vs rent from the parsed records.
- Return `(all_listings, sale_data, rent_data)` to match the existing source interface.

### 7. Add update-mode support

In `run_update_mode(...)`, add a `source == "Nexo"` branch that:

- pulls all active Nexo URLs from DB
- re-scrapes them with `scrape_nexo_listings_concurrent(...)`
- reuses the existing batch upsert path

### 8. Add validation rules for Nexo

Extend `check_listing_still_active(url, source)` for `source == "Nexo"`.

Treat these as inactive:

- 404 / 410
- a page with zero title block and zero characteristics block
- ColdFusion error pages
- pages that visibly render `Error Occurred While Processing Request`

Do not deactivate on:

- 403
- generic 5xx without a recognizable inactive/error page body
- timeouts / transient network errors

## Parsing Notes by Property Type

Houses:

- usually expose `Tamano del Terreno`, `Tamano construccion`, `Distribucion`, `Tipo de ubicacion`, `Tipo de Acabados`, `Detalles de la residencial`

Apartments:

- usually expose `Area del apartamento`, `Distribucion`, `Tipo de ubicacion`, `Tipo de Acabados`, `Detalles del Condominio`
- can expose an apartment level row instead of floors

Land:

- usually exposes lot area only
- often includes `Topografia`, `Apto para`, `Tipo de Acceso`, `Servicios basicos`, `Otros detalles`

The parser should not assume a fixed detail label set. It should preserve unknown labels in `details`.

## Phase Split

### Phase 1

- source wiring
- category crawl
- detail parsing
- insert/upsert
- update mode
- Nexo-specific validation

### Phase 2

- persist `contact_info` only if the DB and insert path support it
- investigate whether Nexo exposes coordinates or a stable geocoding hint
- add optional zone-filter crawl only if category pagination proves incomplete

## Acceptance Criteria

- `python scraper_encuentra24.py --Nexo --limit 5 --skip-validation` returns parsed Nexo records without crashes
- records insert through the existing batch upsert path
- `source == "Nexo"` rows appear in `scrappeddata_ingest`
- `match_scraped_listings(...)` runs without schema changes
- `python scraper_encuentra24.py --update --Nexo --limit 5 --skip-validation` re-scrapes active Nexo URLs
- validation does not falsely keep ColdFusion error pages active
- no `external_id` collisions with existing sources

## Test Checklist

Smoke-test these real pages:

- House sale: `https://nexo.com.sv/1/510/Colonia-Universitaria-Norte-casa-en-venta-1-planta-3-habitaciones`
- Apartment sale: `https://nexo.com.sv/3/64/Colonia-Escal%C3%B3n-parte-alta-apartamento-en-venta-2-habitaciones`
- Land sale: `https://nexo.com.sv/6/42/Terreno-en-venta-en-la-Hacienda-2800-vrs-Plano`
- House sale index: `https://nexo.com.sv/casas-en-venta-el-salvador/1`
- Sitemap seed: `https://nexo.com.sv/sitemap.xml`
- Robots check: `https://nexo.com.sv/robots.txt`

Regression checks:

- no breakage in existing CLI defaults
- no breakage in `run_update_mode(...)`
- no breakage in `validate_all_active_listings(...)`

## Recommendation

Implement Nexo inside the existing monolith first, not as a separate script.

Reason:

- the repo already centralizes insert, update, validation, type-correction, area normalization, and location matching in `scraper_encuentra24.py`
- Nexo is a small, static HTML source
- the lowest-risk path is to add one more source adapter that conforms to the existing interface
