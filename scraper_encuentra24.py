"""
Multi-Source Housing Scraper - OPTIMIZED
Uses concurrent requests to scrape listings from Encuentra24, MiCasaSV, Realtor.com, and Vivo Latam.
Inserts results directly into Supabase database (scrappeddata_ingest table).

Usage:
  python scraper_encuentra24.py                             # Default: scrape ALL sources
  python scraper_encuentra24.py --Encuentra24 --limit 100   # Scrape 100 from Encuentra24 only
  python scraper_encuentra24.py --MiCasaSV --limit 10       # Scrape 10 from MiCasaSV only
  python scraper_encuentra24.py --Realtor --limit 50        # Scrape 50 from Realtor.com only
  python scraper_encuentra24.py --VivoLatam --limit 20      # Scrape 20 from Vivo Latam only
  python scraper_encuentra24.py --Encuentra24 --MiCasaSV    # Scrape from specific sources
"""
import argparse
import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os
import hashlib
from urllib.parse import unquote
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import localization plugin for generating searchable tags
from localization_plugin import build_destination_queries

# ============== SUPABASE CONFIG ==============
SUPABASE_URL = "https://zvamupbxzuxdgvzgbssn.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp2YW11cGJ4enV4ZGd2emdic3NuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTA5MDMwNSwiZXhwIjoyMDg0NjY2MzA1fQ.VfONseJg19pMEymrc6FbdEQJUWxTzJdNlVTboAaRgEs"
TABLE_NAME = "scrappeddata_ingest"


def insert_listing(listing):
    """Insert a single listing to Supabase."""
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    # Parse external_id to bigint
    external_id_str = listing.get("external_id", "")
    try:
        external_id = int(external_id_str)
    except (ValueError, TypeError):
        print(f"  Invalid external_id: {external_id_str}")
        return False
    
    # Parse published_date - convert DD/MM/YYYY to YYYY-MM-DD
    pub_date = listing.get("published_date")
    parsed_date = None
    if pub_date and pub_date.strip():
        # Convert DD/MM/YYYY to YYYY-MM-DD for PostgreSQL
        try:
            parts = pub_date.strip().split("/")
            if len(parts) == 3:
                day, month, year = parts
                parsed_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            else:
                parsed_date = pub_date  # Keep as-is if not in expected format
        except:
            parsed_date = None
    
    # Prepare data for insertion (match DB schema)
    # JSONB fields are sent as dicts/lists - requests.post with json= handles serialization
    
    # Build location JSONB with breakdown
    location_data = {
        "location_original": listing.get("location", ""),
        "municipio_detectado": listing.get("municipio_detectado", "No identificado"),
        "departamento": listing.get("departamento", "")
    }
    
    # Generate tags using localization plugin (use pre-computed if available)
    tags = listing.get("tags")
    if not tags:
        tags = generate_location_tags(listing)
    
    data = {
        "external_id": external_id,
        "title": listing.get("title"),
        "price": parse_price(listing.get("price", "")),
        "location": location_data,
        "published_date": parsed_date,
        "listing_type": listing.get("listing_type"),
        "url": listing.get("url"),
        "specs": listing.get("specs", {}),
        "details": listing.get("details", {}),
        "description": listing.get("description"),
        "images": listing.get("images", []),
        "source": listing.get("source"),
        "active": listing.get("active", True),
        "tags": tags
    }
    
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
    
    try:
        resp = requests.post(url, headers=headers, json=data, timeout=30)
        if resp.status_code in (200, 201):
            print(f"  Inserted: {listing.get('title', '')[:50]}...")
            return True
        else:
            print(f"  Insert error: {resp.status_code} - {resp.text[:300]}")
            return False
    except Exception as e:
        print(f"  Insert exception: {e}")
        return False


def insert_listings_batch(listings, batch_size=50):
    """Insert multiple listings to Supabase in batches."""
    if not listings:
        return 0, 0
    
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    success = 0
    errors = 0
    
    # Process in batches
    for i in range(0, len(listings), batch_size):
        batch = listings[i:i + batch_size]
        batch_data = []
        
        for listing in batch:
            # Parse external_id to bigint
            external_id_str = listing.get("external_id", "")
            try:
                external_id = int(external_id_str)
            except (ValueError, TypeError):
                errors += 1
                continue
            
            # Parse published_date - convert DD/MM/YYYY to YYYY-MM-DD
            pub_date = listing.get("published_date")
            parsed_date = None
            if pub_date and pub_date.strip():
                try:
                    parts = pub_date.strip().split("/")
                    if len(parts) == 3:
                        day, month, year = parts
                        parsed_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                except:
                    parsed_date = None
            
            # Build location JSONB with breakdown
            location_data = {
                "location_original": listing.get("location", ""),
                "municipio_detectado": listing.get("municipio_detectado", "No identificado"),
                "departamento": listing.get("departamento", "")
            }
            
            # Get tags (pre-computed or generate now)
            tags = listing.get("tags")
            if not tags:
                tags = generate_location_tags(listing)
            
            # Build record
            record = {
                "external_id": external_id,
                "title": listing.get("title"),
                "price": parse_price(listing.get("price", "")),
                "location": location_data,
                "published_date": parsed_date,
                "listing_type": listing.get("listing_type"),
                "url": listing.get("url"),
                "specs": listing.get("specs", {}),
                "details": listing.get("details", {}),
                "description": listing.get("description"),
                "images": listing.get("images", []),
                "source": listing.get("source"),
                "active": listing.get("active", True),
                "tags": tags
            }
            batch_data.append(record)
        
        if not batch_data:
            continue
        
        # Send batch request
        url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
        try:
            resp = requests.post(url, headers=headers, json=batch_data, timeout=60)
            if resp.status_code in (200, 201):
                success += len(batch_data)
                print(f"  Batch inserted: {len(batch_data)} records")
            else:
                # Try to parse error for details
                print(f"  Batch error: {resp.status_code} - {resp.text[:500]}")
                errors += len(batch_data)
        except Exception as e:
            print(f"  Batch exception: {e}")
            errors += len(batch_data)
    
    return success, errors


def parse_price(price_str):
    """Parse price string to float."""
    if not price_str:
        return None
    # Remove $ and commas, keep only digits and decimal
    cleaned = re.sub(r'[^\d.]', '', str(price_str))
    try:
        return float(cleaned)
    except:
        return None


def generate_location_tags(listing):
    """
    Generate searchable location tags for a listing using the localization plugin.
    Uses the build_destination_queries function to create location query strings
    that serve as searchable tags.
    
    Args:
        listing: Dict with listing data including location info
        
    Returns:
        List of tag strings for the listing
    """
    try:
        # Build a listing dict in the format expected by localization_plugin
        loc_listing = {
            "title": listing.get("title", ""),
            "description": listing.get("description", ""),
            "location": {
                "municipio_detectado": listing.get("municipio_detectado", ""),
                "departamento": listing.get("departamento", ""),
                "location_original": listing.get("location", "")
            }
        }
        
        # Generate tags using the localization plugin's query builder
        # Only keep the first (most specific) tag, then split into separate tags
        tags = build_destination_queries(loc_listing)
        
        if tags:
            # Split the first tag by ", " to get individual tags
            # e.g., "Santa Rosa, Santa Tecla, La Libertad, El Salvador" 
            # becomes ["Santa Rosa", "Santa Tecla", "La Libertad", "El Salvador"]
            return [t.strip() for t in tags[0].split(",") if t.strip()]
        return []
    except Exception as e:
        print(f"  Warning: Could not generate tags: {e}")
        return []


def parse_date(date_str):
    """Parse date string to ISO format."""
    if not date_str:
        return None
    # Return as-is if already valid, otherwise return None
    return date_str if date_str else None


def remove_emojis(text):
    """Remove emojis and special Unicode characters from text."""
    if not text:
        return text
    # Pattern to match emojis and other special Unicode symbols
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "\U0001F900-\U0001F9FF"  # supplemental symbols
        "\U0001FA00-\U0001FA6F"  # chess symbols
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
        "\U00002600-\U000026FF"  # misc symbols
        "\U00002300-\U000023FF"  # misc technical
        "]+",
        flags=re.UNICODE
    )
    # Remove emojis
    cleaned = emoji_pattern.sub('', text)
    # Also remove any remaining non-printable or weird characters
    cleaned = re.sub(r'[^\x00-\x7F\xC0-\xFF\u0100-\u017F\u00A0-\u00FF]+', '', cleaned)
    # Clean up multiple spaces/newlines
    cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned)
    cleaned = re.sub(r'  +', ' ', cleaned)
    return cleaned.strip()


# Get data directory from environment or use relative path
DATA_DIR = os.environ.get("CHIVOFERTON_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ============== ENCUENTRA24 CONFIG ==============
BASE_URL = "https://www.encuentra24.com"
SALE_URL = "https://www.encuentra24.com/el-salvador-es/bienes-raices-venta-de-propiedades-casas"
RENT_URL = "https://www.encuentra24.com/el-salvador-es/bienes-raices-alquiler-casas"

# ============== MICASASV CONFIG ==============
MICASASV_BASE_URL = "https://micasasv.com"
MICASASV_SALE_URL = "https://micasasv.com/explore/?type=inmuebles-en-venta"
MICASASV_RENT_URL = "https://micasasv.com/explore/?type=inmuebles-en-alquiler"

# ============== REALTOR.COM CONFIG ==============
REALTOR_BASE_URL = "https://www.realtor.com"
REALTOR_SALE_URL = "https://www.realtor.com/international/sv"
REALTOR_RENT_URL = "https://www.realtor.com/international/sv?channel=rent"
REALTOR_PHOTO_CDN = "https://s1.rea.global/img/600x400-prop/"  # Corrected CDN URL with size prefix
SQFT_TO_M2 = 0.092903  # Conversion factor from sq ft to sq meters

# ============== VIVOLATAM CONFIG ==============
VIVOLATAM_BASE_URL = "https://www.vivolatam.com"
VIVOLATAM_LISTINGS_URL = "https://www.vivolatam.com/es/el-salvador/bienes-raices/m"
VIVOLATAM_CDN = "https://cdn.vivolatam.com"

# How many pages to fetch concurrently
CONCURRENT_PAGES = 10
# Maximum listings to get (set to None for unlimited)
MAX_LISTINGS = None

# ============== MUNICIPIOS DE EL SALVADOR ==============
# Lista completa de los 262 municipios organizados por departamento
MUNICIPIOS_EL_SALVADOR = {
    "Ahuachapán": [
        "Ahuachapán", "Apaneca", "Atiquizaya", "Concepción de Ataco", "El Refugio",
        "Guaymango", "Jujutla", "San Francisco Menéndez", "San Lorenzo", "San Pedro Puxtla",
        "Tacuba", "Turín"
    ],
    "Santa Ana": [
        "Candelaria de la Frontera", "Chalchuapa", "Coatepeque", "El Congo", "El Porvenir",
        "Masahuat", "Metapán", "San Antonio Pajonal", "San Sebastián Salitrillo", "Santa Ana",
        "Santa Rosa Guachipilín", "Santiago de la Frontera", "Texistepeque"
    ],
    "Sonsonate": [
        "Acajutla", "Armenia", "Caluco", "Cuisnahuat", "Izalco", "Juayúa",
        "Nahuizalco", "Nahulingo", "Salcoatitán", "San Antonio del Monte", "San Julián",
        "Santa Catarina Masahuat", "Santa Isabel Ishuatán", "Santo Domingo de Guzmán",
        "Sonsonate", "Sonzacate"
    ],
    "Chalatenango": [
        "Agua Caliente", "Arcatao", "Azacualpa", "Chalatenango", "Citalá", "Comalapa",
        "Concepción Quezaltepeque", "Dulce Nombre de María", "El Carrizal", "El Paraíso",
        "La Laguna", "La Palma", "La Reina", "Las Vueltas", "Nombre de Jesús",
        "Nueva Concepción", "Nueva Trinidad", "Ojos de Agua", "Potonico", "San Antonio de la Cruz",
        "San Antonio Los Ranchos", "San Fernando", "San Francisco Lempa", "San Francisco Morazán",
        "San Ignacio", "San Isidro Labrador", "San José Cancasque", "San José Las Flores",
        "San Luis del Carmen", "San Miguel de Mercedes", "San Rafael", "Santa Rita",
        "Tejutla"
    ],
    "La Libertad": [
        "Antiguo Cuscatlán", "Chiltiupán", "Ciudad Arce", "Colón", "Comasagua", "Huizúcar",
        "Jayaque", "Jicalapa", "La Libertad", "Nuevo Cuscatlán", "Opico", "Quezaltepeque",
        "Sacacoyo", "San José Villanueva", "San Juan Opico", "San Matías", "San Pablo Tacachico",
        "Santa Tecla", "Talnique", "Tamanique", "Teotepeque", "Tepecoyo", "Zaragoza"
    ],
    "San Salvador": [
        "Aguilares", "Apopa", "Ayutuxtepeque", "Cuscatancingo", "Delgado", "El Paisnal",
        "Guazapa", "Ilopango", "Mejicanos", "Nejapa", "Panchimalco", "Rosario de Mora",
        "San Marcos", "San Martín", "San Salvador", "Santiago Texacuangos", "Santo Tomás",
        "Soyapango", "Tonacatepeque"
    ],
    "Cuscatlán": [
        "Candelaria", "Cojutepeque", "El Carmen", "El Rosario", "Monte San Juan",
        "Oratorio de Concepción", "San Bartolomé Perulapía", "San Cristóbal", "San José Guayabal",
        "San Pedro Perulapán", "San Rafael Cedros", "San Ramón", "Santa Cruz Analquito",
        "Santa Cruz Michapa", "Suchitoto", "Tenancingo"
    ],
    "La Paz": [
        "Cuyultitán", "El Rosario", "Jerusalén", "Mercedes La Ceiba", "Olocuilta",
        "Paraíso de Osorio", "San Antonio Masahuat", "San Emigdio", "San Francisco Chinameca",
        "San Juan Nonualco", "San Juan Talpa", "San Juan Tepezontes", "San Luis La Herradura",
        "San Luis Talpa", "San Miguel Tepezontes", "San Pedro Masahuat", "San Pedro Nonualco",
        "San Rafael Obrajuelo", "Santa María Ostuma", "Santiago Nonualco", "Tapalhuaca",
        "Zacatecoluca"
    ],
    "Cabañas": [
        "Cinquera", "Dolores", "Guacotecti", "Ilobasco", "Jutiapa", "San Isidro",
        "Sensuntepeque", "Tejutepeque", "Victoria"
    ],
    "San Vicente": [
        "Apastepeque", "Guadalupe", "San Cayetano Istepeque", "San Esteban Catarina",
        "San Ildefonso", "San Lorenzo", "San Sebastián", "San Vicente", "Santa Clara",
        "Santo Domingo", "Tecoluca", "Tepetitán", "Verapaz"
    ],
    "Usulután": [
        "Alegría", "Berlín", "California", "Concepción Batres", "El Triunfo", "Ereguayquín",
        "Estanzuelas", "Jiquilisco", "Jucuapa", "Jucuarán", "Mercedes Umaña", "Nueva Granada",
        "Ozatlán", "Puerto El Triunfo", "San Agustín", "San Buenaventura", "San Dionisio",
        "San Francisco Javier", "Santa Elena", "Santa María", "Santiago de María",
        "Tecapán", "Usulután"
    ],
    "San Miguel": [
        "Carolina", "Chapeltique", "Chinameca", "Chirilagua", "Ciudad Barrios", "Comacarán",
        "El Tránsito", "Lolotique", "Moncagua", "Nueva Guadalupe", "Nuevo Edén de San Juan",
        "Quelepa", "San Antonio", "San Gerardo", "San Jorge", "San Luis de la Reina",
        "San Miguel", "San Rafael Oriente", "Sesori", "Uluazapa"
    ],
    "Morazán": [
        "Arambala", "Cacaopera", "Chilanga", "Corinto", "Delicias de Concepción", "El Divisadero",
        "El Rosario", "Gualococti", "Guatajiagua", "Joateca", "Jocoaitique", "Jocoro",
        "Lolotiquillo", "Meanguera", "Osicala", "Perquín", "San Carlos", "San Fernando",
        "San Francisco Gotera", "San Isidro", "San Simón", "Sensembra", "Sociedad",
        "Torola", "Yamabal", "Yoloaiquín"
    ],
    "La Unión": [
        "Anamorós", "Bolívar", "Concepción de Oriente", "Conchagua", "El Carmen", "El Sauce",
        "Intipucá", "La Unión", "Lislique", "Meanguera del Golfo", "Nueva Esparta",
        "Pasaquina", "Polorós", "San Alejo", "San José", "Santa Rosa de Lima", "Yayantique", "Yucuaiquín"
    ]
}

# Crear lista plana de todos los municipios para búsqueda rápida
ALL_MUNICIPIOS = []
MUNICIPIO_TO_DEPARTAMENTO = {}
for depto, municipios in MUNICIPIOS_EL_SALVADOR.items():
    for muni in municipios:
        ALL_MUNICIPIOS.append(muni)
        MUNICIPIO_TO_DEPARTAMENTO[muni.lower()] = {"municipio": muni, "departamento": depto}

# Agregar variantes comunes y nombres alternativos
MUNICIPIO_ALIASES = {
    # San Salvador area
    "santa tecla": "Santa Tecla",
    "nueva san salvador": "Santa Tecla",
    "antiguo cuscatlan": "Antiguo Cuscatlán",
    "san salvador": "San Salvador",
    "soyapango": "Soyapango",
    "mejicanos": "Mejicanos",
    "apopa": "Apopa",
    "ilopango": "Ilopango",
    "san martin": "San Martín",
    "san marcos": "San Marcos",
    "ciudad merliot": "Santa Tecla",
    "merliot": "Santa Tecla",
    "escalon": "San Salvador",
    "escalón": "San Salvador",
    "colonia escalon": "San Salvador",
    "colonia escalón": "San Salvador",
    "zona rosa": "San Salvador",
    "metrocentro": "San Salvador",
    "centro historico": "San Salvador",
    "centro histórico": "San Salvador",
    "el boqueron": "San Salvador",
    "el boquerón": "San Salvador",
    
    # La Libertad area
    "la libertad": "La Libertad",
    "puerto la libertad": "La Libertad",
    "el tunco": "La Libertad",
    "playa el tunco": "La Libertad",
    "colon": "Colón",
    "lourdes colon": "Colón",
    "lourdes colón": "Colón",
    "lourdes": "Colón",
    "san juan opico": "San Juan Opico",
    "opico": "San Juan Opico",
    "ciudad arce": "Ciudad Arce",
    "quezaltepeque": "Quezaltepeque",
    "zaragoza": "Zaragoza",
    "santa tecla": "Santa Tecla",
    "nuevo cuscatlan": "Nuevo Cuscatlán",
    "nuevo cuscatlán": "Nuevo Cuscatlán",
    "san luis talpa": "San Luis Talpa",
    "comalapa": "San Luis Talpa",  # Comalapa Flats está en San Luis Talpa
    "comalapa flats": "San Luis Talpa",
    
    # La Paz department
    "la paz": "Zacatecoluca",  # Capital del departamento
    "zacatecoluca": "Zacatecoluca",
    "olocuilta": "Olocuilta",
    "san luis la herradura": "San Luis La Herradura",
    "la costa del sol": "San Luis La Herradura",
    "costa del sol": "San Luis La Herradura",
    "san juan nonualco": "San Juan Nonualco",
    "santiago nonualco": "Santiago Nonualco",
    
    # Cuscatlán department
    "cuscatlan": "Cojutepeque",  # Capital del departamento
    "cuscatlán": "Cojutepeque",
    "cojutepeque": "Cojutepeque",
    "suchitoto": "Suchitoto",
    "san pedro perulapan": "San Pedro Perulapán",
    "san pedro perulapán": "San Pedro Perulapán",
    
    # San Vicente department
    "san vicente": "San Vicente",
    "tecoluca": "Tecoluca",
    
    # Chalatenango area
    "la palma": "La Palma",
    "el pital": "San Ignacio",
    "chalatenango": "Chalatenango",
    "nueva concepcion": "Nueva Concepción",
    "nueva concepción": "Nueva Concepción",
    
    # Sonsonate area
    "juayua": "Juayúa",
    "juayúa": "Juayúa",
    "ataco": "Concepción de Ataco",
    "concepcion de ataco": "Concepción de Ataco",
    "apaneca": "Apaneca",
    "ruta de las flores": "Juayúa",
    "sonsonate": "Sonsonate",
    "izalco": "Izalco",
    "nahuizalco": "Nahuizalco",
    "acajutla": "Acajutla",
    "armenia": "Armenia",
    
    # Santa Ana area
    "santa ana": "Santa Ana",
    "metapan": "Metapán",
    "metapán": "Metapán",
    "chalchuapa": "Chalchuapa",
    "el congo": "El Congo",
    "coatepeque": "Coatepeque",
    
    # Ahuachapán area
    "ahuachapan": "Ahuachapán",
    "ahuachapán": "Ahuachapán",
    
    # Usulután area
    "usulutan": "Usulután",
    "usulután": "Usulután",
    "jiquilisco": "Jiquilisco",
    "berlin": "Berlín",
    "berlín": "Berlín",
    "alegria": "Alegría",
    "alegría": "Alegría",
    "santiago de maria": "Santiago de María",
    "santiago de maría": "Santiago de María",
    
    # San Miguel area
    "san miguel": "San Miguel",
    "chinameca": "Chinameca",
    "ciudad barrios": "Ciudad Barrios",
    "chirilagua": "Chirilagua",
    "el cuco": "Chirilagua",
    "playa el cuco": "Chirilagua",
    
    # La Unión area
    "la union": "La Unión",
    "la unión": "La Unión",
    "conchagua": "Conchagua",
    "santa rosa de lima": "Santa Rosa de Lima",
    
    # Morazán area
    "morazan": "San Francisco Gotera",
    "morazán": "San Francisco Gotera",
    "san francisco gotera": "San Francisco Gotera",
    "perquin": "Perquín",
    "perquín": "Perquín",
    
    # Cabañas area
    "cabanas": "Sensuntepeque",
    "cabañas": "Sensuntepeque",
    "sensuntepeque": "Sensuntepeque",
    "ilobasco": "Ilobasco",
    
    # Panchimalco area
    "planes de renderos": "Panchimalco",
    "los planes": "Panchimalco",
    "panchimalco": "Panchimalco"
}


def normalize_text(text):
    """Normalize text for comparison: lowercase, remove accents and special chars."""
    if not text:
        return ""
    import unicodedata
    # Lowercase
    text = text.lower()
    # Remove accents
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text


def detect_municipio(location, description="", title=""):
    """
    Detect municipality from location, description, and title fields.
    Analyzes all three fields to find the best match.
    Returns a dict with municipio_detectado and departamento.
    """
    # Combine all texts for searching (title often has the most specific location info)
    combined_text = f"{title or ''} {location or ''} {description or ''}".lower()
    combined_normalized = normalize_text(combined_text)
    
    # First, check aliases (most specific matches) - sorted by length (longer first)
    sorted_aliases = sorted(MUNICIPIO_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
    for alias, municipio in sorted_aliases:
        if alias in combined_text or normalize_text(alias) in combined_normalized:
            depto_info = MUNICIPIO_TO_DEPARTAMENTO.get(municipio.lower(), {})
            return {
                "municipio_detectado": municipio,
                "departamento": depto_info.get("departamento", "")
            }
    
    # Sort municipios by length (longer first) to match more specific names first
    sorted_municipios = sorted(ALL_MUNICIPIOS, key=len, reverse=True)
    
    # Check in title first (highest priority - often has most specific info)
    title_normalized = normalize_text(title or "")
    for municipio in sorted_municipios:
        muni_lower = municipio.lower()
        muni_normalized = normalize_text(municipio)
        
        if muni_lower in (title or "").lower() or muni_normalized in title_normalized:
            depto_info = MUNICIPIO_TO_DEPARTAMENTO.get(muni_lower, {})
            return {
                "municipio_detectado": municipio,
                "departamento": depto_info.get("departamento", "")
            }
    
    # Then check in location
    location_normalized = normalize_text(location or "")
    for municipio in sorted_municipios:
        muni_lower = municipio.lower()
        muni_normalized = normalize_text(municipio)
        
        if muni_lower in (location or "").lower() or muni_normalized in location_normalized:
            depto_info = MUNICIPIO_TO_DEPARTAMENTO.get(muni_lower, {})
            return {
                "municipio_detectado": municipio,
                "departamento": depto_info.get("departamento", "")
            }
    
    # Check in description as fallback
    desc_normalized = normalize_text(description or "")
    for municipio in sorted_municipios:
        muni_lower = municipio.lower()
        muni_normalized = normalize_text(municipio)
        
        if muni_lower in (description or "").lower() or muni_normalized in desc_normalized:
            depto_info = MUNICIPIO_TO_DEPARTAMENTO.get(muni_lower, {})
            return {
                "municipio_detectado": municipio,
                "departamento": depto_info.get("departamento", "")
            }
    
    # No match found
    return {
        "municipio_detectado": "No identificado",
        "departamento": ""
    }


def make_absolute_url(href):
    """Convert relative URL to absolute URL."""
    if href.startswith("http"):
        return href
    return BASE_URL + href


def fetch_page(url):
    """Fetch a single page and return listings found."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        links = soup.select("a.d3-ad-tile__description")
        urls = []
        for link in links:
            href = link.get("href")
            if href:
                urls.append(make_absolute_url(href))
        return urls
    except Exception as e:
        return []


def get_listing_urls_fast(base_url, max_listings=None):
    """Collect listing URLs using concurrent requests."""
    all_urls = set()
    page = 1
    consecutive_empty = 0
    
    print(f"  Fetching listings (concurrent mode)...")
    
    while True:
        # Prepare batch of pages to fetch
        page_urls = []
        for i in range(CONCURRENT_PAGES):
            page_url = base_url if page == 1 else f"{base_url}.{page}"
            page_urls.append((page, page_url))
            page += 1
        
        # Fetch pages concurrently
        new_urls_found = 0
        with ThreadPoolExecutor(max_workers=CONCURRENT_PAGES) as executor:
            futures = {executor.submit(fetch_page, url): pg for pg, url in page_urls}
            for future in as_completed(futures):
                urls = future.result()
                for url in urls:
                    if url not in all_urls:
                        all_urls.add(url)
                        new_urls_found += 1
        
        print(f"    Pages {page - CONCURRENT_PAGES}-{page-1}: found {new_urls_found} new URLs (total: {len(all_urls)})")
        
        # Stop if no new URLs found
        if new_urls_found == 0:
            consecutive_empty += 1
            if consecutive_empty >= 2:
                print(f"  No more listings found.")
                break
        else:
            consecutive_empty = 0
        
        # Stop if we have enough
        if max_listings and len(all_urls) >= max_listings:
            print(f"  Reached limit of {max_listings} listings.")
            break
        
        time.sleep(0.2)  # Small delay between batches
    
    urls_list = list(all_urls)
    if max_listings:
        return urls_list[:max_listings]
    return urls_list


def scrape_listing(url, listing_type):
    """Scrape a single listing page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Check if listing was deleted/removed
        page_text_lower = soup.get_text().lower()
        deleted_indicators = [
            "anuncio borrado",
            "eliminado por el anunciante",
            "ya no está disponible",
            "this listing has been removed",
            "listing not found",
            "página no encontrada"
        ]
        for indicator in deleted_indicators:
            if indicator in page_text_lower:
                return None  # Skip deleted listings

        # Title
        title_el = soup.select_one("h1") or soup.select_one("title")
        title = title_el.get_text(strip=True) if title_el else ""
        
        # Skip if title indicates deleted
        if not title or "borrado" in title.lower() or "eliminado" in title.lower():
            return None

        # Price
        price_el = soup.select_one(".estate-price") or soup.select_one(".d3-price")
        price = price_el.get_text(strip=True) if price_el else ""
        if not price:
            match = re.search(r"\$[\d,\.]+", soup.get_text())
            price = match.group(0) if match else ""

        # Specs - from insight attributes (bedrooms, bathrooms, area, etc.)
        specs = {}
        for item in soup.select(".d3-property-insight__attribute"):
            label_el = item.select_one(".d3-property-insight__attribute-title")
            value_el = item.select_one(".d3-property-insight__attribute-value")
            if label_el and value_el:
                label = label_el.get_text(strip=True)
                value = value_el.get_text(strip=True)
                label_lower = label.lower()
                if "recámaras" in label_lower or "habitaciones" in label_lower:
                    specs["bedrooms"] = value
                elif "baños" in label_lower:
                    specs["bathrooms"] = value
                elif "área" in label_lower or "terreno" in label_lower or "construcción" in label_lower:
                    # Store area info with original label
                    specs[label] = value

        # Details - from d3-property-details__detail-label (Location, Published date, etc.)
        details = {}
        published_date = ""
        location = ""
        
        for label_el in soup.select(".d3-property-details__detail-label"):
            # Get the label text (direct text node, not nested elements)
            label_text = ""
            for content in label_el.children:
                if isinstance(content, str):
                    label_text = content.strip()
                    break
            if not label_text:
                label_text = label_el.get_text(strip=True)
            
            # Clean up label
            label_text = label_text.replace(":", "").strip()
            
            # Get the value from the nested <p> element
            value_el = label_el.select_one(".d3-property-details__detail, p")
            if value_el:
                value = value_el.get_text(strip=True)
                if label_text and value:
                    details[label_text] = value
                    
                    # Extract specific fields
                    if "publicado" in label_text.lower():
                        published_date = value
                    elif "localización" in label_text.lower() or "ubicación" in label_text.lower():
                        location = value
        
        # Fallback for location if not found in details
        if not location:
            location = details.get("Ubicación", details.get("Localización", ""))

        # Description - preserve line breaks
        desc_el = soup.select_one(".d3-property-about__text")
        if desc_el:
            # Get text with line breaks preserved (use \n as separator between elements)
            description = remove_emojis(desc_el.get_text(separator='\n', strip=True)[:1000])
        else:
            description = ""

        # External ID (needed for image extraction)
        external_id = url.rstrip("/").split("/")[-1]

        # Images - extract ALL unique images using listing ID pattern
        images = []
        page_html = str(soup)
        
        # Find all unique image suffixes for this listing (format: 29872317_abc123)
        image_pattern = re.compile(rf'{external_id}_([a-z0-9]+)')
        unique_suffixes = set(image_pattern.findall(page_html))
        
        if unique_suffixes:
            # Build the image path from listing ID (e.g., 29872317 -> sv/29/87/23/17/)
            id_str = str(external_id)
            if len(id_str) >= 8:
                path_parts = [id_str[i:i+2] for i in range(0, 8, 2)]
                img_path = f"sv/{'/'.join(path_parts)}"
                
                # Construct high-resolution URLs for all unique images
                for suffix in unique_suffixes:
                    img_url = f"https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/{img_path}/{external_id}_{suffix}"
                    images.append(img_url)
        
        # Fallback: also check for direct photo URLs if pattern didn't work
        if not images:
            for script in soup.select("script"):
                script_text = script.string or ""
                photo_urls = re.findall(r'https://photos\.encuentra24\.com[^"\'\\\s]+', script_text)
                for img_url in photo_urls:
                    img_url = re.sub(r'[\\"\'"].*$', '', img_url)
                    if img_url not in images:
                        images.append(img_url)



        # Price-based listing type adjustment:
        # If marked as sale but price < $1000, it's likely a rent listing
        price_value = parse_price(price)
        if listing_type == "sale" and price_value and price_value < 1000:
            listing_type = "rent"

        # Detect municipality from location, description and title
        municipio_info = detect_municipio(location, description, title)

        return {
            "title": title,
            "price": price,
            "location": location,
            "published_date": published_date,
            "listing_type": listing_type,
            "url": url,
            "external_id": external_id,
            "specs": specs,
            "details": details,
            "description": description,
            "images": images,
            "source": "Encuentra24",
            "active": True,
            "municipio_detectado": municipio_info["municipio_detectado"],
            "departamento": municipio_info["departamento"],
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        return None


def scrape_listings_concurrent(urls, listing_type, max_workers=10):
    """Scrape multiple listings concurrently."""
    results = []
    total = len(urls)
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_listing, url, listing_type): url for url in urls}
        for future in as_completed(futures):
            completed += 1
            data = future.result()
            if data and data.get("title"):
                results.append(data)
            if completed % 50 == 0 or completed == total:
                print(f"    Scraped {completed}/{total} ({len(results)} with data)")
    
    return results


# ============== MICASASV FUNCTIONS ==============

def slug_to_external_id(slug):
    """Convert a URL slug to a numeric external_id using hash."""
    # Use first 15 digits of MD5 hash to create a unique bigint
    hash_hex = hashlib.md5(slug.encode()).hexdigest()
    # Take first 15 hex chars and convert to int (fits in bigint)
    return int(hash_hex[:15], 16)


def get_micasasv_listing_urls(base_url, max_listings=None):
    """Collect listing URLs from MiCasaSV sitemap.
    
    Note: MiCasaSV explore page loads content dynamically with JavaScript,
    so we use the WordPress sitemap instead which lists all listings.
    """
    all_urls = []
    
    print(f"  Fetching MiCasaSV listings from sitemap...")
    
    # Use the WordPress sitemap to get all listing URLs
    sitemap_url = "https://micasasv.com/job_listing-sitemap.xml"
    
    try:
        resp = requests.get(sitemap_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"    Error fetching sitemap: HTTP {resp.status_code}")
            return []
        
        # Parse URLs from sitemap using regex (no lxml dependency)
        urls = re.findall(r'<loc>(https://micasasv\.com/listing/[^<]+)</loc>', resp.text)
        
        for url in urls:
            if url not in all_urls:
                all_urls.append(url)
        
        print(f"    Found {len(all_urls)} listing URLs in sitemap")
        
    except Exception as e:
        print(f"    Error fetching sitemap: {e}")
        return []
    
    # Apply limit if specified
    if max_listings and len(all_urls) > max_listings:
        print(f"  Limiting to {max_listings} listings")
        return all_urls[:max_listings]
    
    return all_urls




def scrape_micasasv_listing(url, listing_type):
    """Scrape a single MiCasaSV listing page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None
            
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Title
        title_el = soup.select_one("h1.case27-primary-text") or soup.select_one("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        
        if not title:
            return None
        
        # Price - look in .price-or-date .value or search for $ in page
        price = ""
        price_el = soup.select_one(".price-or-date .value")
        if price_el:
            price = price_el.get_text(strip=True)
        else:
            # Fallback: find element containing $ price
            for el in soup.select(".lmb-label, .value, span"):
                text = el.get_text(strip=True)
                if "$" in text and any(c.isdigit() for c in text):
                    price = text
                    break
        
        # Determine listing type from price label
        price_label = soup.select_one(".price-or-date .lmb-label")
        if price_label:
            label_text = price_label.get_text(strip=True).lower()
            if "alquiler" in label_text or "renta" in label_text:
                listing_type = "rent"
            elif "venta" in label_text:
                listing_type = "sale"
        
        # Location - from block-type-location (map section) or tagline
        location = ""
        loc_block = soup.select_one(".block-type-location")
        if loc_block:
            # Extract address from location block, removing "Ubicación" and "Obtener Indicaciones"
            loc_text = loc_block.get_text(separator=' ', strip=True)
            # Clean up the location text
            full_address = re.sub(r'(Ubicaci[óo]n|Obtener Indicaciones)', '', loc_text).strip()
            
            # Normalize location to just city/municipality to match Encuentra24 format
            # Format is typically: "Street Address, ZIP City, Departamento de X, El Salvador"
            # We want to extract just the city name
            if full_address:
                parts = full_address.split(',')
                if len(parts) >= 2:
                    # Second part usually contains "ZIP City" like "01101 San Salvador"
                    city_part = parts[1].strip()
                    # Remove ZIP code (5-digit number at start)
                    city_match = re.sub(r'^\d{5}\s*', '', city_part).strip()
                    if city_match:
                        location = city_match
                    else:
                        # Try third part if second didn't work
                        if len(parts) >= 3:
                            dept_part = parts[2].strip()
                            # Remove "Departamento de" prefix
                            location = re.sub(r'^Departamento de\s*', '', dept_part).strip()
                
                # If we couldn't parse, use a simplified version (remove El Salvador and street)
                if not location:
                    # Remove "El Salvador" and try to get municipality from Departamento
                    simplified = re.sub(r',?\s*El Salvador\s*$', '', full_address)
                    dept_match = re.search(r'Departamento de\s+(\w+)', simplified)
                    if dept_match:
                        location = dept_match.group(1)
                    else:
                        # Last resort: take the second comma-separated part
                        location = parts[1].strip() if len(parts) > 1 else full_address
        
        # Fallback to tagline if no location found
        if not location:
            tagline_el = soup.select_one("h2.profile-tagline")
            if tagline_el:
                location = tagline_el.get_text(strip=True)
        
        # Description
        desc_el = soup.select_one(".block-field-job_description .wp-editor-content")
        if not desc_el:
            desc_el = soup.select_one(".wp-editor-content")
        description = remove_emojis(desc_el.get_text(separator='\n', strip=True)[:1000]) if desc_el else ""
        
        # Specs - from table blocks
        specs = {}
        details = {}
        
        # Look for table items with label/value pairs
        for item in soup.select(".block-type-table .table-block li, .details-list li"):
            label_el = item.select_one(".item-label")
            value_el = item.select_one(".item-value")
            if label_el and value_el:
                label = label_el.get_text(strip=True).lower()
                value = value_el.get_text(strip=True)
                
                # Map to specs
                if "habitacion" in label or "recamara" in label or "dormitorio" in label:
                    specs["bedrooms"] = value
                elif "baño" in label:
                    specs["bathrooms"] = value
                elif "área" in label or "tamaño" in label or "terreno" in label or "construcción" in label:
                    specs[label_el.get_text(strip=True)] = value
                else:
                    details[label_el.get_text(strip=True)] = value
        
        # Also check for quick specs in card format
        for li in soup.select(".listing-details-3 .details-list li"):
            icon = li.select_one("i")
            value_span = li.select_one("span")
            if icon and value_span:
                icon_class = icon.get("class", [])
                value = value_span.get_text(strip=True)
                if any("clone" in c or "bed" in c for c in icon_class):
                    specs["bedrooms"] = value
                elif any("bath" in c or "shower" in c for c in icon_class):
                    specs["bathrooms"] = value
                elif any("box" in c or "area" in c for c in icon_class):
                    specs["area"] = value
        
        # Categories
        categories = []
        for cat_el in soup.select(".block-type-categories .category-name, .category a"):
            cat_text = cat_el.get_text(strip=True)
            if cat_text:
                categories.append(cat_text)
        if categories:
            details["categorias"] = ", ".join(categories)
        
        # Images - from photoswipe items
        images = []
        for img_link in soup.select("a.photoswipe-item"):
            href = img_link.get("href", "")
            if href and href.startswith("http"):
                images.append(href)
        
        # Fallback: get from img tags
        if not images:
            for img in soup.select(".gallery-image img, .lf-background"):
                src = img.get("src") or img.get("data-src", "")
                style = img.get("style", "")
                if src and src.startswith("http"):
                    images.append(src)
                elif "background-image" in style:
                    match = re.search(r'url\(["\']?(https?://[^"\')\s]+)["\']?\)', style)
                    if match:
                        images.append(match.group(1))
        

        
        # External ID from slug
        slug = url.rstrip("/").split("/")[-1]
        external_id = slug_to_external_id(slug)
        
        # Published date - try meta tags (og:updated_time or article:published_time)
        published_date = ""
        # First try og:updated_time (most reliable for MiCasaSV)
        meta_date = soup.select_one("meta[property='og:updated_time']")
        if not meta_date:
            meta_date = soup.select_one("meta[property='article:published_time']")
        if not meta_date:
            meta_date = soup.select_one("meta[property='article:modified_time']")
        
        if meta_date:
            date_val = meta_date.get("content", "")
            if date_val:
                try:
                    # Parse ISO format and convert to DD/MM/YYYY
                    # Handle timezone offset format
                    dt = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
                    published_date = dt.strftime("%d/%m/%Y")
                except:
                    pass
        
        # Price-based listing type adjustment:
        # If marked as sale but price < $1000, it's likely a rent listing
        price_value = parse_price(price)
        if listing_type == "sale" and price_value and price_value < 1000:
            listing_type = "rent"
        
        # Detect municipality from location, description and title
        municipio_info = detect_municipio(location, description, title)
        
        return {
            "title": title,
            "price": price,
            "location": location,
            "published_date": published_date,
            "listing_type": listing_type,
            "url": url,
            "external_id": str(external_id),
            "specs": specs,
            "details": details,
            "description": description,
            "images": images,
            "source": "MiCasaSV",
            "active": True,
            "municipio_detectado": municipio_info["municipio_detectado"],
            "departamento": municipio_info["departamento"],
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None


def scrape_micasasv_listings_concurrent(urls, listing_type, max_workers=5):
    """Scrape multiple MiCasaSV listings concurrently."""
    results = []
    total = len(urls)
    completed = 0
    
    # Use fewer workers for MiCasaSV to avoid rate limiting
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_micasasv_listing, url, listing_type): url for url in urls}
        for future in as_completed(futures):
            completed += 1
            data = future.result()
            if data and data.get("title"):
                results.append(data)
            if completed % 20 == 0 or completed == total:
                print(f"    Scraped {completed}/{total} ({len(results)} with data)")
    
    return results


# ============== REALTOR.COM FUNCTIONS ==============

def get_realtor_listings_from_page(page_url):
    """
    Extract listing data directly from Realtor.com page's __NEXT_DATA__ JSON.
    Returns a list of normalized listing dictionaries.
    """
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            print(f"  Failed to fetch {page_url}: {response.status_code}")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        next_data = soup.select_one("script#__NEXT_DATA__")
        
        if not next_data or not next_data.string:
            print("  No __NEXT_DATA__ found")
            return []
        
        data = json.loads(next_data.string)
        apollo_state = data.get("props", {}).get("apolloState", {})
        
        listings = []
        
        # Helper to resolve Apollo references
        def resolve_ref(ref):
            if isinstance(ref, dict) and ref.get("id"):
                return apollo_state.get(ref["id"], ref)
            return ref
        
        # Extract all ListingDetail entries
        for key, value in apollo_state.items():
            if not key.startswith("ListingDetail:"):
                continue
            if not isinstance(value, dict):
                continue
            if not value.get("id"):
                continue
            
            listing_id = value.get("id")
            
            # Skip if no URL
            url_key = 'detailPageUrl({"language":"en"})'
            detail_url = value.get(url_key)
            if not detail_url:
                continue
            
            full_url = f"{REALTOR_BASE_URL}{detail_url}"
            
            # Resolve price
            price_key = 'price({"currency":"USD","language":"en"})'
            price_ref = value.get(price_key)
            price_data = resolve_ref(price_ref)
            price_str = ""
            if isinstance(price_data, dict):
                price_str = price_data.get("displayListingPrice", "")
            
            # Resolve location - Only show department (state)
            location_ref = value.get("location")
            location_data = resolve_ref(location_ref)
            location = ""
            if isinstance(location_data, dict):
                # Only use the state/department, formatted nicely
                state = (location_data.get("state") or "").replace("-", " ").replace(" Department", "")
                location = state.strip()
            
            # Resolve multilingual for title
            ml_key = 'multilingual({"language":"en"})'
            ml_ref = value.get(ml_key)
            ml_data = resolve_ref(ml_ref)
            title = value.get("displayAddress", "")
            if isinstance(ml_data, dict) and ml_data.get("fullAddress"):
                title = ml_data["fullAddress"]
            
            # Resolve photos
            photos = value.get("photos", [])
            image_urls = []
            for photo_ref in photos[:10]:  # Limit to 10 photos
                photo_data = resolve_ref(photo_ref)
                if isinstance(photo_data, dict) and photo_data.get("path"):
                    image_urls.append(f"{REALTOR_PHOTO_CDN}{photo_data['path']}")
            

            
            # Specs
            specs = {}
            bedrooms = value.get("bedrooms")
            bathrooms = value.get("bathrooms")
            parking = value.get("parkingSpaces")
            
            if bedrooms:
                specs["habitaciones"] = str(bedrooms)
            if bathrooms:
                specs["banos"] = str(bathrooms)
            if parking:
                specs["parqueo"] = str(parking)
            
            # Building/Land size - Convert from sqft to m²
            size_key = 'buildingSize({"language":"en","unit":"SQUARE_FEET"})'
            size_val = value.get(size_key)
            if size_val:
                try:
                    # Remove commas and convert
                    sqft = float(str(size_val).replace(",", ""))
                    m2 = round(sqft * SQFT_TO_M2, 2)
                    specs["area"] = f"{m2} m²"
                except:
                    specs["area"] = str(size_val)
            
            land_key = 'landSize({"language":"en","unit":"SQUARE_FEET"})'
            land_val = value.get(land_key)
            if land_val:
                try:
                    sqft = float(str(land_val).replace(",", ""))
                    m2 = round(sqft * SQFT_TO_M2, 2)
                    specs["terreno"] = f"{m2} m²"
                except:
                    specs["terreno"] = str(land_val)
            
            # Determine listing type from channel parameter in URL or default to sale
            listing_type = "sale"  # Default
            
            # Parse price for type adjustment
            price_value = parse_price(price_str)
            if listing_type == "sale" and price_value and price_value < 1000:
                listing_type = "rent"
            
            # Property type - extract from JSON format
            prop_types_key = 'propertyTypes({"language":"en"})'
            prop_types_raw = value.get(prop_types_key, {})
            property_type = ""
            if isinstance(prop_types_raw, dict) and prop_types_raw.get("json"):
                # Format: {'type': 'json', 'json': ['House']}
                prop_list = prop_types_raw.get("json", [])
                if isinstance(prop_list, list) and len(prop_list) > 0:
                    property_type = prop_list[0]
            elif isinstance(prop_types_raw, list) and len(prop_types_raw) > 0:
                property_type = prop_types_raw[0] if isinstance(prop_types_raw[0], str) else ""
            
            # Extract description directly (available in JSON)
            description = value.get("description", "")
            if description:
                description = remove_emojis(description[:1000])
            
            # Extract published date
            published_date = ""
            published_at = value.get("publishedAt", "")
            if published_at:
                try:
                    # Format: "2026-01-22 08:20:47" -> "22/01/2026"
                    dt = datetime.strptime(published_at.split(" ")[0], "%Y-%m-%d")
                    published_date = dt.strftime("%d/%m/%Y")
                except:
                    pass
            
            # Build details dict
            details = {}
            if property_type:
                details["property_type"] = property_type
            channel = value.get("channel", "")
            if channel:
                details["channel"] = channel
            listing_category = value.get("listingCategory", "")
            if listing_category:
                details["category"] = listing_category
            
            # Detect municipality from location, description and title
            municipio_info = detect_municipio(location, description, title)
            
            listings.append({
                "title": remove_emojis(title[:200]) if title else "",
                "price": price_str,
                "location": location,
                "published_date": published_date,
                "listing_type": listing_type,
                "url": full_url,
                "external_id": str(listing_id),
                "specs": specs,
                "details": details,
                "description": description,
                "images": image_urls,
                "source": "Realtor",
                "active": True,
                "municipio_detectado": municipio_info["municipio_detectado"],
                "departamento": municipio_info["departamento"],
                "last_updated": datetime.now().isoformat()
            })
        
        return listings
        
    except Exception as e:
        import traceback
        print(f"  Error fetching {page_url}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return []


def enrich_realtor_listing(listing):
    """
    Fetch additional details from individual Realtor.com listing page.
    Adds description and published_date that are not available in list view.
    """
    try:
        url = listing.get("url", "")
        if not url:
            return listing
        
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code != 200:
            return listing
        
        soup = BeautifulSoup(response.text, "html.parser")
        next_data = soup.select_one("script#__NEXT_DATA__")
        
        if not next_data or not next_data.string:
            return listing
        
        data = json.loads(next_data.string)
        apollo_state = data.get("props", {}).get("apolloState", {})
        
        # Find the listing detail
        listing_id = listing.get("external_id", "")
        detail_key = f"ListingDetail:{listing_id}"
        detail = apollo_state.get(detail_key, {})
        
        if not detail:
            # Try to find any ListingDetail
            for key, value in apollo_state.items():
                if key.startswith("ListingDetail:") and isinstance(value, dict):
                    detail = value
                    break
        
        # Extract description
        description = detail.get("description", "")
        if description:
            listing["description"] = remove_emojis(description[:1000])
        
        # Extract published date
        published_at = detail.get("publishedAt", "")
        if published_at:
            try:
                dt = datetime.strptime(published_at.split(" ")[0], "%Y-%m-%d")
                listing["published_date"] = dt.strftime("%d/%m/%Y")
            except:
                pass
        
        # Extract property type if not already set
        if not listing.get("details", {}).get("property_type"):
            prop_types = detail.get("propertyTypes", {})
            if isinstance(prop_types, dict) and prop_types.get("json"):
                prop_list = prop_types.get("json", [])
                if prop_list:
                    listing.setdefault("details", {})["property_type"] = prop_list[0]
        
        return listing
        
    except Exception as e:
        print(f"    Error enriching {listing.get('url', '')}: {e}")
        return listing


def enrich_realtor_listings(listings, max_workers=5):
    """Enrich multiple Realtor.com listings concurrently."""
    if not listings:
        return listings
    
    print(f"  Enriching {len(listings)} listings with full details...")
    enriched = []
    completed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(enrich_realtor_listing, listing): listing for listing in listings}
        for future in as_completed(futures):
            completed += 1
            result = future.result()
            enriched.append(result)
            if completed % 10 == 0 or completed == len(listings):
                print(f"    Enriched {completed}/{len(listings)}")
    
    return enriched

def get_realtor_all_listings(base_url, max_listings=None, listing_type="sale"):
    """
    Fetch all listings from Realtor.com by paginating through pages.
    Each page contains listings embedded in __NEXT_DATA__.
    """
    all_listings = []
    page = 1
    max_pages = 50  # Safety limit
    
    while page <= max_pages:
        # Build URL with page parameter
        if "?" in base_url:
            page_url = f"{base_url}&page={page}"
        else:
            page_url = f"{base_url}?page={page}"
        
        print(f"  Fetching page {page}: {page_url}")
        listings = get_realtor_listings_from_page(page_url)
        
        if not listings:
            print(f"  No more listings found on page {page}")
            break
        
        # Set listing type for all listings
        for listing in listings:
            # Override listing type based on channel
            if "channel=rent" in base_url:
                listing["listing_type"] = "rent"
            else:
                listing["listing_type"] = "sale"
                # Apply price-based adjustment
                price_value = parse_price(listing.get("price", ""))
                if price_value and price_value < 1000:
                    listing["listing_type"] = "rent"
        
        all_listings.extend(listings)
        print(f"    Got {len(listings)} listings (total: {len(all_listings)})")
        
        # Check limit
        if max_listings and len(all_listings) >= max_listings:
            all_listings = all_listings[:max_listings]
            print(f"  Reached limit of {max_listings} listings")
            break
        
        # Check if we got fewer listings than expected (likely last page)
        if len(listings) < 20:
            print(f"  Likely last page (only {len(listings)} listings)")
            break
        
        page += 1
        time.sleep(0.5)  # Rate limiting
    
    return all_listings


def main_realtor(limit=None):
    """Main scraper function for Realtor.com International (El Salvador)."""
    all_listings = []
    remaining_limit = limit
    sale_data = []
    rent_data = []
    
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} total listings from Realtor.com ***")
    
    # --- SALE LISTINGS ---
    print("\n=== Scraping Realtor.com SALE Listings ===")
    sale_data = get_realtor_all_listings(REALTOR_SALE_URL, max_listings=remaining_limit, listing_type="sale")
    print(f"  Got {len(sale_data)} sale listings from list view")
    
    # Enrich with individual page data (description, published_date)
    if sale_data:
        sale_data = enrich_realtor_listings(sale_data)
    
    all_listings.extend(sale_data)
    
    # Check if we need more listings
    if remaining_limit:
        remaining_limit = remaining_limit - len(sale_data)
    
    # --- RENT LISTINGS (only if limit not reached or no limit) ---
    if remaining_limit is None or remaining_limit > 0:
        print("\n=== Scraping Realtor.com RENT Listings ===")
        rent_data = get_realtor_all_listings(REALTOR_RENT_URL, max_listings=remaining_limit, listing_type="rent")
        print(f"  Got {len(rent_data)} rent listings from list view")
        
        # Enrich with individual page data
        if rent_data:
            rent_data = enrich_realtor_listings(rent_data)
        
        all_listings.extend(rent_data)
    else:
        print("\n=== Skipping RENT Listings (limit already reached) ===")
    
    return all_listings, sale_data, rent_data


def main_micasasv(limit=None):
    """Main scraper function for MiCasaSV."""
    all_listings = []
    remaining_limit = limit
    sale_data = []
    rent_data = []
    
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} total listings from MiCasaSV ***")
    
    # --- SALE LISTINGS ---
    print("\n=== Scraping MiCasaSV SALE Listings ===")
    sale_urls = get_micasasv_listing_urls(MICASASV_SALE_URL, max_listings=remaining_limit)
    print(f"Found {len(sale_urls)} sale URLs. Scraping details...")
    sale_data = scrape_micasasv_listings_concurrent(sale_urls, "sale")
    all_listings.extend(sale_data)
    print(f"  Got {len(sale_data)} sale listings")
    
    # Check if we need more listings
    if remaining_limit:
        remaining_limit = remaining_limit - len(sale_data)

    # --- RENT LISTINGS (only if limit not reached or no limit) ---
    if remaining_limit is None or remaining_limit > 0:
        print("\n=== Scraping MiCasaSV RENT Listings ===")
        rent_urls = get_micasasv_listing_urls(MICASASV_RENT_URL, max_listings=remaining_limit)
        print(f"Found {len(rent_urls)} rent URLs. Scraping details...")
        rent_data = scrape_micasasv_listings_concurrent(rent_urls, "rent")
        all_listings.extend(rent_data)
        print(f"  Got {len(rent_data)} rent listings")
    else:
        print("\n=== Skipping RENT Listings (limit already reached) ===")

    return all_listings, sale_data, rent_data


def main_encuentra24(limit=None):
    """Main scraper function for Encuentra24."""
    all_listings = []
    remaining_limit = limit
    sale_data = []
    rent_data = []
    
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} total listings from Encuentra24 ***")
    
    # --- SALE LISTINGS ---
    print("\n=== Scraping Encuentra24 SALE Listings ===")
    sale_urls = get_listing_urls_fast(SALE_URL, max_listings=remaining_limit)
    print(f"Found {len(sale_urls)} sale URLs. Scraping details concurrently...")
    sale_data = scrape_listings_concurrent(sale_urls, "sale")
    all_listings.extend(sale_data)
    print(f"  Got {len(sale_data)} sale listings")
    
    # Check if we need more listings
    if remaining_limit:
        remaining_limit = remaining_limit - len(sale_data)

    # --- RENT LISTINGS (only if limit not reached or no limit) ---
    if remaining_limit is None or remaining_limit > 0:
        print("\n=== Scraping Encuentra24 RENT Listings ===")
        rent_urls = get_listing_urls_fast(RENT_URL, max_listings=remaining_limit)
        print(f"Found {len(rent_urls)} rent URLs. Scraping details concurrently...")
        rent_data = scrape_listings_concurrent(rent_urls, "rent")
        all_listings.extend(rent_data)
        print(f"  Got {len(rent_data)} rent listings")
    else:
        print("\n=== Skipping RENT Listings (limit already reached) ===")

    return all_listings, sale_data, rent_data


# ============== VIVOLATAM FUNCTIONS ==============

def get_vivolatam_listing_urls(url_file=None, max_listings=None):
    """
    Collect listing URLs from Vivo Latam sitemap.
    
    Fetches property URLs from the Vivo Latam sitemap. If a URL file is provided,
    it will use that instead of the sitemap.
    
    Args:
        url_file: Optional path to file containing property URLs (one per line)
        max_listings: Maximum number of listings to return
        
    Returns:
        List of property page URLs
    """
    all_urls = []
    
    # If URL file is provided, use it
    if url_file and os.path.exists(url_file):
        print(f"  Reading Vivo Latam URLs from file: {url_file}")
        with open(url_file, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and url.startswith('https://www.vivolatam.com'):
                    all_urls.append(url)
        print(f"    Found {len(all_urls)} URLs in file")
    else:
        # Fetch from sitemap automatically
        print(f"  Fetching Vivo Latam URLs from sitemap...")
        sitemap_url = "https://www.vivolatam.com/sitemap/property_listings.xml"
        
        try:
            resp = requests.get(sitemap_url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                # Extract Spanish URLs only (avoid duplicates with English versions)
                urls = re.findall(r'<loc>(https://www\.vivolatam\.com/es/[^<]+/l/[^<]+)</loc>', resp.text)
                all_urls = list(set(urls))  # Remove duplicates
                print(f"    Found {len(all_urls)} Spanish listing URLs in sitemap")
            else:
                print(f"    Error fetching sitemap: HTTP {resp.status_code}")
                return []
        except Exception as e:
            print(f"    Error fetching sitemap: {e}")
            return []
    
    if max_listings and len(all_urls) > max_listings:
        print(f"  Limiting to {max_listings} listings")
        return all_urls[:max_listings]
    
    return all_urls


def scrape_vivolatam_listing(url, listing_type="sale"):
    """Scrape a single Vivo Latam listing page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"  Failed to fetch {url}: HTTP {resp.status_code}")
            return None
            
        soup = BeautifulSoup(resp.text, "html.parser")
        page_text = soup.get_text()
        
        # Title from h1
        title_el = soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else ""
        
        if not title:
            print(f"  No title found for {url}")
            return None
        
        # Price extraction - look for JSON embedded price first (more accurate)
        # Pattern: "price":{"sale":{"value":4600000}} or "price":{"rent":{"value":1500}}
        price = None
        raw_html = resp.text
        
        # Try to find price in embedded JSON data
        sale_price_match = re.search(r'"price":\s*\{\s*"sale":\s*\{\s*"value":\s*(\d+)', raw_html)
        rent_price_match = re.search(r'"price":\s*\{\s*"rent":\s*\{\s*"value":\s*(\d+)', raw_html)
        
        if sale_price_match:
            price = int(sale_price_match.group(1))
        elif rent_price_match:
            price = int(rent_price_match.group(1))
        else:
            # Fallback to traditional regex on visible text (skip per-unit prices)
            # Match prices >= $1000 to avoid matching "$136 por v2"
            price_matches = re.findall(r'\$([\d,]+)(?:\.\d{2})?', page_text)
            for pm in price_matches:
                cleaned = pm.replace(',', '')
                if cleaned.isdigit() and int(cleaned) >= 1000:
                    price = int(cleaned)
                    break
        
        # Specs from text
        specs = {}
        bedroom_match = re.search(r'(\d+)\s*(?:dormitorio|habitaci)', page_text, re.I)
        bathroom_match = re.search(r'(\d+)\s*(?:baño|bath)', page_text, re.I)
        area_match = re.search(r'([\d,]+)\s*(?:m2|metros?\s*cuadrados?|m²)', page_text, re.I)
        
        if bedroom_match:
            specs["habitaciones"] = bedroom_match.group(1)
        if bathroom_match:
            specs["banos"] = bathroom_match.group(1)
        if area_match:
            specs["area"] = f"{area_match.group(1)} m²"
        
        # Description - look for content after "Descripción" heading
        description = ""
        desc_section = soup.find("h2", string=re.compile(r"Descripci[oó]n", re.I))
        if desc_section:
            # Get next siblings for description content
            next_el = desc_section.find_next_sibling()
            if next_el:
                description = next_el.get_text(strip=True)[:1000]
        
        # If no description from heading, try meta description
        if not description:
            og_desc = soup.find("meta", {"property": "og:description"})
            if og_desc and og_desc.get("content"):
                description = og_desc["content"][:1000]
        
        # Location from breadcrumb links
        location = ""
        loc_links = soup.select('a[href*="/bienes-raices/m/"]')
        if loc_links:
            # Get location from first valid link after the base
            for link in loc_links:
                link_text = link.get_text(strip=True)
                if link_text and link_text != "El Salvador bienes raices":
                    location = link_text
                    break
        
        # Generate external_id from URL slug
        slug = url.split('/')[-1]
        external_id = slug_to_external_id(slug)
        
        # Images from og:image meta tag and other sources
        images = []
        og_image = soup.find("meta", {"property": "og:image"})
        if og_image and og_image.get("content"):
            images.append(og_image["content"])
        
        # Also look for other image sources
        for img in soup.find_all("img"):
            src = img.get("src", "") or img.get("data-src", "")
            if src and "cdn.vivolatam.com" in src and src not in images:
                images.append(src)
                if len(images) >= 10:  # Cap at 10 images
                    break
        
        # Detect listing type from title/URL
        title_lower = title.lower()
        url_lower = url.lower()
        if "alquiler" in title_lower or "renta" in title_lower or "rent" in url_lower:
            listing_type = "rent"
        else:
            listing_type = "sale"
        
        # Detect municipality
        municipio_info = detect_municipio(location, description, title)
        
        listing = {
            "title": remove_emojis(title[:200]) if title else "",
            "price": price,
            "location": location,
            "published_date": "",  # Not easily available on page
            "listing_type": listing_type,
            "url": url,
            "external_id": str(external_id),
            "specs": specs,
            "details": {},
            "description": remove_emojis(description) if description else "",
            "images": images,
            "source": "VivoLatam",
            "active": True,
            "municipio_detectado": municipio_info["municipio_detectado"],
            "departamento": municipio_info["departamento"],
            "last_updated": datetime.now().isoformat()
        }
        
        print(f"  Scraped: {title[:50]}...")
        return listing
        
    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None


def scrape_vivolatam_listings_concurrent(urls, listing_type="sale", max_workers=5):
    """Scrape multiple Vivo Latam listings concurrently."""
    results = []
    
    print(f"  Scraping {len(urls)} Vivo Latam listings with {max_workers} workers...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(scrape_vivolatam_listing, url, listing_type): url for url in urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception as e:
                print(f"  Error processing {url}: {e}")
    
    return results


def main_vivolatam(limit=None, url_file=None):
    """Main scraper function for Vivo Latam."""
    all_listings = []
    sale_data = []
    rent_data = []
    
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} listings from Vivo Latam ***")
    
    # Get listing URLs from file
    urls = get_vivolatam_listing_urls(url_file=url_file, max_listings=limit)
    
    if not urls:
        print("  No Vivo Latam URLs found to scrape")
        return [], [], []
    
    print(f"\n=== Scraping Vivo Latam Listings ===")
    listings = scrape_vivolatam_listings_concurrent(urls, "sale")
    all_listings.extend(listings)
    
    # Separate by listing type
    sale_data = [l for l in all_listings if l.get("listing_type") == "sale"]
    rent_data = [l for l in all_listings if l.get("listing_type") == "rent"]
    
    print(f"  Vivo Latam total: {len(all_listings)} ({len(sale_data)} sales, {len(rent_data)} rentals)")
    
    return all_listings, sale_data, rent_data


def main(encuentra24=True, micasasv=False, realtor=False, vivolatam=False, limit=None, vivolatam_urls=None):
    """
    Main scraper function that orchestrates scraping from multiple sources.
    
    Args:
        encuentra24: If True, scrape from Encuentra24
        micasasv: If True, scrape from MiCasaSV
        realtor: If True, scrape from Realtor.com International
        vivolatam: If True, scrape from Vivo Latam
        limit: Optional max number of listings to scrape (per source if both enabled)
        vivolatam_urls: Path to file containing Vivo Latam URLs to scrape
    """
    all_listings = []
    total_sale = 0
    total_rent = 0
    
    # --- ENCUENTRA24 ---
    if encuentra24:
        print("\n" + "="*60)
        print("SCRAPING SOURCE: Encuentra24")
        print("="*60)
        listings, sale_data, rent_data = main_encuentra24(limit)
        all_listings.extend(listings)
        total_sale += len(sale_data)
        total_rent += len(rent_data)
    
    # --- MICASASV ---
    if micasasv:
        print("\n" + "="*60)
        print("SCRAPING SOURCE: MiCasaSV")
        print("="*60)
        listings, sale_data, rent_data = main_micasasv(limit)
        all_listings.extend(listings)
        total_sale += len(sale_data)
        total_rent += len(rent_data)
    
    # --- REALTOR.COM ---
    if realtor:
        print("\n" + "="*60)
        print("SCRAPING SOURCE: Realtor.com International")
        print("="*60)
        listings, sale_data, rent_data = main_realtor(limit)
        all_listings.extend(listings)
        total_sale += len(sale_data)
        total_rent += len(rent_data)
    
    # --- VIVOLATAM ---
    if vivolatam:
        print("\n" + "="*60)
        print("SCRAPING SOURCE: Vivo Latam")
        print("="*60)
        listings, sale_data, rent_data = main_vivolatam(limit, url_file=vivolatam_urls)
        all_listings.extend(listings)
        total_sale += len(sale_data)
        total_rent += len(rent_data)

    # --- INSERT TO SUPABASE ---
    print("\n=== Inserting to Supabase ===")
    success, errors = insert_listings_batch(all_listings)
    print(f"  Inserted: {success} | Errors: {errors}")

    # --- ALSO SAVE JSON (backup) ---
    output_file = os.path.join(DATA_DIR, "listings_all_sources.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_listings, f, ensure_ascii=False, indent=2)

    # --- REFRESH MATERIALIZED VIEW ---
    print("\n=== Refreshing Materialized View ===")
    try:
        refresh_url = f"{SUPABASE_URL}/rest/v1/rpc/refresh_mv_sd_depto_stats"
        refresh_resp = requests.post(
            refresh_url,
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            },
            json={}
        )
        if refresh_resp.status_code in [200, 204]:
            print("  Materialized view refreshed successfully!")
        else:
            print(f"  Warning: Could not refresh view. Status: {refresh_resp.status_code}")
            print(f"  Response: {refresh_resp.text[:200]}")
    except Exception as e:
        print(f"  Warning: Error refreshing view: {e}")

    print(f"\n=== DONE ===")
    print(f"Total listings scraped: {len(all_listings)}")
    print(f"  - Sale: {total_sale}")
    print(f"  - Rent: {total_rent}")
    print(f"Supabase: {success} inserted, {errors} errors")
    print(f"JSON backup: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-source real estate scraper (Encuentra24, MiCasaSV, Realtor.com, Vivo Latam)"
    )
    parser.add_argument(
        "--Encuentra24",
        action="store_true",
        help="Scrape listings from Encuentra24"
    )
    parser.add_argument(
        "--MiCasaSV",
        action="store_true",
        help="Scrape listings from MiCasaSV"
    )
    parser.add_argument(
        "--Realtor",
        action="store_true",
        help="Scrape listings from Realtor.com International (El Salvador)"
    )
    parser.add_argument(
        "--VivoLatam",
        action="store_true",
        help="Scrape listings from Vivo Latam (El Salvador)"
    )
    parser.add_argument(
        "--vivolatam-urls",
        type=str,
        default=None,
        help="Optional: Path to file containing Vivo Latam URLs to scrape. If not provided, URLs are fetched from sitemap."
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Optional: Limit total number of listings to scrape per source (e.g., 10, 30, 100). If not set, scrapes all."
    )
    args = parser.parse_args()
    
    # Get source flags
    encuentra24 = args.Encuentra24
    micasasv = args.MiCasaSV
    realtor = args.Realtor
    vivolatam = args.VivoLatam
    
    # Default behavior: scrape from ALL sources if no source is specified
    if not encuentra24 and not micasasv and not realtor and not vivolatam:
        encuentra24 = True
        micasasv = True
        realtor = True
        vivolatam = True
        print("No source specified. Scraping from ALL sources: Encuentra24, MiCasaSV, Realtor, VivoLatam")
    
    main(
        encuentra24=encuentra24, 
        micasasv=micasasv, 
        realtor=realtor, 
        vivolatam=vivolatam,
        limit=args.limit,
        vivolatam_urls=args.vivolatam_urls
    )