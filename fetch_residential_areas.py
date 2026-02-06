#!/usr/bin/env python3
"""
Fetch all landuse=residential and place=neighbourhood areas from El Salvador 
using OpenStreetMap's Overpass API and Nominatim for address details.
Outputs: residential_areas_el_salvador.json with complete geocoding data.

Usage:
    python fetch_residential_areas.py              # Fetch all areas
    python fetch_residential_areas.py --limit 50   # Fetch only first 50 areas (for testing)
    python fetch_residential_areas.py --clear-cache  # Clear cache and start fresh
"""

import argparse
import json
import os
import time
import requests
from typing import Optional

try:
    from shapely.geometry import Point, Polygon, shape
    from shapely.prepared import prep
    SHAPELY_AVAILABLE = True
except ImportError:
    SHAPELY_AVAILABLE = False
    print("⚠️ Shapely not installed. Spatial parent lookup disabled.")
    print("   Install with: pip install shapely")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_LOOKUP_URL = "https://nominatim.openstreetmap.org/lookup"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"

CACHE_FILE = "nominatim_cache.json"
REVERSE_CACHE_FILE = "nominatim_reverse_cache.json"
BATCH_SIZE = 50


def create_nominatim_session() -> requests.Session:
    """Create a requests session configured for Nominatim API."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "ChivocasaBot/1.0 (https://github.com/chivocasa42-sys)",
        "Accept": "application/json",
        "Accept-Language": "es,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    })
    return session


def load_cache() -> dict:
    """Load cached Nominatim results."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict):
    """Save Nominatim results to cache."""
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def query_overpass(query: str, max_retries: int = 3) -> dict:
    """Execute an Overpass API query with retry logic."""
    for attempt in range(max_retries):
        try:
            print(f"  Overpass query (attempt {attempt + 1}/{max_retries})...")
            response = requests.post(
                OVERPASS_URL,
                data={"data": query},
                timeout=300,
                headers={"Accept-Charset": "utf-8"}
            )
            response.raise_for_status()
            response.encoding = 'utf-8'
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"  Request failed: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                print(f"  Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
            else:
                raise
    return {}


def get_residential_areas() -> list[dict]:
    """Fetch all landuse=residential and place=neighbourhood areas in El Salvador."""
    
    query = """
    [out:json][timeout:300];
    
    area["ISO3166-1"="SV"][admin_level=2]->.el_salvador;
    
    (
      way["landuse"="residential"](area.el_salvador);
      relation["landuse"="residential"](area.el_salvador);
      way["place"="neighbourhood"](area.el_salvador);
      relation["place"="neighbourhood"](area.el_salvador);
    );
    
    out center tags;
    """
    
    print("Fetching residential areas and neighbourhoods from El Salvador...")
    result = query_overpass(query)
    
    elements = result.get("elements", [])
    print(f"Found {len(elements)} areas (residential + neighbourhoods)")
    
    return elements


def osm_type_prefix(osm_type: str) -> str:
    """Convert OSM type to Nominatim prefix (N=node, W=way, R=relation)."""
    prefixes = {"node": "N", "way": "W", "relation": "R"}
    return prefixes.get(osm_type, "W")


def nominatim_lookup_batch(session: requests.Session, osm_ids: list[str], cache: dict, max_retries: int = 3) -> dict:
    """Batch lookup using Nominatim /lookup endpoint with geocodejson format."""
    
    uncached_ids = [oid for oid in osm_ids if oid not in cache]
    
    if not uncached_ids:
        print(f"    All {len(osm_ids)} IDs cached")
        return {oid: cache[oid] for oid in osm_ids}
    
    params = {
        "osm_ids": ",".join(uncached_ids),
        "format": "geocodejson",
    }
    
    print(f"    Fetching {len(uncached_ids)} IDs from Nominatim...")
    
    for attempt in range(max_retries):
        try:
            response = session.get(NOMINATIM_LOOKUP_URL, params=params, timeout=60)
            
            print(f"    Response status: {response.status_code}")
            
            if response.status_code == 429:
                wait_time = int(response.headers.get("Retry-After", 60))
                print(f"    ⏳ Rate limited. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            
            if response.status_code == 403:
                print(f"    ❌ 403 Forbidden")
                # Mark uncached as "not_found" so we don't retry
                for oid in uncached_ids:
                    cache[oid] = "not_found"
                return {oid: cache.get(oid) for oid in osm_ids}
            
            response.raise_for_status()
            response.encoding = 'utf-8'
            data = response.json()
            
            # geocodejson returns a FeatureCollection
            features = data.get("features", [])
            print(f"    ✓ Received {len(features)} results (out of {len(uncached_ids)} requested)")
            
            # Mark IDs that were returned
            returned_ids = set()
            
            for feature in features:
                props = feature.get("properties", {})
                geocoding = props.get("geocoding", {})
                geometry = feature.get("geometry", {})
                coords = geometry.get("coordinates", [0, 0])  # [lon, lat]
                
                osm_type = geocoding.get("osm_type", "way")
                osm_id = geocoding.get("osm_id", "")
                osm_key = f"{osm_type_prefix(osm_type)}{osm_id}"
                returned_ids.add(osm_key)
                
                # Extract admin directly from geocodejson (already formatted as level4, level5, etc.)
                admin = geocoding.get("admin", {}) or {}
                
                result = {
                    "name": geocoding.get("name", ""),
                    "label": geocoding.get("label", ""),
                    "district": geocoding.get("district", ""),
                    "city": geocoding.get("city", ""),
                    "state": geocoding.get("state", ""),
                    "country": geocoding.get("country", ""),
                    "type": geocoding.get("type", ""),
                    "class": geocoding.get("osm_key", ""),
                    "lat": float(coords[1]) if len(coords) > 1 else 0,
                    "lon": float(coords[0]) if len(coords) > 0 else 0,
                    "admin": admin,  # Admin hierarchy levels (level4, level5, level6, etc.)
                    "nominatim": True  # Flag that this came from Nominatim
                }
                
                cache[osm_key] = result
                print(f"      ✓ {osm_key}: {result['name'] or result['district'] or 'unnamed'}")
            
            # Mark IDs that were NOT returned as "not_found"
            for oid in uncached_ids:
                if oid not in returned_ids and oid not in cache:
                    cache[oid] = "not_found"
                    print(f"      ✗ {oid}: not in Nominatim")
            
            break
            
        except requests.exceptions.RequestException as e:
            print(f"    ⚠️ Error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) * 5)
    
    return {oid: cache.get(oid) for oid in osm_ids}


def extract_center(element: dict) -> Optional[tuple[float, float]]:
    """Extract center coordinates from an OSM element."""
    
    if "center" in element:
        return (element["center"]["lat"], element["center"]["lon"])
    
    if "lat" in element and "lon" in element:
        return (element["lat"], element["lon"])
    
    return None


def get_parent_polygons() -> list[dict]:
    """Fetch named areas with full polygon geometries from Overpass.
    
    These are larger areas (like "Colonia Santa Luisa", "Residencial Las Mercedes") 
    that contain smaller areas (like "Pol N", "Pol B").
    
    Includes multiple place types to catch different tagging conventions.
    """
    # Query for named areas with geometry - expanded to catch more place types
    query = """
    [out:json][timeout:300];
    
    area["ISO3166-1"="SV"][admin_level=2]->.el_salvador;
    
    (
      // Residential landuse
      way["landuse"="residential"]["name"](area.el_salvador);
      relation["landuse"="residential"]["name"](area.el_salvador);
      
      // Various place types that might contain residential blocks
      way["place"~"neighbourhood|suburb|locality|quarter|village|hamlet"]["name"](area.el_salvador);
      relation["place"~"neighbourhood|suburb|locality|quarter|village|hamlet"]["name"](area.el_salvador);
      
      // Named boundary areas
      way["boundary"="administrative"]["name"](area.el_salvador);
      relation["boundary"="administrative"]["name"][admin_level~"[789]|10"](area.el_salvador);
    );
    
    out body geom;
    """
    
    print("\n🗺️ Fetching parent polygons with geometries...")
    result = query_overpass(query)
    
    elements = result.get("elements", [])
    print(f"   Found {len(elements)} named areas with geometries")
    
    return elements


def build_parent_index(elements: list[dict]) -> list[dict]:
    """Build a spatial index of parent polygons.
    
    Returns a list of dicts with 'name', 'osm_id', and 'geometry' (Shapely polygon).
    """
    if not SHAPELY_AVAILABLE:
        print("   ⚠️ Shapely not available, skipping spatial index")
        return []
    
    parent_polygons = []
    
    for element in elements:
        name = element.get("tags", {}).get("name", "")
        if not name:
            continue
        
        osm_type = element.get("type", "way")
        osm_id = element.get("id")
        
        # Extract geometry based on element type
        geometry = None
        
        if osm_type == "way":
            # Way has 'geometry' as a list of {lat, lon} points
            geom_points = element.get("geometry", [])
            if len(geom_points) >= 3:
                # Convert to Shapely polygon (lon, lat order)
                coords = [(p["lon"], p["lat"]) for p in geom_points]
                try:
                    geometry = Polygon(coords)
                    if not geometry.is_valid:
                        geometry = geometry.buffer(0)  # Fix invalid geometry
                except Exception:
                    continue
        
        elif osm_type == "relation":
            # Relations have 'members' with geometry
            # Try to extract outer ring
            members = element.get("members", [])
            outer_coords = []
            for member in members:
                if member.get("role") == "outer" and member.get("geometry"):
                    for p in member["geometry"]:
                        outer_coords.append((p["lon"], p["lat"]))
            
            if len(outer_coords) >= 3:
                try:
                    geometry = Polygon(outer_coords)
                    if not geometry.is_valid:
                        geometry = geometry.buffer(0)
                except Exception:
                    continue
        
        if geometry and geometry.is_valid and not geometry.is_empty:
            parent_polygons.append({
                "name": name,
                "osm_id": f"{osm_type_prefix(osm_type)}{osm_id}",
                "geometry": geometry,
                "prepared": prep(geometry),  # Prepared geometry for faster lookups
                "area": geometry.area
            })
    
    # Sort by area (smallest first) so we find the most specific parent
    parent_polygons.sort(key=lambda x: x["area"])
    
    print(f"   Built spatial index with {len(parent_polygons)} polygons")
    return parent_polygons


def find_parent_residential(lat: float, lon: float, parent_polygons: list[dict], own_name: str = "") -> Optional[str]:
    """Find which parent polygon contains this point.
    
    Returns the name of the containing polygon, or None if not found.
    Skips polygons with the same name as the point's own name.
    """
    if not SHAPELY_AVAILABLE or not parent_polygons:
        return None
    
    point = Point(lon, lat)  # Shapely uses (x, y) = (lon, lat)
    
    for parent in parent_polygons:
        # Skip if the parent has the same name (don't return own name as parent)
        if parent["name"] == own_name:
            continue
        
        # Use prepared geometry for faster containment check
        if parent["prepared"].contains(point):
            return parent["name"]
    
    return None


def extract_parent_context(label: str, name: str) -> str:
    """Extract parent context from Nominatim label.
    
    Label format is typically: "Name, Parent, City, State, Country"
    We want to extract "Parent" (the immediate parent of this area).
    """
    if not label or not name:
        return ""
    
    # Split by comma and strip whitespace
    parts = [p.strip() for p in label.split(",")]
    
    # Find the name in parts and get the next part (parent)
    for i, part in enumerate(parts):
        if part == name and i + 1 < len(parts):
            return parts[i + 1]
    
    # If name wasn't found exactly, try to get second part
    if len(parts) >= 2:
        return parts[1]
    
    return ""


def load_reverse_cache() -> dict:
    """Load cached reverse geocoding results."""
    if os.path.exists(REVERSE_CACHE_FILE):
        try:
            with open(REVERSE_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_reverse_cache(cache: dict):
    """Save reverse geocoding results to cache."""
    with open(REVERSE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def reverse_geocode(session: requests.Session, lat: float, lon: float, cache: dict) -> Optional[str]:
    """Reverse geocode coordinates to get parent context.
    
    Returns the neighbourhood/residential area name from the address hierarchy.
    """
    cache_key = f"{lat:.6f},{lon:.6f}"
    
    if cache_key in cache:
        return cache[cache_key]
    
    params = {
        "lat": lat,
        "lon": lon,
        "format": "geocodejson",
        "zoom": 18,  # High zoom for detailed address
    }
    
    try:
        response = session.get(NOMINATIM_REVERSE_URL, params=params, timeout=30)
        
        if response.status_code == 429:
            wait_time = int(response.headers.get("Retry-After", 60))
            print(f"      ⏳ Rate limited. Waiting {wait_time}s...")
            time.sleep(wait_time)
            return reverse_geocode(session, lat, lon, cache)  # Retry
        
        if response.status_code != 200:
            cache[cache_key] = None
            return None
        
        response.encoding = 'utf-8'
        data = response.json()
        
        # Extract from geocodejson format
        features = data.get("features", [])
        if features:
            props = features[0].get("properties", {})
            geocoding = props.get("geocoding", {})
            
            # Try to get neighbourhood, then locality, then district
            result = (
                geocoding.get("neighbourhood") or
                geocoding.get("locality") or
                geocoding.get("district") or
                geocoding.get("city") or
                ""
            )
            
            # Also check admin hierarchy
            if not result:
                admin = geocoding.get("admin", {})
                # Look for level6, level7, level8 (more local levels)
                for level in ["level8", "level7", "level6"]:
                    if admin.get(level):
                        result = admin[level]
                        break
            
            cache[cache_key] = result
            return result
        
        cache[cache_key] = None
        return None
        
    except Exception as e:
        print(f"      ⚠️ Reverse geocode error: {e}")
        cache[cache_key] = None
        return None


def deduplicate_names(areas: list[dict], parent_polygons: list[dict] = None, session: requests.Session = None) -> list[dict]:
    """Add display_name field with parent context for duplicate names.
    
    For unique names: display_name = name
    For duplicate names: display_name = "name (Parent Context)"
    
    Uses spatial lookup (primary) or reverse geocoding (fallback) for parent context.
    """
    from collections import Counter
    
    # Count occurrences of each name
    name_counts = Counter(a.get("name", "") for a in areas)
    
    # Find duplicate names (count > 1)
    duplicate_names = {name for name, count in name_counts.items() if count > 1 and name}
    
    print(f"\n📊 Name deduplication:")
    print(f"   - Total unique names: {len(name_counts)}")
    print(f"   - Duplicate name groups: {len(duplicate_names)}")
    
    if parent_polygons:
        print(f"   - Using spatial index with {len(parent_polygons)} parent polygons")
    
    spatial_hits = 0
    reverse_calls = 0
    reverse_cache = load_reverse_cache() if session else {}
    
    # Add display_name to each area
    for area in areas:
        name = area.get("name", "")
        label = area.get("label", "")
        
        if name in duplicate_names:
            parent = None
            
            # Method 1: Try spatial lookup first (most reliable)
            if parent_polygons:
                lat = area.get("lat", 0)
                lon = area.get("lon", 0)
                if lat and lon:
                    parent = find_parent_residential(lat, lon, parent_polygons, own_name=name)
                    if parent:
                        spatial_hits += 1
            
            # Method 2: Try extracting from label
            if not parent:
                parent = extract_parent_context(label, name)
            
            # Method 3: Fallback to reverse geocoding
            if not parent and session:
                lat = area.get("lat", 0)
                lon = area.get("lon", 0)
                if lat and lon:
                    cache_key = f"{lat:.6f},{lon:.6f}"
                    if cache_key not in reverse_cache:
                        reverse_calls += 1
                        if reverse_calls % 10 == 0:
                            print(f"   🔄 Reverse geocoding... ({reverse_calls} calls)")
                        time.sleep(1.1)  # Rate limit
                    parent = reverse_geocode(session, lat, lon, reverse_cache)
            
            if parent and parent != name:  # Don't use parent if it's the same as name
                area["display_name"] = f"{name} ({parent})"
                area["parent_residential"] = parent  # Also store separately
            else:
                # No parent found, use name as-is
                area["display_name"] = name
                area["parent_residential"] = None
        else:
            # Unique name, no disambiguation needed
            area["display_name"] = name
            area["parent_residential"] = None
    
    # Save reverse cache
    if session:
        save_reverse_cache(reverse_cache)
    
    print(f"   ✓ Spatial lookups found: {spatial_hits}")
    if reverse_calls > 0:
        print(f"   ✓ Reverse geocode calls: {reverse_calls}")
    
    # Note: Some display_names may still be duplicates if no parent context was found
    # These will remain as-is (duplicates allowed)
    
    return areas


def test_nominatim_connection(session: requests.Session) -> bool:
    """Test if we can connect to Nominatim."""
    print("\nTesting Nominatim connection...")
    
    params = {"osm_ids": "W137269034", "format": "json"}
    
    try:
        response = session.get(NOMINATIM_LOOKUP_URL, params=params, timeout=30)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            print("  ✓ Nominatim connection OK")
            return True
        else:
            print(f"  ✗ Status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ✗ Connection error: {e}")
        return False


def main():
    """Main function to fetch residential areas and export to JSON."""
    
    parser = argparse.ArgumentParser(
        description="Fetch residential areas from El Salvador (OpenStreetMap)"
    )
    parser.add_argument("--limit", "-l", type=int, default=None,
        help="Limit the number of areas to process (for testing)")
    parser.add_argument("--clear-cache", action="store_true",
        help="Clear the cache and start fresh")
    parser.add_argument("--test-only", action="store_true",
        help="Only test the Nominatim connection")
    parser.add_argument("--nominatim-only", action="store_true",
        help="Only include areas that have Nominatim address data")
    args = parser.parse_args()
    
    print("=" * 70)
    print("Fetching residential areas from El Salvador (OpenStreetMap)")
    print("=" * 70)
    
    session = create_nominatim_session()
    print(f"\nUser-Agent: {session.headers['User-Agent']}")
    
    if not test_nominatim_connection(session):
        if args.test_only:
            return
        print("\n⚠️ Nominatim connection failed. Proceeding anyway...")
    
    if args.test_only:
        return
    
    if args.clear_cache:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            print("\n🗑️ Cache cleared!")
        cache = {}
    else:
        cache = load_cache()
        print(f"\nLoaded {len(cache)} cached results")
    
    # Step 1: Get all residential areas from Overpass
    residential_areas = get_residential_areas()
    
    if not residential_areas:
        print("No residential areas found!")
        return
    
    # Step 2: Build areas_data from Overpass (this is the source of truth)
    areas_data = []
    for element in residential_areas:
        center = extract_center(element)
        if center:
            tags = element.get("tags", {})
            osm_type = element.get("type", "way")
            osm_id = element.get("id")
            osm_key = f"{osm_type_prefix(osm_type)}{osm_id}"
            
            areas_data.append({
                "osm_id": osm_key,
                "osm_type": osm_type,
                "name": tags.get("name", ""),
                "lat": center[0],
                "lon": center[1],
                "tags": tags
            })
    
    if args.limit and args.limit > 0:
        areas_data = areas_data[:args.limit]
        print(f"\n⚠️  TESTING MODE: Limited to {args.limit} areas")
    
    print(f"\nProcessing {len(areas_data)} areas...")
    
    # Step 3: Batch lookup from Nominatim
    osm_keys = [a["osm_id"] for a in areas_data]
    batches = [osm_keys[i:i + BATCH_SIZE] for i in range(0, len(osm_keys), BATCH_SIZE)]
    total_batches = len(batches)
    
    print(f"\nFetching details via Nominatim /lookup (batches of {BATCH_SIZE})...")
    
    for batch_num, batch in enumerate(batches, 1):
        cached_in_batch = sum(1 for oid in batch if oid in cache)
        uncached_in_batch = len(batch) - cached_in_batch
        
        print(f"\nBatch {batch_num}/{total_batches}: {len(batch)} IDs ({cached_in_batch} cached, {uncached_in_batch} to fetch)")
        
        nominatim_lookup_batch(session, batch, cache)
        
        if batch_num % 5 == 0:
            save_cache(cache)
        
        if uncached_in_batch > 0:
            time.sleep(1.1)
    
    save_cache(cache)
    print(f"\n💾 Cache saved ({len(cache)} entries)")
    
    # Step 4: Merge Overpass data with Nominatim data
    output_areas = []
    nominatim_found = 0
    nominatim_not_found = 0
    
    for area in areas_data:
        osm_key = area["osm_id"]
        nominatim_data = cache.get(osm_key)
        
        if nominatim_data and nominatim_data != "not_found" and isinstance(nominatim_data, dict):
            # Use Nominatim data
            nominatim_found += 1
            output_areas.append({
                "osm_id": osm_key,
                **nominatim_data
            })
        else:
            # Use Overpass data only (no address info)
            nominatim_not_found += 1
            output_areas.append({
                "osm_id": osm_key,
                "name": area["name"],
                "label": "",
                "district": "",
                "city": "",
                "state": "",
                "country": "El Salvador",
                "type": area["tags"].get("landuse") or area["tags"].get("place") or "",
                "class": "landuse" if "landuse" in area["tags"] else "place",
                "lat": area["lat"],
                "lon": area["lon"],
                "admin": {},  # Empty admin for consistency
                "nominatim": False  # Flag that this is Overpass-only
            })
    
    # Step 5: Filter if --nominatim-only
    if args.nominatim_only:
        output_areas = [a for a in output_areas if a.get("nominatim") == True]
        print(f"\n📋 Filtered to {len(output_areas)} areas with Nominatim data")
    
    # Step 5.5: Build spatial index for parent lookup
    parent_polygons = []
    if SHAPELY_AVAILABLE:
        parent_elements = get_parent_polygons()
        parent_polygons = build_parent_index(parent_elements)
    
    # Step 5.6: Deduplicate names (add display_name with parent context for duplicates)
    output_areas = deduplicate_names(output_areas, parent_polygons=parent_polygons, session=session)
    
    # Step 6: Build output
    output_data = {
        "metadata": {
            "source": "OpenStreetMap via Overpass + Nominatim",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "query": "landuse=residential OR place=neighbourhood in El Salvador",
            "total_areas": len(output_areas),
            "nominatim_found": nominatim_found,
            "nominatim_not_found": nominatim_not_found
        },
        "areas": output_areas
    }
    
    # Step 6: Export
    output_file = "residential_areas_el_salvador.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Exported {len(output_areas)} areas to {output_file}")
    print(f"   - With Nominatim data: {nominatim_found}")
    print(f"   - Overpass only (no address): {nominatim_not_found}")
    
    # Summary
    departments = set(a.get("state", "") for a in output_areas if a.get("state"))
    if departments:
        print(f"\nDepartments found: {', '.join(sorted(departments))}")


if __name__ == "__main__":
    main()
