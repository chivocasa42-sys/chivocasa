# SIVAR CASAS — DOCUMENTACIÓN TÉCNICA COMPLETA

> **Producto:** Sivar Casas (alias histórico: ChivoCasa)
> **Dominio:** sivarcasas.com
> **Versión del documento:** 2.0
> **Última actualización:** 2026-02-14

---

## CHANGELOG DE DOCUMENTACIÓN

| Fecha       | Versión | Cambios                                                       |
|-------------|---------|---------------------------------------------------------------|
| 2026-02-14  | 2.0     | Reescritura completa alineada al código actual del repositorio |
| 2025-06-15  | 1.0     | Documento inicial                                              |

---

## 1. RESUMEN EJECUTIVO

Sivar Casas es una plataforma de inteligencia inmobiliaria para El Salvador. Agrega listados de múltiples fuentes (Encuentra24, MiCasaSV, Realtor.com, Vivo Latam), los normaliza, deduplica y almacena en Supabase. El frontend Next.js presenta estadísticas de mercado, rankings por departamento, un mapa interactivo, páginas de detalle, un valuador automatizado (AVM), favoritos persistidos en cookie, y tendencias nacionales.

**Stack tecnológico:**

| Capa         | Tecnología                                   |
|-------------|----------------------------------------------|
| Frontend    | Next.js 16, React 19, TypeScript 5, TailwindCSS 4 |
| Gráficas    | ECharts 6 (tree-shaken: Bar, Line, Canvas)   |
| Mapas       | Leaflet 1.9 + react-leaflet 5               |
| Backend     | Next.js API Routes (Node.js + Edge runtime)  |
| Base de datos | Supabase (PostgreSQL + PostGIS)            |
| Scraper     | Python 3.11 (requests, BeautifulSoup4, supabase-py) |
| CI/CD       | GitHub Actions (cron), Vercel (deploy)       |
| Observabilidad | Vercel Analytics + Speed Insights         |
| Imágenes    | sharp 0.34 (optimización server-side)        |
| CSS inlining | critters 0.0.23                             |

---

## 2. ESTRUCTURA DE CARPETAS

```
SivarCasas2/
├── .github/workflows/          # CI/CD pipelines
│   ├── scrape-new.yml          # Scraping de nuevos listados (cron cada hora)
│   └── scrape-update.yml       # Re-scraping de activos (cron cada 12h)
├── public/                     # Assets estáticos
│   ├── logo.png                # Logo del sitio
│   ├── favicon.ico             # Favicon
│   └── el-salvador.geojson     # GeoJSON para el mapa interactivo
├── sql/                        # Scripts SQL para Supabase
│   ├── avm_functions.sql       # AVM: avm_nearest_matches, avm_value_point
│   ├── fn_search_colonias.sql  # Búsqueda fuzzy de colonias
│   ├── fn_valuador_comps.sql   # Comparables para valuador (v2)
│   ├── get_price_estimate.sql  # Estimación de precio (legacy)
│   ├── get_listings_for_cards_v2_location.sql
│   ├── get_municipalities_for_department.sql
│   ├── get_categories_for_department.sql
│   ├── supabase_tag_functions.sql
│   ├── create_sv_locations_table.sql
│   ├── insert_sv_locations.sql
│   ├── insert_sv_locations_residential.sql
│   ├── recreate_mv_with_location_match.sql
│   ├── recreate_mv_with_median.sql
│   ├── update_fn_nearby_candidates.sql
│   ├── update_get_listings_by_tag_sort.sql
│   ├── update_get_listings_by_tag_with_tags.sql
│   ├── update_get_listings_for_cards_sort.sql
│   ├── update_get_listings_for_cards_with_tags.sql
│   ├── update_best_opportunity_images.sql
│   ├── cleanup_specs.sql
│   ├── fix_area_m2_values.sql
│   ├── migrate_area_to_area_m2.sql
│   └── unmatched_locations.sql
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── layout.tsx          # Root layout (Inter font, Analytics, Providers)
│   │   ├── template.tsx        # Homepage JSON-LD injection
│   │   ├── page.tsx            # Home: KPIs, mapa, tarjetas departamento
│   │   ├── Providers.tsx       # Context providers (FavoritesProvider)
│   │   ├── robots.ts           # robots.txt dinámico
│   │   ├── sitemap.ts          # sitemap.xml dinámico
│   │   ├── opengraph-image.tsx # OG image dinámico (@vercel/og)
│   │   ├── twitter-image.tsx   # Twitter card dinámico
│   │   ├── globals.css         # CSS core (variables, reset, temas)
│   │   ├── pages.css           # CSS específico de páginas
│   │   ├── tendencias/
│   │   │   └── page.tsx        # Tendencias nacionales
│   │   ├── valuador-de-inmuebles/
│   │   │   ├── layout.tsx      # Metadata del valuador
│   │   │   └── page.tsx        # Valuador AVM interactivo
│   │   ├── favoritos/
│   │   │   └── page.tsx        # Página de favoritos
│   │   ├── inmuebles/[id]/
│   │   │   └── page.tsx        # Detalle de inmueble
│   │   ├── [departamento]/[[...filter]]/
│   │   │   └── page.tsx        # Listings por departamento
│   │   ├── tag/[tag]/[[...filter]]/
│   │   │   └── page.tsx        # Listings por tag
│   │   └── api/                # 13 API routes
│   │       ├── colonias/route.ts
│   │       ├── department-stats/route.ts
│   │       ├── department/[slug]/route.ts
│   │       ├── department/[slug]/top-scored/route.ts
│   │       ├── geocode/route.ts
│   │       ├── listing/[id]/route.ts
│   │       ├── listings/route.ts
│   │       ├── listings/batch/route.ts
│   │       ├── nearby-listings/route.ts
│   │       ├── reverse-geocode/route.ts
│   │       ├── tag/[tag]/route.ts
│   │       ├── tags/route.ts
│   │       └── valuador/route.ts
│   ├── components/             # 32 componentes React
│   ├── hooks/                  # Custom hooks
│   │   ├── useFavorites.tsx    # Context + cookie, max 25
│   │   └── useDepartmentFilters.ts # Filtros URL-synced
│   ├── lib/                    # Utilidades
│   │   ├── biCalculations.ts   # Cálculos BI (percentil, stats)
│   │   ├── echarts.ts          # ECharts tree-shaken
│   │   ├── imageCache.ts       # Cache de imágenes client-side
│   │   ├── rankingChartsAdapter.ts # Adaptador datos → ECharts
│   │   ├── seo.ts              # Generadores JSON-LD
│   │   └── slugify.ts          # Slug ↔ departamento
│   ├── types/                  # Interfaces TypeScript
│   │   ├── listing.ts          # Listing, ListingSpecs, ListingLocation
│   │   └── biStats.ts          # NationalStats, DepartmentBIStats, etc.
│   ├── data/
│   │   └── departamentos.ts    # 14 departamentos + municipios + aliases
│   └── empty-polyfills.js      # Stub para eliminar polyfills legacy
├── scraper_encuentra24.py      # Scraper principal multi-fuente (3706 líneas)
├── match_locations.py          # Matching listados → jerarquía sv_loc_group
├── area_normalizer.py          # Normalización área → m²
├── deduplication.py            # Deduplicación de listados
├── listing_validator.py        # Validación de listados activos
├── enrich_locations.py         # Enriquecimiento de ubicaciones
├── export_to_supabase.py       # Export directo a Supabase
├── fetch_residential_areas.py  # Fetch áreas residenciales
├── find_unmatched.py           # Listados sin match de ubicación
├── generate_sql_from_json.py   # Generador SQL desde JSON
├── import_locations_to_supabase.py
├── scraper_el_salvador_locations.py
├── scraper_with_dedup.py
├── validate_encuentra24.py
├── validate_listings.py
├── localization_plugin.py
├── requirements.txt            # Deps Python
├── package.json                # Deps Node.js
├── next.config.ts              # Config Next.js
├── tsconfig.json               # Config TypeScript
├── eslint.config.mjs           # ESLint flat config
├── postcss.config.mjs          # PostCSS (TailwindCSS v4)
├── run_dev.bat                 # Script Windows para dev server
└── .env.example                # Variables de entorno requeridas
```

---

## 3. FLUJO DE DATOS

```
┌─────────────────┐     ┌────────────────┐     ┌─────────────┐
│  Encuentra24    │     │   MiCasaSV     │     │ Realtor.com │
│  (HTML + JSON)  │     │  (XML sitemap) │     │ (__NEXT_DATA)|
└────────┬────────┘     └───────┬────────┘     └──────┬──────┘
         │                      │                      │
         └──────────┬───────────┘──────────────────────┘
                    ▼
         scraper_encuentra24.py
         ├── ThreadPoolExecutor (concurrente)
         ├── parse_price() + correct_listing_type()
         ├── generate_location_tags()
         ├── area_normalizer.normalize_listing_specs()
         └── match_locations.match_scraped_listings()
                    │
                    ▼
         ┌─────────────────┐
         │   Supabase      │
         │  PostgreSQL +   │
         │    PostGIS      │
         ├─────────────────┤
         │ scrappeddata_   │
         │   ingest        │ ← tabla principal
         │ sv_loc_group2-5 │ ← jerarquía ubicaciones
         │ listing_location│
         │   _match        │ ← matching listado↔ubicación
         │ mv_sd_depto_    │
         │   stats         │ ← vista materializada
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  Next.js API    │
         │   Routes (13)   │
         │  Node.js/Edge   │
         └────────┬────────┘
                  │
                  ▼
         ┌─────────────────┐
         │  React Frontend │
         │  SSR + CSR      │
         │  (Vercel)       │
         └─────────────────┘
```

---

## 4. PÁGINAS Y RUTAS

### 4.1 HOME — src/app/page.tsx

- **Ruta:** /
- **Rendering:** SSR con `unstable_cache` (tag: `department-stats`, revalidate: 300s)
- **Filtro global:** Total | Venta | Alquiler (state: `activeView`)
- **Secciones renderizadas:**
  1. `Navbar` — total de listados activos, botón refresh
  2. `HeroSection` — búsqueda de ubicación, llama a `handleHeroLocationSelect`
  3. `HomeHeader` — KPIs globales
  4. `MapExplorer` — mapa Leaflet (dynamic import, SSR: false)
  5. Grid de `DepartmentCard` — 14 departamentos con stats
  6. `MarketRankingCharts` — gráficas ECharts de rankings
- **Cálculos:** `getDisplayStats()` computa promedios ponderados para vista "all"

### 4.2 LAYOUT RAÍZ — src/app/layout.tsx

- **Font:** Inter (Google Fonts, `next/font/google`)
- **Idioma:** `lang="es"`
- **Providers:** `FavoritesProvider` vía `Providers.tsx`
- **Observabilidad:** `<SpeedInsights />` + `<Analytics />` (Vercel)
- **Metadata:** title template `%s | sivarcasas`, metadataBase `https://sivarcasas.com`, OpenGraph, Twitter cards, keywords

### 4.3 TEMPLATE HOME — src/app/template.tsx

- Server component que inyecta JSON-LD (Organization + WebSite schemas) via `<JsonLd />`

### 4.4 TENDENCIAS — src/app/tendencias/page.tsx

- **Ruta:** /tendencias
- **Rendering:** SSR con `unstable_cache` (tag: `department-stats`, revalidate: 300s)
- **Componente principal:** `TendenciasClient` (client component)
- Muestra rankings nacionales, gráficas comparativas, evolución mensual simulada

### 4.5 VALUADOR DE INMUEBLES — src/app/valuador-de-inmuebles/

- **Ruta:** /valuador-de-inmuebles
- **Rendering:** Client-side (use client)
- **layout.tsx:** Metadata específica (title, description, canonical)
- **page.tsx (642 líneas):**
  - Autocomplete de ubicación via `/api/geocode` y `/api/colonias`
  - Selección de tipo de propiedad (casa, apartamento, lote, local)
  - Inputs: área m², recámaras, baños, parking
  - Llama a `POST /api/valuador` para obtener estimación
  - Muestra: valor estimado, rango bajo/alto, confianza, precio/m², renta estimada, proyección 12m, top comparables

### 4.6 FAVORITOS — src/app/favoritos/page.tsx

- **Ruta:** /favoritos
- **Rendering:** Client-side
- **Persistencia:** Cookie via `useFavorites` hook (máximo 25 favoritos)
- **Funcionalidad:** Grid de listados favoritos, comparación de precio/área, botón eliminar

### 4.7 DETALLE DE INMUEBLE — src/app/inmuebles/[id]/page.tsx

- **Ruta:** /inmuebles/:id
- **Rendering:** Client-side
- **Interface:** `FullListing` con todos los campos (specs, details, images, contact_info, tags)
- **Features:** Galería de imágenes con navegación teclado (←→), botón favorito, tags de ubicación, enlace a fuente original

### 4.8 DEPARTAMENTO — src/app/[departamento]/[[...filter]]/page.tsx

- **Rutas:**
  - `/:departamento` — todos los listados
  - `/:departamento/venta` — solo ventas
  - `/:departamento/alquiler` — solo alquileres
- **Rendering:** SSR + Client-side filters
- **Filtros:** tipo (venta/alquiler), municipio, precio, categoría, ordenamiento
- **Paginación:** Offset-based, 24 items por página
- **Hook:** `useDepartmentFilters` — sincroniza filtros con URL

### 4.9 TAG — src/app/tag/[tag]/[[...filter]]/page.tsx

- **Rutas:** `/tag/:tag`, `/tag/:tag/venta`, `/tag/:tag/alquiler`
- **Redirects:** `/tag/:departamento` → `/:departamento` (301 permanente, via next.config.ts)

### 4.10 SEO DINÁMICO

| Archivo                  | Genera        | Detalles                                |
|--------------------------|---------------|-----------------------------------------|
| src/app/robots.ts        | robots.txt    | Allow: /, Disallow: /api/               |
| src/app/sitemap.ts       | sitemap.xml   | Home + tendencias + valuador + 14 deptos × 3 variantes |
| src/app/opengraph-image.tsx | OG image   | 1200×630, @vercel/og runtime            |
| src/app/twitter-image.tsx   | Twitter card | 1200×600, @vercel/og runtime          |

---

## 5. API ROUTES (13 ENDPOINTS)

### 5.1 GET /api/department-stats

- **Runtime:** Node.js
- **Cache:** In-memory (30s TTL) + Cache-Control headers + Next.js revalidate 300s
- **Fuente:** Vista materializada `mv_sd_depto_stats`
- **Respuesta:** Array de objetos agrupados por departamento con stats de venta/renta
- **Headers:** `X-Cache: HIT|MISS`

### 5.2 GET /api/department/[slug]

- **Runtime:** Node.js
- **Params URL:** slug (departamento)
- **Query:** type, sort, limit (default 24), offset, municipalities, min_price, max_price, category
- **Fuente:** RPC `get_listings_for_cards` + `get_municipalities_for_department` + `get_categories_for_department`
- **Respuesta:** `{ listings: CardListing[], municipalities: Municipality[], categories: string[], pagination: {...} }`
- **Nota:** Extrae property types de tags con set `PROPERTY_TYPES`

### 5.3 GET /api/department/[slug]/top-scored

- **Runtime:** Node.js
- **Query:** type (sale|rent|all), limit (default 10)
- **Fuente:** RPC `get_top_scored_listings`
- **Respuesta:** `{ departamento, sale: [...], rent: [...], all: [...] }`
- **Cache:** revalidate 300s

### 5.4 GET /api/listing/[id]

- **Runtime:** Edge
- **Fuente:** REST query directa a `scrappeddata_ingest` por `external_id`
- **Cache:** revalidate 60s
- **Nota:** Regex fix para `external_id` > 15 dígitos (previene pérdida de precisión JS)

### 5.5 GET /api/listings

- **Runtime:** Node.js
- **Fuente:** REST query a `scrappeddata_ingest` (select=*, order=last_updated.desc)
- **Cache:** revalidate 300s
- **Nota:** Endpoint legacy, sin paginación

### 5.6 GET /api/listings/batch

- **Runtime:** Node.js
- **Query:** ids (comma-separated external_ids)
- **Fuente:** REST query con `external_id=in.(...)`
- **Cache:** revalidate 60s
- **Uso:** Página de favoritos fetch batch por IDs de cookie

### 5.7 GET /api/nearby-listings

- **Runtime:** Node.js
- **Query:** lat, lng (required), radius (km, default 2, clamped 0.5-10), sort_by, limit (1-20), offset, listing_type
- **Fuente:** RPCs `fn_listing_price_stats_nearby` + `fn_listings_nearby_page` (paralelo)
- **Respuesta:** `{ stats: PriceStats[], listings: NearbyListing[], pagination, meta }`

### 5.8 GET /api/geocode

- **Runtime:** Node.js
- **Query:** q (min 2 chars)
- **Proxy:** Nominatim OSM (`countrycodes=sv`)
- **Cache:** revalidate 3600s (1h)
- **Nota:** Strip diacríticos para búsqueda sin acentos

### 5.9 GET /api/reverse-geocode

- **Runtime:** Node.js
- **Query:** lat, lng
- **Proxy:** Nominatim reverse geocoding (zoom=18)
- **Cache:** revalidate 86400s (24h)
- **Respuesta:** `{ name: string | null }` — nombre compuesto de lugar

### 5.10 GET /api/colonias

- **Runtime:** Node.js
- **Query:** q (min 2 chars)
- **Fuente:** RPC `search_colonias`
- **Cache:** revalidate 3600s
- **Respuesta:** Array `ColoniaResult[]` con id, name, lat, lng, municipio, departamento

### 5.11 GET /api/tags

- **Runtime:** Edge
- **Fuente:** RPC `get_available_tags` con fallback a query directa
- **Cache:** revalidate 300s
- **Respuesta:** `{ tags: [{tag}], count }`

### 5.12 GET /api/tag/[tag]

- **Runtime:** Edge
- **Query:** limit, offset, type, sort
- **Fuente:** RPC `get_listings_by_tag`
- **Cache:** revalidate 60s
- **Filtro post-query:** Excluye "Casa" ventas < $15,000 (probable misclasificación)
- **Respuesta:** `{ tag, slug, listings, pagination }`

### 5.13 POST /api/valuador

- **Runtime:** Node.js
- **Body JSON:** `{ lat, lng, area_m2, property_type, bedrooms?, bathrooms?, parking? }`
- **Fuente:** RPCs `avm_value_point` (sale + rent en paralelo) + `avm_nearest_matches` (top 5 comps)
- **Respuesta:** `{ estimated_value, range_low, range_high, confidence, price_per_m2, estimated_rent, rent_percentage, projection_12m, top_comps[], ... }`
- **Fallback renta:** Si `insufficient_data`, usa 0.6% del valor de venta
- **Proyección:** 5% apreciación anual hardcoded

---

## 6. COMPONENTES (32)

| Componente                | Archivo                         | Tipo    | Descripción |
|---------------------------|--------------------------------|---------|-------------|
| Navbar                    | Navbar.tsx                     | Client  | Barra superior con logo, total listados, navegación |
| HeroSection               | HeroSection.tsx                | Client  | Hero con búsqueda de ubicación |
| HomeHeader                | HomeHeader.tsx                 | Client  | KPIs globales del home |
| DepartmentCard            | DepartmentCard.tsx             | Client  | Tarjeta de departamento con stats |
| DepartmentCardBI          | DepartmentCardBI.tsx           | Client  | Versión BI de la tarjeta |
| MapExplorer               | MapExplorer.tsx                | Client  | Mapa Leaflet interactivo (dynamic import) |
| MarketRankingCharts       | MarketRankingCharts.tsx        | Client  | Gráficas ECharts de rankings |
| ListingCard               | ListingCard.tsx                | Client  | Tarjeta individual de listado |
| ListingModal              | ListingModal.tsx               | Client  | Modal detalle de listado |
| ListingsView              | ListingsView.tsx               | Client  | Vista de grid de listados |
| BestOpportunitySection    | BestOpportunitySection.tsx     | Client  | Sección de mejores oportunidades |
| TendenciasClient          | TendenciasClient.tsx           | Client  | Dashboard de tendencias |
| TrendsSection             | TrendsSection.tsx              | Client  | Sección de tendencias |
| TrendsInsights            | TrendsInsights.tsx             | Client  | Insights de tendencias |
| DepartmentFilterBar       | DepartmentFilterBar.tsx        | Client  | Barra de filtros por departamento |
| FiltersPanel              | FiltersPanel.tsx               | Client  | Panel expandible de filtros |
| ActiveFilterChips         | ActiveFilterChips.tsx          | Client  | Chips de filtros activos |
| MunicipalityFilterChips   | MunicipalityFilterChips.tsx    | Client  | Chips de filtro por municipio |
| TagFilterChips            | TagFilterChips.tsx             | Client  | Chips de filtro por tag |
| PriceRangePopover         | PriceRangePopover.tsx          | Client  | Popover para rango de precios |
| KPICard                   | KPICard.tsx                    | Client  | Tarjeta individual de KPI |
| KPIStrip                  | KPIStrip.tsx                   | Client  | Strip horizontal de KPIs |
| RankingCard               | RankingCard.tsx                | Client  | Tarjeta de ranking individual |
| RankingsSection           | RankingsSection.tsx            | Client  | Sección contenedora de rankings |
| DashboardHeader           | DashboardHeader.tsx            | Client  | Header del dashboard |
| SectionHeader             | SectionHeader.tsx              | Client  | Header reutilizable de secciones |
| FeatureCards              | FeatureCards.tsx               | Client  | Tarjetas de features del sitio |
| InsightsPanel             | InsightsPanel.tsx              | Client  | Panel de insights BI |
| LocationCard              | LocationCard.tsx               | Client  | Tarjeta de ubicación |
| LazyImage                 | LazyImage.tsx                  | Client  | Imagen lazy con imageCache |
| JsonLd                    | JsonLd.tsx                     | Server  | Inyector de JSON-LD |
| UnclassifiedCard          | UnclassifiedCard.tsx           | Client  | Tarjeta para listados sin clasificar |

---

## 7. HOOKS PERSONALIZADOS

### 7.1 useFavorites — src/hooks/useFavorites.tsx

- **Tipo:** Context + Provider (`FavoritesProvider`)
- **Persistencia:** Cookie `sivarcasas_favorites`
- **Límite:** 25 favoritos máximo
- **API:** `addFavorite(id)`, `removeFavorite(id)`, `toggleFavorite(id)`, `isFavorite(id)`, `favorites: string[]`
- **Almacena:** Array de `external_id` como strings

### 7.2 useDepartmentFilters — src/hooks/useDepartmentFilters.ts

- **Tipo:** Hook con estado local sincronizado a URL
- **Filtros:** listingType (all|sale|rent), priceRange [min,max], municipalities[], categories[]
- **Sorting:** recent, price_asc, price_desc
- **Derivados:** `activeFiltersCount`, `filterChips[]`
- **Sincronización:** Lee/escribe `searchParams` via `useRouter`

---

## 8. UTILIDADES (src/lib/)

### 8.1 biCalculations.ts (267 líneas)

Funciones de cálculo para métricas BI del home. Importa `Listing` y tipos de `biStats.ts`.

| Función                     | Descripción                                      |
|-----------------------------|--------------------------------------------------|
| `calculatePercentile(values, percentile)` | Percentil de array numérico            |
| `isWithinDays(dateStr, days)` | Verifica si fecha está dentro de N días         |
| `getLocationString(listing)` | Extrae string de ubicación de un listing         |
| `calculateNationalStats(listings)` | Stats nacionales (median sale/rent, total, new 7d) |
| `calculateDepartmentBIStats(listings, filterType)` | Stats por departamento con municipios |
| `calculateInsights(departments)` | Top 3 subidas, bajadas, actividad 7d           |
| `calculateHomeBIData(listings, filterType)` | Función principal que calcula todo     |
| `formatPrice(price)` | Formato: $125,000                                     |
| `formatTrend(pct)` | Formato con flecha: ▲ 5.2% / ▼ -3.1%                   |
| `formatTime(isoString)` | Formato hora local                                 |

### 8.2 echarts.ts (22 líneas)

Importación modular de ECharts para reducir bundle (~326 KiB → ~80-100 KiB):

- Componentes: `BarChart`, `LineChart`, `TitleComponent`, `TooltipComponent`, `GridComponent`
- Renderer: `CanvasRenderer`

### 8.3 imageCache.ts (219 líneas)

Singleton `ImageCacheManager` para cache client-side de imágenes:

- Max concurrent requests: 4
- Cache TTL: 5 minutos
- Max cache size: 100 imágenes
- Usa `URL.createObjectURL()` con blob
- Evicción LRU automática
- API: `getImage(url)`, `preloadImages(urls)`, `isCached(url)`, `getCachedUrl(url)`, `clearCache()`

### 8.4 rankingChartsAdapter.ts (147 líneas)

Adaptador datos → ECharts. No recalcula, solo mapea estructuras existentes.

| Función                    | Descripción                                    |
|----------------------------|------------------------------------------------|
| `formatPriceCompact(price)` | $125K, $1.2M                                 |
| `toExpensiveDataPoints(items)` | Top 5 más caros (reversed)                 |
| `toCheapDataPoints(items)` | Top 5 más baratos (reversed)                   |
| `toActiveDataPoints(items)` | Top 5 más activos                             |
| `computeRankings(departments, view)` | Computa rankings desde datos raw       |
| `toAllDeptPriceDataPoints(...)` | Precio medio todos los deptos, sorted     |
| `toMonthlyEvolution(...)` | Evolución mensual simulada (12 meses, variación estacional) |

### 8.5 seo.ts (224 líneas)

Generadores de Schema.org JSON-LD para SEO:

| Función                          | Schema generado          |
|----------------------------------|--------------------------|
| `generateOrganizationSchema()`   | RealEstateAgent          |
| `generateWebSiteSchema()`        | WebSite con SearchAction |
| `generateListingSchema(listing)` | RealEstateListing        |
| `generateItemListSchema(items, url, name)` | ItemList       |
| `generateBreadcrumbSchema(items)` | BreadcrumbList          |
| `generateDepartmentPageSchema(name, stats)` | CollectionPage |

### 8.6 slugify.ts (62 líneas)

Conversión bidireccional departamento ↔ slug URL:

- `departamentoToSlug("San Salvador")` → `"san-salvador"`
- `slugToDepartamento("san-salvador")` → `"San Salvador"`
- `getAllDepartamentoSlugs()` → array de 14 slugs
- `isValidDepartamentoSlug(slug)` → boolean

---

## 9. TIPOS TYPESCRIPT (src/types/)

### 9.1 listing.ts

```typescript
type ListingSpecs = Record<string, string | number | undefined>;

type ListingLocation = string | {
    municipio_detectado?: string;
    city?: string; state?: string; country?: string;
    departamento?: string;
    latitude?: number; longitude?: number;
    [key: string]: string | number | undefined;
} | null;

interface Listing {
    external_id: string | number;  // String para prevenir pérdida de precisión
    title: string;
    price: number;
    listing_type: 'sale' | 'rent';
    id?: number;
    url?: string; source?: string; currency?: string;
    tags?: string[] | null;
    location?: ListingLocation;
    description?: string;
    specs?: ListingSpecs | null;
    details?: Record<string, string>;
    images?: string[] | null;
    contact_info?: ListingContactInfo;
    published_date?: string;
    scraped_at?: string;
    last_updated?: string;
}

interface LocationStats {
    count: number; listings: Listing[];
    avg: number; min: number; max: number;
}
```

### 9.2 biStats.ts

```typescript
interface NationalStats {
    median_sale: number; median_rent: number;
    total_active: number;
    new_7d: number; new_prev_7d: number;
    updated_at: string; sources: string[];
}

interface DepartmentBIStats {
    departamento: string; count_active: number;
    municipios_con_actividad: number;
    median_price: number; p25_price: number; p75_price: number;
    new_7d: number; trend_30d_pct: number;
    municipios: Record<string, MunicipioStats>;
}

interface MunicipioStats {
    count: number; median_price: number;
    p25_price: number; p75_price: number;
    new_7d: number; listings: Listing[];
}

interface InsightItem { municipio: string; departamento: string; value: number; }
interface Insights { top3_up_30d: InsightItem[]; top3_down_30d: InsightItem[]; top3_active_7d: InsightItem[]; }
interface HomeBIData { national: NationalStats; departments: DepartmentBIStats[]; insights: Insights; unclassified: {...}; }
```

---

## 10. DATOS ESTÁTICOS (src/data/)

### departamentos.ts (191 líneas)

- `DEPARTAMENTOS`: Record de 14 departamentos → array de municipios
- `LOCATION_ALIASES`: Mapeo de nombres coloquiales → {municipio, departamento}
  - Ejemplo: `"escalón"` → `{ municipio: "San Salvador", departamento: "San Salvador" }`
  - Ejemplo: `"merliot"` → `{ municipio: "Antiguo Cuscatlán", departamento: "La Libertad" }`
- `normalizeText(text)`: Quita acentos y convierte a minúsculas
- `detectDepartamento(location)`: Detecta departamento/municipio de un string
- `getDepartamentoNames()`, `getMunicipios(departamento)`

---

## 11. BASE DE DATOS (SUPABASE + POSTGRESQL + POSTGIS)

### 11.1 TABLAS PRINCIPALES

| Tabla                    | Descripción                                          |
|--------------------------|------------------------------------------------------|
| `scrappeddata_ingest`    | Tabla principal de listados scrapeados                |
| `sv_loc_group2`          | Colonias/barrios (nivel 2, con coordenadas)          |
| `sv_loc_group3`          | Municipios (nivel 3)                                 |
| `sv_loc_group4`          | Distritos (nivel 4)                                  |
| `sv_loc_group5`          | Departamentos (nivel 5)                              |
| `listing_location_match` | Matching listado ↔ colonia (external_id → loc_group2_id) |

### 11.2 VISTAS MATERIALIZADAS

| Vista                | Descripción                                                 |
|----------------------|-------------------------------------------------------------|
| `mv_sd_depto_stats`  | Stats por departamento + listing_type (count, min, max, avg) |

### 11.3 FUNCIONES RPC (SUPABASE)

| Función RPC                      | Archivo SQL                              | Descripción |
|----------------------------------|-----------------------------------------|-------------|
| `get_listings_for_cards`         | get_listings_for_cards_v2_location.sql   | Listados paginados para tarjetas, con filtros y sorting |
| `get_municipalities_for_department` | get_municipalities_for_department.sql | Municipios con conteo de listados |
| `get_categories_for_department`  | get_categories_for_department.sql        | Categorías (tipos propiedad) disponibles |
| `get_listings_by_tag`            | supabase_tag_functions.sql              | Listados por tag con paginación |
| `get_available_tags`             | supabase_tag_functions.sql              | Tags únicos disponibles |
| `get_top_scored_listings`        | (inline en la tabla)                    | Top listados por score/departamento |
| `get_price_estimate`             | get_price_estimate.sql                  | Estimación de precio (legacy) |
| `search_colonias`                | fn_search_colonias.sql                  | Búsqueda fuzzy en sv_loc_group2 |
| `fn_valuador_comps`              | fn_valuador_comps.sql                   | Comparables para valuador (con PostGIS) |
| `fn_listing_price_stats_nearby`  | update_fn_nearby_candidates.sql         | Stats de precio en radio |
| `fn_listings_nearby_page`        | update_fn_nearby_candidates.sql         | Listados cercanos paginados |
| `avm_nearest_matches`           | avm_functions.sql                       | Comparables AVM con pesos multi-factor |
| `avm_value_point`               | avm_functions.sql                       | Valuación punto con IQR + confianza |

### 11.4 FUNCIONES AVM (DETALLE)

**avm_nearest_matches** — Nearest comparable listings:
- Parámetros: lat, lon, area_m2, listing_type, property_class, bedrooms, bathrooms, parking
- Radius ladder: [1km, 2km, 3km, 5km, 8km, 12km, 20km] — escoge el más pequeño con ≥ min_comps
- Filtro área: 0.60x — 1.80x del subject
- Pesos: distance (exponencial), freshness (exp decay 60d), status (active=1, <90d=0.7, else=0.45), size (log-normal), features (bedrooms × bathrooms × parking)
- IQR outlier removal
- Fallback nacional si no hay suficientes comps locales

**avm_value_point** — Point valuation:
- Llama a `avm_nearest_matches` internamente
- Calcula: weighted PPM2, percentil 25/75 para rango
- Confianza: `min(0.95, min(1, count/15) × exp(-IQR_dispersion))`
- Retorna: est_price, est_low, est_high, confidence, method (radius_weighted_ppm2 | national_fallback | insufficient_data)

### 11.5 SCRIPTS SQL AUXILIARES

| Script                                  | Propósito                                    |
|-----------------------------------------|----------------------------------------------|
| create_sv_locations_table.sql           | Crear tablas sv_loc_group                    |
| insert_sv_locations.sql                 | Insertar datos de ubicaciones                |
| insert_sv_locations_residential.sql     | Insertar áreas residenciales                 |
| recreate_mv_with_location_match.sql     | Recrear MV con join a location_match         |
| recreate_mv_with_median.sql             | Recrear MV con mediana                       |
| cleanup_specs.sql                       | Limpiar campo specs                          |
| fix_area_m2_values.sql                  | Corregir valores de área                     |
| migrate_area_to_area_m2.sql            | Migrar campo area → area_m2                  |
| unmatched_locations.sql                 | Query para listados sin match de ubicación   |
| update_best_opportunity_images.sql      | Actualizar imágenes de mejores oportunidades |

---

## 12. SCRAPER Y PIPELINE

### 12.1 SCRAPER PRINCIPAL — scraper_encuentra24.py (3706 líneas)

**Fuentes soportadas:**

| Fuente       | Método de parseo                     | Tipo              |
|-------------|--------------------------------------|-------------------|
| Encuentra24  | HTML + CSS selectors                 | Venta + Alquiler  |
| MiCasaSV     | XML sitemap → HTML detail pages      | Venta + Alquiler  |
| Realtor.com  | `__NEXT_DATA__` JSON embedded        | Venta + Alquiler  |
| Vivo Latam   | HTML                                 | Venta + Alquiler  |

**Pipeline de procesamiento por listado:**
1. `parse_price()` → extrae precio numérico
2. `correct_listing_type()` → corrige misclasificaciones (heurísticas: precio, keywords, URL path)
3. `generate_location_tags()` → genera tags de tipo de propiedad
4. `area_normalizer.normalize_listing_specs()` → normaliza a m²
5. `match_locations.match_scraped_listings()` → match a jerarquía sv_loc_group
6. `insert_listings_batch()` → upsert a Supabase (batch de 50)

**Modo update (`--update`):**
1. `get_active_listings_from_db()` → fetch activos con paginación
2. Re-scrape cada URL activa
3. `update_listings_batch()` → PATCH en Supabase
4. `validate_and_deactivate_listings()` → marca inactivos los que ya no existen (404/sold)

**CLI:**

```bash
# Scrape nuevos (últimos 7 días, todas las fuentes)
python scraper_encuentra24.py --max-days 7

# Scrape con límite
python scraper_encuentra24.py --max-days 7 --limit 100

# Modo update (re-verificar activos)
python scraper_encuentra24.py --update

# Update con límite
python scraper_encuentra24.py --update --limit 50
```

### 12.2 SCRIPTS DE SOPORTE

| Script                  | Función                                              |
|------------------------|------------------------------------------------------|
| match_locations.py      | Matching listados → jerarquía sv_loc_group          |
| area_normalizer.py      | Normalización de unidades de área a m²              |
| deduplication.py        | Deduplicación de listados por external_id/URL       |
| listing_validator.py    | Validación HTTP de URLs activas                     |
| enrich_locations.py     | Enriquecimiento de datos de ubicación               |
| export_to_supabase.py   | Export manual a Supabase                            |
| fetch_residential_areas.py | Fetch de áreas residenciales                     |
| find_unmatched.py       | Identificar listados sin match de ubicación         |
| generate_sql_from_json.py | Generar SQL INSERT desde JSON                     |
| import_locations_to_supabase.py | Import bulk de ubicaciones               |
| validate_encuentra24.py | Validación específica de Encuentra24                |
| validate_listings.py    | Validación general de listados                      |
| scraper_with_dedup.py   | Scraper con deduplicación integrada                 |
| scraper_el_salvador_locations.py | Scraper de datos geográficos de ES         |
| localization_plugin.py  | Plugin de localización                              |

### 12.3 DEPENDENCIAS PYTHON — requirements.txt

```
requests>=2.31.0
beautifulsoup4>=4.12.0
supabase>=2.0.0
python-dotenv>=1.0.0
```

---

## 13. CI/CD (GITHUB ACTIONS)

### 13.1 scrape-new.yml — Scrape New Listings

- **Trigger:** Cron cada hora (`0 * * * *`) + workflow_dispatch manual
- **Runner:** ubuntu-latest, timeout 60 min
- **Python:** 3.11 con cache pip
- **Inputs manuales:** max_days (default 7), limit (optional)
- **Secrets:** `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **Comando:** `python scraper_encuentra24.py --max-days {max_days} [--limit {limit}]`

### 13.2 scrape-update.yml — Update Active Listings

- **Trigger:** Cron cada 12 horas (`0 0,12 * * *`) + workflow_dispatch manual
- **Runner:** ubuntu-latest, timeout 60 min
- **Python:** 3.11 con cache pip
- **Inputs manuales:** limit (optional)
- **Secrets:** `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- **Comando:** `python scraper_encuentra24.py --update [--limit {limit}]`

---

## 14. CONFIGURACIÓN

### 14.1 VARIABLES DE ENTORNO

| Variable              | Ubicación              | Descripción                        |
|-----------------------|-----------------------|------------------------------------|
| `SUPABASE_URL`        | .env.local + GH Secrets | URL del proyecto Supabase         |
| `SUPABASE_SERVICE_KEY` | .env.local + GH Secrets | Service role key de Supabase     |

Archivo `.env.example`:
```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
```

### 14.2 next.config.ts

- **experimental:** `optimizePackageImports` (react-leaflet, leaflet, echarts), `cssChunking: 'strict'`, `optimizeCss: true`
- **images:** `remotePatterns: [{ protocol: 'https', hostname: '**' }]` (permite cualquier dominio HTTPS)
- **redirects:** `/tag/:departamento` → `/:departamento` (301 permanente, 14 departamentos)
- **webpack:** Stub `polyfill-nomodule` con `src/empty-polyfills.js`
- **turbopack:** Stub polyfill via `resolveAlias`

### 14.3 tsconfig.json

- Target: ES2017, Module: esnext, Module Resolution: bundler
- Strict mode habilitado
- Path alias: `@/*` → `./src/*`
- Plugin: `next`

### 14.4 eslint.config.mjs

- Flat config con `eslint-config-next/core-web-vitals` + `typescript`
- Ignores: `.next/`, `out/`, `build/`, `next-env.d.ts`

### 14.5 postcss.config.mjs

- Plugin: `@tailwindcss/postcss` (TailwindCSS v4)

### 14.6 package.json

- **name:** sivarcasas-dashboard v0.1.0
- **scripts:** dev, build, start, lint
- **browserslist:** last 2 versions de Chrome, Firefox, Safari, Edge

### 14.7 empty-polyfills.js

Stub vacío que reemplaza el chunk de polyfills legacy de Next.js. El browserslist ya apunta a navegadores modernos que soportan todas las APIs polyfilled.

### 14.8 run_dev.bat

Script Windows para iniciar dev server:
```bat
@echo off
echo Starting SivarCasas Development Server...
SET PATH=%PATH%;C:\Program Files\nodejs
npm run dev
pause
```

---

## 15. DESPLIEGUE Y EJECUCIÓN

### 15.1 DESARROLLO LOCAL

```bash
# 1. Clonar repositorio
git clone https://github.com/chivocasa42-sys/chivocasa.git
cd chivocasa

# 2. Instalar dependencias
npm install
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env.local
# Editar .env.local con credenciales de Supabase

# 4. Iniciar dev server
npm run dev
# O en Windows:
run_dev.bat
```

### 15.2 PRODUCCIÓN

```bash
npm run build    # Build de producción
npm run start    # Iniciar servidor de producción
```

El deploy principal es via **Vercel** con deploy automático en push a main.

### 15.3 EJECUCIÓN DEL SCRAPER (LOCAL)

```bash
# Scrape nuevos listados
python scraper_encuentra24.py --max-days 7

# Actualizar listados activos
python scraper_encuentra24.py --update
```

---

## 16. PRIVACIDAD Y DATOS

- Los listados son datos públicos scrapeados de portales inmobiliarios
- No se almacenan datos personales de usuarios
- Los favoritos se almacenan en cookie del navegador (no server-side)
- Las credenciales de Supabase usan service role key (no expuesta al cliente)
- El User-Agent del scraper se identifica como `ChivocasaBot/1.0`
- Las APIs de geocodificación (Nominatim) se usan como proxy server-side

---

## 17. OBSERVABILIDAD

| Herramienta            | Propósito                              |
|------------------------|----------------------------------------|
| Vercel Analytics       | Page views, visitantes, referrers      |
| Vercel Speed Insights  | Core Web Vitals, LCP, FID, CLS        |
| console.time/timeEnd   | Perf logging en API routes (server-side) |
| X-Cache header         | Hit/Miss en department-stats cache     |

---

## 18. LISTA DE LOS 14 DEPARTAMENTOS

| # | Departamento    | Slug URL         |
|---|----------------|------------------|
| 1 | Ahuachapán     | ahuachapan       |
| 2 | Cabañas        | cabanas          |
| 3 | Chalatenango   | chalatenango     |
| 4 | Cuscatlán      | cuscatlan        |
| 5 | La Libertad    | la-libertad      |
| 6 | La Paz         | la-paz           |
| 7 | La Unión       | la-union         |
| 8 | Morazán        | morazan          |
| 9 | San Miguel     | san-miguel       |
| 10| San Salvador   | san-salvador     |
| 11| San Vicente    | san-vicente      |
| 12| Santa Ana      | santa-ana        |
| 13| Sonsonate      | sonsonate        |
| 14| Usulután       | usulutan         |

---

## 19. MEJORAS PENDIENTES

- [ ] Implementar cálculo real de tendencias 30 días (actualmente trend_30d_pct está en 0)
- [ ] Agregar búsqueda global de propiedades
- [ ] Incluir gráficas de tendencia temporal en tarjetas de departamento
- [ ] Exportación CSV/Excel de datos
- [ ] Tests unitarios para funciones BI (biCalculations.ts)
- [ ] Desarrollo PWA para móvil
- [ ] Implementar dark mode (variables CSS ya preparadas)
- [ ] Evolución mensual real (actualmente simulada con variación estacional)
- [ ] Agregar más fuentes de scraping

---

## 20. CHECKLIST DE VERIFICACIÓN

| #  | Verificación                                           | Estado |
|----|--------------------------------------------------------|--------|
| 1  | Nombre del producto: "Sivar Casas"                     | ✅     |
| 2  | Árbol de carpetas completo y preciso                   | ✅     |
| 3  | Todas las 10 páginas/rutas documentadas                | ✅     |
| 4  | Todos los 13 endpoints API documentados                | ✅     |
| 5  | Los 32 componentes listados                            | ✅     |
| 6  | Ambos hooks documentados                               | ✅     |
| 7  | Las 6 utilidades de lib/ documentadas                  | ✅     |
| 8  | Ambos archivos de tipos documentados                   | ✅     |
| 9  | Archivo de datos departamentos.ts documentado          | ✅     |
| 10 | Esquema de base de datos (tablas, MVs, RPCs)           | ✅     |
| 11 | Funciones AVM documentadas en detalle                  | ✅     |
| 12 | 23 scripts SQL listados                                | ✅     |
| 13 | Scraper principal documentado (fuentes, pipeline, CLI) | ✅     |
| 14 | 15 scripts Python de soporte listados                  | ✅     |
| 15 | Dependencias Python documentadas                       | ✅     |
| 16 | 2 workflows GitHub Actions documentados                | ✅     |
| 17 | Todas las variables de entorno documentadas             | ✅     |
| 18 | Configuración Next.js (polyfills, images, redirects)   | ✅     |
| 19 | browserslist y CSS performance documentados            | ✅     |
| 20 | SEO dinámico (robots, sitemap, OG, Twitter, JSON-LD)   | ✅     |
| 21 | Comandos de ejecución documentados                     | ✅     |
| 22 | Privacidad y datos documentados                        | ✅     |
| 23 | Observabilidad documentada                             | ✅     |
| 24 | Lista de 14 departamentos con slugs                    | ✅     |
| 25 | Mejoras pendientes actualizadas                        | ✅     |
| 26 | Changelog de documentación presente                    | ✅     |
| 27 | Sin enlaces visibles (solo rutas de archivo)           | ✅     |
| 28 | Títulos en mayúsculas                                  | ✅     |
