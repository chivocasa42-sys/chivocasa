#!/usr/bin/env python3
"""
Export residential areas from JSON to Supabase sv_locations table.

Usage:
    python export_to_supabase.py                    # Export all areas
    python export_to_supabase.py --dry-run          # Preview without inserting
    python export_to_supabase.py --clear            # Clear table before inserting
"""

import argparse
import json
import os
from supabase import create_client, Client

# Supabase credentials (hardcoded for convenience - remove before committing!)
SUPABASE_URL = "https://zvamupbxzuxdgvzgbssn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inp2YW11cGJ4enV4ZGd2emdic3NuIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2OTA5MDMwNSwiZXhwIjoyMDg0NjY2MzA1fQ.VfONseJg19pMEymrc6FbdEQJUWxTzJdNlVTboAaRgEs"

JSON_FILE = "residential_areas_el_salvador.json"
TABLE_NAME = "sv_locations"
BATCH_SIZE = 500  # Supabase upsert batch limit


def load_json_data(filepath: str) -> list[dict]:
    """Load residential areas from JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # The JSON has a structure with "metadata" and "areas"
    if isinstance(data, dict) and "areas" in data:
        return data["areas"]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"Unexpected JSON structure in {filepath}")


def transform_area(area: dict) -> dict:
    """Transform JSON area to sv_locations table schema.
    
    JSON fields:
        osm_id, name, label, district, city, state, country, 
        lat, lon, admin, display_name, parent_residential
    
    Table columns:
        id, name, department, municipality, latitude, longitude,
        district, labels, loc_admin, country
    """
    # Build labels JSONB - store display_name, label, parent info
    labels = {}
    if area.get("display_name"):
        labels["display_name"] = area["display_name"]
    if area.get("label"):
        labels["label"] = area["label"]
    if area.get("parent_residential"):
        labels["parent"] = area["parent_residential"]
    if area.get("type"):
        labels["type"] = area["type"]
    if area.get("class"):
        labels["class"] = area["class"]
    
    # Build loc_admin JSONB from admin hierarchy
    loc_admin = area.get("admin", {})
    
    return {
        "id": area.get("osm_id", ""),
        "name": area.get("display_name") or area.get("name", ""),  # Use display_name if available (deduplicated)
        "department": area.get("state", ""),  # state = department in El Salvador
        "municipality": area.get("city", "") or None,  # city = municipality
        "latitude": area.get("lat") if area.get("lat") else None,
        "longitude": area.get("lon") if area.get("lon") else None,
        "district": area.get("district", "") or None,
        "labels": labels if labels else None,
        "loc_admin": loc_admin if loc_admin else None,
        "country": area.get("country", "El Salvador"),
    }


def export_to_supabase(areas: list[dict], supabase: Client, clear_first: bool = False, dry_run: bool = False):
    """Export areas to Supabase sv_locations table."""
    
    # Transform all areas
    rows = [transform_area(area) for area in areas]
    
    # Filter out any rows without required fields
    valid_rows = [r for r in rows if r["id"] and r["name"] and r["department"]]
    skipped = len(rows) - len(valid_rows)
    
    print(f"\n📊 Data Summary:")
    print(f"   - Total areas in JSON: {len(areas)}")
    print(f"   - Valid rows to insert: {len(valid_rows)}")
    print(f"   - Skipped (missing required fields): {skipped}")
    
    if dry_run:
        print(f"\n🔍 DRY RUN - Preview first 5 rows:")
        for i, row in enumerate(valid_rows[:5]):
            print(f"\n   Row {i+1}:")
            print(f"     id: {row['id']}")
            print(f"     name: {row['name']}")
            print(f"     department: {row['department']}")
            print(f"     municipality: {row['municipality']}")
            print(f"     lat/lon: {row['latitude']}, {row['longitude']}")
        return
    
    # Clear table if requested
    if clear_first:
        print(f"\n🗑️ Clearing {TABLE_NAME} table...")
        supabase.table(TABLE_NAME).delete().neq("id", "").execute()
        print("   ✓ Table cleared")
    
    # Insert in batches
    total_batches = (len(valid_rows) + BATCH_SIZE - 1) // BATCH_SIZE
    inserted = 0
    
    print(f"\n📤 Inserting {len(valid_rows)} rows in {total_batches} batches...")
    
    for i in range(0, len(valid_rows), BATCH_SIZE):
        batch = valid_rows[i:i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        
        try:
            # Use upsert to handle any existing rows
            result = supabase.table(TABLE_NAME).upsert(batch, on_conflict="id").execute()
            inserted += len(batch)
            print(f"   Batch {batch_num}/{total_batches}: {len(batch)} rows ✓")
        except Exception as e:
            print(f"   Batch {batch_num}/{total_batches}: ERROR - {e}")
    
    print(f"\n✅ Export complete: {inserted} rows inserted/updated")


def main():
    parser = argparse.ArgumentParser(description="Export residential areas to Supabase")
    parser.add_argument("--dry-run", action="store_true",
        help="Preview the data without inserting")
    parser.add_argument("--clear", action="store_true",
        help="Clear the table before inserting")
    parser.add_argument("--file", "-f", type=str, default=JSON_FILE,
        help=f"JSON file to import (default: {JSON_FILE})")
    args = parser.parse_args()
    
    print("=" * 60)
    print("Export Residential Areas to Supabase")
    print("=" * 60)
    
    # Check environment variables
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("\n❌ Error: Supabase credentials not found!")
        print("   Set environment variables:")
        print("   - SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL")
        print("   - SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY")
        return
    
    print(f"\n🔗 Supabase URL: {SUPABASE_URL[:40]}...")
    
    # Load JSON data
    print(f"\n📂 Loading data from: {args.file}")
    try:
        areas = load_json_data(args.file)
        print(f"   ✓ Loaded {len(areas)} areas")
    except FileNotFoundError:
        print(f"   ❌ File not found: {args.file}")
        return
    except Exception as e:
        print(f"   ❌ Error loading file: {e}")
        return
    
    # Connect to Supabase
    print("\n🔌 Connecting to Supabase...")
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("   ✓ Connected")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return
    
    # Export data
    export_to_supabase(areas, supabase, clear_first=args.clear, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
