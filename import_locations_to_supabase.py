#!/usr/bin/env python3
"""
Import El Salvador Locations to Supabase
=========================================
Reads el_salvador_locations.json (source of truth) and safely ingests all 
locations into the Supabase sv_locations table.

This module handles:
- Dynamic ID generation (database handles SERIAL)
- Timestamp generation at insert time (database handles created_at)
- Deduplication by name + municipality + department
- Data normalization (Title Case, numeric coordinates)
- Batch processing with progress persistence
- Skip unchanged existing records

IMPORTANT: The JSON file is the canonical data source. Database-specific fields
(id, created_at, constraints) are NOT expected in the JSON.
"""

import json
import os
import unicodedata
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Set, Tuple
from pathlib import Path

try:
    from supabase import create_client, Client
    from dotenv import load_dotenv
    HAS_SUPABASE = True
except (ImportError, AttributeError, Exception) as e:
    HAS_SUPABASE = False
    # Silently fail - SQL generation will still work
    # print(f"⚠️  Supabase libraries not available: {e}")
    # print("   SQL generation will still work. Use --sql or --fresh-sql")


# ==============================================================================
# Configuration
# ==============================================================================

# Batch size for database inserts (max 15 per requirements)
BATCH_SIZE = 15

# Progress file for resumable imports
PROGRESS_FILE = '.dedup_cache/import_progress.json'

# Source file (canonical source of truth)
SOURCE_FILE = 'el_salvador_locations.json'

# ==============================================================================
# Text Normalization Utilities
# ==============================================================================

def normalize_for_comparison(text: Optional[str]) -> str:
    """
    Normalize text for uniqueness comparison.
    
    Rules:
    - Trim whitespace
    - Convert to lowercase
    - Normalize accents (á → a, ñ → n)
    - Treat None, empty string, or missing as equivalent (returns '')
    """
    if text is None or text == '':
        return ''
    
    # Trim and lowercase
    text = str(text).strip().lower()
    
    # Normalize unicode accents to base characters
    # NFD decomposes characters, then we remove combining marks
    normalized = unicodedata.normalize('NFD', text)
    text_without_accents = ''.join(
        c for c in normalized 
        if unicodedata.category(c) != 'Mn'  # Mn = Mark, Nonspacing
    )
    
    return text_without_accents


def to_title_case(text: Optional[str]) -> str:
    """
    Convert text to Title Case while preserving accented characters.
    
    Handles special cases like "de", "del", "la", etc.
    """
    if text is None or text == '':
        return ''
    
    text = str(text).strip()
    if not text:
        return ''
    
    # Words that should stay lowercase (Spanish articles/prepositions)
    lowercase_words = {'de', 'del', 'la', 'las', 'el', 'los', 'y', 'e', 'en', 'a'}
    
    words = text.split()
    result = []
    
    for i, word in enumerate(words):
        # First word always capitalized, others check lowercase list
        if i == 0 or word.lower() not in lowercase_words:
            result.append(word.capitalize())
        else:
            result.append(word.lower())
    
    return ' '.join(result)


def to_float(value: Any) -> Optional[float]:
    """
    Convert latitude/longitude to float.
    Returns None for invalid values.
    """
    if value is None:
        return None
    
    try:
        f = float(value)
        # Sanity check for El Salvador coordinates
        # Latitude: ~13.0 to 14.5
        # Longitude: ~-90.5 to -87.5
        if -100 < f < 100:  # Very loose check
            return f
        return None
    except (ValueError, TypeError):
        return None


# ==============================================================================
# Uniqueness Key Generation
# ==============================================================================

def generate_uniqueness_key(name: str, municipality: str, department: str) -> str:
    """
    Generate a uniqueness key for deduplication.
    
    Key format: normalized(name)|normalized(municipality)|normalized(department)
    """
    return '|'.join([
        normalize_for_comparison(name),
        normalize_for_comparison(municipality),
        normalize_for_comparison(department)
    ])


# ==============================================================================
# Data Loading & Parsing
# ==============================================================================

def load_locations(filepath: str = SOURCE_FILE) -> List[Dict[str, Any]]:
    """
    Load locations from el_salvador_locations.json.
    
    Reads ONLY the 'locations' array; the 'metadata' object is ignored.
    Returns an empty list if the file doesn't exist or is invalid.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract only the locations array (ignore metadata)
        locations = data.get('locations', [])
        
        if not isinstance(locations, list):
            print(f"⚠️  'locations' in {filepath} is not an array")
            return []
        
        return locations
    
    except FileNotFoundError:
        print(f"❌ Source file not found: {filepath}")
        return []
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {filepath}: {e}")
        return []


# ==============================================================================
# Deduplication Logic
# ==============================================================================

def deduplicate_locations(locations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove duplicate locations based on uniqueness key.
    
    Uniqueness key: name + municipality + department (after normalization)
    
    Deduplication rules:
    - First occurrence wins
    - Comparison uses normalized values (trimmed, lowercase, no accents)
    - null, "", and missing are treated as equivalent
    """
    seen_keys: Set[str] = set()
    unique_locations: List[Dict[str, Any]] = []
    duplicates_removed = 0
    
    for loc in locations:
        name = loc.get('name', '')
        municipality = loc.get('municipality', '')
        department = loc.get('department', '')
        
        key = generate_uniqueness_key(name, municipality, department)
        
        if key in seen_keys:
            duplicates_removed += 1
            continue
        
        seen_keys.add(key)
        unique_locations.append(loc)
    
    if duplicates_removed > 0:
        print(f"🔍 Removed {duplicates_removed} duplicate records")
    
    return unique_locations


# ==============================================================================
# Record Transformation
# ==============================================================================

def transform_to_db_record(loc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a raw JSON location into a database-ready record.
    
    Transformations applied:
    - Title Case for name, municipality, department
    - Numeric conversion for latitude, longitude
    - type and source fields preserved
    
    Note: id and created_at are NOT included; the database generates them.
    Accented characters are preserved in the final values.
    """
    return {
        'name': to_title_case(loc.get('name', '')),
        'municipality': to_title_case(loc.get('municipality', '')) or None,
        'department': to_title_case(loc.get('department', '')) or '',
        'latitude': to_float(loc.get('latitude')),
        'longitude': to_float(loc.get('longitude')),
        'type': loc.get('type', '') or None,
        'source': loc.get('source', '') or None,
    }


def records_are_equal(existing: Dict[str, Any], new: Dict[str, Any]) -> bool:
    """
    Check if two records are equal (for skip-if-unchanged logic).
    
    Compares: name, municipality, department, latitude, longitude, type, source
    """
    fields_to_compare = ['name', 'municipality', 'department', 'type', 'source']
    
    for field in fields_to_compare:
        existing_val = existing.get(field) or ''
        new_val = new.get(field) or ''
        if str(existing_val).strip().lower() != str(new_val).strip().lower():
            return False
    
    # Compare coordinates with tolerance
    for coord in ['latitude', 'longitude']:
        existing_coord = existing.get(coord)
        new_coord = new.get(coord)
        
        if existing_coord is None and new_coord is None:
            continue
        if existing_coord is None or new_coord is None:
            return False
        
        try:
            if abs(float(existing_coord) - float(new_coord)) > 0.0001:
                return False
        except (ValueError, TypeError):
            return False
    
    return True


# ==============================================================================
# Progress Persistence
# ==============================================================================

def load_progress() -> Dict[str, Any]:
    """Load import progress from file."""
    try:
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {'last_batch': 0, 'inserted': 0, 'skipped': 0, 'updated': 0}


def save_progress(progress: Dict[str, Any]):
    """Save import progress to file."""
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2)


def clear_progress():
    """Clear progress file after successful completion."""
    try:
        os.remove(PROGRESS_FILE)
    except FileNotFoundError:
        pass


# ==============================================================================
# Supabase Import Logic
# ==============================================================================

def get_existing_records(supabase: 'Client') -> Dict[str, Dict[str, Any]]:
    """
    Fetch all existing records from sv_locations.
    Returns a dict keyed by uniqueness key.
    """
    existing = {}
    
    try:
        # Fetch all records (paginated if necessary)
        result = supabase.table('sv_locations').select('*').execute()
        
        for record in result.data:
            key = generate_uniqueness_key(
                record.get('name', ''),
                record.get('municipality', ''),
                record.get('department', '')
            )
            existing[key] = record
        
        print(f"📊 Found {len(existing)} existing records in database")
        
    except Exception as e:
        print(f"⚠️  Could not fetch existing records: {e}")
    
    return existing


def delete_all_locations(supabase: 'Client') -> int:
    """
    Delete ALL existing records from sv_locations table.
    
    Returns the number of records deleted.
    WARNING: This is destructive and cannot be undone!
    """
    try:
        # Count existing records first
        count_result = supabase.table('sv_locations').select('id', count='exact').execute()
        total_count = count_result.count or 0
        
        if total_count == 0:
            print("📭 No existing records to delete")
            return 0
        
        print(f"🗑️  Deleting {total_count} existing records...")
        
        # Delete all records (using a condition that matches everything)
        # We use id > 0 since all records have positive IDs
        supabase.table('sv_locations').delete().gte('id', 0).execute()
        
        print(f"✅ Successfully deleted {total_count} records")
        return total_count
        
    except Exception as e:
        print(f"❌ Error deleting records: {e}")
        return 0


def import_to_supabase(locations: List[Dict[str, Any]], resume: bool = True, fresh: bool = False):
    """
    Import locations to Supabase in batches of 15.
    
    Features:
    - Deduplication before import
    - Skip existing unchanged records
    - Update existing changed records
    - Insert new records
    - Progress persistence after each batch
    
    Args:
        locations: List of location dicts from JSON
        resume: Whether to resume from previous progress
        fresh: If True, delete ALL existing records before importing
    """
    if not HAS_SUPABASE:
        print("❌ Supabase libraries not available")
        return
    
    load_dotenv('.env.local')
    
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_ANON_KEY')
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Missing SUPABASE_URL or SUPABASE_KEY in environment")
        print("   Set SUPABASE_SERVICE_ROLE_KEY in .env.local for insert access")
        return
    
    print(f"🔗 Connecting to Supabase...")
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # If fresh import, delete all existing records first
    if fresh:
        print("\n🔄 Fresh import requested - removing all existing records...")
        delete_all_locations(supabase)
        existing_records = {}  # No existing records after delete
        # Clear any previous progress since we're starting fresh
        clear_progress()
    else:
        # Get existing records for comparison
        existing_records = get_existing_records(supabase)
    
    # Deduplicate incoming data
    unique_locations = deduplicate_locations(locations)
    
    # Transform to DB records
    records = [transform_to_db_record(loc) for loc in unique_locations]
    print(f"📊 Processing {len(records)} unique locations")
    
    # Load progress if resuming
    progress = load_progress() if resume else {'last_batch': 0, 'inserted': 0, 'skipped': 0, 'updated': 0}
    start_batch = progress['last_batch']
    
    if start_batch > 0:
        print(f"📌 Resuming from batch {start_batch + 1}")
    
    # Process in batches of 15
    total_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE
    
    for i in range(start_batch * BATCH_SIZE, len(records), BATCH_SIZE):
        batch_num = i // BATCH_SIZE + 1
        batch = records[i:i + BATCH_SIZE]
        
        to_insert = []
        to_update = []
        
        for record in batch:
            key = generate_uniqueness_key(
                record['name'],
                record['municipality'] or '',
                record['department']
            )
            
            if key in existing_records:
                existing = existing_records[key]
                if records_are_equal(existing, record):
                    progress['skipped'] += 1
                else:
                    # Record changed, need to update
                    to_update.append({
                        'id': existing['id'],
                        **record
                    })
            else:
                to_insert.append(record)
        
        # Perform inserts
        if to_insert:
            try:
                result = supabase.table('sv_locations').insert(to_insert).execute()
                progress['inserted'] += len(to_insert)
                
                # Add new records to existing_records for future batches
                for record in to_insert:
                    key = generate_uniqueness_key(
                        record['name'],
                        record['municipality'] or '',
                        record['department']
                    )
                    existing_records[key] = record
                    
            except Exception as e:
                print(f"   ✗ Insert error in batch {batch_num}: {e}")
        
        # Perform updates
        for record in to_update:
            try:
                record_id = record.pop('id')
                supabase.table('sv_locations').update(record).eq('id', record_id).execute()
                progress['updated'] += 1
            except Exception as e:
                print(f"   ✗ Update error for id {record_id}: {e}")
        
        # Update progress
        progress['last_batch'] = batch_num
        save_progress(progress)
        
        # Status update
        status = f"   ✓ Batch {batch_num}/{total_batches}: "
        status += f"+{len(to_insert)} new, "
        status += f"~{len(to_update)} updated, "
        status += f"={len(batch) - len(to_insert) - len(to_update)} skipped"
        print(status)
    
    # Clear progress file on completion
    clear_progress()
    
    print(f"\n✅ Import complete!")
    print(f"   📥 Inserted: {progress['inserted']}")
    print(f"   🔄 Updated:  {progress['updated']}")
    print(f"   ⏭️ Skipped:  {progress['skipped']}")


# ==============================================================================
# SQL Generation (Alternative to API)
# ==============================================================================

def generate_sql_inserts(locations: List[Dict[str, Any]], output_file: str = 'sql/insert_sv_locations.sql'):
    """
    Generate SQL INSERT statements as an alternative to API import.
    
    Uses INSERT ... ON CONFLICT for upsert behavior.
    """
    print(f"📝 Generating SQL inserts to {output_file}...")
    
    # Deduplicate first
    unique_locations = deduplicate_locations(locations)
    records = [transform_to_db_record(loc) for loc in unique_locations]
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- ============================================\n")
        f.write("-- Auto-generated INSERT statements for sv_locations\n")
        f.write(f"-- Generated at: {datetime.now().isoformat()}\n")
        f.write(f"-- Total records: {len(records)}\n")
        f.write("-- ============================================\n")
        f.write("-- Run this in Supabase SQL Editor after creating the table\n\n")
        f.write("BEGIN;\n\n")
        
        for i, record in enumerate(records):
            # Escape single quotes
            name = (record['name'] or '').replace("'", "''")
            department = (record['department'] or '').replace("'", "''")
            municipality = record['municipality']
            municipality_sql = f"'{municipality.replace(chr(39), chr(39)+chr(39))}'" if municipality else 'NULL'
            lat = record['latitude'] if record['latitude'] is not None else 'NULL'
            lon = record['longitude'] if record['longitude'] is not None else 'NULL'
            
            f.write(f"INSERT INTO sv_locations (name, department, municipality, latitude, longitude) ")
            f.write(f"VALUES ('{name}', '{department}', {municipality_sql}, {lat}, {lon});\n")
            
            # Add batch commit every 15 records
            if (i + 1) % BATCH_SIZE == 0:
                f.write(f"-- Batch {(i + 1) // BATCH_SIZE} complete\n")
        
        f.write("\nCOMMIT;\n")
    
    print(f"✅ Generated {len(records)} INSERT statements")
    print(f"📄 File: {output_file}")


def generate_fresh_sql(locations: List[Dict[str, Any]], output_file: str = 'sql/fresh_import_sv_locations.sql'):
    """
    Generate SQL statements that DELETE ALL existing records, then INSERT new ones.
    
    This is the SQL equivalent of --fresh flag for environments where
    the Python Supabase SDK doesn't work.
    """
    print(f"📝 Generating FRESH SQL (DELETE ALL + INSERT) to {output_file}...")
    
    # Deduplicate first
    unique_locations = deduplicate_locations(locations)
    records = [transform_to_db_record(loc) for loc in unique_locations]
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("-- ============================================\n")
        f.write("-- FRESH IMPORT: DELETE ALL + INSERT\n")
        f.write("-- Auto-generated SQL for sv_locations\n")
        f.write(f"-- Generated at: {datetime.now().isoformat()}\n")
        f.write(f"-- Total records: {len(records)}\n")
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
        
        for i, record in enumerate(records):
            # Escape single quotes
            name = (record['name'] or '').replace("'", "''")
            department = (record['department'] or '').replace("'", "''")
            municipality = record['municipality']
            municipality_sql = f"'{municipality.replace(chr(39), chr(39)+chr(39))}'" if municipality else 'NULL'
            lat = record['latitude'] if record['latitude'] is not None else 'NULL'
            lon = record['longitude'] if record['longitude'] is not None else 'NULL'
            
            f.write(f"INSERT INTO sv_locations (name, department, municipality, latitude, longitude) ")
            f.write(f"VALUES ('{name}', '{department}', {municipality_sql}, {lat}, {lon});\n")
            
            # Add batch marker every 15 records
            if (i + 1) % BATCH_SIZE == 0:
                f.write(f"-- Batch {(i + 1) // BATCH_SIZE} complete ({i + 1} records)\n")
        
        f.write("\n-- ============================================\n")
        f.write(f"-- Total: {len(records)} locations inserted\n")
        f.write("-- ============================================\n")
        f.write("\nCOMMIT;\n")
    
    print(f"✅ Generated FRESH SQL with DELETE ALL + {len(records)} INSERT statements")
    print(f"📄 File: {output_file}")
    print(f"\n⚠️  Copy and paste the contents of this file into Supabase SQL Editor to execute.")


# ==============================================================================
# Summary & Validation
# ==============================================================================

def print_summary(locations: List[Dict[str, Any]]):
    """Print a summary of the location data."""
    unique = deduplicate_locations(locations)
    
    # Count by type
    by_type: Dict[str, int] = {}
    for loc in unique:
        t = loc.get('type', 'Unknown') or 'Unknown'
        by_type[t] = by_type.get(t, 0) + 1
    
    # Count by department
    by_dept: Dict[str, int] = {}
    for loc in unique:
        d = loc.get('department', '') or 'Sin Departamento'
        by_dept[d] = by_dept.get(d, 0) + 1
    
    print("\n📊 Location Data Summary")
    print("=" * 40)
    print(f"Total locations: {len(locations)}")
    print(f"Unique locations: {len(unique)}")
    print(f"Duplicates: {len(locations) - len(unique)}")
    
    print("\nBy Type:")
    for t, count in sorted(by_type.items(), key=lambda x: -x[1])[:10]:
        print(f"  • {t}: {count}")
    
    print("\nBy Department:")
    for d, count in sorted(by_dept.items(), key=lambda x: -x[1])[:10]:
        print(f"  • {d}: {count}")


# ==============================================================================
# Main Entry Point
# ==============================================================================

def main():
    import sys
    
    # Load locations from source of truth
    locations = load_locations()
    
    if not locations:
        print("❌ No locations to process")
        return
    
    print(f"📂 Loaded {len(locations)} locations from {SOURCE_FILE}")
    
    # Parse command line arguments
    if '--summary' in sys.argv:
        # Just print summary
        print_summary(locations)
    elif '--sql' in sys.argv:
        # Generate SQL file instead of using API
        generate_sql_inserts(locations)
    elif '--fresh-sql' in sys.argv:
        # Generate SQL with DELETE ALL + INSERT (for use when API doesn't work)
        generate_fresh_sql(locations)
    elif '--fresh' in sys.argv:
        # Fresh import via API: delete ALL existing records, then insert new ones
        print("\n⚠️  FRESH IMPORT: All existing locations will be DELETED!")
        import_to_supabase(locations, resume=False, fresh=True)
    elif '--no-resume' in sys.argv:
        # Import without resuming from progress
        import_to_supabase(locations, resume=False)
    else:
        # Default: import via Supabase API with resume capability
        import_to_supabase(locations)


if __name__ == '__main__':
    main()
