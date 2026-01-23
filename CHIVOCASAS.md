# CHIVOCASAS.md - Documentación Técnica del Proyecto ChivoCasas

---

## 1. RESUMEN EJECUTIVO DEL PROYECTO

| Campo | Descripción |
|-------|-------------|
| **Nombre del proyecto** | ChivoCasas - Plataforma de Agregación de Propiedades Inmobiliarias |
| **Propósito y objetivo principal** | Sistema de web scraping multi-fuente que recolecta, clasifica por municipio y muestra propiedades inmobiliarias de El Salvador desde múltiples portales (Encuentra24, MiCasaSV, Realtor.com). Incluye dashboard interactivo para visualización y análisis de precios por ubicación. |
| **Stack tecnológico** | **Backend/Scraper:** Python 3.x, BeautifulSoup4, Requests, ThreadPoolExecutor. **Frontend:** HTML5, JavaScript ES6+, Bootstrap 5.3. **Base de datos:** Supabase (PostgreSQL). **Fuentes de datos:** Encuentra24, MiCasaSV, Realtor.com International |
| **Estado actual del desarrollo** | En desarrollo activo con funcionalidades core implementadas. Scrapers operativos para 3 fuentes. Dashboard funcional con agrupación por municipio. |
| **Nivel de criticidad** | **5/10** - Herramienta de análisis de datos inmobiliarios. No maneja datos sensibles de usuarios ni transacciones financieras. |

---

## 2. ARQUITECTURA DEL PROYECTO

### 2.1 Estructura de Carpetas

```
/ChivoCasas
├── scraper_encuentra24.py      # Scraper multi-fuente (1686 líneas)
│   ├── Configuración Supabase
│   ├── Funciones de inserción (insert_listing, insert_listings_batch)
│   ├── Utilidades (parse_price, remove_emojis, normalize_text)
│   ├── Sistema de detección de municipios (262 municipios + aliases)
│   ├── Scraper Encuentra24
│   ├── Scraper MiCasaSV
│   ├── Scraper Realtor.com
│   └── CLI con argparse
│
├── dashboard.html              # Dashboard interactivo (528 líneas)
│   ├── Estilos CSS (Bootstrap + custom)
│   ├── Componentes UI (cards, modals, filtros)
│   └── Lógica JavaScript (fetch, render, filtros, ordenamiento)
│
├── scrapdata.json              # Archivo de datos de ejemplo
├── CLAUDE.md                   # Template de documentación (referencia)
└── .vscode/                    # Configuración VS Code
```

### 2.2 Flujo de Datos

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FLUJO DE DATOS                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                           FUENTES DE DATOS                                    │
├──────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐              │
│  │   Encuentra24   │  │    MiCasaSV     │  │   Realtor.com   │              │
│  │   (HTML/CSS)    │  │   (WordPress)   │  │  (__NEXT_DATA__) │              │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘              │
│           │                    │                    │                        │
└───────────┼────────────────────┼────────────────────┼────────────────────────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
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
            │                                          │
            │  Tabla: scrappeddata_ingest              │
            │  Campos JSONB: location, specs, details  │
            └──────────────────┬───────────────────────┘
                               │
                               │ GET (Anon Key)
                               ▼
            ┌──────────────────────────────────────────┐
            │           dashboard.html                 │
            │                                          │
            │  - Vista por municipios                  │
            │  - Filtros (Venta/Alquiler)             │
            │  - Ordenamiento (Precio, m², hab)        │
            │  - Detalle de propiedades                │
            └──────────────────────────────────────────┘
```

### 2.3 Patrones de Arquitectura Identificados

| Patrón | Implementación | Ubicación |
|--------|---------------|-----------|
| **Concurrent Scraping** | ThreadPoolExecutor para requests paralelos | `scrape_listings_concurrent()`, `get_listing_urls_fast()` |
| **Data Normalization** | Estructura unificada para todas las fuentes | Funciones `scrape_*_listing()` |
| **Municipality Detection** | Búsqueda por aliases y nombres normalizados | `detect_municipio()`, `MUNICIPIO_ALIASES` |
| **JSONB Storage** | Campos estructurados en PostgreSQL | `location`, `specs`, `details`, `images` |
| **SPA-like Dashboard** | JavaScript sin framework, navegación por estados | `showOverview()`, `showLocation()`, `showDetail()` |
| **API REST** | Supabase PostgREST para CRUD | Endpoints `/rest/v1/` |

**Convenciones de código encontradas:**
- Funciones Python: `snake_case`
- Variables Python: `snake_case`, constantes `UPPER_CASE`
- Funciones JavaScript: `camelCase`
- IDs HTML: `camelCase`
- Clases CSS: `kebab-case` (Bootstrap convention)

---

## 3. COMPONENTES PRINCIPALES

### 3.1 Scraper Multi-Fuente (scraper_encuentra24.py)

#### Sistema de Detección de Municipios

**Función Principal**: `detect_municipio(location, description, title)`
- **Ubicación**: Líneas 529-595
- **Responsabilidades**: Detectar municipio desde campos de texto
- **Prioridad de búsqueda**:
  1. Aliases (más específicos primero, ordenados por longitud)
  2. Título (mayor prioridad - info más específica)
  3. Location (original del sitio)
  4. Description (fallback)
- **Retorna**: `{"municipio_detectado": str, "departamento": str}`

**Datos de Referencia**:
- `MUNICIPIOS_EL_SALVADOR`: Dict con 14 departamentos y 262 municipios
- `MUNICIPIO_ALIASES`: 130+ aliases comunes (ej: "Merliot" → "Santa Tecla")
- `MUNICIPIO_TO_DEPARTAMENTO`: Mapeo municipio → departamento

**Función Auxiliar**: `normalize_text(text)`
- Normaliza texto: lowercase, elimina acentos
- Usa `unicodedata` para comparación insensible a acentos

---

#### Scraper Encuentra24

**Funciones principales**:
| Función | Líneas | Descripción |
|---------|--------|-------------|
| `get_listing_urls_fast()` | 621-669 | Recolecta URLs con requests concurrentes |
| `fetch_page()` | 605-618 | Obtiene URLs de una página |
| `scrape_listing()` | 672-830 | Extrae datos de una propiedad |
| `scrape_listings_concurrent()` | 833-849 | Scraping paralelo de múltiples URLs |
| `main_encuentra24()` | 1550-1583 | Función principal del scraper |

**Selectores CSS utilizados**:
```python
# Título
soup.select_one("h1") or soup.select_one("title")

# Precio
soup.select_one(".estate-price") or soup.select_one(".d3-price")

# Specs
soup.select(".d3-property-insight__attribute")

# Descripción
soup.select_one(".d3-property-about__text")

# Imágenes
# Patrón: https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/{path}/{id}_{suffix}
```

---

#### Scraper MiCasaSV

**Funciones principales**:
| Función | Líneas | Descripción |
|---------|--------|-------------|
| `get_micasasv_listing_urls()` | 862-899 | URLs desde sitemap XML |
| `slug_to_external_id()` | 854-859 | Genera ID desde slug (MD5 hash) |
| `scrape_micasasv_listing()` | 904-1112 | Extrae datos de una propiedad |
| `main_micasasv()` | 1514-1547 | Función principal |

**Particularidades**:
- Usa sitemap WordPress: `https://micasasv.com/job_listing-sitemap.xml`
- Contenido renderizado con JavaScript, por eso usa sitemap
- Galería con PhotoSwipe

---

#### Scraper Realtor.com International

**Funciones principales**:
| Función | Líneas | Descripción |
|---------|--------|-------------|
| `get_realtor_listings_from_page()` | 1137-1330 | Extrae desde `__NEXT_DATA__` JSON |
| `enrich_realtor_listing()` | 1333-1394 | Agrega descripción desde página individual |
| `enrich_realtor_listings()` | 1397-1415 | Enriquecimiento concurrente |
| `get_realtor_all_listings()` | 1417-1469 | Paginación automática |
| `main_realtor()` | 1472-1511 | Función principal |

**Particularidades**:
- Datos embebidos en `__NEXT_DATA__` (Next.js)
- Sistema de referencias Apollo Client (`__ref`)
- Conversión sqft → m² (factor: 0.092903)
- CDN de imágenes: `https://s1.rea.global/img/600x400-prop/`

---

#### Sistema de Inserción a Supabase

**Funciones**:
| Función | Líneas | Descripción |
|---------|--------|-------------|
| `insert_listing()` | 31-101 | Inserción individual |
| `insert_listings_batch()` | 104-188 | Inserción en lotes (batch_size=50) |

**Estructura de datos enviada**:
```python
{
    "external_id": int,           # ID único de la fuente
    "title": str,
    "price": float,               # Parseado sin símbolos
    "location": {                 # JSONB
        "location_original": str,
        "municipio_detectado": str,
        "departamento": str
    },
    "published_date": str,        # YYYY-MM-DD
    "listing_type": str,          # "sale" | "rent"
    "url": str,
    "specs": dict,                # JSONB: bedrooms, bathrooms, area
    "details": dict,              # JSONB: campos adicionales
    "description": str,
    "images": list,               # Array de URLs
    "source": str,                # "Encuentra24" | "MiCasaSV" | "Realtor"
    "active": bool
}
```

---

### 3.2 Dashboard (dashboard.html)

#### Estructura HTML

| Sección | ID/Clase | Descripción |
|---------|----------|-------------|
| Navbar | `.navbar` | Logo, contador de listings, botón Refresh |
| Breadcrumb | `#breadcrumb` | Navegación Municipios > Detalle |
| Overview | `#overviewSection` | Grid de tarjetas por municipio |
| Listings | `#listingsSection` | Grid de propiedades de un municipio |
| Modal | `#detailModal` | Carousel de imágenes, specs, descripción |

#### Funciones JavaScript

| Función | Líneas | Descripción |
|---------|--------|-------------|
| `fetchListings()` | 242-252 | Fetch de Supabase con anon key |
| `calculateStats()` | 254-277 | Agrupa por `municipio_detectado` |
| `formatPrice()` | 279-283 | Formatea precio con separadores |
| `renderLocations()` | 285-314 | Renderiza tarjetas de municipios |
| `setFilter()` | 316-340 | Filtra por tipo (all/sale/rent) |
| `showLocation()` | 342-357 | Muestra propiedades de un municipio |
| `getArea()` | 359-365 | Extrae área en m² de specs |
| `sortListings()` | 367-406 | Ordena por precio, habitaciones, precio/m² |
| `renderListingsGrid()` | 408-432 | Renderiza grid de propiedades |
| `showDetail()` | 434-502 | Abre modal con detalles |
| `showOverview()` | 504-510 | Vuelve a vista de municipios |
| `refreshData()` | 512-516 | Recarga datos de Supabase |
| `loadData()` | 518-529 | Carga inicial |

#### Configuración Supabase

```javascript
const SUPABASE_URL = 'https://zvamupbxzuxdgvzgbssn.supabase.co';
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...';
const TABLE = 'scrappeddata_ingest';
```

---

## 4. GUÍA DE TRABAJO POR COMPONENTE

### 4.1 Agregar Nueva Fuente de Datos

1. **Crear función de recolección de URLs**:
   ```python
   def get_nuevafuente_listing_urls(base_url, max_listings=None):
       # Implementar lógica de paginación/sitemap
       return urls_list
   ```

2. **Crear función de scraping individual**:
   ```python
   def scrape_nuevafuente_listing(url, listing_type):
       # Parse HTML/JSON
       # Extraer campos requeridos
       municipio_info = detect_municipio(location, description, title)
       return {
           "title": ...,
           "price": ...,
           "location": ...,
           # ... todos los campos del schema
           "municipio_detectado": municipio_info["municipio_detectado"],
           "departamento": municipio_info["departamento"],
       }
   ```

3. **Crear función principal**:
   ```python
   def main_nuevafuente(limit=None):
       # Combinar recolección y scraping
       # Insertar en Supabase
   ```

4. **Agregar a CLI**:
   ```python
   parser.add_argument("--NuevaFuente", action="store_true")
   ```

5. **Actualizar función `main()`** para incluir nueva fuente

---

### 4.2 Agregar Nuevo Municipio/Alias

**Para agregar un alias**:
```python
# En MUNICIPIO_ALIASES (línea ~369)
MUNICIPIO_ALIASES = {
    # ...
    "nuevo alias": "Nombre Municipio Oficial",
}
```

**Para agregar un municipio nuevo** (raramente necesario):
```python
# En MUNICIPIOS_EL_SALVADOR (línea ~256)
"Departamento": [
    # ...
    "Nuevo Municipio",
]
```

---

### 4.3 Modificar Dashboard

**Agregar nuevo filtro**:
1. Agregar botón en HTML (`#overviewSection`)
2. Crear función `setNewFilter(value)` en JavaScript
3. Modificar `calculateStats()` para aplicar filtro

**Agregar nuevo ordenamiento**:
1. Agregar `<option>` en `#sortSelect`
2. Agregar case en `sortListings()`

**Mostrar nuevo campo en tarjetas**:
1. Modificar `renderListingsGrid()` para incluir campo
2. Agregar estilos CSS si necesario

---

## 5. CONVENCIONES Y ESTÁNDARES DEL PROYECTO

### Nomenclatura

| Elemento | Convención | Ejemplo |
|----------|------------|---------|
| Funciones Python | snake_case | `detect_municipio`, `scrape_listing` |
| Constantes Python | UPPER_SNAKE_CASE | `SUPABASE_URL`, `MUNICIPIO_ALIASES` |
| Funciones JavaScript | camelCase | `fetchListings`, `showDetail` |
| IDs HTML | camelCase | `#detailModal`, `#locationsGrid` |
| Clases CSS | kebab-case | `.listing-card`, `.price-avg` |

### Estructura de Datos (Schema)

```json
{
  "external_id": "bigint (required)",
  "title": "text",
  "price": "numeric",
  "location": {
    "location_original": "text",
    "municipio_detectado": "text",
    "departamento": "text"
  },
  "published_date": "date (YYYY-MM-DD)",
  "listing_type": "text (sale|rent)",
  "url": "text",
  "specs": {
    "bedrooms": "text",
    "bathrooms": "text",
    "area": "text"
  },
  "details": {},
  "description": "text",
  "images": ["url1", "url2"],
  "source": "text",
  "active": "boolean"
}
```

### Manejo de Errores

**Scraper**:
- Funciones de scraping retornan `None` en caso de error
- Logs con `print()` para debugging
- Listings nulos se filtran antes de inserción

**Dashboard**:
- Try/catch en `loadData()`
- Mensaje de error visual en grid

---

## 6. CONFIGURACIÓN Y VARIABLES

### Variables Críticas en scraper_encuentra24.py

```python
# Supabase
SUPABASE_URL = "https://zvamupbxzuxdgvzgbssn.supabase.co"
SUPABASE_SERVICE_KEY = "eyJ..."  # ⚠️ Service Role Key
TABLE_NAME = "scrappeddata_ingest"

# Concurrencia
CONCURRENT_PAGES = 10
MAX_LISTINGS = None  # Sin límite por defecto

# Headers
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ..."
}

# URLs base
SALE_URL = "https://www.encuentra24.com/el-salvador-es/bienes-raices-venta-de-propiedades-casas"
RENT_URL = "https://www.encuentra24.com/el-salvador-es/bienes-raices-alquiler-casas"
MICASASV_SALE_URL = "https://micasasv.com/explore/?type=inmuebles-en-venta"
REALTOR_SALE_URL = "https://www.realtor.com/international/sv"
```

### Variables en dashboard.html

```javascript
const SUPABASE_URL = 'https://zvamupbxzuxdgvzgbssn.supabase.co';
const SUPABASE_ANON_KEY = 'eyJ...';  // Anon Key (público)
const TABLE = 'scrappeddata_ingest';
```

---

## 7. CLI Y COMANDOS

### Uso del Scraper

```bash
# Scrape solo Encuentra24 (default)
python scraper_encuentra24.py

# Scrape con límite
python scraper_encuentra24.py --limit 100

# Scrape MiCasaSV
python scraper_encuentra24.py --MiCasaSV

# Scrape Realtor.com
python scraper_encuentra24.py --Realtor

# Scrape múltiples fuentes
python scraper_encuentra24.py --Encuentra24 --MiCasaSV --Realtor

# Scrape todas con límite
python scraper_encuentra24.py --Encuentra24 --MiCasaSV --Realtor --limit 50
```

### Argumentos CLI

| Argumento | Tipo | Descripción |
|-----------|------|-------------|
| `--Encuentra24` | flag | Habilita scraping de Encuentra24 |
| `--MiCasaSV` | flag | Habilita scraping de MiCasaSV |
| `--Realtor` | flag | Habilita scraping de Realtor.com |
| `--limit` | int | Máximo de listings por fuente |

---

## 8. ISSUES Y MEJORAS IDENTIFICADAS

### 🔴 Crítico

1. **Service Key expuesta en código**
   - **Ubicación**: `scraper_encuentra24.py:27`
   - **Problema**: Key con permisos de admin visible en código
   - **Solución**: Mover a variable de entorno `.env`

2. **Sin manejo de rate limiting**
   - **Problema**: Requests sin delay pueden resultar en bloqueos
   - **Solución**: Agregar `time.sleep()` configurable entre requests

### 🟡 Importante

1. **Logs básicos con print()**
   - **Problema**: Sin niveles de log, difícil debugging
   - **Solución**: Implementar `logging` module

2. **Sin validación de datos**
   - **Problema**: Datos malformados pueden causar errores
   - **Solución**: Agregar schema validation (pydantic)

3. **Dashboard sin framework**
   - **Problema**: Código JS difícil de mantener
   - **Solución**: Considerar migrar a Vue/React para proyectos más complejos

### 🟢 Mejoras

1. **Agregar tests unitarios**
   - Tests para `detect_municipio()`
   - Tests para funciones de parsing

2. **Cache de resultados**
   - Evitar re-scraping de URLs ya procesadas

3. **Webhook/notificaciones**
   - Alertas cuando se detectan nuevas propiedades

4. **Exportación de datos**
   - Botón de descarga CSV/Excel en dashboard

---

## 9. GUÍA DE INICIO RÁPIDO

### Requisitos

```bash
# Python 3.8+
python --version

# Dependencias
pip install requests beautifulsoup4
```

### Setup

```bash
# 1. Clonar/Descargar proyecto
cd ChivoCasas

# 2. Instalar dependencias
pip install requests beautifulsoup4

# 3. Ejecutar scraper (prueba con límite)
python scraper_encuentra24.py --Encuentra24 --limit 10

# 4. Abrir dashboard
# Simplemente abrir dashboard.html en navegador
# O usar servidor local:
python -m http.server 8000
# Navegar a http://localhost:8000/dashboard.html
```

### Verificar Funcionamiento

1. **Scraper**: Debe mostrar mensajes de inserción
   ```
   Batch inserted: 10 records
   ```

2. **Dashboard**: Debe mostrar tarjetas de municipios con conteo

---

## 10. LISTA DE MUNICIPIOS DE EL SALVADOR

El proyecto incluye los 262 municipios oficiales de El Salvador organizados por departamento:

| Departamento | Cantidad | Municipios Destacados |
|--------------|----------|----------------------|
| Ahuachapán | 12 | Ahuachapán, Apaneca, Atiquizaya |
| Santa Ana | 13 | Santa Ana, Metapán, Chalchuapa |
| Sonsonate | 16 | Sonsonate, Juayúa, Izalco, Nahuizalco |
| Chalatenango | 33 | Chalatenango, La Palma, San Ignacio |
| La Libertad | 23 | Santa Tecla, La Libertad, Colón, Antiguo Cuscatlán |
| San Salvador | 19 | San Salvador, Soyapango, Mejicanos, Apopa |
| Cuscatlán | 16 | Cojutepeque, Suchitoto |
| La Paz | 22 | Zacatecoluca, San Luis Talpa, Olocuilta |
| Cabañas | 9 | Sensuntepeque, Ilobasco |
| San Vicente | 13 | San Vicente, Tecoluca |
| Usulután | 23 | Usulután, Jiquilisco, Berlín |
| San Miguel | 20 | San Miguel, Chinameca, Chirilagua |
| Morazán | 26 | San Francisco Gotera, Perquín |
| La Unión | 18 | La Unión, Conchagua, Santa Rosa de Lima |

---

*Documento generado el 23 de Enero de 2026*
*Versión: 1.0*
