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
    """Load all sv_loc_group tables into memory for fast matching."""
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
                
                groups[level][loc_id] = {
                    'id': loc_id,
                    'name': name,
                    'normalized': normalized_name,
                    'no_prefix': name_no_prefix,
                    'alt_names': alt_names,
                    'parent_id': row.get('parent_loc_group')
                }
            
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
    """Match a listing to location hierarchy using hybrid approach.
    
    Strategy:
    1. Find L5 (department) first
    2. Search ALL L4, L3, L2 entries that belong to that department
    3. Pick the most specific match (lowest level)
    4. Derive full parent chain from database
    5. If no L5, try bottom-up from L3/L2
    
    This allows matching "San Antonio Abad" directly even if L4 region isn't mentioned.
    """
    texts = extract_searchable_text(listing)
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
    
    # Step 1: Find L5 (Department)
    l5_match = find_best_match_in_level(texts, groups.get(5, {}))
    
    if l5_match:
        l5_id, l5_score, l5_text, l5_source = l5_match
        result['locGroup5Id'] = l5_id
        result['matchLevel'] = 5
        result['matchScore'] = round(l5_score, 2)
        result['matchSource'] = l5_source
        result['matchedText'] = l5_text[:255] if l5_text else None
        
        # Step 2: Search ALL lower levels under this department, find most specific match
        best_lower = None
        best_lower_level = 5
        best_lower_score = 0
        
        # Try L2 first (most specific), then L3, then L4
        for level in [2, 3, 4]:
            valid_ids = get_ids_under_department(level, l5_id)
            if not valid_ids:
                continue
            
            # Filter to only valid IDs
            filtered_data = {k: v for k, v in groups.get(level, {}).items() if k in valid_ids}
            if not filtered_data:
                continue
            
            match = find_best_match_in_level(texts, filtered_data)
            if match:
                loc_id, score, matched_text, source = match
                if score >= MIN_SCORE and level < best_lower_level:
                    # More specific level wins
                    best_lower = (loc_id, score, matched_text, source)
                    best_lower_level = level
                    best_lower_score = score
                elif score > best_lower_score and level == best_lower_level:
                    # Same level, higher score wins
                    best_lower = (loc_id, score, matched_text, source)
                    best_lower_score = score
        
        # If we found a more specific match, update result with full parent chain
        if best_lower:
            loc_id, score, matched_text, source = best_lower
            parent_chain = get_parent_chain(loc_id, best_lower_level, groups)
            result.update(parent_chain)
            result['matchLevel'] = best_lower_level
            result['matchScore'] = round(score, 2)
            result['matchSource'] = source
            result['matchedText'] = matched_text[:255] if matched_text else None
        
        return result
    
    # No L5 match - try bottom-up approach
    # Try L3 first (municipality) - more reliable than L2
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
            
            return result
    
    # Try L2 directly as last resort
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
        
        # Run matching algorithm
        match_result = match_listing_with_texts(texts, groups)
        
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


def match_listing_with_texts(texts: Dict[str, str], groups: Dict) -> dict:
    """Match listing to location hierarchy using pre-extracted texts.
    
    This is a simplified version of match_listing that takes pre-normalized texts.
    Returns dict with locGroup2Id, locGroup3Id, locGroup4Id, locGroup5Id.
    """
    import re
    
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
            
            return result
    
    # Step 2: No L3 match - try L5 (Department) and search within it
    l5_match = find_match(groups.get(5, {}))
    
    if l5_match:
        l5_id, l5_score, l5_text, l5_source = l5_match
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
