#!/usr/bin/env python3
"""
Convert residential_areas_el_salvador 1.json to Supabase INSERT SQL statements.

Target table schema:
create table public.sv_locations (
  id character varying not null,
  name text not null,
  department text not null,
  municipality text null,
  latitude numeric(10, 7) null,
  longitude numeric(10, 7) null,
  created_at timestamp with time zone null default now(),
  district text null,
  labels jsonb null,
  loc_admin jsonb null,
  country text null,
  constraint sv_locations_pkey primary key (id)
)
"""

import json
import os
from datetime import datetime


def escape_sql_string(value):
    """Escape single quotes for SQL strings."""
    if value is None:
        return None
    return str(value).replace("'", "''")


def to_sql_value(value, is_string=True):
    """Convert a Python value to SQL value syntax."""
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return "NULL"
    if is_string:
        return f"'{escape_sql_string(value)}'"
    return str(value)


def to_jsonb_value(obj):
    """Convert a Python dict to JSONB SQL value."""
    if obj is None:
        return "NULL"
    escaped = json.dumps(obj, ensure_ascii=False).replace("'", "''")
    return f"'{escaped}'::jsonb"


def convert_json_to_sql(json_path, output_path, batch_size=100):
    """
    Convert the residential areas JSON file to SQL INSERT statements.
    
    Args:
        json_path: Path to the input JSON file
        output_path: Path to the output SQL file
        batch_size: Number of records per INSERT statement (for performance)
    """
    # Load JSON data
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    areas = data.get('areas', [])
    metadata = data.get('metadata', {})
    
    print(f"Found {len(areas)} residential areas in JSON")
    print(f"Source: {metadata.get('source', 'Unknown')}")
    print(f"Generated at: {metadata.get('generated_at', 'Unknown')}")
    
    # Filter out records with null or empty names (required field)
    valid_areas = [a for a in areas if a.get('name') and str(a.get('name')).strip()]
    skipped_count = len(areas) - len(valid_areas)
    
    if skipped_count > 0:
        print(f"Skipping {skipped_count} records with null/empty names")
    
    print(f"Valid records to insert: {len(valid_areas)}")
    
    with open(output_path, 'w', encoding='utf-8') as f:
        # Write header
        f.write("-- ============================================================\n")
        f.write("-- El Salvador Residential Areas - INSERT Script for Supabase\n")
        f.write(f"-- Generated: {datetime.now().isoformat()}\n")
        f.write(f"-- Source: {metadata.get('source', 'Unknown')}\n")
        f.write(f"-- Total Records in JSON: {len(areas)}\n")
        f.write(f"-- Skipped (null/empty name): {skipped_count}\n")
        f.write(f"-- Valid Records to Insert: {len(valid_areas)}\n")
        f.write("-- ============================================================\n\n")
        
        # Optional: Delete existing records first (commented out by default)
        f.write("-- Uncomment the following line to delete existing records before inserting:\n")
        f.write("-- DELETE FROM public.sv_locations WHERE country = 'El Salvador';\n\n")
        
        # Process in batches
        for batch_start in range(0, len(valid_areas), batch_size):
            batch_end = min(batch_start + batch_size, len(valid_areas))
            batch = valid_areas[batch_start:batch_end]
            
            f.write(f"-- Batch {batch_start // batch_size + 1}: Records {batch_start + 1} to {batch_end}\n")
            f.write("INSERT INTO public.sv_locations (id, name, department, municipality, latitude, longitude, district, labels, loc_admin, country)\nVALUES\n")
            
            values = []
            for area in batch:
                # Map JSON fields to table columns
                id_val = to_sql_value(area.get('osm_id'))
                name_val = to_sql_value(area.get('name'))
                department_val = to_sql_value(area.get('state'))  # state = departamento
                municipality_val = to_sql_value(area.get('city'))  # city = municipio
                latitude_val = to_sql_value(area.get('lat'), is_string=False)
                longitude_val = to_sql_value(area.get('lon'), is_string=False)
                district_val = to_sql_value(area.get('district') or None)
                
                # Build labels JSONB object
                labels_obj = {
                    "label": area.get('label'),
                    "type": area.get('type'),
                    "class": area.get('class'),
                    "nominatim": area.get('nominatim', False)
                }
                labels_val = to_jsonb_value(labels_obj)
                
                # Admin levels as JSONB
                loc_admin_val = to_jsonb_value(area.get('admin'))
                
                country_val = to_sql_value(area.get('country'))
                
                values.append(
                    f"  ({id_val}, {name_val}, {department_val}, {municipality_val}, "
                    f"{latitude_val}, {longitude_val}, {district_val}, {labels_val}, "
                    f"{loc_admin_val}, {country_val})"
                )
            
            f.write(",\n".join(values))
            f.write("\nON CONFLICT (id) DO UPDATE SET\n")
            f.write("  name = EXCLUDED.name,\n")
            f.write("  department = EXCLUDED.department,\n")
            f.write("  municipality = EXCLUDED.municipality,\n")
            f.write("  latitude = EXCLUDED.latitude,\n")
            f.write("  longitude = EXCLUDED.longitude,\n")
            f.write("  district = EXCLUDED.district,\n")
            f.write("  labels = EXCLUDED.labels,\n")
            f.write("  loc_admin = EXCLUDED.loc_admin,\n")
            f.write("  country = EXCLUDED.country;\n\n")
        
        f.write("-- ============================================================\n")
        f.write(f"-- End of INSERT script ({len(valid_areas)} valid records)\n")
        f.write("-- ============================================================\n")
    
    print(f"\nSQL file generated: {output_path}")
    print(f"Total batches: {(len(valid_areas) + batch_size - 1) // batch_size}")


if __name__ == "__main__":
    # Paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    
    json_path = os.path.join(project_dir, "residential_areas_el_salvador 1.json")
    output_path = os.path.join(project_dir, "sql", "insert_sv_locations_residential.sql")
    
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    convert_json_to_sql(json_path, output_path, batch_size=100)
