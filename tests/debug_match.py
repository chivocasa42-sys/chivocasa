#!/usr/bin/env python3
"""Debug matching for a specific listing."""

from supabase import create_client
from match_locations import normalize_text, remove_location_prefixes, load_location_groups, match_listing_with_texts

url = 'https://zvamupbxzuxdgvzgbssn.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp2YW11cGJ4enV4ZGd2emdic3NuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTA5MDMwNSwiZXhwIjoyMDg0NjY2MzA1fQ.VfONseJg19pMEymrc6FbdEQJUWxTzJdNlVTboAaRgEs'

supabase = create_client(url, key)

# Get the listing
external_id = 31783891
r = supabase.table('scrapped_data').select('*').eq('external_id', external_id).execute()

if not r.data:
    print(f"Listing {external_id} not found in scrapped_data")
    exit()

listing = r.data[0]
print(f"=== Listing {external_id} ===")
print(f"Title: {listing.get('title', '')}")
print(f"Location: {listing.get('location', '')}")
print(f"Description: {str(listing.get('description', ''))[:200]}...")

# Check location match
r2 = supabase.table('listing_location_match').select('*').eq('external_id', external_id).execute()
if r2.data:
    print(f"\n=== Current Location Match ===")
    print(r2.data[0])
else:
    print(f"\n=== NO Location Match in DB ===")

# Try to match manually
print(f"\n=== Manual Matching Test ===")

# Load groups
groups = load_location_groups(supabase)

# Build texts like the scraper does
texts = {
    'title': normalize_text(listing.get('title', '') or ''),
    'location': normalize_text(str(listing.get('location', '') or '')),
    'details': normalize_text(str(listing.get('details', '') or '')),
    'description': normalize_text(listing.get('description', '') or '')
}

print(f"Normalized title: {texts['title'][:100]}")
print(f"Normalized location: {texts['location'][:100]}")

# Check if 'la castellana' is in texts
for source, text in texts.items():
    if 'castellana' in text:
        print(f"  Found 'castellana' in {source}: ...{text[max(0,text.find('castellana')-20):text.find('castellana')+30]}...")

# Check the sv_loc_group2 entries for Castellana
print(f"\n=== sv_loc_group2 entries with 'castellana' ===")
for loc_id, info in groups[2].items():
    if 'castellana' in info['normalized'] or any('castellana' in alt for alt in info.get('alt_names', [])):
        print(f"  ID {loc_id}: name={info['name']}, normalized={info['normalized']}, no_prefix={info['no_prefix']}, alt_names={info.get('alt_names', [])}")

# Now try the matching function
print(f"\n=== Running match_listing_with_texts ===")
result = match_listing_with_texts(texts, groups)
print(f"Result: {result}")
