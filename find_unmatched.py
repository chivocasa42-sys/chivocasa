#!/usr/bin/env python3
"""Find unmatched listings (in scrapped_data but not in listing_location_match)."""

from supabase import create_client

url = 'https://zvamupbxzuxdgvzgbssn.supabase.co'
key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp2YW11cGJ4enV4ZGd2emdic3NuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTA5MDMwNSwiZXhwIjoyMDg0NjY2MzA1fQ.VfONseJg19pMEymrc6FbdEQJUWxTzJdNlVTboAaRgEs'

supabase = create_client(url, key)

# Get all external_ids from scrapped_data (Encuentra24 only) - paginated
print("Fetching scrapped_data...")
all_rows = []
offset = 0
page_size = 1000
while True:
    result = supabase.table('scrapped_data').select('external_id, title, location, url').eq('source', 'Encuentra24').eq('active', True).range(offset, offset + page_size - 1).execute()
    if not result.data:
        break
    all_rows.extend(result.data)
    if len(result.data) < page_size:
        break
    offset += page_size
    print(f"  Fetched {len(all_rows)} so far...")

all_ids = set(r['external_id'] for r in all_rows)
print(f'Total active Encuentra24 listings: {len(all_ids)}')

# Get all external_ids from listing_location_match - paginated
print("Fetching listing_location_match...")
matched_rows = []
offset = 0
while True:
    result = supabase.table('listing_location_match').select('external_id').range(offset, offset + page_size - 1).execute()
    if not result.data:
        break
    matched_rows.extend(result.data)
    if len(result.data) < page_size:
        break
    offset += page_size

matched_ids = set(r['external_id'] for r in matched_rows)
print(f'Listings with location match: {len(matched_ids)}')

# Find unmatched
unmatched_ids = all_ids - matched_ids
print(f'Unmatched: {len(unmatched_ids)}')

# Show details for unmatched
if unmatched_ids:
    print("\n" + "="*60)
    print("UNMATCHED LISTINGS:")
    print("="*60)

    for row in all_rows:
        if row['external_id'] in unmatched_ids:
            print(f"\n--- ID: {row['external_id']} ---")
            title = row.get('title', '') or ''
            print(f"Title: {title[:80]}")
            
            loc = row.get('location', {})
            if isinstance(loc, dict):
                loc_original = loc.get('location_original', '')
                municipio = loc.get('municipio_detectado', '')
                print(f"Location: {loc_original} | Municipio: {municipio}")
            else:
                print(f"Location: {loc}")
            
            print(f"URL: {row.get('url', '')}")
else:
    print("\nAll listings matched!")

