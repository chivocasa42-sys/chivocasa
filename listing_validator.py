"""
Listing Validator Module
========================
Validates listing status by checking if listings still exist at the source.
Detects deleted, sold, rented, or unavailable listings.

Usage:
    from listing_validator import validate_listing, validate_listings_batch
    
    result = validate_listing("https://encuentra24.com/...", "Encuentra24")
    # {'status': 'deleted', 'reason': 'Anuncio borrado detected', 'checked_at': '...'}
"""

import requests
import time
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from enum import Enum
from bs4 import BeautifulSoup

# ============== STATUS ENUM ==============

class ListingStatus(Enum):
    """Possible listing statuses."""
    ACTIVE = "active"          # Listing exists and is available
    DELETED = "deleted"        # Explicitly marked as deleted/removed
    SOLD = "sold"              # Property sold (if detectable)
    RENTED = "rented"          # Property rented (if detectable)
    NOT_FOUND = "not_found"    # 404 or page not accessible
    UNKNOWN = "unknown"        # Could not determine status
    ERROR = "error"            # Transient error, retry later


# ============== SUPABASE CONFIG ==============
SUPABASE_URL = "https://zvamupbxzuxdgvzgbssn.supabase.co"
SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp2YW11cGJ4enV4ZGd2emdic3NuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTA5MDMwNSwiZXhwIjoyMDg0NjY2MzA1fQ.VfONseJg19pMEymrc6FbdEQJUWxTzJdNlVTboAaRgEs"
TABLE_NAME = "scrappeddata_ingest"


# ============== DETECTION PATTERNS ==============

# Encuentra24 - Patterns indicating deleted listing
ENCUENTRA24_DELETED_PATTERNS = [
    r"anuncio\s+borrado",
    r"eliminado\s+por\s+el\s+anunciante",
    r"este\s+anuncio\s+ya\s+no\s+est[áa]\s+disponible",
    r"anuncio\s+no\s+encontrado",
    r"lo\s+sentimos\s+mucho.*eliminado",
]

# Encuentra24 - Patterns indicating sold/rented
ENCUENTRA24_SOLD_PATTERNS = [
    r"vendido",
    r"propiedad\s+vendida",
]

ENCUENTRA24_RENTED_PATTERNS = [
    r"alquilado",
    r"rentado",
    r"propiedad\s+alquilada",
]

# MiCasaSV patterns
MICASASV_DELETED_PATTERNS = [
    r"listing\s+not\s+found",
    r"no\s+encontrado",
    r"page\s+not\s+found",
]

# VivoLatam patterns
VIVOLATAM_DELETED_PATTERNS = [
    r"property\s+not\s+found",
    r"no\s+encontrado",
    r"página\s+no\s+encontrada",
]


# ============== REQUEST CONFIGURATION ==============

REQUEST_TIMEOUT = 30
MAX_RETRIES = 2
RETRY_DELAY = 2  # seconds

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}


# ============== VALIDATOR FUNCTIONS ==============

def _fetch_page(url: str, retries: int = MAX_RETRIES) -> Tuple[Optional[str], int, Optional[str]]:
    """
    Fetch a page with retry logic.
    
    Returns:
        Tuple of (html_content, status_code, error_message)
    """
    for attempt in range(retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
            return resp.text, resp.status_code, None
        except requests.exceptions.Timeout:
            if attempt < retries:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            return None, 0, "Timeout"
        except requests.exceptions.ConnectionError:
            if attempt < retries:
                time.sleep(RETRY_DELAY * (attempt + 1))
                continue
            return None, 0, "Connection error"
        except Exception as e:
            return None, 0, str(e)
    
    return None, 0, "Max retries exceeded"


def _check_patterns(text: str, patterns: List[str]) -> bool:
    """Check if any pattern matches the text."""
    text_lower = text.lower()
    for pattern in patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    return False


def validate_encuentra24(url: str) -> Dict:
    """
    Validate an Encuentra24 listing.
    
    Detects:
    - "Anuncio borrado" modal
    - 404 errors
    - Sold/Rented status
    """
    html, status_code, error = _fetch_page(url)
    
    if error:
        return {
            "status": ListingStatus.ERROR.value,
            "reason": error,
            "checked_at": datetime.now().isoformat()
        }
    
    if status_code == 404:
        return {
            "status": ListingStatus.NOT_FOUND.value,
            "reason": "HTTP 404",
            "checked_at": datetime.now().isoformat()
        }
    
    if status_code != 200:
        return {
            "status": ListingStatus.ERROR.value,
            "reason": f"HTTP {status_code}",
            "checked_at": datetime.now().isoformat()
        }
    
    # Check for deleted patterns
    if _check_patterns(html, ENCUENTRA24_DELETED_PATTERNS):
        return {
            "status": ListingStatus.DELETED.value,
            "reason": "Anuncio borrado detected",
            "checked_at": datetime.now().isoformat()
        }
    
    # Check for sold patterns
    if _check_patterns(html, ENCUENTRA24_SOLD_PATTERNS):
        return {
            "status": ListingStatus.SOLD.value,
            "reason": "Property marked as sold",
            "checked_at": datetime.now().isoformat()
        }
    
    # Check for rented patterns
    if _check_patterns(html, ENCUENTRA24_RENTED_PATTERNS):
        return {
            "status": ListingStatus.RENTED.value,
            "reason": "Property marked as rented",
            "checked_at": datetime.now().isoformat()
        }
    
    # Check if page has listing content (title, price elements)
    soup = BeautifulSoup(html, 'html.parser')
    title_el = soup.select_one(".d3-property-title, h1")
    if not title_el or not title_el.get_text(strip=True):
        return {
            "status": ListingStatus.UNKNOWN.value,
            "reason": "No listing content found",
            "checked_at": datetime.now().isoformat()
        }
    
    return {
        "status": ListingStatus.ACTIVE.value,
        "reason": "Listing active",
        "checked_at": datetime.now().isoformat()
    }


def validate_micasasv(url: str) -> Dict:
    """Validate a MiCasaSV listing."""
    html, status_code, error = _fetch_page(url)
    
    if error:
        return {
            "status": ListingStatus.ERROR.value,
            "reason": error,
            "checked_at": datetime.now().isoformat()
        }
    
    if status_code == 404:
        return {
            "status": ListingStatus.NOT_FOUND.value,
            "reason": "HTTP 404",
            "checked_at": datetime.now().isoformat()
        }
    
    if status_code != 200:
        return {
            "status": ListingStatus.ERROR.value,
            "reason": f"HTTP {status_code}",
            "checked_at": datetime.now().isoformat()
        }
    
    # Check for deleted patterns
    if _check_patterns(html, MICASASV_DELETED_PATTERNS):
        return {
            "status": ListingStatus.DELETED.value,
            "reason": "Listing not found message detected",
            "checked_at": datetime.now().isoformat()
        }
    
    # Check if redirected to homepage
    if "micasasv.com/listing/" not in url.lower() or len(html) < 5000:
        # Possibly redirected or empty page
        soup = BeautifulSoup(html, 'html.parser')
        title_el = soup.select_one(".listing-title, h1.entry-title")
        if not title_el:
            return {
                "status": ListingStatus.NOT_FOUND.value,
                "reason": "No listing content found",
                "checked_at": datetime.now().isoformat()
            }
    
    return {
        "status": ListingStatus.ACTIVE.value,
        "reason": "Listing active",
        "checked_at": datetime.now().isoformat()
    }


def validate_realtor(url: str) -> Dict:
    """Validate a Realtor.com listing."""
    html, status_code, error = _fetch_page(url)
    
    if error:
        return {
            "status": ListingStatus.ERROR.value,
            "reason": error,
            "checked_at": datetime.now().isoformat()
        }
    
    if status_code == 404:
        return {
            "status": ListingStatus.NOT_FOUND.value,
            "reason": "HTTP 404",
            "checked_at": datetime.now().isoformat()
        }
    
    if status_code != 200:
        return {
            "status": ListingStatus.ERROR.value,
            "reason": f"HTTP {status_code}",
            "checked_at": datetime.now().isoformat()
        }
    
    # Check for __NEXT_DATA__ which contains listing info
    if "__NEXT_DATA__" not in html:
        return {
            "status": ListingStatus.UNKNOWN.value,
            "reason": "No NEXT_DATA found",
            "checked_at": datetime.now().isoformat()
        }
    
    # Check if listing data exists in NEXT_DATA
    soup = BeautifulSoup(html, 'html.parser')
    next_data = soup.select_one("script#__NEXT_DATA__")
    if next_data:
        try:
            import json
            data = json.loads(next_data.string)
            # Check if listing exists in data
            if "pageProps" not in data.get("props", {}):
                return {
                    "status": ListingStatus.NOT_FOUND.value,
                    "reason": "No listing in page data",
                    "checked_at": datetime.now().isoformat()
                }
        except:
            pass
    
    return {
        "status": ListingStatus.ACTIVE.value,
        "reason": "Listing active",
        "checked_at": datetime.now().isoformat()
    }


def validate_vivolatam(url: str) -> Dict:
    """Validate a VivoLatam listing."""
    html, status_code, error = _fetch_page(url)
    
    if error:
        return {
            "status": ListingStatus.ERROR.value,
            "reason": error,
            "checked_at": datetime.now().isoformat()
        }
    
    if status_code == 404:
        return {
            "status": ListingStatus.NOT_FOUND.value,
            "reason": "HTTP 404",
            "checked_at": datetime.now().isoformat()
        }
    
    if status_code != 200:
        return {
            "status": ListingStatus.ERROR.value,
            "reason": f"HTTP {status_code}",
            "checked_at": datetime.now().isoformat()
        }
    
    # Check for deleted patterns
    if _check_patterns(html, VIVOLATAM_DELETED_PATTERNS):
        return {
            "status": ListingStatus.DELETED.value,
            "reason": "Property not found message detected",
            "checked_at": datetime.now().isoformat()
        }
    
    # Check if page has property content
    soup = BeautifulSoup(html, 'html.parser')
    
    # VivoLatam uses specific property data structure
    price_el = soup.select_one("[class*='price'], .property-price")
    title_el = soup.select_one("h1, [class*='title']")
    
    if not price_el and not title_el:
        return {
            "status": ListingStatus.NOT_FOUND.value,
            "reason": "No property content found",
            "checked_at": datetime.now().isoformat()
        }
    
    return {
        "status": ListingStatus.ACTIVE.value,
        "reason": "Listing active",
        "checked_at": datetime.now().isoformat()
    }


# ============== MAIN VALIDATOR DISPATCHER ==============

def validate_listing(url: str, source: str) -> Dict:
    """
    Validate a listing's status based on its source.
    
    Args:
        url: The listing URL
        source: The source name (Encuentra24, MiCasaSV, Realtor, VivoLatam)
        
    Returns:
        Dict with status, reason, and checked_at
    """
    source_lower = source.lower()
    
    if "encuentra24" in source_lower:
        return validate_encuentra24(url)
    elif "micasasv" in source_lower or "micasa" in source_lower:
        return validate_micasasv(url)
    elif "realtor" in source_lower:
        return validate_realtor(url)
    elif "vivolatam" in source_lower or "vivo" in source_lower:
        return validate_vivolatam(url)
    else:
        return {
            "status": ListingStatus.UNKNOWN.value,
            "reason": f"Unknown source: {source}",
            "checked_at": datetime.now().isoformat()
        }


def validate_listings_batch(
    listings: List[Dict],
    rate_limit: float = 1.0,
    on_progress: callable = None
) -> List[Dict]:
    """
    Validate multiple listings with rate limiting.
    
    Args:
        listings: List of dicts with 'url' and 'source' keys
        rate_limit: Seconds between requests (default 1.0)
        on_progress: Optional callback(index, total, result)
        
    Returns:
        List of validation results with original listing data
    """
    results = []
    total = len(listings)
    
    for i, listing in enumerate(listings):
        url = listing.get("url")
        source = listing.get("source")
        external_id = listing.get("external_id")
        
        if not url or not source:
            results.append({
                "external_id": external_id,
                "url": url,
                "source": source,
                "status": ListingStatus.UNKNOWN.value,
                "reason": "Missing URL or source",
                "checked_at": datetime.now().isoformat()
            })
            continue
        
        # Validate
        result = validate_listing(url, source)
        result["external_id"] = external_id
        result["url"] = url
        result["source"] = source
        results.append(result)
        
        # Progress callback
        if on_progress:
            on_progress(i + 1, total, result)
        
        # Rate limiting (skip on last item)
        if i < total - 1 and rate_limit > 0:
            time.sleep(rate_limit)
    
    return results


# ============== DATABASE UPDATE FUNCTIONS ==============

def update_listing_status(external_id: int, active: bool, reason: str = None) -> bool:
    """
    Update a listing's active status in the database.
    
    Args:
        external_id: The listing's external_id
        active: Whether the listing is active
        reason: Optional reason for the status change
        
    Returns:
        True if update successful
    """
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    data = {"active": active}
    
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?external_id=eq.{external_id}"
    
    try:
        resp = requests.patch(url, headers=headers, json=data, timeout=30)
        if resp.status_code in (200, 204):
            print(f"  Updated {external_id}: active={active} ({reason})")
            return True
        else:
            print(f"  Update error for {external_id}: {resp.status_code} - {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  Update exception for {external_id}: {e}")
        return False


def get_active_listings(source: str = None, limit: int = None) -> List[Dict]:
    """
    Get active listings from the database.
    
    Args:
        source: Optional filter by source
        limit: Optional limit on results
        
    Returns:
        List of listings with external_id, url, source
    """
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?select=external_id,url,source&active=eq.true"
    
    if source:
        url += f"&source=eq.{source}"
    
    if limit:
        url += f"&limit={limit}"
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"Error fetching listings: {resp.status_code}")
            return []
    except Exception as e:
        print(f"Exception fetching listings: {e}")
        return []


# ============== QUICK TEST ==============

if __name__ == "__main__":
    print("Listing Validator Test")
    print("=" * 60)
    
    # Test with a sample URL (this may or may not exist)
    test_urls = [
        ("https://www.encuentra24.com/el-salvador-es/bienes-raices-alquiler-casas/123456", "Encuentra24"),
    ]
    
    for url, source in test_urls:
        print(f"\nTesting: {url[:60]}...")
        result = validate_listing(url, source)
        print(f"  Status: {result['status']}")
        print(f"  Reason: {result['reason']}")
