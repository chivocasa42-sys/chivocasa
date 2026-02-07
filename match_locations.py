#!/usr/bin/env python3
"""
Location Matching for Scraped Data
===================================
Matches scrapped_data listings to sv_loc_group hierarchy (levels 2-5)
by analyzing title, location, details, and description fields.

Usage:
    python match_locations.py --full    # Process all listings
    python match_locations.py --new     # Process only unmatched listings
    python match_locations.py --dry-run # Preview without inserting
"""

import argparse
import json
import math
import unicodedata
import requests
from typing import Dict, List, Optional, Tuple
from supabase import create_client, Client

# Supabase credentials (hardcoded for convenience)
SUPABASE_URL = "https://zvamupbxzuxdgvzgbssn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp2YW11cGJ4enV4ZGd2emdic3NuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTA5MDMwNSwiZXhwIjoyMDg0NjY2MzA1fQ.VfONseJg19pMEymrc6FbdEQJUWxTzJdNlVTboAaRgEs"

BATCH_SIZE = 100
DEBUG = True  # Set to True to see sample data


def normalize_text(text: str) -> str:
    """Normalize text for matching: lowercase, remove accents, strip prefixes."""
    if not text:
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Remove accents (á→a, é→e, í→i, ó→o, ú→u, ñ→n)
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    
    return text.strip()


def remove_location_prefixes(text: str) -> str:
    """Remove common location prefixes for better matching."""
    prefixes = [
        'residencial ', 'colonia ', 'urbanizacion ', 'urbanización ',
        'barrio ', 'lotificacion ', 'lotificación ', 'reparto ',
        'comunidad ', 'cantón ', 'canton ', 'caserio ',
        'col. ', 'res. ', 'urb. ', 'bo. ',
        # Also add Spanish articles for cases like "La Cima" -> "Cima"
        'la ', 'el ', 'los ', 'las '
    ]
    normalized = normalize_text(text)
    # Keep stripping prefixes until none match (handles "Colonia La Cima" -> "Cima")
    changed = True
    while changed:
        changed = False
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                changed = True
                break
    return normalized.strip()


def extract_searchable_text(listing: dict) -> Dict[str, str]:
    """Extract text fields from listing for searching."""
    texts = {}
    
    # Title
    texts['title'] = normalize_text(listing.get('title', '') or '')
    
    # Location fields
    location = listing.get('location') or {}
    if isinstance(location, str):
        try:
            location = json.loads(location)
        except:
            location = {}
    
    loc_parts = []
    for key in ['municipio_detectado', 'direccion', 'departamento', 'zona']:
        val = location.get(key, '')
        if val:
            loc_parts.append(normalize_text(val))
    texts['location'] = ' '.join(loc_parts)
    
    # Details
    details = listing.get('details', '') or ''
    if isinstance(details, dict):
        details = json.dumps(details)
    texts['details'] = normalize_text(details)
    
    # Description
    texts['description'] = normalize_text(listing.get('description', '') or '')
    
    return texts


def load_location_groups(supabase: Client) -> Dict[int, Dict]:
    """Load all sv_loc_group tables into memory for fast matching.
    
    Note: L3 (municipalities), L4 (districts), L5 (departments) are static
    reference data that never changes. Only L2 (colonias) can grow via
    auto-creation from scraping.
    """
    groups = {}
    
    for level in [2, 3, 4, 5]:
        table_name = f"sv_loc_group{level}"
        try:
            # Paginate to get all rows (Supabase default limit is 1000)
            all_rows = []
            offset = 0
            page_size = 1000
            while True:
                result = supabase.table(table_name).select("*").range(offset, offset + page_size - 1).execute()
                if not result.data:
                    break
                all_rows.extend(result.data)
                if len(result.data) < page_size:
                    break
                offset += page_size
            
            groups[level] = {}
            
            for row in all_rows:
                loc_id = row['id']
                # Use loc_name (display) and loc_name_search (normalized)
                name = row.get('loc_name', '')
                normalized_name = normalize_text(row.get('loc_name_search', '') or name)
                name_no_prefix = remove_location_prefixes(name)
                
                # Get alternative names from details field (especially useful for L2)
                details = row.get('details', '') or ''
                alt_names = []
                if details:
                    # Details might contain alternative names like "Nueva San Salvador"
                    alt_names = [normalize_text(details)]
                    # Also add without prefix
                    alt_names.append(remove_location_prefixes(details))
                
                entry = {
                    'id': loc_id,
                    'name': name,
                    'normalized': normalized_name,
                    'no_prefix': name_no_prefix,
                    'alt_names': alt_names,
                    'parent_id': row.get('parent_loc_group')
                }
                
                # Load coordinates for L2 (colonias have cords JSONB)
                if level == 2:
                    cords = row.get('cords') or {}
                    if isinstance(cords, dict) and cords.get('latitude') and cords.get('longitude'):
                        entry['latitude'] = float(cords['latitude'])
                        entry['longitude'] = float(cords['longitude'])
                
                groups[level][loc_id] = entry
            
            print(f"   Loaded {len(groups[level])} entries from {table_name}")
            
            # Debug: show sample names
            if DEBUG and all_rows:
                samples = list(groups[level].values())[:3]
                print(f"   Sample L{level}: {[s['normalized'] for s in samples]}")
        except Exception as e:
            print(f"   ⚠️ Error loading {table_name}: {e}")
            groups[level] = {}
    
    return groups


def find_match_in_level(text: str, level_data: Dict, source: str) -> Optional[Tuple[int, float, str]]:
    """Find best match in a level's data. Returns (id, score, matched_text) or None."""
    if not text:
        return None
    
    import re
    best_match = None
    best_score = 0
    
    for loc_id, loc_info in level_data.items():
        normalized_name = loc_info['normalized']
        name_no_prefix = loc_info['no_prefix']
        alt_names = loc_info.get('alt_names', [])
        
        if not normalized_name:
            continue
        
        # Quick check: skip if name not in text at all (faster than regex)
        if normalized_name not in text:
            # Check alt_names too
            has_alt = False
            for alt in alt_names:
                if alt and alt in text:
                    has_alt = True
                    break
            if not has_alt:
                continue
        
        score = 0
        matched_name = normalized_name
        
        # Check primary name
        pattern = r'\b' + re.escape(normalized_name) + r'\b'
        if re.search(pattern, text):
            score = 1.0
            matched_name = loc_info['name']
        elif name_no_prefix and re.search(r'\b' + re.escape(name_no_prefix) + r'\b', text):
            score = 0.95
            matched_name = loc_info['name']
        # Check alternative names from details field
        elif alt_names:
            for alt in alt_names:
                if alt and re.search(r'\b' + re.escape(alt) + r'\b', text):
                    score = 0.9  # Slightly lower than primary name match
                    matched_name = f"{loc_info['name']} ({alt})"
                    break
        
        # Boost score based on source
        if score > 0:
            if source == 'title':
                score *= 1.0
            elif source == 'location':
                score *= 0.95
            elif source == 'details':
                score *= 0.85
            elif source == 'description':
                score *= 0.75
            
            if score > best_score:
                best_score = score
                best_match = (loc_id, score, matched_name)
    
    return best_match


def get_parent_chain(loc_id: int, level: int, groups: Dict) -> Dict[str, Optional[int]]:
    """Get all parent IDs for a matched location by following DB relationships."""
    result = {
        'locGroup2Id': None,
        'locGroup3Id': None,
        'locGroup4Id': None,
        'locGroup5Id': None
    }
    
    current_id = loc_id
    current_level = level
    
    while current_level <= 5:
        result[f'locGroup{current_level}Id'] = current_id
        
        if current_level == 5:
            break
        
        # Get parent ID from current level
        if current_id in groups.get(current_level, {}):
            parent_id = groups[current_level][current_id].get('parent_id')
            if parent_id:
                current_id = parent_id
                current_level += 1
            else:
                break
        else:
            break
    
    return result


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two coordinates using Haversine formula."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


# ============== L2 AUTO-CREATION ==============
# Known colonia/neighborhood prefixes used to extract candidate L2 names from scraped text.
# These are ordered by specificity (longer prefixes first to avoid partial matches).
COLONIA_PREFIXES = [
    'residencial ', 'urbanizacion ', 'urbanización ', 'lotificacion ', 'lotificación ',
    'comunidad ', 'condominio ', 'reparto ', 'colonia ', 'barrio ', 'cantón ', 'canton ',
    'caserio ', 'caserío ', 'parcelacion ', 'parcelación ',
    'res. ', 'col. ', 'urb. ', 'bo. ', 'cond. ',
]

# Minimum name length to accept as a valid colonia candidate (avoids single letters/noise)
MIN_COLONIA_NAME_LEN = 4

# Maximum words in a colonia name (prevents capturing entire listing titles)
MAX_COLONIA_NAME_WORDS = 5

# Distance threshold: don't create a new L2 if one already exists within this radius
L2_DEDUP_RADIUS_KM = 1.0

# Real estate terms that signal the end of a colonia name (stop the extraction here)
_STOP_WORDS = {
    # Sales / rental terms
    'en', 'venta', 'alquiler', 'renta', 'precio', 'usd', 'dolares',
    # Property specs
    'recamara', 'recamaras', 'habitacion', 'habitaciones', 'bano', 'banos',
    'dormitorio', 'dormitorios', 'garage', 'garaje', 'cochera',
    # Property types
    'casa', 'apartamento', 'terreno', 'local', 'bodega', 'oficina',
    # Lot / block / address parts
    'lote', 'lotes', 'pasaje', 'poligono', 'manzana', 'bloque', 'block',
    'edif', 'edificio', 'cluster', 'torre',
    # Measurements
    'metros', 'mt2', 'm2', 'v2', 'varas',
    # Infrastructure / roads
    'distrito', 'carretera', 'carreterea', 'km', 'calle', 'avenida',
    'boulevard', 'bulevar', 'autopista',
    # Prepositions / conjunctions that signal end of name
    'por', 'con', 'cerca', 'frente', 'atras', 'junto', 'sobre',
    'minutos',
    # Adjectives (not colonia names)
    'nueva', 'nuevo', 'exclusiva', 'exclusivo', 'hermosa', 'hermoso',
    'amplia', 'amplio', 'moderna', 'moderno', 'bonita', 'bonito',
    # Subdivision / phase markers
    'porcion', 'jurisdiccion', 'etapa', 'fase',
    'primera', 'segunda', 'tercera', 'cuarta', 'quinta',
    'uno', 'dos', 'tres', 'cuatro', 'cinco',
    # Roman numerals
    'i', 'ii', 'iii', 'iv', 'v', 'vi',
    # Directional
    'nor', 'poniente', 'oriente',
    # Colonia prefixes that appear MID-name signal a second location
    'residencial', 'urbanizacion', 'lotificacion', 'comunidad', 'condominio',
    'reparto', 'colonia', 'barrio', 'canton', 'caserio', 'parcelacion',
    # Commercial
    'comercial', 'industrial', 'recreativo',
}

# Names that are just generic adjectives/descriptions, not real colonia names
_INVALID_NAMES = {
    'exclusiva', 'exclusivo', 'nueva', 'nuevo', 'hermosa', 'hermoso',
    'moderna', 'moderno', 'bonita', 'bonito', 'amplia', 'amplio',
    'grande', 'pequena', 'privada', 'privado', 'comercial', 'recreativo',
    'hacienda',
}

# Trailing filler words to strip after all other cleanup
_TRAILING_FILLER = {'la', 'el', 'los', 'las', 'de', 'del', 'y', 'e', 'a',
                    'san', 'santa', 'nor', 'sur', 'oriente', 'poniente'}


_loc_stop_names_cache: Optional[set] = None


def _build_location_stop_names(groups: Dict) -> set:
    """Build a set of normalized L3/L4/L5 names to strip from candidates.
    
    Cached at module level because L3/L4/L5 data is static and never changes.
    Only L2 (colonias) can grow via auto-creation.
    """
    global _loc_stop_names_cache
    if _loc_stop_names_cache is not None:
        return _loc_stop_names_cache
    
    stop_names = set()
    for level in [3, 4, 5]:
        for info in groups.get(level, {}).values():
            name = info.get('normalized', '')
            if name and len(name) >= 3:
                stop_names.add(name)
            no_pref = info.get('no_prefix', '')
            if no_pref and len(no_pref) >= 3:
                stop_names.add(no_pref)
    
    _loc_stop_names_cache = stop_names
    return stop_names


def extract_colonia_candidate(texts: Dict[str, str], groups: Dict = None) -> Optional[Tuple[str, str, str]]:
    """Extract a candidate colonia/neighborhood name from listing text fields.
    
    Looks for known prefixes (Residencial, Colonia, etc.) followed by a name.
    Uses stop words, L3/L4/L5 cross-check, and trailing filler stripping.
    
    Args:
        texts: Dict of source -> normalized text (from extract_searchable_text or inline)
        groups: Optional location groups dict for L3/L4/L5 name cross-check
    
    Returns:
        (display_name, normalized_name, source_field) or None if no candidate found.
    """
    import re
    
    loc_stop_names = _build_location_stop_names(groups) if groups else set()
    
    high_confidence_sources = ['title', 'location']
    low_confidence_sources = ['details', 'description']
    
    def _strip_location_names(words: list) -> list:
        """Remove L3/L4/L5 location names from the word list.
        
        Two passes:
        1. Forward scan from position 2+: find the earliest L3/L4/L5 name
           match and truncate everything from that position onwards.
        2. Backward scan: strip trailing L3/L4/L5 names and filler repeatedly.
        """
        if not loc_stop_names or len(words) <= 1:
            return words
        
        # Pass 1: Forward scan — find earliest L3/L4/L5 name starting at pos 2+
        # (preserve at least 2 words of the actual colonia name)
        best_cut = len(words)
        for start in range(2, len(words)):
            for window_len in range(1, min(4, len(words) - start + 1)):
                window = ' '.join(words[start:start + window_len])
                if window in loc_stop_names:
                    best_cut = start
                    break
            if best_cut < len(words):
                break
        words = words[:best_cut]
        
        # Pass 2: Backward scan — strip trailing location names + filler repeatedly
        changed = True
        while changed and len(words) > 1:
            changed = False
            for suffix_len in range(1, min(4, len(words))):
                tail = ' '.join(words[-suffix_len:])
                if tail in loc_stop_names:
                    words = words[:-suffix_len]
                    changed = True
                    break
            while words and words[-1] in _TRAILING_FILLER:
                words = words[:-1]
                changed = True
        
        return words
    
    def _find_in_text(text: str, source: str) -> Optional[Tuple[str, str, str]]:
        if not text:
            return None
        for prefix in COLONIA_PREFIXES:
            idx = text.find(prefix)
            if idx == -1:
                continue
            after = text[idx + len(prefix):]
            # Collect words, stopping at stop words or digits.
            # Extra lookahead so location stripping has context.
            extra_lookahead = 4
            words = []
            for word_match in re.finditer(r'[a-záéíóúñü]+(?:\d+)?', after):
                w = word_match.group()
                if w in _STOP_WORDS:
                    break
                if w.isdigit() and len(words) > 0:
                    break
                words.append(w)
                if len(words) >= MAX_COLONIA_NAME_WORDS + extra_lookahead:
                    break
            
            if not words:
                continue
            
            # Strip L3/L4/L5 location names (repeatedly, handles stacked names)
            words = _strip_location_names(words)
            if not words:
                continue
            
            # Enforce word cap
            words = words[:MAX_COLONIA_NAME_WORDS]
            
            # Final trailing filler strip (after word cap may expose new trailing filler)
            while words and words[-1] in _TRAILING_FILLER:
                words = words[:-1]
            if not words:
                continue
            
            raw_name = ' '.join(words).strip()
            if len(raw_name) < MIN_COLONIA_NAME_LEN:
                continue
            
            # Filter out names that are just generic adjectives
            content_words = [w for w in words if w not in _TRAILING_FILLER]
            if not content_words or all(w in _INVALID_NAMES for w in content_words):
                continue
            
            # Build display name: prefix + cleaned name
            display = (prefix.strip() + ' ' + raw_name).strip()
            display = ' '.join(
                w.capitalize() if w not in ('de', 'del', 'la', 'las', 'los', 'el', 'y')
                else w for w in display.split()
            )
            normalized = normalize_text(display)
            return (display, normalized, source)
        return None
    
    # Try high-confidence sources first
    for source in high_confidence_sources:
        result = _find_in_text(texts.get(source, ''), source)
        if result:
            return result
    
    # Try low-confidence sources (will be flagged for staging, not immediate insert)
    for source in low_confidence_sources:
        result = _find_in_text(texts.get(source, ''), source)
        if result:
            return result
    
    return None


def check_l2_duplicate(candidate_normalized: str, lat: float, lng: float, 
                        l3_id: int, groups: Dict) -> Optional[int]:
    """Check if a candidate L2 already exists (by name or proximity).
    
    Args:
        candidate_normalized: Normalized candidate name
        lat, lng: Listing coordinates
        l3_id: Parent municipality ID
        groups: Location groups dict
    
    Returns:
        Existing L2 id if duplicate found, None if candidate is genuinely new.
    """
    l2_data = groups.get(2, {})
    candidate_stripped = remove_location_prefixes(candidate_normalized)
    
    for loc_id, info in l2_data.items():
        # Only check L2s in the same municipality
        if info.get('parent_id') != l3_id:
            continue
        
        # Check name similarity
        existing_normalized = info.get('normalized', '')
        existing_stripped = info.get('no_prefix', '')
        
        if (candidate_normalized == existing_normalized or 
            candidate_stripped == existing_stripped or
            candidate_normalized == existing_stripped or
            candidate_stripped == existing_normalized):
            return loc_id
        
        # Check coordinate proximity (within dedup radius)
        l2_lat = info.get('latitude')
        l2_lng = info.get('longitude')
        if l2_lat is not None and l2_lng is not None:
            dist = haversine_distance(lat, lng, l2_lat, l2_lng)
            if dist < L2_DEDUP_RADIUS_KM:
                return loc_id
    
    return None


def _next_l2_id(groups: Dict) -> int:
    """Compute the next available L2 id from in-memory groups (DB sequence is unreliable)."""
    l2_data = groups.get(2, {})
    return max(l2_data.keys(), default=0) + 1


def insert_auto_l2(display_name: str, normalized_name: str, lat: float, lng: float,
                    l3_id: int, groups: Dict, supabase_url: str = None, 
                    supabase_key: str = None) -> Optional[int]:
    """Insert a new auto-generated L2 entry into sv_loc_group2 and update in-memory groups.
    
    Uses explicit IDs computed from the in-memory groups dict because the DB
    sequence is out of sync. Retries with incremented IDs on 409 conflicts.
    
    Args:
        display_name: Human-readable name (e.g. "Residencial Los Almendros")
        normalized_name: Normalized search name
        lat, lng: Coordinates for the new L2
        l3_id: Parent municipality ID
        groups: Location groups dict (will be updated in-place)
        supabase_url: Optional Supabase URL
        supabase_key: Optional Supabase key
    
    Returns:
        New L2 id on success, None on failure.
    """
    url = supabase_url or SUPABASE_URL
    key = supabase_key or SUPABASE_KEY
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    max_retries = 3
    new_id = _next_l2_id(groups)
    
    for attempt in range(max_retries):
        payload = {
            "id": new_id,
            "loc_name": display_name,
            "loc_name_search": normalized_name,
            "parent_loc_group": l3_id,
            "cords": {"latitude": lat, "longitude": lng},
            "details": "auto-generated from scraping"
        }
        
        try:
            resp = requests.post(
                f"{url}/rest/v1/sv_loc_group2",
                headers=headers,
                json=payload,
                timeout=30
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                actual_id = data[0]['id'] if isinstance(data, list) and data else data.get('id', new_id)
                # Update in-memory groups so subsequent listings can match this L2
                groups.setdefault(2, {})[actual_id] = {
                    'id': actual_id,
                    'name': display_name,
                    'normalized': normalized_name,
                    'no_prefix': remove_location_prefixes(display_name),
                    'alt_names': [],
                    'parent_id': l3_id,
                    'latitude': lat,
                    'longitude': lng
                }
                print(f"    ✓ Auto-created L2 #{actual_id}: '{display_name}' under L3={l3_id} at ({lat:.4f}, {lng:.4f})")
                return actual_id
            elif resp.status_code == 409:
                # Duplicate key — increment and retry
                new_id += 1
                continue
            else:
                print(f"    ⚠️ Failed to insert auto L2 '{display_name}': {resp.status_code} - {resp.text[:200]}")
                break
        except Exception as e:
            print(f"    ⚠️ Exception inserting auto L2 '{display_name}': {e}")
            break
    
    return None


def stage_l2_candidate(display_name: str, normalized_name: str, lat: float, lng: float,
                        l3_id: int, source_field: str, external_id: int,
                        supabase_url: str = None, supabase_key: str = None) -> bool:
    """Stage a low-confidence L2 candidate for manual review.
    
    Inserts into unmatched_locations with special status 'l2_candidate' so it can
    be reviewed and promoted to a real L2 later.
    
    Returns True on success.
    """
    url = supabase_url or SUPABASE_URL
    key = supabase_key or SUPABASE_KEY
    
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=ignore-duplicates,return=minimal"
    }
    
    payload = {
        "external_id": external_id,
        "title": display_name[:500],
        "location_data": {
            "candidate_l2_name": display_name,
            "candidate_l2_normalized": normalized_name,
            "latitude": lat,
            "longitude": lng,
            "parent_l3_id": l3_id,
            "extracted_from": source_field
        },
        "searched_text": f"L2 candidate: {display_name} (from {source_field})",
        "source": "auto-l2-staging",
        "status": "l2_candidate"
    }
    
    try:
        resp = requests.post(
            f"{url}/rest/v1/unmatched_locations",
            headers=headers,
            json=payload,
            timeout=30
        )
        if resp.status_code in (200, 201):
            return True
    except Exception:
        pass
    return False


def try_create_l2_from_listing(texts: Dict[str, str], lat: float, lng: float,
                                l3_id: int, groups: Dict, external_id: int = None,
                                supabase_url: str = None, supabase_key: str = None) -> Optional[int]:
    """Attempt to create or stage a new L2 from listing text + coordinates.
    
    High confidence (prefix found in title/location) -> immediate insert.
    Low confidence (prefix found in description only) -> stage for review.
    
    Args:
        texts: Normalized text fields dict
        lat, lng: Listing coordinates
        l3_id: Confirmed parent municipality ID
        groups: Location groups dict
        external_id: Listing external_id (for staging)
    
    Returns:
        New L2 id if high-confidence insert succeeded, None otherwise.
    """
    candidate = extract_colonia_candidate(texts, groups=groups)
    if not candidate:
        return None
    
    display_name, normalized_name, source_field = candidate
    
    # Check for duplicates first
    existing_id = check_l2_duplicate(normalized_name, lat, lng, l3_id, groups)
    if existing_id:
        return existing_id  # Already exists, just return it for matching
    
    # High confidence: prefix found in title or location -> immediate insert
    if source_field in ('title', 'location'):
        new_id = insert_auto_l2(
            display_name, normalized_name, lat, lng, l3_id, groups,
            supabase_url=supabase_url, supabase_key=supabase_key
        )
        return new_id
    
    # Low confidence: found in description/details -> stage for review
    if external_id:
        stage_l2_candidate(
            display_name, normalized_name, lat, lng, l3_id, source_field,
            external_id, supabase_url=supabase_url, supabase_key=supabase_key
        )
    
    return None


def match_by_coordinates(lat: float, lng: float, groups: Dict, max_l2_km: float = 3.0, max_l3_km: float = 20.0,
                          texts: Dict[str, str] = None, external_id: int = None,
                          supabase_url: str = None, supabase_key: str = None) -> Optional[dict]:
    """Match a listing to L2/L3/L4/L5 hierarchy using coordinates.
    
    Two-tier approach:
    1. Find nearest L2 (colonia) within max_l2_km -> derive full L3/L4/L5 chain
    2. If no L2 close enough, compute L3 centroids (averaged from child L2 coords)
       and find nearest L3 (municipality) within max_l3_km -> derive L4/L5
    3. If Tier 2 matches L3 but no L2, attempt to auto-create an L2 from listing text
    
    Args:
        lat: Listing latitude
        lng: Listing longitude
        groups: Location groups dict from load_location_groups()
        max_l2_km: Maximum distance for L2 match (default 3km)
        max_l3_km: Maximum distance for L3 fallback match (default 20km)
        texts: Optional normalized text fields for L2 auto-creation
        external_id: Optional listing external_id for staging low-confidence candidates
        supabase_url: Optional Supabase URL for L2 insertion
        supabase_key: Optional Supabase key for L2 insertion
    
    Returns:
        dict with locGroup2Id..5Id, matchLevel, matchScore, matchSource, matchedText
        or None if nothing matches within thresholds.
    """
    if not lat or not lng:
        return None
    
    l2_data = groups.get(2, {})
    if not l2_data:
        return None
    
    # --- Tier 1: Find nearest L2 (colonia) ---
    best_l2_id = None
    best_l2_dist = float('inf')
    best_l2_name = ""
    
    for loc_id, info in l2_data.items():
        l2_lat = info.get('latitude')
        l2_lng = info.get('longitude')
        if l2_lat is None or l2_lng is None:
            continue
        
        dist = haversine_distance(lat, lng, l2_lat, l2_lng)
        if dist < best_l2_dist:
            best_l2_dist = dist
            best_l2_id = loc_id
            best_l2_name = info.get('name', '')
    
    if best_l2_id is not None and best_l2_dist <= max_l2_km:
        # L2 matched — derive full chain
        result = {
            'locGroup2Id': None, 'locGroup3Id': None, 'locGroup4Id': None, 'locGroup5Id': None,
            'matchLevel': 2,
            'matchScore': round(max(0.5, 1.0 - (best_l2_dist / max_l2_km)), 2),
            'matchSource': 'coordinates',
            'matchedText': f"{best_l2_name} ({best_l2_dist:.2f}km)"[:255]
        }
        chain = get_parent_chain(best_l2_id, 2, groups)
        result.update(chain)
        return result
    
    # --- Tier 2: No close L2 — compute L3 centroids and find nearest municipality ---
    # Build L3 centroids by averaging the coordinates of all child L2 entries
    l3_centroids = {}  # l3_id -> {'lat_sum', 'lng_sum', 'count'}
    for loc_id, info in l2_data.items():
        l2_lat = info.get('latitude')
        l2_lng = info.get('longitude')
        parent_l3 = info.get('parent_id')
        if l2_lat is None or l2_lng is None or parent_l3 is None:
            continue
        if parent_l3 not in l3_centroids:
            l3_centroids[parent_l3] = {'lat_sum': 0.0, 'lng_sum': 0.0, 'count': 0}
        l3_centroids[parent_l3]['lat_sum'] += l2_lat
        l3_centroids[parent_l3]['lng_sum'] += l2_lng
        l3_centroids[parent_l3]['count'] += 1
    
    best_l3_id = None
    best_l3_dist = float('inf')
    best_l3_name = ""
    
    for l3_id, centroid in l3_centroids.items():
        if centroid['count'] == 0:
            continue
        c_lat = centroid['lat_sum'] / centroid['count']
        c_lng = centroid['lng_sum'] / centroid['count']
        dist = haversine_distance(lat, lng, c_lat, c_lng)
        if dist < best_l3_dist:
            best_l3_dist = dist
            best_l3_id = l3_id
            best_l3_name = groups.get(3, {}).get(l3_id, {}).get('name', '')
    
    if best_l3_id is not None and best_l3_dist <= max_l3_km:
        # L3 matched — derive L4/L5 from parent chain (no L2)
        result = {
            'locGroup2Id': None, 'locGroup3Id': None, 'locGroup4Id': None, 'locGroup5Id': None,
            'matchLevel': 3,
            'matchScore': round(max(0.4, 0.9 - (best_l3_dist / max_l3_km)), 2),
            'matchSource': 'coordinates',
            'matchedText': f"{best_l3_name} ({best_l3_dist:.2f}km)"[:255]
        }
        chain = get_parent_chain(best_l3_id, 3, groups)
        result.update(chain)
        
        # --- Tier 3: Try to auto-create L2 from listing text ---
        # We have coords + confirmed L3 but no L2 match. If the listing mentions
        # a recognizable colonia name, create a new L2 entry.
        if texts:
            auto_l2_id = try_create_l2_from_listing(
                texts, lat, lng, best_l3_id, groups,
                external_id=external_id,
                supabase_url=supabase_url, supabase_key=supabase_key
            )
            if auto_l2_id:
                result['locGroup2Id'] = auto_l2_id
                result['matchLevel'] = 2
                result['matchSource'] = 'coordinates+auto-l2'
                auto_name = groups.get(2, {}).get(auto_l2_id, {}).get('name', '')
                result['matchedText'] = f"{auto_name} (auto, {best_l3_name})"[:255]
        
        return result
    
    return None


def find_best_match_in_level(texts: Dict[str, str], level_data: Dict, parent_filter: Optional[int] = None) -> Optional[Tuple[int, float, str, str]]:
    """Find best match in a level, optionally filtering by parent_id.
    
    Args:
        texts: Dict of source -> normalized text
        level_data: Dict of loc_id -> location info
        parent_filter: If provided, only consider entries where parent_id == this value
    
    Returns: (loc_id, score, matched_text, source) or None
    """
    best = None
    best_score = 0
    
    for source in ['location', 'title', 'details', 'description']:  # location first for tie-breaker
        text = texts.get(source, '')
        if not text:
            continue
        
        # Filter level_data by parent if specified
        if parent_filter is not None:
            filtered_data = {k: v for k, v in level_data.items() if v.get('parent_id') == parent_filter}
        else:
            filtered_data = level_data
        
        match = find_match_in_level(text, filtered_data, source)
        if match:
            loc_id, score, matched_text = match
            # location source gets slight boost (tie-breaker)
            if source == 'location':
                score += 0.01
            if score > best_score:
                best_score = score
                best = (loc_id, score, matched_text, source)
    
    return best


def match_listing(listing: dict, groups: Dict) -> Optional[dict]:
    """Match a listing to location hierarchy using coordinates (primary) or text (fallback).
    
    Strategy:
    1. Try coordinate-based matching first (nearest L2 by distance)
    2. Fall back to text matching:
       a. Find L3 (municipality) first - most specific reliable match
       b. If found, derive full parent chain and search for L2 within it
       c. If no L3, find L5 (department) with disambiguation check
       d. Search within L5 for lower levels
       e. If no L5, try L2 directly as last resort
    """
    # Try coordinate-based matching first
    location = listing.get('location') or {}
    if isinstance(location, str):
        try:
            location = json.loads(location)
        except:
            location = {}
    
    lat = location.get('latitude') if isinstance(location, dict) else None
    lng = location.get('longitude') if isinstance(location, dict) else None
    
    # Extract texts early so we can pass them to coordinate matching for L2 auto-creation
    texts = extract_searchable_text(listing)
    ext_id = listing.get('external_id')
    
    if lat and lng:
        coord_result = match_by_coordinates(
            float(lat), float(lng), groups,
            texts=texts, external_id=ext_id
        )
        if coord_result:
            coord_result['externalId'] = ext_id
            return coord_result
    
    MIN_SCORE = 0.9  # Minimum score to accept a match
    
    # Helper to get all IDs at a level that belong to a department
    def get_ids_under_department(level: int, dept_id: int) -> set:
        """Get all location IDs at given level that belong to department."""
        if level == 4:
            # L4 directly has L5 as parent
            return {lid for lid, info in groups.get(4, {}).items() if info.get('parent_id') == dept_id}
        elif level == 3:
            # L3 -> L4 -> L5
            l4_ids = get_ids_under_department(4, dept_id)
            return {lid for lid, info in groups.get(3, {}).items() if info.get('parent_id') in l4_ids}
        elif level == 2:
            # L2 -> L3 -> L4 -> L5
            l3_ids = get_ids_under_department(3, dept_id)
            return {lid for lid, info in groups.get(2, {}).items() if info.get('parent_id') in l3_ids}
        return set()
    
    result = {
        'externalId': listing['external_id'],
        'locGroup2Id': None,
        'locGroup3Id': None,
        'locGroup4Id': None,
        'locGroup5Id': None,
        'matchLevel': None,
        'matchScore': None,
        'matchSource': None,
        'matchedText': None
    }
    
    # Step 1: Try L3 (Municipality) first - most reliable, prevents false department matches
    # E.g., "Antiguo Cuscatlán" matches L3 municipality (in La Libertad),
    # preventing a false L5 match to "Cuscatlán" department.
    l3_match = find_best_match_in_level(texts, groups.get(3, {}))
    
    if l3_match:
        l3_id, l3_score, l3_text, l3_source = l3_match
        if l3_score >= MIN_SCORE:
            parent_chain = get_parent_chain(l3_id, 3, groups)
            result.update(parent_chain)
            result['matchLevel'] = 3
            result['matchScore'] = round(l3_score, 2)
            result['matchSource'] = l3_source
            result['matchedText'] = l3_text[:255] if l3_text else None
            
            # Try to get L2 within this L3
            l2_match = find_best_match_in_level(texts, groups.get(2, {}), parent_filter=l3_id)
            if l2_match:
                l2_id, l2_score, l2_text, l2_source = l2_match
                if l2_score >= MIN_SCORE:
                    result['locGroup2Id'] = l2_id
                    result['matchLevel'] = 2
                    result['matchScore'] = round(l2_score, 2)
                    result['matchSource'] = l2_source
                    result['matchedText'] = l2_text[:255] if l2_text else None
            
            # If no L2 found but listing has coordinates, try auto-creating one
            if result['locGroup2Id'] is None and lat and lng:
                auto_l2_id = try_create_l2_from_listing(
                    texts, float(lat), float(lng), l3_id, groups,
                    external_id=ext_id
                )
                if auto_l2_id:
                    result['locGroup2Id'] = auto_l2_id
                    result['matchLevel'] = 2
                    result['matchSource'] = 'text+auto-l2'
                    auto_name = groups.get(2, {}).get(auto_l2_id, {}).get('name', '')
                    result['matchedText'] = f"{auto_name} (auto, {l3_text})"[:255]
            
            return result
    
    # Step 2: No L3 match - try L5 (Department) with disambiguation
    l5_match = find_best_match_in_level(texts, groups.get(5, {}))
    
    if l5_match:
        l5_id, l5_score, l5_text, l5_source = l5_match
        
        # Disambiguation: verify the department name isn't part of a longer L3 municipality
        # name that appears in the text. E.g., "Cuscatlán" dept should NOT match when
        # text says "Antiguo Cuscatlán" (a municipality in La Libertad).
        import re
        dept_name = groups.get(5, {}).get(l5_id, {}).get('normalized', '')
        disambiguated = False
        
        if dept_name:
            for l3_id_check, l3_info in groups.get(3, {}).items():
                l3_name = l3_info['normalized']
                # Check if L3 name contains the department name as a part (but isn't identical)
                if dept_name in l3_name and dept_name != l3_name:
                    # Check if the full L3 name appears in any text field
                    for src, txt in texts.items():
                        if not txt:
                            continue
                        if re.search(r'\b' + re.escape(l3_name) + r'\b', txt):
                            # The longer L3 name matches - use L3 instead of L5
                            parent_chain = get_parent_chain(l3_id_check, 3, groups)
                            result.update(parent_chain)
                            result['matchLevel'] = 3
                            result['matchScore'] = round(l5_score, 2)
                            result['matchSource'] = src
                            result['matchedText'] = l3_info['name'][:255]
                            
                            # Try L2 under this L3
                            l2_match = find_best_match_in_level(texts, groups.get(2, {}), parent_filter=l3_id_check)
                            if l2_match:
                                l2_id, l2_score, l2_text, l2_source = l2_match
                                if l2_score >= MIN_SCORE:
                                    result['locGroup2Id'] = l2_id
                                    result['matchLevel'] = 2
                                    result['matchScore'] = round(l2_score, 2)
                                    result['matchSource'] = l2_source
                                    result['matchedText'] = l2_text[:255] if l2_text else None
                            
                            disambiguated = True
                            break
                if disambiguated:
                    break
        
        if disambiguated:
            return result
        
        # Not ambiguous - proceed with L5 match
        result['locGroup5Id'] = l5_id
        result['matchLevel'] = 5
        result['matchScore'] = round(l5_score, 2)
        result['matchSource'] = l5_source
        result['matchedText'] = l5_text[:255] if l5_text else None
        
        # Search ALL lower levels under this department, find most specific match
        best_lower = None
        best_lower_level = 5
        best_lower_score = 0
        
        for level in [2, 3, 4]:
            valid_ids = get_ids_under_department(level, l5_id)
            if not valid_ids:
                continue
            filtered_data = {k: v for k, v in groups.get(level, {}).items() if k in valid_ids}
            if not filtered_data:
                continue
            match = find_best_match_in_level(texts, filtered_data)
            if match:
                loc_id, score, matched_text, source = match
                if score >= MIN_SCORE and level < best_lower_level:
                    best_lower = (loc_id, score, matched_text, source)
                    best_lower_level = level
                    best_lower_score = score
                elif score > best_lower_score and level == best_lower_level:
                    best_lower = (loc_id, score, matched_text, source)
                    best_lower_score = score
        
        if best_lower:
            loc_id, score, matched_text, source = best_lower
            parent_chain = get_parent_chain(loc_id, best_lower_level, groups)
            result.update(parent_chain)
            result['matchLevel'] = best_lower_level
            result['matchScore'] = round(score, 2)
            result['matchSource'] = source
            result['matchedText'] = matched_text[:255] if matched_text else None
        
        return result
    
    # Step 3: No L5 and no L3 - try L2 directly as last resort
    l2_match = find_best_match_in_level(texts, groups.get(2, {}))
    if l2_match:
        l2_id, l2_score, l2_text, l2_source = l2_match
        if l2_score >= MIN_SCORE:
            parent_chain = get_parent_chain(l2_id, 2, groups)
            result.update(parent_chain)
            result['matchLevel'] = 2
            result['matchScore'] = round(l2_score, 2)
            result['matchSource'] = l2_source
            result['matchedText'] = l2_text[:255] if l2_text else None
            return result
    
    return None  # No match found





def process_listings(supabase: Client, groups: Dict, mode: str, dry_run: bool = False, limit: int = 0):
    """Process listings and insert matches."""
    
    PAGE_SIZE = 1000  # Supabase default limit
    
    # Get listings to process
    if mode == 'full':
        print("\n📋 Loading ALL active listings...")
        all_listings = []
        offset = 0
        while True:
            result = supabase.table('scrapped_data').select(
                'external_id, title, location, details, description'
            ).eq('active', True).range(offset, offset + PAGE_SIZE - 1).execute()
            
            if not result.data:
                break
            all_listings.extend(result.data)
            print(f"   Loaded {len(all_listings)} listings...", flush=True)
            
            if len(result.data) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
        
        listings = all_listings
    else:  # 'new' mode
        print("\n📋 Loading unmatched listings...")
        # Get listings not yet in listing_location_match
        result = supabase.rpc('get_unmatched_listings').execute()
        if not result.data:
            # Fallback: get all active and filter client-side
            all_listings = []
            offset = 0
            while True:
                page = supabase.table('scrapped_data').select(
                    'external_id, title, location, details, description'
                ).eq('active', True).range(offset, offset + PAGE_SIZE - 1).execute()
                
                if not page.data:
                    break
                all_listings.extend(page.data)
                if len(page.data) < PAGE_SIZE:
                    break
                offset += PAGE_SIZE
            
            # Get matched IDs with pagination too
            matched_ids = []
            offset = 0
            while True:
                page = supabase.table('listing_location_match').select('externalId').range(offset, offset + PAGE_SIZE - 1).execute()
                if not page.data:
                    break
                matched_ids.extend(page.data)
                if len(page.data) < PAGE_SIZE:
                    break
                offset += PAGE_SIZE
            
            matched_set = {r['externalId'] for r in matched_ids}
            listings = [l for l in all_listings if l['external_id'] not in matched_set]
        else:
            listings = result.data
    
    # Apply limit if specified
    if limit > 0:
        listings = listings[:limit]
        print(f"   Found {len(result.data)} listings, processing first {limit}")
    else:
        print(f"   Found {len(listings)} listings to process")
    
    if not listings:
        print("   Nothing to process!")
        return
    
    # Process listings
    matches = []
    unmatched = []  # Track unmatched for insertion
    
    for i, listing in enumerate(listings):
        if (i + 1) % 100 == 0:
            print(f"   Processing... {i+1}/{len(listings)} (matched: {len(matches)})", flush=True)
        
        match = match_listing(listing, groups)
        if match:
            matches.append(match)
        else:
            # Track unmatched listing
            unmatched.append(listing)
            # Debug: show first few non-matches
            if DEBUG and len(unmatched) <= 3:
                texts = extract_searchable_text(listing)
                print(f"\n   🔍 DEBUG No match for #{listing['external_id']}:")
                print(f"      title: {texts['title'][:80]}..." if len(texts['title']) > 80 else f"      title: {texts['title']}")
                print(f"      location: {texts['location'][:80]}..." if len(texts['location']) > 80 else f"      location: {texts['location']}")
    
    print(f"\n📊 Results:")
    print(f"   ✓ Matched: {len(matches)}")
    print(f"   ✗ No match: {len(unmatched)}")
    
    # Show level breakdown
    level_counts = {}
    for m in matches:
        lvl = m['matchLevel']
        level_counts[lvl] = level_counts.get(lvl, 0) + 1
    for lvl in sorted(level_counts.keys()):
        print(f"   Level {lvl}: {level_counts[lvl]}")
    
    if dry_run:
        print("\n🔍 DRY RUN - Preview first 5 matches:")
        for m in matches[:5]:
            print(f"   {m['externalId']}: L{m['matchLevel']} '{m['matchedText']}' ({m['matchSource']}, {m['matchScore']})")
        return
    
    # Insert matches in batches (using ingest view with trigger)
    if matches:
        print(f"\n📤 Inserting {len(matches)} matches into listing_location_match_ingest...")
        for i in range(0, len(matches), BATCH_SIZE):
            batch = matches[i:i + BATCH_SIZE]
            try:
                supabase.table('listing_location_match_ingest').insert(batch).execute()
                print(f"   Batch {i//BATCH_SIZE + 1}: {len(batch)} rows ✓")
            except Exception as e:
                print(f"   Batch {i//BATCH_SIZE + 1}: ERROR - {e}")
        
        print("   ✅ Done!")
    
    # Insert unmatched listings into tracking table
    if unmatched:
        print(f"\n📤 Inserting {len(unmatched)} unmatched listings to tracking table...")
        unmatched_success = 0
        for u in unmatched:
            ext_id = u.get('external_id')
            if not ext_id:
                continue
            
            # Prepare location data
            loc = u.get('location')
            if isinstance(loc, dict):
                location_data = loc
            elif loc:
                location_data = {"raw": str(loc)}
            else:
                location_data = {}
            
            # Build searched text for debugging
            texts = extract_searchable_text(u)
            searched_text = f"title:{texts.get('title','')} | location:{texts.get('location','')}"
            
            try:
                supabase.table('unmatched_locations').upsert({
                    "external_id": ext_id,
                    "title": (u.get('title', '') or '')[:500],
                    "location_data": location_data,
                    "url": u.get('url', ''),
                    "searched_text": searched_text[:1000],
                    "source": "match_locations.py",
                    "status": "pending"
                }, on_conflict="external_id").execute()
                unmatched_success += 1
            except Exception as e:
                if DEBUG:
                    print(f"   Error inserting unmatched {ext_id}: {e}")
        
        print(f"   ✅ Inserted {unmatched_success}/{len(unmatched)} unmatched listings")


def match_scraped_listings(listings: list, supabase_url: str = None, supabase_key: str = None) -> Tuple[int, int]:
    """
    Match scraped listings to location hierarchy and insert to listing_location_match_ingest.
    
    This function is called by the scraper DURING scraping, using the raw scraped data
    (title, location text, details, description) to determine location matches.
    
    Args:
        listings: List of scraped listing dicts with:
            - external_id: Unique identifier
            - title: Listing title
            - location: Raw location string (e.g., "Colonia San Benito") 
            - details: Details dict or string (may contain "Dirección exacta", etc.)
            - description: Full description text
        supabase_url: Optional Supabase URL (uses default if not provided)
        supabase_key: Optional Supabase key (uses default if not provided)
    
    Returns:
        Tuple of (matched_count, error_count)
    """
    import requests
    
    url = supabase_url or SUPABASE_URL
    key = supabase_key or SUPABASE_KEY
    
    print("\n=== Matching Listings to Location Hierarchy ===")
    
    # Load location groups (uses Supabase client for loading)
    supabase = create_client(url, key)
    groups = load_location_groups(supabase)
    
    # Match all listings
    matches = []
    unmatched = []
    for listing in listings:
        # Get external_id
        ext_id = listing.get('external_id')
        if not ext_id:
            continue
        try:
            ext_id = int(ext_id)
        except (ValueError, TypeError):
            continue
        
        # Build searchable text from raw scraped data
        texts = {
            'title': normalize_text(listing.get('title', '') or ''),
            'location': normalize_text(str(listing.get('location', '') or '')),
            'details': normalize_text(str(listing.get('details', '') or '')),
            'description': normalize_text(listing.get('description', '') or '')
        }
        
        # Extract coordinates (stored directly on listing dict by scrapers)
        latitude = listing.get('latitude')
        longitude = listing.get('longitude')
        
        # Run matching algorithm (coordinates first, text fallback, L2 auto-creation)
        match_result = match_listing_with_texts(
            texts, groups, latitude=latitude, longitude=longitude,
            external_id=ext_id, supabase_url=url, supabase_key=key
        )
        
        # Only insert if we got at least one match
        if any(v for k, v in match_result.items() if k.startswith('locGroup') and v is not None):
            match_result['externalId'] = ext_id
            matches.append(match_result)
        else:
            # Track unmatched for logging
            unmatched.append({
                'external_id': ext_id,
                'title': (listing.get('title', '') or '')[:60],
                'location': str(listing.get('location', '') or '')[:80],
                'url': listing.get('url', '')
            })
    
    matched_count = len(matches)
    print(f"  Matched: {matched_count}/{len(listings)} listings")
    
    # Log and insert unmatched listings
    if unmatched:
        print(f"\n  ⚠️ UNMATCHED LISTINGS ({len(unmatched)}):") 
        for u in unmatched:
            print(f"    - ID: {u['external_id']}")
            print(f"      Title: {u['title']}...")
            print(f"      Location: {u['location']}")
            if u['url']:
                print(f"      URL: {u['url']}")
        
        # Insert unmatched listings into database for tracking
        print(f"\n  Inserting {len(unmatched)} unmatched listings to tracking table...")
        unmatched_headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        
        unmatched_success = 0
        for u in unmatched:
            # Get full listing data for this unmatched entry
            listing_data = next(
                (l for l in listings if l.get('external_id') == u['external_id']), 
                {}
            )
            
            # Prepare data for insert
            rpc_payload = {
                "p_external_id": u['external_id'],
                "p_title": (listing_data.get('title', '') or '')[:500],
                "p_location_data": listing_data.get('location') if isinstance(listing_data.get('location'), dict) else {"raw": str(listing_data.get('location', '') or '')},
                "p_url": u['url'],
                "p_searched_text": f"title:{u.get('title','')} | location:{u.get('location','')}",
                "p_source": listing_data.get('source', 'Unknown')
            }
            
            try:
                resp = requests.post(
                    f"{url}/rest/v1/rpc/insert_unmatched_location",
                    headers=unmatched_headers,
                    json=rpc_payload,
                    timeout=30
                )
                if resp.status_code in (200, 204):
                    unmatched_success += 1
                else:
                    # Try direct insert as fallback
                    direct_payload = {
                        "external_id": u['external_id'],
                        "title": rpc_payload["p_title"],
                        "location_data": rpc_payload["p_location_data"],
                        "url": rpc_payload["p_url"],
                        "searched_text": rpc_payload["p_searched_text"],
                        "source": rpc_payload["p_source"]
                    }
                    resp2 = requests.post(
                        f"{url}/rest/v1/unmatched_locations",
                        headers={**unmatched_headers, "Prefer": "resolution=ignore-duplicates,return=minimal"},
                        json=direct_payload,
                        timeout=30
                    )
                    if resp2.status_code in (200, 201):
                        unmatched_success += 1
            except Exception as e:
                print(f"    Error inserting unmatched: {e}")
        
        print(f"  Inserted {unmatched_success}/{len(unmatched)} unmatched listings to tracking table")
    
    if not matches:
        return 0, 0
    
    # Insert in batches via HTTP API (to avoid extra supabase lib dependency in scraper)
    success = 0
    errors = 0
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    ingest_url = f"{url}/rest/v1/listing_location_match_ingest"
    
    for i in range(0, len(matches), BATCH_SIZE):
        batch = matches[i:i + BATCH_SIZE]
        try:
            resp = requests.post(ingest_url, headers=headers, json=batch, timeout=60)
            if resp.status_code in (200, 201):
                success += len(batch)
            else:
                print(f"  Location match insert error: {resp.status_code} - {resp.text[:300]}")
                errors += len(batch)
        except Exception as e:
            print(f"  Location match insert exception: {e}")
            errors += len(batch)
    
    print(f"  Inserted: {success} location matches ({errors} errors)")
    return success, errors


def match_listing_with_texts(texts: Dict[str, str], groups: Dict, latitude: float = None, longitude: float = None,
                              external_id: int = None, supabase_url: str = None, supabase_key: str = None) -> dict:
    """Match listing to location hierarchy using coordinates (primary) or text (fallback).
    
    Strategy:
    1. If lat/lng available, find nearest L2 by distance -> derive L3/L4/L5
    2. If no coordinates or no match, fall back to text-based matching
    3. If L3 matched but no L2, attempt to auto-create L2 from listing text
    
    Returns dict with locGroup2Id, locGroup3Id, locGroup4Id, locGroup5Id.
    """
    import re
    
    # Try coordinate-based matching first (most accurate)
    if latitude and longitude:
        coord_result = match_by_coordinates(
            latitude, longitude, groups,
            texts=texts, external_id=external_id,
            supabase_url=supabase_url, supabase_key=supabase_key
        )
        if coord_result:
            return coord_result
    
    MIN_SCORE = 0.9
    
    result = {
        'locGroup2Id': None,
        'locGroup3Id': None,
        'locGroup4Id': None,
        'locGroup5Id': None,
        'matchLevel': None,
        'matchScore': None,
        'matchSource': None,
        'matchedText': None
    }
    
    def find_match(level_data, parent_filter=None):
        """Find best match in a level."""
        best = None
        best_score = 0
        source_priority = {'location': 4, 'title': 3, 'details': 2, 'description': 1}
        
        for loc_id, info in level_data.items():
            if parent_filter and info.get('parent_id') != parent_filter:
                continue
            
            search_name = info['normalized']
            no_prefix = info.get('no_prefix', '')
            alt_names = info.get('alt_names', [])
            
            # All possible name variants to check
            all_variants = [search_name, no_prefix] + alt_names
            all_variants = [v for v in all_variants if v]  # Filter out empty strings
            
            for source, text in texts.items():
                if not text:
                    continue
                
                # Quick check - see if any variant matches as a complete word (use regex word boundaries)
                # This prevents false positives like "colonia" matching "colón"
                def has_word_match(variant, text):
                    if not variant:
                        return False
                    # Use word boundaries to ensure we match complete words only
                    pattern = r'\b' + re.escape(variant) + r'\b'
                    return bool(re.search(pattern, text))
                
                if not any(has_word_match(v, text) for v in all_variants):
                    continue
                
                score = 0
                matched_name = info['name']
                
                # Check primary name first (highest score)
                pattern = r'\b' + re.escape(search_name) + r'\b'
                if re.search(pattern, text):
                    score = 1.0
                # Check no_prefix variant (e.g., "cima 1" matching "Colonia La Cima 1")
                elif no_prefix and re.search(r'\b' + re.escape(no_prefix) + r'\b', text):
                    score = 0.95
                    matched_name = f"{info['name']} (via {no_prefix})"
                else:
                    # Check alt_names
                    for alt in alt_names:
                        if alt and re.search(r'\b' + re.escape(alt) + r'\b', text):
                            score = 0.9
                            matched_name = f"{info['name']} ({alt})"
                            break
                
                if score > 0:
                    priority = source_priority.get(source, 0) * 0.001
                    adjusted = score + priority
                    if adjusted > best_score:
                        best_score = adjusted
                        best = (loc_id, score, matched_name, source)
        
        return best
    
    def get_ids_under_dept(level, dept_id):
        if level == 4:
            return {lid for lid, info in groups.get(4, {}).items() if info.get('parent_id') == dept_id}
        elif level == 3:
            l4_ids = get_ids_under_dept(4, dept_id)
            return {lid for lid, info in groups.get(3, {}).items() if info.get('parent_id') in l4_ids}
        elif level == 2:
            l3_ids = get_ids_under_dept(3, dept_id)
            return {lid for lid, info in groups.get(2, {}).items() if info.get('parent_id') in l3_ids}
        return set()
    
    def get_parent_chain_local(loc_id, level):
        chain = {'locGroup2Id': None, 'locGroup3Id': None, 'locGroup4Id': None, 'locGroup5Id': None}
        current_id = loc_id
        current_level = level
        while current_level <= 5:
            chain[f'locGroup{current_level}Id'] = current_id
            if current_level == 5:
                break
            if current_id in groups.get(current_level, {}):
                parent_id = groups[current_level][current_id].get('parent_id')
                if parent_id:
                    current_id = parent_id
                    current_level += 1
                else:
                    break
            else:
                break
        return chain
    
    # STRATEGY: Try L3 (municipality) FIRST globally, as it's more specific.
    # This prevents false matches like "Cuscatlán" department matching when
    # the listing mentions "Antiguo Cuscatlán" (a municipality in La Libertad).
    
    # Step 1: Try L3 globally first (most specific common match)
    l3_match = find_match(groups.get(3, {}))
    
    if l3_match:
        l3_id, l3_score, l3_text, l3_source = l3_match
        if l3_score >= MIN_SCORE:
            # Great! Found a municipality match - derive the full chain from it
            chain = get_parent_chain_local(l3_id, 3)
            result.update(chain)
            result['matchLevel'] = 3
            result['matchScore'] = round(l3_score, 2)
            result['matchSource'] = l3_source
            result['matchedText'] = l3_text[:255] if l3_text else None
            
            # Now try to find L2 (colonia) under this municipality
            l2_match = find_match(groups.get(2, {}), parent_filter=l3_id)
            if l2_match:
                l2_id, l2_score, l2_text, l2_source = l2_match
                if l2_score >= MIN_SCORE:
                    result['locGroup2Id'] = l2_id
                    result['matchLevel'] = 2
                    result['matchScore'] = round(l2_score, 2)
                    result['matchSource'] = l2_source
                    result['matchedText'] = l2_text[:255] if l2_text else None
            
            # If no L2 found but we have coordinates, try auto-creating one
            if result['locGroup2Id'] is None and latitude and longitude:
                auto_l2_id = try_create_l2_from_listing(
                    texts, latitude, longitude, l3_id, groups,
                    external_id=external_id,
                    supabase_url=supabase_url, supabase_key=supabase_key
                )
                if auto_l2_id:
                    result['locGroup2Id'] = auto_l2_id
                    result['matchLevel'] = 2
                    result['matchSource'] = 'text+auto-l2'
                    auto_name = groups.get(2, {}).get(auto_l2_id, {}).get('name', '')
                    result['matchedText'] = f"{auto_name} (auto, {l3_text})"[:255]
            
            return result
    
    # Step 2: No L3 match - try L5 (Department) and search within it
    l5_match = find_match(groups.get(5, {}))
    
    if l5_match:
        l5_id, l5_score, l5_text, l5_source = l5_match
        
        # Disambiguation: verify the department name isn't part of a longer L3 municipality
        # name that appears in the text. E.g., "Cuscatlán" dept should NOT match when
        # text says "Antiguo Cuscatlán" (a municipality in La Libertad).
        dept_name = groups.get(5, {}).get(l5_id, {}).get('normalized', '')
        disambiguated = False
        
        if dept_name:
            for l3_id_check, l3_info in groups.get(3, {}).items():
                l3_name = l3_info['normalized']
                # Check if L3 name contains the department name as a part (but isn't identical)
                if dept_name in l3_name and dept_name != l3_name:
                    # Check if the full L3 name appears in any text field
                    for src, txt in texts.items():
                        if not txt:
                            continue
                        if re.search(r'\b' + re.escape(l3_name) + r'\b', txt):
                            # The longer L3 name matches - use L3 instead of L5
                            chain = get_parent_chain_local(l3_id_check, 3)
                            result.update(chain)
                            result['matchLevel'] = 3
                            result['matchScore'] = round(l5_score, 2)
                            result['matchSource'] = src
                            result['matchedText'] = l3_info['name'][:255]
                            
                            # Try L2 under this L3
                            l2_match = find_match(groups.get(2, {}), parent_filter=l3_id_check)
                            if l2_match:
                                l2_id, l2_score, l2_text, l2_source = l2_match
                                if l2_score >= MIN_SCORE:
                                    result['locGroup2Id'] = l2_id
                                    result['matchLevel'] = 2
                                    result['matchScore'] = round(l2_score, 2)
                                    result['matchSource'] = l2_source
                                    result['matchedText'] = l2_text[:255] if l2_text else None
                            
                            disambiguated = True
                            break
                if disambiguated:
                    break
        
        if disambiguated:
            return result
        
        # Not ambiguous - proceed with L5 match
        result['locGroup5Id'] = l5_id
        result['matchLevel'] = 5
        result['matchScore'] = round(l5_score, 2)
        result['matchSource'] = l5_source
        result['matchedText'] = l5_text[:255] if l5_text else None
        
        # Search lower levels under this department
        best_lower = None
        best_lower_level = 5
        
        for level in [2, 3, 4]:
            valid_ids = get_ids_under_dept(level, l5_id)
            if not valid_ids:
                continue
            filtered = {k: v for k, v in groups.get(level, {}).items() if k in valid_ids}
            match = find_match(filtered)
            if match:
                loc_id, score, text, src = match
                if score >= MIN_SCORE and level < best_lower_level:
                    best_lower = (loc_id, level, score, text, src)
                    best_lower_level = level
        
        if best_lower:
            loc_id, level, score, text, src = best_lower
            chain = get_parent_chain_local(loc_id, level)
            result.update(chain)
            result['matchLevel'] = level
            result['matchScore'] = round(score, 2)
            result['matchSource'] = src
            result['matchedText'] = text[:255] if text else None
        
        return result
    
    # No L5 and no L3 - try L2 directly as last resort
    # This catches cases where only the colonia name is in the listing (e.g., "Ciudad Marsella")
    l2_match = find_match(groups.get(2, {}))
    if l2_match:
        l2_id, l2_score, l2_text, l2_source = l2_match
        if l2_score >= MIN_SCORE:
            # Get parent chain to fill in L3/L4/L5
            chain = get_parent_chain_local(l2_id, 2)
            result.update(chain)
            result['matchLevel'] = 2
            result['matchScore'] = round(l2_score, 2)
            result['matchSource'] = l2_source
            result['matchedText'] = l2_text[:255] if l2_text else None
            return result
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Match listings to location hierarchy")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--full', action='store_true', help='Process all listings')
    group.add_argument('--new', action='store_true', help='Process only unmatched listings')
    parser.add_argument('--dry-run', action='store_true', help='Preview without inserting')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of listings to process (0=all)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("Location Matching for Scraped Data")
    print("=" * 60)
    
    # Connect to Supabase
    print("\n🔌 Connecting to Supabase...")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("   ✓ Connected")
    
    # Load location groups
    print("\n📂 Loading location groups...")
    groups = load_location_groups(supabase)
    
    # Process listings
    mode = 'full' if args.full else 'new'
    process_listings(supabase, groups, mode, dry_run=args.dry_run, limit=args.limit)
    
    # Refresh materialized view (needed for updated location joins)
    if not args.dry_run:
        print("\n=== Refreshing Materialized View ===")
        try:
            refresh_url = f"{SUPABASE_URL}/rest/v1/rpc/refresh_mv_sd_depto_stats"
            refresh_resp = requests.post(
                refresh_url,
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json"
                },
                json={},
                timeout=60
            )
            if refresh_resp.status_code in [200, 204]:
                print("  ✓ Materialized view refreshed successfully!")
            else:
                print(f"  ⚠️ Warning: Could not refresh view. Status: {refresh_resp.status_code}")
        except Exception as e:
            print(f"  ⚠️ Warning: Could not refresh view: {e}")


if __name__ == "__main__":
    main()
