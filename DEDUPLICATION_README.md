# Deduplication System for ChivoCasa Real Estate Data Pipeline

## Overview

This document explains the deduplication system implemented for the El Salvador real estate data extraction pipeline. The system addresses the issues of duplicated property records and inconsistent location data by implementing robust duplicate detection **at the extraction stage**.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTRACTION PIPELINE                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌─────────────┐   ┌──────────────────┐   ┌─────────────────┐      │
│   │  Scraper    │──▶│  Deduplication   │──▶│  Insert to      │      │
│   │  Sources    │   │  Manager         │   │  Supabase       │      │
│   │             │   │  (Real-time)     │   │                 │      │
│   └─────────────┘   └────────┬─────────┘   └─────────────────┘      │
│                              │                                       │
│                     ┌────────▼─────────┐                            │
│                     │   Checkpoint     │                            │
│                     │   System         │                            │
│                     │   (Every 15 rec) │                            │
│                     └────────┬─────────┘                            │
│                              │                                       │
│                     ┌────────▼─────────┐                            │
│                     │  Persistent      │                            │
│                     │  Cache (.pkl)    │                            │
│                     └──────────────────┘                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Files Created

| File | Purpose |
|------|---------|
| `deduplication.py` | Core deduplication module with all logic |
| `scraper_with_dedup.py` | Integration example and usage guide |

---

## Deduplication Logic

### 1. Multi-Layer Duplicate Detection

The system uses **4 detection strategies** in order of efficiency:

```
┌────────────────────────────────────────────────────────────────┐
│                DUPLICATE DETECTION PIPELINE                     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  1. EXTERNAL ID + SOURCE (O(1) - Fastest)                      │
│     Key: "encuentra24:31817095"                                │
│     ├─ Match? → DUPLICATE                                      │
│     └─ No match? → Continue                                    │
│                                                                │
│  2. URL MATCH (O(1))                                           │
│     Hash of normalized URL                                     │
│     ├─ Match? → DUPLICATE                                      │
│     └─ No match? → Continue                                    │
│                                                                │
│  3. DEDUP KEY HASH (O(1))                                      │
│     SHA-256(rounded_coords + norm_title + norm_location)       │
│     ├─ Match? → DUPLICATE                                      │
│     └─ No match? → Continue                                    │
│                                                                │
│  4. SIMILARITY MATCHING (O(n) - Slowest, Optional)             │
│     Jaccard similarity on title tokens + coordinate proximity  │
│     └─ Similarity ≥ 85%? → DUPLICATE                           │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### 2. Stable Deduplication Key

The dedup key is generated deterministically using:

```python
def generate_dedup_key(listing):
    # Components
    lat_norm = round(latitude, 4)      # ~11m precision
    lon_norm = round(longitude, 4)     # ~11m precision
    title_norm = normalize_text(title)[:100]
    location_norm = normalize_address(location)[:100]
    
    # Combine
    key_string = f"lat:{lat_norm}|lon:{lon_norm}|title:{title_norm}|loc:{location_norm}"
    
    # Hash for efficient storage
    return sha256(key_string).hexdigest()
```

**Why this works:**
- **Coordinates** catch the same physical property even with different titles
- **Title + Location** catch the same listing even with slightly different coordinates
- **Hashing** enables O(1) lookup and memory-efficient storage

### 3. Data Normalization

All text and coordinates are normalized before comparison:

#### Text Normalization
```python
"  COLONIA SAN BENITO,   San Salvador  "
    ↓ lowercase
"  colonia san benito,   san salvador  "
    ↓ remove accents (NFD normalization)  
"  colonia san benito,   san salvador  "
    ↓ remove special characters
"  colonia san benito    san salvador  "
    ↓ collapse whitespace + trim
"colonia san benito san salvador"
```

#### Address Normalization
```python
"Col. San Benito, SS"
    ↓ expand abbreviations
"colonia san benito san salvador"
    ↓ remove house numbers
"colonia san benito san salvador"
```

#### Coordinate Normalization
```python
(13.6969123456, -89.2341987654)
    ↓ round to 4 decimal places (~11m precision)
(13.6969, -89.2342)
```

---

## Incremental Extraction & Checkpointing

### Checkpoint System

Progress is saved every **N records** (default: 15):

```
Record 1: Process → Cache in memory
Record 2: Process → Cache in memory
...
Record 15: Process → CHECKPOINT → Save to disk
Record 16: Process → Cache in memory
...
Record 30: Process → CHECKPOINT → Save to disk
```

**Checkpoint files (in `.dedup_cache/`):**
- `dedup_keys.pkl` - Set of seen dedup key hashes
- `url_keys.pkl` - Set of seen URL hashes  
- `external_ids.pkl` - Set of seen external_id:source pairs
- `processed_records.pkl` - List of records for similarity matching
- `metadata.json` - Stats and last checkpoint time

### Resume After Interruption

When the scraper restarts:

1. Load existing cache from disk
2. All previously processed records are in the lookup sets
3. New records are checked against the loaded cache
4. **No re-ingestion of already-processed records**

```python
# On restart
dedup = DeduplicationManager(cache_dir=".dedup_cache")
# Automatically loads:
#   - 50,000 dedup keys from cache
#   - 50,000 URL keys from cache
#   - 50,000 external IDs from cache
# 
# New listings are checked against all loaded records
```

---

## Performance Considerations

### Memory Efficiency

| Structure | Size per Record | 100K Records |
|-----------|-----------------|--------------|
| Dedup key hash (64 chars) | ~70 bytes | ~7 MB |
| URL key hash (64 chars) | ~70 bytes | ~7 MB |
| External ID key | ~30 bytes | ~3 MB |
| ProcessedRecord | ~200 bytes | ~20 MB |
| **Total** | | **~37 MB** |

### Time Complexity

| Operation | Complexity | Notes |
|-----------|------------|-------|
| External ID check | O(1) | Set lookup |
| URL check | O(1) | Set lookup |
| Dedup key check | O(1) | Set lookup |
| Similarity check | O(n) | Limited to last 1000 records |
| Mark processed | O(1) | Set insertion |

### Scaling

The system is designed to handle **tens of thousands** of listings:

- **Hash-based lookups** enable O(1) duplicate detection
- **LRU caching** for text tokenization
- **Configurable similarity window** (last 1000 records)
- **Automatic cache pruning** when MAX_CACHE_SIZE exceeded

---

## Configuration Options

```python
from deduplication import DeduplicationManager

dedup = DeduplicationManager(
    # Directory for persistent cache files
    cache_dir=".dedup_cache",
    
    # Save checkpoint every N records
    checkpoint_interval=15,
    
    # Enable fuzzy text similarity matching
    enable_similarity_check=True,
    
    # Minimum similarity score (0.0 - 1.0)
    similarity_threshold=0.85,
    
    # Coordinate tolerance in degrees (~55m default)
    coordinate_tolerance=0.0005
)
```

---

## Usage Examples

### Basic Usage

```python
from deduplication import DeduplicationManager

# Initialize
dedup = DeduplicationManager()

# During extraction
for listing in scraped_listings:
    is_duplicate, reason = dedup.is_duplicate(listing)
    
    if is_duplicate:
        print(f"Skip: {reason}")
        continue
    
    # Process unique listing
    save_to_database(listing)
    dedup.mark_processed(listing)
    
    # Checkpoint if needed
    if dedup.should_checkpoint():
        dedup.save_checkpoint()

# Final checkpoint
dedup.save_checkpoint()
```

### Batch Processing

```python
from deduplication import deduplicate_listings

# Deduplicate a batch
unique_listings, duplicates = deduplicate_listings(
    listings=all_scraped_listings,
    return_duplicates=True
)

print(f"Unique: {len(unique_listings)}")
print(f"Duplicates: {len(duplicates)}")
```

### Find Duplicates in Existing Data

```python
from deduplication import find_duplicates_in_list, merge_duplicate_listings

# Find duplicate groups
duplicate_groups = find_duplicates_in_list(all_listings)

# Merge each group into single canonical record
for key, dupes in duplicate_groups.items():
    canonical = merge_duplicate_listings(dupes)
    print(f"Merged {len(dupes)} duplicates into 1 record")
```

---

## Assumptions About Data Structure

The deduplication module assumes listings have the following structure:

```python
listing = {
    # Required for best deduplication
    "external_id": "31817095",        # Unique per source
    "source": "Encuentra24",          # Source platform
    "url": "https://...",             # Listing URL
    
    # Used for dedup key generation
    "title": "Casa en Venta...",      # Listing title
    "location": "San Salvador",       # Location string or dict
    
    # Optional: coordinates for proximity matching
    "latitude": 13.6969,              # Or "lat"
    "longitude": -89.2341,            # Or "lon" or "lng"
    
    # Other fields (not used for deduplication)
    "price": "$250,000",
    "description": "...",
    "images": [...],
    ...
}
```

---

## Integration Checklist

- [ ] Import `DeduplicationManager` in scraper_encuentra24.py
- [ ] Initialize manager at scraper start
- [ ] Check `is_duplicate()` for each listing before processing
- [ ] Call `mark_processed()` after successful save
- [ ] Add auto-checkpoint with `should_checkpoint()` and `save_checkpoint()`
- [ ] Call `save_checkpoint()` at the end of the run
- [ ] Test resume behavior after simulated interruption

---

## Troubleshooting

### "Too many duplicates being detected"

- Lower the similarity threshold: `similarity_threshold=0.70`
- Increase coordinate tolerance: `coordinate_tolerance=0.001`
- Disable similarity matching: `enable_similarity_check=False`

### "Duplicates still getting through"

- Ensure `external_id` and `source` are being set correctly
- Check that coordinates are being extracted properly
- Verify title normalization is working (check for special characters)

### "Cache getting too large"

- The system auto-prunes at `MAX_CACHE_SIZE` (100,000)
- Clear cache manually: `dedup.clear_cache()`
- Reduce similarity window (modify `recent_records = self.processed_records[-1000:]`)

### "Checkpoint files corrupted"

- Delete the `.dedup_cache/` directory
- Restart the scraper for a fresh run

---

## Summary

| Goal | Solution |
|------|----------|
| Duplicate detection during extraction | Multi-layer detection (ID, URL, hash, similarity) |
| Stable deduplication key | SHA-256 hash of normalized coords + title + location |
| Incremental extraction | Persistent pickle cache loaded on startup |
| Checkpointing | Auto-save every 15 records |
| Data normalization | Text, address, and coordinate normalization |
| Performance | O(1) hash lookups, memory-efficient sets |
| Scalability | Handles 100K+ listings |
