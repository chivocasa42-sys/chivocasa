#!/usr/bin/env python3
"""
Scraper Integration Example: Using Deduplication with the Real Estate Pipeline
===============================================================================
This file demonstrates how to integrate the deduplication module with
the existing scraper_encuentra24.py for robust duplicate-free extraction.

Usage:
  python scraper_with_dedup.py --Encuentra24 --limit 100

Features:
  - Duplicate detection during extraction (not post-processing)
  - Incremental extraction with persistent cache
  - Checkpoint-based progress saving (every 15 records)
  - Handles resume after interruption
"""

import argparse
import json
import time
from datetime import datetime
from typing import List, Dict, Tuple

# Import the deduplication module
from deduplication import (
    DeduplicationManager,
    deduplicate_listings,
    normalize_text,
    normalize_coordinate,
    generate_dedup_key
)


# ============== CONFIGURATION ==============

# Cache directory for deduplication state
DEDUP_CACHE_DIR = ".dedup_cache"

# Checkpoint interval (save progress every N records)
CHECKPOINT_INTERVAL = 15


# ============== INTEGRATION WRAPPER ==============

class DeduplicatedScraper:
    """
    Wrapper that adds deduplication to any scraper.
    
    Usage:
        dedup_scraper = DeduplicatedScraper()
        
        # Option 1: Process listings one at a time
        for listing in scrape_source():
            if dedup_scraper.is_duplicate(listing):
                continue
            
            # Process unique listing
            save_to_database(listing)
            dedup_scraper.mark_processed(listing)
        
        # Option 2: Deduplicate a batch
        unique_listings = dedup_scraper.deduplicate_batch(all_listings)
    """
    
    def __init__(self, 
                 run_id: str = None,
                 enable_similarity_check: bool = True):
        """
        Initialize the deduplicated scraper.
        
        Args:
            run_id: Unique identifier for this extraction run
            enable_similarity_check: Enable fuzzy text matching (slower but catches more dupes)
        """
        self.run_id = run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.start_time = datetime.now()
        
        # Initialize deduplication manager
        self.dedup = DeduplicationManager(
            cache_dir=DEDUP_CACHE_DIR,
            checkpoint_interval=CHECKPOINT_INTERVAL,
            enable_similarity_check=enable_similarity_check
        )
        
        # Statistics
        self.scraped_count = 0
        self.duplicate_count = 0
        self.error_count = 0
        
        print(f"\n{'='*60}")
        print(f"🏠 Deduplicated Scraper - Run ID: {self.run_id}")
        print(f"{'='*60}")
        print(f"  Cache directory: {DEDUP_CACHE_DIR}")
        print(f"  Checkpoint interval: {CHECKPOINT_INTERVAL}")
        print(f"  Similarity check: {'Enabled' if enable_similarity_check else 'Disabled'}")
        print(f"  Loaded {len(self.dedup.seen_dedup_keys)} previously seen records")
    
    def is_duplicate(self, listing: Dict) -> bool:
        """
        Check if a listing is a duplicate.
        
        Args:
            listing: Listing dictionary to check
            
        Returns:
            True if duplicate, False if unique
        """
        is_dup, reason = self.dedup.is_duplicate(listing)
        
        if is_dup:
            self.duplicate_count += 1
            self.dedup.mark_duplicate_found()
        
        return is_dup
    
    def mark_processed(self, listing: Dict):
        """
        Mark a listing as successfully processed.
        
        Args:
            listing: Listing dictionary that was processed
        """
        self.dedup.mark_processed(listing)
        self.scraped_count += 1
        
        # Auto-checkpoint
        if self.dedup.should_checkpoint():
            self.checkpoint()
    
    def checkpoint(self):
        """Save progress checkpoint."""
        self.dedup.save_checkpoint()
    
    def deduplicate_batch(self, listings: List[Dict]) -> List[Dict]:
        """
        Deduplicate a batch of listings.
        
        Args:
            listings: List of listing dictionaries
            
        Returns:
            List of unique listings
        """
        unique = []
        
        for listing in listings:
            if not self.is_duplicate(listing):
                self.mark_processed(listing)
                unique.append(listing)
        
        return unique
    
    def get_dedup_key(self, listing: Dict) -> str:
        """
        Get the deduplication key for a listing.
        
        Args:
            listing: Listing dictionary
            
        Returns:
            Dedup key hash string
        """
        return generate_dedup_key(listing)
    
    def finalize(self):
        """
        Finalize the scraping run: save final checkpoint and print summary.
        """
        self.checkpoint()
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        unique_count = self.scraped_count
        total_processed = self.scraped_count + self.duplicate_count
        
        print(f"\n{'='*60}")
        print(f"📊 Extraction Complete - Run ID: {self.run_id}")
        print(f"{'='*60}")
        print(f"  Total processed: {total_processed}")
        print(f"  Unique records: {unique_count}")
        print(f"  Duplicates skipped: {self.duplicate_count}")
        print(f"  Duplicate rate: {self.duplicate_count / total_processed * 100:.1f}%" if total_processed > 0 else "  Duplicate rate: 0%")
        print(f"  Errors: {self.error_count}")
        print(f"  Elapsed time: {elapsed:.1f}s")
        print(f"  Rate: {total_processed / elapsed:.1f} records/sec" if elapsed > 0 else "")
        print(f"\n  Dedup cache stats:")
        stats = self.dedup.get_stats()
        for key, value in stats['cache_sizes'].items():
            print(f"    - {key}: {value:,}")
        
        return {
            "run_id": self.run_id,
            "total_processed": total_processed,
            "unique_count": unique_count,
            "duplicate_count": self.duplicate_count,
            "error_count": self.error_count,
            "elapsed_seconds": elapsed,
            "cache_stats": stats
        }


# ============== EXAMPLE INTEGRATION WITH SCRAPER ==============

def scrape_with_deduplication_example():
    """
    Example showing how to integrate deduplication with the existing scraper.
    
    This is a template - in actual use, you would import the actual scraper
    functions from scraper_encuentra24.py.
    """
    
    # Simulate scraped listings (in real use, these come from the actual scraper)
    sample_listings = [
        {
            "external_id": "31817095",
            "source": "Encuentra24",
            "title": "Casa en Venta en Colonia Escalón",
            "price": "$250,000",
            "location": "San Salvador",
            "latitude": 13.7028,
            "longitude": -89.2432,
            "url": "https://encuentra24.com/listing/31817095",
            "description": "Hermosa casa de 3 habitaciones...",
            "listing_type": "sale"
        },
        {
            "external_id": "31817096",
            "source": "Encuentra24",
            "title": "Apartamento Moderno Santa Tecla",
            "price": "$150,000",
            "location": "La Libertad",
            "latitude": 13.6647,
            "longitude": -89.2767,
            "url": "https://encuentra24.com/listing/31817096",
            "description": "Apartamento de 2 habitaciones...",
            "listing_type": "sale"
        },
        {
            "external_id": "31817095",  # Duplicate external_id!
            "source": "Encuentra24",
            "title": "Casa en Venta Colonia Escalon",  # Slightly different title
            "price": "$250,000",
            "location": "San Salvador",
            "latitude": 13.7028,
            "longitude": -89.2432,
            "url": "https://encuentra24.com/listing/31817095",
            "description": "Hermosa casa de 3 habitaciones...",
            "listing_type": "sale"
        },
        {
            "external_id": "99999",
            "source": "MiCasaSV",  # Different source
            "title": "Casa en Venta en Colonia Escalón",  # Same property, different source?
            "price": "$250,000",
            "location": "San Salvador",
            "latitude": 13.7028,  # Same coordinates
            "longitude": -89.2432,
            "url": "https://micasasv.com/listing/99999",
            "description": "Casa de 3 habitaciones en excelente ubicación",
            "listing_type": "sale"
        },
        {
            "external_id": "31817097",
            "source": "Encuentra24",
            "title": "Terreno en Santa Ana",
            "price": "$75,000",
            "location": "Santa Ana",
            "latitude": 13.9944,
            "longitude": -89.5589,
            "url": "https://encuentra24.com/listing/31817097",
            "description": "Terreno de 500v2...",
            "listing_type": "sale"
        },
    ]
    
    print("\n" + "="*60)
    print("🧪 DEDUPLICATION INTEGRATION EXAMPLE")
    print("="*60)
    
    # Initialize deduplicated scraper
    dedup_scraper = DeduplicatedScraper(
        run_id="example_run",
        enable_similarity_check=True
    )
    
    # Process each listing
    unique_listings = []
    
    print("\n📋 Processing listings:")
    for i, listing in enumerate(sample_listings):
        print(f"\n  [{i+1}/{len(sample_listings)}] {listing.get('title', '')[:50]}...")
        
        # Check for duplicates
        if dedup_scraper.is_duplicate(listing):
            print(f"    ⏭️ SKIPPED - Duplicate detected")
            continue
        
        # In real use, this is where you would:
        # 1. Save to database: insert_listing(listing)
        # 2. Or add to batch: batch.append(listing)
        
        unique_listings.append(listing)
        dedup_scraper.mark_processed(listing)
        print(f"    ✅ UNIQUE - Added to results")
    
    # Finalize and get summary
    summary = dedup_scraper.finalize()
    
    print(f"\n📦 Unique listings collected: {len(unique_listings)}")
    for listing in unique_listings:
        print(f"  - {listing.get('title', '')[:60]}")
    
    return unique_listings, summary


# ============== HOW TO MODIFY EXISTING SCRAPER ==============

INTEGRATION_GUIDE = """
================================================================================
📖 INTEGRATION GUIDE: Adding Deduplication to scraper_encuentra24.py
================================================================================

1. IMPORT THE DEDUPLICATION MODULE
   Add at the top of scraper_encuentra24.py:
   
   from deduplication import DeduplicationManager

2. INITIALIZE THE DEDUPLICATION MANAGER
   In the main scraping function (e.g., run_scraper()):
   
   dedup = DeduplicationManager(
       cache_dir=".dedup_cache",
       checkpoint_interval=15,
       enable_similarity_check=True
   )

3. CHECK DUPLICATES DURING EXTRACTION
   When processing each listing from scrape_listing() or similar:
   
   # Inside your listing processing loop:
   for listing in scraped_listings:
       is_dup, reason = dedup.is_duplicate(listing)
       
       if is_dup:
           print(f"  Skip duplicate: {reason}")
           dedup.mark_duplicate_found()
           continue
       
       # Process unique listing
       # ... your existing code ...
       
       # Mark as processed
       dedup.mark_processed(listing)
       
       # Auto-checkpoint
       if dedup.should_checkpoint():
           dedup.save_checkpoint()

4. MODIFY insert_listings_batch()
   Add deduplication before inserting:
   
   def insert_listings_batch_with_dedup(listings, dedup_manager, batch_size=50):
       # Filter duplicates first
       unique_listings = []
       for listing in listings:
           is_dup, reason = dedup_manager.is_duplicate(listing)
           if not is_dup:
               unique_listings.append(listing)
               dedup_manager.mark_processed(listing)
       
       # Insert only unique listings
       if unique_listings:
           success, errors = insert_listings_batch(unique_listings, batch_size)
           return success, errors
       return 0, 0

5. ADD CLEANUP FOR INCREMENTAL RUNS
   The cache persists between runs automatically. To start fresh:
   
   dedup.clear_cache()

6. RESUME AFTER INTERRUPTION
   The checkpoint system handles this automatically. Just restart the scraper
   and previously processed records will be skipped.

================================================================================
"""


# ============== MAIN ==============

def main():
    """Run the example integration."""
    parser = argparse.ArgumentParser(
        description="Deduplication integration example for real estate scraper"
    )
    parser.add_argument(
        "--example", 
        action="store_true",
        help="Run the example integration demo"
    )
    parser.add_argument(
        "--guide",
        action="store_true",
        help="Show integration guide"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the deduplication cache"
    )
    
    args = parser.parse_args()
    
    if args.clear_cache:
        dedup = DeduplicationManager(cache_dir=DEDUP_CACHE_DIR)
        dedup.clear_cache()
        print("✅ Deduplication cache cleared")
        return
    
    if args.guide:
        print(INTEGRATION_GUIDE)
        return
    
    # Default: run the example
    scrape_with_deduplication_example()


if __name__ == "__main__":
    main()
