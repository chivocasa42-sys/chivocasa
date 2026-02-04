#!/usr/bin/env python3
"""
Generate SQL INSERT statements from el_salvador_locations.json

This script reads the JSON file (which is a direct array of location objects)
and generates SQL INSERT statements for the sv_locations table.
"""

import json
import os
from datetime import datetime

# Configuration
SOURCE_FILE = 'el_salvador_locations.json'
OUTPUT_FILE = 'sql/insert_sv_locations.sql'
BATCH_SIZE = 15

def escape_sql_string(value):
    """Escape single quotes for SQL strings."""
    if value is None:
        return None
    return str(value).replace("'", "''")

def format_sql_value(value, is_string=True):
    """Format a value for SQL insertion."""
    if value is None or value == '':
        return 'NULL'
    if is_string:
        return f"'{escape_sql_string(value)}'"
    return str(value)

def main():
    # Load JSON data
    print(f"📂 Loading locations from {SOURCE_FILE}...")
    
    with open(SOURCE_FILE, 'r', encoding='utf-8') as f:
        locations = json.load(f)
    
    if not isinstance(locations, list):
        print("❌ JSON file should contain an array of locations")
        return
    
    print(f"📊 Found {len(locations)} locations")
    
    # Create output directory if needed
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    # Generate SQL file
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("-- ============================================\n")
        f.write("-- FRESH IMPORT: DELETE ALL + INSERT\n")
        f.write("-- Auto-generated SQL for sv_locations\n")
        f.write(f"-- Generated at: {datetime.now().isoformat()}\n")
        f.write(f"-- Total records: {len(locations)}\n")
        f.write("-- ============================================\n")
        f.write("-- WARNING: This will DELETE ALL existing locations!\n")
        f.write("-- Run this in Supabase SQL Editor\n\n")
        f.write("BEGIN;\n\n")
        
        # DELETE ALL existing records first
        f.write("-- ============================================\n")
        f.write("-- Step 1: Delete ALL existing locations\n")
        f.write("-- ============================================\n")
        f.write("DELETE FROM sv_locations WHERE id >= 0;\n\n")
        
        # Reset the sequence (optional, for clean IDs)
        f.write("-- Reset ID sequence to start from 1\n")
        f.write("ALTER SEQUENCE sv_locations_id_seq RESTART WITH 1;\n\n")
        
        f.write("-- ============================================\n")
        f.write("-- Step 2: Insert new locations from JSON source\n")
        f.write("-- ============================================\n\n")
        
        for i, loc in enumerate(locations):
            name = format_sql_value(loc.get('name'))
            department = format_sql_value(loc.get('department'))
            municipality = format_sql_value(loc.get('municipality'))
            
            # Handle latitude and longitude - they might be strings or numbers
            lat = loc.get('latitude')
            lon = loc.get('longitude')
            
            lat_sql = 'NULL' if lat is None else str(lat).strip('"')
            lon_sql = 'NULL' if lon is None else str(lon).strip('"')
            
            f.write(f"INSERT INTO sv_locations (name, department, municipality, latitude, longitude) ")
            f.write(f"VALUES ({name}, {department}, {municipality}, {lat_sql}, {lon_sql});\n")
            
            # Add batch marker every BATCH_SIZE records
            if (i + 1) % BATCH_SIZE == 0:
                f.write(f"-- Batch {(i + 1) // BATCH_SIZE} complete ({i + 1} records)\n")
        
        f.write("\n-- ============================================\n")
        f.write(f"-- Total: {len(locations)} locations inserted\n")
        f.write("-- ============================================\n")
        f.write("\nCOMMIT;\n")
    
    print(f"✅ Generated SQL file: {OUTPUT_FILE}")
    print(f"📝 Total INSERT statements: {len(locations)}")
    print(f"\n⚠️  Copy and paste the contents into Supabase SQL Editor to execute.")

if __name__ == '__main__':
    main()
