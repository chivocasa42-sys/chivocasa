#!/usr/bin/env python3
"""
Validate stored listing data against the current live page for each active row.

This script re-scrapes each listing from its `url` using the source-specific
detail scraper and compares the live parse against the stored database row.

It is intentionally conservative:
- default table is `scrapped_data`
- default concurrency is 1
- Encuentra24 discrepancies are classified using both embedded and rendered
  fallbacks so we can separate stale rows from real parser drift

Examples:
    py validate_listing_fidelity.py --table scrapped_data --source Encuentra24 --limit 25
    py validate_listing_fidelity.py --table scrapped_data --external-id 31907564 31857905
    py validate_listing_fidelity.py --table scrapped_data --source CasasAhorita --only-mismatches
"""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import requests

from scraper_encuentra24 import (
    REALTYELSALVADOR_PROPERTIES_URL,
    HEADERS,
    SUPABASE_SERVICE_KEY,
    SUPABASE_URL,
    check_listing_still_active,
    extract_encuentra24_embedded_fallback,
    extract_encuentra24_rendered_fallback,
    get_propilatam_page_issue,
    get_propilatam_page_snapshot,
    get_cbr_properties_by_ids,
    get_realtyelsalvador_session,
    has_valid_coordinates,
    listing_signal_score,
    normalize_realtyelsalvador_property,
    normalize_published_date_for_db,
    normalize_source_text,
    parse_price,
    scrape_realtor_listing,
    scrape_casasahorita_listing,
    scrape_listing,
    scrape_micasasv_listing,
    scrape_nexo_listing,
    scrape_propilatam_listing,
    scrape_vivolatam_listing,
)


DEFAULT_TABLE = "scrapped_data"
SUPPORTED_SOURCES = {
    "camarabienesraices": "CamaraBienesRaices",
    "encuentra24": "Encuentra24",
    "micasasv": "MiCasaSV",
    "casasahorita": "CasasAhorita",
    "vivolatam": "VivoLatam",
    "propilatam": "PropiLatam",
    "nexo": "Nexo",
    "realtor": "Realtor",
    "realtyelsalvador": "RealtyElSalvador",
}


def supabase_headers() -> Dict[str, str]:
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "count=exact",
    }


def simplify_text(value: Any) -> str:
    cleaned = normalize_source_text(value)
    if not cleaned:
        return ""
    normalized = unicodedata.normalize("NFKD", cleaned.lower())
    ascii_like = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    ascii_like = re.sub(r"[^a-z0-9\s]", " ", ascii_like)
    ascii_like = re.sub(r"\s+", " ", ascii_like).strip()
    return ascii_like


def token_overlap(a: str, b: str) -> float:
    a_tokens = {token for token in simplify_text(a).split() if token}
    b_tokens = {token for token in simplify_text(b).split() if token}
    if not a_tokens or not b_tokens:
        return 0.0
    return len(a_tokens & b_tokens) / max(1, min(len(a_tokens), len(b_tokens)))


def texts_similar(a: Any, b: Any, min_overlap: float = 0.75) -> bool:
    left = simplify_text(a)
    right = simplify_text(b)
    if not left and not right:
        return True
    if not left or not right:
        return False
    if left == right:
        return True
    if len(left) >= 8 and left in right:
        return True
    if len(right) >= 8 and right in left:
        return True
    return token_overlap(left, right) >= min_overlap


def to_float(value: Any) -> Optional[float]:
    if value in ("", None, [], {}):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = normalize_source_text(value)
    if not text:
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def numeric_match(a: Any, b: Any, absolute_tolerance: float = 1.0, relative_tolerance: float = 0.02) -> bool:
    left = to_float(a)
    right = to_float(b)
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    diff = abs(left - right)
    if diff <= absolute_tolerance:
        return True
    scale = max(abs(left), abs(right), 1.0)
    return (diff / scale) <= relative_tolerance


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def coordinates_match(db_row: Dict[str, Any], live_row: Dict[str, Any], max_distance_km: float = 2.0) -> bool:
    db_location = db_row.get("location") if isinstance(db_row.get("location"), dict) else {}
    db_lat = db_location.get("latitude")
    db_lng = db_location.get("longitude")
    live_lat = live_row.get("latitude")
    live_lng = live_row.get("longitude")

    if not has_valid_coordinates(db_lat, db_lng) and not has_valid_coordinates(live_lat, live_lng):
        return True
    if not has_valid_coordinates(db_lat, db_lng) or not has_valid_coordinates(live_lat, live_lng):
        return False

    return haversine_km(float(db_lat), float(db_lng), float(live_lat), float(live_lng)) <= max_distance_km


def get_details_mapping(row: Dict[str, Any]) -> Dict[str, Any]:
    return row.get("details") if isinstance(row.get("details"), dict) else {}


def get_specs_mapping(row: Dict[str, Any]) -> Dict[str, Any]:
    return row.get("specs") if isinstance(row.get("specs"), dict) else {}


def detail_value(details: Dict[str, Any], aliases: Iterable[str]) -> Any:
    if not isinstance(details, dict):
        return None

    normalized_aliases = {simplify_text(alias) for alias in aliases}
    for key, value in details.items():
        if simplify_text(key) in normalized_aliases:
            return value
    return None


def location_text_looks_garbled(value: Any) -> bool:
    text = normalize_source_text(value)
    if not text:
        return False

    lowered = text.lower()
    garbled_markers = (
        "recámaras por",
        "recamaras por",
        "baños por",
        "banos por",
        "por usd",
        "por $",
        "#23",
        "#31",
        "#38",
        "alquiler en ",
    )
    if any(marker in lowered for marker in garbled_markers):
        return True

    return bool(
        re.search(
            r"\b\d+\s+rec(?:á|a)maras\b|\b\d+\s+ba(?:ñ|n)os\b|\busd\s*\d",
            lowered,
            re.IGNORECASE,
        )
    )


def location_variants_conflict(left: Any, right: Any) -> bool:
    left_text = normalize_source_text(left)
    right_text = normalize_source_text(right)
    if not left_text or not right_text:
        return False

    if simplify_text(left_text) == simplify_text(right_text):
        return False

    left_parts = [part.strip() for part in left_text.split(",") if part.strip()]
    right_parts = [part.strip() for part in right_text.split(",") if part.strip()]
    left_tokens = {token for token in simplify_text(left_text).split() if token}
    right_tokens = {token for token in simplify_text(right_text).split() if token}

    if location_text_looks_garbled(left_text) != location_text_looks_garbled(right_text):
        return False

    shorter_tokens, longer_tokens = (
        (left_tokens, right_tokens) if len(left_tokens) <= len(right_tokens) else (right_tokens, left_tokens)
    )
    if shorter_tokens and len(shorter_tokens) <= 2 and shorter_tokens.issubset(longer_tokens):
        return False

    if token_overlap(left_text, right_text) < 0.8:
        return True

    longer = max(len(left_text), len(right_text))
    shorter = max(1, min(len(left_text), len(right_text)))
    if abs(len(left_parts) - len(right_parts)) >= 2 and longer >= int(shorter * 1.5):
        return True

    return False


def derive_location_text(row: Dict[str, Any]) -> str:
    if normalize_source_text(row.get("location")) and not isinstance(row.get("location"), dict):
        return normalize_source_text(row.get("location"))

    details = get_details_mapping(row)
    value = detail_value(details, ("Ubicación", "Localización", "location", "localizacion", "ubicacion", "Ciudad", "city"))
    if normalize_source_text(value):
        return normalize_source_text(value)

    return ""


def build_listing_like_snapshot(row: Dict[str, Any]) -> Dict[str, Any]:
    location = row.get("location") if isinstance(row.get("location"), dict) else {}
    return {
        "title": row.get("title", ""),
        "price": row.get("price"),
        "location": derive_location_text(row),
        "specs": get_specs_mapping(row),
        "details": get_details_mapping(row),
        "description": row.get("description", ""),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
    }


def specs_value(specs: Dict[str, Any], aliases: Iterable[str]) -> Any:
    alias_list = list(aliases)
    if not isinstance(specs, dict):
        return None

    normalized_aliases = {simplify_text(alias) for alias in alias_list}
    for key, value in specs.items():
        if simplify_text(key) in normalized_aliases:
            return value
    return None


def summarize_details(row: Dict[str, Any]) -> Dict[str, Any]:
    details = get_details_mapping(row)
    summary = {}
    detail_aliases = {
        "Ubicación": ("Ubicación", "Localización", "location", "localizacion", "ubicacion"),
        "Región": ("Región", "Region", "region"),
        "property_type": ("property_type",),
        "Niveles": ("Niveles", "Número de Piso", "Numero de Piso"),
        "Año": ("Año", "Antigüedad", "Antiguedad"),
    }
    for output_key, aliases in detail_aliases.items():
        value = detail_value(details, aliases)
        if value not in ("", None, [], {}):
            summary[output_key] = value
    return summary


def compare_core_fields(db_row: Dict[str, Any], live_row: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    mismatches: Dict[str, Dict[str, Any]] = {}

    db_title = db_row.get("title", "")
    live_title = live_row.get("title", "")
    if not texts_similar(db_title, live_title, min_overlap=0.7):
        mismatches["title"] = {"db": db_title, "live": live_title}

    db_price = parse_price(db_row.get("price"))
    live_price = parse_price(live_row.get("price"))
    if not numeric_match(db_price, live_price, absolute_tolerance=1.0, relative_tolerance=0.005):
        mismatches["price"] = {"db": db_price, "live": live_price}

    db_location = derive_location_text(db_row)
    live_location = derive_location_text(live_row)
    if not texts_similar(db_location, live_location, min_overlap=0.65):
        mismatches["location"] = {"db": db_location, "live": live_location}

    db_date = normalize_published_date_for_db(db_row.get("published_date"))
    live_date = normalize_published_date_for_db(live_row.get("published_date"))
    if db_date != live_date and not (db_date is None and live_date is None):
        mismatches["published_date"] = {"db": db_date, "live": live_date}

    db_specs = get_specs_mapping(db_row)
    live_specs = get_specs_mapping(live_row)
    spec_aliases = {
        "area_m2": ("area_m2", "area", "área construida (m²)", "area construida (m2)", "área construida"),
        "bedrooms": ("bedrooms", "recamaras", "habitaciones"),
        "bathrooms": ("bathrooms", "banos", "baños"),
        "parking": ("parking", "parqueo", "parqueos", "vehiculos"),
    }

    for field_name, aliases in spec_aliases.items():
        db_value = specs_value(db_specs, aliases)
        live_value = specs_value(live_specs, aliases)
        if field_name == "area_m2":
            matches = numeric_match(db_value, live_value, absolute_tolerance=3.0, relative_tolerance=0.03)
        else:
            matches = numeric_match(db_value, live_value, absolute_tolerance=0.1, relative_tolerance=0.001)
        if not matches:
            mismatches[field_name] = {"db": db_value, "live": live_value}

    if not coordinates_match(db_row, live_row):
        db_location_obj = db_row.get("location") if isinstance(db_row.get("location"), dict) else {}
        mismatches["coordinates"] = {
            "db": {
                "latitude": db_location_obj.get("latitude"),
                "longitude": db_location_obj.get("longitude"),
            },
            "live": {
                "latitude": live_row.get("latitude"),
                "longitude": live_row.get("longitude"),
            },
        }

    db_property_type = detail_value(get_details_mapping(db_row), ("property_type",))
    live_property_type = detail_value(get_details_mapping(live_row), ("property_type",))
    if not texts_similar(db_property_type, live_property_type):
        mismatches["property_type"] = {"db": db_property_type, "live": live_property_type}

    db_description = normalize_source_text(db_row.get("description"))
    live_description = normalize_source_text(live_row.get("description"))
    if (len(db_description) < 40) != (len(live_description) < 40):
        mismatches["description_presence"] = {
            "db": bool(len(db_description) >= 40),
            "live": bool(len(live_description) >= 40),
        }

    return mismatches


def source_key(source: str) -> str:
    return simplify_text(source).replace(" ", "")


def scrape_realtor_live_listing(row: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    listing = scrape_realtor_listing(row.get("url"), row.get("listing_type") or "auto")
    if listing is None:
        return None, "inactive_at_source: Realtor detail page returned 404"
    return listing, None


def scrape_cbr_live_listing(row: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    external_id = row.get("external_id")
    try:
        normalized_id = int(str(external_id))
    except (TypeError, ValueError):
        return None, "invalid_external_id"

    listings = get_cbr_properties_by_ids([normalized_id])
    if not listings:
        return None, "inactive_at_source: listing not returned by CamaraBienesRaices API"

    for listing in listings:
        if str(listing.get("external_id")) == str(normalized_id):
            return listing, None

    return listings[0], None


def scrape_realtyelsalvador_live_listing(row: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    url = row.get("url") or ""
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    slug = path_parts[-1] if path_parts else ""
    if not slug or slug == "propiedades":
        return None, "missing_slug"

    session = get_realtyelsalvador_session()
    response = session.get(
        REALTYELSALVADOR_PROPERTIES_URL,
        params={"slug": slug, "per_page": 1, "_embed": "1"},
        timeout=30,
    )

    if response.status_code == 404:
        return None, "inactive_at_source: RealtyElSalvador returned 404"
    if response.status_code >= 400:
        return None, f"http_{response.status_code}"

    payload = response.json()
    if not payload:
        return None, "inactive_at_source: listing not present in RealtyElSalvador API"

    listing = normalize_realtyelsalvador_property(payload[0])
    if not listing:
        return None, "live_scrape_returned_none"
    if not listing.get("active", True):
        return None, "inactive_at_source: property status is not disponible"

    return listing, None


def classify_propi_family_empty_response(url: str, source_label: str) -> Optional[str]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except Exception:
        return None

    if response.status_code == 404:
        return f"inactive_at_source: {source_label} returned 404"
    if response.status_code != 200:
        return None

    html = response.text
    page_issue = get_propilatam_page_issue(html)
    if page_issue == "listing unavailable":
        return f"inactive_at_source: {source_label} listing page is no longer available"
    if page_issue == "placeholder page":
        return f"inactive_at_source: {source_label} placeholder page"

    page_snapshot = get_propilatam_page_snapshot(html)
    page_text = page_snapshot["body_prefix_lower"]
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    page_title = normalize_source_text(title_match.group(1)).lower() if title_match else ""

    if any(
        marker in page_text
        for marker in (
            "página no encontrada",
            "pagina no encontrada",
            "no se encontró este anuncio",
            "no se encontro este anuncio",
            "no se encuentra disponible",
        )
    ):
        return f"inactive_at_source: {source_label} listing page is no longer available"

    if "undefined" in page_title:
        return f"inactive_at_source: {source_label} placeholder page"

    if (
        "precio desde" in page_text
        and "programar asesor" in page_text
        and "elegir unidad" in page_text
        and not re.search(r"<h1\b", html, re.IGNORECASE)
    ):
        return f"inactive_at_source: {source_label} placeholder page"

    return None


def scrape_live_listing(row: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    source = source_key(row.get("source", ""))
    url = row.get("url")
    listing_type = row.get("listing_type") or "auto"
    if not url:
        return None, "missing_url"

    try:
        if source == "encuentra24":
            return scrape_listing(url, listing_type if listing_type != "auto" else "sale"), None
        if source == "micasasv":
            return scrape_micasasv_listing(url, listing_type if listing_type != "auto" else "sale"), None
        if source == "casasahorita":
            return scrape_casasahorita_listing(url, listing_type), None
        if source == "camarabienesraices":
            return scrape_cbr_live_listing(row)
        if source == "vivolatam":
            listing = scrape_vivolatam_listing(url, listing_type if listing_type != "auto" else "sale")
            if listing:
                return listing, None
            return None, classify_propi_family_empty_response(url, "VivoLatam") or "live_scrape_returned_none"
        if source == "propilatam":
            listing = scrape_propilatam_listing(url, listing_type if listing_type != "auto" else "sale")
            if listing:
                return listing, None
            return None, classify_propi_family_empty_response(url, "PropiLatam") or "live_scrape_returned_none"
        if source == "nexo":
            return scrape_nexo_listing(url, listing_type), None
        if source == "realtor":
            return scrape_realtor_live_listing(row)
        if source == "realtyelsalvador":
            return scrape_realtyelsalvador_live_listing(row)
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"

    return None, f"unsupported_source:{row.get('source')}"


def gather_encuentra24_diagnostics(url: str) -> Dict[str, Any]:
    diagnostics: Dict[str, Any] = {"embedded": {}, "rendered": {}, "error": None}
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        diagnostics["http_status"] = response.status_code
        if response.status_code != 200:
            diagnostics["error"] = f"http_{response.status_code}"
            return diagnostics
        diagnostics["embedded"] = extract_encuentra24_embedded_fallback(response.text, url)
        diagnostics["rendered"] = extract_encuentra24_rendered_fallback(response.text, url)
        return diagnostics
    except Exception as exc:
        diagnostics["error"] = f"{type(exc).__name__}: {exc}"
        return diagnostics


def find_conflicting_encuentra24_fields(diagnostics: Dict[str, Any]) -> List[str]:
    conflicts: List[str] = []
    embedded = diagnostics.get("embedded") if isinstance(diagnostics.get("embedded"), dict) else {}
    rendered = diagnostics.get("rendered") if isinstance(diagnostics.get("rendered"), dict) else {}

    embedded_price = parse_price(embedded.get("price"))
    rendered_price = parse_price(rendered.get("price"))
    if not numeric_match(embedded_price, rendered_price, absolute_tolerance=1.0, relative_tolerance=0.005):
        if embedded_price is not None and rendered_price is not None:
            conflicts.append("price")

    if location_variants_conflict(derive_location_text(embedded), derive_location_text(rendered)):
        conflicts.append("location")

    return conflicts


def classify_result(
    db_row: Dict[str, Any],
    live_row: Optional[Dict[str, Any]],
    mismatches: Dict[str, Dict[str, Any]],
    live_error: Optional[str],
    diagnostics: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    if live_row is None:
        if live_error and live_error.startswith("unsupported_source"):
            return "unsupported_source", live_error
        if live_error and live_error.startswith("inactive_at_source:"):
            return "inactive_at_source", live_error.split(":", 1)[1].strip()

        is_active, reason = check_listing_still_active(db_row.get("url"), db_row.get("source"))
        if not is_active:
            return "inactive_at_source", reason
        return "scrape_error", live_error or "live_scrape_returned_none"

    if not mismatches:
        return "up_to_date", "stored row matches current live scrape"

    db_score = listing_signal_score(build_listing_like_snapshot(db_row))
    live_score = listing_signal_score(live_row)

    if source_key(db_row.get("source", "")) == "encuentra24" and diagnostics:
        conflicts = find_conflicting_encuentra24_fields(diagnostics)
        relevant_conflicts: List[str] = []
        if "price" in conflicts and "price" in mismatches:
            relevant_conflicts.append("price")
        if "location" in conflicts and "location" in mismatches:
            live_location = derive_location_text(live_row)
            if not live_location or location_text_looks_garbled(live_location):
                relevant_conflicts.append("location")
        if relevant_conflicts:
            deduped_conflicts = list(dict.fromkeys(relevant_conflicts))
            return "likely_scraper_issue", f"encuentra24 fallbacks disagree on: {', '.join(deduped_conflicts)}"

    if live_score >= max(4, db_score):
        return "refresh_needed", "current live scrape looks coherent and differs from stored row"

    return "needs_manual_review", "live scrape differs, but confidence is not high enough to auto-classify as stale"


def fetch_active_rows(
    table_name: str,
    source: Optional[str] = None,
    limit: Optional[int] = None,
    external_ids: Optional[List[str]] = None,
    page_size: int = 500,
) -> List[Dict[str, Any]]:
    fields = ",".join(
        [
            "external_id",
            "title",
            "price",
            "location",
            "published_date",
            "listing_type",
            "url",
            "specs",
            "details",
            "description",
            "source",
            "active",
            "last_updated",
        ]
    )
    headers = supabase_headers()
    rows: List[Dict[str, Any]] = []
    wanted_ids = {str(value) for value in external_ids or []}
    offset = 0

    while True:
        url = (
            f"{SUPABASE_URL}/rest/v1/{table_name}"
            f"?select={fields}&active=eq.true&order=external_id&offset={offset}&limit={page_size}"
        )
        if source:
            url += f"&source=eq.{source}"

        response = requests.get(url, headers=headers, timeout=60)
        if response.status_code not in (200, 206):
            raise RuntimeError(f"supabase_fetch_failed:{response.status_code}:{response.text[:200]}")

        batch = response.json()
        if not batch:
            break

        for row in batch:
            if wanted_ids and str(row.get("external_id")) not in wanted_ids:
                continue
            rows.append(row)
            if limit and len(rows) >= limit:
                return rows[:limit]

        if wanted_ids and wanted_ids.issubset({str(row.get('external_id')) for row in rows}):
            break

        if len(batch) < page_size:
            break
        offset += page_size

    return rows[:limit] if limit else rows


def build_result(row: Dict[str, Any]) -> Dict[str, Any]:
    live_row, live_error = scrape_live_listing(row)
    mismatches: Dict[str, Dict[str, Any]] = {}
    diagnostics: Optional[Dict[str, Any]] = None

    if live_row is None and (not live_error or live_error == "live_scrape_returned_none"):
        time.sleep(0.35)
        retry_live_row, retry_live_error = scrape_live_listing(row)
        if retry_live_row is not None or retry_live_error != live_error:
            live_row, live_error = retry_live_row, retry_live_error

    if live_row:
        mismatches = compare_core_fields(row, live_row)

    if mismatches and source_key(row.get("source", "")) == "encuentra24":
        diagnostics = gather_encuentra24_diagnostics(row.get("url"))

    classification, reason = classify_result(row, live_row, mismatches, live_error, diagnostics)

    result = {
        "external_id": row.get("external_id"),
        "source": row.get("source"),
        "url": row.get("url"),
        "listing_type": row.get("listing_type"),
        "db_last_updated": row.get("last_updated"),
        "classification": classification,
        "reason": reason,
        "mismatch_fields": sorted(mismatches.keys()),
        "db_signal_score": listing_signal_score(build_listing_like_snapshot(row)),
        "live_signal_score": listing_signal_score(live_row) if live_row else None,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    if mismatches:
        result["mismatches"] = mismatches

    if live_row:
        result["live_snapshot"] = {
            "title": live_row.get("title"),
            "price": parse_price(live_row.get("price")),
            "location": derive_location_text(live_row),
            "published_date": normalize_published_date_for_db(live_row.get("published_date")),
            "specs": get_specs_mapping(live_row),
            "details": summarize_details(live_row),
            "coordinates": {
                "latitude": live_row.get("latitude"),
                "longitude": live_row.get("longitude"),
            },
        }

    result["db_snapshot"] = {
        "title": row.get("title"),
        "price": parse_price(row.get("price")),
        "location": derive_location_text(row),
        "published_date": normalize_published_date_for_db(row.get("published_date")),
        "specs": get_specs_mapping(row),
        "details": summarize_details(row),
        "coordinates": {
            "latitude": (row.get("location") or {}).get("latitude") if isinstance(row.get("location"), dict) else None,
            "longitude": (row.get("location") or {}).get("longitude") if isinstance(row.get("location"), dict) else None,
        },
    }

    if diagnostics:
        diagnostic_conflicts = find_conflicting_encuentra24_fields(diagnostics)
        result["diagnostics"] = {
            "embedded": {
                "price": parse_price(diagnostics.get("embedded", {}).get("price")),
                "location": derive_location_text(diagnostics.get("embedded", {})),
            },
            "rendered": {
                "price": parse_price(diagnostics.get("rendered", {}).get("price")),
                "location": derive_location_text(diagnostics.get("rendered", {})),
            },
            "error": diagnostics.get("error"),
            "http_status": diagnostics.get("http_status"),
            "conflicts": diagnostic_conflicts,
        }

    return result


def print_progress(index: int, total: int, result: Dict[str, Any]) -> None:
    indicator_map = {
        "up_to_date": "OK",
        "refresh_needed": "RF",
        "likely_scraper_issue": "BUG",
        "inactive_at_source": "OFF",
        "scrape_error": "ERR",
        "unsupported_source": "SKIP",
        "needs_manual_review": "REV",
    }
    indicator = indicator_map.get(result["classification"], "???")
    fields = ",".join(result.get("mismatch_fields", []))
    if fields:
        fields = f" [{fields}]"
    print(f"[{index}/{total}] {indicator} {result['external_id']} {result['classification']}{fields}")


def summarize_results(results: List[Dict[str, Any]]) -> None:
    counts: Dict[str, int] = {}
    for result in results:
        counts[result["classification"]] = counts.get(result["classification"], 0) + 1

    print("\nSummary")
    print("=" * 60)
    for key in sorted(counts):
        print(f"{key}: {counts[key]}")
    print(f"total: {len(results)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate live listing fidelity against active DB rows")
    parser.add_argument("--table", default=DEFAULT_TABLE, help=f"Supabase table to validate (default: {DEFAULT_TABLE})")
    parser.add_argument("--source", help="Optional source filter, for example Encuentra24 or CasasAhorita")
    parser.add_argument("--limit", type=int, help="Optional max number of rows to validate")
    parser.add_argument("--external-id", nargs="*", help="Optional list of external_id values to validate")
    parser.add_argument("--max-workers", type=int, default=1, help="Concurrent validation workers (default: 1)")
    parser.add_argument("--only-mismatches", action="store_true", help="Suppress up_to_date rows in terminal output")
    parser.add_argument("--json-out", help="Optional path to save full JSON results")
    args = parser.parse_args()

    print("=" * 60)
    print("LISTING FIDELITY VALIDATOR")
    print("=" * 60)
    print(f"table: {args.table}")
    print(f"source: {args.source or 'all'}")
    print(f"limit: {args.limit or 'all'}")
    print(f"external_ids: {', '.join(args.external_id) if args.external_id else 'all'}")
    print(f"max_workers: {args.max_workers}")
    print("=" * 60)

    rows = fetch_active_rows(
        table_name=args.table,
        source=args.source,
        limit=args.limit,
        external_ids=args.external_id,
    )

    if not rows:
        print("No matching active rows found.")
        return

    print(f"Fetched {len(rows)} active rows for validation.\n")

    results: List[Dict[str, Any]] = []
    total = len(rows)

    if args.max_workers <= 1:
        for index, row in enumerate(rows, start=1):
            result = build_result(row)
            results.append(result)
            if not args.only_mismatches or result["classification"] != "up_to_date":
                print_progress(index, total, result)
    else:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_index = {
                executor.submit(build_result, row): index
                for index, row in enumerate(rows, start=1)
            }
            buffered_results: Dict[int, Dict[str, Any]] = {}
            next_index = 1

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                buffered_results[index] = future.result()

                while next_index in buffered_results:
                    result = buffered_results.pop(next_index)
                    results.append(result)
                    if not args.only_mismatches or result["classification"] != "up_to_date":
                        print_progress(next_index, total, result)
                    next_index += 1

    summarize_results(results)

    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            json.dump(results, handle, ensure_ascii=False, indent=2)
        print(f"\nSaved JSON report to {args.json_out}")


if __name__ == "__main__":
    main()
