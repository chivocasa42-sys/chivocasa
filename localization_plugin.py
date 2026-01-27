import os
import re
import json
import time
import requests
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

GEOAPIFY_URL = "https://api.geoapify.com/v1/geocode/search"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"


# ---------- helpers ----------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _clean_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s

def _normalize_input(
    listing_json: Union[str, Dict[str, Any], List[Any]]
) -> Union[Dict[str, Any], List[Any]]:
    """
    Accepts:
      - raw JSON string (can contain true/false/null) -> json.loads
      - Python dict/list -> passthrough
    """
    if isinstance(listing_json, str):
        listing_json = listing_json.strip()
        return json.loads(listing_json)
    return listing_json

def _unwrap_singleton_lists(obj: Any) -> Any:
    """
    Handles cases like:
      [[{...}]] -> [{...}]
    Keeps unwrapping while it's a 1-item list.
    """
    while isinstance(obj, list) and len(obj) == 1:
        obj = obj[0]
    return obj

def _get_listing(obj: Union[Dict[str, Any], List[Any]]) -> Dict[str, Any]:
    """
    Accepts:
      - dict (single listing)
      - list of dicts
      - nested singleton lists
    Returns the first listing dict.
    """
    obj = _unwrap_singleton_lists(obj)

    if isinstance(obj, dict):
        return obj

    if isinstance(obj, list):
        if not obj:
            raise ValueError("Empty listing list provided.")
        if not isinstance(obj[0], dict):
            raise ValueError("Expected a list of listing dicts.")
        return obj[0]

    raise ValueError("Invalid input type for listing_json.")

def _extract_best_area_hint(listing: Dict[str, Any]) -> Optional[str]:
    """
    Heuristic neighborhood extractor (expand over time).
    """
    text = " ".join([
        listing.get("title", "") or "",
        listing.get("description", "") or ""
    ]).lower()

    if "santa rosa" in text:
        return "Santa Rosa"
    if "salamar" in text:
        return "El Salamar"

    return None

def build_destination_queries(listing: Dict[str, Any]) -> List[str]:
    """
    Builds multiple increasingly generic queries (best -> safe).
    """
    loc = listing.get("location") or {}
    municipio = _clean_text(loc.get("municipio_detectado", ""))
    depto = _clean_text(loc.get("departamento", ""))

    area_hint = _extract_best_area_hint(listing)

    title = _clean_text(listing.get("title", ""))
    title = title.split("|")[0].strip()

    queries = []

    if area_hint and municipio and depto:
        queries.append(f"{area_hint}, {municipio}, {depto}, El Salvador")

    if municipio and depto:
        queries.append(f"{municipio}, {depto}, El Salvador")

    if title and municipio and depto:
        queries.append(f"{title}, {municipio}, {depto}, El Salvador")

    if municipio:
        queries.append(f"{municipio}, El Salvador")
    if depto:
        queries.append(f"{depto}, El Salvador")

    # De-dupe preserving order
    seen = set()
    out = []
    for q in queries:
        q2 = _clean_text(q)
        if q2 and q2 not in seen:
            seen.add(q2)
            out.append(q2)
    return out


# ---------- geocoders ----------

def geocode_geoapify(query: str, api_key: str, country_code: str = "sv") -> Dict[str, Any]:
    params = {
        "text": query,
        "apiKey": api_key,
        "format": "json",
        "limit": 1,
        "filter": f"countrycode:{country_code}",
        "lang": "es",
    }
    r = requests.get(GEOAPIFY_URL, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    results = data.get("results") or []
    if not results:
        return {"ok": False, "provider": "geoapify", "query": query, "error": "No results", "raw": data}

    top = results[0]
    confidence = None
    rank = top.get("rank")
    if isinstance(rank, dict):
        confidence = rank.get("confidence")

    return {
        "ok": True,
        "provider": "geoapify",
        "query": query,
        "lat": top.get("lat"),
        "lon": top.get("lon"),
        "formatted": top.get("formatted"),
        "confidence": confidence,
        "raw": top,
    }

def geocode_nominatim(
    query: str,
    country_code: str = "sv",
    user_agent: Optional[str] = None,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Hardened Nominatim:
    - Accept-Language header
    - Better User-Agent (optionally include contact email)
    - Safe handling when response is HTML (403/429) instead of JSON
    """
    email = email or os.getenv("NOMINATIM_EMAIL")
    if not user_agent:
        user_agent = f"ListingGeocoderTest/1.0 ({email})" if email else "ListingGeocoderTest/1.0"

    headers = {
        "User-Agent": user_agent,
        "Accept-Language": "es,en;q=0.8",
    }
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": country_code,
        "addressdetails": 1,
    }

    try:
        r = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=20)
    except Exception as e:
        return {"ok": False, "provider": "nominatim", "query": query, "error": f"request_error: {e}"}

    if r.status_code != 200:
        return {
            "ok": False,
            "provider": "nominatim",
            "query": query,
            "error": f"http_{r.status_code}",
            "body_excerpt": (r.text or "")[:300],
        }

    try:
        data = r.json()
    except Exception as e:
        return {
            "ok": False,
            "provider": "nominatim",
            "query": query,
            "error": f"json_decode_error: {e}",
            "body_excerpt": (r.text or "")[:300],
        }

    if not data:
        return {"ok": False, "provider": "nominatim", "query": query, "error": "No results"}

    top = data[0]
    try:
        lat = float(top.get("lat"))
        lon = float(top.get("lon"))
    except Exception:
        return {"ok": False, "provider": "nominatim", "query": query, "error": "Invalid lat/lon", "raw": top}

    return {
        "ok": True,
        "provider": "nominatim",
        "query": query,
        "lat": lat,
        "lon": lon,
        "formatted": top.get("display_name"),
        "confidence": None,
        "raw": top,
    }


# ---------- main ----------

def estimate_location_from_listing(
    listing_json: Union[str, Dict[str, Any], List[Any]],
    provider: str = "nominatim",
    api_key: Optional[str] = None,
    country_code: str = "sv",
    throttle_seconds: float = 1.2,
) -> Dict[str, Any]:
    """
    Input:
      - raw JSON string (true/false/null) OR Python dict/list
    Output:
      estimate_location dict

    Changes requested:
      - tried_queries returned as "tags"
      - query returned as "best_query"
    """
    listing_json = _normalize_input(listing_json)
    listing = _get_listing(listing_json)

    if provider not in ("nominatim", "geoapify"):
        raise ValueError("provider must be 'nominatim' or 'geoapify'")

    if provider == "geoapify":
        api_key = api_key or os.getenv("GEOAPIFY_API_KEY")
        if not api_key:
            raise ValueError("Missing Geoapify key. Set GEOAPIFY_API_KEY or pass api_key=...")

    tried_queries: List[str] = []
    last_failure: Dict[str, Any] = {}

    for q in build_destination_queries(listing):
        tried_queries.append(q)

        if provider == "geoapify":
            res = geocode_geoapify(q, api_key=api_key, country_code=country_code)
        else:
            res = geocode_nominatim(q, country_code=country_code)

        if throttle_seconds and throttle_seconds > 0:
            time.sleep(throttle_seconds)

        if res.get("ok") and res.get("lat") is not None and res.get("lon") is not None:
            return {
                "lat": res["lat"],
                "lon": res["lon"],
                "formatted": res.get("formatted"),
                "provider": res.get("provider"),
                "best_query": res.get("query"),     # renamed
                "confidence": res.get("confidence"),
                "updated_at": _now_iso(),
                "tags": tried_queries,              # renamed
            }

        last_failure = res

    return {
        "provider": provider,
        "status": "failed",
        "updated_at": _now_iso(),
        "tags": tried_queries,  # renamed
        "best_query": tried_queries[-1] if tried_queries else None,  # renamed
        "error": last_failure.get("error", "No results"),
        "debug": {k: last_failure.get(k) for k in ["error", "body_excerpt"] if last_failure.get(k)},
    }


# ---------- example usage ----------

if __name__ == "__main__":
    listing_json_str = r'''
   [
  {
    "external_id": 30780235,
    "last_updated": "2026-01-23 17:41:36.076337+00",
    "title": "Alquilo Casa en Santa Rosa etapa 2 Tipo B | 3 Recamaras por 1625.00 en Santa Tecla",
    "price": 1625,
    "location": {
      "departamento": "La Libertad",
      "location_original": "Santa Tecla",
      "municipio_detectado": "Santa Tecla"
    },
    "published_date": "2026-01-03 00:00:00",
    "listing_type": "sale",
    "url": "https://www.encuentra24.com/el-salvador-es/bienes-raices-venta-de-propiedades-casas/alquilo-casa-en-santa-rosa-etapa-2-tipo-b/30780235",
    "specs": {
      "bedrooms": "3",
      "bathrooms": "2.5",
      "Área construida (m²)": "200"
    },
    "details": {
      "Publicado": "03/01/2026",
      "M² totales": "¡Pregunta al anunciante!",
      "Localización": "Santa Tecla",
      "Dirección exacta": "¡Pregunta al anunciante!",
      "Costos de mantenimiento": "¡Pregunta al anunciante!",
      "Precio/M² de construcción": "$8.12"
    },
    "description": "Alquilo Casa en Santa Rosa etapa 2 Tipo B\nárea de construcción 200 m2\nárea de terreno 247v2\n-Lobby\n-Sala Social\n-Comedor\n-Terraza extendida\n-Cocina\n-Lavandería\n-Bodega\n-Cuarto de servicio\n-Cochera para 2 vehículos techada\n-Jardín\n-Sala Familiar\n-1 habitación principal con walking clóset y baño con aire acondicionado\n-2 habitaciones Jr con baño compartido con aire acondicionado\nIncluye:\naire acondicionado en las habitaciones\ncalentador\nPrecio de alquiler $1,625 (mantenimiento incluido",
    "images": [
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_33be89",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_d206a2",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_cfeaca",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_679aaf",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_8da4b1",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_ec7fc6",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_59624f",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_5a83cc",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_084c22",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_ee1a9b",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_f06576",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_a011b7",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_840796",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_29d5bc",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_d03deb",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_abec60",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_13a8d9",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_d923cb",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_39c05c",
      "https://photos.encuentra24.com/t_or_fh_l/f_auto/v1/sv/30/78/02/35/30780235_f6809e"
    ],
    "source": "Encuentra24",
    "active": true,
    "contact_info": null
  }
]
    '''

    print(estimate_location_from_listing(listing_json_str, provider="nominatim"))
