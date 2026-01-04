# facility_recommendations.py
"""
Facility lookup helper - migrated from oldMedaidfiles/recommendations.py

- Google Places API integration with OpenStreetMap fallback
- Distance calculation and caching
- Returns list of nearby medical facilities
"""

import os
import json
import math
import time
import requests
from pathlib import Path
from django.conf import settings

# API keys from environment
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
MAPS_EMBED_KEY = os.getenv("MAPS_EMBED_KEY", "") or GOOGLE_PLACES_API_KEY

# Cache configuration
CACHE_DIR = Path(settings.BASE_DIR) / ".facility_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL = 60 * 60 * 6  # 6 hours

def _cache_get(key):
    """Get cached data if not expired"""
    path = CACHE_DIR / (key.replace("/", "_").replace(" ", "_") + ".json")
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf8"))
        if time.time() - data.get("_ts", 0) > CACHE_TTL:
            return None
        return data.get("value")
    except Exception:
        return None

def _cache_set(key, value):
    """Cache data with timestamp"""
    path = CACHE_DIR / (key.replace("/", "_").replace(" ", "_") + ".json")
    try:
        obj = {"_ts": time.time(), "value": value}
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf8")
    except Exception:
        pass

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
        _cache_set(cache_key, None)
        return None
    except Exception:
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
        out = []
        if data.get("status") in ("OK", "ZERO_RESULTS"):
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
        _cache_set(cache_key, out)
        return out
    except Exception:
        return []

# OpenStreetMap fallback methods
def _nominatim_geocode(address):
    """Geocode using OpenStreetMap Nominatim"""
    cache_key = f"geocode_nominatim_{address}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": address, "format": "json", "limit": 1}
    headers = {"User-Agent": "Medaid/1.0 (medaid@example.com)"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        if data:
            out = {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"]), "raw": data[0]}
            _cache_set(cache_key, out)
            return out
        _cache_set(cache_key, None)
        return None
    except Exception:
        return None

def _overpass_find_hospitals(lat, lng, radius_m=10000):
    """Find hospitals using OpenStreetMap Overpass API"""
    cache_key = f"overpass_{lat}_{lng}_{radius_m}"
    cached = _cache_get(cache_key)
    if cached:
        return cached
    
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="hospital"](around:{radius_m},{lat},{lng});
      way["amenity"="hospital"](around:{radius_m},{lat},{lng});
      node["healthcare"="clinic"](around:{radius_m},{lat},{lng});
      node["healthcare"="doctors"](around:{radius_m},{lat},{lng});
    );
    out center 20;
    """
    url = "https://overpass-api.de/api/interpreter"
    try:
        resp = requests.post(url, data=query, timeout=30)
        data = resp.json()
        out = []
        for el in data.get("elements", [])[:50]:
            if el.get("type") == "node":
                latp = el.get("lat")
                lngp = el.get("lon")
            else:
                c = el.get("center") or {}
                latp = c.get("lat")
                lngp = c.get("lon")
            
            tags = el.get("tags", {})
            name = tags.get("name") or tags.get("official_name") or "Hospital"
            
            addr_parts = []
            for k in ("addr:street", "addr:housenumber", "addr:city", "addr:postcode"):
                if tags.get(k):
                    addr_parts.append(tags.get(k))
            address = ", ".join(addr_parts) if addr_parts else (tags.get("operator") or "")
            
            maps_url = f"https://www.openstreetmap.org/?mlat={latp}&mlon={lngp}#map=16/{latp}/{lngp}"
            out.append({
                "name": name,
                "address": address,
                "lat": latp,
                "lng": lngp,
                "maps_url": maps_url,
                "phone": tags.get("phone", "")
            })
        _cache_set(cache_key, out)
        return out
    except Exception:
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
        if "," in str(location):
            parts = location.split(",")
            user_lat = float(parts[0].strip())
            user_lng = float(parts[1].strip())
        else:
            # Geocode the location
            coords = _google_geocode(location) or _nominatim_geocode(location)
            if not coords:
                return []
            user_lat = coords["lat"]
            user_lng = coords["lng"]
    except Exception:
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

def get_dietary_recommendations(risk_level, possible_conditions=None):
    """
    Get dietary recommendations based on risk level and conditions
    
    Args:
        risk_level: Patient risk level
        possible_conditions: List of possible medical conditions
    
    Returns:
        List of dietary recommendation strings
    """
    recommendations = []
    
    # General recommendations by risk level
    if risk_level in ["emergency", "high"]:
        recommendations.append("Focus on easily digestible foods and stay well-hydrated")
        recommendations.append("Avoid heavy, spicy, or greasy foods until symptoms improve")
        recommendations.append("Small, frequent meals are better than large meals")
    
    # Condition-specific recommendations
    if possible_conditions:
        conditions_lower = [c.lower() if isinstance(c, str) else "" for c in possible_conditions]
        
        if any("diabetes" in c or "blood sugar" in c for c in conditions_lower):
            recommendations.extend([
                "Monitor carbohydrate intake - focus on complex carbs",
                "Avoid sugary drinks and processed foods",
                "Include fiber-rich foods like vegetables and whole grains"
            ])
        
        if any("hypertension" in c or "blood pressure" in c for c in conditions_lower):
            recommendations.extend([
                "Reduce sodium intake - avoid processed and packaged foods",
                "Include potassium-rich foods like bananas and leafy greens",
                "Limit caffeine and alcohol consumption"
            ])
        
        if any("gastro" in c or "stomach" in c or "digestive" in c for c in conditions_lower):
            recommendations.extend([
                "Eat bland, easy-to-digest foods (BRAT diet: bananas, rice, applesauce, toast)",
                "Avoid dairy, caffeine, and fatty foods temporarily",
                "Stay hydrated with clear fluids"
            ])
    
    # Default recommendations if none added
    if not recommendations:
        recommendations.extend([
            "Maintain a balanced diet with fruits, vegetables, and whole grains",
            "Stay well-hydrated - drink 8-10 glasses of water daily",
            "Limit processed foods, excess sugar, and saturated fats"
        ])
    
    return recommendations
