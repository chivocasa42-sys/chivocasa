#!/usr/bin/env python3
"""
One-time script to check and deactivate expired Encuentra24 listings.
Run this to clean up listings that are marked as "desactivado o expirado" on Encuentra24.

Usage:
    python validate_encuentra24.py
"""

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper_encuentra24 import (
    check_listing_still_active, 
    get_supabase_client,
    deactivate_listings
)

def get_active_encuentra24_listings():
    """Get all active listings from Encuentra24."""
    supabase = get_supabase_client()
    if not supabase:
        print("Error: Could not connect to Supabase")
        return []
    
    # Get all active Encuentra24 listings
    response = supabase.table("scrapped_data").select(
        "external_id, url, source"
    ).eq("source", "Encuentra24").eq("active", True).execute()
    
    return response.data if response.data else []


def validate_encuentra24_listings(max_workers=10, limit=None):
    """
    Check all active Encuentra24 listings and deactivate expired ones.
    
    Args:
        max_workers: Number of concurrent validation requests
        limit: Optional limit on number of listings to check (for testing)
    """
    print("\n" + "="*60)
    print("ENCUENTRA24 DEACTIVATION CHECK")
    print("="*60)
    
    # Get active listings
    listings = get_active_encuentra24_listings()
    if not listings:
        print("No active Encuentra24 listings found.")
        return 0, 0
    
    if limit:
        listings = listings[:limit]
    
    print(f"Found {len(listings)} active Encuentra24 listings to check")
    
    # Validate concurrently
    to_deactivate = []
    validated = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_listing = {
            executor.submit(check_listing_still_active, l['url'], l['source']): l 
            for l in listings
        }
        
        for future in as_completed(future_to_listing):
            listing = future_to_listing[future]
            validated += 1
            
            try:
                is_active, reason = future.result()
                if not is_active:
                    to_deactivate.append({
                        'external_id': listing['external_id'],
                        'url': listing['url'],
                        'reason': reason
                    })
                    print(f"  ✗ INACTIVE: ID {listing['external_id']} - {reason}")
            except Exception as e:
                print(f"  ? ERROR: ID {listing['external_id']} - {e}")
            
            # Progress update every 100 listings
            if validated % 100 == 0:
                print(f"  ... Checked {validated}/{len(listings)} ({len(to_deactivate)} inactive)")
    
    print(f"\nValidation complete: {validated} checked, {len(to_deactivate)} to deactivate")
    
    # Deactivate in database
    if to_deactivate:
        print("\nDeactivating listings...")
        external_ids = [d['external_id'] for d in to_deactivate]
        deactivated = deactivate_listings(external_ids)
        print(f"✓ Deactivated {deactivated} listings in database")
        
        # Print summary
        print("\nDeactivated listings:")
        for item in to_deactivate[:20]:  # Show first 20
            print(f"  - ID {item['external_id']}: {item['reason']}")
        if len(to_deactivate) > 20:
            print(f"  ... and {len(to_deactivate) - 20} more")
        
        return validated, deactivated
    
    return validated, 0


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Validate and deactivate Encuentra24 listings")
    parser.add_argument("--limit", type=int, help="Limit number of listings to check (for testing)")
    parser.add_argument("--workers", type=int, default=10, help="Number of concurrent workers")
    args = parser.parse_args()
    
    validated, deactivated = validate_encuentra24_listings(
        max_workers=args.workers,
        limit=args.limit
    )
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: Checked {validated}, Deactivated {deactivated}")
    print(f"{'='*60}")
