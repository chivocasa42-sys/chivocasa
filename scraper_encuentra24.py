"""
Multi-Source Housing Scraper - OPTIMIZED
Uses concurrent requests to scrape listings from Encuentra24, MiCasaSV, Nexo, Realtor.com, Realty El Salvador, Casas Ahorita, Camara Bienes Raices, Vivo Latam, and Propi Latam.
Inserts results directly into Supabase database (scrappeddata_ingest table).

Usage:
  python scraper_encuentra24.py                             # Default: scrape ALL sources
  python scraper_encuentra24.py --Encuentra24 --limit 100   # Scrape 100 from Encuentra24 only
  python scraper_encuentra24.py --MiCasaSV --limit 10       # Scrape 10 from MiCasaSV only
  python scraper_encuentra24.py --Nexo --limit 20           # Scrape 20 from Nexo only
  python scraper_encuentra24.py --Realtor --limit 50        # Scrape 50 from Realtor.com only
  python scraper_encuentra24.py --RealtyElSalvador --limit 20  # Scrape 20 from Realty El Salvador only
  python scraper_encuentra24.py --CasasAhorita --limit 20  # Scrape 20 from Casas Ahorita only
  python scraper_encuentra24.py --CamaraBienesRaices --limit 20  # Scrape 20 from Camara Bienes Raices only
  python scraper_encuentra24.py --VivoLatam --limit 20      # Scrape 20 from Vivo Latam only
  python scraper_encuentra24.py --PropiLatam --limit 20     # Scrape 20 from Propi Latam only
  python scraper_encuentra24.py --Encuentra24 --MiCasaSV    # Scrape from specific sources
  python scraper_encuentra24.py --update-actives            # Validate active/inactive status only
"""
import argparse
import requests
from bs4 import BeautifulSoup
import json
import re
import time
import os
import hashlib
import random
import traceback
import unicodedata
from html import unescape
from urllib.parse import unquote, urlparse, urljoin
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import localization plugin for generating searchable tags
from localization_plugin import build_destination_queries

# Import area normalizer for standardizing area units to m²
from area_normalizer import normalize_listing_specs

# Import location matcher lazily so source-specific smoke tests can run
# without importing the full Supabase client stack up front.
MATCH_SCRAPED_LISTINGS = None


def get_match_scraped_listings():
    """Load the location matcher only when a full ingest run needs it."""
    global MATCH_SCRAPED_LISTINGS
    if MATCH_SCRAPED_LISTINGS is None:
        from match_locations import match_scraped_listings as imported_match_scraped_listings

        MATCH_SCRAPED_LISTINGS = imported_match_scraped_listings
    return MATCH_SCRAPED_LISTINGS

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
    
    # Normalize published_date for PostgreSQL while preserving ISO-like values.
    parsed_date = normalize_published_date_for_db(listing.get("published_date"))
    
    # Prepare data for insertion (match DB schema)
    # JSONB fields are sent as dicts/lists - requests.post with json= handles serialization
    
    # Build location JSONB with coordinates only (L2-L5 resolved by match_locations)
    location_data = {
        "latitude": listing.get("latitude"),
        "longitude": listing.get("longitude")
    }
    
    # Generate tags using localization plugin (use pre-computed if available)
    tags = listing.get("tags")
    if not tags:
        tags = generate_location_tags(listing)
    
    # Filter out redundant tags (all listings are in El Salvador, so it's not useful)
    # Also filter out "No identificado" which provides no value for search
    excluded_tags = ["el salvador", "no identificado"]
    if tags:
        tags = [t for t in tags if t.lower() not in excluded_tags]
    
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


def normalize_published_date_for_db(pub_date):
    """Normalize scraped published_date values to YYYY-MM-DD when possible."""
    if pub_date is None:
        return None

    pub_date_str = str(pub_date).strip()
    if not pub_date_str:
        return None

    iso_match = re.match(r"^(\d{4}-\d{2}-\d{2})", pub_date_str)
    if iso_match:
        return iso_match.group(1)

    normalized_iso = pub_date_str.replace("Z", "+00:00").replace(" ", "T", 1)
    try:
        return datetime.fromisoformat(normalized_iso).date().isoformat()
    except ValueError:
        pass

    for fmt in ("%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(pub_date_str, fmt).date().isoformat()
        except ValueError:
            continue

    return None


def has_nonempty_mapping(value):
    """Return True when a mapping contains at least one meaningful value."""
    return isinstance(value, dict) and any(item not in ("", None, [], {}) for item in value.values())


def has_valid_coordinates(latitude, longitude):
    """Return True for plausible, non-zero coordinates."""
    try:
        lat = float(latitude)
        lng = float(longitude)
    except (TypeError, ValueError):
        return False

    if abs(lat) < 0.000001 and abs(lng) < 0.000001:
        return False

    return -90 <= lat <= 90 and -180 <= lng <= 180


def listing_signal_score(listing):
    """Estimate how complete a scraped listing is using core user-visible fields."""
    score = 0

    price_value = parse_price(listing.get("price"))
    if price_value and price_value > 0:
        score += 1

    if normalize_source_text(listing.get("location")):
        score += 1

    if has_nonempty_mapping(listing.get("specs")):
        score += 1

    if has_nonempty_mapping(listing.get("details")):
        score += 1

    if len(normalize_source_text(listing.get("description"))) >= 40:
        score += 1

    if has_valid_coordinates(listing.get("latitude"), listing.get("longitude")):
        score += 1

    return score


def fetch_existing_records_map(external_ids):
    """Fetch existing listings from Supabase so partial scrapes do not wipe good data."""
    ids = []
    for external_id in external_ids:
        try:
            ids.append(int(external_id))
        except (TypeError, ValueError):
            continue

    ids = list(dict.fromkeys(ids))
    if not ids:
        return {}

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    params = {
        "select": "external_id,title,price,location,specs,details,description,images,tags,published_date",
        "external_id": f"in.({','.join(str(external_id) for external_id in ids)})",
    }
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code != 200:
            print(f"  Warning: could not fetch existing listings for merge ({resp.status_code})")
            return {}

        rows = resp.json()
        return {
            int(row["external_id"]): row
            for row in rows
            if row.get("external_id") is not None
        }
    except Exception as e:
        print(f"  Warning: failed to fetch existing listings for merge: {e}")
        return {}


def merge_listing_with_existing(listing, existing):
    """
    Preserve prior good data when a new scrape comes back obviously incomplete.

    This keeps transient parser regressions or anti-bot challenge pages from
    overwriting rich rows with empty dicts, blank descriptions, or null prices.
    """
    if not existing:
        return listing

    merged = dict(listing)
    incoming_score = listing_signal_score(merged)

    existing_details = existing.get("details") if isinstance(existing.get("details"), dict) else {}
    existing_specs = existing.get("specs") if isinstance(existing.get("specs"), dict) else {}
    existing_location = existing.get("location") if isinstance(existing.get("location"), dict) else {}

    if not normalize_source_text(merged.get("title")) and existing.get("title"):
        merged["title"] = existing["title"]

    if not normalize_source_text(merged.get("description")) and existing.get("description"):
        merged["description"] = existing["description"]

    incoming_specs = merged.get("specs") if isinstance(merged.get("specs"), dict) else {}
    if existing_specs:
        merged_specs = dict(existing_specs)
        for key, value in incoming_specs.items():
            if value not in ("", None, [], {}):
                merged_specs[key] = value
        merged["specs"] = merged_specs

    incoming_details = merged.get("details") if isinstance(merged.get("details"), dict) else {}
    if existing_details:
        merged_details = dict(existing_details)
        for key, value in incoming_details.items():
            if value not in ("", None, [], {}):
                merged_details[key] = value
        merged["details"] = merged_details

    if not normalize_source_text(merged.get("location")):
        for key, value in existing_details.items():
            normalized_key = normalize_source_text(key).lower()
            if any(marker in normalized_key for marker in ("ubicacion", "localizacion", "city", "municipio")):
                if normalize_source_text(value):
                    merged["location"] = value
                    break

    if not merged.get("images") and existing.get("images"):
        merged["images"] = existing["images"]

    if not merged.get("tags") and existing.get("tags"):
        merged["tags"] = existing["tags"]

    if not normalize_source_text(merged.get("published_date")) and existing.get("published_date"):
        merged["published_date"] = existing["published_date"]

    if not has_valid_coordinates(merged.get("latitude"), merged.get("longitude")) and has_valid_coordinates(
        existing_location.get("latitude"),
        existing_location.get("longitude"),
    ):
        merged["latitude"] = existing_location.get("latitude")
        merged["longitude"] = existing_location.get("longitude")

    if parse_price(merged.get("price")) is None and existing.get("price") is not None and incoming_score <= 1:
        merged["price"] = existing["price"]

    return merged


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
        existing_records = fetch_existing_records_map([listing.get("external_id") for listing in batch])
        
        for listing in batch:
            # Parse external_id to bigint
            external_id_str = listing.get("external_id", "")
            try:
                external_id = int(external_id_str)
            except (ValueError, TypeError):
                errors += 1
                continue

            listing = merge_listing_with_existing(listing, existing_records.get(external_id))
            
            # Normalize published_date for PostgreSQL while preserving ISO-like values.
            parsed_date = normalize_published_date_for_db(listing.get("published_date"))
            
            # Build location JSONB with coordinates only (L2-L5 resolved by match_locations)
            location_data = {
                "latitude": listing.get("latitude"),
                "longitude": listing.get("longitude")
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


# ============== UPDATE MODE FUNCTIONS ==============

def get_active_listings_from_db(source=None, limit=None):
    """
    Fetch all active listings from the database.
    Uses pagination to bypass Supabase's default 1000-row limit.
    Includes retry logic and continues on error.
    
    Args:
        source: Optional filter by source (e.g., "Encuentra24", "MiCasaSV")
        limit: Optional limit on number of results
        
    Returns:
        List of dicts with {external_id, url, source, listing_type}
    """
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Prefer": "count=exact"  # Get total count in response headers
    }
    
    all_listings = []
    page_size = 1000  # Fetch 1000 at a time
    offset = 0
    max_retries = 3
    consecutive_failures = 0
    max_consecutive_failures = 5  # Stop if 5 batches in a row fail
    
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?select=external_id,url,source,listing_type&active=eq.true&order=external_id&offset={offset}&limit={page_size}"
        
        if source:
            url += f"&source=eq.{source}"
        
        batch = None
        for attempt in range(max_retries):
            try:
                resp = requests.get(url, headers=headers, timeout=60)
                # 200 = OK, 206 = Partial Content (used for paginated results with count header)
                if resp.status_code in (200, 206):
                    batch = resp.json()
                    consecutive_failures = 0  # Reset on success
                    break
                else:
                    print(f"  Attempt {attempt + 1}/{max_retries} failed: {resp.status_code} - {resp.text[:100]}")
                    if attempt < max_retries - 1:
                        time.sleep(2)  # Wait before retry
            except Exception as e:
                print(f"  Attempt {attempt + 1}/{max_retries} exception: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        
        if batch is None:
            # All retries failed for this batch
            consecutive_failures += 1
            print(f"  [WARN] Failed to fetch batch at offset {offset} after {max_retries} attempts, skipping...")
            
            if consecutive_failures >= max_consecutive_failures:
                print(f"  [ERROR] Too many consecutive failures ({consecutive_failures}), stopping pagination")
                break
            
            # Continue to next batch
            offset += page_size
            continue
        
        if not batch:
            # Empty batch = no more records
            break
        
        all_listings.extend(batch)
        print(f"  Fetched {len(all_listings)} active listings so far...")
        
        # Check if we've hit the user-specified limit
        if limit and len(all_listings) >= limit:
            all_listings = all_listings[:limit]
            break
        
        # If we got fewer than page_size, we're done
        if len(batch) < page_size:
            break
        
        offset += page_size
    
    print(f"  Total: {len(all_listings)} active listings fetched from database")
    return all_listings


def update_listings_batch(listings, batch_size=50):
    """
    Update multiple listings in Supabase by external_id.
    Uses PATCH requests to update existing records.
    
    Args:
        listings: List of listing dicts to update
        batch_size: Number of records to update per batch
        
    Returns:
        Tuple of (success_count, error_count)
    """
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
    
    for listing in listings:
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
        
        # Build location JSONB with coordinates only (L2-L5 resolved by match_locations)
        location_data = {
            "latitude": listing.get("latitude"),
            "longitude": listing.get("longitude")
        }
        
        # Get tags (pre-computed or generate now)
        tags = listing.get("tags")
        if not tags:
            tags = generate_location_tags(listing)
        
        # Build update data (exclude external_id as it's the filter key)
        update_data = {
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
        
        # PATCH request to update by external_id
        url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?external_id=eq.{external_id}"
        try:
            resp = requests.patch(url, headers=headers, json=update_data, timeout=30)
            if resp.status_code in (200, 204):
                success += 1
            else:
                print(f"  Update error for {external_id}: {resp.status_code} - {resp.text[:200]}")
                errors += 1
        except Exception as e:
            print(f"  Update exception for {external_id}: {e}")
            errors += 1
        
        # Progress update every 50 listings
        if (success + errors) % 50 == 0:
            print(f"  Updated {success + errors}/{len(listings)} ({success} success, {errors} errors)")
    
    return success, errors


def run_update_mode(sources=None, limit=None, skip_validation=False):
    """
    Update mode: re-scrape existing active listings from DB and update them.
    Uses the same post-run validation/deactivation flow as regular mode.
    
    Args:
        sources: List of sources to update (None = all sources)
        limit: Optional limit per source
        skip_validation: If True, skip the validation phase
    """
    print("\n" + "="*60)
    print("UPDATE MODE: Re-scraping and updating existing listings")
    print("="*60)
    run_start_time = datetime.now().isoformat()
    print(f"Update run started at: {run_start_time}")
    
    # Determine which sources to update
    all_sources = [
        "Encuentra24",
        "MiCasaSV",
        NEXO_SOURCE,
        "Realtor",
        REALTYELSALVADOR_SOURCE,
        CASASAHORITA_SOURCE,
        CAMARABIENESRAICES_SOURCE,
        "PropiLatam",
        "VivoLatam",
    ]
    if sources:
        sources_to_update = [s for s in sources if s in all_sources]
    else:
        sources_to_update = all_sources
    
    print(f"Sources to update: {', '.join(sources_to_update)}")
    
    total_updated = 0
    total_errors = 0
    total_deactivated = 0
    source_failures = []
    successful_sources = []
    run_scraped_external_ids = set()
    
    for source in sources_to_update:
        print(f"\n--- Processing {source} ---")
        try:
            # Fetch active listings for this source
            active_listings = get_active_listings_from_db(source=source, limit=limit)
            
            if not active_listings:
                print(f"  No active listings found for {source}")
                continue
            
            print(f"  Found {len(active_listings)} listings to re-scrape")
            
            # Build URL -> external_id mapping to track which listings fail to scrape
            url_to_id = {l['url']: l['external_id'] for l in active_listings}
            original_urls = set(url_to_id.keys())
            
            # Group by listing_type
            sale_urls = [(l['url'], l['external_id']) for l in active_listings if l.get('listing_type') == 'sale']
            rent_urls = [(l['url'], l['external_id']) for l in active_listings if l.get('listing_type') == 'rent']
            
            scraped_listings = []
            
            # Re-scrape based on source
            if source == "Encuentra24":
                if sale_urls:
                    print(f"  Re-scraping {len(sale_urls)} sale listings...")
                    scraped, _ = scrape_listings_concurrent([u[0] for u in sale_urls], "sale", max_workers=10)
                    scraped_listings.extend(scraped)
                if rent_urls:
                    print(f"  Re-scraping {len(rent_urls)} rent listings...")
                    scraped, _ = scrape_listings_concurrent([u[0] for u in rent_urls], "rent", max_workers=10)
                    scraped_listings.extend(scraped)
                    
            elif source == "MiCasaSV":
                if sale_urls:
                    print(f"  Re-scraping {len(sale_urls)} sale listings...")
                    scraped, _ = scrape_micasasv_listings_concurrent([u[0] for u in sale_urls], "sale", max_workers=5)
                    scraped_listings.extend(scraped)
                if rent_urls:
                    print(f"  Re-scraping {len(rent_urls)} rent listings...")
                    scraped, _ = scrape_micasasv_listings_concurrent([u[0] for u in rent_urls], "rent", max_workers=5)
                    scraped_listings.extend(scraped)

            elif source == NEXO_SOURCE:
                all_urls = [u[0] for u in sale_urls + rent_urls]
                all_urls = list(dict.fromkeys(all_urls))
                if all_urls:
                    print(f"  Re-scraping {len(all_urls)} listings...")
                    scraped, _ = scrape_nexo_listings_concurrent(all_urls, "auto", max_workers=4)
                    scraped_listings.extend(scraped)
                    
            elif source == "Realtor":
                # Realtor uses page-based scraping - re-fetch all from paginated pages
                print(f"  Re-fetching Realtor listings from pages (page-based scraping)...")
                
                # Fetch sale listings
                sale_listings = get_realtor_all_listings(REALTOR_SALE_URL, max_listings=limit, listing_type="sale")
                if sale_listings:
                    print(f"  Fetched {len(sale_listings)} sale listings")
                    scraped_listings.extend(sale_listings)
                
                # Fetch rent listings
                rent_listings = get_realtor_all_listings(REALTOR_RENT_URL, max_listings=limit, listing_type="rent")
                if rent_listings:
                    print(f"  Fetched {len(rent_listings)} rent listings")
                    scraped_listings.extend(rent_listings)
                
                # Disabled: update mode now uses the same stale-listing validation pass as regular mode
                # after all upserts complete (see validate_and_deactivate_listings below).
                if False and len(scraped_listings) >= len(active_listings) * 0.5:
                    scraped_external_ids = {str(l.get('external_id')) for l in scraped_listings if l.get('external_id')}
                    db_external_ids = {str(l['external_id']) for l in active_listings}
                    missing_ids = db_external_ids - scraped_external_ids
                    
                    if missing_ids:
                        print(f"  [WARN] {len(missing_ids)} Realtor listings no longer on site, deactivating...")
                        deactivated = deactivate_listings([int(eid) for eid in missing_ids])
                        total_deactivated += deactivated
                        print(f"  Deactivated {deactivated} Realtor listings")
                elif False:
                    print(f"  [WARN] Scrape returned too few results ({len(scraped_listings)}/{len(active_listings)}), skipping deactivation to prevent data loss")

            elif source == REALTYELSALVADOR_SOURCE:
                print(f"  Re-fetching Realty El Salvador listings from the WP REST API...")
                scraped, _, _ = main_realtyelsalvador(limit=limit, max_days=None)
                scraped_listings.extend(scraped)

            elif source == CASASAHORITA_SOURCE:
                print(f"  Re-fetching Casas Ahorita listings from current search results...")
                scraped, _, _ = main_casasahorita(limit=limit, max_days=None)
                scraped_listings.extend(scraped)

            elif source == CAMARABIENESRAICES_SOURCE:
                property_ids = [l["external_id"] for l in active_listings if l.get("external_id")]
                if property_ids:
                    print(f"  Re-fetching {len(property_ids)} Camara Bienes Raices listings via REST API...")
                    scraped_listings.extend(get_cbr_properties_by_ids(property_ids))

            elif source == "VivoLatam":
                all_urls = [u[0] for u in sale_urls + rent_urls]
                if all_urls:
                    print(f"  Re-scraping {len(all_urls)} listings...")
                    scraped, _ = scrape_vivolatam_listings_concurrent(all_urls, "sale", max_workers=5)
                    scraped_listings.extend(scraped)

            elif source == "PropiLatam":
                all_urls = [u[0] for u in sale_urls + rent_urls]
                all_urls = list(dict.fromkeys(all_urls))  # de-duplicate while preserving order
                if all_urls:
                    print(f"  Re-scraping {len(all_urls)} listings...")
                    scraped, _ = scrape_propilatam_listings_concurrent(all_urls, "auto", max_workers=5)
                    scraped_listings.extend(scraped)
            
            # Determine which listings failed to scrape
            scraped_urls = {l.get('url') for l in scraped_listings if l.get('url')}
            failed_urls = original_urls - scraped_urls
            
            # Disabled: per-source deactivation is handled by the shared validation phase below.
            if False and failed_urls:
                print(f"  [WARN] {len(failed_urls)} listings failed to scrape, verifying if truly inactive...")
                # Verify each failed URL to confirm it's actually 404/sold (not just rate limited)
                confirmed_inactive_ids = []
                for url in failed_urls:
                    is_active, reason = check_listing_still_active(url, source)
                    if not is_active:
                        confirmed_inactive_ids.append(url_to_id[url])
                        print(f"    X Confirmed inactive: {url[:60]}... ({reason})")
                    else:
                        print(f"    ? Skipping (may be transient): {url[:60]}... ({reason})")
                
                if confirmed_inactive_ids:
                    deactivated = deactivate_listings(confirmed_inactive_ids)
                    total_deactivated += deactivated
                    print(f"  Deactivated {deactivated} confirmed inactive listings")
            
            if scraped_listings:
                print(f"  Successfully scraped {len(scraped_listings)} listings")
                run_scraped_external_ids.update(collect_listing_external_ids(scraped_listings))
                print(f"  Inserting/updating database (DB trigger handles upsert)...")
                success, errors = insert_listings_batch(scraped_listings)
                total_updated += success
                total_errors += errors
                successful_sources.append(source)
                print(f"  {source}: {success} upserted, {errors} errors")
            else:
                successful_sources.append(source)
                print(f"  No listings scraped for {source}")
        except Exception as e:
            source_failures.append({"source": source, "error": str(e)})
            total_errors += 1
            log_source_failure("update", source, e)
            continue

    if source_failures:
        print("\n=== Update Source Failures ===")
        for failure in source_failures:
            print(f"  - {failure['source']}: {failure['error']}")

    # Match regular mode deactivation behavior: validate stale listings after upserts
    validated_count = 0
    if not skip_validation and limit is None:
        if successful_sources:
            validated_count, deactivated_count = validate_and_deactivate_listings(
                run_start_time,
                sources=successful_sources,
                exclude_external_ids=run_scraped_external_ids,
            )
            total_deactivated += deactivated_count
        else:
            print("\n=== Skipping validation phase (no update sources completed successfully) ===")
    else:
        skip_reason = "--limit flag" if limit is not None else "--skip-validation flag"
        print(f"\n=== Skipping validation phase ({skip_reason}) ===")
    
    # Refresh materialized view after updates
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
    except Exception as e:
        print(f"  Warning: Error refreshing view: {e}")
    
    print(f"\n=== UPDATE MODE COMPLETE ===")
    print(f"Total updated: {total_updated}")
    if not skip_validation:
        print(f"Validation: {validated_count} checked, {total_deactivated} deactivated")
    print(f"Total deactivated: {total_deactivated}")
    print(f"Total errors: {total_errors}")
    if source_failures:
        print(f"Sources failed but update continued: {len(source_failures)}")
    
    return total_updated, total_deactivated, total_errors


# ============== LISTING VALIDATION FUNCTIONS ==============

def get_stale_active_listings(run_start_time, source=None, page_size=1000):
    """
    Fetch active listings that were NOT updated in the current run.
    These are candidates for validation (might be sold/removed).
    
    Args:
        run_start_time: ISO timestamp of when the scrape run started
        source: Optional source filter (e.g., "Encuentra24", "MiCasaSV")
        page_size: Number of records per page when paginating Supabase results
    
    Returns:
        List of dicts with {external_id, url, source}
    """
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Query all pages: active=true AND last_updated < run_start_time
    # Supabase may cap single responses (commonly at ~1000 rows), so paginate.
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
    all_listings = []
    offset = 0
    
    while True:
        params = {
            "select": "external_id,url,source,listing_type",
            "active": "eq.true",
            "last_updated": f"lt.{run_start_time}",
            "order": "external_id",
            "limit": page_size,
            "offset": offset
        }
        
        if source:
            params["source"] = f"eq.{source}"
        
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=60)
            if resp.status_code != 200:
                print(f"  Error fetching stale listings (offset {offset}): {resp.status_code} - {resp.text[:200]}")
                break
            
            batch = resp.json()
            if not batch:
                break
            
            all_listings.extend(batch)
            print(f"  Fetched {len(all_listings)} stale active listings so far...")
            
            # Last page reached
            if len(batch) < page_size:
                break
            
            offset += page_size
        except Exception as e:
            print(f"  Exception fetching stale listings at offset {offset}: {e}")
            break
    
    return all_listings


def collect_listing_external_ids(listings):
    """Return normalized external_id strings for listings touched in the current run."""
    external_ids = set()
    for listing in listings or []:
        external_id = listing.get("external_id")
        if external_id in ("", None):
            continue
        external_ids.add(str(external_id))
    return external_ids


def check_listing_still_active(url, source):
    """
    Check if a listing URL is still active (not 404 or sold).
    
    Args:
        url: Listing URL to check
        source: Source name for source-specific detection
    
    Returns:
        Tuple of (is_active: bool, reason: str)
    """
    # Keywords that indicate a listing is no longer available
    INACTIVE_KEYWORDS = [
        'vendido', 'vendida', 'sold', 'no disponible', 'not available',
        'expirado', 'expired', 'eliminado', 'deleted', 'removed',
        'listing not found', 'no existe', 'does not exist',
        'página no encontrada', 'page not found', '404',
        'desactivado'  # Added for Encuentra24
    ]
    
    # Exact phrases that definitely indicate inactive (Encuentra24 specific)
    INACTIVE_PHRASES = [
        'este anuncio esta desactivado o expirado',
        'este anuncio está desactivado o expirado',
        'anuncio desactivado',
        'anuncio expirado',
        'anuncio borrado',
        'eliminado por el anunciante',
        'ya no está disponible',
        'ya no esta disponible',
    ]
    
    REALTOR_INACTIVE_PHRASES = [
        'listing not exist',
        'property was deleted, sold or offlined by agent',
        'not available',
    ]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    try:
        if source == "PropiLatam":
            return check_propilatam_listing_still_active(url, headers)
        if source == REALTYELSALVADOR_SOURCE:
            return get_realtyelsalvador_listing_status(url)

        # Use GET to check the full page (some sites don't support HEAD properly)
        resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)

        if source == NEXO_SOURCE:
            raw_html = resp.text or ""
            soup = BeautifulSoup(raw_html, "html.parser")

            if resp.status_code in (404, 410):
                return False, f"HTTP {resp.status_code}"

            if is_nexo_error_page(raw_html, soup=soup):
                return False, "ColdFusion error page"

            title_el = soup.select_one("article.titulo [itemprop='name']") or soup.select_one("article.titulo h1")
            has_title = bool(normalize_nexo_text(title_el.get_text(" ", strip=True) if title_el else ""))
            has_characteristics = bool(soup.select_one(".caracteristicas"))

            if not has_title and not has_characteristics:
                return False, "Missing title and characteristics"

            if resp.status_code == 403:
                return True, "403 Forbidden (assumed active - bot blocked)"

            if resp.status_code >= 500:
                return True, f"HTTP {resp.status_code} (assumed active)"

            if resp.status_code >= 400:
                return True, f"HTTP {resp.status_code} (assumed active)"

            return True, "Active"

        if source == CASASAHORITA_SOURCE:
            raw_html = resp.text or ""
            soup = BeautifulSoup(raw_html, "html.parser")

            if resp.status_code in (404, 410):
                return False, f"HTTP {resp.status_code}"

            if resp.status_code == 403:
                return True, "403 Forbidden (assumed active - bot blocked)"

            if resp.status_code >= 500:
                return True, f"HTTP {resp.status_code} (assumed active)"

            if casasahorita_is_placeholder_page(raw_html, soup=soup):
                return False, "Placeholder/empty listing page"

            title_el = soup.select_one("div.content.row h1")
            title_text = normalize_source_text(title_el.get_text(" ", strip=True) if title_el else "")
            gallery_images = [
                img for img in soup.select("img[src]")
                if "/img/user_uploads/" in (img.get("src") or "")
                and "/profile_fotos/" not in (img.get("src") or "")
            ]
            if not title_text or (title_text.endswith("-") and not gallery_images):
                return False, "Missing title and gallery"

            return True, "Active"
        
        # Check for 404 or 410 (Gone) - these definitively mean listing removed
        if resp.status_code == 404:
            return False, "404 Not Found"
        
        if resp.status_code == 410:
            return False, "410 Gone"
        
        # 403 = bot blocked/access denied - don't deactivate, listing may still exist
        if resp.status_code == 403:
            return True, "403 Forbidden (assumed active - bot blocked)"
        
        # Other 4xx/5xx errors - assume active to avoid false deactivations
        if resp.status_code >= 400:
            return True, f"HTTP {resp.status_code} (assumed active)"
        
        # Check if redirected to homepage or search page (common for removed listings)
        final_url = resp.url.lower()
        if source == "Encuentra24" and "/bienes-raices-venta-de-propiedades" not in final_url and "/bienes-raices-alquiler" not in final_url:
            # Redirected away from listing detail page
            if "/bienes-raices" in final_url and len(final_url) < 100:
                return False, "Redirected to listing index"
        
        # Check page content for inactive indicators.
        # Important: Encuentra24 embeds a generic Next.js notFound template in script data
        # even on active listings. Scanning raw HTML causes false positives (e.g. "ya no
        # está disponible" appears inside that embedded template). Restrict checks to
        # visible page text and prominent headings.
        raw_html = resp.text
        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "template"]):
            tag.decompose()
        
        page_text = soup.get_text(" ", strip=True).lower()
        title_text = (soup.title.get_text(" ", strip=True).lower() if soup.title else "")
        h1_el = soup.select_one("h1")
        h1_text = h1_el.get_text(" ", strip=True).lower() if h1_el else ""

        if source == "Realtor":
            realtor_deleted_marker = 'property was deleted, sold or offlined by agent'
            realtor_soft_404_markers = ['listing not exist', 'not available']
            if realtor_deleted_marker in page_text:
                return False, f"Realtor unavailable page ('{realtor_deleted_marker}')"
            if all(marker in page_text for marker in realtor_soft_404_markers):
                return False, "Realtor unavailable page ('listing not exist' + 'not available')"

        # Check for exact inactive phrases in visible content
        for phrase in INACTIVE_PHRASES:
            if phrase in page_text:
                return False, f"Page contains '{phrase}'"
        
        # Check for keywords only in prominent page text (title/H1) to avoid matching
        # related listings or embedded metadata.
        for keyword in INACTIVE_KEYWORDS:
            if (title_text and keyword in title_text) or (h1_text and keyword in h1_text):
                return False, f"Page contains '{keyword}'"
        
        # Listing appears active
        return True, "Active"
        
    except requests.exceptions.Timeout:
        return True, "Timeout (assumed active)"  # Don't deactivate on timeout
    except requests.exceptions.ConnectionError:
        return True, "Connection error (assumed active)"
    except Exception as e:
        return True, f"Error: {str(e)[:50]} (assumed active)"


def validate_and_deactivate_listings(run_start_time, sources=None, max_workers=5, exclude_external_ids=None):
    """
    Validate all active listings that weren't updated in the current run.
    Marks listings as inactive if they return 404 or are sold/expired.
    
    Args:
        run_start_time: ISO timestamp of when the scrape run started
        sources: Optional list of sources to validate (None = all sources)
        max_workers: Number of concurrent validation requests
        exclude_external_ids: Optional iterable of external_ids already scraped in this run
    
    Returns:
        Tuple of (validated_count, deactivated_count)
    """
    print("\n" + "="*60)
    print("VALIDATION PHASE: Checking for inactive listings")
    print("="*60)
    
    # Get all stale active listings (those not updated in this run)
    stale_listings = get_stale_active_listings(run_start_time, source=None)
    
    if sources:
        # Filter to only specified sources
        stale_listings = [l for l in stale_listings if l.get('source') in sources]

    excluded_ids = {str(external_id) for external_id in (exclude_external_ids or []) if external_id not in ("", None)}
    if excluded_ids:
        before_exclusion = len(stale_listings)
        stale_listings = [
            listing for listing in stale_listings
            if str(listing.get("external_id")) not in excluded_ids
        ]
        excluded_count = before_exclusion - len(stale_listings)
        if excluded_count:
            print(f"  Excluded {excluded_count} listings already scraped in this run")
    
    if not stale_listings:
        print("  No stale active listings to validate.")
        return 0, 0
    
    print(f"  Found {len(stale_listings)} active listings to validate")
    
    # Group by source for reporting
    by_source = {}
    for l in stale_listings:
        src = l.get('source', 'Unknown')
        by_source[src] = by_source.get(src, 0) + 1
    for src, count in by_source.items():
        print(f"    - {src}: {count}")
    
    # Validate listings concurrently
    to_deactivate = []
    route_updates = []
    validated = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_listing = {
            executor.submit(check_listing_status_for_record, l): l
            for l in stale_listings
        }
        
        for future in as_completed(future_to_listing):
            listing = future_to_listing[future]
            validated += 1
            try:
                status = future.result()
                is_active = status.get("is_active", True)
                reason = status.get("reason", "Active")
                if not is_active:
                    to_deactivate.append({
                        'external_id': listing['external_id'],
                        'reason': reason
                    })
                    print(f"    X INACTIVE: {listing['url'][:60]}... ({reason})")
                elif listing.get("source") == "PropiLatam":
                    resolved_url = status.get("resolved_url")
                    resolved_type = status.get("resolved_listing_type")
                    if resolved_url and resolved_url != listing.get("url"):
                        route_updates.append({
                            "external_id": listing["external_id"],
                            "url": resolved_url,
                            "listing_type": resolved_type
                        })
            except Exception as e:
                print(f"    ? ERROR checking: {listing['url'][:60]}... ({e})")
            
            # Progress update every 50 listings
            if validated % 50 == 0:
                print(
                    f"    Validated {validated}/{len(stale_listings)} "
                    f"({len(to_deactivate)} inactive, {len(route_updates)} route-updates)"
                )
    
    print(f"  Validation complete: {validated} checked, {len(to_deactivate)} to deactivate")
    
    if route_updates:
        print(f"  Applying {len(route_updates)} Propi URL/type updates...")
        route_ok, route_err = update_listing_routes(route_updates)
        print(f"  Applied {route_ok} route updates ({route_err} errors)")
    
    # Deactivate listings in database
    if to_deactivate:
        deactivated = deactivate_listings([d['external_id'] for d in to_deactivate])
        print(f"  Deactivated {deactivated} listings in database")
        return validated, deactivated
    
    return validated, 0


def validate_all_active_listings(sources=None, max_workers=10):
    """
    Validate ALL active listings in the database by checking if their URLs
    are still live. This is a lightweight check (HTTP GET only, no full scrape)
    that runs much faster than run_update_mode.
    
    Args:
        sources: Optional list of source names to filter (e.g., ["Encuentra24"])
        max_workers: Number of concurrent validation requests
    
    Returns:
        Tuple of (validated_count, deactivated_count)
    """
    print("\n" + "="*60)
    print("VALIDATE-ALL MODE: Checking all active listings")
    print("="*60)
    
    # Determine which sources to validate
    all_source_names = [
        "Encuentra24",
        "MiCasaSV",
        NEXO_SOURCE,
        "Realtor",
        REALTYELSALVADOR_SOURCE,
        CASASAHORITA_SOURCE,
        CAMARABIENESRAICES_SOURCE,
        "PropiLatam",
        "VivoLatam",
    ]
    if sources:
        sources_to_check = [s for s in sources if s in all_source_names]
    else:
        sources_to_check = all_source_names
    
    print(f"Sources to validate: {', '.join(sources_to_check)}")
    
    total_validated = 0
    total_deactivated = 0
    
    for source in sources_to_check:
        print(f"\n--- Validating {source} ---")
        
        # Fetch all active listings for this source
        active_listings = get_active_listings_from_db(source=source)
        
        if not active_listings:
            print(f"  No active listings found for {source}")
            continue
        
        print(f"  Found {len(active_listings)} active listings to validate")
        
        # Validate listings concurrently
        to_deactivate = []
        route_updates = []
        validated = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_listing = {
                executor.submit(check_listing_status_for_record, l): l
                for l in active_listings
            }
            
            for future in as_completed(future_to_listing):
                listing = future_to_listing[future]
                validated += 1
                try:
                    status = future.result()
                    is_active = status.get("is_active", True)
                    reason = status.get("reason", "Active")
                    if not is_active:
                        to_deactivate.append(listing['external_id'])
                        print(f"    X INACTIVE: {listing['url'][:70]}... ({reason})")
                    elif source == "PropiLatam":
                        resolved_url = status.get("resolved_url")
                        resolved_type = status.get("resolved_listing_type")
                        if resolved_url and resolved_url != listing.get("url"):
                            route_updates.append({
                                "external_id": listing["external_id"],
                                "url": resolved_url,
                                "listing_type": resolved_type
                            })
                except Exception as e:
                    print(f"    ? ERROR: {listing['url'][:70]}... ({e})")
                
                # Progress update every 100 listings
                if validated % 100 == 0:
                    print(
                        f"    Progress: {validated}/{len(active_listings)} checked "
                        f"({len(to_deactivate)} inactive, {len(route_updates)} route-updates)"
                    )
        
        print(
            f"  {source}: {validated} checked, {len(to_deactivate)} inactive, "
            f"{len(route_updates)} route-updates"
        )

        if route_updates:
            print(f"  Applying {len(route_updates)} Propi URL/type updates...")
            route_ok, route_err = update_listing_routes(route_updates)
            print(f"  Applied {route_ok} route updates ({route_err} errors)")
        
        # Deactivate confirmed inactive listings
        if to_deactivate:
            deactivated = deactivate_listings(to_deactivate)
            total_deactivated += deactivated
            print(f"  Deactivated {deactivated} listings")
        
        total_validated += validated
    
    # Refresh materialized view after deactivations
    if total_deactivated > 0:
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
        except Exception as e:
            print(f"  Warning: Error refreshing view: {e}")
    
    print(f"\n=== VALIDATE-ALL COMPLETE ===")
    print(f"Total validated: {total_validated}")
    print(f"Total deactivated: {total_deactivated}")
    
    return total_validated, total_deactivated


def deactivate_listings(external_ids):
    """
    Set active=false for a list of external_ids.
    
    Args:
        external_ids: List of external_id values to deactivate
    
    Returns:
        Number of successfully deactivated listings
    """
    if not external_ids:
        return 0
    
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }
    
    deactivated = 0
    
    # Process in batches of 100
    batch_size = 100
    for i in range(0, len(external_ids), batch_size):
        batch = external_ids[i:i + batch_size]
        
        # Use PATCH with filter to update multiple records
        # external_id.in.(id1,id2,id3...)
        ids_param = ",".join(str(eid) for eid in batch)
        url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?external_id=in.({ids_param})"
        
        try:
            resp = requests.patch(
                url, 
                headers=headers, 
                json={"active": False},
                timeout=30
            )
            if resp.status_code in (200, 204):
                deactivated += len(batch)
            else:
                print(f"    Deactivate batch error: {resp.status_code} - {resp.text[:200]}")
        except Exception as e:
            print(f"    Deactivate batch exception: {e}")
    
    return deactivated


def update_listing_routes(route_updates):
    """
    Update listing URL/listing_type by external_id.

    Args:
        route_updates: list of dicts with keys:
            - external_id
            - url
            - listing_type (optional)

    Returns:
        Tuple of (updated_count, error_count)
    """
    if not route_updates:
        return 0, 0

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    deduped = {}
    for item in route_updates:
        ext_id = item.get("external_id")
        new_url = item.get("url")
        if ext_id is None or not new_url:
            continue
        deduped[str(ext_id)] = item

    updated = 0
    errors = 0
    now_iso = datetime.now().isoformat()
    total = len(deduped)

    for idx, item in enumerate(deduped.values(), 1):
        ext_id = item["external_id"]
        patch_data = {
            "url": item["url"],
            "last_updated": now_iso
        }
        if item.get("listing_type"):
            patch_data["listing_type"] = item["listing_type"]

        patch_url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?external_id=eq.{ext_id}"
        try:
            resp = requests.patch(patch_url, headers=headers, json=patch_data, timeout=30)
            if resp.status_code in (200, 204):
                updated += 1
            else:
                errors += 1
                print(f"    Route update error for {ext_id}: {resp.status_code} - {resp.text[:160]}")
        except Exception as e:
            errors += 1
            print(f"    Route update exception for {ext_id}: {e}")

        if idx % 50 == 0 or idx == total:
            print(f"    Route updates: {idx}/{total} processed ({updated} ok, {errors} errors)")

    return updated, errors


def check_listing_status_for_record(listing):
    """
    Validate listing with optional normalized URL/type output.

    Returns dict:
      - is_active
      - reason
      - resolved_url
      - resolved_listing_type
    """
    source = listing.get("source")
    url = listing.get("url")

    if source == "PropiLatam":
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        return get_propilatam_listing_status(url, headers)

    is_active, reason = check_listing_still_active(url, source)
    return {
        "is_active": is_active,
        "reason": reason,
        "resolved_url": url,
        "resolved_listing_type": listing.get("listing_type"),
    }


def parse_localized_number(value):
    """Parse a human-formatted numeric token with either US or ES separators."""
    if value is None:
        return None

    cleaned = re.sub(r"[^\d,.\-]", "", str(value)).strip()
    if not cleaned or cleaned in {"-", ".", ",", "-.", "-,"}:
        return None

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif cleaned.count(",") > 1:
        cleaned = cleaned.replace(",", "")
    elif cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "")
    elif "," in cleaned:
        left, right = cleaned.rsplit(",", 1)
        if len(right) == 3 and left:
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        left, right = cleaned.rsplit(".", 1)
        if len(right) == 3 and left:
            cleaned = cleaned.replace(".", "")

    try:
        return float(cleaned)
    except (TypeError, ValueError):
        return None


def parse_price(price_str):
    """Parse a property price string into a float, including K/M abbreviations."""
    if price_str is None or price_str == "":
        return None

    if isinstance(price_str, (int, float)) and not isinstance(price_str, bool):
        return float(price_str)

    text = normalize_source_text(str(price_str))
    if not text:
        return None

    lowered = text.lower()
    if "consultar" in lowered and not re.search(r"\d", lowered):
        return None

    multiplier = 1
    if re.search(r"\bmill(?:ones?)?\b|\bmillon(?:es)?\b|(?<![a-z0-9])\d[\d.,]*\s*m\b", lowered):
        multiplier = 1_000_000
    elif re.search(r"\bmil\b|(?<![a-z0-9])\d[\d.,]*\s*k\b", lowered):
        multiplier = 1_000

    number_match = re.search(r"-?\d[\d.,]*", lowered)
    if not number_match:
        return None

    base_value = parse_localized_number(number_match.group(0))
    if base_value is None:
        return None

    return float(base_value) * multiplier


def correct_listing_type(listing_type, title, description, price, url=None):
    """
    Correct listing_type based on content analysis.
    Users sometimes list sale properties in the rent section and vice versa.
    
    Detection heuristics:
    1. URL path (most reliable for Encuentra24): "alquiler" = rent, "venta" = sale
    2. Strong sale keywords: "VENDO", "VENTA", "EN VENTA", "SE VENDE"
    3. Strong rent keywords: "ALQUILO", "RENTA", "ALQUILER", "MENSUAL"
    4. Price heuristics:
       - Sale prices are typically > $50,000 (for most properties)
       - Rent prices are typically < $5,000/month
    
    Args:
        listing_type: Current listing_type ('sale' or 'rent')
        title: Listing title
        description: Listing description
        price: Parsed price (float)
        url: Optional URL for path-based detection
        
    Returns:
        Corrected listing_type ('sale' or 'rent')
    """
    original_type = listing_type
    
    # 1. URL-based detection (most reliable for Encuentra24)
    if url:
        url_lower = url.lower()
        if 'alquiler' in url_lower or '-alquiler-' in url_lower:
            if listing_type == 'sale':
                print("    Warning: URL indicates rent but marked as sale, correcting to rent")
            return 'rent'
        elif 'venta' in url_lower or '-venta-' in url_lower:
            if listing_type == 'rent':
                print("    Warning: URL indicates sale but marked as rent, correcting to sale")
            return 'sale'
    
    if not title and not description:
        return listing_type
    
    # Combine title and description for analysis (uppercase for matching)
    text = f"{title or ''} {description or ''}".upper()
    title_upper = (title or '').upper()
    
    # Strong sale indicators
    sale_keywords = [
        r'\bVENDO\b',
        r'\bVENTA\b', 
        r'\bEN VENTA\b',
        r'\bSE VENDE\b',
        r'\bVENDER\b',
        r'\bPRECIO DE VENTA\b',
    ]
    
    # Strong rent indicators
    rent_keywords = [
        r'\bALQUILO\b',
        r'\bALQUILER\b',
        r'\bRENTA\b',
        r'\bEN RENTA\b',
        r'\bSE ALQUILA\b',
        r'\bMENSUAL\b',
        r'\bPOR MES\b',
        r'\b/MES\b',
    ]
    
    # Count keyword matches
    sale_matches = sum(1 for pattern in sale_keywords if re.search(pattern, text))
    rent_matches = sum(1 for pattern in rent_keywords if re.search(pattern, text))
    
    # Check for strong indicators in TITLE specifically (more weight)
    title_has_rent = any(re.search(pattern, title_upper) for pattern in [r'\bALQUILER\b', r'\bALQUILO\b', r'\bRENTA\b', r'\bSE ALQUILA\b'])
    title_has_sale = any(re.search(pattern, title_upper) for pattern in [r'\bVENTA\b', r'\bVENDO\b', r'\bSE VENDE\b'])
    
    # Price-based heuristics (in USD)
    price_suggests_sale = False
    price_suggests_rent = False
    
    if price:
        # Very low prices (<$500) could be rent
        if price < 500:
            price_suggests_rent = True
        # Mid-range ($500-$5000) is ambiguous, rely on keywords
        elif price < 5000:
            price_suggests_rent = True if rent_matches > sale_matches else False
    
    # Decision logic
    corrected_type = listing_type
    
    # If title explicitly says one type, trust it
    if title_has_rent and not title_has_sale:
        corrected_type = 'rent'
    elif title_has_sale and not title_has_rent:
        corrected_type = 'sale'
    elif listing_type == 'rent':
        # Currently marked as rent - check if it should be sale
        if sale_matches > rent_matches and (sale_matches >= 2 or price_suggests_sale):
            corrected_type = 'sale'
        elif sale_matches > 0 and price_suggests_sale:
            corrected_type = 'sale'
    elif listing_type == 'sale':
        # Currently marked as sale - check if it should be rent
        if rent_matches > sale_matches and (rent_matches >= 1 or price_suggests_rent):
            corrected_type = 'rent'
        elif rent_matches > 0 and price_suggests_rent and price and price < 5000:
            corrected_type = 'rent'
    
    if corrected_type != original_type:
        print(
            f"    Warning: Corrected listing_type {original_type} -> {corrected_type} "
            f"(sale_kw={sale_matches}, rent_kw={rent_matches}, price=${price})"
        )
    
    return corrected_type


def infer_listing_type_from_url(url, default_type="sale"):
    """
    Infer listing type from URL path.

    Returns:
        'rent' if URL indicates alquiler/rent
        'sale' if URL indicates venta/sale
        default_type otherwise
    """
    if not url:
        return default_type

    url_lower = url.lower()
    if "/alquiler/" in url_lower or "-alquiler-" in url_lower or "rent" in url_lower:
        return "rent"
    if "/venta/" in url_lower or "-venta-" in url_lower or "sale" in url_lower:
        return "sale"
    return default_type


def generate_location_tags(listing):
    """
    Generate property type tags for a listing.
    
    NOTE: Location tags are no longer generated here as we now use the 
    listing_location_match table with the sv_loc_group hierarchy for 
    location-based filtering.
    
    Only returns property type tags: Casa, Apartamento, Terreno, Local
    
    Args:
        listing: Dict with listing data including title, description, URL
        
    Returns:
        List containing the property type tag if detected, empty list otherwise
    """
    tags = []
    
    # Allowed property type tags
    ALLOWED_PROPERTY_TYPES = {"Casa", "Apartamento", "Terreno", "Local"}
    
    # Detect property subtype and add to tags
    try:
        subtype = detect_property_subtype(
            listing.get("title", ""),
            listing.get("description", ""),
            listing.get("details"),
            listing.get("url", "")
        )
        if subtype and subtype in ALLOWED_PROPERTY_TYPES:
            tags.append(subtype)
    except Exception as e:
        print(f"  Warning: Could not detect property subtype: {e}")
    
    return tags


def map_explicit_property_type(raw_value):
    """
    Map an explicit source-side property/category label to a normalized tag.

    Accepts English and Spanish variants from source-specific metadata such as:
    - details.property_type
    - details.categorias
    - details.property_type_label
    """
    if not raw_value:
        return None

    value = str(raw_value).strip().lower()

    if any(token in value for token in ["land", "lot", "lots", "terreno", "terrenos", "lote", "lotes", "solar", "parcela", "parcelas", "finca"]):
        return "Terreno"
    if any(token in value for token in ["apartment", "apartamento", "apartamentos", "condo", "condominium", "flat", "penthouse"]):
        return "Apartamento"
    if any(token in value for token in ["commercial", "office", "retail", "warehouse", "oficina", "oficinas", "local", "locales", "bodega", "bodegas", "galera", "nave industrial"]):
        return "Local"
    if any(token in value for token in ["house", "home", "single family", "townhouse", "casa", "casas", "residencia", "residencias", "vivienda"]):
        return "Casa"

    return None


def detect_property_subtype(title, description="", details=None, url=""):
    """
    Detect property subtype from listing content.
    
    Priority:
    1. Check details.property_type (explicit classification from source)
    2. Check URL path for category hints (e.g., /casas/, /terrenos/)
    3. Check TITLE for keywords (most reliable text indicator)
    4. Check DESCRIPTION for keywords (less reliable, may have false positives)
    
    Order of keyword checking: Apartamento → Local → Casa → Terreno
    (Casa before Terreno because houses often mention "terreno" as lot size)
    
    Args:
        title: Listing title
        description: Listing description
        details: Details dict (may contain property_type field)
        url: Listing URL
        
    Returns:
        One of ["Apartamento", "Local", "Casa", "Terreno"] or None
    """
    # First, check explicit property_type from source (most reliable)
    if details and isinstance(details, dict):
        explicit_type = map_explicit_property_type(details.get("property_type"))
        if explicit_type:
            return explicit_type

        # Some sources expose the real property class in category labels instead
        # of a canonical property_type field (for example MiCasaSV: "Lotes y terrenos").
        for key in ["categorias", "category", "categories", "property_type_label"]:
            explicit_category_type = map_explicit_property_type(details.get(key))
            if explicit_category_type:
                return explicit_category_type
    
    # Check URL for category hints (very reliable for Encuentra24)
    url_lower = (url or "").lower()
    if "/casas/" in url_lower or "/alquiler-casas/" in url_lower or "bienes-raices-alquiler-casas" in url_lower or "bienes-raices-venta-casas" in url_lower:
        return "Casa"
    if "/apartamentos/" in url_lower or "/alquiler-apartamentos/" in url_lower or "bienes-raices-alquiler-apartamentos" in url_lower or "bienes-raices-venta-apartamentos" in url_lower:
        return "Apartamento"
    if "/terrenos/" in url_lower or "bienes-raices-venta-terrenos" in url_lower:
        return "Terreno"
    if "/locales/" in url_lower or "/oficinas/" in url_lower or "bienes-raices-alquiler-locales" in url_lower:
        return "Local"
    
    # Keyword lists
    apartamento_keywords = [
        'apartamento', 'apto', 'apto.', 'depto',
        'penthouse', 'pent house', 'pent-house',
        'condominio', 'condo',
        'apartment', 'flat',
        'torre residencial'
    ]
    
    local_keywords = [
        'local comercial', 'local-comercial',
        'oficina', 'office',
        'bodega', 'warehouse', 'galera',
        'nave industrial', 'nave-industrial',
        'comercial', 'commercial',
        'retail', 'tienda',
        'negocio',
        'clinica', 'clínica'
    ]
    
    casa_keywords = [
        'casa', 'house', 'home',
        'residencia', 'residence',
        'chalet', 'vivienda',
        'quinta', 'townhouse', 'town house', 'town-house',
        'duplex', 'dúplex'
    ]
    
    # More specific terreno patterns to avoid matching "X m2 de terreno"
    terreno_keywords = [
        'venta de terreno', 'terreno en venta',
        'lote en venta', 'venta de lote',
        'solar', 'parcela', 'finca',
        'land for sale', 'lot for sale',
        'hectarea', 'hectárea',
        'predio'
    ]
    
    # Simple terreno keywords (less specific, check last)
    terreno_simple = ['terreno', 'lote', 'land', 'lot']
    
    title_lower = (title or "").lower()
    description_lower = (description or "").lower()
    
    # STEP 1: Check TITLE first (most reliable)
    # Order: Apartamento → Local → Casa → Terreno
    for keyword in apartamento_keywords:
        if keyword in title_lower:
            return "Apartamento"
    
    for keyword in local_keywords:
        if keyword in title_lower:
            return "Local"
    
    for keyword in casa_keywords:
        if keyword in title_lower:
            return "Casa"
    
    # Check specific terreno patterns in title
    for keyword in terreno_keywords:
        if keyword in title_lower:
            return "Terreno"
    
    # Check simple terreno keywords in title (if no casa found yet)
    for keyword in terreno_simple:
        if keyword in title_lower:
            return "Terreno"
    
    # STEP 2: Check DESCRIPTION (less reliable, Casa/Apto/Local takes priority over Terreno)
    for keyword in apartamento_keywords:
        if keyword in description_lower:
            return "Apartamento"
    
    for keyword in local_keywords:
        if keyword in description_lower:
            return "Local"
    
    for keyword in casa_keywords:
        if keyword in description_lower:
            return "Casa"
    
    # Only classify as Terreno from description if using specific patterns
    # Avoid matching "1000 m2 de terreno" which just describes lot size
    for keyword in terreno_keywords:
        if keyword in description_lower:
            return "Terreno"
    
    # Don't use simple terreno keywords from description (too many false positives)
    
    return None


def parse_date(date_str):
    """Parse date string to ISO format."""
    if not date_str:
        return None
    # Return as-is if already valid, otherwise return None
    return date_str if date_str else None


def is_listing_within_date_range(published_date_str, max_days=7):
    """
    Check if a listing's published date is within the allowed range.
    
    Args:
        published_date_str: Date string in various formats (dd/mm/yyyy, yyyy-mm-dd, etc.)
        max_days: Maximum age in days. If 0 or None, always returns True (no filtering).
        
    Returns:
        Tuple of (is_within_range: bool, parsed_date: datetime or None)
        Returns (True, None) if date cannot be parsed (fail-safe: don't exclude valid listings)
    """
    # If no filtering requested, always return True
    if not max_days or max_days <= 0:
        return (True, None)
    
    if not published_date_str:
        return (True, None)  # No date = don't exclude
    
    date_str = str(published_date_str).strip().lower()
    parsed_date = None
    
    try:
        # Try various date formats
        formats_to_try = [
            ("%d/%m/%Y", date_str),           # 25/01/2026
            ("%Y-%m-%d", date_str),           # 2026-01-25
            ("%d-%m-%Y", date_str),           # 25-01-2026
            ("%Y/%m/%d", date_str),           # 2026/01/25
            ("%d %b %Y", date_str),           # 25 Jan 2026
            ("%d de %B de %Y", date_str),     # 25 de enero de 2026
        ]
        
        for fmt, date_val in formats_to_try:
            try:
                parsed_date = datetime.strptime(date_val, fmt)
                break
            except ValueError:
                continue
        
        # Handle ISO format with time (2026-01-25T10:30:00)
        if not parsed_date and 'T' in date_str:
            try:
                parsed_date = datetime.fromisoformat(date_str.split('T')[0])
            except:
                pass
        
        # Handle relative dates (Spanish)
        if not parsed_date:
            relative_patterns = [
                (r'hace\s+(\d+)\s+d[ií]as?', 'days'),
                (r'hace\s+(\d+)\s+semanas?', 'weeks'),
                (r'hace\s+(\d+)\s+meses?', 'months'),
                (r'hace\s+(\d+)\s+horas?', 'hours'),
                (r'(\d+)\s+d[ií]as?\s+atr[aá]s', 'days'),
                (r'hoy', 'today'),
                (r'ayer', 'yesterday'),
            ]
            
            for pattern, unit in relative_patterns:
                match = re.search(pattern, date_str)
                if match:
                    if unit == 'today':
                        parsed_date = datetime.now()
                    elif unit == 'yesterday':
                        parsed_date = datetime.now() - timedelta(days=1)
                    elif unit == 'hours':
                        hours = int(match.group(1))
                        parsed_date = datetime.now() - timedelta(hours=hours)
                    elif unit == 'days':
                        days = int(match.group(1))
                        parsed_date = datetime.now() - timedelta(days=days)
                    elif unit == 'weeks':
                        weeks = int(match.group(1))
                        parsed_date = datetime.now() - timedelta(weeks=weeks)
                    elif unit == 'months':
                        months = int(match.group(1))
                        parsed_date = datetime.now() - timedelta(days=months * 30)
                    break
        
        # If we parsed a date, check if within range
        if parsed_date:
            days_old = (datetime.now() - parsed_date).days
            is_within = days_old <= max_days
            return (is_within, parsed_date)
        
        # Could not parse date - don't exclude (fail-safe)
        return (True, None)
        
    except Exception as e:
        # Any parsing error - don't exclude
        return (True, None)

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


def normalize_source_text(text):
    """Normalize scraped text, including common mojibake repairs."""
    if text is None:
        return ""

    cleaned = unescape(str(text)).replace("\xa0", " ").replace("\r", " ")
    cleaned = cleaned.replace("\u200b", " ")

    if any(marker in cleaned for marker in ("Ã", "Â", "â", "\x81", "\x8d", "\x8f", "\x90", "\x9d")):
        for source_encoding in ("latin-1", "cp1252"):
            try:
                repaired = cleaned.encode(source_encoding).decode("utf-8")
                if repaired and repaired.count("Ã") < cleaned.count("Ã"):
                    cleaned = repaired
                    break
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue

    cleaned = remove_emojis(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def is_probable_bot_block_page(page_html, soup=None):
    """Detect common anti-bot challenge pages without flagging normal listing pages."""
    if not page_html:
        return False

    lowered = page_html.lower()
    strong_markers = [
        "attention required",
        "just a moment",
        "verify you are human",
        "please enable cookies",
        "cf-browser-verification",
        "/cdn-cgi/challenge-platform/",
        "__cf_chl_tk",
    ]
    if not any(marker in lowered for marker in strong_markers):
        return False

    soup = soup or BeautifulSoup(page_html, "html.parser")
    title_text = normalize_source_text(soup.title.get_text(" ", strip=True) if soup.title else "").lower()
    h1_el = soup.select_one("h1")
    h1_text = normalize_source_text(h1_el.get_text(" ", strip=True) if h1_el else "").lower()

    blocking_titles = ("attention required", "just a moment", "access denied", "verify you are human")
    if any(marker in title_text for marker in blocking_titles):
        return True
    if any(marker in h1_text for marker in blocking_titles):
        return True

    has_listing_signals = bool(h1_text) and "og:title" in lowered
    return not has_listing_signals


def extract_meta_content(page_html, meta_name):
    """Extract a meta tag content value by property/name."""
    if not page_html or not meta_name:
        return ""

    pattern = rf'<meta[^>]+(?:property|name)="{re.escape(meta_name)}"[^>]+content="([^"]*)"'
    match = re.search(pattern, page_html, re.IGNORECASE)
    if not match:
        return ""

    return normalize_source_text(unescape(match.group(1)))


PROPILATAM_UNAVAILABLE_MARKERS = (
    "pagina no encontrada",
    "no se encontro este anuncio",
    "no se encuentra disponible",
)


def clean_propilatam_heading_text(value):
    """Normalize Propi/Vivo heading text and strip brand/ID suffixes."""
    cleaned = normalize_source_text(value)
    if not cleaned:
        return ""

    if " | " in cleaned:
        cleaned = cleaned.split(" | ", 1)[0]

    return cleaned.strip(" |")


def get_propilatam_page_snapshot(raw_html, soup=None):
    """Extract high-signal title/state fields from a Propi/Vivo detail page."""
    snapshot = {
        "page_title": "",
        "og_title": "",
        "h1_text": "",
        "meta_description": "",
        "body_prefix": "",
        "body_prefix_lower": "",
        "high_signal_text": "",
        "display_title": "",
        "has_listing_signal": False,
    }
    if not raw_html:
        return snapshot

    soup = soup or BeautifulSoup(raw_html, "html.parser")
    page_title = clean_propilatam_heading_text(
        soup.title.get_text(" ", strip=True) if soup.title else extract_meta_content(raw_html, "title")
    )
    og_title = clean_propilatam_heading_text(extract_meta_content(raw_html, "og:title"))
    h1_el = soup.find("h1")
    h1_text = clean_propilatam_heading_text(h1_el.get_text(" ", strip=True) if h1_el else "")
    meta_description = normalize_source_text(
        extract_meta_content(raw_html, "og:description") or extract_meta_content(raw_html, "description")
    )
    main_el = soup.find("main") or soup.body or soup
    body_text = normalize_source_text(main_el.get_text(" ", strip=True) if main_el else "")
    body_prefix = body_text[:1600]
    high_signal_parts = [page_title, og_title, h1_text, meta_description]
    high_signal_text = " | ".join(part for part in high_signal_parts if part).lower()

    snapshot.update(
        {
            "page_title": page_title,
            "og_title": og_title,
            "h1_text": h1_text,
            "meta_description": meta_description,
            "body_prefix": body_prefix,
            "body_prefix_lower": body_prefix.lower(),
            "high_signal_text": high_signal_text,
            "display_title": h1_text or og_title or page_title,
            "has_listing_signal": bool(h1_text or og_title),
        }
    )
    return snapshot


def get_propilatam_page_issue(raw_html, soup=None):
    """Classify high-signal Propi/Vivo page states without scanning the whole app shell."""
    snapshot = get_propilatam_page_snapshot(raw_html, soup=soup)
    high_signal_text = snapshot["high_signal_text"]
    body_prefix_lower = snapshot["body_prefix_lower"]

    if any(
        "undefined" in field.lower()
        for field in (snapshot["page_title"], snapshot["og_title"], snapshot["h1_text"])
        if field
    ):
        return "placeholder page"

    if any(marker in high_signal_text for marker in PROPILATAM_UNAVAILABLE_MARKERS):
        return "listing unavailable"

    if not snapshot["has_listing_signal"] and any(
        marker in body_prefix_lower for marker in PROPILATAM_UNAVAILABLE_MARKERS
    ):
        return "listing unavailable"

    if (
        not snapshot["h1_text"]
        and "precio desde" in body_prefix_lower
        and "programar asesor" in body_prefix_lower
        and "elegir unidad" in body_prefix_lower
    ):
        return "placeholder page"

    return None


def decode_escaped_json_string(raw_value):
    """Decode a JSON-escaped string fragment from Next.js flight payloads."""
    if raw_value is None:
        return ""

    try:
        decoded = json.loads(f'"{raw_value}"')
    except json.JSONDecodeError:
        decoded = raw_value.replace('\\"', '"').replace("\\\\", "\\")

    decoded = normalize_source_text(decoded)

    if not decoded or decoded == "$undefined" or re.fullmatch(r"\$[0-9a-f]+", decoded):
        return ""

    return decoded


def extract_escaped_string_value(blob, key):
    """Extract a string value from an escaped JSON fragment."""
    pattern = rf'\\"{re.escape(key)}\\":\\"((?:\\\\.|[^"\\\\])*)\\"'
    match = re.search(pattern, blob)
    if not match:
        return ""
    return decode_escaped_json_string(match.group(1))


def extract_escaped_number_value(blob, key):
    """Extract a numeric value from an escaped JSON fragment."""
    pattern = rf'\\"{re.escape(key)}\\":(-?\d+(?:\.\d+)?)'
    match = re.search(pattern, blob)
    if not match:
        return None

    raw_value = match.group(1)
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None


ENCUENTRA24_OFFICE_LOCATION_MARKERS = (
    "torre futura",
    "plaza paradiso",
    "urbanización lomas de altamira",
    "urbanizacion lomas de altamira",
    "calle el zenzontle",
    "avenida bernal y yumury",
    "bambú city center",
    "bambu city center",
    "colonia escalon cp",
    " cp ",
)

EL_SALVADOR_DEPARTMENTS = {
    "ahuachapan",
    "santa ana",
    "sonsonate",
    "chalatenango",
    "la libertad",
    "san salvador",
    "cuscatlan",
    "la paz",
    "cabanas",
    "san vicente",
    "usulutan",
    "san miguel",
    "morazan",
    "la union",
}

LOCATION_CONTEXT_STOPWORDS = {
    "de",
    "del",
    "la",
    "las",
    "los",
    "el",
    "en",
    "y",
    "no",
    "por",
}


def is_suspicious_encuentra24_location_fragment(text):
    """Detect broker office/location contamination inside Encuentra24 address fields."""
    cleaned = normalize_source_text(text).lower()
    if not cleaned:
        return False

    if encuentra24_location_looks_garbled(cleaned):
        return True

    if any(marker in cleaned for marker in ENCUENTRA24_OFFICE_LOCATION_MARKERS):
        return True

    if re.search(r"\b\d{1,2}-\d{2}[a-z]?\b", cleaned):
        return True

    return False


def is_street_level_encuentra24_location_fragment(text):
    """Detect street-address fragments that are too specific for the compact location field."""
    cleaned = normalize_source_text(text).lower()
    if not cleaned:
        return False

    return bool(
        re.search(r"\b(calle|avenida|av\.?|boulevard|blvd|pasaje|carretera|km|kil[oó]metro)\b", cleaned)
    )


def is_el_salvador_department(text):
    """Check whether a location fragment is a Salvadoran department label."""
    cleaned = normalize_source_text(text)
    if not cleaned:
        return False
    normalized = unicodedata.normalize("NFKD", cleaned.lower())
    ascii_like = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_like = re.sub(r"[^a-z0-9\s]", " ", ascii_like)
    ascii_like = re.sub(r"\s+", " ", ascii_like).strip()
    return ascii_like in EL_SALVADOR_DEPARTMENTS


def simplify_location_text(text):
    """Normalize location-like text to comparable ASCII tokens."""
    cleaned = normalize_source_text(text)
    if not cleaned:
        return ""
    normalized = unicodedata.normalize("NFKD", cleaned.lower())
    ascii_like = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_like = re.sub(r"[^a-z0-9\s]", " ", ascii_like)
    ascii_like = re.sub(r"\s+", " ", ascii_like).strip()
    return ascii_like


def location_token_set(text):
    """Build a compact token set for location-vs-context comparisons."""
    return {
        token
        for token in simplify_location_text(text).split()
        if token and token not in LOCATION_CONTEXT_STOPWORDS
    }


def encuentra24_location_has_street_level_fragment(text):
    """Check whether any part of a location string looks like a street address."""
    return any(
        is_street_level_encuentra24_location_fragment(part)
        for part in clean_encuentra24_location_parts(text)
    )


def encuentra24_location_looks_garbled(text):
    """Detect rendered fallbacks that accidentally include price/spec text."""
    cleaned = normalize_source_text(text).lower()
    if not cleaned:
        return False
    if any(
        marker in cleaned
        for marker in ("recámaras", "recamaras", "baños", "banos", "por usd", "por $")
    ):
        return True
    return bool(
        re.search(
            r"\b\d+\s+rec(?:á|a)maras\b|\b\d+\s+ba(?:ñ|n)os\b|\busd\s*\d",
            cleaned,
            re.IGNORECASE,
        )
    )


def encuentra24_location_context_score(location, title, url):
    """Measure how strongly a location candidate matches the title/URL context."""
    loc_tokens = location_token_set(location)
    if not loc_tokens:
        return 0

    url_path = unquote(urlparse(url).path.replace("-", " ")) if url else ""
    context_tokens = location_token_set(f"{title or ''} {url_path}")
    return len(loc_tokens & context_tokens)


def should_prefer_rendered_encuentra24_location(current, rendered, title="", url=""):
    """Choose rendered location when it aligns better with the listing context."""
    current_text = normalize_source_text(current)
    rendered_text = normalize_source_text(rendered)
    if not rendered_text or encuentra24_location_looks_garbled(rendered_text):
        return False
    if not current_text:
        return True

    current_tokens = location_token_set(current_text)
    rendered_tokens = location_token_set(rendered_text)
    if rendered_tokens and len(rendered_tokens) <= 2 and rendered_tokens.issubset(current_tokens):
        return False

    if (
        (is_suspicious_encuentra24_location_fragment(current_text) or encuentra24_location_has_street_level_fragment(current_text))
        and not is_suspicious_encuentra24_location_fragment(rendered_text)
    ):
        return True

    current_score = encuentra24_location_context_score(current_text, title, url)
    rendered_score = encuentra24_location_context_score(rendered_text, title, url)

    if rendered_score > current_score:
        return True

    if (
        not any(is_el_salvador_department(part) for part in clean_encuentra24_location_parts(current_text))
        and any(is_el_salvador_department(part) for part in clean_encuentra24_location_parts(rendered_text))
        and rendered_score >= current_score
    ):
        return True

    return False


def clean_encuentra24_location_parts(raw_value):
    """Split a location field into clean geographic parts, stopping before office noise."""
    cleaned = normalize_source_text(raw_value)
    if not cleaned:
        return []

    parts = []
    for piece in cleaned.split(","):
        part = normalize_source_text(piece).strip(" ,|-.")
        if not part or part.lower() == "el salvador":
            continue
        if is_suspicious_encuentra24_location_fragment(part):
            break
        if part.lower() not in [existing.lower() for existing in parts]:
            parts.append(part)

    if not parts and not is_suspicious_encuentra24_location_fragment(cleaned):
        return [cleaned]

    return parts


def build_encuentra24_location_text(exact_address="", address="", region_name="", city="", locality=""):
    """Build a cleaner location string from Encuentra24 embedded fields."""
    parts = []

    primary_parts = clean_encuentra24_location_parts(exact_address)
    if not primary_parts:
        primary_parts = clean_encuentra24_location_parts(address)
    while primary_parts and is_street_level_encuentra24_location_fragment(primary_parts[0]):
        primary_parts = primary_parts[1:]

    has_department = any(is_el_salvador_department(part) for part in primary_parts)

    for part in primary_parts:
        if part.lower() not in [existing.lower() for existing in parts]:
            parts.append(part)

    for value in [locality, city, region_name]:
        for part in clean_encuentra24_location_parts(value):
            if part.lower() not in [existing.lower() for existing in parts]:
                if has_department and len(primary_parts) >= 2:
                    continue
                parts.append(part)

    compact_location = ", ".join(parts[:3])
    compact_location = re.sub(r",?\s*el salvador\s*(?=,|$)", "", compact_location, flags=re.IGNORECASE)
    compact_location = re.sub(r"\s+,", ",", compact_location)
    compact_location = re.sub(r",\s*,+", ", ", compact_location)
    return compact_location.strip(" ,|-")


def extract_encuentra24_rendered_fallback(page_html, url):
    """
    Extract listing fields from Encuentra24's rendered React/Tailwind layout.

    Some current listing pages no longer expose the old `.d3-*` blocks or an
    easily anchored flight payload, but the rendered `main` content still
    contains the primary price/spec/description data.
    """
    fallback = {
        "price": "",
        "location": "",
        "published_date": "",
        "description": "",
        "specs": {},
        "details": {},
        "latitude": None,
        "longitude": None,
    }

    if not page_html:
        return fallback

    soup = BeautifulSoup(page_html, "html.parser")
    main_el = soup.find("main")
    main_text = normalize_source_text(main_el.get_text(" ", strip=True) if main_el else soup.get_text(" ", strip=True))
    title_el = soup.find("h1")
    title_text = normalize_source_text(title_el.get_text(" ", strip=True) if title_el else "")
    meta_title = extract_meta_content(page_html, "og:title") or extract_meta_content(page_html, "title")
    meta_description = extract_meta_content(page_html, "og:description") or extract_meta_content(page_html, "description")

    after_title = main_text
    if title_text and title_text.lower() in main_text.lower():
        title_index = main_text.lower().find(title_text.lower())
        after_title = main_text[title_index + len(title_text):].strip()

    price_token_pattern = r"(?:US\$|USD|\$)\s*[\d,.]+(?:\s*(?:[kKmM]\b|mil(?:lones?)?\b|millones?\b))?"

    # The location appears immediately after the title and before the first main
    # price. Ignore country-only placeholders like "El Salvador".
    location_segment = re.split(price_token_pattern, after_title, maxsplit=1, flags=re.IGNORECASE)[0]
    location_segment = normalize_source_text(location_segment.replace(" ,", ",").strip(" ,|-"))
    if location_segment:
        location_parts = []
        for part in [normalize_source_text(piece) for piece in location_segment.split(",")]:
            if not part or part.lower() == "el salvador":
                continue
            if part.lower() not in [existing.lower() for existing in location_parts]:
                location_parts.append(part)
        fallback["location"] = ", ".join(location_parts[:2])

    named_price_pattern = r"por\s+((?:(?:US\$|USD|\$)\s*)?[\d,.]+(?:\s*(?:[kKmM]\b|mil(?:lones?)?\b|millones?\b))?)"
    title_price_match = re.search(named_price_pattern, title_text, re.IGNORECASE) if title_text else None
    meta_price_match = re.search(named_price_pattern, meta_title, re.IGNORECASE) if meta_title else None

    if title_price_match and parse_price(title_price_match.group(1)):
        fallback["price"] = title_price_match.group(1).strip()
    elif meta_price_match and parse_price(meta_price_match.group(1)):
        fallback["price"] = meta_price_match.group(1).strip()

    price_segment = after_title
    spec_anchor = re.search(r"\brec[áa]maras\b|\bba[ñn]os\b|\bparking\b|\bdetalles adicionales\b", price_segment, re.IGNORECASE)
    if spec_anchor:
        price_segment = price_segment[:spec_anchor.start()]

    if not fallback["price"]:
        price_candidates = []
        for match in re.finditer(price_token_pattern, price_segment, re.IGNORECASE):
            candidate = normalize_source_text(match.group(0))
            parsed = parse_price(candidate)
            if not parsed or parsed <= 0:
                continue

            context_window = price_segment[max(0, match.start() - 30):match.end() + 45].lower()
            if parsed < 10000 and any(token in context_window for token in ("mantenimiento", "/mes", "mensual")):
                continue

            price_candidates.append(candidate)

        if "% off" in price_segment.lower() and len(price_candidates) >= 2:
            fallback["price"] = price_candidates[1]
        elif price_candidates:
            fallback["price"] = price_candidates[0]

    if fallback["price"] and not parse_price(fallback["price"]):
        fallback["price"] = ""

    if not fallback["location"] and meta_title:
        location_match = re.search(r"\ben\s+([^|]+)$", meta_title, re.IGNORECASE)
        if location_match:
            inferred_location = normalize_source_text(location_match.group(1))
            if inferred_location and inferred_location.lower() != "el salvador":
                fallback["location"] = inferred_location

    updated_match = re.search(r"Actualizado el:\s*(\d{2}/\d{2}/\d{4})", main_text, re.IGNORECASE)
    if updated_match:
        fallback["published_date"] = updated_match.group(1)

    bedrooms_match = re.search(r"\brec[áa]maras\s+(\d+(?:[.,]\d+)?)", main_text, re.IGNORECASE)
    bathrooms_match = re.search(r"\bba[ñn]os\s+(\d+(?:[.,]\d+)?)", main_text, re.IGNORECASE)
    parking_match = re.search(r"\bparking\s+(\d+(?:[.,]\d+)?)", main_text, re.IGNORECASE)
    area_match = re.search(r"[áa]rea construida\s+([\d,.]+)\s*m[²2]", main_text, re.IGNORECASE)
    total_area_match = re.search(r"[áa]rea total\s+([\d,.]+)\s*m[²2]", main_text, re.IGNORECASE)

    if bedrooms_match:
        fallback["specs"]["bedrooms"] = bedrooms_match.group(1).replace(",", ".")
    if bathrooms_match:
        fallback["specs"]["bathrooms"] = bathrooms_match.group(1).replace(",", ".")
    if parking_match:
        fallback["specs"]["parking"] = parking_match.group(1).replace(",", ".")
    if area_match:
        fallback["specs"]["area_m2"] = area_match.group(1).replace(",", "")
    if total_area_match:
        fallback["specs"]["Área total"] = f'{total_area_match.group(1)} m²'

    details_heading = next(
        (
            h2 for h2 in soup.find_all("h2")
            if "detalles adicionales" in normalize_source_text(h2.get_text(" ", strip=True)).lower()
        ),
        None,
    )
    if details_heading:
        details_grid = details_heading.find_next(
            lambda tag: tag.name == "div" and {"grid", "gap-2"}.issubset(set(tag.get("class", [])))
        )
        if details_grid:
            for container in details_grid.select("div.flex-1.min-w-0"):
                label_el = container.select_one("p.text-xs.text-muted-foreground")
                value_el = container.select_one("p.text-sm.font-medium.text-foreground")
                if not label_el or not value_el:
                    continue

                label = normalize_source_text(label_el.get_text(" ", strip=True))
                value = normalize_source_text(value_el.get_text(" ", strip=True))
                if not label or not value or value.lower() == "consultar":
                    continue

                label_lower = label.lower()
                if "tipo de propiedad" in label_lower:
                    fallback["details"]["property_type"] = value
                elif "niveles" in label_lower:
                    fallback["details"]["Niveles"] = value
                elif "área construida" in label_lower or "area construida" in label_lower:
                    area_value = re.search(r"([\d,.]+)", value)
                    if area_value:
                        fallback["specs"]["area_m2"] = area_value.group(1).replace(",", "")
                elif "área total" in label_lower or "area total" in label_lower:
                    fallback["specs"]["Área total"] = value
                else:
                    fallback["details"][label] = value

    details_location = build_encuentra24_location_text(
        exact_address=fallback["details"].get("Ubicación", ""),
        region_name=fallback["details"].get("Región", ""),
    )
    if details_location and (
        not fallback["location"]
        or is_suspicious_encuentra24_location_fragment(fallback["location"])
        or ("," not in fallback["location"] and "," in details_location)
    ):
        fallback["location"] = details_location
        fallback["details"]["Ubicación"] = details_location

    description_heading = next(
        (
            h2 for h2 in soup.find_all("h2")
            if normalize_source_text(h2.get_text(" ", strip=True)).lower() == "descripción"
        ),
        None,
    )
    if description_heading:
        description_el = description_heading.find_next(
            lambda tag: tag.name == "p" and normalize_source_text(tag.get_text(" ", strip=True)).lower() not in ("", "descripción")
        )
        if description_el:
            description_text = remove_emojis(description_el.get_text(separator="\n", strip=True))
            description_text = re.sub(r"\n{3,}", "\n\n", description_text).strip()
            if description_text and "encuentra24 nunca solicita" not in description_text.lower():
                fallback["description"] = description_text

    if not fallback["description"]:
        fallback["description"] = meta_description

    if fallback["location"]:
        fallback["details"].setdefault("Ubicación", fallback["location"])

    title_region_match = re.search(r"\ben\s+([^|]+)$", meta_title, re.IGNORECASE) if meta_title else None
    if title_region_match:
        inferred_region = normalize_source_text(title_region_match.group(1))
        if inferred_region and inferred_region.lower() != "el salvador":
            fallback["details"].setdefault("Región", inferred_region)

    return fallback


def extract_encuentra24_embedded_fallback(page_html, url):
    """
    Extract listing fields from Encuentra24's embedded Next.js flight payload.

    The newer page format keeps the listing data in escaped JSON within script
    tags instead of the older `.d3-*` HTML blocks. This fallback anchors on the
    current listing path so we do not accidentally parse a related listing card.
    """
    fallback = {
        "price": "",
        "location": "",
        "description": "",
        "specs": {},
        "details": {},
        "latitude": None,
        "longitude": None,
    }

    if not page_html or not url:
        return fallback

    path = urlparse(url).path
    anchor = page_html.find(f'\\"link\\":\\"{path}\\"')

    # Most of the current listing object lives after the `link` field. Keep a
    # smaller prefix for fields like description that appear before it.
    if anchor != -1:
        blob_before = page_html[max(0, anchor - 4000):anchor]
        blob_after = page_html[anchor:min(len(page_html), anchor + 10000)]
    else:
        blob_before = ""
        blob_after = ""

    region_name = extract_escaped_string_value(blob_after, "regionName")
    exact_address = extract_escaped_string_value(blob_after, "exactAddress")
    address = extract_escaped_string_value(blob_after, "address")
    city = extract_escaped_string_value(blob_after, "city")
    locality = extract_escaped_string_value(blob_after, "locality")

    location_text = build_encuentra24_location_text(
        exact_address=exact_address,
        address=address,
        region_name=region_name,
        city=city,
        locality=locality,
    )

    price_value = extract_escaped_number_value(blob_after, "price_value")
    if price_value is None:
        price_value = extract_escaped_number_value(blob_after, "propertyPrice")

    latitude = extract_escaped_number_value(blob_after, "lat")
    longitude = extract_escaped_number_value(blob_after, "lon")
    if latitude is not None and longitude is not None and abs(latitude) < 0.000001 and abs(longitude) < 0.000001:
        latitude = None
        longitude = None

    bedrooms = extract_escaped_string_value(blob_after, "rooms")
    bathrooms = extract_escaped_string_value(blob_after, "bathrooms")
    parking = extract_escaped_string_value(blob_after, "parking")
    square = extract_escaped_string_value(blob_after, "square")
    lot_size = extract_escaped_string_value(blob_after, "lotSize")
    age = extract_escaped_string_value(blob_after, "age")
    stories = extract_escaped_string_value(blob_after, "stories")
    floor_type = extract_escaped_string_value(blob_after, "floorType")
    property_type = extract_escaped_string_value(blob_after, "subCategoryType")

    description = extract_escaped_string_value(blob_before, "description")
    if description:
        description = (
            description.replace("<br />", "\n")
            .replace("<br/>", "\n")
            .replace("<br>", "\n")
        )
        description = re.sub(r"\n{3,}", "\n\n", description).strip()

    if price_value:
        fallback["price"] = f"${price_value:,.2f}"

    fallback["location"] = location_text
    fallback["description"] = description
    fallback["latitude"] = latitude
    fallback["longitude"] = longitude

    if bedrooms:
        fallback["specs"]["bedrooms"] = bedrooms
    if bathrooms:
        fallback["specs"]["bathrooms"] = bathrooms
    if parking:
        fallback["specs"]["parking"] = parking
    if square:
        fallback["specs"]["Área construida (m²)"] = square
    if lot_size:
        fallback["specs"]["Área de terreno (m²)"] = lot_size

    if location_text:
        fallback["details"]["Ubicación"] = location_text
    if property_type:
        fallback["details"]["property_type"] = property_type
    if region_name:
        fallback["details"]["Región"] = region_name
    if age:
        fallback["details"]["Año"] = age
    if stories:
        fallback["details"]["Niveles"] = stories
    if floor_type:
        fallback["details"]["Tipo de piso"] = floor_type

    # SEO metadata remains stable and provides a good fallback when the embedded
    # description is compressed or missing.
    if not fallback["description"]:
        fallback["description"] = extract_meta_content(page_html, "og:description")

    if not fallback["price"]:
        meta_title = extract_meta_content(page_html, "og:title") or extract_meta_content(page_html, "title")
        price_match = re.search(r'por\s+(?:USD\s+)?([\d,.]+)', meta_title, re.IGNORECASE)
        if price_match:
            try:
                if float(price_match.group(1).replace(",", "")) > 0:
                    fallback["price"] = f"${price_match.group(1)}"
            except ValueError:
                pass

    if not fallback["location"]:
        meta_title = extract_meta_content(page_html, "og:title") or extract_meta_content(page_html, "title")
        location_match = re.search(r'\ben\s+([^|]+)$', meta_title, re.IGNORECASE)
        if location_match:
            fallback["location"] = normalize_source_text(location_match.group(1))

    if "bedrooms" not in fallback["specs"]:
        meta_title = extract_meta_content(page_html, "og:title") or extract_meta_content(page_html, "title")
        bedrooms_match = re.search(r'(\d+(?:[.,]\d+)?)\s+recámaras', meta_title, re.IGNORECASE)
        if bedrooms_match:
            fallback["specs"]["bedrooms"] = bedrooms_match.group(1).replace(",", ".")

    return fallback


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

# ============== NEXO CONFIG ==============
NEXO_SOURCE = "Nexo"
NEXO_BASE_URL = "https://nexo.com.sv"
NEXO_LISTING_TYPE_BY_CODE = {
    "1": "sale",
    "2": "rent",
    "3": "sale",
    "4": "rent",
    "6": "sale",
}
NEXO_PROPERTY_TYPE_BY_CODE = {
    "1": "house",
    "2": "house",
    "3": "apartment",
    "4": "apartment",
    "6": "land",
}
NEXO_CATEGORIES = [
    {"name": "houses_sale", "url": f"{NEXO_BASE_URL}/casas-en-venta-el-salvador/{{}}", "listing_type": "sale", "property_type": "house", "type_code": "1"},
    {"name": "apartments_sale", "url": f"{NEXO_BASE_URL}/apartamentos-en-venta-el-salvador/{{}}", "listing_type": "sale", "property_type": "apartment", "type_code": "3"},
    {"name": "land_sale", "url": f"{NEXO_BASE_URL}/terrenos-en-venta-el-salvador/{{}}", "listing_type": "sale", "property_type": "land", "type_code": "6"},
    {"name": "houses_rent", "url": f"{NEXO_BASE_URL}/casas-en-alquiler-el-salvador/{{}}", "listing_type": "rent", "property_type": "house", "type_code": "2"},
    {"name": "apartments_rent", "url": f"{NEXO_BASE_URL}/apartamentos-en-alquiler-el-salvador/{{}}", "listing_type": "rent", "property_type": "apartment", "type_code": "4"},
]
NEXO_ERROR_MARKERS = [
    "error occurred while processing request",
    "the web site you are accessing has experienced an unexpected error",
    "error executing database query",
]

# ============== REALTOR.COM CONFIG ==============
REALTOR_BASE_URL = "https://www.realtor.com"
REALTOR_SALE_URL = "https://www.realtor.com/international/sv"
REALTOR_RENT_URL = "https://www.realtor.com/international/sv?channel=rent"
REALTOR_PHOTO_CDN = "https://s1.rea.global/img/600x400-prop/"  # Corrected CDN URL with size prefix
SQFT_TO_M2 = 0.092903  # Conversion factor from sq ft to sq meters

# Shared Realtor session with browser-like headers to reduce 403s
REALTOR_SESSION = None

def get_realtor_session():
    """Get or create a shared requests.Session with full browser headers for Realtor.com."""
    global REALTOR_SESSION
    if REALTOR_SESSION is None:
        REALTOR_SESSION = requests.Session()
        REALTOR_SESSION.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9,es;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
    return REALTOR_SESSION

# ============== CAMARA BIENES RAICES CONFIG ==============
CAMARABIENESRAICES_SOURCE = "CamaraBienesRaices"
CBR_BASE_URL = "https://www.camarabienesraices.com.sv"
CBR_API_BASE = f"{CBR_BASE_URL}/wp-json/wp/v2"
CBR_PROPERTIES_URL = f"{CBR_API_BASE}/properties"
CBR_AGENTS_URL = f"{CBR_API_BASE}/agents"
CBR_MEDIA_URL = f"{CBR_API_BASE}/media"
CBR_PER_PAGE = 100

CBR_SESSION = None

def get_cbr_session():
    """Get or create a shared requests.Session for Camara Bienes Raices."""
    global CBR_SESSION
    if CBR_SESSION is None:
        CBR_SESSION = requests.Session()
        CBR_SESSION.headers.update({
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "es-SV,es;q=0.9,en;q=0.8",
        })
    return CBR_SESSION

# ============== REALTY EL SALVADOR CONFIG ==============
REALTYELSALVADOR_SOURCE = "RealtyElSalvador"
REALTYELSALVADOR_BASE_URL = "https://realtyelsalvador.com"
REALTYELSALVADOR_API_BASE = f"{REALTYELSALVADOR_BASE_URL}/wp-json/wp/v2"
REALTYELSALVADOR_PROPERTIES_URL = f"{REALTYELSALVADOR_API_BASE}/propiedades"
REALTYELSALVADOR_PROPERTY_TYPE_URL = f"{REALTYELSALVADOR_API_BASE}/tipo-de-propiedad"
REALTYELSALVADOR_PROPERTY_STATUS_URL = f"{REALTYELSALVADOR_API_BASE}/estado-de-propiedad"
REALTYELSALVADOR_PER_PAGE = 100

REALTYELSALVADOR_SESSION = None
REALTYELSALVADOR_AVAILABLE_STATUS_ID = None


def get_realtyelsalvador_session():
    """Get or create a shared requests.Session for Realty El Salvador."""
    global REALTYELSALVADOR_SESSION
    if REALTYELSALVADOR_SESSION is None:
        REALTYELSALVADOR_SESSION = requests.Session()
        REALTYELSALVADOR_SESSION.headers.update({
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "es-SV,es;q=0.9,en;q=0.8",
            "Referer": f"{REALTYELSALVADOR_BASE_URL}/",
            "Origin": REALTYELSALVADOR_BASE_URL,
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "DNT": "1",
        })
    return REALTYELSALVADOR_SESSION


# ============== CASAS AHORITA CONFIG ==============
CASASAHORITA_SOURCE = "CasasAhorita"
CASASAHORITA_BASE_URL = "https://casasahorita.com"
CASASAHORITA_SEARCH_URL = f"{CASASAHORITA_BASE_URL}/buscar/sv"
CASASAHORITA_FALLBACK_SEARCH_URL = f"{CASASAHORITA_BASE_URL}/pages/search"

CASASAHORITA_SESSION = None


def get_casasahorita_session():
    """Get or create a shared requests.Session for Casas Ahorita."""
    global CASASAHORITA_SESSION
    if CASASAHORITA_SESSION is None:
        CASASAHORITA_SESSION = requests.Session()
        CASASAHORITA_SESSION.headers.update({
            "User-Agent": HEADERS["User-Agent"],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-SV,es;q=0.9,en;q=0.8",
        })
    return CASASAHORITA_SESSION

# ============== VIVOLATAM CONFIG ==============
VIVOLATAM_BASE_URL = "https://www.vivolatam.com"
VIVOLATAM_LISTINGS_URL = "https://www.vivolatam.com/es/el-salvador/bienes-raices/m"
VIVOLATAM_CDN = "https://cdn.vivolatam.com"

# ============== PROPILATAM CONFIG ==============
PROPILATAM_BASE_URL = "https://www.propilatam.com"
PROPILATAM_LISTINGS_URL = "https://www.propilatam.com/sv"
PROPILATAM_SITEMAP_URL = "https://www.propilatam.com/sitemap.xml"
PROPILATAM_ASSETS_CDN = "https://storage.googleapis.com/assets-us-east4-propilatam"

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
    import re
    
    def has_word_match(pattern, text):
        """Check if pattern exists as a complete word in text using word boundaries."""
        if not pattern or not text:
            return False
        # Use word boundaries to prevent partial matches (e.g., "colon" in "colonia")
        regex = r'\b' + re.escape(pattern) + r'\b'
        return bool(re.search(regex, text, re.IGNORECASE))
    
    # Combine all texts for alias searching
    combined_text = f"{title or ''} {location or ''} {description or ''}"
    combined_normalized = normalize_text(combined_text)
    
    # First, check aliases (most specific matches) - sorted by length (longer first)
    sorted_aliases = sorted(MUNICIPIO_ALIASES.items(), key=lambda x: len(x[0]), reverse=True)
    for alias, municipio in sorted_aliases:
        if has_word_match(alias, combined_text) or has_word_match(normalize_text(alias), combined_normalized):
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
        
        if has_word_match(muni_lower, (title or "").lower()) or has_word_match(muni_normalized, title_normalized):
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
        
        if has_word_match(muni_lower, (location or "").lower()) or has_word_match(muni_normalized, location_normalized):
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
        
        if has_word_match(muni_lower, (description or "").lower()) or has_word_match(muni_normalized, desc_normalized):
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
        if is_probable_bot_block_page(resp.text, soup=soup):
            print(f"    Warning: probable anti-bot challenge on listing page {url}")
            return []

        page_path = urlparse(url).path
        page_path = re.sub(r"\.\d+$", "", page_path).rstrip("/")
        urls = []
        seen = set()
        for link in soup.select("a[href]"):
            href = normalize_source_text(link.get("href"))
            if not href:
                continue

            absolute_url = make_absolute_url(href)
            href_path = urlparse(absolute_url).path.rstrip("/")
            if not href_path.startswith(page_path + "/"):
                continue

            if not re.search(r"/\d+$", href_path):
                continue

            clean_url = absolute_url.split("?", 1)[0]
            if clean_url not in seen:
                seen.add(clean_url)
                urls.append(clean_url)
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

        if is_probable_bot_block_page(resp.text, soup=soup):
            print(f"  Warning: probable anti-bot challenge for {url}")
            return None
        
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

        # Price - extract from multiple sources and use the most complete one
        price = ""
        price_candidates = []
        meta_title = extract_meta_content(resp.text, "og:title") or extract_meta_content(resp.text, "title")
        
        # Source 1: Price element on page
        price_el = soup.select_one(".estate-price") or soup.select_one(".d3-price")
        if price_el:
            el_price = price_el.get_text(strip=True)
            if el_price:
                price_candidates.append(el_price)
        
        # Source 2: Look for price in title (common pattern: "por XXXXX.00")
        title_price_match = re.search(
            r'por\s+(?:USD\s+|US\$\s*|\$\s*)?([\d,.]+(?:\s*(?:[kKmM]\b|mil(?:lones?)?\b|millones?\b))?)',
            title,
            re.IGNORECASE,
        )
        if title_price_match:
            price_candidates.append(f"${title_price_match.group(1)}")
        
        # Source 3: Look for $ price in title
        title_dollar_match = re.search(r'\$\s*([\d,.]+(?:\s*(?:[kKmM]\b|mil(?:lones?)?\b|millones?\b))?)', title)
        if title_dollar_match:
            price_candidates.append(f"${title_dollar_match.group(1)}")

        # Source 4: Price in SEO metadata (common on newer Encuentra24 pages)
        if meta_title:
            meta_price_match = re.search(
                r'por\s+(?:USD\s+|US\$\s*|\$\s*)?([\d,.]+(?:\s*(?:[kKmM]\b|mil(?:lones?)?\b|millones?\b))?)',
                meta_title,
                re.IGNORECASE,
            )
            if meta_price_match:
                meta_candidate = f"${meta_price_match.group(1)}"
                if (parse_price(meta_candidate) or 0) > 0:
                    price_candidates.append(meta_candidate)

            meta_dollar_match = re.search(r'\$\s*([\d,.]+(?:\s*(?:[kKmM]\b|mil(?:lones?)?\b|millones?\b))?)', meta_title)
            if meta_dollar_match:
                meta_candidate = f"${meta_dollar_match.group(1)}"
                if (parse_price(meta_candidate) or 0) > 0:
                    price_candidates.append(meta_candidate)

        # Source 5: Fallback - search explicit "Precio" labels only.
        # Avoid grabbing revenue mentions such as "$7,200 mensuales" from the
        # description body, which can appear before the asking price in page text.
        if not price_candidates:
            page_text = normalize_source_text(soup.get_text(" ", strip=True))
            page_match = re.search(
                r"\bprecio\b\s*:?\s*\$\s*([\d,.]+(?:\s*(?:[kKmM]\b|mil(?:lones?)?\b|millones?\b))?)",
                page_text,
                re.IGNORECASE,
            )
            if page_match:
                price_candidates.append(f"${page_match.group(1)}")
        
        # Choose the largest price (to get full price, not truncated display)
        best_price = 0
        for candidate in price_candidates:
            parsed = parse_price(candidate)
            if parsed and parsed > best_price:
                best_price = parsed
                price = candidate
        
        # If no named price found, use empty
        if not price and price_candidates:
            fallback_candidate = price_candidates[0]
            if (parse_price(fallback_candidate) or 0) > 0:
                price = fallback_candidate

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
                elif "parqueo" in label_lower or "parking" in label_lower or "estacionamiento" in label_lower or "garaje" in label_lower:
                    specs["parking"] = value
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
        
        # Fallback: Extract published_date from raw HTML using regex if not found via CSS selectors
        if not published_date:
            # Look for date in HTML tags like >01/08/2025<
            date_match = re.search(r'>(\d{2}/\d{2}/\d{4})<', str(resp.text))
            if date_match:
                published_date = date_match.group(1)
        
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
        image_pattern = re.compile(rf'{external_id}_([a-z0-9]+(?:-[a-z0-9]+)*)')
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



        # Extract coordinates from Google Maps embed URL
        # Pattern: google.com/maps/embed/v1/place?key=...&q=LAT,LNG&zoom=...
        latitude = None
        longitude = None
        coord_match = re.search(r'google\.com/maps/embed/v1/place\?[^"]*?q=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)', str(resp.text))
        if coord_match:
            try:
                latitude = float(coord_match.group(1))
                longitude = float(coord_match.group(2))
            except (ValueError, TypeError):
                pass

        if not price or not location or not specs or latitude is None or longitude is None:
            fallback = extract_encuentra24_embedded_fallback(resp.text, url)

            if not price:
                price = fallback.get("price", "") or price
            if not location:
                location = fallback.get("location", "") or location
            if not description:
                description = fallback.get("description", "") or description
            if fallback.get("specs"):
                merged_specs = dict(fallback["specs"])
                for key, value in specs.items():
                    if value not in ("", None, [], {}):
                        merged_specs[key] = value
                specs = merged_specs or specs

            if fallback.get("details"):
                merged_details = dict(fallback["details"])
                merged_details.update(details)
                details = merged_details

            if latitude is None and fallback.get("latitude") is not None:
                latitude = fallback["latitude"]
            if longitude is None and fallback.get("longitude") is not None:
                longitude = fallback["longitude"]

        if (
            not price
            or not location
            or not specs
            or not details
            or not description
            or is_suspicious_encuentra24_location_fragment(location)
        ):
            rendered_fallback = extract_encuentra24_rendered_fallback(resp.text, url)

            if not price:
                price = rendered_fallback.get("price", "") or price
            rendered_location = rendered_fallback.get("location", "")
            if rendered_location and should_prefer_rendered_encuentra24_location(location, rendered_location, title=title, url=url):
                location = rendered_location
                if rendered_fallback.get("details", {}).get("Ubicación"):
                    details["Ubicación"] = rendered_fallback["details"]["Ubicación"]
            elif not location:
                location = rendered_fallback.get("location", "") or location
            if not published_date:
                published_date = rendered_fallback.get("published_date", "") or published_date
            if not description:
                description = rendered_fallback.get("description", "") or description

            if rendered_fallback.get("specs"):
                merged_specs = dict(rendered_fallback["specs"])
                for key, value in specs.items():
                    if value not in ("", None, [], {}):
                        merged_specs[key] = value
                specs = merged_specs or specs

            if rendered_fallback.get("details"):
                merged_details = dict(rendered_fallback["details"])
                merged_details.update(details)
                details = merged_details

        # Correct listing_type based on content analysis (title, description, price)
        # Users sometimes list sale properties in the rent section and vice versa
        price_value = parse_price(price)
        listing_type = correct_listing_type(listing_type, title, description, price_value, url=url)

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
            "specs": normalize_listing_specs(specs),  # Normalize specs (area, beds, baths, etc.)
            "details": details,
            "description": description,
            "images": images,
            "source": "Encuentra24",
            "active": True,
            "municipio_detectado": municipio_info["municipio_detectado"],
            "departamento": municipio_info["departamento"],
            "latitude": latitude,
            "longitude": longitude,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        return None


def scrape_listings_concurrent(urls, listing_type, max_workers=10, max_days=None):
    """Scrape multiple listings concurrently with optional date filtering.
    
    Args:
        urls: List of listing URLs to scrape
        listing_type: 'sale' or 'rent'
        max_workers: Number of concurrent workers
        max_days: Maximum age of listings in days. None or 0 = no filtering.
        
    Returns:
        Tuple of (results, old_listing_count) - results is list of scraped listings,
        old_listing_count is number of listings skipped due to age
    """
    results = []
    total = len(urls)
    completed = 0
    old_listing_count = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_listing, url, listing_type): url for url in urls}
        for future in as_completed(futures):
            completed += 1
            data = future.result()
            if data and data.get("title"):
                # Check date if filtering is enabled
                if max_days and max_days > 0:
                    published_date = data.get("published_date") or data.get("details", {}).get("Publicado")
                    is_within_range, _ = is_listing_within_date_range(published_date, max_days)
                    if not is_within_range:
                        old_listing_count += 1
                        continue  # Skip old listings
                results.append(data)
            if completed % 50 == 0 or completed == total:
                if max_days and max_days > 0:
                    print(f"    Scraped {completed}/{total} ({len(results)} recent, {old_listing_count} old skipped)")
                else:
                    print(f"    Scraped {completed}/{total} ({len(results)} with data)")
    
    return results, old_listing_count


# ============== MICASASV FUNCTIONS ==============

def slug_to_external_id(slug):
    """Convert a URL slug to a numeric external_id using hash."""
    # Use first 15 digits of MD5 hash to create a unique bigint
    hash_hex = hashlib.md5(slug.encode()).hexdigest()
    # Take first 15 hex chars and convert to int (fits in bigint)
    return int(hash_hex[:15], 16)


# ============== NEXO FUNCTIONS ==============

def normalize_nexo_text(text):
    """Normalize text extracted from Nexo pages."""
    if text is None:
        return ""

    cleaned = str(text)
    if any(marker in cleaned for marker in ("\u00c3", "\u00c2", "\u00e2")):
        try:
            repaired = cleaned.encode("latin-1").decode("utf-8")
            if repaired:
                cleaned = repaired
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

    cleaned = remove_emojis(cleaned).replace("\xa0", " ").replace("\r", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def normalize_nexo_key(text):
    """Normalize a Nexo label for matching without accents or punctuation."""
    normalized = normalize_nexo_text(text).lower()
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalized.strip()


def is_nexo_error_page(raw_html, soup=None):
    """Return True when a Nexo page is a ColdFusion error page or equivalent."""
    html_lower = (raw_html or "").lower()
    if any(marker in html_lower for marker in NEXO_ERROR_MARKERS):
        return True

    if soup is None:
        soup = BeautifulSoup(raw_html or "", "html.parser")

    title_text = normalize_nexo_text(soup.title.get_text(" ", strip=True) if soup.title else "").lower()
    if "error occurred while processing request" in title_text:
        return True

    return False


def nexo_extract_value_text(node):
    """Extract a list item value while ignoring the bold label span."""
    if node is None:
        return ""

    parts = []
    for child in node.contents:
        if getattr(child, "name", None) == "span":
            classes = child.get("class", []) or []
            if "bold" in classes:
                continue
        if isinstance(child, str):
            parts.append(child)
        else:
            parts.append(child.get_text(" ", strip=True))

    return normalize_nexo_text(" ".join(parts))


def nexo_extract_first_number(text):
    """Extract the first numeric token from a text fragment."""
    match = re.search(r"(\d+(?:[.,]\d+)?)", normalize_nexo_text(text))
    return match.group(1) if match else ""


def nexo_normalize_area_value(text):
    """Normalize Nexo area units to formats understood by area_normalizer."""
    value = normalize_nexo_text(text)
    value = re.sub(r"\bvrs(?:2)?\b", "v2", value, flags=re.IGNORECASE)
    return value


def get_nexo_listing_urls(max_listings=None):
    """Collect Nexo listing detail URLs from the public paginated category pages."""
    all_urls = []
    seen = set()

    for category in NEXO_CATEGORIES:
        page = 1
        print(f"  Fetching Nexo category: {category['name']}")

        while True:
            page_url = category["url"].format(page)

            try:
                resp = requests.get(page_url, headers=HEADERS, timeout=15)
            except Exception as e:
                print(f"    Error fetching {page_url}: {e}")
                break

            if resp.status_code != 200:
                print(f"    Stopping {category['name']}: HTTP {resp.status_code}")
                break

            resp.encoding = "iso-8859-1"
            soup = BeautifulSoup(resp.text, "html.parser")
            visible_text = soup.get_text(" ", strip=True)

            if is_nexo_error_page(resp.text, soup=soup):
                print(f"    Stopping {category['name']}: error page at page {page}")
                break

            detail_links = []
            for anchor in soup.select(".resultados .dresultado a[itemprop='url'], .resultados .dresultado a[href]"):
                href = (anchor.get("href") or "").strip()
                if not href or "ver detalles" not in normalize_nexo_text(anchor.get_text(" ", strip=True)).lower():
                    continue
                detail_links.append(urljoin(page_url, href))

            if not detail_links or re.search(r"Existen\s+0\b", visible_text, re.IGNORECASE):
                print(f"    Page {page}: no listings")
                break

            new_on_page = 0
            for detail_url in detail_links:
                if detail_url in seen:
                    continue
                seen.add(detail_url)
                all_urls.append(detail_url)
                new_on_page += 1

                if max_listings and len(all_urls) >= max_listings:
                    print(f"    Reached limit of {max_listings} Nexo listings")
                    return all_urls[:max_listings]

            print(f"    Page {page}: found {new_on_page} new listings (total {len(all_urls)})")
            page += 1

    return all_urls


def scrape_nexo_listing(url, listing_type="auto"):
    """Scrape a single Nexo listing page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
    except Exception:
        return None

    if resp.status_code != 200:
        return None

    resp.encoding = "iso-8859-1"
    raw_html = resp.text
    soup = BeautifulSoup(raw_html, "html.parser")

    if is_nexo_error_page(raw_html, soup=soup):
        return None

    title_el = soup.select_one("article.titulo [itemprop='name']") or soup.select_one("article.titulo h1")
    title = normalize_nexo_text(title_el.get_text(" ", strip=True) if title_el else "")
    if not title:
        return None

    description_el = soup.select_one("article.descripcion [itemprop='description']") or soup.select_one("article.descripcion p")
    description = normalize_nexo_text(description_el.get_text(" ", strip=True) if description_el else "")

    price_el = soup.select_one("[itemprop='price']")
    price = normalize_nexo_text(price_el.get_text(" ", strip=True) if price_el else "")

    id_inmueble_el = soup.select_one("input[name='id_inmueble']")
    type_code_el = soup.select_one("input[name='cod_tipo_inmueble']")
    product_code_el = soup.select_one("input[name='cod_inmueble']") or soup.select_one("[itemprop='productID']")
    id_inmueble = normalize_nexo_text(id_inmueble_el.get("value", "") if id_inmueble_el else "")
    type_code = normalize_nexo_text(type_code_el.get("value", "") if type_code_el else "")
    product_code = normalize_nexo_text(
        product_code_el.get("value", "") if product_code_el and product_code_el.name == "input"
        else product_code_el.get_text(" ", strip=True) if product_code_el
        else ""
    )

    if product_code:
        external_id = slug_to_external_id(f"nexo:{product_code}")
    else:
        url_path = urlparse(resp.url).path.rstrip("/")
        external_id = slug_to_external_id(f"nexo:{type_code}:{id_inmueble}:{url_path}")

    href_type = (soup.select_one("link[itemprop='additionalType']") or {}).get("href", "").lower()
    property_type = NEXO_PROPERTY_TYPE_BY_CODE.get(type_code, "")
    if not property_type:
        if "apartment" in href_type:
            property_type = "apartment"
        elif "house" in href_type:
            property_type = "house"
        elif "land" in href_type or "lot" in href_type:
            property_type = "land"

    if listing_type == "auto":
        listing_type = NEXO_LISTING_TYPE_BY_CODE.get(type_code, "sale")

    departamento = normalize_nexo_text((soup.select_one("[itemprop='addressRegion']") or {}).get_text(" ", strip=True) if soup.select_one("[itemprop='addressRegion']") else "")
    municipio = normalize_nexo_text((soup.select_one("[itemprop='addressLocality']") or {}).get_text(" ", strip=True) if soup.select_one("[itemprop='addressLocality']") else "")
    zona = normalize_nexo_text((soup.select_one("[itemprop='streetAddress']") or {}).get_text(" ", strip=True) if soup.select_one("[itemprop='streetAddress']") else "")
    location_text = ", ".join(part for part in [zona, municipio, departamento] if part)

    details = {}
    specs = {}

    if property_type:
        details["property_type"] = property_type
    if product_code:
        details["product_code"] = product_code

    location_article = soup.select_one(".caracteristicas article.caracteristicas2[itemprop='offers']")
    if location_article:
        for paragraph in location_article.select("p"):
            text = normalize_nexo_text(paragraph.get_text(" ", strip=True))
            if not text:
                continue

            p_classes = set(paragraph.get("class", []) or [])
            text_key = normalize_nexo_key(text)

            if "cuarto2" in p_classes or "habitacion" in text_key:
                value = nexo_extract_first_number(text) or text
                specs["bedrooms"] = value
                continue
            if "bano2" in p_classes or "bano" in text_key:
                value = nexo_extract_first_number(text) or text
                specs["bathrooms"] = value
                continue
            if "cochera2" in p_classes or "vehiculo" in text_key or "parqueo" in text_key:
                value = nexo_extract_first_number(text) or text
                specs["parking"] = value
                continue
            if "piso2" in p_classes or "planta" in text_key:
                value = nexo_extract_first_number(text) or text
                specs["floors"] = value
                continue
            if "nivel" in text_key:
                value = nexo_extract_first_number(text) or text
                specs["level"] = value

    detail_articles = soup.select(".caracteristicas article.caracteristicas2:not([itemprop='offers'])")
    for article in detail_articles:
        for item in article.select("li"):
            label_el = item.select_one("span.bold")
            label = normalize_nexo_text(label_el.get_text(" ", strip=True)).rstrip(":") if label_el else ""
            value = nexo_extract_value_text(item)
            if not label or not value:
                continue

            details[label] = value
            label_key = normalize_nexo_key(label)

            if "habitacion" in label_key:
                specs["bedrooms"] = nexo_extract_first_number(value) or value
            elif "bano" in label_key:
                specs["bathrooms"] = nexo_extract_first_number(value) or value
            elif "vehiculo" in label_key or "parqueo" in label_key or "cochera" in label_key:
                specs["parking"] = nexo_extract_first_number(value) or value
            elif "tamano del terreno" in label_key or "area del terreno" in label_key or "tamano terreno" in label_key:
                area_value = nexo_normalize_area_value(value)
                specs[label] = area_value
                specs["lot_area"] = area_value
            elif "tamano construccion" in label_key or "tamano de construccion" in label_key or "area del apartamento" in label_key or "area construida" in label_key:
                area_value = nexo_normalize_area_value(value)
                specs[label] = area_value
                specs["area"] = area_value
            elif "planta" in label_key:
                specs["floors"] = nexo_extract_first_number(value) or value
            elif "nivel" in label_key:
                specs["level"] = nexo_extract_first_number(value) or value

    listing_type = correct_listing_type(listing_type, title, description, parse_price(price), url=resp.url)

    municipio_info = detect_municipio(location_text, description, title)
    municipio_detectado = municipio or municipio_info.get("municipio_detectado") or "No identificado"
    departamento_final = departamento or municipio_info.get("departamento") or ""

    location_data = {
        "direccion": zona,
        "zona": zona,
        "municipio": municipio,
        "municipio_detectado": municipio_detectado,
        "departamento": departamento_final,
    }

    images = []
    main_image = soup.select_one(".imgprincipal img")
    if main_image and main_image.get("src"):
        images.append(urljoin(resp.url, main_image.get("src").strip()))

    for anchor in soup.select(".gallery a[href]"):
        image_url = urljoin(resp.url, anchor.get("href", "").strip())
        if image_url and image_url not in images:
            images.append(image_url)

    og_image = soup.select_one("meta[property='og:image']")
    if og_image and og_image.get("content"):
        og_url = urljoin(resp.url, og_image.get("content").strip())
        if og_url and og_url not in images:
            images.insert(0, og_url)

    return {
        "title": title,
        "price": price,
        "location": location_data,
        "published_date": None,
        "listing_type": listing_type,
        "url": resp.url,
        "external_id": external_id,
        "specs": normalize_listing_specs(specs),
        "details": details,
        "description": description,
        "images": images,
        "source": NEXO_SOURCE,
        "active": True,
        "municipio_detectado": municipio_detectado,
        "departamento": departamento_final,
        "latitude": None,
        "longitude": None,
        "last_updated": datetime.now().isoformat()
    }


def scrape_nexo_listings_concurrent(urls, listing_type="auto", max_workers=4):
    """Scrape multiple Nexo listings concurrently."""
    results = []
    total = len(urls)
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_nexo_listing, url, listing_type): url for url in urls}
        for future in as_completed(futures):
            completed += 1
            data = future.result()
            if data and data.get("title"):
                results.append(data)

            if completed % 25 == 0 or completed == total:
                print(f"    Scraped {completed}/{total} ({len(results)} with data)")

    return results, 0


def main_nexo(limit=None, max_days=None):
    """Main scraper function for Nexo."""
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} total listings from Nexo ***")
    if max_days and max_days > 0:
        print("*** DATE FILTER requested, but Nexo does not expose a reliable published date. Scraping all live listings. ***")

    urls = get_nexo_listing_urls(max_listings=limit)
    if not urls:
        print("  No Nexo URLs found to scrape")
        return [], [], []

    print(f"Found {len(urls)} Nexo URLs. Scraping details...")
    all_listings, _ = scrape_nexo_listings_concurrent(urls, "auto", max_workers=4)

    sale_data = [listing for listing in all_listings if listing.get("listing_type") == "sale"]
    rent_data = [listing for listing in all_listings if listing.get("listing_type") == "rent"]

    print(f"  Nexo total: {len(all_listings)} ({len(sale_data)} sales, {len(rent_data)} rentals)")
    return all_listings, sale_data, rent_data


def is_service_listing(listing_data):
    """
    Check if a MiCasaSV listing is a service ad (not a real estate property).
    
    Service listings typically have:
    - Service-related categories (electricista, limpieza, fontanero, etc.)
    - Service-related title keywords
    - No price
    - Empty specs
    
    Returns True if listing should be EXCLUDED (is a service).
    """
    if not listing_data:
        return True
    
    # Service category keywords
    SERVICE_CATEGORIES = [
        'servicio de limpieza', 'limpieza de piscinas', 'limpieza de ventanas',
        'electricista', 'fontanero', 'plomero', 'carpintero', 'pintor',
        'aire acondicionado', 'climatización', 'mantenimiento',
        'jardinería', 'jardinero', 'mudanza', 'transporte',
        'remodelación', 'remodelacion', 'construcción', 'construccion',
        'diseño web', 'diseno web', 'marketing', 'publicidad',
        'abogado', 'contador', 'asesor', 'consultor',
        'seguridad', 'vigilancia', 'cerrajero',
        'fumigación', 'fumigacion', 'control de plagas',
        'reparación', 'reparacion', 'técnico', 'tecnico',
    ]
    
    # Service title keywords
    SERVICE_TITLE_KEYWORDS = [
        'servicio de', 'servicios de', 'mantenimiento de', 'reparación de',
        'limpieza de', 'instalación de', 'instalacion de',
        'fontanero', 'electricista', 'plomero', 'carpintero',
        'se busca', 'plaza disponible', 'vacante', 'empleo',
        'trabajo de', 'ofrecemos', 'ofrezco',
    ]
    
    # Check categories
    categorias = listing_data.get('details', {}).get('categorias', '').lower()
    for service_cat in SERVICE_CATEGORIES:
        if service_cat in categorias:
            return True  # Is a service listing
    
    # Check title
    title = (listing_data.get('title', '') or '').lower()
    for keyword in SERVICE_TITLE_KEYWORDS:
        if keyword in title:
            return True  # Is a service listing
    
    # Additional heuristic: No price AND empty specs AND empty departamento
    # These are strong indicators of non-property listings
    price = listing_data.get('price')
    specs = listing_data.get('specs', {})
    departamento = listing_data.get('departamento', '')
    
    has_no_price = not price or price == ''
    has_empty_specs = not specs or len(specs) == 0
    has_no_location = not departamento or departamento == ''
    
    # If all three conditions are true, likely a service listing
    if has_no_price and has_empty_specs and has_no_location:
        # Extra check: does title contain any property-related words?
        property_keywords = ['casa', 'apartamento', 'terreno', 'local', 'bodega', 
                           'oficina', 'venta', 'alquiler', 'habitacion', 'cuarto']
        title_lower = title.lower()
        has_property_keyword = any(kw in title_lower for kw in property_keywords)
        if not has_property_keyword:
            return True  # Likely a service listing
    
    return False  # Is a valid property listing

def get_micasasv_listing_urls(base_url, max_listings=None):
    """Collect listing URLs from MiCasaSV sitemap.
    
    Note: MiCasaSV explore page loads content dynamically with JavaScript,
    so we use the WordPress sitemap instead which lists all listings.
    """
    all_urls = []
    
    # Blacklist: URLs that are not actual property listings (ads, services, etc.)
    BLACKLIST_PATTERNS = [
        'sitios-web-inmobiliarios',  # Service ad
        'diseno-web',
        'marketing',
        'publicidad',
        'servicios',
        'contacto',
        'nosotros',
        'about',
        'terms',
        'privacy',
    ]
    
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
            # Skip blacklisted URLs (non-property content)
            url_lower = url.lower()
            is_blacklisted = any(pattern in url_lower for pattern in BLACKLIST_PATTERNS)
            
            if is_blacklisted:
                continue
                
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
            label_el = item.select_one(".item-label") or item.select_one(".item-attr")
            value_el = item.select_one(".item-value") or item.select_one(".item-property")
            if label_el and value_el:
                label = label_el.get_text(strip=True).lower()
                value = value_el.get_text(strip=True)
                
                # Map to specs
                if "habitacion" in label or "recamara" in label or "dormitorio" in label:
                    specs["bedrooms"] = value
                elif "baño" in label:
                    specs["bathrooms"] = value
                elif "parqueo" in label or "parking" in label or "estacionamiento" in label or "garaje" in label or "aparcamiento" in label:
                    specs["parking"] = value
                elif "área" in label or "tamaño" in label or "tomaño" in label or "terreno" in label or "construcción" in label:
                    specs[label_el.get_text(strip=True)] = value
                else:
                    details[label_el.get_text(strip=True)] = value
        
        def _normalize_spec_label(text):
            if not text:
                return ""
            text = str(text).strip()
            # Repair common mojibake labels from MiCasaSV, e.g. "TamaÃ±o", "BaÃ±os".
            if "Ã" in text or "Â" in text:
                try:
                    text = text.encode("latin-1").decode("utf-8")
                except (UnicodeEncodeError, UnicodeDecodeError):
                    pass
            text = unicodedata.normalize("NFKD", text.lower())
            return "".join(ch for ch in text if not unicodedata.combining(ch))

        # Fallback pass for MiCasaSV "Detalles" rows rendered without .item-label/.item-value
        # (e.g. "Tamaño 110 m²"), which otherwise causes the generic quick-spec area to win.
        for item in soup.select(".details-list li"):
            if item.select_one(".item-label") and item.select_one(".item-value"):
                continue

            parts = [s.strip() for s in item.stripped_strings if s and s.strip()]
            if len(parts) < 2:
                continue

            label_text = parts[0]
            value = parts[-1]
            if not label_text or not value or label_text == value:
                continue

            label_norm = _normalize_spec_label(label_text)

            if "habitacion" in label_norm or "recamara" in label_norm or "dormitorio" in label_norm:
                specs.setdefault("bedrooms", value)
            elif "bano" in label_norm or "bath" in label_norm:
                specs.setdefault("bathrooms", value)
            elif any(tok in label_norm for tok in ["parqueo", "parking", "estacionamiento", "garaje", "aparcamiento"]):
                specs.setdefault("parking", value)
            elif any(tok in label_norm for tok in ["area", "tamano", "tomano", "terreno", "construccion", "superficie", "lote"]):
                specs.setdefault(label_text, value)
            else:
                details.setdefault(label_text, value)

        # Also check for quick specs in card format
        # MiCasaSV sometimes shows a generic icon "area" value (often lot area)
        # that conflicts with the detailed table "Tamaño"/"Construcción" value.
        # Keep the detailed table area when present.
        has_detailed_area_spec = any(
            any(token in _normalize_spec_label(k) for token in ["tama", "toma", "area", "constru", "superficie", "terreno", "lote"])
            for k in specs.keys()
        )
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
                elif any("car" in c or "parking" in c or "garage" in c for c in icon_class):
                    specs["parking"] = value
                elif any("box" in c or "area" in c for c in icon_class):
                    if not has_detailed_area_spec and "area" not in specs:
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
        
        # Extract coordinates from marker_lat/marker_lng in HTML or ld+json GeoCoordinates
        latitude = None
        longitude = None
        raw_html = resp.text
        # Pattern 1: marker_lat/marker_lng in HTML-encoded JSON
        marker_lat = re.search(r'marker_lat[&quot;:"\s]+(-?\d{1,3}\.\d+)', raw_html)
        marker_lng = re.search(r'marker_lng[&quot;:"\s]+(-?\d{1,3}\.\d+)', raw_html)
        if marker_lat and marker_lng:
            try:
                latitude = float(marker_lat.group(1))
                longitude = float(marker_lng.group(1))
            except (ValueError, TypeError):
                pass
        # Pattern 2: ld+json GeoCoordinates fallback
        if latitude is None:
            geo_lat = re.search(r'"latitude"\s*:\s*"(-?\d{1,3}\.\d+)"', raw_html)
            geo_lng = re.search(r'"longitude"\s*:\s*"(-?\d{1,3}\.\d+)"', raw_html)
            if geo_lat and geo_lng:
                try:
                    latitude = float(geo_lat.group(1))
                    longitude = float(geo_lng.group(1))
                except (ValueError, TypeError):
                    pass
        
        # Correct listing_type based on content analysis (title, description, price)
        # Users sometimes list sale properties in the rent section and vice versa
        price_value = parse_price(price)
        listing_type = correct_listing_type(listing_type, title, description, price_value)
        
        # Detect municipality from location, description and title
        municipio_info = detect_municipio(location, description, title)
        
        property_tag = detect_property_subtype(title, description, details, url)
        normalized_specs = normalize_listing_specs(specs)

        # MiCasaSV land listings often expose bogus quick-spec bedroom/bathroom values.
        # Once the source category confirms this is land, avoid preserving those fields.
        if property_tag == "Terreno":
            normalized_specs.pop("bedrooms", None)
            normalized_specs.pop("bathrooms", None)
            normalized_specs.pop("parking", None)

        return {
            "title": title,
            "price": price,
            "location": location,
            "published_date": published_date,
            "listing_type": listing_type,
            "url": url,
            "external_id": str(external_id),
            "specs": normalized_specs,  # Normalize specs (area, beds, baths, etc.)
            "details": details,
            "description": description,
            "images": images,
            "source": "MiCasaSV",
            "active": True,
            "tags": [property_tag] if property_tag else [],
            "municipio_detectado": municipio_info["municipio_detectado"],
            "departamento": municipio_info["departamento"],
            "latitude": latitude,
            "longitude": longitude,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None


def scrape_micasasv_listings_concurrent(urls, listing_type, max_workers=5, max_days=None):
    """Scrape multiple MiCasaSV listings concurrently with optional date filtering.
    
    Args:
        urls: List of listing URLs
        listing_type: 'sale' or 'rent'
        max_workers: Number of concurrent workers
        max_days: Maximum age of listings in days. None or 0 = no filtering.
        
    Returns:
        Tuple of (results, old_listing_count)
    """
    results = []
    skipped_services = 0
    old_listing_count = 0
    total = len(urls)
    completed = 0
    
    # Use fewer workers for MiCasaSV to avoid rate limiting
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scrape_micasasv_listing, url, listing_type): url for url in urls}
        for future in as_completed(futures):
            completed += 1
            data = future.result()
            if data and data.get("title"):
                # Filter out service listings (not real estate)
                if is_service_listing(data):
                    skipped_services += 1
                    continue
                
                # Check date if filtering is enabled
                if max_days and max_days > 0:
                    published_date = data.get("published_date") or data.get("details", {}).get("Publicado")
                    is_within_range, _ = is_listing_within_date_range(published_date, max_days)
                    if not is_within_range:
                        old_listing_count += 1
                        continue
                        
                results.append(data)
            if completed % 20 == 0 or completed == total:
                if max_days and max_days > 0:
                    print(f"    Scraped {completed}/{total} ({len(results)} recent, {old_listing_count} old, {skipped_services} services skipped)")
                else:
                    print(f"    Scraped {completed}/{total} ({len(results)} properties, {skipped_services} services skipped)")
    
    if skipped_services > 0:
        print(f"    Filtered out {skipped_services} service listings (not real estate)")
    
    return results, old_listing_count

def get_realtor_detail_published_date(detail_url):
    """
    Fetch a single Realtor.com listing detail page and extract publishedAt
    from its __NEXT_DATA__ JSON. Used as fallback when the list-page JSON
    doesn't include the date.
    
    Args:
        detail_url: Full URL of the listing detail page
    
    Returns:
        Published date string in DD/MM/YYYY format, or empty string if not found
    """
    try:
        session = get_realtor_session()
        resp = session.get(detail_url, timeout=20)
        if resp.status_code != 200:
            return ""
        
        soup = BeautifulSoup(resp.text, "html.parser")
        next_data = soup.select_one("script#__NEXT_DATA__")
        
        if not next_data or not next_data.string:
            return ""
        
        data = json.loads(next_data.string)
        apollo_state = data.get("props", {}).get("apolloState", {})
        
        # Find the ListingDetail entry with publishedAt
        for key, value in apollo_state.items():
            if key.startswith("ListingDetail:") and isinstance(value, dict):
                published_at = value.get("publishedAt", "")
                if published_at:
                    try:
                        dt = datetime.strptime(published_at.split(" ")[0], "%Y-%m-%d")
                        return dt.strftime("%d/%m/%Y")
                    except:
                        pass
        return ""
    except Exception:
        return ""


def realtor_resolve_apollo_ref(apollo_state, ref):
    """Resolve Apollo references in Realtor __NEXT_DATA__ payloads."""
    if isinstance(ref, dict) and ref.get("id"):
        return apollo_state.get(ref["id"], ref)
    return ref


def normalize_realtor_listing_detail(apollo_state, value, detail_page_url=None):
    """Normalize one Realtor ListingDetail payload into the shared listing schema."""
    if not isinstance(value, dict):
        return None

    listing_id = value.get("id")
    if not listing_id:
        return None

    url_key = 'detailPageUrl({"language":"en"})'
    detail_url = value.get(url_key)
    if detail_url:
        full_url = detail_url if str(detail_url).startswith("http") else f"{REALTOR_BASE_URL}{detail_url}"
    else:
        full_url = detail_page_url or ""

    if not full_url:
        return None

    price_key = 'price({"currency":"USD","language":"en"})'
    price_data = realtor_resolve_apollo_ref(apollo_state, value.get(price_key))
    price_str = ""
    if isinstance(price_data, dict):
        price_str = price_data.get("displayListingPrice", "")

    location_data = realtor_resolve_apollo_ref(apollo_state, value.get("location"))
    location = ""
    if isinstance(location_data, dict):
        state = (location_data.get("state") or "").replace("-", " ").replace(" Department", "")
        location = state.strip()

    ml_key = 'multilingual({"language":"en"})'
    ml_data = realtor_resolve_apollo_ref(apollo_state, value.get(ml_key))
    title = value.get("displayAddress", "")
    if isinstance(ml_data, dict) and ml_data.get("fullAddress"):
        title = ml_data["fullAddress"]

    image_urls = []
    for photo_ref in value.get("photos", [])[:10]:
        photo_data = realtor_resolve_apollo_ref(apollo_state, photo_ref)
        if isinstance(photo_data, dict) and photo_data.get("path"):
            image_urls.append(f"{REALTOR_PHOTO_CDN}{photo_data['path']}")

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

    size_key = 'buildingSize({"language":"en","unit":"SQUARE_FEET"})'
    size_val = value.get(size_key)
    if size_val:
        try:
            sqft = float(str(size_val).replace(",", ""))
            specs["area"] = f"{round(sqft * SQFT_TO_M2, 2)} m2"
        except Exception:
            specs["area"] = str(size_val)

    land_key = 'landSize({"language":"en","unit":"SQUARE_FEET"})'
    land_val = value.get(land_key)
    if land_val:
        try:
            sqft = float(str(land_val).replace(",", ""))
            specs["terreno"] = f"{round(sqft * SQFT_TO_M2, 2)} m2"
        except Exception:
            specs["terreno"] = str(land_val)

    description = value.get("description", "")
    if description:
        description = remove_emojis(description[:1000])

    price_value = parse_price(price_str)
    listing_type = correct_listing_type("sale", title, description, price_value, url=full_url)

    prop_types_key = 'propertyTypes({"language":"en"})'
    prop_types_raw = value.get(prop_types_key, {})
    property_type = ""
    if isinstance(prop_types_raw, dict) and prop_types_raw.get("json"):
        prop_list = prop_types_raw.get("json", [])
        if isinstance(prop_list, list) and prop_list:
            property_type = prop_list[0]
    elif isinstance(prop_types_raw, list) and prop_types_raw:
        property_type = prop_types_raw[0] if isinstance(prop_types_raw[0], str) else ""

    published_date = ""
    published_at = value.get("publishedAt", "")
    if published_at:
        try:
            dt = datetime.strptime(published_at.split(" ")[0], "%Y-%m-%d")
            published_date = dt.strftime("%d/%m/%Y")
        except Exception:
            pass

    if not published_date and full_url:
        published_date = get_realtor_detail_published_date(full_url)

    details = {}
    if property_type:
        details["property_type"] = property_type
    channel = value.get("channel", "")
    if channel:
        details["channel"] = channel
    listing_category = value.get("listingCategory", "")
    if listing_category:
        details["category"] = listing_category

    latitude = None
    longitude = None
    geo_key = f"$ListingDetail:{listing_id}.geoLocation"
    geo_data = apollo_state.get(geo_key, {})
    if isinstance(geo_data, dict):
        try:
            lat_val = geo_data.get("latitude")
            lng_val = geo_data.get("longitude")
            if lat_val is not None and lng_val is not None:
                latitude = float(lat_val)
                longitude = float(lng_val)
        except (ValueError, TypeError):
            pass

    municipio_info = detect_municipio(location, description, title)
    return {
        "title": remove_emojis(title[:200]) if title else "",
        "price": price_str,
        "location": location,
        "published_date": published_date,
        "listing_type": listing_type,
        "url": full_url,
        "external_id": str(listing_id),
        "specs": normalize_listing_specs(specs),
        "details": details,
        "description": description,
        "images": image_urls,
        "source": "Realtor",
        "active": True,
        "municipio_detectado": municipio_info["municipio_detectado"],
        "departamento": municipio_info["departamento"],
        "latitude": latitude,
        "longitude": longitude,
        "last_updated": datetime.now().isoformat()
    }


def scrape_realtor_listing(detail_url, listing_type="auto"):
    """Scrape one Realtor detail URL into the shared listing schema."""
    session = get_realtor_session()
    response = session.get(detail_url, timeout=30)
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        raise RuntimeError(f"Realtor detail fetch failed ({response.status_code})")

    soup = BeautifulSoup(response.text, "html.parser")
    next_data = soup.select_one("script#__NEXT_DATA__")
    if not next_data or not next_data.string:
        raise RuntimeError("Realtor detail page missing __NEXT_DATA__")

    data = json.loads(next_data.string)
    apollo_state = data.get("props", {}).get("apolloState", {})
    target_path = urlparse(detail_url).path.rstrip("/")

    candidates = []
    matched_listing = None
    for key, value in apollo_state.items():
        if not key.startswith("ListingDetail:"):
            continue
        normalized = normalize_realtor_listing_detail(apollo_state, value, detail_page_url=detail_url)
        if not normalized:
            continue
        candidates.append(normalized)
        candidate_path = urlparse(normalized.get("url") or "").path.rstrip("/")
        if candidate_path == target_path:
            matched_listing = normalized
            break

    if not matched_listing and len(candidates) == 1:
        matched_listing = candidates[0]

    if not matched_listing:
        raise RuntimeError("Realtor detail page did not contain a matching listing")

    if listing_type in ("sale", "rent"):
        matched_listing["listing_type"] = listing_type

    return matched_listing


def get_realtor_listings_from_page(page_url):
    """
    Extract listing data directly from Realtor.com page's __NEXT_DATA__ JSON.
    Returns a list of normalized listing dictionaries.
    """
    try:
        session = get_realtor_session()
        response = session.get(page_url, timeout=30)
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
        for key, value in apollo_state.items():
            if not key.startswith("ListingDetail:"):
                continue
            normalized = normalize_realtor_listing_detail(apollo_state, value)
            if normalized:
                listings.append(normalized)
        
        return listings
        
    except Exception as e:
        import traceback
        print(f"  Error fetching {page_url}: {type(e).__name__}: {e}")
        traceback.print_exc()
        return []


def get_realtor_all_listings(base_url, max_listings=None, listing_type="sale"):
    """
    Fetch all listings from Realtor.com by paginating through pages.
    Each page contains listings embedded in __NEXT_DATA__.
    Includes retry with exponential backoff on 403 errors.
    """
    all_listings = []
    page = 1
    max_pages = 50  # Safety limit
    consecutive_failures = 0
    max_consecutive_failures = 3  # Stop after 3 consecutive failed pages
    
    while page <= max_pages:
        # Build URL with page parameter
        if "?" in base_url:
            page_url = f"{base_url}&page={page}"
        else:
            page_url = f"{base_url}?page={page}"
        
        print(f"  Fetching page {page}: {page_url}")
        
        # Retry logic with exponential backoff
        listings = None
        for attempt in range(3):
            listings = get_realtor_listings_from_page(page_url)
            if listings:
                consecutive_failures = 0
                break
            # Exponential backoff: 5s, 15s, 30s
            backoff = [5, 15, 30][attempt]
            if attempt < 2:
                print(f"    Retry {attempt + 1}/3 after {backoff}s backoff...")
                time.sleep(backoff)
        
        if not listings:
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                print(f"  Stopping: {max_consecutive_failures} consecutive page failures")
                break
            print(f"  No listings from page {page} after retries, trying next page...")
            page += 1
            time.sleep(random.uniform(3.0, 5.0))
            continue
        
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
        time.sleep(random.uniform(1.5, 3.0))  # Rate limiting with jitter
    
    return all_listings


def main_realtor(limit=None, max_days=None):
    """Main scraper function for Realtor.com International (El Salvador).
    
    Args:
        limit: Maximum number of listings to scrape
        max_days: Maximum age of listings in days. None or 0 = no filtering.
    """
    all_listings = []
    remaining_limit = limit
    sale_data = []
    rent_data = []
    total_old_skipped = 0
    
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} total listings from Realtor.com ***")
    if max_days and max_days > 0:
        print(f"*** DATE FILTER: Only listings from last {max_days} days ***")
    
    # --- SALE LISTINGS ---
    print("\n=== Scraping Realtor.com SALE Listings ===")
    sale_data = get_realtor_all_listings(REALTOR_SALE_URL, max_listings=remaining_limit, listing_type="sale")
    print(f"  Got {len(sale_data)} sale listings from list view")
    
    # Filter by date (description and published_date already extracted from list pages)
    if max_days and max_days > 0:
        filtered_sale = []
        for listing in sale_data:
            published_date = listing.get("published_date")
            is_within_range, _ = is_listing_within_date_range(published_date, max_days)
            if is_within_range:
                filtered_sale.append(listing)
            else:
                total_old_skipped += 1
        sale_data = filtered_sale
        print(f"  After date filter: {len(sale_data)} sale listings")
    
    all_listings.extend(sale_data)
    
    # Check if we need more listings
    if remaining_limit:
        remaining_limit = remaining_limit - len(sale_data)
    
    # --- RENT LISTINGS (only if limit not reached or no limit) ---
    if remaining_limit is None or remaining_limit > 0:
        print("\n=== Scraping Realtor.com RENT Listings ===")
        rent_data = get_realtor_all_listings(REALTOR_RENT_URL, max_listings=remaining_limit, listing_type="rent")
        print(f"  Got {len(rent_data)} rent listings from list view")
        
        # Filter by date (description and published_date already extracted from list pages)
        if max_days and max_days > 0:
            filtered_rent = []
            for listing in rent_data:
                published_date = listing.get("published_date")
                is_within_range, _ = is_listing_within_date_range(published_date, max_days)
                if is_within_range:
                    filtered_rent.append(listing)
                else:
                    total_old_skipped += 1
            rent_data = filtered_rent
            print(f"  After date filter: {len(rent_data)} rent listings")
        
        all_listings.extend(rent_data)
    else:
        print("\n=== Skipping RENT Listings (limit already reached) ===")
    
    if total_old_skipped > 0:
        print(f"\n  Total old listings skipped (>{max_days} days): {total_old_skipped}")
    
    return all_listings, sale_data, rent_data


def main_micasasv(limit=None, max_days=None):
    """Main scraper function for MiCasaSV.
    
    Args:
        limit: Maximum number of listings to scrape
        max_days: Maximum age of listings in days. None or 0 = no filtering.
    """
    all_listings = []
    remaining_limit = limit
    sale_data = []
    rent_data = []
    total_old_skipped = 0
    
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} total listings from MiCasaSV ***")
    if max_days and max_days > 0:
        print(f"*** DATE FILTER: Only listings from last {max_days} days ***")
    
    # --- SALE LISTINGS ---
    print("\n=== Scraping MiCasaSV SALE Listings ===")
    sale_urls = get_micasasv_listing_urls(MICASASV_SALE_URL, max_listings=remaining_limit)
    print(f"Found {len(sale_urls)} sale URLs. Scraping details...")
    sale_data, old_count = scrape_micasasv_listings_concurrent(sale_urls, "sale", max_days=max_days)
    all_listings.extend(sale_data)
    total_old_skipped += old_count
    print(f"  Got {len(sale_data)} sale listings" + (f" ({old_count} old skipped)" if old_count else ""))
    
    # Check if we need more listings
    if remaining_limit:
        remaining_limit = remaining_limit - len(sale_data)

    # --- RENT LISTINGS (only if limit not reached or no limit) ---
    if remaining_limit is None or remaining_limit > 0:
        print("\n=== Scraping MiCasaSV RENT Listings ===")
        rent_urls = get_micasasv_listing_urls(MICASASV_RENT_URL, max_listings=remaining_limit)
        print(f"Found {len(rent_urls)} rent URLs. Scraping details...")
        rent_data, old_count = scrape_micasasv_listings_concurrent(rent_urls, "rent", max_days=max_days)
        all_listings.extend(rent_data)
        total_old_skipped += old_count
        print(f"  Got {len(rent_data)} rent listings" + (f" ({old_count} old skipped)" if old_count else ""))
    else:
        print("\n=== Skipping RENT Listings (limit already reached) ===")

    if total_old_skipped > 0:
        print(f"\n  Total old listings skipped (>{max_days} days): {total_old_skipped}")

    return all_listings, sale_data, rent_data


def main_encuentra24(limit=None, max_days=None):
    """Main scraper function for Encuentra24.
    
    Args:
        limit: Maximum number of listings to scrape
        max_days: Maximum age of listings in days. None or 0 = no filtering.
    """
    all_listings = []
    remaining_limit = limit
    sale_data = []
    rent_data = []
    total_old_skipped = 0
    
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} total listings from Encuentra24 ***")
    if max_days and max_days > 0:
        print(f"*** DATE FILTER: Only listings from last {max_days} days ***")
    
    # --- SALE LISTINGS ---
    print("\n=== Scraping Encuentra24 SALE Listings ===")
    sale_urls = get_listing_urls_fast(SALE_URL, max_listings=remaining_limit)
    print(f"Found {len(sale_urls)} sale URLs. Scraping details concurrently...")
    sale_data, old_count = scrape_listings_concurrent(sale_urls, "sale", max_days=max_days)
    all_listings.extend(sale_data)
    total_old_skipped += old_count
    print(f"  Got {len(sale_data)} sale listings" + (f" ({old_count} old skipped)" if old_count else ""))
    
    # Check if we need more listings
    if remaining_limit:
        remaining_limit = remaining_limit - len(sale_data)

    # --- RENT LISTINGS (only if limit not reached or no limit) ---
    if remaining_limit is None or remaining_limit > 0:
        print("\n=== Scraping Encuentra24 RENT Listings ===")
        rent_urls = get_listing_urls_fast(RENT_URL, max_listings=remaining_limit)
        print(f"Found {len(rent_urls)} rent URLs. Scraping details concurrently...")
        rent_data, old_count = scrape_listings_concurrent(rent_urls, "rent", max_days=max_days)
        all_listings.extend(rent_data)
        total_old_skipped += old_count
        print(f"  Got {len(rent_data)} rent listings" + (f" ({old_count} old skipped)" if old_count else ""))
    else:
        print("\n=== Skipping RENT Listings (limit already reached) ===")

    if total_old_skipped > 0:
        print(f"\n  Total old listings skipped (>{max_days} days): {total_old_skipped}")

    return all_listings, sale_data, rent_data


# ============== CAMARA BIENES RAICES FUNCTIONS ==============

def cbr_get_meta_list(meta, key):
    """Return a clean list of non-empty meta values for a property/agent payload."""
    if not isinstance(meta, dict):
        return []

    raw_value = meta.get(key)
    if raw_value is None:
        return []

    if isinstance(raw_value, list):
        values = []
        for item in raw_value:
            item_str = str(item).strip()
            if item_str:
                values.append(item_str)
        return values

    raw_str = str(raw_value).strip()
    return [raw_str] if raw_str else []


def cbr_get_meta_value(meta, key, default=""):
    """Return the first non-empty meta value for a property/agent payload."""
    values = cbr_get_meta_list(meta, key)
    return values[0] if values else default


def cbr_to_int(value):
    """Convert numeric-looking values to int, returning None on failure."""
    if value is None:
        return None

    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def cbr_parse_number(value):
    """Parse a numeric string that may contain commas or periods."""
    if value is None:
        return None

    cleaned = re.sub(r"[^\d,.-]", "", str(value).strip())
    if not cleaned:
        return None

    if cleaned.count(",") > 1 and "." not in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." not in cleaned:
        left, right = cleaned.rsplit(",", 1)
        if len(right) == 3 and left.replace("-", "").isdigit():
            cleaned = cleaned.replace(",", "")
        else:
            cleaned = f"{left}.{right}"

    try:
        return float(cleaned)
    except ValueError:
        return None


def cbr_strip_html(html_text, max_length=None):
    """Convert HTML text to cleaned plain text."""
    if not html_text:
        return ""

    text = BeautifulSoup(str(html_text), "html.parser").get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = remove_emojis(text)
    if max_length:
        return text[:max_length].strip()
    return text.strip()


def cbr_get_embedded_terms(property_data):
    """Extract embedded WP taxonomy terms grouped by taxonomy name."""
    terms_by_taxonomy = {}
    embedded = property_data.get("_embedded", {}) or {}

    for group in embedded.get("wp:term", []) or []:
        if not isinstance(group, list):
            continue
        for term in group:
            if not isinstance(term, dict):
                continue
            taxonomy = term.get("taxonomy")
            name = term.get("name")
            if not taxonomy or not name:
                continue
            bucket = terms_by_taxonomy.setdefault(taxonomy, [])
            if name not in bucket:
                bucket.append(name)

    return terms_by_taxonomy


def cbr_get_featured_image(property_data):
    """Extract the featured image URL from an embedded property payload."""
    embedded = property_data.get("_embedded", {}) or {}
    for media_item in embedded.get("wp:featuredmedia", []) or []:
        if not isinstance(media_item, dict):
            continue
        source_url = media_item.get("source_url")
        if source_url:
            return source_url
    return ""


def cbr_fetch_media_map(media_ids):
    """Fetch WordPress media records in batches and map id -> source_url."""
    session = get_cbr_session()
    media_map = {}
    unique_ids = []
    seen_ids = set()

    for media_id in media_ids:
        int_id = cbr_to_int(media_id)
        if int_id is None or int_id in seen_ids:
            continue
        seen_ids.add(int_id)
        unique_ids.append(int_id)

    for start in range(0, len(unique_ids), CBR_PER_PAGE):
        batch_ids = unique_ids[start:start + CBR_PER_PAGE]
        params = {
            "include": ",".join(str(media_id) for media_id in batch_ids),
            "per_page": len(batch_ids),
            "orderby": "include",
            "_fields": "id,source_url"
        }
        try:
            resp = session.get(CBR_MEDIA_URL, params=params, timeout=30)
            if resp.status_code != 200:
                print(f"  Warning: media batch fetch failed ({resp.status_code})")
                continue
            for item in resp.json():
                media_id = item.get("id")
                source_url = item.get("source_url")
                if media_id and source_url:
                    media_map[int(media_id)] = source_url
        except Exception as e:
            print(f"  Warning: media batch fetch exception: {e}")

    return media_map


def cbr_fetch_agents_map(agent_ids):
    """Fetch WordPress agent records in batches and map id -> agent payload."""
    session = get_cbr_session()
    agents_map = {}
    unique_ids = []
    seen_ids = set()

    for agent_id in agent_ids:
        int_id = cbr_to_int(agent_id)
        if int_id is None or int_id in seen_ids:
            continue
        seen_ids.add(int_id)
        unique_ids.append(int_id)

    for start in range(0, len(unique_ids), CBR_PER_PAGE):
        batch_ids = unique_ids[start:start + CBR_PER_PAGE]
        params = {
            "include": ",".join(str(agent_id) for agent_id in batch_ids),
            "per_page": len(batch_ids),
            "orderby": "include",
            "_fields": "id,title,link,agent_meta"
        }
        try:
            resp = session.get(CBR_AGENTS_URL, params=params, timeout=30)
            if resp.status_code != 200:
                print(f"  Warning: agent batch fetch failed ({resp.status_code})")
                continue
            for item in resp.json():
                agent_id = item.get("id")
                if agent_id:
                    agents_map[int(agent_id)] = item
        except Exception as e:
            print(f"  Warning: agent batch fetch exception: {e}")

    return agents_map


def cbr_prefetch_related_records(properties):
    """Collect media and agent records referenced by a property batch."""
    media_ids = []
    agent_ids = []

    for property_data in properties:
        property_meta = property_data.get("property_meta", {}) or {}
        media_ids.extend(cbr_get_meta_list(property_meta, "fave_property_images"))

        thumbnail_id = cbr_get_meta_value(property_meta, "_thumbnail_id")
        if thumbnail_id:
            media_ids.append(thumbnail_id)

        agent_ids.extend(cbr_get_meta_list(property_meta, "fave_agents"))

    media_map = cbr_fetch_media_map(media_ids) if media_ids else {}
    agents_map = cbr_fetch_agents_map(agent_ids) if agent_ids else {}
    return media_map, agents_map


def cbr_map_property_type(property_type_name):
    """Map a raw Houzez property type label to normalized values used downstream."""
    if not property_type_name:
        return "", ""

    value = str(property_type_name).strip().lower()
    if any(token in value for token in ["apart", "condo", "penthouse"]):
        return "apartment", "Apartamento"
    if any(token in value for token in ["casa", "residencia", "vivienda", "townhouse"]):
        return "house", "Casa"
    if any(token in value for token in ["terreno", "lote", "land", "solar", "finca", "parcela"]):
        return "land", "Terreno"
    if any(token in value for token in ["local", "oficina", "bodega", "comercial", "warehouse", "retail"]):
        return "commercial", "Local"
    return "", ""


def cbr_build_location_text(term_names, property_meta):
    """Build a compact location string from taxonomy names and address fields."""
    def is_noise_fragment(value):
        cleaned = normalize_source_text(value).strip(" ,|-")
        if not cleaned:
            return True
        if cleaned.lower() == "el salvador":
            return True
        if re.fullmatch(r"-?\d+(?:\.\d+)?", cleaned):
            return True
        if re.fullmatch(r"-?\d{1,3}\.\d+\s*,\s*-?\d{1,3}\.\d+(?:\s*,\s*\d+(?:\.\d+)?)?", cleaned):
            return True
        return False

    def extract_parts(raw_value):
        cleaned = normalize_source_text(raw_value)
        if not cleaned:
            return []

        parts = []
        for piece in re.split(r"[|,]", cleaned):
            part = normalize_source_text(piece).strip(" ,|-")
            if is_noise_fragment(part):
                continue
            if part.lower() not in [existing.lower() for existing in parts]:
                parts.append(part)

        if not parts and not is_noise_fragment(cleaned):
            return [cleaned]

        return parts

    parts = []
    for taxonomy in ["property_area", "property_city", "property_state"]:
        for value in term_names.get(taxonomy, []):
            for part in extract_parts(value):
                if part and part.lower() not in [existing.lower() for existing in parts]:
                    parts.append(part)

    for meta_key in ["fave_property_location", "fave_property_map_address", "fave_property_address"]:
        value = cbr_get_meta_value(property_meta, meta_key)
        for part in extract_parts(value):
            if part and part.lower() not in [existing.lower() for existing in parts]:
                parts.append(part)
            if len(parts) >= 3:
                break
        if len(parts) >= 3:
            break

    return ", ".join(parts[:3])


def cbr_build_contact_info(agent_data):
    """Extract contact fields from an agent payload."""
    if not agent_data:
        return None

    agent_meta = agent_data.get("agent_meta", {}) or {}
    contact_info = {
        "name": cbr_strip_html((agent_data.get("title") or {}).get("rendered", ""), max_length=120),
        "company": cbr_get_meta_value(agent_meta, "fave_agent_company"),
        "phone": cbr_get_meta_value(agent_meta, "fave_agent_mobile"),
        "whatsapp": cbr_get_meta_value(agent_meta, "fave_agent_whatsapp"),
        "email": cbr_get_meta_value(agent_meta, "fave_agent_email"),
        "website": cbr_get_meta_value(agent_meta, "fave_agent_website"),
        "address": cbr_get_meta_value(agent_meta, "fave_agent_address"),
        "profile_url": agent_data.get("link") or "",
    }

    filtered = {key: value for key, value in contact_info.items() if value}
    return filtered or None


def cbr_parse_listing_type(status_names, title="", description="", price=None, url=None):
    """Infer the normalized listing type from property status terms."""
    status_text = " ".join(status_names).lower()
    if "renta" in status_text or "alquiler" in status_text:
        return "rent"
    if "venta" in status_text:
        return "sale"
    return correct_listing_type("sale", title, description, price, url=url)


def normalize_cbr_property(property_data, media_map=None, agents_map=None):
    """Normalize one Camara Bienes Raices REST payload into the scraper schema."""
    media_map = media_map or {}
    agents_map = agents_map or {}

    property_id = property_data.get("id")
    if not property_id:
        return None

    property_meta = property_data.get("property_meta", {}) or {}
    term_names = cbr_get_embedded_terms(property_data)

    title = cbr_strip_html((property_data.get("title") or {}).get("rendered", ""), max_length=200)
    if not title:
        title = cbr_strip_html(property_data.get("slug", ""), max_length=200)
    if not title:
        return None

    description = cbr_strip_html((property_data.get("content") or {}).get("rendered", ""), max_length=1000)
    price_raw = cbr_get_meta_value(property_meta, "fave_property_price")
    price_value = cbr_parse_number(price_raw)
    published_date = normalize_published_date_for_db(property_data.get("date_gmt") or property_data.get("date"))
    source_modified_at = property_data.get("modified_gmt") or property_data.get("modified") or ""
    listing_type = cbr_parse_listing_type(
        term_names.get("property_status", []),
        title=title,
        description=description,
        price=price_value,
        url=property_data.get("link"),
    )

    property_type_label = (term_names.get("property_type") or [""])[0]
    property_type, property_tag = cbr_map_property_type(property_type_label)
    location = cbr_build_location_text(term_names, property_meta)

    specs = {}
    size = cbr_get_meta_value(property_meta, "fave_property_size")
    land = cbr_get_meta_value(property_meta, "fave_property_land")
    bedrooms = cbr_get_meta_value(property_meta, "fave_property_bedrooms")
    bathrooms = cbr_get_meta_value(property_meta, "fave_property_bathrooms")
    garage = cbr_get_meta_value(property_meta, "fave_property_garage")

    if size:
        specs["area"] = size
    if land:
        specs["terreno"] = land
    if bedrooms:
        specs["bedrooms"] = bedrooms
    if bathrooms:
        specs["bathrooms"] = bathrooms
    if garage:
        specs["parking"] = garage

    details = {}
    if property_type:
        details["property_type"] = property_type
    if property_type_label:
        details["property_type_label"] = property_type_label
    status_label = ", ".join(term_names.get("property_status", []))
    if status_label:
        details["property_status"] = status_label
    country = ", ".join(term_names.get("property_country", []))
    if country:
        details["country"] = country
    state = ", ".join(term_names.get("property_state", []))
    if state:
        details["state"] = state
    city = ", ".join(term_names.get("property_city", []))
    if city:
        details["city"] = city
    area = ", ".join(term_names.get("property_area", []))
    if area:
        details["area"] = area

    for meta_key, detail_key in [
        ("fave_property_id", "fave_property_id"),
        ("fave_property_address", "address"),
        ("fave_property_map_address", "map_address"),
        ("fave_property_location", "location_label"),
        ("fave_property_year", "year_built"),
    ]:
        value = cbr_get_meta_value(property_meta, meta_key)
        if value:
            details[detail_key] = value

    if published_date:
        details["published_date"] = published_date
    if source_modified_at:
        details["source_modified_at"] = source_modified_at

    latitude = cbr_parse_number(cbr_get_meta_value(property_meta, "houzez_geolocation_lat"))
    longitude = cbr_parse_number(cbr_get_meta_value(property_meta, "houzez_geolocation_long"))

    image_urls = []
    featured_image = cbr_get_featured_image(property_data)
    if featured_image:
        image_urls.append(featured_image)

    for media_id in cbr_get_meta_list(property_meta, "fave_property_images"):
        media_url = media_map.get(cbr_to_int(media_id))
        if media_url and media_url not in image_urls:
            image_urls.append(media_url)

    thumbnail_url = media_map.get(cbr_to_int(cbr_get_meta_value(property_meta, "_thumbnail_id")))
    if thumbnail_url and thumbnail_url not in image_urls:
        image_urls.insert(0, thumbnail_url)

    agent_contact = None
    for agent_id in cbr_get_meta_list(property_meta, "fave_agents"):
        agent_contact = cbr_build_contact_info(agents_map.get(cbr_to_int(agent_id)))
        if agent_contact:
            break

    if agent_contact and agent_contact.get("company"):
        details["agent_company"] = agent_contact["company"]

    municipio_info = detect_municipio(location, description, title)
    listing = {
        "title": title,
        "price": price_raw or price_value,
        "location": location,
        "published_date": published_date,
        "listing_type": listing_type,
        "url": property_data.get("link"),
        "external_id": str(property_id),
        "specs": normalize_listing_specs(specs),
        "details": details,
        "description": description,
        "images": image_urls,
        "source": CAMARABIENESRAICES_SOURCE,
        "active": True,
        "municipio_detectado": municipio_info["municipio_detectado"],
        "departamento": municipio_info["departamento"],
        "latitude": latitude,
        "longitude": longitude,
        "last_updated": datetime.now().isoformat(),
    }

    if property_tag:
        listing["tags"] = [property_tag]
    if agent_contact:
        listing["contact_info"] = agent_contact

    return listing


def normalize_cbr_properties(properties):
    """Normalize a property batch while prefetching related media and agent data."""
    if not properties:
        return []

    media_map, agents_map = cbr_prefetch_related_records(properties)
    listings = []

    for property_data in properties:
        normalized = normalize_cbr_property(property_data, media_map=media_map, agents_map=agents_map)
        if normalized:
            listings.append(normalized)

    return listings


def get_cbr_properties_page(page=1, extra_params=None):
    """Fetch one Camara Bienes Raices property page from the WP REST API."""
    session = get_cbr_session()
    params = {
        "page": page,
        "per_page": CBR_PER_PAGE,
        "_embed": "1",
        "orderby": "date",
        "order": "desc",
        "status": "publish",
    }
    if extra_params:
        params.update(extra_params)

    resp = session.get(CBR_PROPERTIES_URL, params=params, timeout=45)
    if resp.status_code != 200:
        raise RuntimeError(f"CBR property page fetch failed ({resp.status_code}): {resp.text[:200]}")

    total_pages = int(resp.headers.get("X-WP-TotalPages", "1") or "1")
    total_items = int(resp.headers.get("X-WP-Total", "0") or "0")
    return resp.json(), total_pages, total_items


def get_cbr_all_properties(limit=None, max_days=None):
    """Fetch property payloads from Camara Bienes Raices with optional date filtering."""
    all_properties = []
    page = 1
    extra_params = {}

    if max_days and max_days > 0:
        threshold = datetime.utcnow() - timedelta(days=max_days)
        extra_params["after"] = threshold.isoformat(timespec="seconds")

    while True:
        properties, total_pages, total_items = get_cbr_properties_page(page=page, extra_params=extra_params)
        all_properties.extend(properties)
        print(f"  Fetched CBR page {page}/{total_pages} ({len(all_properties)}/{total_items} raw listings)")

        if limit and len(all_properties) >= limit:
            return all_properties[:limit]

        if page >= total_pages:
            break

        page += 1
        time.sleep(0.15)

    return all_properties


def get_cbr_properties_by_ids(property_ids):
    """Fetch specific CBR property IDs in API batches for update mode."""
    session = get_cbr_session()
    unique_ids = []
    seen_ids = set()

    for property_id in property_ids:
        int_id = cbr_to_int(property_id)
        if int_id is None or int_id in seen_ids:
            continue
        seen_ids.add(int_id)
        unique_ids.append(int_id)

    properties = []
    for start in range(0, len(unique_ids), CBR_PER_PAGE):
        batch_ids = unique_ids[start:start + CBR_PER_PAGE]
        params = {
            "include": ",".join(str(property_id) for property_id in batch_ids),
            "per_page": len(batch_ids),
            "_embed": "1",
            "orderby": "include",
            "status": "publish",
        }
        try:
            resp = session.get(CBR_PROPERTIES_URL, params=params, timeout=45)
            if resp.status_code != 200:
                print(f"  Warning: CBR batch fetch failed ({resp.status_code})")
                continue
            batch = resp.json()
            properties.extend(batch)
            print(f"  Fetched {len(properties)}/{len(unique_ids)} CBR update candidates")
        except Exception as e:
            print(f"  Warning: CBR batch fetch exception: {e}")

    return normalize_cbr_properties(properties)


def main_camarabienesraices(limit=None, max_days=None):
    """Main scraper function for Camara Bienes Raices."""
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} total listings from Camara Bienes Raices ***")
    if max_days and max_days > 0:
        print(f"*** DATE FILTER: Only listings from last {max_days} days ***")

    raw_properties = get_cbr_all_properties(limit=limit, max_days=max_days)
    all_listings = normalize_cbr_properties(raw_properties)

    total_old_skipped = 0
    if max_days and max_days > 0:
        filtered_listings = []
        for listing in all_listings:
            is_recent, _ = is_listing_within_date_range(listing.get("published_date"), max_days)
            if is_recent:
                filtered_listings.append(listing)
            else:
                total_old_skipped += 1
        all_listings = filtered_listings

    sale_data = [listing for listing in all_listings if listing.get("listing_type") == "sale"]
    rent_data = [listing for listing in all_listings if listing.get("listing_type") == "rent"]

    print(
        f"  Camara Bienes Raices total: {len(all_listings)} "
        f"({len(sale_data)} sales, {len(rent_data)} rentals)"
    )
    if total_old_skipped > 0:
        print(f"  Skipped {total_old_skipped} old listings (>{max_days} days)")

    return all_listings, sale_data, rent_data


# ============== REALTY EL SALVADOR FUNCTIONS ==============

def realtyelsalvador_parse_datetime(date_str):
    """Parse a Realty El Salvador ISO-like datetime string."""
    if not date_str:
        return None

    cleaned = str(date_str).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def realtyelsalvador_format_date(date_str):
    """Convert Realty date strings to dd/mm/YYYY."""
    parsed = realtyelsalvador_parse_datetime(date_str)
    return parsed.strftime("%d/%m/%Y") if parsed else ""


def realtyelsalvador_get_available_status_id(force_refresh=False):
    """Resolve the Realty El Salvador status taxonomy ID for available listings."""
    global REALTYELSALVADOR_AVAILABLE_STATUS_ID

    if REALTYELSALVADOR_AVAILABLE_STATUS_ID and not force_refresh:
        return REALTYELSALVADOR_AVAILABLE_STATUS_ID

    session = get_realtyelsalvador_session()
    try:
        resp = session.get(
            REALTYELSALVADOR_PROPERTY_STATUS_URL,
            params={"per_page": 100},
            timeout=30
        )
        if resp.status_code != 200:
            return None

        for term in resp.json():
            slug = str(term.get("slug", "")).strip().lower()
            if slug == "disponible":
                REALTYELSALVADOR_AVAILABLE_STATUS_ID = term.get("id")
                return REALTYELSALVADOR_AVAILABLE_STATUS_ID
    except Exception as e:
        print(f"  Warning: Could not resolve Realty available status ID: {e}")

    return None


def realtyelsalvador_get_class_slug(property_data, prefix):
    """Extract one class_list slug suffix from a Realty property payload."""
    for class_name in property_data.get("class_list", []) or []:
        class_str = str(class_name).strip()
        if class_str.startswith(prefix):
            return class_str[len(prefix):]
    return ""


def realtyelsalvador_is_available(property_data, term_names=None):
    """Return True when the Realty property is still marked as available."""
    status_slug = realtyelsalvador_get_class_slug(property_data, "property-status-")
    if status_slug == "disponible":
        return True
    if status_slug == "no-disponible":
        return False

    if property_data.get("status") != "publish":
        return False

    if term_names is None:
        term_names = cbr_get_embedded_terms(property_data)

    statuses = [normalize_source_text(value).lower() for value in term_names.get("property-status", [])]
    if any(value == "disponible" for value in statuses):
        return True
    if any("no disponible" in value for value in statuses):
        return False

    return True


def realtyelsalvador_pick_image_url(image_entry):
    """Pick the best available image URL from a Realty gallery image entry."""
    if not isinstance(image_entry, dict):
        return ""

    for key in ("full_url", "url"):
        candidate = normalize_source_text(image_entry.get(key))
        if candidate.startswith("http"):
            return candidate

    sizes = image_entry.get("sizes", {}) or {}
    preferred_sizes = [
        "post-featured-image",
        "large",
        "medium_large",
        "property-detail-video-image",
        "modern-property-child-slider",
        "property-thumb-image",
        "medium",
        "thumbnail",
    ]
    for size_key in preferred_sizes:
        size_entry = sizes.get(size_key)
        if isinstance(size_entry, dict):
            candidate = normalize_source_text(size_entry.get("url"))
            if candidate.startswith("http"):
                return candidate

    return ""


def realtyelsalvador_map_property_type(label="", slug=""):
    """Map Realty property taxonomy labels/slugs into normalized property types."""
    combined = normalize_source_text(f"{label} {slug}").lower()
    if any(token in combined for token in ("apartamento", "apartment", "condo", "condominio")):
        return "apartment"
    if any(token in combined for token in ("terreno", "lote", "land", "lot", "parcela", "finca")):
        return "land"
    if any(token in combined for token in ("hotel", "local", "oficina", "bodega", "comercial", "industrial")):
        return "commercial"
    if any(token in combined for token in ("casa", "house", "residencia", "quinta")):
        return "house"
    return ""


def realtyelsalvador_build_location_text(term_names, property_meta):
    """Build the best location string available for a Realty listing."""
    parts = []
    address = normalize_source_text(property_meta.get("REAL_HOMES_property_address"))
    if address:
        parts.append(address)

    for value in term_names.get("property-city", []) or []:
        cleaned = normalize_source_text(value)
        if cleaned and cleaned not in parts:
            parts.append(cleaned)

    return ", ".join(parts)


def realtyelsalvador_describe_error_response(resp):
    """Build a readable error summary for blocked or failed Realty responses."""
    body_preview = normalize_source_text((resp.text or "")[:200])
    lowered = body_preview.lower()
    if resp.status_code == 403 and "just a moment" in lowered:
        return "403 Cloudflare anti-bot challenge"
    if resp.status_code == 403 and "attention required" in lowered:
        return "403 Cloudflare access challenge"
    if resp.status_code == 429:
        return "429 rate limited"
    return f"{resp.status_code}: {body_preview or 'empty response'}"


def realtyelsalvador_get_properties_page(page=1, active_only=True):
    """Fetch one page of Realty El Salvador properties from the public WP REST API."""
    global REALTYELSALVADOR_SESSION
    params = {
        "page": page,
        "per_page": REALTYELSALVADOR_PER_PAGE,
        "_embed": "1",
        "orderby": "modified",
        "order": "desc",
        "status": "publish",
    }

    available_status_id = realtyelsalvador_get_available_status_id()
    if active_only and available_status_id:
        params["estado-de-propiedad"] = available_status_id

    last_error = None
    for attempt in range(1, 4):
        session = get_realtyelsalvador_session()
        try:
            resp = session.get(REALTYELSALVADOR_PROPERTIES_URL, params=params, timeout=45)
        except requests.exceptions.RequestException as e:
            last_error = f"request exception on attempt {attempt}/3: {e}"
        else:
            if resp.status_code == 200:
                total_pages = int(resp.headers.get("X-WP-TotalPages", "1") or "1")
                total_items = int(resp.headers.get("X-WP-Total", "0") or "0")
                return resp.json(), total_pages, total_items

            last_error = (
                f"Realty property page fetch failed on attempt {attempt}/3: "
                f"{realtyelsalvador_describe_error_response(resp)}"
            )

            if resp.status_code not in (403, 429, 500, 502, 503, 504):
                break

        if attempt < 3:
            print(f"  Warning: {last_error}. Retrying...")
            time.sleep(attempt * 1.5)
            REALTYELSALVADOR_SESSION = None

    raise RuntimeError(last_error or "Realty property page fetch failed with unknown error")


def normalize_realtyelsalvador_property(property_data):
    """Normalize one Realty El Salvador property payload to the shared listing schema."""
    if not isinstance(property_data, dict):
        return None

    property_id = property_data.get("id")
    if not property_id:
        return None

    property_meta = property_data.get("property_meta") or {}
    term_names = cbr_get_embedded_terms(property_data)

    title = cbr_strip_html((property_data.get("title") or {}).get("rendered", ""), max_length=200)
    description = cbr_strip_html((property_data.get("content") or {}).get("rendered", ""))
    if not description:
        description = cbr_strip_html((property_data.get("excerpt") or {}).get("rendered", ""))

    price_raw = normalize_source_text(property_meta.get("REAL_HOMES_property_price"))
    price_prefix = normalize_source_text(property_meta.get("REAL_HOMES_property_price_prefix"))
    price_postfix = normalize_source_text(property_meta.get("REAL_HOMES_property_price_postfix"))
    price_parts = [part for part in [price_prefix, price_raw, price_postfix] if part]
    price_text = " ".join(price_parts) if price_parts else price_raw
    parsed_price = parse_price(price_text or price_raw)

    listing_type = correct_listing_type(
        "sale",
        title,
        description,
        parsed_price,
        url=property_data.get("link")
    )

    property_type_label = (term_names.get("property-type") or [""])[0]
    property_type_slug = realtyelsalvador_get_class_slug(property_data, "property-type-")
    property_type = realtyelsalvador_map_property_type(property_type_label, property_type_slug)

    specs = {}
    bedrooms = normalize_source_text(property_meta.get("REAL_HOMES_property_bedrooms"))
    bathrooms = normalize_source_text(property_meta.get("REAL_HOMES_property_bathrooms"))
    garage = normalize_source_text(property_meta.get("REAL_HOMES_property_garage"))
    size = normalize_source_text(property_meta.get("REAL_HOMES_property_size"))
    size_postfix = normalize_source_text(property_meta.get("REAL_HOMES_property_size_postfix"))
    lot_size = normalize_source_text(property_meta.get("REAL_HOMES_property_lot_size"))
    lot_postfix = normalize_source_text(property_meta.get("REAL_HOMES_property_lot_size_postfix"))

    if bedrooms:
        specs["bedrooms"] = bedrooms
    if bathrooms:
        specs["bathrooms"] = bathrooms
    if garage:
        specs["parking"] = garage
    if size:
        specs["area"] = " ".join(part for part in [size, size_postfix] if part)
    if lot_size:
        specs["terreno"] = " ".join(part for part in [lot_size, lot_postfix] if part)

    location = realtyelsalvador_build_location_text(term_names, property_meta)
    published_date = realtyelsalvador_format_date(property_data.get("date"))
    source_modified_at = normalize_source_text(property_data.get("modified_gmt") or property_data.get("modified"))

    details = {
        "source_listing_id": str(property_id),
    }
    if property_type:
        details["property_type"] = property_type
    if property_type_label:
        details["property_type_label"] = property_type_label

    property_status = ", ".join(term_names.get("property-status", []))
    if property_status:
        details["property_status"] = property_status
    city_label = ", ".join(term_names.get("property-city", []))
    if city_label:
        details["city"] = city_label

    property_ref = normalize_source_text(property_meta.get("REAL_HOMES_property_id"))
    if property_ref:
        details["source_property_ref"] = property_ref
    if source_modified_at:
        details["source_modified_at"] = source_modified_at

    author_data = ((property_data.get("_embedded") or {}).get("author") or [])
    if author_data:
        author = author_data[0]
        author_name = normalize_source_text(author.get("name"))
        author_url = normalize_source_text(author.get("url"))
        if author_name:
            details["agent_name"] = author_name
        if author_url:
            details["agent_url"] = author_url

    feature_labels = term_names.get("property-feature", []) or []
    if feature_labels:
        details["features"] = feature_labels

    property_location = property_meta.get("REAL_HOMES_property_location") or {}
    latitude = cbr_parse_number(property_location.get("latitude"))
    longitude = cbr_parse_number(property_location.get("longitude"))

    images = []
    featured_image = cbr_get_featured_image(property_data)
    if featured_image:
        images.append(featured_image)
    for image_entry in property_meta.get("REAL_HOMES_property_images", []) or []:
        image_url = realtyelsalvador_pick_image_url(image_entry)
        if image_url and image_url not in images:
            images.append(image_url)

    municipio_info = detect_municipio(location, description, title)
    return {
        "title": title,
        "price": price_text or price_raw,
        "location": location,
        "published_date": published_date,
        "listing_type": listing_type,
        "url": property_data.get("link"),
        "external_id": str(slug_to_external_id(f"realtyelsalvador:{property_id}")),
        "specs": normalize_listing_specs(specs),
        "details": details,
        "description": description,
        "images": images,
        "source": REALTYELSALVADOR_SOURCE,
        "active": realtyelsalvador_is_available(property_data, term_names=term_names),
        "municipio_detectado": municipio_info["municipio_detectado"],
        "departamento": municipio_info["departamento"],
        "latitude": latitude,
        "longitude": longitude,
        "last_updated": datetime.now().isoformat(),
    }


def get_realtyelsalvador_all_listings(limit=None, max_days=None, active_only=True):
    """Fetch and normalize Realty El Salvador properties."""
    raw_properties = []
    page = 1

    while True:
        properties, total_pages, total_items = realtyelsalvador_get_properties_page(
            page=page,
            active_only=active_only
        )
        raw_properties.extend(properties)
        print(
            f"  Fetched Realty page {page}/{total_pages} "
            f"({len(raw_properties)}/{total_items} raw listings)"
        )

        if limit and len(raw_properties) >= limit:
            raw_properties = raw_properties[:limit]
            break

        if page >= total_pages:
            break

        page += 1
        time.sleep(0.15)

    listings = []
    old_listing_count = 0
    for property_data in raw_properties:
        listing = normalize_realtyelsalvador_property(property_data)
        if not listing:
            continue
        if active_only and not listing.get("active", True):
            continue
        if max_days and max_days > 0:
            is_recent, _ = is_listing_within_date_range(listing.get("published_date"), max_days)
            if not is_recent:
                old_listing_count += 1
                continue
        listings.append(listing)

    return listings, old_listing_count


def get_realtyelsalvador_listing_status(url):
    """Validate one Realty El Salvador listing via the public WP REST API."""
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    slug = path_parts[-1] if path_parts else ""
    if not slug or slug == "propiedades":
        return False, "Missing property slug"

    session = get_realtyelsalvador_session()
    try:
        resp = session.get(
            REALTYELSALVADOR_PROPERTIES_URL,
            params={"slug": slug, "per_page": 1, "_embed": "1"},
            timeout=30
        )
        if resp.status_code == 404:
            return False, "404 Not Found"
        if resp.status_code >= 400:
            return True, f"HTTP {resp.status_code} (assumed active)"

        payload = resp.json()
        if not payload:
            return False, "Listing not present in WP API"

        property_data = payload[0]
        if not realtyelsalvador_is_available(property_data):
            return False, "Property status is not disponible"

        return True, "Active"
    except requests.exceptions.Timeout:
        return True, "Timeout (assumed active)"
    except requests.exceptions.ConnectionError:
        return True, "Connection error (assumed active)"
    except Exception as e:
        return True, f"Error: {str(e)[:50]} (assumed active)"


def main_realtyelsalvador(limit=None, max_days=None):
    """Main scraper function for Realty El Salvador."""
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} total listings from Realty El Salvador ***")
    if max_days and max_days > 0:
        print(f"*** DATE FILTER: Only listings from last {max_days} days ***")

    all_listings, old_count = get_realtyelsalvador_all_listings(
        limit=limit,
        max_days=max_days,
        active_only=True
    )

    sale_data = [listing for listing in all_listings if listing.get("listing_type") == "sale"]
    rent_data = [listing for listing in all_listings if listing.get("listing_type") == "rent"]

    print(
        f"  Realty El Salvador total: {len(all_listings)} "
        f"({len(sale_data)} sales, {len(rent_data)} rentals)"
    )
    if old_count > 0:
        print(f"  Skipped {old_count} old listings (>{max_days} days)")

    return all_listings, sale_data, rent_data


# ============== CASAS AHORITA FUNCTIONS ==============

CASASAHORITA_MONTHS = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}

CASASAHORITA_PROPERTY_TYPE_MAP = {
    "casa": "house",
    "apartamento": "apartment",
    "terreno-general": "land",
    "espacio-comercial": "commercial",
    "industrial": "commercial",
    "hotel": "commercial",
    "otro": "other",
}


def casasahorita_normalize_key(text):
    """Normalize Casas Ahorita labels for accent-insensitive matching."""
    normalized = normalize_source_text(text).lower()
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return normalized.strip()


def _legacy_casasahorita_parse_datetime(date_text):
    """Parse Casas Ahorita date strings like 'Jue 10 Abr 2025 09:38:01 CST'."""
    cleaned = normalize_source_text(date_text).lower()
    match = re.search(
        r"(\d{1,2})\s+([a-záéíóú]+)\s+(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?",
        cleaned
    )
    if not match:
        return None

    day = int(match.group(1))
    month_token = match.group(2)[:3]
    month = CASASAHORITA_MONTHS.get(month_token)
    year = int(match.group(3))
    hour = int(match.group(4) or 0)
    minute = int(match.group(5) or 0)
    second = int(match.group(6) or 0)

    if not month:
        return None

    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


def _legacy_casasahorita_extract_dates(raw_html):
    """Extract publication and update timestamps from a Casas Ahorita detail page."""
    original_match = re.search(
        r"Fecha Original De Publicación:</strong>\s*<br>\s*([^<]+)",
        raw_html,
        re.IGNORECASE
    )
    updated_match = re.search(
        r"Cambio Más Reciente:</strong>\s*<br>\s*([^<]+)",
        raw_html,
        re.IGNORECASE
    )

    original_raw = normalize_source_text(original_match.group(1)) if original_match else ""
    updated_raw = normalize_source_text(updated_match.group(1)) if updated_match else ""
    original_dt = _legacy_casasahorita_parse_datetime(original_raw)
    updated_dt = _legacy_casasahorita_parse_datetime(updated_raw)

    return {
        "published_raw": original_raw,
        "updated_raw": updated_raw,
        "published_date": original_dt.strftime("%d/%m/%Y") if original_dt else "",
        "updated_iso": updated_dt.isoformat() if updated_dt else "",
    }


def casasahorita_slug_info_from_url(url):
    """Parse transaction, property type, and source ID from a Casas Ahorita listing URL."""
    path = urlparse(url).path.rstrip("/")
    slug = path.split("/")[-1] if path else ""
    match = re.search(r"-(venta|alquiler)-([a-z-]+)-(\d{10})$", slug, re.IGNORECASE)
    if not match:
        return {
            "slug": slug,
            "listing_type": infer_listing_type_from_url(url, default_type="sale"),
            "property_type_slug": "",
            "source_listing_id": "",
        }

    return {
        "slug": slug,
        "listing_type": "rent" if match.group(1).lower() == "alquiler" else "sale",
        "property_type_slug": match.group(2).lower(),
        "source_listing_id": match.group(3),
    }


def casasahorita_is_placeholder_page(raw_html, soup=None):
    """Return True when a Casas Ahorita URL resolves to an empty placeholder listing."""
    if soup is None:
        soup = BeautifulSoup(raw_html or "", "html.parser")

    h1 = normalize_source_text(
        soup.select_one("div.content.row h1").get_text(" ", strip=True)
        if soup.select_one("div.content.row h1") else ""
    ).lower()
    h2 = normalize_source_text(
        soup.select_one("div.content.row h2.lead").get_text(" ", strip=True)
        if soup.select_one("div.content.row h2.lead") else ""
    ).lower()
    page_text = normalize_source_text(soup.get_text(" ", strip=True)).lower()
    gallery_images = [
        img for img in soup.select("img[src]")
        if "/img/user_uploads/" in (img.get("src") or "")
        and "/profile_fotos/" not in (img.get("src") or "")
    ]

    has_blank_heading = (not h1) or h1 in {"en -", "en  -", "-"} or (h1.endswith("-") and "$" not in h1)
    has_blank_subheading = not h2
    has_zero_photos = ("numero de fotos: 0" in page_text) or (len(gallery_images) == 0)
    has_epoch_date = "31 dic 1969" in page_text or "1970" in page_text or "1969" in page_text

    return (has_blank_heading and has_zero_photos) or (has_blank_subheading and has_epoch_date)


def _legacy_casasahorita_extract_description(soup):
    """Extract the main description block from a Casas Ahorita detail page."""
    for heading in soup.select("h3, h4, h5"):
        heading_text = normalize_source_text(heading.get_text(" ", strip=True)).lower()
        if "descripción" in heading_text or "descripcion" in heading_text:
            sibling = heading.find_next_sibling("div")
            if sibling:
                text = normalize_source_text(sibling.get_text("\n", strip=True))
                return re.sub(r"\n{3,}", "\n\n", text).strip()
    return ""


def _legacy_casasahorita_extract_specs(soup):
    """Extract the specs table from a Casas Ahorita detail page."""
    specs = {}
    raw_fields = {}

    table = soup.select_one("table.table.table-hover")
    if not table:
        return specs, raw_fields

    for row in table.select("tr"):
        label_el = row.select_one("th")
        value_cells = row.select("td")
        if not label_el or not value_cells:
            continue

        label = normalize_source_text(label_el.get_text(" ", strip=True)).rstrip(":")
        value = normalize_source_text(" ".join(cell.get_text(" ", strip=True) for cell in value_cells))
        if not label or not value:
            continue

        raw_fields[label] = value
        label_lower = label.lower()

        if "recámara" in label_lower or "recamara" in label_lower:
            specs["bedrooms"] = value
        elif "baño" in label_lower:
            specs["bathrooms"] = value
        elif "vehículo" in label_lower or "vehiculo" in label_lower or "parqueo" in label_lower:
            specs["parking"] = value
        elif "tamaño del lote" in label_lower:
            cleaned = re.sub(r"^\(\s*m²\s*\)\s*", "", value, flags=re.IGNORECASE).strip()
            specs["terreno"] = f"{cleaned} m²" if cleaned and "m²" not in cleaned.lower() else cleaned
        elif "tamaño de construcción" in label_lower or "tamaño de construccion" in label_lower:
            cleaned = re.sub(r"^\(\s*m²\s*\)\s*", "", value, flags=re.IGNORECASE).strip()
            specs["area"] = f"{cleaned} m²" if cleaned and "m²" not in cleaned.lower() else cleaned

    return specs, raw_fields


def _legacy_casasahorita_extract_contact_details(soup):
    """Extract contact metadata from the Casas Ahorita detail page."""
    details = {}
    for heading in soup.select("h5"):
        heading_text = normalize_source_text(heading.get_text(" ", strip=True)).lower()
        if "propiedad por" not in heading_text:
            continue

        card_body = heading.find_parent(class_="card-body")
        if not card_body:
            break

        lines = [
            normalize_source_text(node.get_text(" ", strip=True))
            for node in card_body.select("p.card-text")
        ]
        lines = [line for line in lines if line]
        if lines:
            details["contact_name"] = lines[0]

        for line in lines[1:]:
            if re.search(r"@[\w.-]+", line):
                details["contact_email"] = line.strip()
            elif re.search(r"\d", line):
                details["contact_phone"] = line.strip()
        break

    return details


def get_casasahorita_listing_urls(max_listings=None):
    """Collect El Salvador listing URLs from Casas Ahorita's search pages."""
    session = get_casasahorita_session()
    all_urls = []

    for discovery_url in [CASASAHORITA_SEARCH_URL, CASASAHORITA_FALLBACK_SEARCH_URL]:
        try:
            resp = session.get(discovery_url, timeout=30)
            if resp.status_code != 200:
                print(f"  Warning: Casas Ahorita discovery failed ({resp.status_code}) for {discovery_url}")
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            found_urls = []
            for anchor in soup.select("a[href]"):
                href = normalize_source_text(anchor.get("href"))
                if not href:
                    continue
                absolute_url = urljoin(CASASAHORITA_BASE_URL, href)
                if re.match(r"^https://casasahorita\.com/propiedad/sv/[^/]+/?$", absolute_url):
                    found_urls.append(absolute_url.rstrip("/"))

            if found_urls:
                print(f"  Found {len(set(found_urls))} Casas Ahorita URLs in {discovery_url}")
                all_urls.extend(found_urls)
        except Exception as e:
            print(f"  Warning: Error collecting Casas Ahorita URLs from {discovery_url}: {e}")

    deduped_urls = list(dict.fromkeys(all_urls))
    if max_listings and len(deduped_urls) > max_listings:
        return deduped_urls[:max_listings]
    return deduped_urls


def casasahorita_parse_datetime(date_text):
    """Parse Casas Ahorita date strings like 'Jue 10 Abr 2025 09:38:01 CST'."""
    cleaned = casasahorita_normalize_key(date_text)
    match = re.search(
        r"(\d{1,2})\s+([a-z]+)\s+(\d{4})(?:\s+(\d{2}):(\d{2})(?::(\d{2}))?)?",
        cleaned
    )
    if not match:
        return None

    day = int(match.group(1))
    month_token = match.group(2)[:3]
    month = CASASAHORITA_MONTHS.get(month_token)
    year = int(match.group(3))
    hour = int(match.group(4) or 0)
    minute = int(match.group(5) or 0)
    second = int(match.group(6) or 0)

    if not month:
        return None

    try:
        return datetime(year, month, day, hour, minute, second)
    except ValueError:
        return None


def casasahorita_extract_dates(raw_html):
    """Extract publication and update timestamps from a Casas Ahorita detail page."""
    soup = BeautifulSoup(raw_html or "", "html.parser")
    lines = [normalize_source_text(value) for value in soup.stripped_strings]
    lines = [value for value in lines if value]

    original_raw = ""
    updated_raw = ""
    for idx, line in enumerate(lines):
        normalized = casasahorita_normalize_key(line)
        if normalized == "fecha original de publicacion" and idx + 1 < len(lines):
            original_raw = lines[idx + 1]
        elif normalized == "cambio mas reciente" and idx + 1 < len(lines):
            updated_raw = lines[idx + 1]

    original_dt = casasahorita_parse_datetime(original_raw)
    updated_dt = casasahorita_parse_datetime(updated_raw)

    return {
        "published_raw": original_raw,
        "updated_raw": updated_raw,
        "published_date": original_dt.strftime("%d/%m/%Y") if original_dt else "",
        "updated_iso": updated_dt.isoformat() if updated_dt else "",
    }


def casasahorita_extract_description(soup):
    """Extract the main description block from a Casas Ahorita detail page."""
    for heading in soup.select("h3, h4, h5"):
        heading_text = casasahorita_normalize_key(heading.get_text(" ", strip=True))
        if "descripcion" in heading_text:
            sibling = heading.find_next_sibling("div")
            if sibling:
                text = normalize_source_text(sibling.get_text("\n", strip=True))
                return re.sub(r"\n{3,}", "\n\n", text).strip()
    return ""


def casasahorita_extract_specs(soup):
    """Extract the specs table from a Casas Ahorita detail page."""
    specs = {}
    raw_fields = {}

    table = soup.select_one("table.table.table-hover")
    if not table:
        return specs, raw_fields

    for row in table.select("tr"):
        label_el = row.select_one("th")
        value_cells = row.select("td")
        if not label_el or not value_cells:
            continue

        label = normalize_source_text(label_el.get_text(" ", strip=True)).rstrip(":")
        value = normalize_source_text(" ".join(cell.get_text(" ", strip=True) for cell in value_cells))
        if not label or not value:
            continue

        label_key = casasahorita_normalize_key(label)
        raw_fields[label_key] = value

        if "recamara" in label_key:
            specs["bedrooms"] = value
        elif "bano" in label_key:
            specs["bathrooms"] = value
        elif "vehiculo" in label_key or "parqueo" in label_key:
            specs["parking"] = value
        elif "tamano del lote" in label_key:
            cleaned = re.sub(r"^\(\s*m[²2]\s*\)\s*", "", value, flags=re.IGNORECASE).strip()
            specs["terreno"] = f"{cleaned} m2" if cleaned and "m2" not in cleaned.lower() else cleaned
        elif "tamano de construccion" in label_key:
            cleaned = re.sub(r"^\(\s*m[²2]\s*\)\s*", "", value, flags=re.IGNORECASE).strip()
            specs["area"] = f"{cleaned} m2" if cleaned and "m2" not in cleaned.lower() else cleaned

    return specs, raw_fields


def casasahorita_extract_inline_summary(text):
    """Recover price/specs when Casas Ahorita omits the structured table."""
    cleaned = normalize_source_text(text)
    if not cleaned:
        return "", {}, {}

    price = ""
    specs = {}
    raw_fields = {}

    price_match = re.search(r'\$\s*([\d,]+(?:\.\d+)?)', cleaned)
    if price_match:
        price = f"${price_match.group(1)}"

    bedrooms_match = re.search(r'(\d+(?:[.,]\d+)?)\s*Cuartos?', cleaned, re.IGNORECASE)
    if bedrooms_match:
        specs["bedrooms"] = bedrooms_match.group(1).replace(",", ".")
        raw_fields["recamaras"] = specs["bedrooms"]

    bathrooms_match = re.search(r'(\d+(?:[.,]\d+)?)\s*Ba(?:ñ|n)os?', cleaned, re.IGNORECASE)
    if bathrooms_match:
        specs["bathrooms"] = bathrooms_match.group(1).replace(",", ".")
        raw_fields["banos"] = specs["bathrooms"]

    parking_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(?:Veh[ií]culos?|Parqueos?)', cleaned, re.IGNORECASE)
    if parking_match:
        specs["parking"] = parking_match.group(1).replace(",", ".")
        raw_fields["vehiculos"] = specs["parking"]

    area_match = re.search(r'Tama(?:ñ|n)o de construcci(?:ó|o)n:\s*([\d,]+(?:\.\d+)?)', cleaned, re.IGNORECASE)
    if area_match:
        area_value = area_match.group(1)
        specs["area"] = f"{area_value} m2"
        raw_fields["tamano de construccion"] = area_value

    lot_match = re.search(r'Tama(?:ñ|n)o del lote:\s*([\d,]+(?:\.\d+)?)', cleaned, re.IGNORECASE)
    if lot_match:
        lot_value = lot_match.group(1)
        specs["terreno"] = f"{lot_value} m2"
        raw_fields["tamano del lote"] = lot_value

    return price, specs, raw_fields


def casasahorita_extract_contact_details(soup):
    """Extract contact metadata from the Casas Ahorita detail page."""
    details = {}
    for heading in soup.select("h5"):
        heading_text = casasahorita_normalize_key(heading.get_text(" ", strip=True))
        if "propiedad por" not in heading_text:
            continue

        card_body = heading.find_parent(class_="card-body")
        if not card_body:
            break

        lines = [
            normalize_source_text(node.get_text(" ", strip=True))
            for node in card_body.select("p.card-text")
        ]
        lines = [line for line in lines if line]
        if lines:
            details["contact_name"] = lines[0]

        for line in lines[1:]:
            if re.search(r"@[\w.-]+", line):
                details["contact_email"] = line.strip()
            elif re.search(r"\d", line):
                details["contact_phone"] = line.strip()
        break

    return details


def scrape_casasahorita_listing(url, listing_type="auto"):
    """Scrape one Casas Ahorita listing page."""
    session = get_casasahorita_session()

    try:
        resp = session.get(url, timeout=30)
        if resp.status_code in (404, 410):
            return None

        raw_html = resp.text or ""
        soup = BeautifulSoup(raw_html, "html.parser")
        if casasahorita_is_placeholder_page(raw_html, soup=soup):
            return None

        slug_info = casasahorita_slug_info_from_url(url)
        source_listing_id = slug_info.get("source_listing_id")
        if not source_listing_id:
            return None

        header_h1 = normalize_source_text(
            soup.select_one("div.content.row h1").get_text(" ", strip=True)
            if soup.select_one("div.content.row h1") else ""
        )
        header_h2 = normalize_source_text(
            soup.select_one("div.content.row h2.lead").get_text(" ", strip=True)
            if soup.select_one("div.content.row h2.lead") else ""
        )

        price_match = re.search(r"\$[\d,]+(?:\.\d+)?", header_h1)
        price = price_match.group(0) if price_match else ""
        title = header_h2 or header_h1
        if not title:
            return None

        description = casasahorita_extract_description(soup)
        specs, raw_fields = casasahorita_extract_specs(soup)
        inline_price, inline_specs, inline_fields = casasahorita_extract_inline_summary("\n".join(part for part in [header_h2, description] if part))
        if not price:
            price = inline_price
        if inline_specs:
            merged_specs = dict(inline_specs)
            merged_specs.update(specs)
            specs = merged_specs
        if inline_fields:
            merged_fields = dict(inline_fields)
            merged_fields.update(raw_fields)
            raw_fields = merged_fields
        contact_details = casasahorita_extract_contact_details(soup)
        date_info = casasahorita_extract_dates(raw_html)

        listing_type = slug_info.get("listing_type") if listing_type == "auto" else listing_type
        listing_type = correct_listing_type(
            listing_type,
            title,
            description,
            parse_price(price),
            url=url
        )

        property_type_slug = slug_info.get("property_type_slug", "")
        property_type = CASASAHORITA_PROPERTY_TYPE_MAP.get(property_type_slug, "")

        details = {
            "source_listing_id": source_listing_id,
            "source_heading": header_h1,
            "property_type_slug": property_type_slug,
        }
        if property_type:
            details["property_type"] = property_type
        if date_info.get("updated_iso"):
            details["source_modified_at"] = date_info["updated_iso"]
        if date_info.get("updated_raw"):
            details["source_modified_label"] = date_info["updated_raw"]
        if date_info.get("published_raw"):
            details["source_published_label"] = date_info["published_raw"]

        for key, value in raw_fields.items():
            details[key] = value
        details.update(contact_details)

        country = raw_fields.get("pais", "")
        department = raw_fields.get("departamento", "")
        city = raw_fields.get("ciudad", "")
        location_parts = []
        for part in [city, department, country]:
            cleaned = normalize_source_text(part)
            if cleaned and cleaned not in location_parts:
                location_parts.append(cleaned)
        location = ", ".join(location_parts)

        images = []
        for img in soup.select("img[src]"):
            src = normalize_source_text(img.get("src"))
            absolute_url = urljoin(CASASAHORITA_BASE_URL, src)
            if (
                "/img/user_uploads/" in absolute_url
                and "/profile_fotos/" not in absolute_url
                and absolute_url not in images
            ):
                images.append(absolute_url)

        municipio_info = detect_municipio(location, description, title)
        if not location or location == "El Salvador":
            detected_location_parts = []
            for part in [municipio_info.get("municipio_detectado"), municipio_info.get("departamento")]:
                cleaned = normalize_source_text(part)
                if cleaned and cleaned != "No identificado" and cleaned not in detected_location_parts:
                    detected_location_parts.append(cleaned)
            location = ", ".join(
                detected_location_parts
            )
        return {
            "title": title,
            "price": price,
            "location": location,
            "published_date": date_info.get("published_date"),
            "listing_type": listing_type,
            "url": url.rstrip("/"),
            "external_id": str(slug_to_external_id(f"casasahorita:{source_listing_id}")),
            "specs": normalize_listing_specs(specs),
            "details": details,
            "description": description,
            "images": images,
            "source": CASASAHORITA_SOURCE,
            "active": True,
            "municipio_detectado": municipio_info["municipio_detectado"],
            "departamento": municipio_info["departamento"],
            "latitude": None,
            "longitude": None,
            "last_updated": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"  Error scraping Casas Ahorita {url}: {e}")
        return None


def scrape_casasahorita_listings_concurrent(urls, listing_type="auto", max_workers=5, max_days=None):
    """Scrape multiple Casas Ahorita listings concurrently."""
    results = []
    old_listing_count = 0
    total_urls = len(urls)
    completed_count = 0
    started_at = time.time()
    progress_every = 10 if total_urls >= 50 else 5

    print(f"  Scraping {total_urls} Casas Ahorita listings with {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scrape_casasahorita_listing, url, listing_type): url
            for url in urls
        }
        for future in as_completed(future_to_url):
            completed_count += 1
            url = future_to_url[future]
            try:
                listing = future.result()
                if listing:
                    if max_days and max_days > 0:
                        is_recent, _ = is_listing_within_date_range(listing.get("published_date"), max_days)
                        if not is_recent:
                            old_listing_count += 1
                            continue
                    results.append(listing)
            except Exception as e:
                print(f"  Error processing Casas Ahorita {url}: {e}")
            finally:
                if completed_count % progress_every == 0 or completed_count == total_urls:
                    elapsed = time.time() - started_at
                    print(
                        f"    Casas Ahorita progress: {completed_count}/{total_urls} "
                        f"(ok: {len(results)}, old-skipped: {old_listing_count}, elapsed: {elapsed:.1f}s)"
                    )

    return results, old_listing_count


def main_casasahorita(limit=None, max_days=None):
    """Main scraper function for Casas Ahorita."""
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} total listings from Casas Ahorita ***")
    if max_days and max_days > 0:
        print(f"*** DATE FILTER: Only listings from last {max_days} days ***")

    urls = get_casasahorita_listing_urls(max_listings=limit)
    if not urls:
        print("  No Casas Ahorita URLs found to scrape")
        return [], [], []

    all_listings, old_count = scrape_casasahorita_listings_concurrent(
        urls,
        listing_type="auto",
        max_workers=5,
        max_days=max_days
    )

    sale_data = [listing for listing in all_listings if listing.get("listing_type") == "sale"]
    rent_data = [listing for listing in all_listings if listing.get("listing_type") == "rent"]

    print(
        f"  Casas Ahorita total: {len(all_listings)} "
        f"({len(sale_data)} sales, {len(rent_data)} rentals)"
    )
    if old_count > 0:
        print(f"  Skipped {old_count} old listings (>{max_days} days)")

    return all_listings, sale_data, rent_data

# ============== PROPILATAM FUNCTIONS ==============

def infer_propilatam_property_type(slug):
    """Infer Propi property type segment for /sv/venta/<property_type>/... routes."""
    if not slug:
        return "casa"

    slug_l = slug.lower()
    token = slug_l.split("-en-")[0].split("-")[0]
    allowed = {"casa", "apartamento", "terreno", "local", "oficina", "bodega", "finca"}
    if token in allowed:
        return token

    if "apart" in token:
        return "apartamento"
    if "terreno" in slug_l or "lote" in slug_l:
        return "terreno"
    if "oficina" in slug_l:
        return "oficina"
    if "local" in slug_l:
        return "local"

    return "casa"


def build_propilatam_sale_variant_url(url):
    """
    Build a sale-route variant from a Propi rent URL.

    Example:
    /sv/alquiler/<municipio>/<slug>/<id>
    -> /sv/venta/<property_type>/<municipio>/<slug>/<id>
    """
    try:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 5 or parts[0] != "sv" or parts[1] != "alquiler":
            return None

        municipio = parts[2]
        slug = parts[3]
        listing_id = parts[4]
        if not listing_id.isdigit():
            return None

        property_type = infer_propilatam_property_type(slug)
        return f"{PROPILATAM_BASE_URL}/sv/venta/{property_type}/{municipio}/{slug}/{listing_id}"
    except Exception:
        return None


def build_propilatam_rent_variant_url(url):
    """
    Build a rent-route variant from a Propi sale URL.

    Example:
    /sv/venta/<property_type>/<municipio>/<slug>/<id>
    -> /sv/alquiler/<municipio>/<slug>/<id>
    """
    try:
        parsed = urlparse(url)
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 6 or parts[0] != "sv" or parts[1] != "venta":
            return None

        municipio = parts[-3]
        slug = parts[-2]
        listing_id = parts[-1]
        if not listing_id.isdigit():
            return None

        return f"{PROPILATAM_BASE_URL}/sv/alquiler/{municipio}/{slug}/{listing_id}"
    except Exception:
        return None


def build_propilatam_candidate_urls(url):
    """Return preferred URL candidates for one Propi listing (sale first, rent fallback)."""
    candidates = []

    def add(candidate):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    url_l = (url or "").lower()
    if "/sv/alquiler/" in url_l:
        add(build_propilatam_sale_variant_url(url))
        add(url)
    elif "/sv/venta/" in url_l:
        add(url)
        add(build_propilatam_rent_variant_url(url))
    else:
        add(url)

    return candidates


def dedupe_propilatam_urls_by_id(urls):
    """
    De-duplicate Propi URLs by numeric listing ID, preferring sale routes.

    Returns:
        (deduped_urls, sale_replacements)
    """
    selected_by_id = {}
    ordered_ids = []
    sale_replacements = 0

    for url in urls:
        id_match = re.search(r"/(\d+)/?$", url or "")
        listing_key = id_match.group(1) if id_match else f"url::{url}"

        existing = selected_by_id.get(listing_key)
        if existing is None:
            selected_by_id[listing_key] = url
            ordered_ids.append(listing_key)
            continue

        existing_is_sale = "/sv/venta/" in existing.lower()
        candidate_is_sale = "/sv/venta/" in (url or "").lower()
        if candidate_is_sale and not existing_is_sale:
            selected_by_id[listing_key] = url
            sale_replacements += 1

    return [selected_by_id[k] for k in ordered_ids], sale_replacements


def get_propilatam_visibility_flag(raw_html):
    """
    Extract Propi visibility flag from embedded payload.

    Returns:
        True / False when flag is present, otherwise None.
    """
    if not raw_html:
        return None

    # Matches both escaped and unescaped forms:
    # "isPropertyVisible":false
    # \"isPropertyVisible\":false
    m = re.search(r'\\\\?"isPropertyVisible\\\\?"\s*:\s*(true|false)', raw_html, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).lower() == "true"


def get_propilatam_listing_status(url, headers):
    """
    Validate Propi listing activity across sale/rent variants for the same ID.

    Returns:
        dict with:
            is_active (bool)
            reason (str)
            resolved_url (str)
            resolved_listing_type ("sale"|"rent"|None)
    """
    candidate_urls = build_propilatam_candidate_urls(url)
    if not candidate_urls:
        return {
            "is_active": False,
            "reason": "No Propi URL candidates",
            "resolved_url": url,
            "resolved_listing_type": None,
        }

    challenge_signals = [
        "just a moment",
        "cloudflare",
        "captcha",
        "access denied",
        "temporarily unavailable",
    ]

    last_unavailable_reason = "No active Propi variant found"

    for candidate_url in candidate_urls:
        try:
            resp = requests.get(candidate_url, headers=headers, timeout=20, allow_redirects=True)
        except requests.exceptions.Timeout:
            return {
                "is_active": True,
                "reason": "Timeout (assumed active)",
                "resolved_url": url,
                "resolved_listing_type": None,
            }
        except requests.exceptions.ConnectionError:
            return {
                "is_active": True,
                "reason": "Connection error (assumed active)",
                "resolved_url": url,
                "resolved_listing_type": None,
            }
        except Exception:
            continue

        if resp.status_code == 403:
            return {
                "is_active": True,
                "reason": "403 Forbidden (assumed active - bot blocked)",
                "resolved_url": url,
                "resolved_listing_type": None,
            }
        if resp.status_code in (404, 410):
            last_unavailable_reason = f"{resp.status_code} on variant"
            continue
        if resp.status_code >= 400:
            return {
                "is_active": True,
                "reason": f"HTTP {resp.status_code} (assumed active)",
                "resolved_url": url,
                "resolved_listing_type": None,
            }

        raw_html = resp.text

        visibility_flag = get_propilatam_visibility_flag(raw_html)
        if visibility_flag is False:
            last_unavailable_reason = "isPropertyVisible=false (listing unavailable)"
            continue

        soup = BeautifulSoup(raw_html, "html.parser")
        for tag in soup(["script", "style", "template"]):
            tag.decompose()

        page_snapshot = get_propilatam_page_snapshot(raw_html, soup=soup)
        title_text = page_snapshot["page_title"].lower()
        h1_text = page_snapshot["h1_text"].lower()
        challenge_text = " ".join(
            part for part in (title_text, h1_text, page_snapshot["body_prefix_lower"]) if part
        )

        if any(sig in challenge_text for sig in challenge_signals):
            return {
                "is_active": True,
                "reason": "Challenge/blocked page (assumed active)",
                "resolved_url": url,
                "resolved_listing_type": None,
            }

        page_issue = get_propilatam_page_issue(raw_html, soup=soup)
        if page_issue == "listing unavailable":
            last_unavailable_reason = "Page says listing is unavailable"
            continue
        if page_issue == "placeholder page":
            last_unavailable_reason = "Placeholder page"
            continue

        has_embedded_code = bool(re.search(r'\\\\?"code\\\\?"\s*:\s*\d+', raw_html))
        has_embedded_name = bool(re.search(r'\\\\?"name\\\\?"\s*:\s*\\\\?"[^"]+', raw_html))
        if not page_snapshot["display_title"] and not (has_embedded_code and has_embedded_name):
            last_unavailable_reason = "No title/content found (likely inactive)"
            continue

        resolved_url = resp.url if resp.url else candidate_url
        resolved_type = "sale" if "/sv/venta/" in resolved_url.lower() else "rent"

        if resolved_url != url:
            return {
                "is_active": True,
                "reason": f"Active via {resolved_type} variant",
                "resolved_url": resolved_url,
                "resolved_listing_type": resolved_type,
            }

        return {
            "is_active": True,
            "reason": "Active",
            "resolved_url": resolved_url,
            "resolved_listing_type": resolved_type,
        }

    return {
        "is_active": False,
        "reason": last_unavailable_reason,
        "resolved_url": url,
        "resolved_listing_type": None,
    }


def check_propilatam_listing_still_active(url, headers):
    status = get_propilatam_listing_status(url, headers)
    return status["is_active"], status["reason"]


def get_propilatam_listing_urls(url_file=None, max_listings=None):
    """
    Collect listing URLs from Propi Latam sitemap.
    
    Fetches property URLs from the Propi Latam sitemap. If a URL file is provided,
    it will use that instead of the sitemap.
    
    Args:
        url_file: Optional path to file containing property URLs (one per line)
        max_listings: Maximum number of listings to return
        
    Returns:
        List of property page URLs
    """
    all_urls = []
    from_file = bool(url_file and os.path.exists(url_file))
    
    # If URL file is provided, use it
    if from_file:
        print(f"  Reading Propi Latam URLs from file: {url_file}")
        with open(url_file, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if not url:
                    continue
                if url.startswith("https://www.propilatam.com"):
                    all_urls.append(url)
        print(f"    Found {len(all_urls)} URLs in file")
    else:
        # Fetch from sitemap automatically
        print(f"  Fetching Propi Latam URLs from sitemap...")
        sitemap_url = PROPILATAM_SITEMAP_URL
        
        try:
            resp = requests.get(sitemap_url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                # Extract only listing detail URLs with numeric IDs:
                # /sv/(venta|alquiler)/.../<numeric_id>
                urls = re.findall(r'<loc>(https://www\.propilatam\.com/sv/[^<]+)</loc>', resp.text)

                seen = set()
                filtered_urls = []
                for url in urls:
                    if "/sv/venta/" not in url and "/sv/alquiler/" not in url:
                        continue
                    if not re.search(r"/\d+/?$", url):
                        continue
                    if url in seen:
                        continue
                    seen.add(url)
                    filtered_urls.append(url)

                all_urls = filtered_urls
                print(f"    Found {len(all_urls)} Propi Latam listing URLs in sitemap")
            else:
                print(f"    Error fetching sitemap: HTTP {resp.status_code}")
                return []
        except Exception as e:
            print(f"    Error fetching sitemap: {e}")
            return []
    
    # De-duplicate exact URL repeats while preserving order.
    all_urls = list(dict.fromkeys(all_urls))

    # Keep one URL per listing ID (prefer sale route when both sale/rent exist).
    before_id_dedupe = len(all_urls)
    all_urls, sale_replacements = dedupe_propilatam_urls_by_id(all_urls)
    removed_by_id = before_id_dedupe - len(all_urls)
    if removed_by_id > 0:
        print(
            f"    De-duplicated Propi IDs: removed {removed_by_id} duplicates "
            f"(sale-preferred replacements: {sale_replacements})"
        )

    if max_listings and len(all_urls) > max_listings:
        print(f"  Limiting to {max_listings} listings")
        all_urls = all_urls[:max_listings]

    return all_urls


def extract_propilatam_date_from_html(raw_html):
    """
    Extract date fields from Propi Latam / Vivo Latam listing HTML.
    
    Pages embed listing data in Next.js RSC script chunks. We extract whichever
    date-like fields are present (datePublished, dateLastUpdated, updated_at, stats.days)
    directly from static HTML.
    
    Args:
        raw_html: The full HTML response text from requests.get()
    
    Returns:
        dict with 'published_date' (DD/MM/YYYY format) and 'days_on_site' (int or None)
        Returns empty dict if extraction fails.
    """
    result = {}
    
    try:
        # These pages commonly use escaped quotes in embedded JSON: \\\"key\\\":value
        # We need to match both escaped (\\") and unescaped (") quote formats
        
        # Extract "days on site" from stats JSON: \"stats\":{\"days\":255,...} or "stats":{"days":255,...}
        days_match = re.search(r'\\\\?"stats\\\\?"[:\s]*\{[^}]*\\\\?"days\\\\?"[:\s]*(\d+)', raw_html)
        if days_match:
            result['days_on_site'] = int(days_match.group(1))
        
        # Extract datePublished (Unix ms timestamp): \"datePublished\":1748300554000 or "datePublished":1748300554000
        pub_match = re.search(r'\\\\?"datePublished\\\\?"[:\s]*(\d{10,13})', raw_html)
        if pub_match:
            ts = int(pub_match.group(1))
            # Convert milliseconds to seconds if needed
            if ts > 9999999999:
                ts = ts / 1000
            pub_date = datetime.fromtimestamp(ts, timezone.utc)
            result['published_date'] = pub_date.strftime("%d/%m/%Y")
        
        # Fallback: calculate from days_on_site if no datePublished
        if 'published_date' not in result and 'days_on_site' in result:
            pub_date = datetime.now() - timedelta(days=result['days_on_site'])
            result['published_date'] = pub_date.strftime("%d/%m/%Y")
        
        # Also extract dateLastUpdated for potential future use
        upd_match = re.search(r'\\\\?"dateLastUpdated\\\\?"[:\s]*(\d{10,13})', raw_html)
        if upd_match:
            ts = int(upd_match.group(1))
            if ts > 9999999999:
                ts = ts / 1000
            result['date_last_updated'] = datetime.fromtimestamp(ts, timezone.utc).strftime("%d/%m/%Y")

        # PropiLatam commonly exposes updated_at as Unix ms timestamp.
        # Use it as a fallback when explicit publish timestamps are missing.
        propi_updated_match = re.search(r'\\\\?"updated_at\\\\?"[:\s]*(\d{10,13})', raw_html)
        if propi_updated_match:
            ts = int(propi_updated_match.group(1))
            if ts > 9999999999:
                ts = ts / 1000
            updated_date = datetime.fromtimestamp(ts, timezone.utc).strftime("%d/%m/%Y")
            result.setdefault('published_date', updated_date)
            result.setdefault('date_last_updated', updated_date)
    except Exception as e:
        print(f"  Date extraction from HTML failed: {e}")
    
    return result


def normalize_propilatam_location_phrase(location):
    """Clean generic title-derived phrases like 'venta en X' into just 'X'."""
    cleaned = normalize_source_text(location)
    if not cleaned:
        return ""

    cleaned = re.sub(
        r'^(?:(?:compra\s+en\s+preventa)|(?:venta|alquiler|renta|sale|rent)(?:\s+(?:y|o)\s+(?:venta|alquiler|renta|sale|rent))?)\s+en\s+',
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip(" ,|-")


def extract_propilatam_location_from_meta_description(meta_description):
    """Recover location from Propi/Vivo meta descriptions when the page body is sparse."""
    cleaned = normalize_source_text(meta_description)
    if not cleaned:
        return ""

    patterns = [
        r'\bdesde\s+\$?[\d,.]+\s+en\s+(.+?)(?:[.;]|$)',
        r'ubicad[oa]\s+en\s+(.+?)(?:[.;]|$)',
        r'\ben\s+(.+?)(?:[.;]|$)',
    ]
    for pattern in patterns:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if not match:
            continue

        location = normalize_propilatam_location_phrase(match.group(1))
        location = re.sub(r",?\s*el salvador\s*$", "", location, flags=re.IGNORECASE).strip(" ,|-")
        if location:
            return location

    return ""


def extract_propilatam_main_description(main_text):
    """Extract the visible description block from a Propi/Vivo main content string."""
    cleaned = normalize_source_text(main_text)
    if not cleaned:
        return ""

    match = re.search(
        r'Descripci(?:ó|o)n\s+(.*?)(?=Contactar con el vendedor|Solicita m(?:á|a)s informaci(?:ó|o)n|Ubicaci(?:ó|o)n|$)',
        cleaned,
        re.IGNORECASE | re.DOTALL,
    )
    if not match:
        return ""

    description = normalize_source_text(match.group(1))
    return description[:1000]


def extract_propilatam_location_context(main_text):
    """Extract structured location labels from Propi/Vivo visible page content."""
    cleaned = normalize_source_text(main_text)
    if not cleaned:
        return "", {}

    location_blob = cleaned
    location_markers = list(re.finditer(r'Ubicaci(?:ó|o)n\s+', cleaned, re.IGNORECASE))
    if location_markers:
        location_blob = cleaned[location_markers[-1].start():]

    details = {}
    labels_pattern = re.compile(
        r'(Ubicaci(?:ó|o)n|Barrio|Distrito urbano|Distrito municipal|Municipio|Departamento|Pa(?:í|i)s)\s+(.*?)(?=(?:Ubicaci(?:ó|o)n|Barrio|Distrito urbano|Distrito municipal|Municipio|Departamento|Pa(?:í|i)s)\s|$)',
        re.IGNORECASE | re.DOTALL,
    )

    label_aliases = {
        "ubicacion": "Ubicación",
        "barrio": "Barrio",
        "distrito urbano": "Distrito urbano",
        "distrito municipal": "Distrito municipal",
        "municipio": "Municipio",
        "departamento": "Departamento",
        "pais": "País",
    }

    for label, value in labels_pattern.findall(location_blob):
        normalized_label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode("ascii").lower()
        canonical_label = label_aliases.get(normalized_label)
        if not canonical_label:
            continue

        cleaned_value = normalize_source_text(value)
        if canonical_label == "Departamento":
            cleaned_value = re.sub(r"^de\s+", "", cleaned_value, flags=re.IGNORECASE)
        if not cleaned_value:
            continue
        details[canonical_label] = cleaned_value

    explicit_department_match = re.search(
        r'Departamento\s+de\s+(.+?)\s+Departamento(?:\s+|$)',
        location_blob,
        re.IGNORECASE,
    )
    if explicit_department_match:
        details["Departamento"] = normalize_source_text(explicit_department_match.group(1))

    country_match = re.search(r'(El Salvador)\s+Pa(?:í|i)s', location_blob, re.IGNORECASE)
    if country_match:
        details["País"] = normalize_source_text(country_match.group(1))

    location_parts = []
    for key in ("Ubicación", "Departamento", "Distrito municipal", "Municipio", "Barrio"):
        value = normalize_source_text(details.get(key))
        if not value or value.lower() == "el salvador":
            continue
        if value.lower() not in [existing.lower() for existing in location_parts]:
            location_parts.append(value)
        if len(location_parts) >= 2:
            break

    return ", ".join(location_parts), details


def scrape_propilatam_listing(url, listing_type="sale"):
    """Scrape a single Propi Latam listing page."""
    try:
        original_url = url
        candidate_urls = build_propilatam_candidate_urls(original_url)
        if not candidate_urls:
            print(f"  No Propi candidates for {original_url}")
            return None

        selected_url = None
        selected_html = ""
        selected_soup = None
        title = ""

        for candidate_url in candidate_urls:
            try:
                resp = requests.get(candidate_url, headers=HEADERS, timeout=15, allow_redirects=True)
            except Exception:
                continue

            if resp.status_code != 200:
                continue

            candidate_html = resp.text

            visibility_flag = get_propilatam_visibility_flag(candidate_html)
            if visibility_flag is False:
                continue

            candidate_soup = BeautifulSoup(candidate_html, "html.parser")
            page_issue = get_propilatam_page_issue(candidate_html, soup=candidate_soup)
            if page_issue:
                continue

            page_snapshot = get_propilatam_page_snapshot(candidate_html, soup=candidate_soup)
            candidate_title = page_snapshot["display_title"]
            candidate_text_lower = page_snapshot["body_prefix_lower"]

            if any(
                marker in candidate_text_lower
                for marker in (
                    "no se encuentra disponible",
                    "página no encontrada",
                    "pagina no encontrada",
                    "no se encontró este anuncio",
                    "no se encontro este anuncio",
                )
            ):
                continue

            if not candidate_title:
                continue

            if "undefined" in normalize_source_text(candidate_title).lower():
                continue

            selected_url = resp.url if resp.url else candidate_url
            selected_html = candidate_html
            selected_soup = candidate_soup
            title = candidate_title
            break

        if not selected_url or not selected_soup:
            listing_id_match = re.search(r"/(\d+)/?$", original_url or "")
            listing_id = listing_id_match.group(1) if listing_id_match else "unknown-id"
            print(f"  No active Propi variant found for ID {listing_id}: {original_url}")
            return None

        if selected_url != original_url:
            listing_id_match = re.search(r"/(\d+)/?$", selected_url)
            listing_id = listing_id_match.group(1) if listing_id_match else "unknown-id"
            selected_kind = "sale" if "/sv/venta/" in selected_url.lower() else "rent"
            print(f"  Variant selected for {listing_id}: {selected_kind}")

        url = selected_url
        soup = selected_soup
        page_text = soup.get_text()
        raw_html = selected_html
        main_el = soup.find("main")
        main_text = normalize_source_text(main_el.get_text(" ", strip=True) if main_el else page_text)

        # Price extraction - prefer Propi's explicit minimum/base price fields.
        # Project pages often include many unrelated prices (similar projects,
        # calculators, unit variants), so generic "$123,456" regexes can drift.
        price = None

        # NOTE: PropiLatam/VivoLatam HTML often uses escaped quotes like \".
        if not price:
            structured_price_patterns = [
                r'\\"min_base_price\\"\s*:\s*(\d+)',
                r'"min_base_price"\s*:\s*(\d+)',
                r'\\"min_unit_price\\":\\"\$\$?([\d,.]+)\\"',
                r'"min_unit_price"\s*:\s*"\$\$?([\d,.]+)"',
                r'\\"base_price\\":\\"\$\$?([\d,.]+)\\"',
                r'"base_price"\s*:\s*"\$\$?([\d,.]+)"',
                r'\\"base_price\\"\s*:\s*(\d+)',
                r'"base_price"\s*:\s*(\d+)',
            ]
            for pattern in structured_price_patterns:
                match = re.search(pattern, raw_html)
                if not match:
                    continue
                parsed = parse_price(match.group(1))
                if parsed:
                    price = int(parsed)
                    break

        if not price:
            # Pattern 0: direct escaped price string used by PropiLatam:
            # \"price\":\"$$1,500.00\"
            price_match_direct = re.search(r'\\"price\\":\\"\$\$?([\d,.]+)\\"', raw_html)
            if not price_match_direct:
                # Unescaped fallback
                price_match_direct = re.search(r'"price"\s*:\s*"\$\$?([\d,.]+)"', raw_html)
            if price_match_direct:
                try:
                    price = int(float(price_match_direct.group(1).replace(",", "")))
                except Exception:
                    pass

        if not price:
            # Pattern 1: Escaped nested JSON format.
            # Sale: \"sale\":{\"value\":585000}
            # Rent: \"rent\":{\"period\":\"month\",\"value\":1800}  (note: has period field!)
            sale_price_match = re.search(r'\\"sale\\":\{\\"value\\":(\d+)', raw_html)
            # For rent, skip over the "period" field to find "value"
            rent_price_match = re.search(r'\\"rent\\":\{[^}]*\\"value\\":(\d+)', raw_html)

            if sale_price_match:
                price = int(sale_price_match.group(1))
            elif rent_price_match:
                price = int(rent_price_match.group(1))

        # Pattern 2: Non-escaped JSON (fallback for other formats)
        if not price:
            sale_match_alt = re.search(r'"sale"\s*:\s*\{\s*"value"\s*:\s*(\d+)', raw_html)
            # For rent, use flexible pattern to skip over period field
            rent_match_alt = re.search(r'"rent"\s*:\s*\{[^}]*"value"\s*:\s*(\d+)', raw_html)

            if sale_match_alt:
                price = int(sale_match_alt.group(1))
            elif rent_match_alt:
                price = int(rent_match_alt.group(1))


        # Fallback to Regex on visible text if no JSON match
        if not price:
            # First, check for "Millones" format (e.g., "$1.3 Millones" -> 1300000)
            # This is common on PropiLatam listings
            millones_patterns = [
                r'\$\s*([\d,.]+)\s*(?:millones|millon|mill)',  # $1.3 Millones
                r'([\d,.]+)\s*(?:millones|millon|mill)\s*(?:de\s*)?(?:dolares|usd|\$)?',  # 1.3 millones de dolares
            ]
            for pattern in millones_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    val_str = match.group(1).replace(',', '.')
                    try:
                        # Convert "1.3" to 1300000
                        price = int(float(val_str) * 1000000)
                        break
                    except:
                        pass
            
            # Check for "Mil" format (e.g., "$150 Mil" -> 150000)
            if not price:
                mil_patterns = [
                    r'\$\s*([\d,.]+)\s*mil\b',  # $150 Mil
                    r'([\d,.]+)\s*mil\s*(?:dolares|usd|\$)',  # 150 mil dolares
                ]
                for pattern in mil_patterns:
                    match = re.search(pattern, page_text, re.IGNORECASE)
                    if match:
                        val_str = match.group(1).replace(',', '.')
                        try:
                            # Convert "150" to 150000
                            price = int(float(val_str) * 1000)
                            break
                        except:
                            pass
            
            # Standard numeric patterns (fallback)
            if not price:
                # Patterns to look for price in text
                # 1. Standard $ format: $ 150,000 or $150.000
                # 2. USD format: USD 150,000
                # 3. Label format: Precio: $ 150,000
                price_patterns = [
                    r'\$\s*([\d,.]+)',
                    r'USD\s*([\d,.]+)',
                    r'US\$\s*([\d,.]+)',
                    r'Precio\s*[:]?\s*\$\s*([\d,.]+)'
                ]
                
                for pattern in price_patterns:
                    matches = re.finditer(pattern, page_text, re.IGNORECASE)
                    for match in matches:
                        val_str = match.group(1)
                        # Clean up: remove .00 at end, remove non-digits
                        cleaned = val_str.strip()
                        if cleaned.endswith('.00') or cleaned.endswith(',00'):
                            cleaned = cleaned[:-3]
                        
                        # Remove all non-digits to get integer value
                        digits_only = re.sub(r'[^\d]', '', cleaned)
                        
                        if digits_only and digits_only.isdigit():
                            candidate = int(digits_only)
                            # Filter out unreasonable values (e.g. "1" or small numbers that might be just noise)
                            # Property prices usually > 1000 (rent or sale)
                            if candidate >= 50: # Lowered threshold for rent
                                price = candidate
                                break
                    if price:
                        break
        
        # Specs from text
        specs = {}
        bedroom_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:dormitorio|habitaci)', page_text, re.I)
        bathroom_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:baño|bath)', page_text, re.I)
        parking_match = re.search(r'(\d+)\s*(?:parqueo|parking|estacionamiento|garaje|cochera)', page_text, re.I)
        area_match = re.search(r'([\d.,]+)\s*(m2|metros?\s*cuadrados?|m²|ft2|sqft|sq\s*ft|pies?\s*cuadrados?|v2|varas?\s*cuadradas?|varas?)', page_text, re.I)
        
        if bedroom_match:
            specs["habitaciones"] = bedroom_match.group(1)
        if bathroom_match:
            specs["banos"] = bathroom_match.group(1)
        if parking_match:
            specs["parqueo"] = parking_match.group(1)
        if area_match:
            specs["area"] = f"{area_match.group(1)} {area_match.group(2)}"

        # Structured fallbacks used by PropiLatam payloads.
        if "habitaciones" not in specs:
            rooms_match = re.search(r'\\\\?"rooms\\\\?"\s*:\s*\\\\?"([\d.]+)', raw_html)
            if rooms_match:
                specs["habitaciones"] = rooms_match.group(1)
        if "banos" not in specs:
            baths_match = re.search(r'\\\\?"bathrooms\\\\?"\s*:\s*\\\\?"([\d.]+)', raw_html)
            if baths_match:
                specs["banos"] = baths_match.group(1)
        if "parqueo" not in specs:
            parking_match_structured = re.search(r'\\\\?"parkings\\\\?"\s*:\s*\\\\?"([\d.]+)', raw_html)
            if parking_match_structured:
                specs["parqueo"] = parking_match_structured.group(1)
        if "area" not in specs:
            area_match_structured = re.search(r'\\\\?"area\\\\?"\s*:\s*\\\\?"([\d.]+)', raw_html)
            if area_match_structured:
                specs["area"] = f"{area_match_structured.group(1)} m2"
        
        # Description - look for content after "Descripción" heading
        description = extract_propilatam_main_description(main_text)
        desc_section = soup.find("h2", string=re.compile(r"Descripci[oó]n", re.I))
        if not description and desc_section:
            # Get next siblings for description content
            next_el = desc_section.find_next_sibling()
            if next_el:
                description = next_el.get_text(strip=True)[:1000]
        
        og_desc = soup.find("meta", {"property": "og:description"})
        meta_description = normalize_source_text(og_desc.get("content")) if og_desc and og_desc.get("content") else ""

        # If no description from heading, try meta description
        if not description and meta_description:
            description = meta_description[:1000]
        
        # Location from title, breadcrumbs, and URL path.
        location = ""
        if title:
            title_loc_match = re.search(r'\ben\s+([^,]+(?:,\s*[^,]+)?)', title, re.IGNORECASE)
            if title_loc_match:
                location = normalize_propilatam_location_phrase(title_loc_match.group(1).strip())

        structured_location, location_details = extract_propilatam_location_context(main_text)
        if structured_location and (
            not location
            or location.lower().startswith(("venta en ", "alquiler en ", "renta en ", "sale in ", "rent in "))
            or (structured_location.lower().startswith(location.lower()) and len(structured_location) > len(location))
        ):
            location = structured_location

        meta_location = extract_propilatam_location_from_meta_description(meta_description)
        if meta_location and (
            not location
            or location.lower() in ("programar asesoría", "programar asesoria", "elegir unidad", "ver disponibles")
        ):
            location = meta_location

        if not location:
            loc_links = soup.select('a[href*="/bienes-raices/m/"], a[href*="/sv/venta/"], a[href*="/sv/alquiler/"]')
            if loc_links:
                # Get location from first valid link after the base
                for link in loc_links:
                    link_text = link.get_text(strip=True)
                    link_text_lc = link_text.lower() if link_text else ""
                    if not link_text:
                        continue
                    # Skip navigation/menu labels that are not geographic locations.
                    if link_text_lc in ("el salvador bienes raices", "el salvador"):
                        continue
                    if any(token in link_text_lc for token in (
                        "quiero ",
                        "comprar",
                        "alquilar",
                        "vender",
                        "publicar",
                        "iniciar",
                        "registrar",
                        "visita",
                        "programar",
                        "asesor",
                        "asesoría",
                        "asesoria",
                        "elegir unidad",
                        "ver disponibles",
                        "disponibles",
                    )):
                        continue
                    if len(link_text_lc) < 3:
                        continue
                    location = normalize_propilatam_location_phrase(link_text)
                    break

        if not location:
            try:
                path_parts = [p for p in urlparse(url).path.split("/") if p]
                # Expected patterns:
                # /sv/alquiler/<municipio>/<slug>/<id>
                # /sv/venta/<property_type>/<municipio>/<slug>/<id>
                if len(path_parts) >= 4 and path_parts[0] == "sv" and path_parts[1] in ("venta", "alquiler"):
                    municipality_segment = ""
                    if path_parts[1] == "alquiler":
                        municipality_segment = path_parts[2]
                    elif len(path_parts) >= 5:
                        municipality_segment = path_parts[3]
                    else:
                        municipality_segment = path_parts[2]

                    location = normalize_propilatam_location_phrase(
                        unquote(municipality_segment).replace("-", " ").strip().title()
                    )
            except Exception:
                pass

        # Prefer numeric external_id from URL tail. Fallback to slug hash.
        id_match = re.search(r'/(\d+)/?$', url)
        if id_match:
            external_id = int(id_match.group(1))
        else:
            slug = url.rstrip('/').split('/')[-1]
            external_id = slug_to_external_id(slug)
        
        # Images from og:image meta tag and other sources
        images = []
        og_image = soup.find("meta", {"property": "og:image"})
        if og_image and og_image.get("content"):
            images.append(og_image["content"])

        # PropiLatam embeds full gallery URLs in script payloads.
        gallery_urls = re.findall(
            r'https://storage\.googleapis\.com/assets-us-east4-propilatam/properties/[^"\\\']+',
            raw_html
        )
        for img_url in gallery_urls:
            if img_url not in images:
                images.append(img_url)
            if len(images) >= 20:
                break
        
        # Also look for other image sources
        for img in soup.find_all("img"):
            src = img.get("src", "") or img.get("data-src", "")
            if src and ("cdn.vivolatam.com" in src or "assets-us-east4-propilatam" in src) and src not in images:
                images.append(src)
                if len(images) >= 20:  # Cap at 20 images
                    break
        
        # Extract published/updated date from embedded Next.js RSC data in static HTML
        # The datePublished, dateLastUpdated, and stats.days are embedded in script tags
        # No Playwright/Selenium needed — pure regex on the already-fetched HTML
        published_date = ""
        date_data = extract_propilatam_date_from_html(raw_html)
        if date_data.get('published_date'):
            published_date = date_data['published_date']
        
        # Extract coordinates from embedded RSC data
        # Patterns:
        # 1) "coords":[LAT,LNG]
        # 2) "center":[LAT,LNG]
        # 3) "lat":LAT,"lng":LNG (commonly used by PropiLatam)
        latitude = None
        longitude = None
        coord_match = re.search(r'\\"coords\\"\s*:\s*\[\s*(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*\]', raw_html)
        if not coord_match:
            coord_match = re.search(r'\\"center\\"\s*:\s*\[\s*(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*\]', raw_html)
        if not coord_match:
            coord_match = re.search(
                r'\\\\?"lat\\\\?"\s*:\s*(-?\d{1,3}\.\d+)\s*,\s*\\\\?"lng\\\\?"\s*:\s*(-?\d{1,3}\.\d+)',
                raw_html
            )
        if coord_match:
            try:
                latitude = float(coord_match.group(1))
                longitude = float(coord_match.group(2))
            except (ValueError, TypeError):
                pass
        
        # Detect listing type from URL/title.
        # Important: avoid naive "sale" substring checks because "salvador" contains "sale".
        title_lower = title.lower()
        url_lower = url.lower()
        has_sale = (
            "venta" in title_lower
            or "/venta/" in url_lower
            or "/sale/" in url_lower
            or "-venta-" in url_lower
            or "-sale-" in url_lower
        )
        has_rent = (
            "alquiler" in title_lower
            or "renta" in title_lower
            or "/alquiler/" in url_lower
            or "/renta/" in url_lower
            or "/rent/" in url_lower
            or "-alquiler-" in url_lower
            or "-renta-" in url_lower
            or "-rent-" in url_lower
        )
        if has_sale and not has_rent:
            listing_type = "sale"
        elif has_rent and not has_sale:
            listing_type = "rent"
        else:
            listing_type = infer_listing_type_from_url(url, default_type=listing_type or "sale")
        
        # Correct listing_type based on content analysis (title, description, price)
        price_value = parse_price(price)
        listing_type = correct_listing_type(listing_type, title, description, price_value, url=url)
        
        # Detect municipality
        municipio_info = detect_municipio(location, description, title)
        
        listing = {
            "title": remove_emojis(title[:200]) if title else "",
            "price": price,
            "location": location,
            "published_date": published_date,  # Extracted from "Anuncio actualizado" text
            "listing_type": listing_type,
            "url": url,
            "external_id": str(external_id),
            "specs": normalize_listing_specs(specs),  # Normalize specs (area, beds, baths, etc.)
            "details": location_details,
            "description": remove_emojis(description) if description else "",
            "images": images,
            "source": "PropiLatam",
            "active": True,
            "municipio_detectado": municipio_info["municipio_detectado"],
            "departamento": municipio_info["departamento"],
            "latitude": latitude,
            "longitude": longitude,
            "last_updated": datetime.now().isoformat()
        }
        
        print(f"  Scraped: {title[:50]}...")
        return listing
        
    except Exception as e:
        print(f"  Error scraping {url}: {e}")
        return None


def scrape_propilatam_listings_concurrent(urls, listing_type="auto", max_workers=5, max_days=None):
    """Scrape multiple Propi Latam listings concurrently with optional date filtering.
    
    Args:
        urls: List of listing URLs
        listing_type: 'sale', 'rent', or 'auto' (infer from URL)
        max_workers: Number of concurrent workers
        max_days: Maximum age of listings in days. None or 0 = no filtering.
        
    Returns:
        Tuple of (results, old_listing_count)
    """
    results = []
    old_listing_count = 0
    total_urls = len(urls)
    completed_count = 0
    started_at = time.time()
    progress_every = 25 if total_urls >= 250 else 10
    
    print(f"  Scraping {total_urls} Propi Latam listings with {max_workers} workers...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {}
        for url in urls:
            effective_type = listing_type
            if listing_type == "auto":
                effective_type = infer_listing_type_from_url(url, default_type="sale")
            future = executor.submit(scrape_propilatam_listing, url, effective_type)
            future_to_url[future] = url
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            completed_count += 1
            try:
                result = future.result()
                if result:
                    # Check date if filtering is enabled
                    if max_days and max_days > 0:
                        published_date = result.get("published_date") or result.get("details", {}).get("Publicado")
                        is_within_range, _ = is_listing_within_date_range(published_date, max_days)
                        if not is_within_range:
                            old_listing_count += 1
                            continue
                    results.append(result)
            except Exception as e:
                print(f"  Error processing {url}: {e}")
            finally:
                if completed_count % progress_every == 0 or completed_count == total_urls:
                    elapsed = time.time() - started_at
                    print(
                        f"    Propi scrape progress: {completed_count}/{total_urls} "
                        f"(ok: {len(results)}, old-skipped: {old_listing_count}, elapsed: {elapsed:.1f}s)"
                    )
    
    return results, old_listing_count


def main_propilatam(limit=None, url_file=None, max_days=None):
    """Main scraper function for Propi Latam.
    
    Args:
        limit: Maximum number of listings to scrape
        url_file: Optional path to file containing URLs to scrape
        max_days: Maximum age of listings in days. None or 0 = no filtering.
    """
    all_listings = []
    sale_data = []
    rent_data = []
    
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} listings from Propi Latam ***")
    if max_days and max_days > 0:
        print(f"*** DATE FILTER: Only listings from last {max_days} days ***")
    
    # Get listing URLs from file
    urls = get_propilatam_listing_urls(url_file=url_file, max_listings=limit)
    
    if not urls:
        print("  No Propi Latam URLs found to scrape")
        return [], [], []
    
    print(f"\n=== Scraping Propi Latam Listings ===")
    listings, old_count = scrape_propilatam_listings_concurrent(urls, "auto", max_days=max_days)
    all_listings.extend(listings)
    
    if old_count > 0:
        print(f"  Skipped {old_count} old listings (>{max_days} days)")
    
    # Separate by listing type
    sale_data = [l for l in all_listings if l.get("listing_type") == "sale"]
    rent_data = [l for l in all_listings if l.get("listing_type") == "rent"]
    
    print(f"  Propi Latam total: {len(all_listings)} ({len(sale_data)} sales, {len(rent_data)} rentals)")
    
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

    if url_file and os.path.exists(url_file):
        print(f"  Reading Vivo Latam URLs from file: {url_file}")
        with open(url_file, "r", encoding="utf-8") as f:
            for line in f:
                url = line.strip()
                if url and url.startswith("https://www.vivolatam.com"):
                    all_urls.append(url)
        print(f"    Found {len(all_urls)} URLs in file")
    else:
        print("  Fetching Vivo Latam URLs from sitemap...")
        sitemap_url = "https://www.vivolatam.com/sitemap/property_listings.xml"

        try:
            resp = requests.get(sitemap_url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                urls = re.findall(r"<loc>(https://www\.vivolatam\.com/es/[^<]+/l/[^<]+)</loc>", resp.text)
                all_urls = list(set(urls))
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
    """
    Scrape a single Vivo Latam listing page.

    Uses the shared parser and then sets the source explicitly to VivoLatam.
    """
    listing = scrape_propilatam_listing(url, listing_type=listing_type)
    if listing:
        listing["source"] = "VivoLatam"
    return listing


def scrape_vivolatam_listings_concurrent(urls, listing_type="sale", max_workers=5, max_days=None):
    """Scrape multiple Vivo Latam listings concurrently with optional date filtering."""
    results = []
    old_listing_count = 0

    print(f"  Scraping {len(urls)} Vivo Latam listings with {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(scrape_vivolatam_listing, url, listing_type): url for url in urls}
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                if result:
                    if max_days and max_days > 0:
                        published_date = result.get("published_date") or result.get("details", {}).get("Publicado")
                        is_within_range, _ = is_listing_within_date_range(published_date, max_days)
                        if not is_within_range:
                            old_listing_count += 1
                            continue
                    results.append(result)
            except Exception as e:
                print(f"  Error processing {url}: {e}")

    return results, old_listing_count


def main_vivolatam(limit=None, url_file=None, max_days=None):
    """Main scraper function for Vivo Latam."""
    all_listings = []
    sale_data = []
    rent_data = []

    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} listings from Vivo Latam ***")
    if max_days and max_days > 0:
        print(f"*** DATE FILTER: Only listings from last {max_days} days ***")

    urls = get_vivolatam_listing_urls(url_file=url_file, max_listings=limit)

    if not urls:
        print("  No Vivo Latam URLs found to scrape")
        return [], [], []

    print("\n=== Scraping Vivo Latam Listings ===")
    listings, old_count = scrape_vivolatam_listings_concurrent(urls, "sale", max_days=max_days)
    all_listings.extend(listings)

    if old_count > 0:
        print(f"  Skipped {old_count} old listings (>{max_days} days)")

    sale_data = [l for l in all_listings if l.get("listing_type") == "sale"]
    rent_data = [l for l in all_listings if l.get("listing_type") == "rent"]

    print(f"  Vivo Latam total: {len(all_listings)} ({len(sale_data)} sales, {len(rent_data)} rentals)")

    return all_listings, sale_data, rent_data


def log_source_failure(context, source_label, exc):
    """Log a source failure without aborting the entire scraper run."""
    print(f"  ERROR: {context} failed for {source_label}: {exc}")
    traceback.print_exc(limit=6)


def scrape_source_safely(source_label, source_key, scraper_func, *args, **kwargs):
    """Run one source scraper and convert exceptions into a structured result."""
    print("\n" + "=" * 60)
    print(f"SCRAPING SOURCE: {source_label}")
    print("=" * 60)

    try:
        listings, sale_data, rent_data = scraper_func(*args, **kwargs)
        return {
            "source_key": source_key,
            "source_label": source_label,
            "listings": listings or [],
            "sale_data": sale_data or [],
            "rent_data": rent_data or [],
            "error": None,
        }
    except Exception as e:
        log_source_failure("scraper", source_label, e)
        return {
            "source_key": source_key,
            "source_label": source_label,
            "listings": [],
            "sale_data": [],
            "rent_data": [],
            "error": str(e),
        }


def main(
    encuentra24=True,
    micasasv=False,
    nexo=False,
    realtor=False,
    realtyelsalvador=False,
    casasahorita=False,
    camarabienesraices=False,
    vivolatam=False,
    propilatam=False,
    limit=None,
    vivolatam_urls=None,
    propilatam_urls=None,
    skip_validation=False,
    max_days=None
):
    """
    Main scraper function that orchestrates scraping from multiple sources.
    
    Args:
        encuentra24: If True, scrape from Encuentra24
        micasasv: If True, scrape from MiCasaSV
        nexo: If True, scrape from Nexo
        realtor: If True, scrape from Realtor.com International
        realtyelsalvador: If True, scrape from Realty El Salvador
        casasahorita: If True, scrape from Casas Ahorita
        camarabienesraices: If True, scrape from Camara Bienes Raices
        vivolatam: If True, scrape from Vivo Latam
        propilatam: If True, scrape from Propi Latam
        limit: Optional max number of listings to scrape (per source if both enabled)
        vivolatam_urls: Path to file containing Vivo Latam URLs to scrape
        propilatam_urls: Path to file containing Propi Latam URLs to scrape
        skip_validation: If True, skip the validation phase (checking for inactive listings)
        max_days: Maximum age of listings in days. None or 0 = no filtering.
    """
    # Record start time for validation phase (to identify stale listings)
    run_start_time = datetime.now().isoformat()
    print(f"Scrape run started at: {run_start_time}")
    
    if max_days and max_days > 0:
        print(f"Date filter enabled: Only scraping listings from last {max_days} days")
    
    all_listings = []
    total_sale = 0
    total_rent = 0
    run_scraped_external_ids = set()
    
    # Track which sources we're scraping (for targeted validation)
    active_sources = []
    failed_sources = []
    source_jobs = []

    if encuentra24:
        source_jobs.append(("Encuentra24", "Encuentra24", main_encuentra24, (limit,), {"max_days": max_days}))
    if micasasv:
        source_jobs.append(("MiCasaSV", "MiCasaSV", main_micasasv, (limit,), {"max_days": max_days}))
    if nexo:
        source_jobs.append(("Nexo", NEXO_SOURCE, main_nexo, (limit,), {"max_days": max_days}))
    if realtor:
        source_jobs.append(("Realtor.com International", "Realtor", main_realtor, (limit,), {"max_days": max_days}))
    if realtyelsalvador:
        source_jobs.append(("Realty El Salvador", REALTYELSALVADOR_SOURCE, main_realtyelsalvador, (limit,), {"max_days": max_days}))
    if casasahorita:
        source_jobs.append(("Casas Ahorita", CASASAHORITA_SOURCE, main_casasahorita, (limit,), {"max_days": max_days}))
    if camarabienesraices:
        source_jobs.append(("Camara Bienes Raices", CAMARABIENESRAICES_SOURCE, main_camarabienesraices, (limit,), {"max_days": max_days}))
    if vivolatam:
        source_jobs.append(("Vivo Latam", "VivoLatam", main_vivolatam, (limit,), {"url_file": vivolatam_urls, "max_days": max_days}))
    if propilatam:
        source_jobs.append(("Propi Latam", "PropiLatam", main_propilatam, (limit,), {"url_file": propilatam_urls, "max_days": max_days}))

    for source_label, source_key, scraper_func, args, kwargs in source_jobs:
        result = scrape_source_safely(source_label, source_key, scraper_func, *args, **kwargs)
        if result["error"]:
            failed_sources.append({
                "source": source_label,
                "error": result["error"],
            })
            continue

        active_sources.append(source_key)
        all_listings.extend(result["listings"])
        run_scraped_external_ids.update(collect_listing_external_ids(result["listings"]))
        total_sale += len(result["sale_data"])
        total_rent += len(result["rent_data"])

    if failed_sources:
        print("\n=== Source Failures ===")
        for failure in failed_sources:
            print(f"  - {failure['source']}: {failure['error']}")

    # --- INSERT TO SUPABASE ---
    print("\n=== Inserting to Supabase ===")
    success, errors = insert_listings_batch(all_listings)
    print(f"  Inserted: {success} | Errors: {errors}")
    
    # --- MATCH LOCATIONS ---
    # Use the raw scraped data (title, location, details, description) to match to sv_loc_group
    print("\n=== Matching Locations ===")
    try:
        loc_matched, loc_errors = get_match_scraped_listings()(
            all_listings,
            SUPABASE_URL,
            SUPABASE_SERVICE_KEY,
        )
    except Exception as e:
        loc_matched, loc_errors = 0, len(all_listings)
        print(f"  Warning: Location matching skipped due to error: {e}")
    print(f"  Location matches: {loc_matched} | Errors: {loc_errors}")

    # --- ALSO SAVE JSON (backup) ---
    output_file = os.path.join(DATA_DIR, "listings_all_sources.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_listings, f, ensure_ascii=False, indent=2)

    # --- VALIDATION PHASE: Check for inactive listings ---
    # Skip validation if --limit is used (partial scrape) or --skip-validation flag
    validated_count = 0
    deactivated_count = 0
    if not skip_validation and limit is None:
        if active_sources:
            validated_count, deactivated_count = validate_and_deactivate_listings(
                run_start_time,
                sources=active_sources,
                exclude_external_ids=run_scraped_external_ids,
            )
        else:
            print("\n=== Skipping validation phase (no sources completed successfully) ===")
    else:
        skip_reason = "--limit flag" if limit else "--skip-validation flag"
        print(f"\n=== Skipping validation phase ({skip_reason}) ===")

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
    if not skip_validation:
        print(f"Validation: {validated_count} checked, {deactivated_count} deactivated")
    if failed_sources:
        print(f"Sources failed but run continued: {len(failed_sources)}")
    print(f"JSON backup: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-source real estate scraper (Encuentra24, MiCasaSV, Nexo, Realtor.com, Realty El Salvador, Casas Ahorita, Camara Bienes Raices, Vivo Latam, Propi Latam)"
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
        "--Nexo",
        action="store_true",
        help="Scrape listings from Nexo"
    )
    parser.add_argument(
        "--Realtor",
        action="store_true",
        help="Scrape listings from Realtor.com International (El Salvador)"
    )
    parser.add_argument(
        "--RealtyElSalvador",
        action="store_true",
        help="Scrape listings from Realty El Salvador"
    )
    parser.add_argument(
        "--CasasAhorita",
        action="store_true",
        help="Scrape listings from Casas Ahorita"
    )
    parser.add_argument(
        "--CamaraBienesRaices",
        action="store_true",
        help="Scrape listings from Camara Bienes Raices (El Salvador)"
    )
    parser.add_argument(
        "--PropiLatam",
        action="store_true",
        help="Scrape listings from Propi Latam (El Salvador)"
    )
    parser.add_argument(
        "--VivoLatam",
        action="store_true",
        help="Scrape listings from Vivo Latam (El Salvador)"
    )
    parser.add_argument(
        "--propilatam-urls",
        dest="propilatam_urls",
        type=str,
        default=None,
        help="Optional: Path to file containing Propi Latam URLs to scrape. If not provided, URLs are fetched from sitemap."
    )
    parser.add_argument(
        "--vivolatam-urls",
        dest="vivolatam_urls",
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
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip the validation phase (checking for inactive/removed listings)"
    )
    parser.add_argument(
        "--max-days", "-d",
        type=int,
        default=None,
        help="Optional: Maximum age of listings in days (e.g., 7, 14, 30). Only scrape listings published within this many days. If not set, scrapes all listings regardless of age."
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update mode: re-scrape existing active listings from DB and update them (instead of scraping new listings)"
    )
    parser.add_argument(
        "--validate-all",
        action="store_true",
        help="Validate-all mode: check ALL active listings in DB to see if they are still live (lightweight HTTP check, no full re-scrape)"
    )
    parser.add_argument(
        "--update-actives", "--update_actives",
        dest="update_actives",
        action="store_true",
        help="Update-actives mode: only check current active listings and deactivate those that are no longer live (no scraping)"
    )
    args = parser.parse_args()
    
    # Get source flags
    encuentra24 = args.Encuentra24
    micasasv = args.MiCasaSV
    nexo = args.Nexo
    realtor = args.Realtor
    realtyelsalvador = args.RealtyElSalvador
    casasahorita = args.CasasAhorita
    camarabienesraices = args.CamaraBienesRaices
    vivolatam = args.VivoLatam
    propilatam = args.PropiLatam
    
    # Build sources list for update mode
    sources = []
    if encuentra24:
        sources.append("Encuentra24")
    if micasasv:
        sources.append("MiCasaSV")
    if nexo:
        sources.append(NEXO_SOURCE)
    if realtor:
        sources.append("Realtor")
    if realtyelsalvador:
        sources.append(REALTYELSALVADOR_SOURCE)
    if casasahorita:
        sources.append(CASASAHORITA_SOURCE)
    if camarabienesraices:
        sources.append(CAMARABIENESRAICES_SOURCE)
    if vivolatam:
        sources.append("VivoLatam")
    if propilatam:
        sources.append("PropiLatam")
    
    # If no sources specified, use all
    if not sources:
        sources = None  # run_update_mode will use all sources
    
    # Check for active-status-only modes first (lightweight)
    if args.validate_all or args.update_actives:
        validate_all_active_listings(sources=sources, max_workers=10)
    elif args.update:
        # Update mode: re-scrape and update existing active listings
        run_update_mode(sources=sources, limit=args.limit, skip_validation=args.skip_validation)
    else:
        # Normal scrape mode
        # Default behavior: scrape from ALL sources if no source is specified
        if not encuentra24 and not micasasv and not nexo and not realtor and not realtyelsalvador and not casasahorita and not camarabienesraices and not vivolatam and not propilatam:
            encuentra24 = True
            micasasv = True
            nexo = True
            realtor = True
            realtyelsalvador = True
            casasahorita = True
            camarabienesraices = True
            vivolatam = True
            propilatam = True
            print("No source specified. Scraping from ALL sources: Encuentra24, MiCasaSV, Nexo, Realtor, RealtyElSalvador, CasasAhorita, CamaraBienesRaices, VivoLatam, PropiLatam")
        
        main(
            encuentra24=encuentra24, 
            micasasv=micasasv, 
            nexo=nexo,
            realtor=realtor, 
            realtyelsalvador=realtyelsalvador,
            casasahorita=casasahorita,
            camarabienesraices=camarabienesraices,
            vivolatam=vivolatam,
            propilatam=propilatam,
            limit=args.limit,
            vivolatam_urls=args.vivolatam_urls,
            propilatam_urls=args.propilatam_urls,
            skip_validation=args.skip_validation,
            max_days=args.max_days
        )


