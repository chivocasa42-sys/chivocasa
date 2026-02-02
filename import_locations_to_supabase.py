#!/usr/bin/env python3
"""
Import El Salvador Locations to Supabase
=========================================
Reads the JSON file and inserts all locations into the Supabase table.
"""

import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.local')

SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')

def load_locations(filepath: str = 'el_salvador_locations.json') -> list:
    """Load locations from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('locations', [])


def import_to_supabase(locations: list, batch_size: int = 100):
    """Import locations to Supabase in batches."""
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Missing SUPABASE_URL or SUPABASE_KEY in environment")
        print("   Set SUPABASE_SERVICE_ROLE_KEY in .env.local for insert access")
        return
    
    print(f"🔗 Connecting to Supabase...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Prepare data for insertion
    records = []
    for loc in locations:
        records.append({
            'name': loc['name'],
            'department': loc.get('department', ''),
            'municipality': loc.get('municipality', '') or None,
            'latitude': loc.get('latitude') or None,
            'longitude': loc.get('longitude') or None,
        })
    
    print(f"📊 Importing {len(records)} locations...")
    
    # Insert in batches
    total_inserted = 0
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        try:
            result = supabase.table('sv_locations').insert(batch).execute()
            total_inserted += len(batch)
            print(f"   ✓ Inserted batch {i//batch_size + 1}: {len(batch)} records")
        except Exception as e:
            print(f"   ✗ Error in batch {i//batch_size + 1}: {e}")
    
    print(f"\n✅ Import complete! Total inserted: {total_inserted}")


def generate_sql_inserts(locations: list, output_file: str = 'sql/insert_sv_locations.sql'):
    """Generate SQL INSERT statements as an alternative to API import."""
    
    print(f"📝 Generating SQL inserts to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- Auto-generated INSERT statements for sv_locations\n")
        f.write("-- Run this in Supabase SQL Editor after creating the table\n\n")
        f.write("BEGIN;\n\n")
        
        for loc in locations:
            name = loc['name'].replace("'", "''")
            department = loc.get('department', '').replace("'", "''")
            municipality = loc.get('municipality', '')
            municipality = f"'{municipality.replace(chr(39), chr(39)+chr(39))}'" if municipality else 'NULL'
            lat = loc.get('latitude') or 'NULL'
            lon = loc.get('longitude') or 'NULL'
            
            f.write(f"INSERT INTO sv_locations (name, department, municipality, latitude, longitude) ")
            f.write(f"VALUES ('{name}', '{department}', {municipality}, {lat}, {lon});\n")
        
        f.write("\nCOMMIT;\n")
    
    print(f"✅ Generated {len(locations)} INSERT statements")
    print(f"📄 File: {output_file}")


def main():
    import sys
    
    locations = load_locations()
    print(f"📂 Loaded {len(locations)} locations from JSON")
    
    if '--sql' in sys.argv:
        # Generate SQL file instead of using API
        generate_sql_inserts(locations)
    else:
        # Import via Supabase API
        import_to_supabase(locations)


if __name__ == '__main__':
    main()
