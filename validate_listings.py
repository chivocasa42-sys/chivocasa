#!/usr/bin/env python
"""
Validate Listings CLI
=====================
Command-line tool to validate existing listings and update their status.

Usage:
    python validate_listings.py --source Encuentra24 --limit 50
    python validate_listings.py --all --limit 100
    python validate_listings.py --source MiCasaSV --rate-limit 2.0

This script:
1. Fetches active listings from the database
2. Validates each listing by checking the source URL
3. Updates listings that are no longer active (marks active=false)
"""

import argparse
import sys
from datetime import datetime
from listing_validator import (
    validate_listings_batch,
    update_listing_status,
    get_active_listings,
    ListingStatus
)


def progress_callback(current: int, total: int, result: dict):
    """Print progress during validation."""
    status = result.get('status', 'unknown')
    external_id = result.get('external_id', 'N/A')
    
    # Status indicator
    if status == ListingStatus.ACTIVE.value:
        indicator = "✓"
    elif status in (ListingStatus.DELETED.value, ListingStatus.NOT_FOUND.value, 
                    ListingStatus.SOLD.value, ListingStatus.RENTED.value):
        indicator = "✗"
    elif status == ListingStatus.ERROR.value:
        indicator = "⚠"
    else:
        indicator = "?"
    
    print(f"[{current}/{total}] {indicator} {external_id} - {status}: {result.get('reason', '')[:50]}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate listings and update status in database"
    )
    parser.add_argument(
        "--source",
        choices=["Encuentra24", "MiCasaSV", "Realtor", "VivoLatam"],
        help="Filter by source (validate only this source)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all sources"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of listings to validate (default: 50)"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=1.0,
        help="Seconds between requests (default: 1.0)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't update database, just report findings"
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show summary, not individual results"
    )
    
    args = parser.parse_args()
    
    if not args.source and not args.all:
        print("Error: Must specify --source or --all")
        parser.print_help()
        sys.exit(1)
    
    print("=" * 60)
    print("LISTING VALIDATOR")
    print("=" * 60)
    print(f"Source: {args.source or 'All'}")
    print(f"Limit: {args.limit}")
    print(f"Rate limit: {args.rate_limit}s")
    print(f"Dry run: {args.dry_run}")
    print("=" * 60)
    print()
    
    # Fetch listings
    print("Fetching active listings from database...")
    listings = get_active_listings(source=args.source, limit=args.limit)
    
    if not listings:
        print("No listings found to validate.")
        return
    
    print(f"Found {len(listings)} listings to validate.\n")
    
    # Validate
    print("Starting validation...")
    print("-" * 60)
    
    callback = None if args.quiet else progress_callback
    results = validate_listings_batch(
        listings,
        rate_limit=args.rate_limit,
        on_progress=callback
    )
    
    print("-" * 60)
    
    # Summarize results
    status_counts = {}
    inactive_listings = []
    
    for result in results:
        status = result.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
        
        # Track listings to mark as inactive
        if status in (ListingStatus.DELETED.value, ListingStatus.NOT_FOUND.value,
                      ListingStatus.SOLD.value, ListingStatus.RENTED.value):
            inactive_listings.append(result)
    
    print("\nSUMMARY")
    print("=" * 60)
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    print(f"\n  Total validated: {len(results)}")
    print(f"  To mark inactive: {len(inactive_listings)}")
    
    # Update database
    if inactive_listings and not args.dry_run:
        print("\nUpdating database...")
        print("-" * 60)
        
        updated = 0
        failed = 0
        
        for result in inactive_listings:
            external_id = result.get('external_id')
            reason = result.get('reason', 'Unknown')
            
            if external_id:
                success = update_listing_status(external_id, active=False, reason=reason)
                if success:
                    updated += 1
                else:
                    failed += 1
        
        print("-" * 60)
        print(f"Updated: {updated}")
        print(f"Failed: {failed}")
    
    elif inactive_listings and args.dry_run:
        print("\n[DRY RUN] Would mark these listings as inactive:")
        for result in inactive_listings[:10]:  # Show first 10
            print(f"  - {result.get('external_id')}: {result.get('reason')}")
        if len(inactive_listings) > 10:
            print(f"  ... and {len(inactive_listings) - 10} more")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
