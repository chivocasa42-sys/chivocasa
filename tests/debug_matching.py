#!/usr/bin/env python3
"""Debug matching for specific problematic listings."""

from supabase import create_client
from match_locations import normalize_text, remove_location_prefixes, load_location_groups, match_listing_with_texts
import re

url = 'https://zvamupbxzuxdgvzgbssn.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp2YW11cGJ4enV4ZGd2emdic3NuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTA5MDMwNSwiZXhwIjoyMDg0NjY2MzA1fQ.VfONseJg19pMEymrc6FbdEQJUWxTzJdNlVTboAaRgEs'

supabase = create_client(url, key)

# Problem listings
problem_ids = [
    31885955,  # Ciudad Marsella Q9
    31943816,  # Ciudad Marsella Quartier 3
    31916568,  # Arboledas Las Avellanas
]

# Load groups
print("Loading location groups...")
groups = load_location_groups(supabase)

# Check what normalized names exist for these locations
print("\n=== sv_loc_group2 entries for Marsella ===")
for loc_id, info in groups[2].items():
    if 'marsella' in info['normalized']:
        print(f"  ID {loc_id}: normalized='{info['normalized']}', no_prefix='{info['no_prefix']}', alt_names={info.get('alt_names', [])}")

print("\n=== sv_loc_group2 entries for Arboledas ===")
for loc_id, info in groups[2].items():
    if 'arboleda' in info['normalized']:
        print(f"  ID {loc_id}: normalized='{info['normalized']}', no_prefix='{info['no_prefix']}', alt_names={info.get('alt_names', [])}")

print("\n=== sv_loc_group2 entries for San Benito ===")
for loc_id, info in groups[2].items():
    if 'san benito' in info['normalized'] or 'san benito' in str(info.get('alt_names', [])):
        print(f"  ID {loc_id}: normalized='{info['normalized']}', no_prefix='{info['no_prefix']}', alt_names={info.get('alt_names', [])}")

# Check each problem listing
for ext_id in problem_ids:
    print(f"\n{'='*60}")
    print(f"=== Listing {ext_id} ===")
    print('='*60)
    
    r = supabase.table('scrapped_data').select('title, location, description').eq('external_id', ext_id).execute()
    if not r.data:
        print(f"  NOT FOUND in scrapped_data")
        continue
    
    listing = r.data[0]
    print(f"Title: {listing.get('title', '')[:80]}")
    
    loc = listing.get('location', {})
    if isinstance(loc, dict):
        print(f"Location: {loc.get('location_original', '')} | Municipio: {loc.get('municipio_detectado', '')}")
    else:
        print(f"Location: {loc}")
    
    # Build texts like the matcher does
    texts = {
        'title': normalize_text(listing.get('title', '') or ''),
        'location': normalize_text(str(listing.get('location', '') or '')),
        'details': '',
        'description': normalize_text(listing.get('description', '') or '')[:500]
    }
    
    print(f"\nNormalized title: {texts['title'][:100]}")
    
    # Check for key words
    for keyword in ['marsella', 'arboleda', 'avellana', 'san benito', 'quartier']:
        for source, text in texts.items():
            if keyword in text:
                idx = text.find(keyword)
                print(f"  Found '{keyword}' in {source}: ...{text[max(0,idx-20):idx+len(keyword)+20]}...")
    
    # Try matching
    print(f"\n--- Matching result ---")
    result = match_listing_with_texts(texts, groups)
    print(f"Result: {result}")
    
    # Check current DB match
    r2 = supabase.table('listing_location_match').select('*').eq('external_id', ext_id).execute()
    if r2.data:
        print(f"DB match: L2={r2.data[0].get('loc_group2_id')}, L3={r2.data[0].get('loc_group3_id')}, L5={r2.data[0].get('loc_group5_id')}")
    else:
        print(f"DB match: NONE")
