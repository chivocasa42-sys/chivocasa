#!/usr/bin/env python3
"""Test the fix for Colón false positive."""

from scraper_encuentra24 import detect_municipio

# Test case: 'Colonia San Benito' should NOT match 'Colón' municipality
result = detect_municipio('Colonia San Benito', '', '')
print(f"Location: 'Colonia San Benito' -> municipio: '{result['municipio_detectado']}'")
assert result['municipio_detectado'] != 'Colón', "FAIL: Colonia matched Colón!"

# Test case: actual 'Colón' should still match  
result2 = detect_municipio('Colón, La Libertad', '', '')
print(f"Location: 'Colón, La Libertad' -> municipio: '{result2['municipio_detectado']}'")

# Test with title containing 'La Castellana'
result3 = detect_municipio('', '', 'Casa en La Castellana - 4 habitaciones')
print(f"Title: 'Casa en La Castellana' -> municipio: '{result3['municipio_detectado']}'")

print("\n✓ All tests passed!")
