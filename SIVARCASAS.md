# CHIVOCASAS.md - Documentación Técnica del Proyecto SivarCasas

---

## 1. RESUMEN EJECUTIVO DEL PROYECTO

| Campo | Descripción |
|-------|-------------|
| **Nombre del proyecto** | SivarCasas (ChivoCasas) - Índice Inmobiliario de El Salvador |
| **Dominio** | https://sivarcasas.com |
| **Propósito** | Plataforma de análisis de mercado inmobiliario que agrega propiedades de múltiples fuentes (Encuentra24, MiCasaSV, Realtor.com), clasifica por departamento/municipio, y presenta métricas BI + gráficos interactivos para entender el mercado salvadoreño. |
| **Stack tecnológico** | **Frontend:** Next.js 16.1.6, React 19.2.3, TypeScript 5, TailwindCSS 4, Apache ECharts 5, Leaflet/React-Leaflet. **Backend/Scraper:** Python 3.11, BeautifulSoup4, Requests, Supabase SDK. **Base de datos:** Supabase (PostgreSQL + Materialized Views + RPC Functions). **CI/CD:** GitHub Actions (scraping automatizado). **Analytics:** Vercel Analytics + Speed Insights. |
| **Estado actual** | Dashboard BI funcional con KPIs nacionales, grid de 14 departamentos con filtro global (Total/Venta/Renta), ranking de mercado con gráficos ECharts sincronizados al filtro, mapa interactivo con Leaflet, páginas de departamento con listings paginados, sistema de tags, "Best Opportunity" scoring, y scraper multi-fuente automatizado via GitHub Actions. |
| **Repositorio** | https://github.com/chivocasa42-sys/chivocasa.git |

---

## 2. ARQUITECTURA DEL PROYECTO

### 2.1 Estructura de Carpetas

```
/chivocasa
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── department-stats/
│   │   │   │   └── route.ts              # Stats agregados por depto (vista materializada + cache in-memory)
│   │   │   ├── department/
│   │   │   │   └── [slug]/route.ts        # Listings paginados por departamento (RPC)
│   │   │   ├── listing/
│   │   │   │   └── [id]/route.ts          # Detalle de un listing por external_id
│   │   │   ├── listings/
│   │   │   │   └── route.ts               # Todos los listings (legacy)
│   │   │   ├── geocode/
│   │   │   │   └── route.ts               # Proxy a Nominatim para geocodificación
│   │   │   ├── nearby-listings/
│   │   │   │   └── route.ts               # Listings cercanos por lat/lng + stats
│   │   │   ├── tag/
│   │   │   │   └── [tag]/route.ts         # Listings por tag (RPC)
│   │   │   └── tags/
│   │   │       └── route.ts               # Lista de tags disponibles (Edge Runtime)
│   │   │
│   │   ├── [departamento]/
│   │   │   ├── layout.tsx                 # SEO metadata + JSON-LD por departamento
│   │   │   └── [[...filter]]/
│   │   │       ├── page.tsx               # Página de departamento (listings, municipios, best opportunity)
│   │   │       └── loading.tsx            # Skeleton de carga
│   │   │
│   │   ├── tag/
│   │   │   └── [tag]/
│   │   │       ├── layout.tsx             # SEO metadata + JSON-LD por tag
│   │   │       └── [[...filter]]/
│   │   │           └── page.tsx           # Página de tag (listings filtrados)
│   │   │
│   │   ├── globals.css                    # Estilos globales (~2870 líneas, CSS vars, tema premium)
│   │   ├── layout.tsx                     # Root layout (Inter font, Vercel Analytics/SpeedInsights)
│   │   ├── template.tsx                   # JSON-LD Organization + WebSite schema
│   │   ├── page.tsx                       # Home: KPIs, filtro global, grid deptos, ranking charts, mapa
│   │   ├── opengraph-image.tsx            # OG image dinámico (Edge, @vercel/og)
│   │   └── twitter-image.tsx              # Twitter card image dinámico
│   │
│   ├── components/
│   │   ├── Navbar.tsx                     # Navbar con total activos + refresh
│   │   ├── HeroSection.tsx                # Hero con búsqueda de ubicación
│   │   ├── HomeHeader.tsx                 # Filtro global segmentado (Total/Venta/Renta)
│   │   ├── KPIStrip.tsx                   # 4 KPIs nacionales
│   │   ├── KPICard.tsx                    # Card individual de KPI
│   │   ├── FeatureCards.tsx               # Cards de features/beneficios
│   │   ├── SectionHeader.tsx              # Header reutilizable con título accent
│   │   ├── DepartmentCard.tsx             # Card de departamento con pill de filtro
│   │   ├── DepartmentCardBI.tsx           # Card de departamento con métricas BI (legacy)
│   │   ├── MarketRankingCharts.tsx        # 3 gráficos ECharts (caro/barato/activo) + cache + polling
│   │   ├── MapExplorer.tsx                # Mapa interactivo Leaflet con búsqueda y nearby listings
│   │   ├── ListingCard.tsx                # Card de propiedad individual
│   │   ├── ListingModal.tsx               # Modal de detalle de propiedad
│   │   ├── ListingsView.tsx               # Vista de listings con paginación
│   │   ├── LocationCard.tsx               # Card de municipio
│   │   ├── BestOpportunitySection.tsx     # Sección "Mejores Oportunidades" con scoring
│   │   ├── MunicipalityFilterChips.tsx    # Chips de filtro por municipio
│   │   ├── TagFilterChips.tsx             # Chips de filtro por tags
│   │   ├── RankingsSection.tsx            # Sección de rankings (texto)
│   │   ├── RankingCard.tsx                # Card individual de ranking
│   │   ├── InsightsPanel.tsx              # Panel de insights (top zonas activas)
│   │   ├── TrendsSection.tsx              # Sección de tendencias (legacy)
│   │   ├── TrendsInsights.tsx             # Insights de tendencias (legacy)
│   │   ├── LazyImage.tsx                  # Componente de imagen con lazy loading
│   │   ├── UnclassifiedCard.tsx           # Card para listings sin departamento
│   │   ├── DashboardHeader.tsx            # Header del dashboard (legacy)
│   │   └── JsonLd.tsx                     # Componente para inyectar JSON-LD
│   │
│   ├── data/
│   │   └── departamentos.ts               # Mapeo de 14 departamentos + 262 municipios + aliases
│   │
│   ├── lib/
│   │   ├── biCalculations.ts              # Funciones BI: percentiles, medianas, stats nacionales
│   │   ├── rankingChartsAdapter.ts        # Adapter: DepartmentStats → ECharts datapoints + filtro
│   │   ├── slugify.ts                     # Conversión departamento ↔ slug URL
│   │   ├── seo.ts                         # Generadores de Schema.org JSON-LD
│   │   └── imageCache.ts                  # Cache de imágenes client-side con cola de requests
│   │
│   └── types/
│       ├── listing.ts                     # Tipos: Listing, ListingSpecs, ListingLocation, LocationStats
│       └── biStats.ts                     # Tipos: NationalStats, DepartmentBIStats, MunicipioStats, Insights
│
├── public/
│   ├── js/
│   │   └── marketRankingCharts.js         # Apache ECharts interop (lifecycle, theme, resize)
│   ├── sitemap.xml                        # Sitemap estático (14 departamentos)
│   ├── robots.txt                         # Robots.txt
│   ├── logo.webp                          # Logo optimizado
│   └── placeholder.webp                   # Placeholder para imágenes
│
├── sql/                                   # Scripts SQL para Supabase
│   ├── get_listings_for_cards_v2_location.sql   # RPC: listings paginados por departamento
│   ├── get_municipalities_for_department.sql     # RPC: municipios con conteo
│   ├── get_price_estimate.sql                    # RPC: estimación de precio
│   ├── supabase_tag_functions.sql                # RPC: funciones de tags
│   ├── recreate_mv_with_location_match.sql       # Vista materializada de stats
│   ├── create_sv_locations_table.sql             # Tabla de ubicaciones SV
│   ├── insert_sv_locations.sql                   # Insert de ubicaciones
│   └── ... (17 archivos SQL total)
│
├── .github/workflows/
│   ├── scrape-new.yml                     # Cron: cada hora, scrape nuevos listings
│   └── scrape-update.yml                  # Cron: cada 12h, actualizar listings activos
│
├── scraper_encuentra24.py                 # Scraper multi-fuente Python (~146K)
├── match_locations.py                     # Matching de ubicaciones (~74K)
├── deduplication.py                       # Deduplicación de listings
├── listing_validator.py                   # Validación de listings
├── area_normalizer.py                     # Normalización de áreas (m²)
├── enrich_locations.py                    # Enriquecimiento de ubicaciones
├── localization_plugin.py                 # Plugin de localización
├── export_to_supabase.py                  # Exportación a Supabase
│
├── tests/
│   ├── test_deduplication.py              # Tests de deduplicación
│   ├── test_colon_fix.py                  # Tests de fix de colons
│   ├── debug_match.py                     # Debug de matching
│   └── debug_matching.py                  # Debug de matching avanzado
│
├── package.json                           # Dependencias Node.js
├── requirements.txt                       # Dependencias Python
├── next.config.ts                         # Config Next.js (images, redirects)
├── tsconfig.json                          # Config TypeScript
├── eslint.config.mjs                      # Config ESLint
├── postcss.config.mjs                     # Config PostCSS
├── run_dev.bat                            # Script de desarrollo Windows
└── CHIVOCASAS.md                          # Esta documentación
```

### 2.2 Flujo de Datos

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FUENTES DE DATOS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │   Encuentra24   │  │    MiCasaSV     │  │   Realtor.com   │             │
│  │   (HTML/CSS)    │  │   (WordPress)   │  │  (__NEXT_DATA__) │             │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘             │
│           └────────────────────┼────────────────────┘                       │
└────────────────────────────────┼────────────────────────────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │  GitHub Actions (CI/CD)  │
                    │  scrape-new: cada hora   │
                    │  scrape-update: cada 12h │
                    └────────────┬────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────────┐
              │        scraper_encuentra24.py             │
              │                                          │
              │  1. Fetch páginas (ThreadPoolExecutor)   │
              │  2. Parse HTML (BeautifulSoup)           │
              │  3. Extracción + normalización           │
              │  4. Detección de municipio/depto         │
              │  5. Deduplicación                        │
              │  6. Validación de listings               │
              └──────────────────┬───────────────────────┘
                                 │
                                 │ POST /rest/v1/scrappeddata_ingest
                                 ▼
              ┌──────────────────────────────────────────┐
              │          Supabase (PostgreSQL)            │
              │                                          │
              │  Tabla: scrappeddata_ingest               │
              │  Vista: mv_sd_depto_stats (materializada) │
              │  Tabla: sv_locations                       │
              │  RPC: get_listings_for_cards              │
              │  RPC: get_municipalities_for_department   │
              │  RPC: get_listings_by_tag                 │
              │  RPC: get_available_tags                  │
              │  RPC: get_price_estimate                  │
              └──────────────────┬───────────────────────┘
                                 │
                                 │ Next.js API Routes (8 endpoints)
                                 ▼
              ┌──────────────────────────────────────────┐
              │        Next.js 16 Dashboard BI           │
              │                                          │
              │  HOME:                                   │
              │  ├─ KPI Strip (métricas nacionales)      │
              │  ├─ Filtro global (Total/Venta/Renta)    │
              │  ├─ Grid 14 departamentos con pills      │
              │  ├─ Ranking Charts (ECharts, 3 gráficos) │
              │  └─ Mapa interactivo (Leaflet)           │
              │                                          │
              │  DEPARTAMENTO:                           │
              │  ├─ Listings paginados (24/página)       │
              │  ├─ Filtro por municipio (chips)          │
              │  ├─ Best Opportunity (scoring)            │
              │  └─ Modal de detalle                     │
              │                                          │
              │  TAG:                                    │
              │  ├─ Listings por tag                     │
              │  └─ Filtro por tipo (venta/renta)        │
              └──────────────────────────────────────────┘
```

---

## 3. API ROUTES

### 3.1 Endpoints

| Endpoint | Método | Runtime | Cache | Descripción |
|----------|--------|---------|-------|-------------|
| `/api/department-stats` | GET | Node | In-memory 30s + `Cache-Control: max-age=30, stale-while-revalidate=60` | Stats agregados por departamento desde `mv_sd_depto_stats`. Agrupa sale/rent y retorna `{departamento, sale, rent, total_count}[]`. |
| `/api/department/[slug]` | GET | Node | `no-store` (listings), `revalidate: 60` (municipios) | Listings paginados por departamento. Params: `limit`, `offset`, `type`, `sort`, `municipio`. Usa RPC `get_listings_for_cards` + `get_municipalities_for_department`. Filtra casas <$15K mal clasificadas. |
| `/api/listing/[id]` | GET | Edge | `revalidate: 60` | Detalle de un listing por `external_id`. |
| `/api/listings` | GET | Node | `revalidate: 300` | Todos los listings (legacy, tabla completa). |
| `/api/geocode` | GET | Node | `revalidate: 3600` | Proxy a Nominatim OpenStreetMap. Param: `q`. Normaliza acentos. |
| `/api/nearby-listings` | GET | Node | — | Listings cercanos por `lat`, `lng`, `radius`. Retorna stats de precio + listings paginados. |
| `/api/tag/[tag]` | GET | Edge | `revalidate: 60` | Listings por tag via RPC `get_listings_by_tag`. Params: `limit`, `offset`, `type`, `sort`. |
| `/api/tags` | GET | Edge | `revalidate: 300` | Lista de todos los tags disponibles via RPC `get_available_tags`. |

### 3.2 Cache Strategy

```
Browser ←── Cache-Control: max-age=30, stale-while-revalidate=60
         ←── X-Cache: HIT/MISS

Next.js  ←── In-memory TTL cache (30s) para department-stats
         ←── next: { revalidate: N } para fetch de Supabase

Client   ←── localStorage cache (5 min TTL) para ranking charts warm-start
         ←── ImageCacheManager (5 min, max 100 imágenes, 4 concurrent)
```

---

## 4. HOME - PÁGINA PRINCIPAL

### 4.1 Estructura del Home (`src/app/page.tsx`)

| Sección | Componente | Descripción |
|---------|------------|-------------|
| **Navbar** | `Navbar.tsx` | Logo, total activos, botón Refresh |
| **Hero** | `HeroSection.tsx` | Búsqueda de ubicación con autocompletado → puente al mapa |
| **Panorama** | `SectionHeader.tsx` | Título + disclaimer de valores estimados |
| **KPI Strip** | `KPIStrip.tsx` | Precio medio venta, renta típica, anuncios activos, nuevos 7d |
| **Mapa** | `MapExplorer.tsx` | Mapa Leaflet interactivo con búsqueda, markers, nearby listings |
| **Filtro Global** | `HomeHeader.tsx` | Segmented control: Total / Venta / Renta |
| **Grid Departamentos** | `DepartmentCard.tsx` | 14 cards con precio medio, rango, pill de filtro activo |
| **Ranking Charts** | `MarketRankingCharts.tsx` | 3 gráficos ECharts: Más Caros, Más Baratos, Más Activos |

### 4.2 Filtro Global (Total / Venta / Renta)

Estado: `view: 'all' | 'sale' | 'rent'` en `page.tsx`.

El filtro afecta simultáneamente:
- **Grid de departamentos:** filtra listings, ajusta precios mostrados (sale.avg, rent.avg, o weighted avg)
- **Ranking Charts:** `computeRankings(departments, view)` recalcula los 3 rankings según el filtro
- **Pills en cards:** cada card muestra TOTAL (verde), VENTA (azul), o RENTA (rojo)

El cambio de filtro es **inmediato** (no espera polling de 30s): un `useEffect` en `MarketRankingCharts` detecta el cambio de `activeFilter` y re-renderiza los gráficos al instante.

### 4.3 Ranking Charts — Performance

| Feature | Implementación |
|---------|---------------|
| **Warm-start** | `localStorage` cache (`mrc_ranking_cache`, TTL 5 min). Al volver a Home, renderiza datos cacheados instantáneamente y refresca en background. |
| **Script detection** | `scriptsAlreadyLoaded()` detecta si ECharts/interop ya están cargados (SPA return). |
| **Concurrency lock** | `fetchInFlight` ref previene fetches concurrentes. |
| **Lazy load** | `IntersectionObserver` con `rootMargin: 300px` + check inmediato con `getBoundingClientRect`. |
| **Instance reuse** | `echarts.getInstanceByDom()` reutiliza instancias existentes (no destruye en unmount). |
| **Polling** | Cada 30s, solo si la sección es visible. |
| **LIVE indicator** | Solo texto "LIVE" con dot verde + micro-pulse (scale 1.8, 400ms) al recibir datos frescos. |
| **Script strategy** | `afterInteractive` para carga rápida y `onLoad` confiable en SPA. |

### 4.4 Server-side Cache (`department-stats`)

```typescript
let memCache: { data: unknown; ts: number } | null = null;
const MEM_CACHE_TTL = 30_000; // 30 seconds
```

Evita re-consultar Supabase en cada poll de 30s. Retorna `X-Cache: HIT` si el cache es fresco.

---

## 5. PÁGINAS DE DEPARTAMENTO

### 5.1 Routing

```
/[departamento]                    → Todos los listings
/[departamento]/venta              → Solo venta
/[departamento]/renta              → Solo renta
```

Catch-all route: `src/app/[departamento]/[[...filter]]/page.tsx`

### 5.2 Features

- **Paginación:** 24 listings por página, infinite scroll con "Cargar más"
- **Filtro por municipio:** Chips con conteo de listings por municipio
- **Filtro por tipo:** Venta / Renta / Todos
- **Ordenamiento:** Recientes, Precio ↑, Precio ↓
- **Best Opportunity:** Scoring basado en precio/m², habitaciones, baños
- **Modal de detalle:** Galería de imágenes, specs, descripción, contacto
- **Filtro de misclassification:** Casas <$15K en venta se excluyen (probablemente rentas mal clasificadas)

### 5.3 SEO

- `generateMetadata()` dinámico por departamento + filtro
- JSON-LD: `BreadcrumbList` + `CollectionPage` schema
- Canonical URLs: `https://sivarcasas.com/[slug]`
- Redirects: `/tag/[dept]` → `/[dept]` (301 permanente)

---

## 6. SISTEMA DE TAGS

### 6.1 Routing

```
/tag/[tag]                         → Listings con ese tag
/tag/[tag]/venta                   → Solo venta
/tag/[tag]/renta                   → Solo renta
```

### 6.2 Implementación

- Tags almacenados como `string[]` en columna `tags` de `scrappeddata_ingest`
- RPC `get_available_tags` retorna todos los tags únicos
- RPC `get_listings_by_tag` retorna listings paginados filtrados por tag
- `TagFilterChips.tsx` muestra chips seleccionables con conteo
- Redirect legacy: `/tag/san-salvador` → `/san-salvador` (via `next.config.ts`)

---

## 7. MAPA INTERACTIVO

### 7.1 Componente: `MapExplorer.tsx`

- **Librería:** Leaflet + React-Leaflet
- **Tiles:** OpenStreetMap
- **Búsqueda:** Autocompletado via `/api/geocode` (proxy a Nominatim)
- **Nearby listings:** Al hacer click en el mapa, consulta `/api/nearby-listings` con radio configurable
- **Stats:** Muestra mediana de precio venta/renta en la zona seleccionada
- **Bridge:** `HeroSection` puede enviar una ubicación al mapa via prop `externalLocation`

---

## 8. COMPONENTES PRINCIPALES

### 8.1 Funciones de Cálculo BI (`src/lib/biCalculations.ts`)

| Función | Descripción |
|---------|-------------|
| `calculatePercentile(values, percentile)` | Calcula percentil de un array de números |
| `calculateNationalStats(listings)` | Stats nacionales: mediana venta/renta, total activos, tendencia |
| `calculateDepartmentBIStats(listings, filterType)` | Stats por departamento con municipios anidados |
| `calculateInsights(departments)` | Top 3 zonas más activas |
| `calculateHomeBIData(listings)` | Calcula todos los datos BI del Home en una sola llamada |
| `formatPrice(price)` | Formatea precio como `$XXX,XXX` |
| `formatTrend(pct)` | Formatea tendencia con flecha ↑↓ |
| `formatTime(date)` | Formatea fecha relativa |

### 8.2 Ranking Charts Adapter (`src/lib/rankingChartsAdapter.ts`)

| Función | Descripción |
|---------|-------------|
| `computeRankings(departments, view)` | Calcula top 3 caros, baratos, activos según filtro (all/sale/rent) |
| `toExpensiveDataPoints(items)` | Transforma rankings → datapoints ECharts (horizontal bar) |
| `toCheapDataPoints(items)` | Transforma rankings → datapoints ECharts (horizontal bar) |
| `toActiveDataPoints(items)` | Transforma rankings → datapoints ECharts (column chart) |
| `formatPriceCompact(price)` | Formatea: `$150K`, `$1.2M` |
| `getAvgPrice(dept, view)` | Precio promedio según filtro (sale.avg, rent.avg, o weighted) |
| `getCount(dept, view)` | Conteo según filtro (sale.count, rent.count, o total_count) |

### 8.3 Slugify (`src/lib/slugify.ts`)

| Función | Descripción |
|---------|-------------|
| `departamentoToSlug(name)` | `"San Salvador"` → `"san-salvador"` |
| `slugToDepartamento(slug)` | `"san-salvador"` → `"San Salvador"` |
| `getAllDepartamentoSlugs()` | Retorna los 14 slugs válidos |
| `isValidDepartamentoSlug(slug)` | Valida si un slug corresponde a un departamento |

### 8.4 SEO (`src/lib/seo.ts`)

| Función | Descripción |
|---------|-------------|
| `generateOrganizationSchema()` | Schema.org `RealEstateAgent` |
| `generateWebSiteSchema()` | Schema.org `WebSite` con `SearchAction` |
| `generateBreadcrumbSchema(items)` | Schema.org `BreadcrumbList` |

### 8.5 Image Cache (`src/lib/imageCache.ts`)

Singleton `ImageCacheManager` client-side:
- Max 4 requests concurrentes
- Cache de 5 minutos, max 100 imágenes
- Cola de requests con listeners por URL
- Evita duplicar fetches para la misma imagen

### 8.6 ECharts Interop (`public/js/marketRankingCharts.js`)

Script vanilla JS que expone `window.MarketRankingCharts`:

| Método | Descripción |
|--------|-------------|
| `initCharts(config)` | Inicializa 3 gráficos ECharts en los contenedores dados |
| `updateAllCharts(exp, cheap, active)` | Actualiza datos con `setOption` (merge, sin parpadeo) |
| `destroyCharts()` | Destruye instancias y limpia observers |
| `isReady()` | Verifica si `echarts` está disponible |

Features: extracción de theme tokens desde CSS vars, `ResizeObserver` para responsive, click handler en barras para navegación, `getInstanceByDom()` para reutilización de instancias.

---

## 9. TIPOS DE DATOS

### 9.1 Listing (`src/types/listing.ts`)

```typescript
export interface Listing {
    // Core (requeridos para cards)
    external_id: string | number;
    title: string;
    price: number;
    listing_type: 'sale' | 'rent';

    // Opcionales
    id?: number;
    url?: string;
    source?: string;                    // "Encuentra24" | "MiCasaSV" | "Realtor"
    currency?: string;
    tags?: string[] | null;
    location?: ListingLocation;         // JSONB con municipio_detectado
    description?: string;
    specs?: ListingSpecs | null;        // bedrooms, bathrooms, área, etc.
    details?: Record<string, string>;
    images?: string[] | null;
    contact_info?: ListingContactInfo;  // nombre, telefono, whatsapp
    published_date?: string;
    scraped_at?: string;
    last_updated?: string;
}

export interface LocationStats {
    count: number;
    listings: Listing[];
    avg: number;
    min: number;
    max: number;
}
```

### 9.2 Estadísticas BI (`src/types/biStats.ts`)

```typescript
export interface NationalStats {
    median_sale: number;
    median_rent: number;
    total_active: number;
    new_7d: number;
    new_prev_7d: number;
    updated_at: string;
    sources: string[];
}

export interface DepartmentBIStats {
    departamento: string;
    count_active: number;
    municipios_con_actividad: number;
    median_price: number;
    p25_price: number;
    p75_price: number;
    new_7d: number;
    trend_30d_pct: number;
    municipios: Record<string, MunicipioStats>;
}

export interface MunicipioStats {
    count: number;
    median_price: number;
    p25_price: number;
    p75_price: number;
    new_7d: number;
    listings: Listing[];
}

export interface InsightItem {
    municipio: string;
    departamento: string;
    value: number;
}

export interface Insights {
    top3_up_30d: InsightItem[];
    top3_down_30d: InsightItem[];
    top3_active_7d: InsightItem[];
}

export interface HomeBIData {
    national: NationalStats;
    departments: DepartmentBIStats[];
    insights: Insights;
    unclassified: { count: number; listings: Listing[] };
}
```

### 9.3 Department Stats (API response)

```typescript
// Retornado por /api/department-stats
interface DepartmentStatsResponse {
    departamento: string;
    sale: { count: number; min: number; max: number; avg: number } | null;
    rent: { count: number; min: number; max: number; avg: number } | null;
    total_count: number;
}
```

---

## 10. BASE DE DATOS (SUPABASE)

### 10.1 Tablas Principales

| Tabla/Vista | Tipo | Descripción |
|-------------|------|-------------|
| `scrappeddata_ingest` | Tabla | Tabla principal de listings. Campos: external_id, title, price, listing_type, location (JSONB), specs (JSONB), tags (text[]), images (text[]), etc. |
| `mv_sd_depto_stats` | Vista Materializada | Stats agregados por departamento y listing_type: count, min_price, max_price, avg_price. |
| `sv_locations` | Tabla | Ubicaciones de El Salvador (departamentos, municipios, zonas residenciales). |

### 10.2 RPC Functions

| Función | Params | Descripción |
|---------|--------|-------------|
| `get_listings_for_cards` | p_departamento, p_listing_type, p_limit, p_offset, p_sort_by, p_municipio | Listings paginados con first_image, specs extraídos, total_count |
| `get_municipalities_for_department` | p_departamento, p_listing_type | Municipios con conteo de listings |
| `get_listings_by_tag` | p_tag, p_listing_type, p_limit, p_offset, p_sort_by | Listings filtrados por tag |
| `get_available_tags` | search_query | Tags únicos disponibles |
| `get_price_estimate` | (varios) | Estimación de precio basada en zona y specs |

---

## 11. SCRAPER Y CI/CD

### 11.1 Scraper Multi-Fuente (`scraper_encuentra24.py`)

| Fuente | Método de Extracción | Particularidad |
|--------|---------------------|----------------|
| **Encuentra24** | HTML + CSS selectors | Paginación tradicional, ThreadPoolExecutor |
| **MiCasaSV** | WordPress Sitemap XML | Extrae URLs del sitemap, luego parsea cada página |
| **Realtor.com** | `__NEXT_DATA__` JSON | Datos embebidos en el HTML como JSON de Next.js |

### 11.2 GitHub Actions

| Workflow | Cron | Descripción |
|----------|------|-------------|
| `scrape-new.yml` | Cada hora (`0 * * * *`) | Scrape nuevos listings (últimos 7 días por defecto) |
| `scrape-update.yml` | Cada 12h (`0 0,12 * * *`) | Actualiza listings activos existentes |

Ambos workflows:
- Corren en `ubuntu-latest` con Python 3.11
- Usan secrets: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- Timeout: 60 minutos
- Soportan trigger manual con parámetros opcionales (`limit`, `max_days`)

### 11.3 Scripts de Soporte

| Script | Descripción |
|--------|-------------|
| `match_locations.py` | Matching avanzado de ubicaciones con fuzzy search |
| `deduplication.py` | Deduplicación de listings por URL, título, precio |
| `listing_validator.py` | Validación de datos de listings |
| `area_normalizer.py` | Normalización de áreas a m² |
| `enrich_locations.py` | Enriquecimiento de datos de ubicación |
| `export_to_supabase.py` | Exportación batch a Supabase |
| `localization_plugin.py` | Plugin de localización |

### 11.4 CLI Usage

```bash
# Scrape nuevos listings (todas las fuentes, últimos 7 días)
python scraper_encuentra24.py --max-days 7

# Scrape con límite
python scraper_encuentra24.py --max-days 7 --limit 100

# Actualizar listings existentes
python scraper_encuentra24.py --update

# Scrape fuente específica
python scraper_encuentra24.py --Encuentra24 --limit 50
python scraper_encuentra24.py --MiCasaSV --limit 50
python scraper_encuentra24.py --Realtor --limit 50
```

---

## 12. CONFIGURACIÓN

### 12.1 Variables de Entorno (`.env.local`)

```env
SUPABASE_URL=https://zvamupbxzuxdgvzgbssn.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
```

### 12.2 Dependencias Node.js (`package.json`)

```json
{
  "name": "sivarcasas-dashboard",
  "dependencies": {
    "@types/leaflet": "^1.9.21",
    "@vercel/analytics": "^1.6.1",
    "@vercel/speed-insights": "^1.3.1",
    "leaflet": "^1.9.4",
    "next": "^16.1.6",
    "react": "19.2.3",
    "react-dom": "19.2.3",
    "react-leaflet": "^5.0.0"
  },
  "devDependencies": {
    "@tailwindcss/postcss": "^4",
    "@types/node": "^20",
    "@types/react": "^19",
    "@types/react-dom": "^19",
    "eslint": "^9",
    "eslint-config-next": "16.1.4",
    "sharp": "^0.34.5",
    "tailwindcss": "^4",
    "typescript": "^5"
  }
}
```

### 12.3 Dependencias Python (`requirements.txt`)

```
requests>=2.31.0
beautifulsoup4>=4.12.0
supabase>=2.0.0
```

### 12.4 Next.js Config (`next.config.ts`)

- **Images:** Remote patterns permitidos para todos los hosts (`**`)
- **Redirects:** 14 departamentos × 2 patrones = 28 redirects (`/tag/[dept]` → `/[dept]`)

---

## 13. SEO Y METADATA

| Feature | Implementación |
|---------|---------------|
| **Metadata dinámica** | `generateMetadata()` en layouts de departamento y tag |
| **JSON-LD** | Organization, WebSite, BreadcrumbList, CollectionPage schemas |
| **OG Images** | Generadas dinámicamente con `@vercel/og` (Edge Runtime) |
| **Twitter Cards** | `summary_large_image` con imagen dinámica |
| **Sitemap** | Estático en `public/sitemap.xml` (14 departamentos) |
| **Robots.txt** | `Allow: /` con referencia al sitemap |
| **Canonical URLs** | Configuradas por página |
| **Font** | Inter (Google Fonts, `display: swap`) |

---

## 14. TEMA Y ESTILOS

### 14.1 CSS Variables (`:root` en `globals.css`)

```css
/* Fondo */
--bg-gradient-start: #e8edf2;
--bg-gradient-end: #d7dfe8;
--bg-card: #ffffff;
--bg-subtle: #f1f5f9;
--bg-glass: rgba(255, 255, 255, 0.75);

/* Colores primarios */
--primary: #1e3a5f;        /* Azul oscuro (accent) */
--success: #10b981;        /* Verde (Total, LIVE) */
--danger: #ef4444;         /* Rojo (Renta) */
--warning: #f59e0b;        /* Amarillo (Activos) */

/* Texto */
--text-primary: #1e293b;
--text-secondary: #475569;
--text-muted: #64748b;

/* Sombras premium */
--shadow-card: 0 4px 20px -2px rgba(0,0,0,0.08), 0 2px 6px -2px rgba(0,0,0,0.04);
--shadow-float: 0 20px 40px -8px rgba(0,0,0,0.12), 0 8px 16px -4px rgba(0,0,0,0.06);
```

### 14.2 Pills de Filtro

| Filtro | Clase CSS | Color |
|--------|-----------|-------|
| TOTAL | `dept-card__pill--todos` | Verde gradient (`#10b981` → `#059669`) |
| VENTA | (default) | Azul gradient (`#3b82f6` → `#2563eb`) |
| RENTA | `dept-card__pill--renta` | Rojo gradient (`#ef4444` → `#dc2626`) |

Las pills se reutilizan idénticamente en `DepartmentCard` y `MarketRankingCharts`.

---

## 15. COMANDOS

### Desarrollo

```bash
# Instalar dependencias
npm install

# Iniciar servidor de desarrollo
npm run dev          # o: .\run_dev.bat
# → http://localhost:3000

# Build para producción
npm run build
npm start

# Lint
npm run lint
```

### Scraper

```bash
# Instalar dependencias Python
pip install -r requirements.txt

# Ver sección 11.4 para comandos del scraper
```

---

## 16. 14 DEPARTAMENTOS DE EL SALVADOR

| Departamento | Municipios | Slug URL | Destacados |
|--------------|------------|----------|------------|
| San Salvador | 19 | `san-salvador` | San Salvador, Soyapango, Mejicanos, Apopa |
| La Libertad | 19 | `la-libertad` | Santa Tecla, Antiguo Cuscatlán, Colón |
| Santa Ana | 13 | `santa-ana` | Santa Ana, Metapán, Chalchuapa |
| San Miguel | 20 | `san-miguel` | San Miguel, Chinameca |
| La Paz | 22 | `la-paz` | Zacatecoluca, Olocuilta |
| Usulután | 23 | `usulutan` | Usulután, Jiquilisco |
| Sonsonate | 16 | `sonsonate` | Sonsonate, Juayúa, Izalco |
| La Unión | 18 | `la-union` | La Unión, Conchagua |
| Ahuachapán | 12 | `ahuachapan` | Ahuachapán, Atiquizaya |
| Cuscatlán | 16 | `cuscatlan` | Cojutepeque, Suchitoto |
| Chalatenango | 33 | `chalatenango` | Chalatenango, La Palma |
| Morazán | 26 | `morazan` | San Francisco Gotera, Perquín |
| Cabañas | 9 | `cabanas` | Sensuntepeque, Ilobasco |
| San Vicente | 13 | `san-vicente` | San Vicente, Tecoluca |

---

## 17. NAVEGACIÓN JERÁRQUICA

```
HOME (/)
├── Hero + Búsqueda → Mapa
├── KPI Strip
├── Filtro Global (Total/Venta/Renta)
├── Grid 14 Departamentos
│   └── Click en card → /[departamento]
│       ├── Filtro por municipio (chips)
│       ├── Filtro por tipo (venta/renta)
│       ├── Best Opportunity (scoring)
│       ├── Listings paginados (24/página)
│       │   └── Click en listing → Modal de detalle
│       └── Breadcrumb: Inicio > Departamento > [Filtro]
│
├── Ranking Charts (3 gráficos ECharts)
│   └── Click en barra → /[departamento]
│
├── Mapa Interactivo (Leaflet)
│   └── Click en mapa → Nearby listings + stats
│
└── Tags
    └── /tag/[tag] → Listings filtrados por tag
```

---

## 18. MEJORAS PENDIENTES

### Crítico
- [ ] Mover `SUPABASE_SERVICE_KEY` a variables de entorno en scraper (actualmente en GitHub Secrets para CI/CD, pero hardcoded en `env.download`)

### Importante
- [ ] Implementar cálculo de tendencia 30 días con data histórica real
- [ ] Implementar búsqueda global de propiedades (actualmente solo por ubicación en mapa)
- [ ] Agregar gráficos de tendencia temporal en cards de departamento

### Mejoras
- [ ] Agregar exportación CSV/Excel de datos
- [ ] Tests unitarios para funciones BI y adapter
- [ ] PWA para experiencia móvil nativa
- [ ] Sitemap dinámico (actualmente estático)
- [ ] Dark mode (CSS vars ya preparadas para extensión)

### Completado Recientemente
- [x] Cache de resultados del API (in-memory server + localStorage client)
- [x] Gráficos de ranking con Apache ECharts (reemplazó CanvasJS)
- [x] Warm-start instantáneo al volver a Home
- [x] Filtro global sincronizado con ranking charts
- [x] Pills de filtro en cards de gráficos
- [x] Mapa interactivo con Leaflet
- [x] Sistema de tags
- [x] Best Opportunity scoring
- [x] SEO: JSON-LD, OG images, metadata dinámica
- [x] GitHub Actions para scraping automatizado
- [x] Indicador LIVE simplificado con micro-pulse

---

*Documento actualizado: 10 de Febrero de 2026*
*Versión: 3.0 - ECharts + Filtro Global + Mapa + Tags + CI/CD*
