"""
Unit Tests for Area Normalizer Module
=====================================
Tests for area unit detection, parsing, and conversion to m².

Run with: python -m pytest test_area_normalizer.py -v
Or: python test_area_normalizer.py
"""

import unittest
from area_normalizer import (
    detect_unit,
    parse_area_value,
    normalize_area,
    normalize_specs_area,
    convert_vara2_to_m2,
    convert_ft2_to_m2,
    VARA2_TO_M2,
    FT2_TO_M2
)


class TestDetectUnit(unittest.TestCase):
    """Tests for detect_unit function."""
    
    def test_m2_variants(self):
        """Test detection of square meters variants."""
        self.assertEqual(detect_unit("120 m2"), "m2")
        self.assertEqual(detect_unit("120 m²"), "m2")
        self.assertEqual(detect_unit("120 mt2"), "m2")
        self.assertEqual(detect_unit("120 mts2"), "m2")
        self.assertEqual(detect_unit("120 metros"), "m2")
        self.assertEqual(detect_unit("120 metros cuadrados"), "m2")
    
    def test_vara2_variants(self):
        """Test detection of varas cuadradas variants."""
        self.assertEqual(detect_unit("100 v2"), "vara2")
        self.assertEqual(detect_unit("100 v²"), "vara2")
        self.assertEqual(detect_unit("100 vara2"), "vara2")
        self.assertEqual(detect_unit("100 varas2"), "vara2")
        self.assertEqual(detect_unit("100 varas"), "vara2")
        self.assertEqual(detect_unit("100 varas cuadradas"), "vara2")
    
    def test_ft2_variants(self):
        """Test detection of square feet variants."""
        self.assertEqual(detect_unit("500 ft2"), "ft2")
        self.assertEqual(detect_unit("500 ft²"), "ft2")
        self.assertEqual(detect_unit("500 sqft"), "ft2")
        self.assertEqual(detect_unit("500 sq ft"), "ft2")
        self.assertEqual(detect_unit("500 pies"), "ft2")
        self.assertEqual(detect_unit("500 pies cuadrados"), "ft2")
    
    def test_no_unit(self):
        """Test when no unit is detected."""
        self.assertIsNone(detect_unit(""))
        self.assertIsNone(detect_unit(None))
        self.assertIsNone(detect_unit("120"))
        self.assertIsNone(detect_unit("big house"))


class TestParseAreaValue(unittest.TestCase):
    """Tests for parse_area_value function."""
    
    def test_simple_integers(self):
        """Test parsing simple integers."""
        self.assertEqual(parse_area_value("120")[0], 120.0)
        self.assertEqual(parse_area_value("1200")[0], 1200.0)
    
    def test_thousands_separator_comma(self):
        """Test parsing with comma as thousands separator."""
        self.assertEqual(parse_area_value("1,200")[0], 1200.0)
        self.assertEqual(parse_area_value("1,200,000")[0], 1200000.0)
    
    def test_thousands_separator_dot(self):
        """Test parsing with dot as thousands separator."""
        self.assertEqual(parse_area_value("1.200")[0], 1200.0)
        self.assertEqual(parse_area_value("1.200.000")[0], 1200000.0)
    
    def test_decimal_dot(self):
        """Test parsing decimals with dot."""
        self.assertEqual(parse_area_value("80.5")[0], 80.5)
        self.assertEqual(parse_area_value("1200.75")[0], 1200.75)
    
    def test_decimal_comma(self):
        """Test parsing decimals with comma."""
        self.assertEqual(parse_area_value("80,5")[0], 80.5)
        self.assertEqual(parse_area_value("1200,75")[0], 1200.75)
    
    def test_mixed_text(self):
        """Test parsing from mixed text."""
        self.assertEqual(parse_area_value("Área: 120 m2")[0], 120.0)
        self.assertEqual(parse_area_value("120 v2 aprox")[0], 120.0)
        self.assertEqual(parse_area_value("Total: 1,500 sqft")[0], 1500.0)
    
    def test_ranges(self):
        """Test parsing ranges (returns average)."""
        value, is_range = parse_area_value("100-150 m2")
        self.assertEqual(value, 125.0)
        self.assertTrue(is_range)
        
        value, is_range = parse_area_value("100 - 200")
        self.assertEqual(value, 150.0)
        self.assertTrue(is_range)
    
    def test_empty_invalid(self):
        """Test handling of empty/invalid input."""
        self.assertIsNone(parse_area_value("")[0])
        self.assertIsNone(parse_area_value(None)[0])
        self.assertIsNone(parse_area_value("no numbers")[0])


class TestNormalizeArea(unittest.TestCase):
    """Tests for normalize_area function."""
    
    def test_m2_passthrough(self):
        """Test that m² values are passed through unchanged."""
        result = normalize_area("120 m2")
        self.assertTrue(result['parse_success'])
        self.assertEqual(result['value_m2'], 120.0)
        self.assertEqual(result['unit_detected'], 'm2')
    
    def test_vara2_conversion(self):
        """Test vara² to m² conversion."""
        result = normalize_area("100 v2")
        self.assertTrue(result['parse_success'])
        self.assertEqual(result['value_m2'], round(100 * VARA2_TO_M2, 2))
        self.assertEqual(result['unit_detected'], 'vara2')
    
    def test_ft2_conversion(self):
        """Test ft² to m² conversion."""
        result = normalize_area("1000 sqft")
        self.assertTrue(result['parse_success'])
        self.assertEqual(result['value_m2'], round(1000 * FT2_TO_M2, 2))
        self.assertEqual(result['unit_detected'], 'ft2')
    
    def test_real_world_examples(self):
        """Test real-world examples from scraped data."""
        # Vivo Latam style
        result = normalize_area("33,711 v2 lote")
        self.assertTrue(result['parse_success'])
        self.assertGreater(result['value_m2'], 20000)
        
        # Encuentra24 style
        result = normalize_area("Área construcción: 150 mts2")
        self.assertTrue(result['parse_success'])
        self.assertEqual(result['value_m2'], 150.0)
        
        # MiCasaSV style
        result = normalize_area("200 m²")
        self.assertTrue(result['parse_success'])
        self.assertEqual(result['value_m2'], 200.0)
    
    def test_error_handling(self):
        """Test error handling for unparseable input."""
        result = normalize_area("")
        self.assertFalse(result['parse_success'])
        self.assertIsNotNone(result['error'])
        
        result = normalize_area("no area here")
        self.assertFalse(result['parse_success'])


class TestNormalizeSpecsArea(unittest.TestCase):
    """Tests for normalize_specs_area function."""
    
    def test_adds_area_m2(self):
        """Test that area_m2 is added to specs."""
        specs = {
            "bedrooms": "3",
            "bathrooms": "2",
            "Área construida": "150 m2"
        }
        result = normalize_specs_area(specs)
        
        self.assertIn('area_m2', result)
        self.assertEqual(result['area_m2'], 150.0)
    
    def test_prefers_construction_area(self):
        """Test that construction area is preferred over land area."""
        specs = {
            "Área del terreno": "500 m2",
            "Área construida": "150 m2"
        }
        result = normalize_specs_area(specs)
        
        self.assertEqual(result['area_m2'], 150.0)
    
    def test_empty_specs(self):
        """Test handling of empty specs."""
        result = normalize_specs_area({})
        self.assertEqual(result, {})
        
        result = normalize_specs_area(None)
        self.assertIsNone(result)
    
    def test_no_area_specs(self):
        """Test specs without area fields."""
        specs = {
            "bedrooms": "3",
            "bathrooms": "2"
        }
        result = normalize_specs_area(specs)
        self.assertNotIn('area_m2', result)


class TestConversionFunctions(unittest.TestCase):
    """Tests for conversion helper functions."""
    
    def test_vara2_to_m2(self):
        """Test vara² to m² conversion."""
        self.assertEqual(convert_vara2_to_m2(100), 69.87)
        self.assertEqual(convert_vara2_to_m2(1000), 698.7)
    
    def test_ft2_to_m2(self):
        """Test ft² to m² conversion."""
        self.assertEqual(convert_ft2_to_m2(100), 9.29)
        self.assertEqual(convert_ft2_to_m2(1000), 92.9)


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
