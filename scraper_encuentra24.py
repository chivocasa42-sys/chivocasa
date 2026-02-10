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
import random
from urllib.parse import unquote
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
            print(f"  ⚠️ Failed to fetch batch at offset {offset} after {max_retries} attempts, skipping...")
            
            if consecutive_failures >= max_consecutive_failures:
                print(f"  ❌ Too many consecutive failures ({consecutive_failures}), stopping pagination")
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


def run_update_mode(sources=None, limit=None):
    """
    Update mode: re-scrape existing active listings from DB and update them.
    Also marks listings as inactive if they fail to scrape (404, sold, expired).
    
    Args:
        sources: List of sources to update (None = all sources)
        limit: Optional limit per source
    """
    print("\n" + "="*60)
    print("UPDATE MODE: Re-scraping and updating existing listings")
    print("="*60)
    
    # Determine which sources to update
    all_sources = ["Encuentra24", "MiCasaSV", "Realtor", "VivoLatam"]
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
            
            # For Realtor, check which active listings from DB are no longer on the site
            # SAFEGUARD: Only deactivate if we successfully scraped at least 50% of expected listings
            # This prevents mass deactivation if scraping fails completely
            if len(scraped_listings) >= len(active_listings) * 0.5:
                scraped_external_ids = {str(l.get('external_id')) for l in scraped_listings if l.get('external_id')}
                db_external_ids = {str(l['external_id']) for l in active_listings}
                missing_ids = db_external_ids - scraped_external_ids
                
                if missing_ids:
                    print(f"  ⚠️ {len(missing_ids)} Realtor listings no longer on site, deactivating...")
                    deactivated = deactivate_listings([int(eid) for eid in missing_ids])
                    total_deactivated += deactivated
                    print(f"  Deactivated {deactivated} Realtor listings")
            else:
                print(f"  ⚠️ Scrape returned too few results ({len(scraped_listings)}/{len(active_listings)}), skipping deactivation to prevent data loss")
            
        elif source == "VivoLatam":
            all_urls = [u[0] for u in sale_urls + rent_urls]
            if all_urls:
                print(f"  Re-scraping {len(all_urls)} listings...")
                scraped, _ = scrape_vivolatam_listings_concurrent(all_urls, "sale", max_workers=5)
                scraped_listings.extend(scraped)
        
        # Determine which listings failed to scrape
        scraped_urls = {l.get('url') for l in scraped_listings if l.get('url')}
        failed_urls = original_urls - scraped_urls
        
        if failed_urls:
            print(f"  ⚠️ {len(failed_urls)} listings failed to scrape, verifying if truly inactive...")
            # Verify each failed URL to confirm it's actually 404/sold (not just rate limited)
            confirmed_inactive_ids = []
            for url in failed_urls:
                is_active, reason = check_listing_still_active(url, source)
                if not is_active:
                    confirmed_inactive_ids.append(url_to_id[url])
                    print(f"    ✗ Confirmed inactive: {url[:60]}... ({reason})")
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
    print(f"Total deactivated: {total_deactivated}")
    print(f"Total errors: {total_errors}")
    
    return total_updated, total_deactivated, total_errors


# ============== LISTING VALIDATION FUNCTIONS ==============

def get_stale_active_listings(run_start_time, source=None):
    """
    Fetch active listings that were NOT updated in the current run.
    These are candidates for validation (might be sold/removed).
    
    Args:
        run_start_time: ISO timestamp of when the scrape run started
        source: Optional source filter (e.g., "Encuentra24", "MiCasaSV")
    
    Returns:
        List of dicts with {external_id, url, source}
    """
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Query: active=true AND last_updated < run_start_time
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
    params = {
        "select": "external_id,url,source",
        "active": "eq.true",
        "last_updated": f"lt.{run_start_time}"
    }
    
    if source:
        params["source"] = f"eq.{source}"
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        else:
            print(f"  Error fetching stale listings: {resp.status_code} - {resp.text[:200]}")
            return []
    except Exception as e:
        print(f"  Exception fetching stale listings: {e}")
        return []


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
        
        # Check page content for inactive indicators
        page_text = resp.text.lower()
        
        # Check for exact inactive phrases first (most reliable)
        for phrase in INACTIVE_PHRASES:
            if phrase in page_text:
                return False, f"Page contains '{phrase}'"
        
        # Check for keywords in title or h1
        for keyword in INACTIVE_KEYWORDS:
            if keyword in page_text[:5000]:  # Check first 5KB for performance
                # Make sure it's prominent (in title or main content)
                if f'<title>{keyword}' in page_text or f'<h1>{keyword}' in page_text:
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
    validated = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_listing = {
            executor.submit(check_listing_still_active, l['url'], l['source']): l 
            for l in stale_listings
        }
        
        for future in as_completed(future_to_listing):
            listing = future_to_listing[future]
            validated += 1
            
            try:
                is_active, reason = future.result()
                if not is_active:
                    to_deactivate.append({
                        'external_id': listing['external_id'],
                        'reason': reason
                    })
                    print(f"    ✗ INACTIVE: {listing['url'][:60]}... ({reason})")
            except Exception as e:
                print(f"    ? ERROR checking: {listing['url'][:60]}... ({e})")
            
            # Progress update every 50 listings
            if validated % 50 == 0:
                print(f"    Validated {validated}/{len(stale_listings)} ({len(to_deactivate)} inactive)")
    
    print(f"  Validation complete: {validated} checked, {len(to_deactivate)} to deactivate")
    
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
    all_source_names = ["Encuentra24", "MiCasaSV", "Realtor", "VivoLatam"]
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
        validated = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_listing = {
                executor.submit(check_listing_still_active, l['url'], source): l
                for l in active_listings
            }
            
            for future in as_completed(future_to_listing):
                listing = future_to_listing[future]
                validated += 1
                
                try:
                    is_active, reason = future.result()
                    if not is_active:
                        to_deactivate.append(listing['external_id'])
                        print(f"    ✗ INACTIVE: {listing['url'][:70]}... ({reason})")
                except Exception as e:
                    print(f"    ? ERROR: {listing['url'][:70]}... ({e})")
                
                # Progress update every 100 listings
                if validated % 100 == 0:
                    print(f"    Progress: {validated}/{len(active_listings)} checked ({len(to_deactivate)} inactive)")
        
        print(f"  {source}: {validated} checked, {len(to_deactivate)} inactive")
        
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
                print(f"    ⚠️ URL indicates rent but marked as sale, correcting to rent")
            return 'rent'
        elif 'venta' in url_lower or '-venta-' in url_lower:
            if listing_type == 'rent':
                print(f"    ⚠️ URL indicates sale but marked as rent, correcting to sale")
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
        print(f"    ⚠️ Corrected listing_type: {original_type} → {corrected_type} (sale_kw={sale_matches}, rent_kw={rent_matches}, price=${price})")
    
    return corrected_type


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


def extract_vivolatam_date_from_html(raw_html):
    """
    Extract date fields from VivoLatam listing's embedded Next.js RSC data.
    
    The VivoLatam page embeds listing data (including datePublished, dateLastUpdated,
    and stats.days) in script tags as part of Next.js React Server Components streaming.
    This extracts those fields directly from static HTML — no browser/Playwright needed.
    
    Args:
        raw_html: The full HTML response text from requests.get()
    
    Returns:
        dict with 'published_date' (DD/MM/YYYY format) and 'days_on_site' (int or None)
        Returns empty dict if extraction fails.
    """
    result = {}
    
    try:
        # Note: VivoLatam uses escaped quotes in their embedded JSON: \\\"key\\\":value
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
    except Exception as e:
        print(f"  Date extraction from HTML failed: {e}")
    
    return result


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
        # Pattern: \"price\":{\"sale\":{\"value\":4600000}} (note: quotes are ESCAPED in HTML)
        # Rent has extra field: \"rent\":{\"period\":\"month\",\"value\":1800}
        price = None
        raw_html = resp.text
        
        # Try multiple patterns for embedded JSON data
        # NOTE: VivoLatam HTML uses ESCAPED quotes like \" not regular "
        if not price:
            # Pattern 1: Escaped JSON format (most common in VivoLatam)
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
            # This is common on VivoLatam listings
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
        area_match = re.search(r'([\d.,]+)\s*(m2|metros?\s*cuadrados?|m²|ft2|sqft|sq\s*ft|pies?\s*cuadrados?|v2|varas?\s*cuadradas?|varas?)', page_text, re.I)
        
        if bedroom_match:
            specs["habitaciones"] = bedroom_match.group(1)
        if bathroom_match:
            specs["banos"] = bathroom_match.group(1)
        if area_match:
            specs["area"] = f"{area_match.group(1)} {area_match.group(2)}"
        
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
        
        # Extract published/updated date from embedded Next.js RSC data in static HTML
        # The datePublished, dateLastUpdated, and stats.days are embedded in script tags
        # No Playwright/Selenium needed — pure regex on the already-fetched HTML
        published_date = ""
        date_data = extract_vivolatam_date_from_html(raw_html)
        if date_data.get('published_date'):
            published_date = date_data['published_date']
        
        # Extract coordinates from embedded RSC data
        # Pattern: "coords":[LAT,LNG] or "center":[LAT,LNG] in escaped JSON
        latitude = None
        longitude = None
        coord_match = re.search(r'\\"coords\\"\s*:\s*\[\s*(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*\]', raw_html)
        if not coord_match:
            coord_match = re.search(r'\\"center\\"\s*:\s*\[\s*(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)\s*\]', raw_html)
        if coord_match:
            try:
                latitude = float(coord_match.group(1))
                longitude = float(coord_match.group(2))
            except (ValueError, TypeError):
                pass
        
        # Detect listing type from title/URL
        title_lower = title.lower()
        url_lower = url.lower()
        if "alquiler" in title_lower or "renta" in title_lower or "rent" in url_lower:
            listing_type = "rent"
        else:
            listing_type = "sale"
        
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
            "source": "VivoLatam",
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


def scrape_vivolatam_listings_concurrent(urls, listing_type="sale", max_workers=5, max_days=None):
    """Scrape multiple Vivo Latam listings concurrently with optional date filtering.
    
    Args:
        urls: List of listing URLs
        listing_type: 'sale' or 'rent'
        max_workers: Number of concurrent workers
        max_days: Maximum age of listings in days. None or 0 = no filtering.
        
    Returns:
        Tuple of (results, old_listing_count)
    """
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
    
    return results, old_listing_count


def main_vivolatam(limit=None, url_file=None, max_days=None):
    """Main scraper function for Vivo Latam.
    
    Args:
        limit: Maximum number of listings to scrape
        url_file: Optional path to file containing URLs to scrape
        max_days: Maximum age of listings in days. None or 0 = no filtering.
    """
    all_listings = []
    sale_data = []
    rent_data = []
    
    if limit:
        print(f"\n*** LIMIT MODE: Scraping up to {limit} listings from Vivo Latam ***")
    if max_days and max_days > 0:
        print(f"*** DATE FILTER: Only listings from last {max_days} days ***")
    
    # Get listing URLs from file
    urls = get_vivolatam_listing_urls(url_file=url_file, max_listings=limit)
    
    if not urls:
        print("  No Vivo Latam URLs found to scrape")
        return [], [], []
    
    print(f"\n=== Scraping Vivo Latam Listings ===")
    listings, old_count = scrape_vivolatam_listings_concurrent(urls, "sale", max_days=max_days)
    all_listings.extend(listings)
    
    if old_count > 0:
        print(f"  Skipped {old_count} old listings (>{max_days} days)")
    
    # Separate by listing type
    sale_data = [l for l in all_listings if l.get("listing_type") == "sale"]
    rent_data = [l for l in all_listings if l.get("listing_type") == "rent"]
    
    print(f"  Vivo Latam total: {len(all_listings)} ({len(sale_data)} sales, {len(rent_data)} rentals)")
    
    return all_listings, sale_data, rent_data


def main(encuentra24=True, micasasv=False, realtor=False, vivolatam=False, limit=None, vivolatam_urls=None, skip_validation=False, max_days=None):
    """
    Main scraper function that orchestrates scraping from multiple sources.
    
    Args:
        encuentra24: If True, scrape from Encuentra24
        micasasv: If True, scrape from MiCasaSV
        realtor: If True, scrape from Realtor.com International
        vivolatam: If True, scrape from Vivo Latam
        limit: Optional max number of listings to scrape (per source if both enabled)
        vivolatam_urls: Path to file containing Vivo Latam URLs to scrape
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
    args = parser.parse_args()
    
    # Get source flags
    encuentra24 = args.Encuentra24
    micasasv = args.MiCasaSV
    realtor = args.Realtor
    vivolatam = args.VivoLatam
    
    # Build sources list for update mode
    sources = []
    if encuentra24:
        sources.append("Encuentra24")
    if micasasv:
        sources.append("MiCasaSV")
    if realtor:
        sources.append("Realtor")
    if vivolatam:
        sources.append("VivoLatam")
    
    # If no sources specified, use all
    if not sources:
        sources = None  # run_update_mode will use all sources
    
    # Check for validate-all mode first (lightweight)
    if args.validate_all:
        validate_all_active_listings(sources=sources, max_workers=10)
    elif args.update:
        # Update mode: re-scrape and update existing active listings
        run_update_mode(sources=sources, limit=args.limit)
    else:
        # Normal scrape mode
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
            vivolatam_urls=args.vivolatam_urls,
            skip_validation=args.skip_validation,
            max_days=args.max_days
        )