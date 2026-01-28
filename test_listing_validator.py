"""
Unit Tests for Listing Validator Module
=======================================
Tests for listing status detection across different sources.

Run with: python -m pytest test_listing_validator.py -v
Or: python test_listing_validator.py
"""

import unittest
from unittest.mock import patch, MagicMock
from listing_validator import (
    validate_encuentra24,
    validate_micasasv,
    validate_realtor,
    validate_vivolatam,
    validate_listing,
    _check_patterns,
    ListingStatus,
    ENCUENTRA24_DELETED_PATTERNS
)


class TestPatternMatching(unittest.TestCase):
    """Tests for pattern matching utility."""
    
    def test_deleted_pattern_match(self):
        """Test detection of deleted patterns."""
        html = """
        <div class="modal">
            <h2>Anuncio borrado</h2>
            <p>Lo sentimos mucho, pero este anuncio ya fue eliminado por el anunciante.</p>
        </div>
        """
        self.assertTrue(_check_patterns(html, ENCUENTRA24_DELETED_PATTERNS))
    
    def test_no_pattern_match(self):
        """Test that active listings don't match deleted patterns."""
        html = """
        <div class="listing">
            <h1>Casa en venta en San Salvador</h1>
            <p class="price">$125,000</p>
        </div>
        """
        self.assertFalse(_check_patterns(html, ENCUENTRA24_DELETED_PATTERNS))


class TestEncuentra24Validator(unittest.TestCase):
    """Tests for Encuentra24 validator."""
    
    @patch('listing_validator._fetch_page')
    def test_active_listing(self, mock_fetch):
        """Test detection of active listing."""
        mock_fetch.return_value = (
            '<html><h1 class="d3-property-title">Casa en venta</h1></html>',
            200,
            None
        )
        result = validate_encuentra24("https://encuentra24.com/test")
        self.assertEqual(result['status'], ListingStatus.ACTIVE.value)
    
    @patch('listing_validator._fetch_page')
    def test_deleted_listing(self, mock_fetch):
        """Test detection of deleted listing."""
        mock_fetch.return_value = (
            '<html><div>Anuncio borrado</div><p>eliminado por el anunciante</p></html>',
            200,
            None
        )
        result = validate_encuentra24("https://encuentra24.com/test")
        self.assertEqual(result['status'], ListingStatus.DELETED.value)
    
    @patch('listing_validator._fetch_page')
    def test_404_listing(self, mock_fetch):
        """Test detection of 404 error."""
        mock_fetch.return_value = ('Not Found', 404, None)
        result = validate_encuentra24("https://encuentra24.com/test")
        self.assertEqual(result['status'], ListingStatus.NOT_FOUND.value)
    
    @patch('listing_validator._fetch_page')
    def test_network_error(self, mock_fetch):
        """Test handling of network errors."""
        mock_fetch.return_value = (None, 0, "Connection error")
        result = validate_encuentra24("https://encuentra24.com/test")
        self.assertEqual(result['status'], ListingStatus.ERROR.value)


class TestMiCasaSVValidator(unittest.TestCase):
    """Tests for MiCasaSV validator."""
    
    @patch('listing_validator._fetch_page')
    def test_active_listing(self, mock_fetch):
        """Test detection of active MiCasaSV listing."""
        mock_fetch.return_value = (
            '<html><h1 class="listing-title">Casa en alquiler</h1>' + 'x' * 6000 + '</html>',
            200,
            None
        )
        result = validate_micasasv("https://micasasv.com/listing/test")
        self.assertEqual(result['status'], ListingStatus.ACTIVE.value)
    
    @patch('listing_validator._fetch_page')
    def test_404_listing(self, mock_fetch):
        """Test detection of 404 MiCasaSV listing."""
        mock_fetch.return_value = ('Not Found', 404, None)
        result = validate_micasasv("https://micasasv.com/listing/test")
        self.assertEqual(result['status'], ListingStatus.NOT_FOUND.value)


class TestRealtorValidator(unittest.TestCase):
    """Tests for Realtor validator."""
    
    @patch('listing_validator._fetch_page')
    def test_active_listing(self, mock_fetch):
        """Test detection of active Realtor listing."""
        mock_fetch.return_value = (
            '<html><script id="__NEXT_DATA__">{"props":{"pageProps":{}}}</script></html>',
            200,
            None
        )
        result = validate_realtor("https://realtor.com/test")
        self.assertEqual(result['status'], ListingStatus.ACTIVE.value)
    
    @patch('listing_validator._fetch_page')
    def test_missing_next_data(self, mock_fetch):
        """Test detection of missing NEXT_DATA."""
        mock_fetch.return_value = ('<html><body>Empty page</body></html>', 200, None)
        result = validate_realtor("https://realtor.com/test")
        self.assertEqual(result['status'], ListingStatus.UNKNOWN.value)


class TestVivoLatamValidator(unittest.TestCase):
    """Tests for VivoLatam validator."""
    
    @patch('listing_validator._fetch_page')
    def test_active_listing(self, mock_fetch):
        """Test detection of active VivoLatam listing."""
        mock_fetch.return_value = (
            '<html><h1 class="title">Propiedad</h1><div class="price">$100,000</div></html>',
            200,
            None
        )
        result = validate_vivolatam("https://vivolatam.com/test")
        self.assertEqual(result['status'], ListingStatus.ACTIVE.value)
    
    @patch('listing_validator._fetch_page')
    def test_404_listing(self, mock_fetch):
        """Test detection of 404 VivoLatam listing."""
        mock_fetch.return_value = ('Not Found', 404, None)
        result = validate_vivolatam("https://vivolatam.com/test")
        self.assertEqual(result['status'], ListingStatus.NOT_FOUND.value)


class TestValidateListingDispatcher(unittest.TestCase):
    """Tests for the main validate_listing dispatcher."""
    
    @patch('listing_validator.validate_encuentra24')
    def test_dispatch_encuentra24(self, mock_validator):
        """Test dispatching to Encuentra24 validator."""
        mock_validator.return_value = {'status': 'active'}
        validate_listing("https://test.com", "Encuentra24")
        mock_validator.assert_called_once()
    
    @patch('listing_validator.validate_micasasv')
    def test_dispatch_micasasv(self, mock_validator):
        """Test dispatching to MiCasaSV validator."""
        mock_validator.return_value = {'status': 'active'}
        validate_listing("https://test.com", "MiCasaSV")
        mock_validator.assert_called_once()
    
    def test_unknown_source(self):
        """Test handling of unknown source."""
        result = validate_listing("https://test.com", "UnknownSource")
        self.assertEqual(result['status'], ListingStatus.UNKNOWN.value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
