# SIVARCASAS — Comprehensive Repository Architecture

> **Documento vivo** que describe la arquitectura, flujos de datos y dependencias del proyecto **SivarCasas** (alias *chivocasa*).  
> Última actualización manual: **2026-03-20**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Technology Stack](#2-technology-stack)
3. [Repository File Map](#3-repository-file-map)
4. [Architecture Overview](#4-architecture-overview)
5. [Frontend — Pages & Routing](#5-frontend--pages--routing)
6. [Frontend — Components](#6-frontend--components)
7. [Frontend — Hooks & Context](#7-frontend--hooks--context)
8. [Frontend — Lib Utilities](#8-frontend--lib-utilities)
9. [Frontend — Types](#9-frontend--types)
10. [API Layer (Next.js Route Handlers)](#10-api-layer-nextjs-route-handlers)
11. [Database — Supabase / PostgreSQL](#11-database--supabase--postgresql)
12. [AVM (Automated Valuation Model)](#12-avm-automated-valuation-model)
13. [Data Pipeline — Scrapers](#13-data-pipeline--scrapers)
14. [CI/CD — GitHub Actions](#14-cicd--github-actions)
15. [SEO & Structured Data](#15-seo--structured-data)
16. [Deployment & Infrastructure](#16-deployment--infrastructure)
17. [End-to-End Critical Flows](#17-end-to-end-critical-flows)
18. [Environment Variables](#18-environment-variables)
19. [PWA — Progressive Web App](#19-pwa--progressive-web-app)

---

## 1. Executive Summary

**SivarCasas** is a real-estate intelligence platform for El Salvador.  It aggregates public property listings from multiple sources (Encuentra24, MiCasaSV, Realtor, VivoLatam), normalizes the data, and presents it through a modern Next.js web application with:

- **Browsing by department** (14 departments, filterable by sale/rent, municipio, price, category)
- **Interactive map** (Leaflet) with nearby-listing search and price-per-m² stats
- **Automated property valuation** (AVM) using weighted comparable-sales analysis
- **Market trends** dashboard with department-level rankings
- **Favorites** system (cookie-based, max 25, side-by-side compare up to 4)
- **Individual property detail pages** with image gallery, specs, and external-source links

The backend is entirely **Supabase** (PostgreSQL + PostGIS + PostgREST). There is no custom server beyond Next.js API routes that proxy requests to Supabase RPCs.

---

## 2. Technology Stack

| Layer | Technology | Version/Notes |
|---|---|---|
| **Framework** | Next.js (App Router) | 16.1.6 |
| **UI** | React | 19 |
| **Styling** | Tailwind CSS | v4 |
| **Maps** | Leaflet + react-leaflet | OSM tiles |
| **Charts** | ECharts | Market trends visualizations |
| **Database** | Supabase (PostgreSQL + PostGIS) | PostgREST API, RPC functions |
| **Scraping** | Python 3 | `requests`, `beautifulsoup4`, `supabase-py` |
| **Image Optimization** | `sharp`, `next/image` | WebP/AVIF auto-conversion |
| **Analytics** | Vercel Analytics + Speed Insights | `@vercel/analytics`, `@vercel/speed-insights` |
| **CI/CD** | GitHub Actions | 2 workflows (scrape-new, scrape-update) |
| **Hosting** | Vercel | `sivarcasas.com` |
| **CSS Optimization** | critters | Critical CSS inlining |

---

## 3. Repository File Map

```
chivocasa/
├── .env.example                 # Template for environment variables
├── .env.local                   # Local Supabase credentials (gitignored)
├── .github/workflows/
│   ├── scrape-new.yml           # Hourly: scrape new listings
│   └── scrape-update.yml        # Every 12h: update existing listings
├── next.config.ts               # Next.js configuration
├── package.json                 # Dependencies and scripts
├── requirements.txt             # Python scraper dependencies
├── tsconfig.json                # TypeScript configuration
│
├── scraper_encuentra24.py       # 3,706 LOC — Multi-source scraper
├── area_normalizer.py           # Normalize area units to m²
├── match_locations.py           # Match listings to sv_loc_group hierarchy
├── scraper_el_salvador_locations.py  # Location data scraper
│
├── sql/                         # 23 SQL files — Database functions & migrations
│   ├── avm_functions.sql        # AVM: avm_nearest_matches + avm_value_point
│   ├── get_price_estimate.sql   # Dual-mode price estimation (coord / hierarchy)
│   ├── get_listings_for_cards_v2_location.sql  # Department listing cards
│   ├── fn_search_colonias.sql   # Colonia autocomplete
│   ├── fn_valuador_comps.sql    # Valuador comparables
│   ├── supabase_tag_functions.sql    # Tag-based listing queries
│   ├── get_municipalities_for_department.sql
│   ├── get_categories_for_department.sql
│   ├── create_sv_locations_table.sql
│   ├── insert_sv_locations*.sql # El Salvador location hierarchy seed data
│   ├── recreate_mv_*.sql        # Materialized view management
│   ├── update_*.sql             # Migration / function update scripts
│   └── ...                      # Cleanup, fix, migrate scripts
│
├── public/                      # Static assets (icons, placeholder images)
│
└── src/
    ├── app/
    │   ├── layout.tsx           # Root layout (fonts, metadata, Providers)
    │   ├── page.tsx             # Homepage (SSR)
    │   ├── sitemap.ts           # Dynamic sitemap (46 URLs)
    │   ├── about/page.tsx       # About page (398 LOC, FAQ, JSON-LD)
    │   ├── tendencias/page.tsx  # Market trends (SSR + client hydration)
    │   ├── valuador-de-inmuebles/page.tsx  # AVM tool (643 LOC)
    │   ├── favoritos/page.tsx   # Favorites + comparison (567 LOC)
    │   ├── inmuebles/[id]/page.tsx  # Individual listing detail (423 LOC)
    │   ├── [departamento]/
    │   │   └── [[...filter]]/page.tsx  # Department listings (473 LOC)
    │   └── api/                 # 13 API route handlers
    │       ├── colonias/route.ts
    │       ├── department-stats/route.ts
    │       ├── department/[slug]/
    │       │   ├── listings/route.ts
    │       │   ├── municipalities/route.ts
    │       │   └── top-scored/route.ts
    │       ├── geocode/route.ts
    │       ├── listing/[id]/route.ts
    │       ├── listings/
    │       │   ├── route.ts
    │       │   └── batch/route.ts
    │       ├── nearby-listings/route.ts
    │       ├── reverse-geocode/route.ts
    │       ├── tag/[tag]/route.ts
    │       └── valuador/route.ts
    │
    ├── components/              # 32 React components
    │   ├── MapExplorer.tsx       # 707 LOC — Interactive Leaflet map
    │   ├── ListingModal.tsx      # 397 LOC — Property detail modal
    │   ├── TendenciasClient.tsx  # Market trends client component
    │   ├── Navbar.tsx            # Global navigation bar
    │   ├── HeroSection.tsx       # Homepage hero
    │   ├── DepartmentCard.tsx    # Department summary card
    │   ├── ListingCard.tsx       # Property listing card
    │   ├── LazyImage.tsx         # Lazy-loading image component
    │   ├── BestOpportunitySection.tsx  # Top-scored listings
    │   ├── FiltersPanel.tsx      # Filter controls panel
    │   ├── DepartmentFilterBar.tsx    # Department-level filter bar
    │   ├── MarketRankingCharts.tsx    # ECharts-based ranking charts
    │   ├── RankingsSection.tsx   # Rankings section container
    │   ├── RankingCard.tsx       # Individual ranking card
    │   ├── TrendsSection.tsx     # Trends section container
    │   ├── TrendsInsights.tsx    # Trend insight cards
    │   ├── KPIStrip.tsx          # Key performance indicator strip
    │   ├── KPICard.tsx           # Individual KPI card
    │   ├── LocationCard.tsx      # Location info card
    │   ├── SectionHeader.tsx     # Reusable section header
    │   ├── JsonLd.tsx            # JSON-LD structured data injector
    │   ├── ActiveFilterChips.tsx # Active filter chip display
    │   ├── MunicipalityFilterChips.tsx # Municipality filter chips
    │   ├── TagFilterChips.tsx    # Tag-based filter chips
    │   ├── PriceRangePopover.tsx # Price range selector popover
    │   ├── FeatureCards.tsx      # Feature highlight cards
    │   ├── HomeHeader.tsx        # Homepage header
    │   ├── DashboardHeader.tsx   # Dashboard header
    │   ├── DepartmentCardBI.tsx  # BI-enhanced department card
    │   ├── InsightsPanel.tsx     # Insights display panel
    │   ├── ListingsView.tsx      # Listings grid/list view
    │   └── UnclassifiedCard.tsx  # Unclassified listing card
    │
    ├── hooks/
    │   ├── useFavorites.tsx      # 163 LOC — Cookie-based favorites (max 25)
    │   └── useDepartmentFilters.ts  # 160 LOC — Filter state management
    │
    ├── lib/
    │   ├── slugify.ts            # 62 LOC — Department ↔ slug conversion (14 departments)
    │   ├── seo.ts                # 248 LOC — Schema.org JSON-LD generators
    │   ├── biCalculations.ts     # 267 LOC — BI metrics (percentile, stats, insights)
    │   ├── Providers.tsx         # React context providers wrapper
    │   └── polyfillStub.js       # Empty module to stub legacy polyfills
    │
    ├── data/
    │   └── departamentos.ts     # El Salvador location hierarchy & detection
    │
    └── types/
        ├── listing.ts           # 72 LOC — Listing, ListingLocation, ListingContactInfo, LocationStats
        └── biStats.ts           # BI statistics type definitions
```

---

## 4. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER  (Browser)                              │
│  ┌─────────┐  ┌──────────┐  ┌───────────┐  ┌───────────────────┐   │
│  │ Homepage │  │  Dept.   │  │ Tendencias│  │  Valuador (AVM)   │   │
│  │ + Hero   │  │ Listings │  │ (Trends)  │  │  Property Valuer  │   │
│  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └────────┬──────────┘   │
│       │              │              │                  │              │
│  ┌────┤──── MapExplorer (Leaflet) ──┤──── ListingModal ┤            │
│  │    │              │              │                  │              │
└──┼────┼──────────────┼──────────────┼──────────────────┼──────────────┘
   │    │              │              │                  │
   ▼    ▼              ▼              ▼                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│               Next.js API Routes  (13 handlers)                      │
│  /api/department-stats  /api/nearby-listings  /api/valuador          │
│  /api/listings          /api/colonias         /api/geocode           │
│  /api/listing/[id]      /api/tag/[tag]        /api/reverse-geocode   │
│  /api/listings/batch    /api/department/[slug]/top-scored             │
│  /api/department/[slug]/listings  /api/department/[slug]/municipalities│
└──────────────────────────┬───────────────────────────────────────────┘
                           │  HTTP (fetch + headers)
                           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    Supabase (PostgreSQL + PostGIS)                    │
│                                                                      │
│  TABLES:                                                             │
│    scrappeddata_ingest (alias: scrapped_data)                        │
│    listing_location_match                                            │
│    sv_loc_group2 (colonias)                                          │
│    sv_loc_group3 (municipios)                                        │
│    sv_loc_group4 (distritos)                                         │
│    sv_loc_group5 (departamentos)                                     │
│                                                                      │
│  MATERIALIZED VIEWS:                                                 │
│    mv_sd_depto_stats (department statistics)                         │
│                                                                      │
│  RPC FUNCTIONS (20+):                                                │
│    get_listings_for_cards()     get_top_scored_listings()             │
│    get_listings_by_tag()        get_municipalities_for_department()   │
│    fn_listings_nearby_page()    fn_listing_price_stats_nearby()       │
│    avm_nearest_matches()        avm_value_point()                    │
│    search_colonias()            get_price_estimate()                 │
│    get_available_tags()         get_categories_for_department()       │
│    ... (additional utility functions)                                │
└──────────────────────────────────────────────────────────────────────┘
                           ▲
                           │  Python (Supabase REST API)
                           │
┌──────────────────────────────────────────────────────────────────────┐
│                    DATA PIPELINE (Python Scrapers)                    │
│                                                                      │
│  scraper_encuentra24.py  (3,706 LOC — Multi-source scraper)          │
│  ├── Sources: Encuentra24, MiCasaSV, Realtor, VivoLatam             │
│  ├── Modes: NEW (scrape new) | UPDATE (re-scrape existing)          │
│  ├── Validation: deactivate 404/sold listings                       │
│  ├── Listing-type correction heuristics                             │
│  └── Concurrent scraping (ThreadPoolExecutor)                       │
│                                                                      │
│  area_normalizer.py     → Normalize all area units to m²            │
│  match_locations.py     → Match listings to sv_loc_group hierarchy   │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 5. Frontend — Pages & Routing

### 5.1 Homepage (`src/app/page.tsx`)

Server-rendered landing page with:
- `HeroSection` with property counts
- `DepartmentCard` grid for all 14 El Salvador departments
- `MapExplorer` for interactive property discovery
- Fetches initial data via `/api/department-stats`

### 5.2 Department Page (`src/app/[departamento]/[[...filter]]/page.tsx`)

**473 LOC** — Client-side rendered with dynamic routing.

| URL Pattern | Filter |
|---|---|
| `/san-salvador` | All listings |
| `/san-salvador/venta` | Sale only |
| `/san-salvador/renta` | Rent only |

Features:
- Paginated listing grid (24 per page) via `get_listings_for_cards` RPC
- "Best Opportunities" section via `get_top_scored_listings` RPC
- Municipality filter chips from `get_municipalities_for_department` RPC
- Category filter chips from `get_categories_for_department` RPC
- Price range filtering, sort options (price_asc, price_desc, recent)
- `ListingModal` for inline detail view
- URL syncing via `window.history.replaceState` (no full-page navigation)

### 5.3 Tendencias Page (`src/app/tendencias/page.tsx`)

**113 LOC** — Server-rendered page with client hydration via `TendenciasClient`.
- Fetches `mv_sd_depto_stats` materialized view
- Uses `unstable_cache` with 5-minute revalidation
- Groups data by department, computes sale/rent stats
- Renders market ranking charts (ECharts), trends, insights

### 5.4 Valuador Page (`src/app/valuador-de-inmuebles/page.tsx`)

**643 LOC** — Client-side AVM tool.
- `LocationAutocomplete` using Nominatim via `/api/geocode`
- Property type selector (Casa, Apartamento, Local, Lote)
- Calls `/api/valuador` → `avm_value_point` RPC
- Displays: estimated value, range (low/high), confidence %, price/m², comparable properties
- Rent estimation and 12-month projection

### 5.5 Favoritos Page (`src/app/favoritos/page.tsx`)

**567 LOC** — Client-side favorites management.
- Reads favorites from `useFavorites` context (cookie-based, max 25)
- Batch-fetches full listing data via `/api/listings/batch`
- **Compare mode**: select up to 4 same-type listings, renders side-by-side comparison table
- Best-value highlighting (⭐) for price, bedrooms, bathrooms, area, parking
- Share and remove-from-favorites actions

### 5.6 Inmuebles Detail Page (`src/app/inmuebles/[id]/page.tsx`)

**423 LOC** — Individual property detail view.
- Fetches single listing via `/api/listing/[id]`
- Image gallery with prev/next navigation (keyboard support)
- Full specs display: bedrooms, bathrooms, area, parking, description
- Tags, location info, contact info
- Favorite toggle, share button, external source link
- Price formatting, area-unit normalization

### 5.7 About Page (`src/app/about/page.tsx`)

**398 LOC** — Static informational page.
- FAQ sections (Real Estate + SivarCasas-specific) with `<details>` accordions
- Schema.org FAQPage JSON-LD structured data
- Benefits, tools, "how it works" pipeline, data sources, team description
- Disclaimer section

### 5.8 Sitemap (`src/app/sitemap.ts`)

Generates 46 URLs:
- 4 static pages (home, tendencias, valuador, about)
- 42 department pages (14 departments × 3 variants: all, venta, alquiler)

---

## 6. Frontend — Components

### Core Components (32 total)

| Component | LOC | Purpose |
|---|---|---|
| **MapExplorer** | 707 | Interactive Leaflet map with marker clustering, nearby search, price/m² stats |
| **ListingModal** | 397 | Full-screen property detail modal with image carousel, specs, AVM data |
| **TendenciasClient** | ~500 | Client-side trends dashboard (charts, rankings, insights) |
| **Navbar** | ~100 | Global navigation with links to all pages + favoritos count badge |
| **HeroSection** | ~120 | Homepage hero with property count display |
| **ListingCard** | ~150 | Reusable property card (image, price, specs, tags, favorite toggle) |
| **LazyImage** | ~50 | Image component with lazy-loading + placeholder fallback |
| **BestOpportunitySection** | ~200 | Top-scored listings carousel for department pages |
| **FiltersPanel** | ~180 | Slide-out filter panel (price, municipio, category) |
| **DepartmentFilterBar** | ~100 | Horizontal filter bar (listing type, sort, price range) |
| **MarketRankingCharts** | ~300 | ECharts bar/line charts for department rankings |
| **KPIStrip** / **KPICard** | ~80 | National-level KPI display (median prices, active count, new 7d) |
| **SectionHeader** | ~30 | Reusable two-tone section header (bold + colored) |

### Filter & UI Components

| Component | Purpose |
|---|---|
| **ActiveFilterChips** | Display/dismiss active filter chips |
| **MunicipalityFilterChips** | Clickable municipality filter chips |
| **TagFilterChips** | Property-type tag filter chips |
| **PriceRangePopover** | Min/max price slider popover |
| **LocationCard** | Location info display card |
| **RankingCard** | Department ranking card with stats |
| **DepartmentCardBI** | BI-enhanced department card with percentiles |
| **InsightsPanel** | Market insights (top activity, trends) |
| **JsonLd** | Schema.org JSON-LD script injector |

---

## 7. Frontend — Hooks & Context

### `useFavorites` (163 LOC)

Cookie-based favorites system with React Context.

```
Cookie: sivarcasas_favorites = JSON array of external_id strings
Max-Age: 7 days
Max Favorites: 25
```

**API:**
- `isFavorite(id)` — check if listing is favorited
- `toggleFavorite(id)` — add/remove (returns `boolean` indicating if added)
- `addFavorite(id)` / `removeFavorite(id)` — explicit add/remove
- `clearFavorites()` — remove all
- `isAtLimit` — boolean, true when at 25
- `limitMessage` — auto-dismissing toast message when limit reached

**Provider:** `<FavoritesProvider>` wraps the app in `layout.tsx` via `Providers.tsx`.

### `useDepartmentFilters` (160 LOC)

Client-side filter state management for department listing pages.

**State:**
- `listingType: 'all' | 'sale' | 'rent'`
- `sort: 'price_asc' | 'price_desc' | 'recent'`
- `priceMin / priceMax: number | null`
- `municipios: string[]`
- `categories: string[]`

**Derived:**
- `activeChips: FilterChip[]` — computed active filter chips
- `hasActiveFilters` — boolean
- `priceLabel` — formatted price range string

**URL Sync:** Uses `window.history.replaceState` to update URL without Next.js navigation when switching listing type.

---

## 8. Frontend — Lib Utilities

### `slugify.ts` (62 LOC)

Bidirectional mapping between department names and URL slugs for all 14 El Salvador departments.

| Function | Purpose |
|---|---|
| `departamentoToSlug("San Salvador")` | → `"san-salvador"` |
| `slugToDepartamento("san-salvador")` | → `"San Salvador"` |
| `getAllDepartamentoSlugs()` | Returns all 14 valid slugs |
| `isValidDepartamentoSlug(slug)` | Validation check |

### `seo.ts` (248 LOC)

Schema.org JSON-LD structured data generators:

| Function | Schema Type |
|---|---|
| `generateOrganizationSchema()` | `RealEstateAgent` |
| `generateWebSiteSchema()` | `WebSite` with `SearchAction` |
| `generateListingSchema(input)` | `RealEstateListing` with `Offer` |
| `generateItemListSchema(items, url, name)` | `ItemList` (max 10 items) |
| `generateBreadcrumbSchema(items)` | `BreadcrumbList` |
| `generateDepartmentPageSchema(name, stats)` | `CollectionPage` |
| `generateFaqSchema(items)` | `FAQPage` |

### `biCalculations.ts` (267 LOC)

Business-intelligence computation utilities:

| Function | Purpose |
|---|---|
| `calculatePercentile(values, p)` | Statistical percentile (P25, P50, P75) |
| `calculateNationalStats(listings)` | Median sale/rent, active count, 7d new |
| `calculateDepartmentBIStats(listings, filter)` | Per-department stats with municipio breakdown |
| `calculateInsights(departments)` | Top 3 active municipios (7d) |
| `calculateHomeBIData(listings, filter)` | Main aggregation function |
| `formatPrice(price)` / `formatTrend(pct)` | Display formatters |

### `Providers.tsx`

Wraps all global React context providers. Currently wraps `<FavoritesProvider>`.

---

## 9. Frontend — Types

### `listing.ts` (72 LOC) — Single Source of Truth

```typescript
interface Listing {
  external_id: string | number;  // string to avoid precision loss for large IDs
  title: string;
  price: number;
  listing_type: 'sale' | 'rent';
  // Optional fields
  id?: number;
  url?: string;
  source?: string;
  currency?: string;
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
```

### `biStats.ts`

Types for BI calculations: `NationalStats`, `DepartmentBIStats`, `MunicipioStats`, `Insights`, `InsightItem`, `HomeBIData`.

---

## 10. API Layer (Next.js Route Handlers)

All API routes act as **proxies** to Supabase REST/RPC endpoints. No ORM — direct HTTP `fetch` to Supabase with `apikey` / `Authorization` headers.

### Common Pattern

```typescript
const url = `${process.env.SUPABASE_URL}/rest/v1/rpc/<function_name>`;
const res = await fetch(url, {
  method: 'POST',
  headers: {
    'apikey': process.env.SUPABASE_SERVICE_KEY!,
    'Authorization': `Bearer ${process.env.SUPABASE_SERVICE_KEY!}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({ ...params }),
  next: { revalidate: <seconds> }
});
```

**BigInt Safety:** All routes fetching listings apply regex to convert large `external_id` values (15+ digits) to strings before `JSON.parse` to avoid JavaScript precision loss:
```typescript
rawText.replace(/"external_id":(\d{15,})/g, '"external_id":"$1"')
```

### Route Inventory

| Route | Method | Supabase Target | Cache | Purpose |
|---|---|---|---|---|
| `/api/department-stats` | GET | `mv_sd_depto_stats` (view) | 5 min + in-memory | Department statistics grouped by sale/rent |
| `/api/listings` | GET | `scrappeddata_ingest` (table) | 5 min | All listings ordered by `last_updated` |
| `/api/listing/[id]` | GET | `scrappeddata_ingest` (table) | 1 min | Single listing by `external_id` |
| `/api/listings/batch` | GET | `scrappeddata_ingest` (table, IN) | 1 min | Multiple listings by comma-separated IDs |
| `/api/nearby-listings` | GET | `fn_listing_price_stats_nearby` + `fn_listings_nearby_page` (RPCs) | 60 sec | Nearby listings + price stats by lat/lng/radius |
| `/api/department/[slug]/listings` | GET | `get_listings_for_cards` (RPC) | — | Paginated department listings with filters |
| `/api/department/[slug]/top-scored` | GET | `get_top_scored_listings` (RPC) | 5 min | Top-scored listings for department |
| `/api/department/[slug]/municipalities` | GET | `get_municipalities_for_department` (RPC) | — | Municipality list for department |
| `/api/tag/[tag]` | GET | `get_listings_by_tag` (RPC) | 1 min | Listings by tag with type/sort filtering |
| `/api/colonias` | GET | `search_colonias` (RPC) | 1 hour | Colonia autocomplete search |
| `/api/geocode` | GET | Nominatim API (external) | 1 hour | Forward geocoding proxy |
| `/api/reverse-geocode` | GET | Nominatim API (external) | 24 hours | Reverse geocoding proxy |
| `/api/valuador` | POST | `avm_value_point` + `avm_nearest_matches` (RPCs) | — | AVM property valuation |

### Special Behaviors

- **`/api/tag/[tag]`**: Applies a post-fetch filter to exclude "Casa" sales under $15,000 (likely misclassified lot/land listings)
- **`/api/nearby-listings`**: Calls two RPCs in parallel (`Promise.all`), supports pagination and sorting
- **`/api/geocode`**: Strips accents from queries for better OSM matching; uses custom User-Agent `ChivocasaBot/1.0`
- **`/api/reverse-geocode`**: Constructs human-readable place names from Nominatim address components

---

## 11. Database — Supabase / PostgreSQL

### Core Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `scrappeddata_ingest` (alias `scrapped_data`) | All scraped listings | `external_id`, `title`, `price`, `listing_type`, `location` (JSONB), `specs` (JSONB), `images` (JSONB), `tags` (JSONB), `active`, `source`, `url`, `published_date`, `last_updated` |
| `listing_location_match` | Links listings to location hierarchy | `external_id`, `loc_group2_id`, `loc_group3_id`, `loc_group4_id`, `loc_group5_id` |

### Location Hierarchy (5 levels)

```
sv_loc_group5  — Departamento (14)   e.g. "San Salvador"
  └── sv_loc_group4  — Distrito       e.g. "Centro"
        └── sv_loc_group3  — Municipio  e.g. "San Salvador" (city)
              └── sv_loc_group2  — Colonia   e.g. "Escalón"
                    └── (listings via listing_location_match)
```

Each level has: `id`, `loc_name`, `parent_loc_group`, `cords` (JSONB with lat/lng centroid).

### Materialized Views

| View | Purpose | Refresh |
|---|---|---|
| `mv_sd_depto_stats` | Department-level stats (count, min/max/avg price) by listing_type | Periodic (via SQL refresh) |

### Key RPC Functions (20+)

| Function | Parameters | Returns | Used By |
|---|---|---|---|
| `get_listings_for_cards` | departamento, listing_type, limit, offset, sort_by, municipio | Paginated lean listing cards | Department page |
| `get_top_scored_listings` | departamento, listing_type, top_per_type | Best-value listings | Department page |
| `get_listings_by_tag` | tag, listing_type, limit, offset, sort_by | Tag-filtered listings | Tag pages |
| `get_municipalities_for_department` | departamento | Municipality list with counts | Department filter |
| `get_categories_for_department` | departamento | Category list | Department filter |
| `fn_listings_nearby_page` | lat, lng, radius, etc. | Paginated nearby listings | Map explorer |
| `fn_listing_price_stats_nearby` | lat, lng, radius | Price stats (median, min, max) | Map explorer |
| `search_colonias` | query | Matching colonias with coords | Valuador autocomplete |
| `avm_nearest_matches` | lat, lng, area_m2, type, class, etc. | Weighted comparable listings | AVM engine |
| `avm_value_point` | lat, lng, area_m2, type, class, etc. | Estimated value + confidence | AVM engine |
| `get_price_estimate` | lat, lng, bedrooms, bathrooms, etc. | Median price stats | Price estimation |
| `get_available_tags` | — | Distinct tags | UI filters |

---

## 12. AVM (Automated Valuation Model)

The AVM is implemented as two PostgreSQL/PostGIS functions:

### `avm_nearest_matches` (453 LOC SQL)

**Purpose:** Find and rank comparable properties using a multi-factor weighted scoring system.

**Radius Ladder:** Tries expanding radii `[1km, 2km, 3km, 5km, 8km, 12km, 20km]` until `min_comps` (default 8) are found. Falls back to national mode if insufficient.

**Filters:**
- Same `listing_type` (sale/rent)
- Same `property_class` (matched via tags or details)
- Area within 60%–180% of subject
- Max age: 180 days
- Coordinates (PostGIS `ST_DWithin`)

**Weighting (multiplicative):**

| Weight | Formula | Decay |
|---|---|---|
| Distance | `exp(-dist / (radius/2))` | Exponential, radius-normalized |
| Freshness | `exp(-days / 60)` | 60-day half-life |
| Status | Active=1.0, Recent inactive=0.7, Old inactive=0.45 | Step function |
| Size | `exp(-|ln(area_comp/area_subject)| / 0.35)` | Log-ratio decay |
| Features | `exp(-|bed_diff|/1.5) × exp(-|bath_diff|/1.0) × exp(-|park_diff|/1.0)` | Per-feature decay |

**Outlier Removal:** IQR-based trimming on price/m² (1.5× IQR fence).

**Output:** Ranked list of comparables with all weights, distances, and price metrics.

### `avm_value_point`

**Purpose:** Produce a single valuation estimate from `avm_nearest_matches`.

- Calls `avm_nearest_matches` with `limit = max(min_comps×4, 30)`
- Computes weighted average price/m² and P25/P75
- **Confidence score:** `min(0.95, min(1, count/15) × exp(-dispersion))`
- **Insufficient data:** Returns error when `count < max(4, min_comps/2)`
- **Estimate:** `area_m2 × weighted_avg_ppm2`
- **Range:** `area_m2 × P25` to `area_m2 × P75`

### Frontend Integration

The `/api/valuador` route calls both `avm_value_point` and `avm_nearest_matches` in parallel, then enriches the response with:
- Rent estimation (via separate `avm_value_point` call with `listing_type='rent'`)
- 12-month price projection (3% appreciation rate)
- Top comparable properties formatted for display

---

## 13. Data Pipeline — Scrapers

### `scraper_encuentra24.py` (3,706 LOC)

**Multi-source concurrent scraper** with the following capabilities:

| Mode | Trigger | Behavior |
|---|---|---|
| **NEW** | `scrape-new.yml` (hourly) | Scrape new listings from all sources |
| **UPDATE** | `scrape-update.yml` (every 12h) | Re-scrape existing active listings, detect sold/removed |

**Data Sources:**

| Source | Method | Content |
|---|---|---|
| Encuentra24 | HTML scraping (BeautifulSoup) | Houses, apartments, lots, commercial |
| MiCasaSV | HTML scraping | Similar property types |
| Realtor | HTML scraping | International listings in SV |
| VivoLatam | HTML scraping | Latin American property platform |

**Key Functions (63 total):**

| Function | Purpose |
|---|---|
| `insert_listing()` / `insert_listings_batch()` | Upsert listings to Supabase |
| `get_active_listings_from_db()` | Paginated fetch of active listings (bypasses 1000-row limit) |
| `update_listings_batch()` | PATCH existing records |
| `run_update_mode()` | Re-scrape + mark inactive |
| `validate_and_deactivate_listings()` | HTTP-check stale listings, deactivate 404/sold |
| `validate_all_active_listings()` | Lightweight URL validation of all active listings |
| `correct_listing_type()` | Heuristic correction of misclassified sale/rent |
| `generate_location_tags()` | Property type tag generation |
| `parse_price()` | Price string → float parsing |

**Post-Processing Pipeline:**

```
Scrape → insert_listings_batch()
       → area_normalizer.normalize_listing_specs()  (standardize m²)
       → match_locations.match_scraped_listings()    (link to sv_loc_group)
```

**Listing Type Correction Heuristics:**
- URL path analysis (`/venta/`, `/alquiler/`)
- Title keyword matching (VENDO, SE VENDE, ALQUILO, SE ALQUILA)
- Price anomaly detection (rentals priced > $200K likely sales; sales < $200/month likely rentals)
- Description keyword scanning

---

## 14. CI/CD — GitHub Actions

### `scrape-new.yml`

| Setting | Value |
|---|---|
| **Trigger** | Cron: hourly (`0 * * * *`) + manual dispatch |
| **Runner** | `ubuntu-latest` |
| **Steps** | Checkout → Python 3.11 → install `requirements.txt` → run scraper |
| **Secrets** | `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` |

### `scrape-update.yml`

| Setting | Value |
|---|---|
| **Trigger** | Cron: every 12 hours (`0 */12 * * *`) + manual dispatch |
| **Runner** | `ubuntu-latest` |
| **Steps** | Same as above but runs scraper in **update mode** |

---

## 15. SEO & Structured Data

### Meta Tags

Every page includes:
- `<title>` with descriptive, keyword-rich text
- `<meta name="description">` with compelling summaries
- OpenGraph tags (`og:title`, `og:description`, `og:url`, `og:type`)
- Twitter Card tags (`twitter:card`, `twitter:title`, `twitter:description`)
- Canonical URLs (`alternates.canonical`)
- `robots: { index: true, follow: true }`

### JSON-LD Structured Data

| Page | Schema Type |
|---|---|
| Homepage | `WebSite` + `Organization` (RealEstateAgent) |
| Department pages | `CollectionPage` + `ItemList` + `BreadcrumbList` |
| About page | `FAQPage` |
| Individual listings | `RealEstateListing` with `Offer` |

### Dynamic Sitemap

`src/app/sitemap.ts` generates 46 entries with:
- Daily change frequency for listing pages
- Weekly/monthly for static pages
- Priority weighting (home=1.0, departments=0.8, about=0.6)

---

## 16. Deployment & Infrastructure

| Aspect | Detail |
|---|---|
| **Hosting** | Vercel |
| **Domain** | `sivarcasas.com` |
| **Framework** | Next.js with App Router (RSC + Client Components) |
| **Image CDN** | Vercel Image Optimization (`sharp`) |
| **Analytics** | Vercel Analytics + Vercel Speed Insights |
| **Database** | Supabase hosted PostgreSQL (`zvamupbxzuxdgvzgbssn.supabase.co`) |
| **CSS** | Tailwind CSS v4 + `critters` for critical CSS inlining |
| **Polyfills** | Stubbed out (`polyfillStub.js`) to eliminate legacy JS |
| **Caching** | `next: { revalidate }` on fetch calls, `unstable_cache` for server-side |
| **Redirects** | `next.config.ts` redirects old department URLs (e.g. `/la-libertad` → correct slug) |

---

## 17. End-to-End Critical Flows

### Flow 1: User Browses Department Listings

```
1. User clicks "San Salvador" on homepage
2. → /san-salvador (DepartmentPage component mounts)
3. → URL parsed: slug="san-salvador", filter=undefined → type="all"
4. → Parallel fetches:
     a. GET /api/department/san-salvador/listings
        → Supabase RPC: get_listings_for_cards('San Salvador', null, 24, 0, 'recent', null)
     b. GET /api/department/san-salvador/top-scored
        → Supabase RPC: get_top_scored_listings('San Salvador', null, 5)
     c. GET /api/department/san-salvador/municipalities
        → Supabase RPC: get_municipalities_for_department('San Salvador')
5. → Listings rendered in 4-column grid
6. User clicks listing card → ListingModal opens
7. → GET /api/listing/{external_id}
     → Supabase table: scrappeddata_ingest WHERE external_id = {id}
8. → Modal displays full image gallery, specs, description, external link
```

### Flow 2: AVM Property Valuation

```
1. User navigates to /valuador-de-inmuebles
2. User types location → LocationAutocomplete
3. → GET /api/geocode?q={query}
     → Nominatim: nominatim.openstreetmap.org/search
4. User selects location, enters area_m2, property type, bedrooms, bathrooms
5. User clicks "Valuar"
6. → POST /api/valuador
     → Parallel Supabase RPCs:
       a. avm_value_point(lat, lng, area_m2, 'sale', 'casa', ...)
       b. avm_nearest_matches(lat, lng, area_m2, 'sale', 'casa', ...)
       c. avm_value_point(lat, lng, area_m2, 'rent', 'casa', ...) [rent estimate]
7. → AVM engine:
     a. Expand radius ladder: 1km → 2km → ... → 20km until ≥8 comps
     b. Filter: same type, same class, area ±60-180%, max 180 days old
     c. Weight each comp: distance × freshness × status × size × features
     d. IQR outlier removal on price/m²
     e. Weighted average price/m² → estimated_value = area × wppm2
     f. Confidence = min(0.95, min(1, count/15) × exp(-dispersion))
8. → Display: estimated value, range, confidence bar, top comparables table
```

### Flow 3: Map Explorer Nearby Search

```
1. User drags/zooms map on homepage or department page
2. → MapExplorer detects center change (debounced)
3. → GET /api/nearby-listings?lat={lat}&lng={lng}&radius={radius}
     → Parallel Supabase RPCs:
       a. fn_listing_price_stats_nearby(lat, lng, radius)
       b. fn_listings_nearby_page(lat, lng, radius, page, limit, sort)
4. → Map renders markers for nearby listings
5. → Stats panel shows median price, price/m², count
6. User clicks marker → ListingModal opens with full details
```

### Flow 4: Scraper Data Pipeline

```
1. GitHub Actions cron triggers scrape-new.yml (hourly)
2. → Python scraper launches concurrent workers per source
3. → Each source: parse HTML → extract listing data → correct listing type
4. → insert_listings_batch(): upsert to scrappeddata_ingest (batch of 50)
5. → area_normalizer.normalize_listing_specs(): standardize all areas to m²
6. → match_locations.match_scraped_listings(): link to sv_loc_group hierarchy
7.
   Every 12 hours:
   → scrape-update.yml triggers update mode
   → get_active_listings_from_db(): fetch all active listings
   → Re-scrape each listing URL, update prices/details
   → validate_and_deactivate_listings(): HTTP check stale listings
   → deactivate_listings(): mark 404/sold as inactive
```

---

## 18. Environment Variables

| Variable | Source | Used By |
|---|---|---|
| `SUPABASE_URL` | `.env.local` | All API routes, Tendencias SSR |
| `SUPABASE_SERVICE_KEY` | `.env.local` | All API routes (apikey + Bearer token) |
| `NEXT_PUBLIC_*` | — | None currently (all API calls server-side) |

**Note:** The scraper (`scraper_encuentra24.py`) has hardcoded Supabase credentials (not recommended for production). GitHub Actions workflows use repository secrets for the same values.

---

## 19. PWA — Progressive Web App

> **Fecha de implementación:** 2026-03-19  
> **Dependencias agregadas:** Ninguna (implementación 100% nativa)

### 19.1 Resumen Ejecutivo

SivarCasas es ahora una **Progressive Web App instalable** en Android (Chrome/Chromium) e iPhone (Safari). La implementación prioriza la seguridad de los datos en tiempo real sobre la experiencia offline: **nunca cachea endpoints dinámicos** de Supabase ni datos sensibles. Se construyó exclusivamente con capacidades nativas de Next.js App Router y vanilla JavaScript, sin `next-pwa`, `workbox` ni ninguna dependencia adicional.

### 19.2 Arquitectura PWA

```
┌──────────────────────────────────────────────────────────────────────┐
│                         BROWSER (Client)                             │
│                                                                      │
│  ┌─────────────┐   ┌──────────────────┐   ┌─────────────────────┐   │
│  │   App Shell  │   │  PWAInstallPrompt │   │  ServiceWorker      │   │
│  │  (Next.js)   │   │  (client comp.)  │   │  Registrar          │   │
│  └──────┬───────┘   └────────┬─────────┘   └──────────┬──────────┘   │
│         │                    │                         │              │
│         │    ┌───────────────┤                         │              │
│         │    │               │                         │              │
│         │    ▼               ▼                         ▼              │
│         │  beforeinstallprompt          navigator.serviceWorker       │
│         │  (Android Chrome)             .register('/sw.js')           │
│         │                               (solo producción)            │
│         │  iOS detection                                             │
│         │  (User-Agent + standalone)                                  │
│         │                                                            │
└─────────┼────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     SERVICE WORKER (sw.js)                            │
│                     Scope: / (raíz)                                  │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────────────┐  │
│  │   INSTALL     │  │   ACTIVATE    │  │         FETCH               │  │
│  │               │  │               │  │                            │  │
│  │ Pre-cache:    │  │ Clean old     │  │  /api/*    → NETWORK ONLY  │  │
│  │ • offline.html│  │ caches        │  │  POST/PUT  → SKIP          │  │
│  │               │  │               │  │  tiles/OSM → SKIP          │  │
│  │ skipWaiting() │  │ clients.claim │  │  /_next/s  → CACHE-FIRST   │  │
│  │               │  │               │  │  /icons/*  → CACHE-FIRST   │  │
│  └──────────────┘  └──────────────┘  │  fonts.*   → CACHE-FIRST   │  │
│                                       │  navigate  → NETWORK→OFFL  │  │
│                                       │  other     → NETWORK ONLY  │  │
│                                       └────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      CACHE STORAGE                                   │
│                      Name: 'sivarcasas-v1'                           │
│                                                                      │
│  Contenido (runtime):                                                │
│  • /offline.html (pre-cacheada en install)                           │
│  • /_next/static/**  (JS/CSS bundles, on-demand)                     │
│  • /icons/**  (PWA icons, on-demand)                                 │
│  • fonts.googleapis.com/**  (Google Fonts, on-demand)                │
│  • fonts.gstatic.com/**  (font files, on-demand)                     │
│                                                                      │
│  Tamaño estimado: ~2-5 MB (depende de bundles cargados)              │
└──────────────────────────────────────────────────────────────────────┘
```

### 19.3 Inventario de Archivos PWA

```
src/
├── app/
│   ├── manifest.ts              # [NEW] Genera /manifest.webmanifest (Next.js nativo)
│   └── layout.tsx               # [MODIFIED] +appleWebApp, +icons, +viewport, +PWA components
│
├── components/
│   ├── ServiceWorkerRegistrar.tsx  # [NEW] Registra SW en producción (0 UI)
│   └── PWAInstallPrompt.tsx        # [NEW] Banner Android + instrucciones iOS
│
public/
├── sw.js                        # [NEW] Service worker (~88 LOC vanilla JS)
├── offline.html                 # [NEW] Fallback offline (branded)
└── icons/                       # [NEW] Directorio de íconos PWA
    ├── android-chrome-192x192.png   (55 KB)
    ├── android-chrome-512x512.png   (298 KB)
    ├── apple-touch-icon.png         (49 KB)
    ├── favicon-16x16.png            (0.9 KB)
    ├── favicon-32x32.png            (2.6 KB)
    └── favicon.ico                  (15 KB)
```

### 19.4 Web App Manifest (`src/app/manifest.ts`)

Utiliza la API nativa de Next.js App Router (`MetadataRoute.Manifest`). Next.js se encarga automáticamente de:
- Generar el archivo JSON en la ruta `/manifest.webmanifest`
- Inyectar `<link rel="manifest">` en el `<head>` de todas las páginas
- Servir con el MIME type correcto (`application/manifest+json`)

**Configuración:**

| Campo | Valor | Justificación |
|---|---|---|
| `name` | "sivarcasas – Propiedades en El Salvador" | Nombre completo para diálogos de instalación |
| `short_name` | "sivarcasas" | Nombre bajo el ícono en home screen |
| `start_url` | `/` | Abre siempre en homepage |
| `display` | `standalone` | Sin barra de navegación del browser |
| `background_color` | `#0a0a0a` | Coincide con el background oscuro del body |
| `theme_color` | `#10b981` | Esmeralda — color de acento del proyecto |
| `icons` | 192px, 512px, 512px maskable | Cubre todos los requisitos de Android/PWA |

**Decisión arquitectónica:** Se eligió `manifest.ts` sobre un archivo estático `site.webmanifest` porque:
1. Se genera en build time y Next.js maneja el linking automático
2. Permite usar TypeScript y detectar errores de schema en compilación
3. No requiere configuración manual de `<link>` tags en el layout

### 19.5 Service Worker — Análisis Detallado (`public/sw.js`)

~88 líneas de vanilla JavaScript. Colocado en `public/` para ser servido en el **scope raíz** (`/`).

#### 19.5.1 Ciclo de vida

```
┌────────┐      ┌──────────┐      ┌────────┐
│ INSTALL │ ───▶ │ ACTIVATE  │ ───▶ │ FETCH   │
│         │      │           │      │ (loop)  │
│ cache   │      │ limpiar   │      │         │
│ offline │      │ caches    │      │ routing │
│ .html   │      │ antiguos  │      │ por URL │
│         │      │           │      │         │
│ skip    │      │ clients   │      │         │
│ Waiting │      │ .claim()  │      │         │
└────────┘      └──────────┘      └────────┘
```

- **`skipWaiting()`**: El nuevo SW toma control inmediatamente sin esperar que se cierren tabs existentes. Decisión conservadora: dado que solo cacheamos assets estáticos, no hay riesgo de inconsistencia de datos.
- **`clients.claim()`**: El SW controla todas las tabs abiertas inmediatamente después de activarse.

#### 19.5.2 Estrategia de routing por fetch

| Condición | Estrategia | Razón |
|---|---|---|
| `method !== 'GET'` | **Skip** (bypass SW) | POST del valuador, etc. — nunca interceptar |
| `pathname.startsWith('/api/')` | **Network-only** | 13 rutas API → Supabase en tiempo real |
| `hostname` incluye `tile`, `nominatim` | **Network-only** | Tiles OSM + geocoding externo |
| `pathname.startsWith('/_next/static/')` | **Cache-first** | JS/CSS bundles con hash (inmutables) |
| `pathname.startsWith('/icons/')` | **Cache-first** | Íconos PWA estáticos |
| `hostname` es `fonts.googleapis.com` o `fonts.gstatic.com` | **Cache-first** | Google Fonts (Inter) |
| `request.mode === 'navigate'` | **Network-first** → `/offline.html` | Páginas HTML: siempre frescas, offline como fallback |
| Cualquier otro | **Network-only** (fall-through) | Sin caché por defecto |

#### 19.5.3 Qué NUNCA se cachea (y por qué)

| Recurso excluido | Razón técnica |
|---|---|
| `/api/listings`, `/api/listing/[id]` | Datos cambian cada hora (scraper cron) |
| `/api/department/*/listings` | Paginados con filtros dinámicos |
| `/api/valuador` | POST con cálculos en tiempo real (AVM) |
| `/api/nearby-listings` | Depende de lat/lng del usuario |
| `/api/department-stats` | Materialized view con revalidación de 5 min |
| `/api/colonias`, `/api/geocode` | Autocompletado y geocoding en vivo |
| `/api/tags` | Catálogo dinámico de tags |
| Tiles OSM (`tile.openstreetmap.org`) | Volumen alto + política de uso OSM |
| Nominatim | Servicio externo con rate-limiting |

**Principio rector:** En una plataforma inmobiliaria donde los precios y disponibilidad cambian constantemente, servir datos desactualizados desde caché es **peor** que no tener datos. La estrategia es: **frescura de datos > disponibilidad offline**.

#### 19.5.4 Versioning y migración de caché

El cache se identifica como `sivarcasas-v1`. Al actualizar el SW:
1. Cambiar `CACHE_NAME` a `sivarcasas-v2`
2. El evento `activate` automáticamente elimina `sivarcasas-v1`
3. Los nuevos assets se cachean on-demand con la nueva versión

### 19.6 Registro del Service Worker (`ServiceWorkerRegistrar.tsx`)

Componente `'use client'` que:

```typescript
// Solo en producción (evita conflictos con HMR en dev)
if (process.env.NODE_ENV === 'production') {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js');
  });
}
```

**Decisiones de diseño:**
- **Solo producción:** En desarrollo, el Hot Module Replacement de Turbopack entra en conflicto con el SW interceptando requests de `/_next/`.
- **`window.load`:** Registra después del render inicial para no competir por bandwidth durante la carga.
- **Render null:** Cero impacto en el DOM.
- **Fuera de Providers:** No depende de `FavoritesProvider` ni ningún contexto React.

### 19.7 UX de Instalación (`PWAInstallPrompt.tsx`)

~230 LOC. Maneja dos plataformas con estrategias distintas:

#### Android (Chrome/Chromium)

```
beforeinstallprompt event
        │
        ▼
  ┌─────────────────┐
  │ e.preventDefault │  ← Captura el prompt nativo
  │ deferredPrompt   │  ← Guarda referencia en useRef
  │ setShowAndroid() │  ← Muestra banner custom
  └────────┬────────┘
           │
    Click "Instalar"
           │
           ▼
  ┌─────────────────┐
  │ prompt.prompt()  │  ← Dispara diálogo nativo de Chrome
  │ prompt.userChoice│  ← Espera aceptar/rechazar
  └────────┬────────┘
           │
     accepted ─── ocultar banner
     dismissed ── mantener para próxima visita
```

#### iOS (Safari)

Safari no soporta `beforeinstallprompt`. La detección es por User-Agent:

```typescript
function isIOS(): boolean {
  return (
    /iPad|iPhone|iPod/.test(navigator.userAgent) ||
    (navigator.userAgent.includes('Mac') && 'ontouchend' in document)
  );
}
```

La segunda condición cubre **iPad con iPadOS 13+** que reporta User-Agent de Mac desktop.

**Detección de standalone:**
```typescript
window.matchMedia('(display-mode: standalone)').matches
// fallback iOS:
navigator.standalone === true
```

**Dismissal:** Se guarda en `localStorage` con timestamp. El banner no vuelve a aparecer durante 7 días (`DISMISS_DAYS = 7`).

**Estilo visual:** Inline CSS con glassmorfismo (background semi-transparente + backdrop-filter blur) que coincide con el design system del proyecto (fondo oscuro #171717 al 95% opacidad, borde esmeralda, esquinas redondeadas 16px).

### 19.8 Integración con Apple / iOS

Metadata agregada en `layout.tsx` vía la API `Metadata` de Next.js:

```typescript
appleWebApp: {
  capable: true,           // <meta name="apple-mobile-web-app-capable" content="yes">
  statusBarStyle: 'black-translucent',  // Status bar sobre el contenido
  title: 'sivarcasas',     // Nombre sugerido al agregar a home screen
},
icons: {
  apple: [
    { url: '/icons/apple-touch-icon.png', sizes: '180x180', type: 'image/png' },
  ],
},
```

**`black-translucent`** se eligió sobre `default` o `black` porque permite que el contenido de la app se extienda debajo de la status bar, creando una experiencia más inmersiva que es consistente con el hero section full-bleed de la homepage.

### 19.9 Viewport y Theme Color

Se exporta `viewport` como objeto separado de `metadata` (requerido en Next.js 14+):

```typescript
export const viewport: Viewport = {
  themeColor: '#10b981',  // Esmeralda — colorea la barra de navegación en Android
};
```

Esto genera `<meta name="theme-color" content="#10b981">` que colorea la barra de estado/navegación del browser en Android cuando el sitio aún no está instalado como PWA.

### 19.10 Offline Fallback (`public/offline.html`)

Página HTML autónoma (sin dependencia de Next.js, React, ni CSS externo) que se muestra cuando:
1. El usuario no tiene conexión a internet
2. La página solicitada no está en caché
3. El service worker está activo

**Diseño:** Coincide con el tema visual del proyecto (background `#0a0a0a`, texto `#e5e5e5`, botón esmeralda `#10b981`, tipografía Inter). Incluye botón "Reintentar" que ejecuta `location.reload()`.

### 19.11 Integración con la Arquitectura Existente

| Componente existente | Impacto PWA | Detalle |
|---|---|---|
| **SSR / RSC** | ✅ Sin impacto | SW no intercepta rendering del servidor |
| **SEO (sitemap, robots, JSON-LD, canonical)** | ✅ Sin impacto | Archivos no modificados |
| **MapExplorer (Leaflet)** | ✅ Sin impacto | Tiles OSM excluidos del caché |
| **ListingModal** | ✅ Sin impacto | Datos siempre desde red |
| **Favoritos (cookies)** | ✅ Sin impacto | Navigation es network-first; cookies pasan al servidor |
| **Valuador (AVM)** | ✅ Sin impacto | POST excluido del SW por método |
| **Vercel Analytics / Speed Insights** | ✅ Sin impacto | Scripts de analytics no interferidos |
| **`unstable_cache` (Tendencias)** | ✅ Sin impacto | Caché del servidor, no del SW |
| **Redirects (next.config.ts)** | ✅ Sin impacto | Redirects son server-side |
| **`critters` (CSS crítico)** | ✅ Sin impacto | Inlining ocurre en build, no en runtime |

### 19.12 Flujo de Instalación End-to-End

#### Android

```
1. Usuario abre https://sivarcasas.com en Chrome
2. → Next.js sirve HTML con <link rel="manifest" href="/manifest.webmanifest">
3. → Chrome lee manifest: display=standalone, icons, start_url
4. → Chrome dispara evento 'beforeinstallprompt'
5. → PWAInstallPrompt.tsx intercepta, muestra banner
6. → Usuario toca "Instalar"
7. → prompt.prompt() → diálogo nativo de Chrome
8. → Usuario acepta → Chrome instala web app
9. → Acceso directo aparece en home screen/app drawer
10. → Al abrir: Chrome carga sivarcasas.com en modo standalone
    (sin barra de URL, con theme_color en status bar)
```

#### iPhone

```
1. Usuario abre https://sivarcasas.com en Safari
2. → Safari lee apple-mobile-web-app-capable=yes
3. → PWAInstallPrompt.tsx detecta iOS + no-standalone
4. → Muestra instrucciones: "Tocá Compartir → Agregar a pantalla de inicio"
5. → Usuario sigue las instrucciones en Safari
6. → iOS crea ícono con apple-touch-icon.png (180×180)
7. → Al abrir: Safari WebKit carga en modo standalone
    (status bar style: black-translucent)
```

### 19.13 Verificación y Resultados

| Prueba | Resultado |
|---|---|
| `npm run build` — compilación | ✅ Sin errores, 20 páginas |
| `/manifest.webmanifest` — contenido JSON | ✅ Válido, todos los campos correctos |
| `/sw.js` — servido con MIME type correcto | ✅ `application/javascript` |
| `/offline.html` — renderizado | ✅ Página branded con tema oscuro |
| `/icons/*` — 6 archivos accesibles | ✅ Todos cargan (192, 512, apple-touch, favicons) |
| Banner de instalación Android | ✅ `beforeinstallprompt` capturado, banner visible |
| Instrucciones iOS | ✅ Detección por UA funcional |
| Navegación existente | ✅ Home, departamentos, listings, favoritos, valuador, tendencias |
| API endpoints no cacheados | ✅ Verificado en código: 13 rutas excluidas |

### 19.14 Limitaciones Conocidas

| Limitación | Detalle | Severidad |
|---|---|---|
| **iOS: Sin install prompt nativo** | Safari no soporta `beforeinstallprompt`; se muestran instrucciones manuales | Baja (limitación del OS) |
| **Push notifications** | No implementadas | Baja (no necesarias para el caso de uso) |
| **Offline completo** | Solo fallback; páginas individuales no se cachean | Diseñado así (datos frescos > offline) |
| **Ícono maskable** | Usa el mismo PNG 512×512; debería tener safe zone dedicada | Cosmético |
| **SW solo producción** | No se puede probar en `npm run dev` (conflicto HMR) | Diseñado así |

---

> **End of document.** This file should be updated whenever significant architectural changes are made to the repository.
