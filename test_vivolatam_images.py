"""Test script to analyze VivoLatam image extraction patterns."""
import requests
import re
import json

url = "https://www.vivolatam.com/es/el-salvador/bienes-raices/l/casa-en-alquiler-en-cuscatancingo-72u6n46e9z"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

print(f"Fetching: {url}")
resp = requests.get(url, headers=headers, timeout=30)
print(f"Status: {resp.status_code}")
html = resp.text

# Debug: check for listing ID in HTML
listing_id = "72u6n46e9z"
listing_id_count = html.count(listing_id)
print(f"Listing ID '{listing_id}' appears {listing_id_count} times in HTML")

# Look for image patterns in the embedded RSC data
# VivoLatam uses vl-cdn bucket with paths like:
# assets/media/app/el-salvador/real-estate/l/{listing_id}/images/{filename}.jpg

# Pattern 1: Look for the image path pattern
image_path_pattern = r'assets/media/app/el-salvador/real-estate/l/[^/]+/images/([^"\\]+\.(jpg|png|webp))'
path_matches = re.findall(image_path_pattern, html)
print(f"\nPattern 1 - Full path matches: {len(path_matches)}")
for m in path_matches[:10]:
    print(f"  {m[0]}")

# Pattern 2: Look for image key pattern (000_uuid.jpg)
image_key_pattern = r'(\d{3}_[a-f0-9-]+\.(jpg|png|webp))'
key_matches = re.findall(image_key_pattern, html, re.I)
print(f"\nPattern 2 - Image key matches: {len(key_matches)}")
for m in set(key_matches)[:10]:
    print(f"  {m[0]}")

# Pattern 3: Look for CDN URLs
cdn_pattern = r'(cdn\.vivolatam\.com[^"\s]+)'
cdn_matches = re.findall(cdn_pattern, html)
print(f"\nPattern 3 - CDN URLs: {len(cdn_matches)}")
for m in set(cdn_matches)[:5]:
    print(f"  {m[:80]}")

# Pattern 4: Look for "media" array in RSC data (escaped JSON style)
# Example: \\\"media\\\":[{\\\"type\\\":\\\"image\\\",\\\"key\\\":\\\"000_xyz.jpg\\\"}]
media_pattern = r'\\\\?"media\\\\?":\s*\[(.*?)\]'
media_matches = re.findall(media_pattern, html, re.DOTALL)
print(f"\nPattern 4 - Media arrays found: {len(media_matches)}")
if media_matches:
    # Take the longest match which likely has all images
    longest = max(media_matches, key=len)
    print(f"  Longest media array ({len(longest)} chars): {longest[:300]}...")

# Pattern 5: Look for image.vivolatam.com URLs
img_service_pattern = r'https?://image\.vivolatam\.com/[a-zA-Z0-9+/=]+'
img_service_matches = re.findall(img_service_pattern, html)
print(f"\nPattern 5 - image.vivolatam.com URLs: {len(img_service_matches)}")
for m in set(img_service_matches)[:3]:
    print(f"  {m[:80]}...")

# Pattern 6: Look for JSON objects with images field
images_field_pattern = r'\\\\?"images\\\\?":\s*\[(.*?)\]'
images_matches = re.findall(images_field_pattern, html, re.DOTALL)
print(f"\nPattern 6 - Images field arrays: {len(images_matches)}")
if images_matches:
    longest = max(images_matches, key=len)
    print(f"  Longest ({len(longest)} chars): {longest[:500]}...")

print("\n=== Done ===")
