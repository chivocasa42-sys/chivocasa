#!/usr/bin/env python3
"""
El Salvador Location Enricher
==============================
Fills in missing department and municipality data using coordinates
and El Salvador's geographic boundaries.
"""

import json
import math
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class DepartmentBounds:
    """Department geographic boundaries (approximate)."""
    name: str
    capital: str
    # Bounding box: (min_lat, max_lat, min_lon, max_lon)
    bounds: Tuple[float, float, float, float]
    # Center point for distance calculation
    center: Tuple[float, float]


# El Salvador Department boundaries (approximate bounding boxes)
# Format: name, capital, (min_lat, max_lat, min_lon, max_lon), (center_lat, center_lon)
DEPARTMENTS = [
    DepartmentBounds("San Salvador", "San Salvador", (13.60, 13.85, -89.35, -89.05), (13.70, -89.20)),
    DepartmentBounds("La Libertad", "Santa Tecla", (13.40, 13.90, -89.65, -89.25), (13.65, -89.45)),
    DepartmentBounds("Santa Ana", "Santa Ana", (13.70, 14.45, -89.90, -89.35), (14.00, -89.55)),
    DepartmentBounds("San Miguel", "San Miguel", (13.15, 13.85, -88.40, -87.80), (13.48, -88.18)),
    DepartmentBounds("Sonsonate", "Sonsonate", (13.40, 13.90, -90.00, -89.55), (13.70, -89.73)),
    DepartmentBounds("Usulután", "Usulután", (13.10, 13.60, -88.75, -88.15), (13.35, -88.45)),
    DepartmentBounds("Ahuachapán", "Ahuachapán", (13.70, 14.10, -90.15, -89.70), (13.92, -89.85)),
    DepartmentBounds("La Unión", "La Unión", (13.10, 13.70, -88.15, -87.65), (13.35, -87.85)),
    DepartmentBounds("La Paz", "Zacatecoluca", (13.20, 13.65, -89.15, -88.65), (13.45, -88.90)),
    DepartmentBounds("Chalatenango", "Chalatenango", (13.90, 14.45, -89.35, -88.75), (14.10, -89.00)),
    DepartmentBounds("Cuscatlán", "Cojutepeque", (13.60, 13.95, -89.10, -88.80), (13.75, -88.95)),
    DepartmentBounds("San Vicente", "San Vicente", (13.40, 13.80, -88.95, -88.50), (13.65, -88.78)),
    DepartmentBounds("Cabañas", "Sensuntepeque", (13.75, 14.10, -88.90, -88.45), (13.90, -88.65)),
    DepartmentBounds("Morazán", "San Francisco Gotera", (13.55, 14.00, -88.30, -87.80), (13.75, -88.10)),
]

# Major municipalities with their approximate centers
MUNICIPALITIES = {
    "San Salvador": {
        "San Salvador": ((13.68, 13.73), (-89.23, -89.17)),
        "Mejicanos": ((13.71, 13.75), (-89.23, -89.19)),
        "Soyapango": ((13.69, 13.73), (-89.17, -89.11)),
        "Apopa": ((13.78, 13.84), (-89.20, -89.14)),
        "Ilopango": ((13.68, 13.72), (-89.13, -89.08)),
        "Ciudad Delgado": ((13.71, 13.75), (-89.18, -89.15)),
        "Cuscatancingo": ((13.72, 13.75), (-89.19, -89.17)),
        "Ayutuxtepeque": ((13.73, 13.76), (-89.22, -89.19)),
        "San Marcos": ((13.64, 13.68), (-89.20, -89.16)),
        "Tonacatepeque": ((13.75, 13.81), (-89.13, -89.08)),
    },
    "La Libertad": {
        "Santa Tecla": ((13.64, 13.70), (-89.32, -89.25)),
        "Antiguo Cuscatlán": ((13.67, 13.70), (-89.27, -89.24)),
        "San Juan Opico": ((13.85, 13.90), (-89.40, -89.32)),
        "Colón": ((13.70, 13.74), (-89.38, -89.33)),
        "Quezaltepeque": ((13.81, 13.86), (-89.30, -89.24)),
        "Ciudad Arce": ((13.82, 13.87), (-89.48, -89.42)),
        "Zaragoza": ((13.58, 13.62), (-89.30, -89.25)),
        "La Libertad": ((13.47, 13.52), (-89.35, -89.28)),
    },
    "Santa Ana": {
        "Santa Ana": ((13.97, 14.02), (-89.58, -89.52)),
        "Metapán": ((14.30, 14.38), (-89.50, -89.42)),
        "Chalchuapa": ((13.96, 14.00), (-89.70, -89.64)),
        "Texistepeque": ((14.10, 14.16), (-89.52, -89.46)),
        "El Congo": ((13.89, 13.93), (-89.52, -89.46)),
        "Coatepeque": ((13.90, 13.95), (-89.58, -89.52)),
    },
    "San Miguel": {
        "San Miguel": ((13.46, 13.52), (-88.22, -88.14)),
        "Chinameca": ((13.48, 13.53), (-88.38, -88.32)),
        "Moncagua": ((13.52, 13.57), (-88.28, -88.22)),
        "Ciudad Barrios": ((13.75, 13.80), (-88.30, -88.24)),
    },
    "Sonsonate": {
        "Sonsonate": ((13.70, 13.75), (-89.75, -89.69)),
        "Acajutla": ((13.55, 13.62), (-89.85, -89.78)),
        "Juayúa": ((13.83, 13.88), (-89.77, -89.72)),
        "Izalco": ((13.73, 13.78), (-89.70, -89.64)),
        "Nahuizalco": ((13.76, 13.80), (-89.76, -89.70)),
    },
    "Usulután": {
        "Usulután": ((13.33, 13.38), (-88.47, -88.42)),
        "Santiago de María": ((13.47, 13.52), (-88.48, -88.42)),
        "Berlín": ((13.48, 13.53), (-88.55, -88.49)),
        "Jiquilisco": ((13.30, 13.35), (-88.60, -88.54)),
    },
    "Ahuachapán": {
        "Ahuachapán": ((13.90, 13.95), (-89.88, -89.82)),
        "Atiquizaya": ((13.96, 14.00), (-89.78, -89.72)),
        "Concepción de Ataco": ((13.85, 13.90), (-89.88, -89.82)),
        "Apaneca": ((13.83, 13.88), (-89.82, -89.78)),
    },
    "La Unión": {
        "La Unión": ((13.32, 13.37), (-87.87, -87.82)),
        "Santa Rosa de Lima": ((13.60, 13.66), (-87.90, -87.84)),
        "Pasaquina": ((13.56, 13.62), (-87.85, -87.78)),
        "Conchagua": ((13.28, 13.34), (-87.90, -87.82)),
    },
    "La Paz": {
        "Zacatecoluca": ((13.50, 13.55), (-88.88, -88.82)),
        "San Luis Talpa": ((13.46, 13.50), (-89.10, -89.04)),
        "Olocuilta": ((13.55, 13.60), (-89.12, -89.06)),
        "San Pedro Masahuat": ((13.52, 13.57), (-89.02, -88.96)),
    },
    "Chalatenango": {
        "Chalatenango": ((14.02, 14.08), (-88.96, -88.90)),
        "Nueva Concepción": ((14.10, 14.16), (-89.30, -89.24)),
        "La Palma": ((14.28, 14.34), (-89.20, -89.14)),
        "Tejutla": ((14.08, 14.14), (-89.12, -89.06)),
    },
    "Cuscatlán": {
        "Cojutepeque": ((13.70, 13.75), (-88.96, -88.90)),
        "San Pedro Perulapán": ((13.72, 13.78), (-89.05, -88.98)),
        "Suchitoto": ((13.92, 13.98), (-89.05, -88.98)),
    },
    "San Vicente": {
        "San Vicente": ((13.62, 13.68), (-88.82, -88.76)),
        "Tecoluca": ((13.50, 13.56), (-88.82, -88.74)),
        "Apastepeque": ((13.65, 13.72), (-88.78, -88.72)),
    },
    "Cabañas": {
        "Sensuntepeque": ((13.85, 13.92), (-88.66, -88.60)),
        "Ilobasco": ((13.82, 13.88), (-88.88, -88.82)),
        "Victoria": ((13.94, 14.00), (-88.68, -88.62)),
    },
    "Morazán": {
        "San Francisco Gotera": ((13.68, 13.74), (-88.12, -88.06)),
        "Jocoro": ((13.60, 13.66), (-88.04, -87.98)),
        "Sociedad": ((13.68, 13.74), (-88.02, -87.96)),
        "Corinto": ((13.92, 13.98), (-88.02, -87.96)),
    },
}


def get_department_from_coords(lat: float, lon: float) -> Optional[str]:
    """Determine department from coordinates using bounding boxes."""
    
    # Check each department's bounding box
    candidates = []
    for dept in DEPARTMENTS:
        min_lat, max_lat, min_lon, max_lon = dept.bounds
        
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            # Calculate distance to center for ranking
            dist = math.sqrt((lat - dept.center[0])**2 + (lon - dept.center[1])**2)
            candidates.append((dept.name, dist))
    
    if candidates:
        # Return the closest department by center distance
        candidates.sort(key=lambda x: x[1])
        return candidates[0][0]
    
    # If not in any bounding box, find closest by center
    closest = None
    min_dist = float('inf')
    
    for dept in DEPARTMENTS:
        dist = math.sqrt((lat - dept.center[0])**2 + (lon - dept.center[1])**2)
        if dist < min_dist:
            min_dist = dist
            closest = dept.name
    
    return closest


def get_municipality_from_coords(lat: float, lon: float, department: str) -> Optional[str]:
    """Determine municipality from coordinates within a department."""
    
    if department not in MUNICIPALITIES:
        return None
    
    for muni_name, bounds in MUNICIPALITIES[department].items():
        (min_lat, max_lat), (min_lon, max_lon) = bounds
        
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return muni_name
    
    return None


def enrich_locations(input_file: str, output_file: str = None):
    """Enrich location data with department and municipality."""
    
    if output_file is None:
        output_file = input_file
    
    print(f"📂 Loading {input_file}...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    locations = data.get('locations', [])
    
    print(f"📊 Found {len(locations)} locations")
    
    enriched_count = 0
    dept_enriched = 0
    muni_enriched = 0
    
    for loc in locations:
        lat = loc.get('latitude', 0)
        lon = loc.get('longitude', 0)
        
        if not lat or not lon:
            continue
        
        # Enrich department if missing
        if not loc.get('department'):
            dept = get_department_from_coords(lat, lon)
            if dept:
                loc['department'] = dept
                dept_enriched += 1
                enriched_count += 1
        
        # Enrich municipality if missing but department is known
        if not loc.get('municipality') and loc.get('department'):
            muni = get_municipality_from_coords(lat, lon, loc['department'])
            if muni:
                loc['municipality'] = muni
                muni_enriched += 1
    
    # Update statistics
    with_full_data = sum(1 for loc in locations if loc.get('municipality') and loc.get('department'))
    with_dept = sum(1 for loc in locations if loc.get('department'))
    
    by_dept = {}
    by_muni = {}
    
    for loc in locations:
        dept = loc.get('department') or 'Sin Departamento'
        by_dept[dept] = by_dept.get(dept, 0) + 1
        
        muni = loc.get('municipality') or 'Sin Municipio'
        by_muni[muni] = by_muni.get(muni, 0) + 1
    
    data['metadata']['with_complete_data'] = with_full_data
    data['metadata']['with_department'] = with_dept
    data['metadata']['statistics']['by_department'] = dict(sorted(by_dept.items(), key=lambda x: -x[1]))
    data['metadata']['statistics']['by_municipality'] = dict(sorted(by_muni.items(), key=lambda x: -x[1])[:30])
    data['metadata']['enrichment'] = {
        'departments_added': dept_enriched,
        'municipalities_added': muni_enriched
    }
    
    # Save
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Enrichment complete!")
    print(f"   📍 Departments added: {dept_enriched}")
    print(f"   🏘️ Municipalities added: {muni_enriched}")
    print(f"   📊 Total with department: {with_dept} ({with_dept*100//len(locations)}%)")
    print(f"   📊 Total with full data: {with_full_data} ({with_full_data*100//len(locations)}%)")
    print(f"\n💾 Saved to {output_file}")


def main():
    import sys
    
    input_file = 'el_salvador_locations.json'
    output_file = 'el_salvador_locations.json'  # Overwrite
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    if len(sys.argv) > 2:
        output_file = sys.argv[2]
    
    enrich_locations(input_file, output_file)


if __name__ == '__main__':
    main()
