#!/usr/bin/env python3
"""
Deduplication Module for Real Estate Data Extraction Pipeline
==============================================================
Provides robust duplicate detection, stable deduplication keys, incremental
extraction safety, checkpointing, and data normalization for El Salvador
real estate listings.

Key Features:
  - Deterministic deduplication keys using hashing
  - Coordinate-based proximity matching (configurable tolerance)
  - Text similarity matching for titles/descriptions
  - Incremental extraction with persistent cache
  - Checkpoint-based progress saving (every N records)
  - Memory-efficient processing for large datasets

Usage:
  from deduplication import DeduplicationManager
  
  dedup = DeduplicationManager(cache_dir=".dedup_cache")
  
  # During extraction
  for listing in listings:
      if dedup.is_duplicate(listing):
          continue  # Skip duplicate
      
      # Process listing
      dedup.mark_processed(listing)
      
      # Checkpoint every N records
      if dedup.should_checkpoint():
          dedup.save_checkpoint()

Author: ChivoCasa Team
Version: 1.0.0
"""

import hashlib
import json
import os
import re
import unicodedata
import pickle
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from functools import lru_cache


# ============== CONFIGURATION ==============

# Coordinate tolerance for proximity matching (in degrees)
# ~0.0001 degrees ≈ ~11 meters at equator
COORDINATE_TOLERANCE = 0.0005  # ~55 meters

# Coordinate rounding precision for dedup key (4 decimal places = ~11m precision)
COORDINATE_PRECISION = 4

# Minimum text similarity score to consider as duplicate (0.0 - 1.0)
TEXT_SIMILARITY_THRESHOLD = 0.85

# Checkpoint interval (save progress every N records)
CHECKPOINT_INTERVAL = 15

# Maximum cache size for seen records (to limit memory usage)
MAX_CACHE_SIZE = 100000


# ============== TEXT NORMALIZATION ==============

def normalize_text(text: Optional[str]) -> str:
    """
    Normalize text for comparison: lowercase, remove accents, trim whitespace,
    remove special characters, and collapse multiple spaces.
    
    Args:
        text: Input text string
        
    Returns:
        Normalized text string
    """
    if not text:
        return ""
    
    # Convert to string if needed
    text = str(text)
    
    # Lowercase
    text = text.lower()
    
    # Remove accents/diacritics using Unicode normalization
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    
    # Remove special characters, keeping only alphanumeric and spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Collapse multiple spaces and trim
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text


def normalize_address(address: Optional[str]) -> str:
    """
    Normalize address for comparison with special handling for
    common El Salvador address patterns.
    
    Args:
        address: Address string
        
    Returns:
        Normalized address string
    """
    if not address:
        return ""
    
    # Base normalization
    addr = normalize_text(address)
    
    # Standardize common abbreviations in Spanish addresses
    replacements = {
        r'\bcol\b': 'colonia',
        r'\bres\b': 'residencial',
        r'\burb\b': 'urbanizacion',
        r'\bav\b': 'avenida',
        r'\bclle\b': 'calle',
        r'\bcl\b': 'calle',
        r'\bpje\b': 'pasaje',
        r'\bblvd\b': 'bulevar',
        r'\bno\b': 'numero',
        r'\bss\b': 'san salvador',
        r'\bdepto\b': 'departamento',
        r'\bn\b': 'norte',
        r'\bs\b': 'sur',
        r'\be\b': 'este',
        r'\bo\b': 'oeste',
    }
    
    for pattern, replacement in replacements.items():
        addr = re.sub(pattern, replacement, addr)
    
    # Remove "numero" followed by digits (house numbers vary even for same property)
    addr = re.sub(r'numero\s*\d+', '', addr)
    
    return addr.strip()


def normalize_coordinate(coord: Optional[float], precision: int = COORDINATE_PRECISION) -> float:
    """
    Normalize coordinate to fixed precision for comparison.
    
    Args:
        coord: Latitude or longitude value
        precision: Number of decimal places
        
    Returns:
        Rounded coordinate value
    """
    if coord is None:
        return 0.0
    
    try:
        return round(float(coord), precision)
    except (ValueError, TypeError):
        return 0.0


def normalize_price(price: Any) -> float:
    """
    Normalize price to float for comparison.
    
    Args:
        price: Price value (string or number)
        
    Returns:
        Normalized price as float
    """
    if price is None:
        return 0.0
    
    if isinstance(price, (int, float)):
        return float(price)
    
    # Parse price string
    price_str = str(price)
    
    # Remove currency symbols and text
    price_str = re.sub(r'[^\d.,]', '', price_str)
    
    if not price_str:
        return 0.0
    
    # Handle comma: could be decimal separator (European) or thousands separator (US)
    if ',' in price_str and '.' not in price_str:
        # Check if comma is followed by exactly 3 digits (thousands separator)
        # or 1-2 digits (decimal separator)
        comma_idx = price_str.rfind(',')
        after_comma = price_str[comma_idx + 1:]
        
        if len(after_comma) == 3 and after_comma.isdigit():
            # Likely thousands separator (e.g., 250,000) - remove it
            price_str = price_str.replace(',', '')
        else:
            # Likely decimal separator (e.g., 250000,50) - replace with dot
            price_str = price_str.replace(',', '.')
    elif ',' in price_str and '.' in price_str:
        # Both exist - comma is thousands separator, dot is decimal
        price_str = price_str.replace(',', '')
    
    try:
        return float(price_str)
    except (ValueError, TypeError):
        return 0.0


# ============== SIMILARITY FUNCTIONS ==============

@lru_cache(maxsize=10000)
def get_text_tokens(text: str) -> frozenset:
    """
    Convert text to a set of tokens for similarity comparison.
    Uses frozenset for caching.
    
    Args:
        text: Normalized text string
        
    Returns:
        Frozen set of tokens
    """
    if not text:
        return frozenset()
    
    # Split into words and filter short words
    tokens = [w for w in text.split() if len(w) >= 2]
    return frozenset(tokens)


def jaccard_similarity(set1: frozenset, set2: frozenset) -> float:
    """
    Calculate Jaccard similarity between two sets.
    
    Args:
        set1: First set of tokens
        set2: Second set of tokens
        
    Returns:
        Similarity score (0.0 - 1.0)
    """
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def text_similarity(text1: str, text2: str) -> float:
    """
    Calculate text similarity between two strings using Jaccard similarity
    on normalized tokens.
    
    Args:
        text1: First text string
        text2: Second text string
        
    Returns:
        Similarity score (0.0 - 1.0)
    """
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    
    tokens1 = get_text_tokens(norm1)
    tokens2 = get_text_tokens(norm2)
    
    return jaccard_similarity(tokens1, tokens2)


def coordinates_match(lat1: float, lon1: float, lat2: float, lon2: float, 
                      tolerance: float = COORDINATE_TOLERANCE) -> bool:
    """
    Check if two coordinate pairs are within tolerance of each other.
    
    Args:
        lat1, lon1: First coordinate pair
        lat2, lon2: Second coordinate pair
        tolerance: Maximum difference in degrees
        
    Returns:
        True if coordinates match within tolerance
    """
    if lat1 == 0 or lon1 == 0 or lat2 == 0 or lon2 == 0:
        return False  # Don't match on missing coordinates
    
    return (abs(lat1 - lat2) <= tolerance and 
            abs(lon1 - lon2) <= tolerance)


# ============== DEDUPLICATION KEY GENERATION ==============

def generate_dedup_key(listing: Dict) -> str:
    """
    Generate a deterministic deduplication key for a listing.
    Uses a combination of:
      - Rounded coordinates
      - Normalized title
      - Normalized address/location
      
    The key is hashed for efficient storage and comparison.
    
    Args:
        listing: Listing dictionary with title, location, lat/lon, etc.
        
    Returns:
        SHA-256 hash string as dedup key
    """
    # Extract and normalize components
    title = normalize_text(listing.get('title', ''))
    
    # Handle location which can be string or dict
    location = listing.get('location', '')
    if isinstance(location, dict):
        location = location.get('location_original', '') or location.get('address', '')
    location = normalize_address(location)
    
    # Get coordinates (handle various field names)
    lat = listing.get('latitude') or listing.get('lat') or 0
    lon = listing.get('longitude') or listing.get('lon') or listing.get('lng') or 0
    
    # Normalize coordinates
    lat_norm = normalize_coordinate(lat)
    lon_norm = normalize_coordinate(lon)
    
    # Build key components
    key_components = [
        f"lat:{lat_norm}",
        f"lon:{lon_norm}",
        f"title:{title[:100]}",  # Limit title length
        f"loc:{location[:100]}"   # Limit location length
    ]
    
    # Create deterministic string and hash it
    key_string = "|".join(key_components)
    return hashlib.sha256(key_string.encode('utf-8')).hexdigest()


def generate_url_key(url: Optional[str]) -> Optional[str]:
    """
    Generate a key from the listing URL, normalizing it for comparison.
    
    Args:
        url: Listing URL
        
    Returns:
        SHA-256 hash of normalized URL, or None if no URL
    """
    if not url:
        return None
    
    # Normalize URL
    url = str(url).lower().strip()
    
    # Remove protocol
    url = re.sub(r'^https?://', '', url)
    
    # Remove trailing slashes
    url = url.rstrip('/')
    
    # Remove common tracking parameters
    url = re.sub(r'\?.*$', '', url)
    
    return hashlib.sha256(url.encode('utf-8')).hexdigest()


def generate_external_id_key(external_id: Optional[str], source: Optional[str]) -> Optional[str]:
    """
    Generate a key from external ID and source combination.
    
    Args:
        external_id: External listing ID
        source: Source name (e.g., "Encuentra24", "MiCasaSV")
        
    Returns:
        Combined key string, or None if no external_id
    """
    if not external_id:
        return None
    
    source = normalize_text(source) if source else "unknown"
    return f"{source}:{external_id}"


# ============== DEDUPLICATION MANAGER ==============

@dataclass
class ProcessedRecord:
    """Represents a processed record for tracking."""
    dedup_key: str
    external_id: Optional[str] = None
    url_key: Optional[str] = None
    title_tokens: frozenset = field(default_factory=frozenset)
    lat: float = 0.0
    lon: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class DeduplicationManager:
    """
    Manages deduplication state, checkpointing, and incremental extraction.
    
    Provides:
      - Fast O(1) duplicate detection using hashes
      - Secondary similarity matching for near-duplicates
      - Persistent cache for incremental runs
      - Automatic checkpointing every N records
    """
    
    def __init__(self, 
                 cache_dir: str = ".dedup_cache",
                 checkpoint_interval: int = CHECKPOINT_INTERVAL,
                 enable_similarity_check: bool = True,
                 similarity_threshold: float = TEXT_SIMILARITY_THRESHOLD,
                 coordinate_tolerance: float = COORDINATE_TOLERANCE):
        """
        Initialize the deduplication manager.
        
        Args:
            cache_dir: Directory for persistent cache/checkpoint files
            checkpoint_interval: Save checkpoint every N records
            enable_similarity_check: Enable fuzzy text similarity matching
            similarity_threshold: Minimum similarity score for duplicates
            coordinate_tolerance: Tolerance for coordinate matching
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.checkpoint_interval = checkpoint_interval
        self.enable_similarity_check = enable_similarity_check
        self.similarity_threshold = similarity_threshold
        self.coordinate_tolerance = coordinate_tolerance
        
        # ID-based lookup sets (O(1) lookup)
        self.seen_dedup_keys: Set[str] = set()
        self.seen_url_keys: Set[str] = set()
        self.seen_external_ids: Set[str] = set()
        
        # For similarity matching (stores ProcessedRecord objects)
        self.processed_records: List[ProcessedRecord] = []
        
        # Counters for checkpointing
        self.records_since_checkpoint = 0
        self.total_processed = 0
        self.duplicates_found = 0
        
        # Load existing cache if available
        self._load_cache()
    
    def _get_cache_file(self, name: str) -> Path:
        """Get path to a cache file."""
        return self.cache_dir / f"{name}.pkl"
    
    def _load_cache(self):
        """Load existing cache from disk if available."""
        try:
            # Load dedup keys
            keys_file = self._get_cache_file("dedup_keys")
            if keys_file.exists():
                with open(keys_file, 'rb') as f:
                    self.seen_dedup_keys = pickle.load(f)
                print(f"  Loaded {len(self.seen_dedup_keys)} dedup keys from cache")
            
            # Load URL keys
            urls_file = self._get_cache_file("url_keys")
            if urls_file.exists():
                with open(urls_file, 'rb') as f:
                    self.seen_url_keys = pickle.load(f)
                print(f"  Loaded {len(self.seen_url_keys)} URL keys from cache")
            
            # Load external IDs
            ids_file = self._get_cache_file("external_ids")
            if ids_file.exists():
                with open(ids_file, 'rb') as f:
                    self.seen_external_ids = pickle.load(f)
                print(f"  Loaded {len(self.seen_external_ids)} external IDs from cache")
            
            # Load processed records for similarity matching
            records_file = self._get_cache_file("processed_records")
            if records_file.exists() and self.enable_similarity_check:
                with open(records_file, 'rb') as f:
                    self.processed_records = pickle.load(f)
                print(f"  Loaded {len(self.processed_records)} records for similarity matching")
                
        except Exception as e:
            print(f"  Warning: Could not load cache: {e}")
    
    def save_checkpoint(self):
        """Save current state to disk."""
        try:
            # Save dedup keys
            with open(self._get_cache_file("dedup_keys"), 'wb') as f:
                pickle.dump(self.seen_dedup_keys, f)
            
            # Save URL keys
            with open(self._get_cache_file("url_keys"), 'wb') as f:
                pickle.dump(self.seen_url_keys, f)
            
            # Save external IDs
            with open(self._get_cache_file("external_ids"), 'wb') as f:
                pickle.dump(self.seen_external_ids, f)
            
            # Save processed records (for similarity matching)
            if self.enable_similarity_check:
                # Limit cache size to avoid memory issues
                if len(self.processed_records) > MAX_CACHE_SIZE:
                    # Keep most recent records
                    self.processed_records = self.processed_records[-MAX_CACHE_SIZE:]
                
                with open(self._get_cache_file("processed_records"), 'wb') as f:
                    pickle.dump(self.processed_records, f)
            
            # Save metadata
            metadata = {
                "total_processed": self.total_processed,
                "duplicates_found": self.duplicates_found,
                "last_checkpoint": datetime.now().isoformat(),
                "cache_sizes": {
                    "dedup_keys": len(self.seen_dedup_keys),
                    "url_keys": len(self.seen_url_keys),
                    "external_ids": len(self.seen_external_ids),
                    "processed_records": len(self.processed_records)
                }
            }
            with open(self._get_cache_file("metadata"), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.records_since_checkpoint = 0
            print(f"  💾 Checkpoint saved ({self.total_processed} total, {self.duplicates_found} duplicates)")
            
        except Exception as e:
            print(f"  Warning: Could not save checkpoint: {e}")
    
    def should_checkpoint(self) -> bool:
        """Check if it's time to save a checkpoint."""
        return self.records_since_checkpoint >= self.checkpoint_interval
    
    def is_duplicate(self, listing: Dict) -> Tuple[bool, str]:
        """
        Check if a listing is a duplicate of a previously seen record.
        
        Uses multiple strategies in order of efficiency:
          1. External ID + Source match (fastest)
          2. URL match
          3. Dedup key match (coordinate + title + location hash)
          4. Text similarity + coordinate proximity (slowest, optional)
        
        Args:
            listing: Listing dictionary to check
            
        Returns:
            Tuple of (is_duplicate: bool, reason: str)
        """
        # 1. Check external ID + source (fastest)
        external_id = listing.get('external_id')
        source = listing.get('source')
        if external_id and source:
            ext_key = generate_external_id_key(external_id, source)
            if ext_key in self.seen_external_ids:
                return True, f"Duplicate external_id: {external_id} from {source}"
        
        # 2. Check URL
        url = listing.get('url')
        if url:
            url_key = generate_url_key(url)
            if url_key and url_key in self.seen_url_keys:
                return True, f"Duplicate URL: {url[:60]}..."
        
        # 3. Check dedup key (hash of coordinates + title + location)
        dedup_key = generate_dedup_key(listing)
        if dedup_key in self.seen_dedup_keys:
            return True, "Duplicate dedup key (coordinates + title + location)"
        
        # 4. Similarity matching (optional, slower)
        if self.enable_similarity_check and self.processed_records:
            # Get listing components for comparison
            title = normalize_text(listing.get('title', ''))
            title_tokens = get_text_tokens(title)
            
            lat = normalize_coordinate(listing.get('latitude') or listing.get('lat') or 0)
            lon = normalize_coordinate(listing.get('longitude') or listing.get('lon') or 0)
            
            # Only check recent records (last 1000) for performance
            recent_records = self.processed_records[-1000:]
            
            for record in recent_records:
                # Check coordinate proximity first (fast)
                if coordinates_match(lat, lon, record.lat, record.lon, 
                                   self.coordinate_tolerance):
                    # Check title similarity
                    similarity = jaccard_similarity(title_tokens, record.title_tokens)
                    if similarity >= self.similarity_threshold:
                        return True, f"Similar listing (similarity: {similarity:.2%})"
        
        return False, "Unique"
    
    def mark_processed(self, listing: Dict):
        """
        Mark a listing as processed and add to tracking sets.
        
        Args:
            listing: Listing dictionary that was successfully processed
        """
        # Add external ID
        external_id = listing.get('external_id')
        source = listing.get('source')
        if external_id and source:
            ext_key = generate_external_id_key(external_id, source)
            if ext_key:
                self.seen_external_ids.add(ext_key)
        
        # Add URL key
        url = listing.get('url')
        if url:
            url_key = generate_url_key(url)
            if url_key:
                self.seen_url_keys.add(url_key)
        
        # Add dedup key
        dedup_key = generate_dedup_key(listing)
        self.seen_dedup_keys.add(dedup_key)
        
        # Add to processed records for similarity matching
        if self.enable_similarity_check:
            title = normalize_text(listing.get('title', ''))
            title_tokens = get_text_tokens(title)
            lat = normalize_coordinate(listing.get('latitude') or listing.get('lat') or 0)
            lon = normalize_coordinate(listing.get('longitude') or listing.get('lon') or 0)
            
            record = ProcessedRecord(
                dedup_key=dedup_key,
                external_id=external_id,
                url_key=generate_url_key(url),
                title_tokens=title_tokens,
                lat=lat,
                lon=lon
            )
            self.processed_records.append(record)
        
        # Update counters
        self.records_since_checkpoint += 1
        self.total_processed += 1
    
    def mark_duplicate_found(self):
        """Increment the duplicate counter."""
        self.duplicates_found += 1
    
    def get_stats(self) -> Dict:
        """Get current deduplication statistics."""
        return {
            "total_processed": self.total_processed,
            "duplicates_found": self.duplicates_found,
            "unique_rate": 1 - (self.duplicates_found / self.total_processed) if self.total_processed > 0 else 1,
            "cache_sizes": {
                "dedup_keys": len(self.seen_dedup_keys),
                "url_keys": len(self.seen_url_keys),
                "external_ids": len(self.seen_external_ids),
                "processed_records": len(self.processed_records)
            }
        }
    
    def clear_cache(self):
        """Clear all cached data (start fresh)."""
        self.seen_dedup_keys.clear()
        self.seen_url_keys.clear()
        self.seen_external_ids.clear()
        self.processed_records.clear()
        self.total_processed = 0
        self.duplicates_found = 0
        self.records_since_checkpoint = 0
        
        # Remove cache files
        for file in self.cache_dir.glob("*.pkl"):
            file.unlink()
        
        metadata_file = self._get_cache_file("metadata").with_suffix('.json')
        if metadata_file.exists():
            metadata_file.unlink()
        
        print("  Cache cleared")


# ============== BATCH PROCESSING UTILITIES ==============

def deduplicate_listings(listings: List[Dict], 
                         dedup_manager: Optional[DeduplicationManager] = None,
                         return_duplicates: bool = False) -> Tuple[List[Dict], List[Dict]]:
    """
    Deduplicate a batch of listings.
    
    Args:
        listings: List of listing dictionaries
        dedup_manager: Optional DeduplicationManager instance (creates new if None)
        return_duplicates: Whether to return duplicate listings
        
    Returns:
        Tuple of (unique_listings, duplicate_listings)
    """
    if dedup_manager is None:
        dedup_manager = DeduplicationManager(
            cache_dir=".dedup_cache_temp",
            enable_similarity_check=True
        )
    
    unique = []
    duplicates = []
    
    for i, listing in enumerate(listings):
        is_dup, reason = dedup_manager.is_duplicate(listing)
        
        if is_dup:
            dedup_manager.mark_duplicate_found()
            if return_duplicates:
                listing['_duplicate_reason'] = reason
                duplicates.append(listing)
            print(f"  Skip duplicate [{i+1}/{len(listings)}]: {reason}")
        else:
            dedup_manager.mark_processed(listing)
            unique.append(listing)
        
        # Auto-checkpoint
        if dedup_manager.should_checkpoint():
            dedup_manager.save_checkpoint()
    
    # Final checkpoint
    dedup_manager.save_checkpoint()
    
    return unique, duplicates


# ============== STANDALONE UTILITY FUNCTIONS ==============

def find_duplicates_in_list(listings: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Find duplicate groups within a single list of listings.
    
    Args:
        listings: List of listing dictionaries
        
    Returns:
        Dictionary mapping dedup_key to list of duplicate listings
    """
    groups: Dict[str, List[Dict]] = {}
    
    for listing in listings:
        key = generate_dedup_key(listing)
        if key not in groups:
            groups[key] = []
        groups[key].append(listing)
    
    # Filter to only groups with duplicates
    return {k: v for k, v in groups.items() if len(v) > 1}


def merge_duplicate_listings(duplicates: List[Dict]) -> Dict:
    """
    Merge multiple duplicate listings into a single canonical record.
    Uses the most complete/recent data from each duplicate.
    
    Args:
        duplicates: List of duplicate listing dictionaries
        
    Returns:
        Merged canonical listing
    """
    if not duplicates:
        return {}
    
    if len(duplicates) == 1:
        return duplicates[0]
    
    # Start with the first listing as base
    merged = duplicates[0].copy()
    
    # Priority fields - newer/longer values preferred
    for dup in duplicates[1:]:
        for key, value in dup.items():
            existing = merged.get(key)
            
            # Skip if value is empty
            if not value:
                continue
            
            # For strings, prefer longer non-empty values
            if isinstance(value, str) and isinstance(existing, str):
                if len(value) > len(existing):
                    merged[key] = value
            
            # For lists (like images), merge and deduplicate
            elif isinstance(value, list):
                if isinstance(existing, list):
                    # Combine and deduplicate
                    combined = list(dict.fromkeys(existing + value))
                    merged[key] = combined
                else:
                    merged[key] = value
            
            # For dicts (like specs, details), merge
            elif isinstance(value, dict):
                if isinstance(existing, dict):
                    merged[key] = {**existing, **value}
                else:
                    merged[key] = value
            
            # For empty existing values, use the new value
            elif not existing:
                merged[key] = value
    
    return merged


# ============== MAIN / TESTING ==============

def main():
    """Test the deduplication module."""
    print("=" * 60)
    print("🔍 Deduplication Module Test")
    print("=" * 60)
    
    # Test text normalization
    print("\n1. Text Normalization Tests:")
    test_texts = [
        "Colonia San Benito, San Salvador",
        "  COLONIA SAN BENITO,   san salvador  ",
        "Colonia Sán Beníto, Sán Sálvádor",
    ]
    for text in test_texts:
        print(f"  '{text}' -> '{normalize_text(text)}'")
    
    # Test coordinate normalization
    print("\n2. Coordinate Normalization Tests:")
    coords = [(13.6969123456, -89.2341987654), (13.6969, -89.2342), (None, -89.234)]
    for lat, lon in coords:
        print(f"  ({lat}, {lon}) -> ({normalize_coordinate(lat)}, {normalize_coordinate(lon)})")
    
    # Test dedup key generation
    print("\n3. Dedup Key Generation Tests:")
    listings = [
        {
            "title": "Casa en Colonia San Benito",
            "location": "San Salvador",
            "latitude": 13.6969,
            "longitude": -89.2341
        },
        {
            "title": "CASA EN COLONIA SAN BENITO",  # Same, different case
            "location": "San Salvador, SS",
            "latitude": 13.6969,
            "longitude": -89.2341
        },
        {
            "title": "Apartamento diferente",  # Different
            "location": "Santa Tecla",
            "latitude": 13.6647,
            "longitude": -89.2767
        }
    ]
    
    keys = []
    for i, listing in enumerate(listings):
        key = generate_dedup_key(listing)
        keys.append(key)
        print(f"  Listing {i+1}: {key[:16]}...")
    
    print(f"\n  Keys 1 and 2 match: {keys[0] == keys[1]}")
    print(f"  Keys 1 and 3 match: {keys[0] == keys[2]}")
    
    # Test similarity matching
    print("\n4. Text Similarity Tests:")
    pairs = [
        ("Casa en venta Colonia San Benito", "Casa en venta Col. San Benito"),
        ("Apartamento moderno 3 habitaciones", "Apartamento moderno con 3 habitaciones"),
        ("Casa completamente diferente", "Apartamento en otra ubicación"),
    ]
    for t1, t2 in pairs:
        sim = text_similarity(t1, t2)
        print(f"  Similarity: {sim:.2%}")
        print(f"    '{t1}'")
        print(f"    '{t2}'")
    
    # Test DeduplicationManager
    print("\n5. DeduplicationManager Tests:")
    dedup = DeduplicationManager(
        cache_dir=".dedup_test_cache",
        checkpoint_interval=3,
        enable_similarity_check=True
    )
    
    test_listings = [
        {
            "external_id": "12345",
            "source": "Encuentra24",
            "title": "Casa en Colonia Escalón",
            "location": "San Salvador",
            "latitude": 13.7028,
            "longitude": -89.2432,
            "url": "https://encuentra24.com/listing/12345"
        },
        {
            "external_id": "12346",
            "source": "Encuentra24",
            "title": "Apartamento en Santa Tecla",
            "location": "La Libertad",
            "latitude": 13.6647,
            "longitude": -89.2767,
            "url": "https://encuentra24.com/listing/12346"
        },
        {
            "external_id": "12345",  # Duplicate!
            "source": "Encuentra24",
            "title": "Casa en Colonia Escalón",
            "location": "San Salvador",
            "latitude": 13.7028,
            "longitude": -89.2432,
            "url": "https://encuentra24.com/listing/12345"
        },
        {
            "external_id": "12347",
            "source": "MiCasaSV",
            "title": "Casa en Colonia Escalon San Salvador",  # Similar!
            "location": "San Salvador",
            "latitude": 13.7029,  # Very close coordinates
            "longitude": -89.2433,
            "url": "https://micasasv.com/listing/12347"
        }
    ]
    
    for i, listing in enumerate(test_listings):
        is_dup, reason = dedup.is_duplicate(listing)
        print(f"  Listing {i+1} ({listing.get('external_id')}): {'DUPLICATE' if is_dup else 'UNIQUE'}")
        if is_dup:
            print(f"    Reason: {reason}")
        else:
            dedup.mark_processed(listing)
    
    # Print stats
    print("\n6. Final Statistics:")
    stats = dedup.get_stats()
    print(f"  Total processed: {stats['total_processed']}")
    print(f"  Duplicates found: {stats['duplicates_found']}")
    print(f"  Unique rate: {stats['unique_rate']:.1%}")
    print(f"  Cache sizes: {stats['cache_sizes']}")
    
    # Clean up test cache
    dedup.clear_cache()
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    main()
