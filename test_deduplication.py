#!/usr/bin/env python3
"""
Unit Tests for Deduplication Module
====================================
Comprehensive tests for the real estate data deduplication pipeline.

Run tests:
  python -m pytest test_deduplication.py -v
  
  OR
  
  python test_deduplication.py

Coverage report:
  python -m pytest test_deduplication.py --cov=deduplication --cov-report=html
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the module under test
from deduplication import (
    # Text normalization functions
    normalize_text,
    normalize_address,
    normalize_coordinate,
    normalize_price,
    
    # Similarity functions
    get_text_tokens,
    jaccard_similarity,
    text_similarity,
    coordinates_match,
    
    # Key generation functions
    generate_dedup_key,
    generate_url_key,
    generate_external_id_key,
    
    # Main class
    DeduplicationManager,
    ProcessedRecord,
    
    # Batch utilities
    deduplicate_listings,
    find_duplicates_in_list,
    merge_duplicate_listings,
    
    # Constants
    COORDINATE_TOLERANCE,
    COORDINATE_PRECISION,
    TEXT_SIMILARITY_THRESHOLD,
    CHECKPOINT_INTERVAL,
)


class TestTextNormalization(unittest.TestCase):
    """Tests for text normalization functions."""
    
    def test_normalize_text_basic(self):
        """Test basic text normalization."""
        self.assertEqual(normalize_text("Hello World"), "hello world")
        self.assertEqual(normalize_text("  HELLO   WORLD  "), "hello world")
    
    def test_normalize_text_accents(self):
        """Test accent/diacritic removal."""
        self.assertEqual(normalize_text("Colonia Sán Beníto"), "colonia san benito")
        self.assertEqual(normalize_text("José María López"), "jose maria lopez")
        self.assertEqual(normalize_text("Niño Pequeño"), "nino pequeno")
    
    def test_normalize_text_special_chars(self):
        """Test special character removal."""
        self.assertEqual(normalize_text("Casa #123, Col. Centro"), "casa 123 col centro")
        self.assertEqual(normalize_text("Precio: $250,000.00!"), "precio 250 000 00")
    
    def test_normalize_text_empty(self):
        """Test handling of empty/None values."""
        self.assertEqual(normalize_text(""), "")
        self.assertEqual(normalize_text(None), "")
        self.assertEqual(normalize_text("   "), "")
    
    def test_normalize_text_unicode(self):
        """Test Unicode normalization."""
        # Different Unicode representations of the same character
        self.assertEqual(
            normalize_text("café"),  # Composed form
            normalize_text("café")   # Decomposed form (if different)
        )


class TestAddressNormalization(unittest.TestCase):
    """Tests for address normalization functions."""
    
    def test_normalize_address_abbreviations(self):
        """Test expansion of common abbreviations."""
        self.assertIn("colonia", normalize_address("Col. San Benito"))
        self.assertIn("avenida", normalize_address("Av. Roosevelt"))
        self.assertIn("urbanizacion", normalize_address("Urb. Las Flores"))
        self.assertIn("residencial", normalize_address("Res. El Paraíso"))
    
    def test_normalize_address_removes_house_numbers(self):
        """Test removal of house numbers."""
        result = normalize_address("Col. Centro No. 123")
        self.assertNotIn("123", result)
    
    def test_normalize_address_san_salvador(self):
        """Test San Salvador abbreviation."""
        self.assertIn("san salvador", normalize_address("SS, Centro"))
    
    def test_normalize_address_empty(self):
        """Test handling of empty values."""
        self.assertEqual(normalize_address(""), "")
        self.assertEqual(normalize_address(None), "")


class TestCoordinateNormalization(unittest.TestCase):
    """Tests for coordinate normalization."""
    
    def test_normalize_coordinate_precision(self):
        """Test coordinate rounding to specified precision."""
        self.assertEqual(normalize_coordinate(13.6969123456, 4), 13.6969)
        self.assertEqual(normalize_coordinate(-89.2341987654, 4), -89.2342)
    
    def test_normalize_coordinate_different_precisions(self):
        """Test different precision levels."""
        coord = 13.6969876543
        self.assertEqual(normalize_coordinate(coord, 2), 13.70)
        self.assertEqual(normalize_coordinate(coord, 3), 13.697)
        self.assertEqual(normalize_coordinate(coord, 4), 13.697)  # round(13.6969876543, 4) = 13.697
        self.assertEqual(normalize_coordinate(coord, 5), 13.69699)
    
    def test_normalize_coordinate_none(self):
        """Test handling of None values."""
        self.assertEqual(normalize_coordinate(None), 0.0)
    
    def test_normalize_coordinate_invalid(self):
        """Test handling of invalid values."""
        self.assertEqual(normalize_coordinate("invalid"), 0.0)
        self.assertEqual(normalize_coordinate(""), 0.0)


class TestPriceNormalization(unittest.TestCase):
    """Tests for price normalization."""
    
    def test_normalize_price_numbers(self):
        """Test price normalization from numbers."""
        self.assertEqual(normalize_price(250000), 250000.0)
        self.assertEqual(normalize_price(250000.50), 250000.50)
    
    def test_normalize_price_strings(self):
        """Test price normalization from strings."""
        self.assertEqual(normalize_price("$250,000"), 250000.0)
        self.assertEqual(normalize_price("USD 150,000.00"), 150000.0)
        self.assertEqual(normalize_price("250000"), 250000.0)
    
    def test_normalize_price_european_format(self):
        """Test European number format (comma as decimal)."""
        self.assertEqual(normalize_price("250000,50"), 250000.50)
    
    def test_normalize_price_empty(self):
        """Test handling of empty/None values."""
        self.assertEqual(normalize_price(None), 0.0)
        self.assertEqual(normalize_price(""), 0.0)


class TestSimilarityFunctions(unittest.TestCase):
    """Tests for similarity matching functions."""
    
    def test_get_text_tokens(self):
        """Test text tokenization."""
        tokens = get_text_tokens("casa en venta colonia escalon")
        self.assertIn("casa", tokens)
        self.assertIn("venta", tokens)
        self.assertIn("colonia", tokens)
        self.assertIn("escalon", tokens)
        self.assertIn("en", tokens)  # 2-letter words are included (filter is >= 2)
    
    def test_get_text_tokens_empty(self):
        """Test empty text tokenization."""
        self.assertEqual(get_text_tokens(""), frozenset())
    
    def test_jaccard_similarity_identical(self):
        """Test Jaccard similarity for identical sets."""
        set1 = frozenset(["casa", "venta", "colonia"])
        self.assertEqual(jaccard_similarity(set1, set1), 1.0)
    
    def test_jaccard_similarity_no_overlap(self):
        """Test Jaccard similarity for disjoint sets."""
        set1 = frozenset(["casa", "venta"])
        set2 = frozenset(["apartamento", "alquiler"])
        self.assertEqual(jaccard_similarity(set1, set2), 0.0)
    
    def test_jaccard_similarity_partial(self):
        """Test Jaccard similarity for partial overlap."""
        set1 = frozenset(["casa", "venta", "colonia"])
        set2 = frozenset(["casa", "venta", "escalon"])
        # Intersection: {casa, venta} = 2
        # Union: {casa, venta, colonia, escalon} = 4
        # Jaccard: 2/4 = 0.5
        self.assertAlmostEqual(jaccard_similarity(set1, set2), 0.5, places=5)
    
    def test_jaccard_similarity_empty(self):
        """Test Jaccard similarity with empty sets."""
        empty = frozenset()
        non_empty = frozenset(["casa"])
        self.assertEqual(jaccard_similarity(empty, non_empty), 0.0)
        self.assertEqual(jaccard_similarity(empty, empty), 0.0)
    
    def test_text_similarity_high(self):
        """Test high text similarity."""
        t1 = "Casa en venta Colonia San Benito"
        t2 = "Casa en venta Col. San Benito"
        similarity = text_similarity(t1, t2)
        self.assertGreater(similarity, 0.7)
    
    def test_text_similarity_low(self):
        """Test low text similarity."""
        t1 = "Casa grande en zona residencial"
        t2 = "Apartamento pequeño centro ciudad"
        similarity = text_similarity(t1, t2)
        self.assertLess(similarity, 0.3)
    
    def test_coordinates_match_exact(self):
        """Test exact coordinate match."""
        self.assertTrue(coordinates_match(13.6969, -89.2341, 13.6969, -89.2341))
    
    def test_coordinates_match_within_tolerance(self):
        """Test coordinates within tolerance."""
        # Default tolerance is 0.0005 degrees (~55m)
        self.assertTrue(coordinates_match(13.6969, -89.2341, 13.6970, -89.2342))
    
    def test_coordinates_match_outside_tolerance(self):
        """Test coordinates outside tolerance."""
        # ~100m apart, should not match with default tolerance
        self.assertFalse(coordinates_match(13.6969, -89.2341, 13.6980, -89.2350))
    
    def test_coordinates_match_zero_values(self):
        """Test that zero coordinates don't match (missing data)."""
        self.assertFalse(coordinates_match(0, 0, 13.6969, -89.2341))
        self.assertFalse(coordinates_match(13.6969, -89.2341, 0, 0))


class TestKeyGeneration(unittest.TestCase):
    """Tests for deduplication key generation."""
    
    def test_generate_dedup_key_deterministic(self):
        """Test that dedup key generation is deterministic."""
        listing = {
            "title": "Casa en Colonia Escalón",
            "location": "San Salvador",
            "latitude": 13.7028,
            "longitude": -89.2432
        }
        key1 = generate_dedup_key(listing)
        key2 = generate_dedup_key(listing)
        self.assertEqual(key1, key2)
    
    def test_generate_dedup_key_case_insensitive(self):
        """Test that dedup key is case-insensitive."""
        listing1 = {"title": "Casa en Colonia Escalón", "location": "San Salvador"}
        listing2 = {"title": "CASA EN COLONIA ESCALON", "location": "SAN SALVADOR"}
        self.assertEqual(generate_dedup_key(listing1), generate_dedup_key(listing2))
    
    def test_generate_dedup_key_accent_insensitive(self):
        """Test that dedup key ignores accents."""
        listing1 = {"title": "Colonia Sán Beníto", "location": "San Salvador"}
        listing2 = {"title": "Colonia San Benito", "location": "San Salvador"}
        self.assertEqual(generate_dedup_key(listing1), generate_dedup_key(listing2))
    
    def test_generate_dedup_key_different_listings(self):
        """Test that different listings get different keys."""
        listing1 = {"title": "Casa en Escalón", "latitude": 13.7028, "longitude": -89.2432}
        listing2 = {"title": "Apartamento en Santa Tecla", "latitude": 13.6647, "longitude": -89.2767}
        self.assertNotEqual(generate_dedup_key(listing1), generate_dedup_key(listing2))
    
    def test_generate_dedup_key_location_dict(self):
        """Test dedup key with location as dictionary."""
        listing = {
            "title": "Casa",
            "location": {"location_original": "San Salvador", "departamento": "San Salvador"}
        }
        key = generate_dedup_key(listing)
        self.assertIsInstance(key, str)
        self.assertEqual(len(key), 64)  # SHA-256 hex length
    
    def test_generate_url_key(self):
        """Test URL key generation."""
        url1 = "https://encuentra24.com/listing/12345"
        url2 = "HTTPS://ENCUENTRA24.COM/listing/12345/"  # Different case/trailing slash
        self.assertEqual(generate_url_key(url1), generate_url_key(url2))
    
    def test_generate_url_key_removes_tracking(self):
        """Test URL key removes tracking parameters."""
        url1 = "https://encuentra24.com/listing/12345"
        url2 = "https://encuentra24.com/listing/12345?utm_source=google"
        self.assertEqual(generate_url_key(url1), generate_url_key(url2))
    
    def test_generate_url_key_none(self):
        """Test URL key with None."""
        self.assertIsNone(generate_url_key(None))
        self.assertIsNone(generate_url_key(""))
    
    def test_generate_external_id_key(self):
        """Test external ID key generation."""
        key = generate_external_id_key("12345", "Encuentra24")
        self.assertEqual(key, "encuentra24:12345")
    
    def test_generate_external_id_key_none(self):
        """Test external ID key with None."""
        self.assertIsNone(generate_external_id_key(None, "Encuentra24"))


class TestDeduplicationManager(unittest.TestCase):
    """Tests for the DeduplicationManager class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for cache
        self.test_cache_dir = tempfile.mkdtemp()
        
        # Sample listings for testing
        self.listing1 = {
            "external_id": "12345",
            "source": "Encuentra24",
            "title": "Casa en Colonia Escalón",
            "location": "San Salvador",
            "latitude": 13.7028,
            "longitude": -89.2432,
            "url": "https://encuentra24.com/listing/12345"
        }
        
        self.listing2 = {
            "external_id": "12346",
            "source": "Encuentra24",
            "title": "Apartamento en Santa Tecla",
            "location": "La Libertad",
            "latitude": 13.6647,
            "longitude": -89.2767,
            "url": "https://encuentra24.com/listing/12346"
        }
        
        self.listing1_duplicate = {
            "external_id": "12345",  # Same ID
            "source": "Encuentra24",
            "title": "Casa en Colonia Escalon",  # Slightly different
            "location": "San Salvador",
            "latitude": 13.7028,
            "longitude": -89.2432,
            "url": "https://encuentra24.com/listing/12345"
        }
        
        self.listing1_cross_source = {
            "external_id": "99999",  # Different ID
            "source": "MiCasaSV",    # Different source
            "title": "Casa en Colonia Escalón",  # Same property?
            "location": "San Salvador",
            "latitude": 13.7029,    # Very close coordinates
            "longitude": -89.2433,
            "url": "https://micasasv.com/listing/99999"
        }
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_cache_dir, ignore_errors=True)
    
    def test_init_creates_cache_dir(self):
        """Test that initialization creates cache directory."""
        cache_dir = os.path.join(self.test_cache_dir, "new_cache")
        dedup = DeduplicationManager(cache_dir=cache_dir)
        self.assertTrue(os.path.exists(cache_dir))
    
    def test_is_duplicate_unique(self):
        """Test unique listing detection."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        is_dup, reason = dedup.is_duplicate(self.listing1)
        self.assertFalse(is_dup)
        self.assertEqual(reason, "Unique")
    
    def test_is_duplicate_by_external_id(self):
        """Test duplicate detection by external ID."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        # Mark first listing as processed
        dedup.mark_processed(self.listing1)
        
        # Check duplicate
        is_dup, reason = dedup.is_duplicate(self.listing1_duplicate)
        self.assertTrue(is_dup)
        self.assertIn("external_id", reason)
    
    def test_is_duplicate_by_url(self):
        """Test duplicate detection by URL."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        # Mark first listing as processed
        dedup.mark_processed(self.listing1)
        
        # Create listing with same URL but different external_id
        same_url = self.listing1.copy()
        same_url["external_id"] = "99999"
        same_url["source"] = "Other"
        
        is_dup, reason = dedup.is_duplicate(same_url)
        self.assertTrue(is_dup)
        self.assertIn("URL", reason)
    
    def test_is_duplicate_by_dedup_key(self):
        """Test duplicate detection by dedup key."""
        dedup = DeduplicationManager(
            cache_dir=self.test_cache_dir,
            enable_similarity_check=False  # Disable to test pure key matching
        )
        
        # Mark first listing as processed
        dedup.mark_processed(self.listing1)
        
        # Create listing with same content but different identifiers
        same_content = {
            "external_id": "99999",
            "source": "Other",
            "title": "Casa en Colonia Escalón",  # Same title
            "location": "San Salvador",
            "latitude": 13.7028,  # Same coordinates
            "longitude": -89.2432,
            "url": "https://other.com/99999"  # Different URL
        }
        
        is_dup, reason = dedup.is_duplicate(same_content)
        self.assertTrue(is_dup)
        self.assertIn("dedup key", reason)
    
    def test_is_duplicate_by_similarity(self):
        """Test duplicate detection by similarity matching."""
        dedup = DeduplicationManager(
            cache_dir=self.test_cache_dir,
            enable_similarity_check=True,
            similarity_threshold=0.8,
            coordinate_tolerance=0.001
        )
        
        # Mark first listing as processed
        dedup.mark_processed(self.listing1)
        
        # Similar listing from different source
        is_dup, reason = dedup.is_duplicate(self.listing1_cross_source)
        self.assertTrue(is_dup)
        self.assertIn("Similar", reason)
    
    def test_mark_processed(self):
        """Test marking listings as processed."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        self.assertEqual(len(dedup.seen_external_ids), 0)
        self.assertEqual(len(dedup.seen_url_keys), 0)
        self.assertEqual(len(dedup.seen_dedup_keys), 0)
        
        dedup.mark_processed(self.listing1)
        
        self.assertEqual(len(dedup.seen_external_ids), 1)
        self.assertEqual(len(dedup.seen_url_keys), 1)
        self.assertEqual(len(dedup.seen_dedup_keys), 1)
        self.assertEqual(dedup.total_processed, 1)
    
    def test_should_checkpoint(self):
        """Test checkpoint triggering."""
        dedup = DeduplicationManager(
            cache_dir=self.test_cache_dir,
            checkpoint_interval=5
        )
        
        # Process 4 records - should not trigger checkpoint
        for i in range(4):
            listing = self.listing1.copy()
            listing["external_id"] = str(i)
            dedup.mark_processed(listing)
            self.assertFalse(dedup.should_checkpoint())
        
        # 5th record should trigger checkpoint
        listing = self.listing1.copy()
        listing["external_id"] = "5"
        dedup.mark_processed(listing)
        self.assertTrue(dedup.should_checkpoint())
    
    def test_save_and_load_checkpoint(self):
        """Test checkpoint persistence."""
        # Create and populate first manager
        dedup1 = DeduplicationManager(cache_dir=self.test_cache_dir)
        dedup1.mark_processed(self.listing1)
        dedup1.mark_processed(self.listing2)
        dedup1.save_checkpoint()
        
        # Create new manager with same cache dir
        dedup2 = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        # Should have loaded the cached data
        self.assertEqual(len(dedup2.seen_dedup_keys), 2)
        
        # Should detect listing1 as duplicate
        is_dup, _ = dedup2.is_duplicate(self.listing1)
        self.assertTrue(is_dup)
    
    def test_clear_cache(self):
        """Test cache clearing."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        dedup.mark_processed(self.listing1)
        dedup.save_checkpoint()
        
        # Clear cache
        dedup.clear_cache()
        
        # Should be empty
        self.assertEqual(len(dedup.seen_dedup_keys), 0)
        self.assertEqual(len(dedup.seen_external_ids), 0)
        self.assertEqual(dedup.total_processed, 0)
        
        # Listing should now be unique
        is_dup, _ = dedup.is_duplicate(self.listing1)
        self.assertFalse(is_dup)
    
    def test_get_stats(self):
        """Test statistics retrieval."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        # Process some listings
        dedup.mark_processed(self.listing1)
        dedup.mark_processed(self.listing2)
        dedup.mark_duplicate_found()
        
        stats = dedup.get_stats()
        
        self.assertEqual(stats["total_processed"], 2)
        self.assertEqual(stats["duplicates_found"], 1)
        self.assertIn("cache_sizes", stats)
        self.assertEqual(stats["cache_sizes"]["dedup_keys"], 2)


class TestBatchProcessing(unittest.TestCase):
    """Tests for batch processing utilities."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_cache_dir = tempfile.mkdtemp()
        
        self.listings = [
            {
                "external_id": "1",
                "source": "Test",
                "title": "Listing One",
                "latitude": 13.7028,
                "longitude": -89.2432,
                "url": "https://test.com/1"
            },
            {
                "external_id": "2",
                "source": "Test",
                "title": "Listing Two",
                "latitude": 13.6647,
                "longitude": -89.2767,
                "url": "https://test.com/2"
            },
            {
                "external_id": "1",  # Duplicate
                "source": "Test",
                "title": "Listing One Copy",
                "latitude": 13.7028,
                "longitude": -89.2432,
                "url": "https://test.com/1"
            },
            {
                "external_id": "3",
                "source": "Test",
                "title": "Listing Three",
                "latitude": 13.9944,
                "longitude": -89.5589,
                "url": "https://test.com/3"
            },
        ]
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_cache_dir, ignore_errors=True)
    
    def test_deduplicate_listings(self):
        """Test batch deduplication."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        unique, duplicates = deduplicate_listings(
            self.listings,
            dedup_manager=dedup,
            return_duplicates=True
        )
        
        self.assertEqual(len(unique), 3)
        self.assertEqual(len(duplicates), 1)
    
    def test_find_duplicates_in_list(self):
        """Test finding duplicate groups in a list."""
        groups = find_duplicates_in_list(self.listings)
        
        # Should find at least one group of duplicates
        self.assertGreater(len(groups), 0)
        
        # Each group should have more than one listing
        for key, dupes in groups.items():
            self.assertGreater(len(dupes), 1)
    
    def test_merge_duplicate_listings_empty(self):
        """Test merging empty list."""
        result = merge_duplicate_listings([])
        self.assertEqual(result, {})
    
    def test_merge_duplicate_listings_single(self):
        """Test merging single listing."""
        result = merge_duplicate_listings([self.listings[0]])
        self.assertEqual(result, self.listings[0])
    
    def test_merge_duplicate_listings_multiple(self):
        """Test merging multiple listings."""
        listing1 = {
            "title": "Short Title",
            "description": "Short desc",
            "images": ["img1.jpg"],
            "specs": {"bedrooms": 3}
        }
        listing2 = {
            "title": "Much Longer and More Descriptive Title",
            "description": "Much longer and more detailed description here",
            "images": ["img2.jpg", "img3.jpg"],
            "specs": {"bathrooms": 2}
        }
        
        merged = merge_duplicate_listings([listing1, listing2])
        
        # Should prefer longer title
        self.assertEqual(merged["title"], listing2["title"])
        
        # Should prefer longer description
        self.assertEqual(merged["description"], listing2["description"])
        
        # Should combine images
        self.assertEqual(len(merged["images"]), 3)
        
        # Should merge specs
        self.assertEqual(merged["specs"]["bedrooms"], 3)
        self.assertEqual(merged["specs"]["bathrooms"], 2)


class TestEdgeCases(unittest.TestCase):
    """Tests for edge cases and error handling."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_cache_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_cache_dir, ignore_errors=True)
    
    def test_listing_with_missing_fields(self):
        """Test handling of listings with missing fields."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        incomplete_listing = {
            "title": "Test Listing"
            # Missing: external_id, source, url, coordinates
        }
        
        # Should not crash
        is_dup, reason = dedup.is_duplicate(incomplete_listing)
        self.assertFalse(is_dup)
        
        # Should be able to mark as processed
        dedup.mark_processed(incomplete_listing)
        self.assertEqual(dedup.total_processed, 1)
    
    def test_listing_with_none_values(self):
        """Test handling of listings with None values."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        none_listing = {
            "external_id": None,
            "source": None,
            "title": None,
            "location": None,
            "latitude": None,
            "longitude": None,
            "url": None
        }
        
        # Should not crash
        is_dup, reason = dedup.is_duplicate(none_listing)
        self.assertFalse(is_dup)
    
    def test_very_long_title(self):
        """Test handling of very long titles."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        long_title = "A" * 10000  # Very long title
        listing = {"title": long_title}
        
        # Should truncate and not crash
        key = generate_dedup_key(listing)
        self.assertEqual(len(key), 64)  # SHA-256 length
    
    def test_special_unicode_characters(self):
        """Test handling of special Unicode characters."""
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        unicode_listing = {
            "title": "Casa 🏠 en 中文 with émojis 🎉",
            "location": "Señor's Café ☕"
        }
        
        # Should not crash
        key = generate_dedup_key(unicode_listing)
        self.assertEqual(len(key), 64)
    
    def test_concurrent_processing_safety(self):
        """Test that dedup sets are thread-safe for basic operations."""
        import threading
        
        dedup = DeduplicationManager(cache_dir=self.test_cache_dir)
        
        def process_listing(listing_id):
            listing = {
                "external_id": str(listing_id),
                "source": "Test",
                "title": f"Listing {listing_id}"
            }
            dedup.mark_processed(listing)
        
        # Process in parallel threads
        threads = []
        for i in range(100):
            t = threading.Thread(target=process_listing, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All should be processed
        self.assertEqual(dedup.total_processed, 100)


class TestPerformance(unittest.TestCase):
    """Performance and scalability tests."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_cache_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_cache_dir, ignore_errors=True)
    
    def test_large_batch_processing(self):
        """Test processing a large number of listings."""
        import time
        
        dedup = DeduplicationManager(
            cache_dir=self.test_cache_dir,
            enable_similarity_check=False  # Disable for speed test
        )
        
        num_listings = 1000
        
        start = time.time()
        for i in range(num_listings):
            listing = {
                "external_id": str(i),
                "source": "Test",
                "title": f"Listing number {i}",
                "latitude": 13.5 + (i * 0.001),
                "longitude": -89.0 - (i * 0.001)
            }
            dedup.is_duplicate(listing)
            dedup.mark_processed(listing)
        elapsed = time.time() - start
        
        # Should process at least 100 listings per second
        rate = num_listings / elapsed
        self.assertGreater(rate, 100, f"Processing rate too slow: {rate:.1f}/sec")
        
        # All should be processed
        self.assertEqual(dedup.total_processed, num_listings)
    
    def test_lookup_performance(self):
        """Test O(1) lookup performance."""
        import time
        
        dedup = DeduplicationManager(
            cache_dir=self.test_cache_dir,
            enable_similarity_check=False
        )
        
        # Pre-populate with listings
        for i in range(5000):
            dedup.seen_dedup_keys.add(f"key_{i}")
        
        # Time lookups
        start = time.time()
        for i in range(10000):
            _ = f"key_{i % 5000}" in dedup.seen_dedup_keys
        elapsed = time.time() - start
        
        # Should be very fast (O(1))
        self.assertLess(elapsed, 0.1, f"Lookup too slow: {elapsed:.3f}s for 10K lookups")


class TestProcessedRecord(unittest.TestCase):
    """Tests for ProcessedRecord dataclass."""
    
    def test_create_processed_record(self):
        """Test creating a ProcessedRecord."""
        record = ProcessedRecord(
            dedup_key="abc123",
            external_id="12345",
            url_key="xyz789",
            title_tokens=frozenset(["casa", "venta"]),
            lat=13.7028,
            lon=-89.2432
        )
        
        self.assertEqual(record.dedup_key, "abc123")
        self.assertEqual(record.external_id, "12345")
        self.assertIn("casa", record.title_tokens)
        self.assertIsNotNone(record.timestamp)
    
    def test_processed_record_defaults(self):
        """Test ProcessedRecord default values."""
        record = ProcessedRecord(dedup_key="test")
        
        self.assertIsNone(record.external_id)
        self.assertIsNone(record.url_key)
        self.assertEqual(record.title_tokens, frozenset())
        self.assertEqual(record.lat, 0.0)
        self.assertEqual(record.lon, 0.0)


# ============== TEST RUNNER ==============

if __name__ == "__main__":
    # Run tests with verbosity
    unittest.main(verbosity=2)
