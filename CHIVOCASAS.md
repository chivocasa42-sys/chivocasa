# CHIVOCASAS.md - Documentación Técnica del Proyecto ChivoCasas

---

## 1. RESUMEN EJECUTIVO DEL PROYECTO

| Campo | Descripción |
|-------|-------------|
| **Nombre del proyecto** | ChivoCasas - Índice Inmobiliario de El Salvador |
| **Propósito y objetivo principal** | Plataforma de análisis de mercado inmobiliario que agrega propiedades de múltiples fuentes (Encuentra24, MiCasaSV, Realtor.com), clasifica por departamento/municipio, y presenta métricas BI para entender el mercado salvadoreño. |
| **Stack tecnológico** | **Frontend:** Next.js 16, React 19, TypeScript, TailwindCSS 4. **Backend/Scraper:** Python 3.x, BeautifulSoup4, Requests. **Base de datos:** Supabase (PostgreSQL). |
| **Estado actual del desarrollo** | Dashboard BI funcional con métricas de mercado, clasificación por 14 departamentos, navegación jerárquica, y scraper multi-fuente operativo. |
| **Repositorio** | https://github.com/chivocasa42-sys/chivocasa.git |

---

## 2. ARQUITECTURA DEL PROYECTO

### 2.1 Estructura de Carpetas

```
/ChivoCasas
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   └── listings/
│   │   │       └── route.ts          # API endpoint para Supabase
│   │   ├── globals.css               # Estilos globales
│   │   ├── layout.tsx                # Layout principal
│   │   └── page.tsx                  # Home BI principal
│   │
│   ├── components/
│   │   ├── DepartmentCardBI.tsx      # Card de departamento con métricas BI
│   │   ├── KPIStrip.tsx              # 4 KPIs nacionales
│   │   ├── InsightsPanel.tsx         # Top 3 zonas activas
│   │   ├── UnclassifiedCard.tsx      # Card para "NO CLASIFICADO"
│   │   ├── LocationCard.tsx          # Card de municipio
│   │   ├── ListingCard.tsx           # Card de propiedad
│   │   ├── ListingsView.tsx          # Vista de listings
│   │   ├── ListingModal.tsx          # Modal de detalle
│   │   └── Navbar.tsx                # Navbar con stats
│   │
│   ├── data/
│   │   └── departamentos.ts          # Mapeo de 14 departamentos + 262 municipios
│   │
│   ├── lib/
│   │   └── biCalculations.ts         # Funciones de cálculo BI (mediana, percentiles)
│   │
│   └── types/
│       ├── listing.ts                # Tipos de listing
│       └── biStats.ts                # Tipos para estadísticas BI
│
├── public/                           # Assets estáticos
├── scraper_encuentra24.py            # Scraper multi-fuente Python
├── CHIVOCASAS.md                     # Esta documentación
├── package.json                      # Dependencias Node.js
├── .env.local                        # Variables de entorno (no en git)
└── tsconfig.json                     # Configuración TypeScript
```

### 2.2 Flujo de Datos

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FUENTES DE DATOS                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │   Encuentra24   │  │    MiCasaSV     │  │   Realtor.com   │              │
│  │   (HTML/CSS)    │  │   (WordPress)   │  │  (__NEXT_DATA__) │              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
│           └────────────────────┼────────────────────┘                        │
└────────────────────────────────┼────────────────────────────────────────────┘
                                 │
                                 ▼
              ┌──────────────────────────────────────────┐
              │        scraper_encuentra24.py            │
              │                                          │
              │  1. Fetch páginas (ThreadPoolExecutor)   │
              │  2. Parse HTML (BeautifulSoup)           │
              │  3. Extracción de datos                  │
              │  4. Detección de municipio               │
              │  5. Normalización de estructura          │
              └──────────────────┬───────────────────────┘
                                 │
                                 │ POST /rest/v1/scrappeddata_ingest
                                 ▼
              ┌──────────────────────────────────────────┐
              │            Supabase (PostgreSQL)         │
              │  Tabla: scrappeddata_ingest              │
              └──────────────────┬───────────────────────┘
                                 │
                                 │ GET (via Next.js API Route)
                                 ▼
              ┌──────────────────────────────────────────┐
              │           Next.js Dashboard BI           │
              │                                          │
              │  - KPI Strip (métricas nacionales)       │
              │  - Cards por 14 departamentos            │
              │  - Drill-down a municipios               │
              │  - Insights de zonas activas             │
              └──────────────────────────────────────────┘
```

---

## 3. HOME BI - ÍNDICE INMOBILIARIO

### 3.1 Estructura del Home

| Sección | Componente | Descripción |
|---------|------------|-------------|
| **Navbar** | `Navbar.tsx` | Logo, "X activos", última actualización, fuentes, botón Refresh |
| **Header** | En `page.tsx` | Título "DEPARTAMENTOS", subtítulo, filtros Todos/Venta/Alquiler |
| **KPI Strip** | `KPIStrip.tsx` | 4 métricas: Precio típico venta, Renta típica, Anuncios activos, Tendencia 30d |
| **Grid Departamentos** | `DepartmentCardBI.tsx` | 14 cards con mediana, rango P25-P75, actividad 7 días |
| **NO CLASIFICADO** | `UnclassifiedCard.tsx` | Listings sin departamento detectado |
| **Insights** | `InsightsPanel.tsx` | Top 3 zonas más activas (7 días) |

### 3.2 Métricas BI

**Por qué MEDIANA en vez de PROMEDIO:**
- Un penthouse de $2M distorsiona el promedio de una zona con casas de $80K
- La mediana (percentil 50) ignora extremos y muestra el "precio típico"

**Por qué P25/P75 en vez de Min/Max:**
- Min=$200 (error de data), Max=$5M (outlier) = rango inútil
- P25-P75 muestra donde está el 50% central del mercado = "rango típico"

### 3.3 Navegación Jerárquica

```
HOME (14 Departamentos)
    │
    ├── Click en "San Salvador"
    │       │
    │       └── Vista: Municipios de San Salvador
    │               │
    │               ├── Click en "Soyapango"
    │               │       │
    │               │       └── Vista: Listings de Soyapango
    │               │               │
    │               │               └── Click en propiedad → Modal de detalle
    │               │
    │               └── [Volver a Departamentos]
    │
    └── Click en "NO CLASIFICADO"
            │
            └── Vista: Listings sin departamento
```

---

## 4. COMPONENTES PRINCIPALES

### 4.1 Funciones de Cálculo BI (`src/lib/biCalculations.ts`)

| Función | Descripción |
|---------|-------------|
| `calculatePercentile(values, percentile)` | Calcula percentil de un array de números |
| `calculateNationalStats(listings)` | Estadísticas nacionales: mediana venta/renta, total activos, tendencia |
| `calculateDepartmentBIStats(listings, filterType)` | Estadísticas por departamento con municipios anidados |
| `calculateInsights(departments)` | Top 3 zonas más activas |
| `formatPrice(price)` | Formatea precio como `$XXX,XXX` |
| `formatTrend(pct)` | Formatea tendencia con flecha |

### 4.2 Mapeo de Departamentos (`src/data/departamentos.ts`)

```typescript
export const DEPARTAMENTOS: Record<string, string[]> = {
    "San Salvador": ["San Salvador", "Soyapango", "Mejicanos", ...],
    "La Libertad": ["Santa Tecla", "Antiguo Cuscatlán", "Colón", ...],
    // ... 12 departamentos más
};

export const LOCATION_ALIASES: Record<string, { municipio: string; departamento: string }> = {
    "merliot": { municipio: "Antiguo Cuscatlán", departamento: "La Libertad" },
    "escalon": { municipio: "San Salvador", departamento: "San Salvador" },
    // ... 50+ aliases
};
```

### 4.3 Scraper Multi-Fuente (`scraper_encuentra24.py`)

| Fuente | Función Principal | Particularidad |
|--------|-------------------|----------------|
| **Encuentra24** | `main_encuentra24()` | HTML tradicional, selectores CSS |
| **MiCasaSV** | `main_micasasv()` | Sitemap WordPress XML |
| **Realtor.com** | `main_realtor()` | `__NEXT_DATA__` JSON embebido |

**CLI Usage:**
```bash
# Scrape todas las fuentes con límite
python scraper_encuentra24.py --Encuentra24 --MiCasaSV --Realtor --limit 100
```

---

## 5. TIPOS DE DATOS

### 5.1 Listing (`src/types/listing.ts`)

```typescript
interface Listing {
    id: number;
    external_id: number;
    url: string;
    source: string;              // "Encuentra24" | "MiCasaSV" | "Realtor"
    title: string;
    price: number;
    currency: string;
    location: unknown;           // JSONB con municipio_detectado
    listing_type: 'sale' | 'rent';
    description: string;
    specs: { bedrooms?, bathrooms?, 'Área construida (m²)'? };
    details: Record<string, string>;
    images: string[];
    published_date: string;
    scraped_at: string;
}
```

### 5.2 Estadísticas BI (`src/types/biStats.ts`)

```typescript
interface DepartmentBIStats {
    departamento: string;
    count_active: number;
    municipios_con_actividad: number;
    median_price: number;
    p25_price: number;
    p75_price: number;
    new_7d: number;
    municipios: Record<string, MunicipioStats>;
}

interface NationalStats {
    median_sale: number;
    median_rent: number;
    total_active: number;
    trend_30d_pct: number;
    updated_at: string;
    sources: string[];
}
```

---

## 6. CONFIGURACIÓN

### Variables de Entorno (`.env.local`)

```env
SUPABASE_URL=https://zvamupbxzuxdgvzgbssn.supabase.co
SUPABASE_SERVICE_KEY=eyJ...
```

### Dependencias (`package.json`)

```json
{
  "dependencies": {
    "next": "16.1.4",
    "react": "19.2.3",
    "react-dom": "19.2.3"
  },
  "devDependencies": {
    "tailwindcss": "^4",
    "typescript": "^5"
  }
}
```

---

## 7. COMANDOS

### Desarrollo

```bash
# Instalar dependencias
npm install

# Iniciar servidor de desarrollo
npm run dev
# → http://localhost:3000

# Build para producción
npm run build
npm start
```

### Scraper

```bash
# Instalar dependencias Python
pip install requests beautifulsoup4

# Ejecutar scraper
python scraper_encuentra24.py --Encuentra24 --limit 50
python scraper_encuentra24.py --MiCasaSV --limit 50
python scraper_encuentra24.py --Realtor --limit 50
```

---

## 8. 14 DEPARTAMENTOS DE EL SALVADOR

| Departamento | Municipios | Destacados |
|--------------|------------|------------|
| San Salvador | 19 | San Salvador, Soyapango, Mejicanos, Apopa |
| La Libertad | 23 | Santa Tecla, Antiguo Cuscatlán, Colón |
| Santa Ana | 13 | Santa Ana, Metapán, Chalchuapa |
| San Miguel | 20 | San Miguel, Chinameca |
| La Paz | 22 | Zacatecoluca, Olocuilta |
| Usulután | 23 | Usulután, Jiquilisco |
| Sonsonate | 16 | Sonsonate, Juayúa, Izalco |
| La Unión | 18 | La Unión, Conchagua |
| Ahuachapán | 12 | Ahuachapán, Atiquizaya |
| Cuscatlán | 16 | Cojutepeque, Suchitoto |
| Chalatenango | 33 | Chalatenango, La Palma |
| Morazán | 26 | San Francisco Gotera, Perquín |
| Cabañas | 9 | Sensuntepeque, Ilobasco |
| San Vicente | 13 | San Vicente, Tecoluca |

---

## 9. MEJORAS PENDIENTES

### 🔴 Crítico
- [ ] Mover `SUPABASE_SERVICE_KEY` a variables de entorno en scraper

### 🟡 Importante
- [ ] Implementar cálculo de tendencia 30 días con data histórica
- [ ] Agregar gráficos de tendencia en cards de departamento
- [ ] Implementar búsqueda global de propiedades

### 🟢 Mejoras
- [ ] Agregar exportación CSV/Excel
- [ ] Cache de resultados del API
- [ ] Tests unitarios para funciones BI
- [ ] PWA para móvil

---

*Documento actualizado: 23 de Enero de 2026*
*Versión: 2.0 - Next.js + Home BI*
