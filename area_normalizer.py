"""
Area Normalizer Module
======================
Normalizes property areas from various units (varas², ft², m²) to square meters (m²).
Also normalizes other listing specs like bedrooms, bathrooms, and parking.

Conversion Factors (Standard):
- 1 vara² (El Salvador) = 0.6987 m²
- 1 ft² = 0.0929 m² (0.3048² = 0.09290304)

Usage:
    from area_normalizer import normalize_area, normalize_specs_area, normalize_listing_specs
    
    result = normalize_area("120 v2")
    # {'original': '120 v2', 'value_m2': 83.84, 'unit_detected': 'vara2', 'parse_success': True}
    
    specs = normalize_listing_specs(specs_dict)
    # Returns standardized dict with keys: 'bedrooms', 'bathrooms', 'parking', 'area_m2'
"""

import re
from typing import Tuple, Optional, Dict, Any

# ============== CONVERSION CONSTANTS ==============
# Standard conversion factors (do not modify unless officially changed)
VARA2_TO_M2 = 0.6987  # 1 vara cuadrada (El Salvador) = 0.6987 m²
FT2_TO_M2 = 0.0929    # 1 pie cuadrado = 0.0929 m² (exact: 0.09290304)

# ============== UNIT DETECTION PATTERNS ==============
# Patterns for detecting area units in text (order matters - more specific first)

UNIT_PATTERNS = {
    'm2': [
        r'\bm[²2]\b',           # m² or m2
        r'\bmt[s]?2\b',         # mt2 or mts2
        r'\bmetros?\s*cuadrados?\b',  # metros cuadrados
        r'\bmetros?\b',         # metros (alone, assumed m²)
    ],
    'vara2': [
        r'\bv[²2]\b',           # v² or v2
        r'\bvaras?[²2]\b',      # vara2 or varas2
        r'\bvaras?\s*cuadradas?\b',   # varas cuadradas
        r'\bvaras?\b',          # varas (alone, assumed vara²)
    ],
    'ft2': [
        r'\bft[²2]\b',          # ft² or ft2
        r'\bsqft\b',            # sqft
        r'\bsq\.?\s*ft\b',      # sq ft or sq.ft
        r'\bpies?\s*cuadrados?\b',    # pies cuadrados
        r'\bpies?\b',           # pies (alone, assumed ft²)
    ],
}


def detect_unit(text: str) -> Optional[str]:
    """
    Detect the area unit from text.
    
    Args:
        text: Raw text containing area information (e.g., "120 v2", "85 m2")
        
    Returns:
        'm2', 'vara2', 'ft2', or None if no unit detected
    """
    if not text:
        return None
    
    text_lower = text.lower().strip()
    
    # Check each unit type's patterns
    for unit, patterns in UNIT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return unit
    
    return None


def parse_area_value(text: str) -> Tuple[Optional[float], bool]:
    """
    Extract numeric value from area text.
    
    Handles:
    - Thousands separators: "1,200" or "1.200"
    - Decimals: "80.5" or "80,5"
    - Ranges: "120-150" (returns average)
    - Mixed text: "Área: 120 m2 aprox"
    
    Args:
        text: Raw text containing numeric area value
        
    Returns:
        Tuple of (value: float, is_range: bool)
        Returns (None, False) if parsing fails
    """
    if not text:
        return None, False
    
    text = text.strip()
    
    # First, try to find a range pattern (e.g., "120-150", "120 - 150", "120 a 150")
    range_pattern = r'([\d.,]+)\s*[-–—a]\s*([\d.,]+)'
    range_match = re.search(range_pattern, text)
    
    if range_match:
        try:
            val1 = _parse_number(range_match.group(1))
            val2 = _parse_number(range_match.group(2))
            if val1 is not None and val2 is not None:
                # Return average of range
                return (val1 + val2) / 2, True
        except:
            pass
    
    # Find all number patterns in the text
    # Pattern matches: 1,234.56 or 1.234,56 or 1234.56 or 1234
    number_pattern = r'[\d]+(?:[.,]\d{3})*(?:[.,]\d+)?'
    matches = re.findall(number_pattern, text)
    
    if matches:
        # Take the first valid number found
        for match in matches:
            value = _parse_number(match)
            if value is not None and value > 0:
                return value, False
    
    return None, False


def _parse_number(text: str) -> Optional[float]:
    """
    Parse a number string handling different decimal/thousands separators.
    
    Args:
        text: Number string (e.g., "1,200", "1.200,5", "1200.5")
        
    Returns:
        Parsed float or None
    """
    if not text:
        return None
    
    text = text.strip()
    
    # Count dots and commas
    dots = text.count('.')
    commas = text.count(',')
    
    try:
        if dots == 0 and commas == 0:
            # Simple integer: "1200"
            return float(text)
        
        elif dots == 1 and commas == 0:
            # Could be decimal (1200.5) or thousands (1.200)
            parts = text.split('.')
            if len(parts[1]) == 3 and len(parts[0]) <= 3:
                # Likely thousands separator: "1.200" -> 1200
                return float(text.replace('.', ''))
            else:
                # Decimal: "1200.5"
                return float(text)
        
        elif commas == 1 and dots == 0:
            # Could be decimal (1200,5) or thousands (1,200)
            parts = text.split(',')
            if len(parts[1]) == 3 and len(parts[0]) <= 3:
                # Likely thousands separator: "1,200" -> 1200
                return float(text.replace(',', ''))
            else:
                # Decimal: "1200,5"
                return float(text.replace(',', '.'))
        
        elif dots >= 1 and commas == 1:
            # Format: 1.234,56 (European style)
            return float(text.replace('.', '').replace(',', '.'))
        
        elif commas >= 1 and dots == 1:
            # Format: 1,234.56 (US style)
            return float(text.replace(',', ''))
        
        elif dots > 1:
            # Multiple dots: 1.234.567 -> thousands separators
            return float(text.replace('.', ''))
        
        elif commas > 1:
            # Multiple commas: 1,234,567 -> thousands separators
            return float(text.replace(',', ''))
        
        else:
            return float(text.replace(',', '.'))
            
    except (ValueError, TypeError):
        return None


def normalize_area(text: str) -> Dict[str, Any]:
    """
    Normalize area text to square meters (m²).
    
    Args:
        text: Raw area text (e.g., "120 v2", "1,200 sqft", "85 m2")
        
    Returns:
        Dict with:
        - original: Original input text
        - value_m2: Normalized value in m² (float or None)
        - unit_detected: Detected unit ('m2', 'vara2', 'ft2', or None)
        - parse_success: Whether parsing was successful
        - is_range: Whether the original was a range
        - error: Error message if parse_success is False
    """
    result = {
        'original': text,
        'value_m2': None,
        'unit_detected': None,
        'parse_success': False,
        'is_range': False,
        'error': None
    }
    
    if not text or not text.strip():
        result['error'] = 'Empty input'
        return result
    
    # Detect unit
    unit = detect_unit(text)
    result['unit_detected'] = unit
    
    if unit is None:
        result['error'] = f'Could not detect unit in: {text}'
        return result
    
    # Parse numeric value
    value, is_range = parse_area_value(text)
    result['is_range'] = is_range
    
    if value is None:
        result['error'] = f'Could not parse numeric value from: {text}'
        return result
    
    # Convert to m²
    if unit == 'm2':
        result['value_m2'] = round(value, 2)
    elif unit == 'vara2':
        result['value_m2'] = round(value * VARA2_TO_M2, 2)
    elif unit == 'ft2':
        result['value_m2'] = round(value * FT2_TO_M2, 2)
    
    result['parse_success'] = True
    return result


def normalize_specs_area(specs: Dict[str, Any]) -> Dict[str, Any]:
    """
    LEGACY: Use normalize_listing_specs instead.
    Normalize all area fields in a specs dictionary.
    """
    if not specs:
        return specs
    
    # Keywords that indicate area fields
    area_keywords = [
        'área', 'area', 'terreno', 'construcción', 'construida',
        'tamaño', 'superficie', 'lote', 'm2', 'mt2', 'metros'
    ]
    
    best_area_m2 = None
    area_source = None
    
    for key, value in specs.items():
        if not value:
            continue
            
        key_lower = key.lower()
        
        # Check if this key is area-related
        is_area_key = any(kw in key_lower for kw in area_keywords)
        
        if is_area_key:
            result = normalize_area(str(value))
            
            if result['parse_success'] and result['value_m2']:
                # Prefer 'construcción' or 'construida' over 'terreno'
                is_construction = 'construc' in key_lower or 'constru' in key_lower
                
                if best_area_m2 is None:
                    best_area_m2 = result['value_m2']
                    area_source = key
                elif is_construction:
                    best_area_m2 = result['value_m2']
                    area_source = key
    
    # Add normalized area to specs
    if best_area_m2 is not None:
        specs['area_m2'] = best_area_m2
        specs['area_m2_source'] = area_source
    
    return specs


def extract_number(text: str) -> Optional[str]:
    """Extract the first integer or float from text."""
    if not text:
        return None
    # Find numbers like 1, 2.5, 3
    match = re.search(r'(\d+(?:\.\d+)?)', str(text))
    if match:
        return match.group(1)
    return None


def normalize_listing_specs(specs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize all listing specs (bedrooms, bathrooms, parking, area).
    
    Args:
        specs: Raw specs dictionary
        
    Returns:
        Standardized specs dictionary containing ONLY:
        - bedrooms (str): Number of bedrooms
        - bathrooms (str): Number of bathrooms
        - parking (str): Number of parking spots
        - area_m2 (str): Area in square meters (converted if needed)
    """
    if not specs:
        return {}
    
    normalized = {}
    
    # 1. Normalize Area (m2)
    # ----------------------
    # Reuse logic from normalize_specs_area but cleaned up
    area_keywords = [
        'área', 'area', 'terreno', 'construcción', 'construida',
        'tamaño', 'superficie', 'lote', 'm2', 'mt2', 'metros'
    ]
    
    best_area_m2 = None
    area_source = None
    
    # Check explicitly named 'area' or 'area_m2' first if they exist
    potential_area_keys = ['area_m2', 'area', 'm2']
    for k in specs:
        if k.lower() in potential_area_keys and specs[k]:
             # If it already looks like a number, just trust it but verify unit if present
             val_str = str(specs[k])
             result = normalize_area(val_str)
             if result['parse_success']:
                 best_area_m2 = result['value_m2']
                 area_source = k
                 break
             else:
                 # If parse failed (e.g. just a number without unit), assume m2 if likely
                 val_num = _parse_number(val_str)
                 if val_num:
                     best_area_m2 = val_num
                     area_source = k
                     break

    # If simple check failed, scan all fields
    if best_area_m2 is None:
        for key, value in specs.items():
            if not value:
                continue
            key_lower = key.lower()
            if any(kw in key_lower for kw in area_keywords):
                val_str = str(value)
                result = normalize_area(val_str)
                if result['parse_success'] and result['value_m2']:
                    # Prefer construction area over land area for "housing" stats
                    is_construction = 'construc' in key_lower or 'constru' in key_lower
                    if best_area_m2 is None or is_construction:
                        best_area_m2 = result['value_m2']
                        area_source = key
                else:
                    # If value has no unit, check if the KEY indicates the unit
                    # e.g., "Área construida (m²)": "1" - the key tells us it's m²
                    val_num = _parse_number(val_str)
                    if val_num is not None:
                        # Check if key indicates the unit
                        key_has_m2 = bool(re.search(r'm[²2]|metros?', key_lower))
                        key_has_v2 = bool(re.search(r'v[²2]|varas?', key_lower))
                        key_has_ft2 = bool(re.search(r'ft[²2]|pies?|sqft', key_lower))
                        
                        if key_has_m2:
                            area_val = val_num  # Already in m²
                        elif key_has_v2:
                            area_val = val_num * VARA2_TO_M2
                        elif key_has_ft2:
                            area_val = val_num * FT2_TO_M2
                        else:
                            # No unit in key, assume m² if it's an area keyword
                            area_val = val_num
                        
                        is_construction = 'construc' in key_lower or 'constru' in key_lower
                        if best_area_m2 is None or is_construction:
                            best_area_m2 = round(area_val, 2)
                            area_source = key

    
    if best_area_m2 is not None:
        normalized['area_m2'] = str(best_area_m2)
        # Optional: include source if debugging is needed, but user seems to want clean output
        # normalized['area_m2_source'] = area_source

    # 2. Normalize Bedrooms
    # ---------------------
    bedroom_keys = ['bedrooms', 'habitaciones', 'recamaras', 'dormitorios', 'hab']
    found_beds = None
    for k in specs:
        if any(bk in k.lower() for bk in bedroom_keys):
            val = extract_number(str(specs[k]))
            if val:
                found_beds = val
                break
    
    if found_beds:
        normalized['bedrooms'] = found_beds
    
    # 3. Normalize Bathrooms
    # ----------------------
    bathroom_keys = ['bathrooms', 'baños', 'banos', 'baths']
    found_baths = None
    for k in specs:
        if any(bk in k.lower() for bk in bathroom_keys):
            val = extract_number(str(specs[k]))
            if val:
                found_baths = val
                break
                
    if found_baths:
        normalized['bathrooms'] = found_baths
        
    # 4. Normalize Parking
    # --------------------
    parking_keys = ['parking', 'estacionamientos', 'cocheras', 'garaje', 'parqueo']
    found_parking = None
    for k in specs:
        if any(pk in k.lower() for pk in parking_keys):
             val = extract_number(str(specs[k]))
             if val:
                 found_parking = val
                 break
    
    if found_parking:
        normalized['parking'] = found_parking

    return normalized


# ============== CONVENIENCE FUNCTIONS ==============

def convert_vara2_to_m2(value: float) -> float:
    """Convert varas cuadradas to metros cuadrados."""
    return round(value * VARA2_TO_M2, 2)


def convert_ft2_to_m2(value: float) -> float:
    """Convert square feet to metros cuadrados."""
    return round(value * FT2_TO_M2, 2)


if __name__ == "__main__":
    # Quick test
    test_cases = [
        "120 m2",
        "100 v2",
        "500 sqft",
        "1,200 varas2",
        "85.5 metros cuadrados",
        "Área: 200 m2 aprox",
        "100-150 m2",
        "33,711 v2 lote",
    ]
    
    print("Area Normalizer Test")
    print("=" * 60)
    
    for test in test_cases:
        result = normalize_area(test)
        status = "✓" if result['parse_success'] else "✗"
        print(f"{status} '{test}'")
        print(f"   → {result['value_m2']} m² (unit: {result['unit_detected']})")
        if result['error']:
            print(f"   Error: {result['error']}")
        print()
    
    print("\nSpecs Normalization Test")
    print("=" * 60)
    sample_specs = {
        "habitaciones": "3 habitaciones",
        "baños": "2.5 baños",
        "estacionamientos": "2 vehiculos",
        "Área de terreno": "500 v2"
    }
    norm = normalize_listing_specs(sample_specs)
    print(f"Input: {sample_specs}")
    print(f"Output: {norm}")
