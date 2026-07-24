# facility_recommendations.py
"""
Facility lookup helper - migrated from oldMedaidfiles/recommendations.py

- Google Places API integration with OpenStreetMap fallback
- Distance calculation and caching
- Returns list of nearby medical facilities
"""

import logging
import os
import json
import math
import time
import re
import requests
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

# API keys from environment
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
MAPS_EMBED_KEY = os.getenv("MAPS_EMBED_KEY", "") or GOOGLE_PLACES_API_KEY

# Cache configuration
CACHE_DIR = Path(settings.BASE_DIR) / ".facility_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 60 * 60 * 6  # 6 hours for a SUCCESSFUL lookup
# A FAILED upstream lookup is cached only briefly so a transient outage (e.g.
# an Overpass 504/406) self-heals within minutes instead of pinning an empty
# result for the full 6 hours. This is the cache-poisoning fix: previously a
# total failure wrote [] with the 6h TTL, so one bad minute blanked facilities
# for hours even after the upstream recovered.
FAILURE_CACHE_TTL = 60 * 5  # 5 minutes

# Overpass mirror-chain limits. Per-mirror HTTP timeout is a ceiling; the
# wall-clock budget caps the WHOLE chain so 4 mirrors can't block a waiting
# patient for 4 x 25s. Each request's effective timeout is shrunk to whatever
# budget remains, so the last mirror never overshoots the total.
OVERPASS_HTTP_TIMEOUT_S = 25
OVERPASS_TOTAL_BUDGET_S = 18

def _cache_get(key):
    """Get cached data if not expired. Honours a per-entry TTL so failure
    entries (short TTL) expire well before successful ones (6h)."""
    path = CACHE_DIR / (key.replace("/", "_").replace(" ", "_") + ".json")
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf8"))
        ttl = data.get("_ttl", CACHE_TTL)  # legacy entries predate _ttl
        if time.time() - data.get("_ts", 0) > ttl:
            return None
        return data.get("value")
    except Exception as e:
        logger.warning("facility.cache_read_failed", extra={"key": key, "error_type": type(e).__name__})
        return None

def _cache_set(key, value, ttl=CACHE_TTL):
    """Cache data with timestamp and an explicit TTL (default 6h). Pass
    FAILURE_CACHE_TTL for a failed/degraded lookup so it self-heals quickly."""
    path = CACHE_DIR / (key.replace("/", "_").replace(" ", "_") + ".json")
    try:
        obj = {"_ts": time.time(), "_ttl": ttl, "value": value}
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf8")
    except Exception as e:
        logger.warning("facility.cache_write_failed", extra={"key": key, "error_type": type(e).__name__})

def _haversine_km(lat1, lon1, lat2, lon2):
    """Calculate distance in km using Haversine formula"""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(d_lam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

# Google Places API methods
def _google_geocode(address):
    """Geocode address using Google Maps API"""
    if not GOOGLE_PLACES_API_KEY:
        return None
    cache_key = f"geocode_google_{address}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_PLACES_API_KEY}
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        if data.get("status") == "OK" and data.get("results"):
            loc = data["results"][0]["geometry"]["location"]
            out = {"lat": loc["lat"], "lng": loc["lng"], "raw": data["results"][0]}
            _cache_set(cache_key, out)
            return out
        # A well-formed "no result" (ZERO_RESULTS etc.) is a real negative,
        # cached normally. A non-OK status is an upstream problem worth seeing.
        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            logger.warning("facility.google_geocode_non_ok", extra={"status": data.get("status")})
        _cache_set(cache_key, None)
        return None
    except Exception as e:
        # Transient error: do NOT cache, so the next request retries.
        logger.warning("facility.google_geocode_failed", extra={"error_type": type(e).__name__})
        return None

def _google_places_nearby(lat, lng, radius=10000, place_type="hospital"):
    """Find nearby places using Google Places API"""
    if not GOOGLE_PLACES_API_KEY:
        return []
    cache_key = f"places_google_{lat}_{lng}_{radius}_{place_type}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached
    
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": radius,
        "type": place_type,
        "key": GOOGLE_PLACES_API_KEY
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        status_value = data.get("status")
        if status_value not in ("OK", "ZERO_RESULTS"):
            # An error status (OVER_QUERY_LIMIT, REQUEST_DENIED, ...) is a
            # failure, not "zero facilities". Cache briefly so it self-heals,
            # never for the full 6h.
            logger.warning("facility.google_places_non_ok", extra={"status": status_value})
            _cache_set(cache_key, [], ttl=FAILURE_CACHE_TTL)
            return []
        out = []
        for p in data.get("results", [])[:20]:
            loc = p.get("geometry", {}).get("location", {})
            item = {
                "name": p.get("name"),
                "address": p.get("vicinity") or p.get("formatted_address") or "",
                "rating": p.get("rating"),
                "lat": loc.get("lat"),
                "lng": loc.get("lng"),
                "place_id": p.get("place_id"),
                "maps_url": f"https://www.google.com/maps/place/?q=place_id:{p.get('place_id')}",
                "phone": p.get("formatted_phone_number", "")
            }
            out.append(item)
        # Genuine success (possibly a real empty result) - cache for the full TTL.
        _cache_set(cache_key, out)
        return out
    except Exception as e:
        logger.warning("facility.google_places_failed", extra={"error_type": type(e).__name__})
        return []

# OpenStreetMap fallback methods
def _nominatim_geocode(address):
    """Geocode using OpenStreetMap Nominatim"""
    cache_key = f"geocode_nominatim_{address}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    
    url = "https://nominatim.openstreetmap.org/search"
    query = str(address or "").strip()
    pincode_match = re.search(r'\b(\d{6})\b', query)
    if pincode_match:
        query = f"{pincode_match.group(1)}, India"
    elif query.isdigit():
        query = f"{query}, India"
    params = {
        "q": query,
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
    }
    headers = {"User-Agent": "MedAid-HealthApp/1.0", "Accept-Language": "en"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        if data:
            out = {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"]), "raw": data[0]}
            _cache_set(cache_key, out)
            return out
        # Genuine "no match" from a 200 response - a real negative, cached normally.
        _cache_set(cache_key, None)
        return None
    except Exception as e:
        # Transient error: do NOT cache, so the next request retries.
        logger.warning("facility.nominatim_geocode_failed", extra={"error_type": type(e).__name__})
        return None

def _overpass_find_hospitals(lat, lng, radius_m=10000):
    """Find hospitals using OpenStreetMap Overpass API"""
    cache_key = f"overpass_{lat}_{lng}_{radius_m}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    query = f"""
    [out:json][timeout:20];
    (
      nwr["amenity"~"hospital|clinic|doctors"](around:{radius_m},{lat},{lng});
      nwr["healthcare"~"hospital|clinic|doctor|doctors"](around:{radius_m},{lat},{lng});
    );
    out center tags;
    """
    # Mirrors ordered by MEASURED reliability (direct probe, all four, both
    # request formats): overpass-api.de, lz4 and maps.mail.ru each returned 200
    # with the raw body; kumi.systems was timing out, so it is demoted to a
    # last-resort long-shot the wall-clock budget will usually skip.
    overpass_urls = [
        "https://overpass-api.de/api/interpreter",
        "https://lz4.overpass-api.de/api/interpreter",
        "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
        "https://overpass.kumi.systems/api/interpreter",
    ]
    headers = {
        "User-Agent": "Medaid/1.0 (medaid@example.com)",
        "Accept": "application/json",
    }

    # Wall-clock budget for the WHOLE chain (see OVERPASS_TOTAL_BUDGET_S).
    deadline = time.monotonic() + OVERPASS_TOTAL_BUDGET_S

    any_mirror_errored = False
    for url in overpass_urls:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            # Budget spent - stop even though mirrors remain untried, so a
            # patient never waits on the full 4 x per-mirror timeout.
            any_mirror_errored = True
            logger.warning(
                "facility.overpass_budget_exhausted",
                extra={"budget_s": OVERPASS_TOTAL_BUDGET_S},
            )
            break
        # Per-mirror HTTP ceiling, shrunk to the remaining budget so the last
        # attempt can't overshoot the total.
        req_timeout = min(OVERPASS_HTTP_TIMEOUT_S, remaining)
        try:
            resp = requests.post(
                url,
                # Raw request body. NOTE: a form-param body (data={"data": query})
                # was measured to make overpass-api.de and lz4 return 504 - the
                # raw body returns 200 on all working mirrors, so it stays.
                data=query,
                timeout=req_timeout,
                headers=headers,
            )
            if resp.status_code != 200:
                # Surface WHICH mirror failed and HOW (the 504/406 we saw were
                # invisible before). Try the next mirror.
                any_mirror_errored = True
                logger.warning(
                    "facility.overpass_mirror_non_200",
                    extra={"mirror": url, "status_code": resp.status_code},
                )
                continue

            data = resp.json()
            out = []
            seen = set()

            for el in data.get("elements", [])[:100]:
                if el.get("type") == "node":
                    latp = el.get("lat")
                    lngp = el.get("lon")
                else:
                    c = el.get("center") or {}
                    latp = c.get("lat")
                    lngp = c.get("lon")

                if latp is None or lngp is None:
                    continue

                tags = el.get("tags", {})
                name = tags.get("name") or tags.get("official_name") or tags.get("operator") or "Medical Facility"

                key = (name, round(float(latp), 5), round(float(lngp), 5))
                if key in seen:
                    continue
                seen.add(key)

                addr_parts = []
                for k in ("addr:housenumber", "addr:street", "addr:suburb", "addr:city", "addr:postcode"):
                    if tags.get(k):
                        addr_parts.append(tags.get(k))
                address = ", ".join(addr_parts) if addr_parts else (tags.get("operator") or "")

                maps_url = f"https://www.openstreetmap.org/?mlat={latp}&mlon={lngp}#map=16/{latp}/{lngp}"
                out.append({
                    "name": name,
                    "address": address,
                    "lat": latp,
                    "lng": lngp,
                    "latitude": latp,
                    "longitude": lngp,
                    "maps_url": maps_url,
                    "phone": tags.get("phone") or tags.get("contact:phone") or ""
                })

            # Successful 200 response. `out` may legitimately be empty (no
            # facilities in range) - that is a real negative, cached for the
            # full TTL.
            _cache_set(cache_key, out)
            return out
        except Exception as e:
            any_mirror_errored = True
            logger.warning(
                "facility.overpass_mirror_failed",
                extra={"mirror": url, "error_type": type(e).__name__},
            )
            continue

    # Every mirror failed. This is the cache-poisoning fix: previously this
    # wrote [] with the 6h TTL, so a transient outage blanked facilities for
    # hours. Cache the empty result only briefly (or, if somehow no mirror was
    # even attempted, not at all) so it self-heals once Overpass recovers.
    logger.warning("facility.overpass_all_mirrors_failed", extra={"mirror_count": len(overpass_urls)})
    if any_mirror_errored:
        _cache_set(cache_key, [], ttl=FAILURE_CACHE_TTL)
    return []

def get_nearby_facilities(location, risk_level="medium", radius_km=10):
    """
    Main function to get nearby medical facilities
    
    Args:
        location: City name, pincode, or "lat,lng" string
        risk_level: Patient risk level (affects search radius)
        radius_km: Search radius in kilometers
    
    Returns:
        List of facility dictionaries with name, address, distance, etc.
    """
    # Adjust radius based on risk
    if risk_level == "emergency" or risk_level == "high":
        radius_km = min(radius_km, 5)  # Closer facilities for urgent cases
    
    radius_m = radius_km * 1000
    
    # Try to parse as coordinates first
    try:
        location_text = str(location or "").strip()
        parsed_as_coords = False

        if "," in location_text:
            parts = [p.strip() for p in location_text.split(",")]
            if len(parts) == 2:
                try:
                    cand_lat = float(parts[0])
                    cand_lng = float(parts[1])
                    if -90 <= cand_lat <= 90 and -180 <= cand_lng <= 180:
                        user_lat = cand_lat
                        user_lng = cand_lng
                        parsed_as_coords = True
                except ValueError:
                    parsed_as_coords = False

        if not parsed_as_coords:
            # Geocode city/address/pincode text
            coords = _google_geocode(location_text) or _nominatim_geocode(location_text)
            if not coords:
                logger.warning("facility.geocode_no_result", extra={"location": location_text[:80]})
                return []
            user_lat = coords["lat"]
            user_lng = coords["lng"]
    except Exception as e:
        logger.warning(
            "facility.lookup_failed",
            extra={"location": str(location)[:80], "error_type": type(e).__name__},
        )
        return []
    
    # Try Google Places first, fall back to OSM
    facilities = _google_places_nearby(user_lat, user_lng, radius_m)
    if not facilities:
        facilities = _overpass_find_hospitals(user_lat, user_lng, radius_m)
    
    # Calculate distances and sort
    for facility in facilities:
        if facility.get("lat") and facility.get("lng"):
            distance = _haversine_km(user_lat, user_lng, facility["lat"], facility["lng"])
            facility["distance_km"] = round(distance, 2)
    
    # Sort by distance
    facilities.sort(key=lambda x: x.get("distance_km", 999))
    
    return facilities[:10]  # Return top 10 closest
