"""
Multi-Source Housing Scraper - OPTIMIZED
Uses concurrent requests to scrape listings from Encuentra24, MiCasaSV, Realtor.com, Camara Bienes Raices, Vivo Latam, and Propi Latam.
Inserts results directly into Supabase database (scrappeddata_ingest table).

Usage:
  python scraper_encuentra24.py                             # Default: scrape ALL sources
  python scraper_encuentra24.py --Encuentra24 --limit 100   # Scrape 100 from Encuentra24 only
  python scraper_encuentra24.py --MiCasaSV --limit 10       # Scrape 10 from MiCasaSV only
  python scraper_encuentra24.py --Realtor --limit 50        # Scrape 50 from Realtor.com only
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
import unicodedata
from urllib.parse import unquote, urlparse
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import localization plugin for generating searchable tags
from localization_plugin import build_destination_queries

# Import area normalizer for standardizing area units to m²
from area_normalizer import normalize_listing_specs

# Import location matcher for matching scraped listings to sv_loc_group hierarchy
from match_locations import match_scraped_listings

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
    all_sources = ["Encuentra24", "MiCasaSV", "Realtor", CAMARABIENESRAICES_SOURCE, "PropiLatam", "VivoLatam"]
    if sources:
        sources_to_update = [s for s in sources if s in all_sources]
    else:
        sources_to_update = all_sources
    
    print(f"Sources to update: {', '.join(sources_to_update)}")
    
    total_updated = 0
    total_errors = 0
    total_deactivated = 0
    
    for source in sources_to_update:
        print(f"\n--- Processing {source} ---")
        
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
            print(f"  Inserting/updating database (DB trigger handles upsert)...")
            success, errors = insert_listings_batch(scraped_listings)
            total_updated += success
            total_errors += errors
            print(f"  {source}: {success} upserted, {errors} errors")
        else:
            print(f"  No listings scraped for {source}")

    # Match regular mode deactivation behavior: validate stale listings after upserts
    validated_count = 0
    if not skip_validation and limit is None:
        validated_count, deactivated_count = validate_and_deactivate_listings(
            run_start_time,
            sources=sources_to_update
        )
        total_deactivated += deactivated_count
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
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    try:
        if source == "PropiLatam":
            return check_propilatam_listing_still_active(url, headers)

        # Use GET to check the full page (some sites don't support HEAD properly)
        resp = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
        
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


def validate_and_deactivate_listings(run_start_time, sources=None, max_workers=5):
    """
    Validate all active listings that weren't updated in the current run.
    Marks listings as inactive if they return 404 or are sold/expired.
    
    Args:
        run_start_time: ISO timestamp of when the scrape run started
        sources: Optional list of sources to validate (None = all sources)
        max_workers: Number of concurrent validation requests
    
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
    all_source_names = ["Encuentra24", "MiCasaSV", "Realtor", CAMARABIENESRAICES_SOURCE, "PropiLatam", "VivoLatam"]
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
        property_type = str(details.get("property_type", "")).lower()
        
        # Map explicit property types to our categories
        if property_type in ["land", "lot", "lots"]:
            return "Terreno"
        elif property_type in ["apartment", "condo", "condominium", "flat"]:
            return "Apartamento"
        elif property_type in ["house", "home", "single family", "townhouse"]:
            return "Casa"
        elif property_type in ["commercial", "office", "retail", "warehouse"]:
            return "Local"
    
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

        # Price - extract from multiple sources and use the most complete one
        price = ""
        price_candidates = []
        
        # Source 1: Price element on page
        price_el = soup.select_one(".estate-price") or soup.select_one(".d3-price")
        if price_el:
            el_price = price_el.get_text(strip=True)
            if el_price:
                price_candidates.append(el_price)
        
        # Source 2: Look for price in title (common pattern: "por XXXXX.00")
        title_price_match = re.search(r'por\s+(?:USD\s+)?([\d,\.]+)', title, re.IGNORECASE)
        if title_price_match:
            price_candidates.append(f"${title_price_match.group(1)}")
        
        # Source 3: Look for $ price in title
        title_dollar_match = re.search(r'\$\s*([\d,\.]+)', title)
        if title_dollar_match:
            price_candidates.append(f"${title_dollar_match.group(1)}")
        
        # Source 4: Fallback - search full page text
        if not price_candidates:
            page_match = re.search(r"\$[\d,\.]+", soup.get_text())
            if page_match:
                price_candidates.append(page_match.group(0))
        
        # Choose the largest price (to get full price, not truncated display)
        best_price = 0
        for candidate in price_candidates:
            parsed = parse_price(candidate)
            if parsed and parsed > best_price:
                best_price = parsed
                price = candidate
        
        # If no named price found, use empty
        if not price and price_candidates:
            price = price_candidates[0]

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
        
        return {
            "title": title,
            "price": price,
            "location": location,
            "published_date": published_date,
            "listing_type": listing_type,
            "url": url,
            "external_id": str(external_id),
            "specs": normalize_listing_specs(specs),  # Normalize specs (area, beds, baths, etc.)
            "details": details,
            "description": description,
            "images": images,
            "source": "MiCasaSV",
            "active": True,
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
            
            # Extract description directly (available in JSON) - needed for correct_listing_type
            description = value.get("description", "")
            if description:
                description = remove_emojis(description[:1000])
            
            # Correct listing_type based on content analysis (title, description, price)
            price_value = parse_price(price_str)
            listing_type = correct_listing_type(listing_type, title, description, price_value, url=full_url)
            
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
            
            # Fallback: fetch detail page if published_date is still empty
            if not published_date and full_url:
                published_date = get_realtor_detail_published_date(full_url)
            
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
            
            # Extract coordinates from geoLocation in Apollo state
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
                "specs": normalize_listing_specs(specs),  # Normalize specs (area, beds, baths, etc.)
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
            })
        
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
    parts = []
    for taxonomy in ["property_area", "property_city", "property_state"]:
        for value in term_names.get(taxonomy, []):
            if value and value not in parts:
                parts.append(value)

    for meta_key in ["fave_property_location", "fave_property_map_address", "fave_property_address"]:
        value = cbr_get_meta_value(property_meta, meta_key)
        if value and value not in parts:
            parts.append(value)
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

        page_text = soup.get_text(" ", strip=True).lower()
        title_text = (soup.title.get_text(" ", strip=True).lower() if soup.title else "")
        h1_el = soup.select_one("h1")
        h1_text = h1_el.get_text(" ", strip=True).lower() if h1_el else ""

        if any(sig in page_text or sig in title_text for sig in challenge_signals):
            return {
                "is_active": True,
                "reason": "Challenge/blocked page (assumed active)",
                "resolved_url": url,
                "resolved_listing_type": None,
            }

        if "no se encuentra disponible" in page_text:
            last_unavailable_reason = "Page says listing is unavailable"
            continue

        has_embedded_code = bool(re.search(r'\\\\?"code\\\\?"\s*:\s*\d+', raw_html))
        has_embedded_name = bool(re.search(r'\\\\?"name\\\\?"\s*:\s*\\\\?"[^"]+', raw_html))
        if not h1_text and not (has_embedded_code and has_embedded_name):
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
            pub_date = datetime.fromtimestamp(ts)
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
            result['date_last_updated'] = datetime.fromtimestamp(ts).strftime("%d/%m/%Y")

        # PropiLatam commonly exposes updated_at as Unix ms timestamp.
        # Use it as a fallback when explicit publish timestamps are missing.
        propi_updated_match = re.search(r'\\\\?"updated_at\\\\?"[:\s]*(\d{10,13})', raw_html)
        if propi_updated_match:
            ts = int(propi_updated_match.group(1))
            if ts > 9999999999:
                ts = ts / 1000
            updated_date = datetime.fromtimestamp(ts).strftime("%d/%m/%Y")
            result.setdefault('published_date', updated_date)
            result.setdefault('date_last_updated', updated_date)
    except Exception as e:
        print(f"  Date extraction from HTML failed: {e}")
    
    return result


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
            candidate_text_lower = candidate_soup.get_text(" ", strip=True).lower()
            title_el = candidate_soup.find("h1")
            candidate_title = title_el.get_text(strip=True) if title_el else ""

            if "no se encuentra disponible" in candidate_text_lower:
                continue

            if not candidate_title:
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

        # Price extraction - prefer structured values from embedded JSON when available.
        price = None
        
        # Try multiple patterns for embedded JSON data
        # NOTE: PropiLatam/VivoLatam HTML often uses escaped quotes like \".
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
        bedroom_match = re.search(r'(\d+)\s*(?:dormitorio|habitaci)', page_text, re.I)
        bathroom_match = re.search(r'(\d+)\s*(?:baño|bath)', page_text, re.I)
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
        
        # Location from title, breadcrumbs, and URL path.
        location = ""
        if title:
            title_loc_match = re.search(r'\ben\s+([^,]+(?:,\s*[^,]+)?)', title, re.IGNORECASE)
            if title_loc_match:
                location = title_loc_match.group(1).strip()

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
                    if any(token in link_text_lc for token in ("quiero ", "comprar", "alquilar", "vender", "publicar", "iniciar", "registrar", "visita")):
                        continue
                    if len(link_text_lc) < 3:
                        continue
                    location = link_text
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

                    location = unquote(municipality_segment).replace("-", " ").strip().title()
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
            "details": {},
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


def main(encuentra24=True, micasasv=False, realtor=False, camarabienesraices=False, vivolatam=False, propilatam=False, limit=None, vivolatam_urls=None, propilatam_urls=None, skip_validation=False, max_days=None):
    """
    Main scraper function that orchestrates scraping from multiple sources.
    
    Args:
        encuentra24: If True, scrape from Encuentra24
        micasasv: If True, scrape from MiCasaSV
        realtor: If True, scrape from Realtor.com International
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
    
    # Track which sources we're scraping (for targeted validation)
    active_sources = []
    
    # --- ENCUENTRA24 ---
    if encuentra24:
        active_sources.append("Encuentra24")
        print("\n" + "="*60)
        print("SCRAPING SOURCE: Encuentra24")
        print("="*60)

        listings, sale_data, rent_data = main_encuentra24(limit, max_days=max_days)
        all_listings.extend(listings)
        total_sale += len(sale_data)
        total_rent += len(rent_data)
    
    # --- MICASASV ---
    if micasasv:
        active_sources.append("MiCasaSV")
        print("\n" + "="*60)
        print("SCRAPING SOURCE: MiCasaSV")
        print("="*60)
        listings, sale_data, rent_data = main_micasasv(limit, max_days=max_days)
        all_listings.extend(listings)
        total_sale += len(sale_data)
        total_rent += len(rent_data)
    
    # --- REALTOR.COM ---
    if realtor:
        active_sources.append("Realtor")
        print("\n" + "="*60)
        print("SCRAPING SOURCE: Realtor.com International")
        print("="*60)
        listings, sale_data, rent_data = main_realtor(limit, max_days=max_days)
        all_listings.extend(listings)
        total_sale += len(sale_data)
        total_rent += len(rent_data)

    # --- CAMARA BIENES RAICES ---
    if camarabienesraices:
        active_sources.append(CAMARABIENESRAICES_SOURCE)
        print("\n" + "="*60)
        print("SCRAPING SOURCE: Camara Bienes Raices")
        print("="*60)
        listings, sale_data, rent_data = main_camarabienesraices(limit, max_days=max_days)
        all_listings.extend(listings)
        total_sale += len(sale_data)
        total_rent += len(rent_data)

    # --- VIVOLATAM ---
    if vivolatam:
        active_sources.append("VivoLatam")
        print("\n" + "="*60)
        print("SCRAPING SOURCE: Vivo Latam")
        print("="*60)
        listings, sale_data, rent_data = main_vivolatam(limit, url_file=vivolatam_urls, max_days=max_days)
        all_listings.extend(listings)
        total_sale += len(sale_data)
        total_rent += len(rent_data)

    # --- PROPILATAM ---
    if propilatam:
        active_sources.append("PropiLatam")
        print("\n" + "="*60)
        print("SCRAPING SOURCE: Propi Latam")
        print("="*60)
        listings, sale_data, rent_data = main_propilatam(limit, url_file=propilatam_urls, max_days=max_days)
        all_listings.extend(listings)
        total_sale += len(sale_data)
        total_rent += len(rent_data)

    # --- INSERT TO SUPABASE ---
    print("\n=== Inserting to Supabase ===")
    success, errors = insert_listings_batch(all_listings)
    print(f"  Inserted: {success} | Errors: {errors}")
    
    # --- MATCH LOCATIONS ---
    # Use the raw scraped data (title, location, details, description) to match to sv_loc_group
    print("\n=== Matching Locations ===")
    loc_matched, loc_errors = match_scraped_listings(all_listings, SUPABASE_URL, SUPABASE_SERVICE_KEY)
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
        validated_count, deactivated_count = validate_and_deactivate_listings(
            run_start_time, 
            sources=active_sources if active_sources else None
        )
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
    print(f"JSON backup: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Multi-source real estate scraper (Encuentra24, MiCasaSV, Realtor.com, Camara Bienes Raices, Vivo Latam, Propi Latam)"
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
    realtor = args.Realtor
    camarabienesraices = args.CamaraBienesRaices
    vivolatam = args.VivoLatam
    propilatam = args.PropiLatam
    
    # Build sources list for update mode
    sources = []
    if encuentra24:
        sources.append("Encuentra24")
    if micasasv:
        sources.append("MiCasaSV")
    if realtor:
        sources.append("Realtor")
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
        if not encuentra24 and not micasasv and not realtor and not camarabienesraices and not vivolatam and not propilatam:
            encuentra24 = True
            micasasv = True
            realtor = True
            camarabienesraices = True
            vivolatam = True
            propilatam = True
            print("No source specified. Scraping from ALL sources: Encuentra24, MiCasaSV, Realtor, CamaraBienesRaices, VivoLatam, PropiLatam")
        
        main(
            encuentra24=encuentra24, 
            micasasv=micasasv, 
            realtor=realtor, 
            camarabienesraices=camarabienesraices,
            vivolatam=vivolatam,
            propilatam=propilatam,
            limit=args.limit,
            vivolatam_urls=args.vivolatam_urls,
            propilatam_urls=args.propilatam_urls,
            skip_validation=args.skip_validation,
            max_days=args.max_days
        )


