"""
Hospital Finder - Find nearby medical facilities
Uses FREE OpenStreetMap APIs (Nominatim + Overpass)
100% Free and Open Source - No API keys needed!
"""

import os
import requests
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from math import radians, sin, cos, sqrt, atan2


@dataclass
class Hospital:
    """Hospital/Medical Facility data structure"""
    name: str
    address: str
    distance: str
    rating: Optional[float] = None
    phone: Optional[str] = None
    is_open: Optional[bool] = None
    place_id: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    
    def get_google_maps_url(self) -> str:
        """Get Google Maps URL for directions"""
        if self.lat and self.lng:
            return f"https://www.google.com/maps/search/?api=1&query={self.lat},{self.lng}"
        else:
            # Fallback to search by name
            search_query = self.name.replace(' ', '+')
            return f"https://www.google.com/maps/search/?api=1&query={search_query}"


class HospitalFinder:
    """Find nearby hospitals using FREE OpenStreetMap APIs"""
    
    def __init__(self):
        # OpenStreetMap APIs - 100% FREE!
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"
        self.overpass_url = "https://overpass-api.de/api/interpreter"
        
        # User agent for Nominatim (required by their usage policy)
        self.headers = {
            'User-Agent': 'MedAid-HealthApp/1.0 (Medical Triage Application)'
        }
        
        print("✅ OpenStreetMap APIs initialized (100% FREE!)")
    
    def find_nearby_hospitals(
        self,
        location: str,
        risk_level: str = "medium",
        radius: int = 5000,
        max_results: int = 5
    ) -> List[Hospital]:
        """
        Find nearby hospitals using FREE OpenStreetMap
        
        Args:
            location: City name, pincode, or address
            risk_level: emergency/high/medium/low
            radius: Search radius in meters
            max_results: Maximum number of results
            
        Returns:
            List of Hospital objects
        """
        try:
            # Step 1: Geocode location using Nominatim (FREE!)
            lat, lng = self._geocode_location(location)
            
            if not lat or not lng:
                print(f"⚠️ Could not geocode location: {location}, using fallback")
                return self._get_fallback_hospitals(location, max_results)
            
            # Step 2: Find nearby hospitals using Overpass API (FREE!)
            hospitals = self._find_with_overpass(lat, lng, radius, max_results)
            
            if hospitals:
                return hospitals
            else:
                print(f"⚠️ No hospitals found via OpenStreetMap, using fallback")
                return self._get_fallback_hospitals(location, max_results)
                
        except Exception as e:
            print(f"⚠️ Error finding hospitals: {e}, using fallback")
            return self._get_fallback_hospitals(location, max_results)
    
    def _geocode_location(self, location: str) -> tuple:
        """Geocode location using Nominatim (FREE!)"""
        try:
            # Add country bias for India
            params = {
                'q': location,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'in'  # Bias towards India
            }
            
            response = requests.get(
                self.nominatim_url,
                params=params,
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data and len(data) > 0:
                    lat = float(data[0]['lat'])
                    lng = float(data[0]['lon'])
                    print(f"✅ Geocoded {location} to ({lat}, {lng})")
                    return lat, lng
            
            return None, None
            
        except Exception as e:
            print(f"⚠️ Geocoding error: {e}")
            return None, None
    
    def _reverse_geocode(self, lat: float, lng: float) -> str:
        """Reverse geocode coordinates to address (FREE!)"""
        try:
            # Nominatim reverse geocoding
            reverse_url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': lat,
                'lon': lng,
                'format': 'json',
                'zoom': 18  # Street level detail
            }
            
            response = requests.get(
                reverse_url,
                params=params,
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                address_data = data.get('address', {})
                
                # Build address from components
                parts = []
                if address_data.get('road'):
                    parts.append(address_data['road'])
                if address_data.get('suburb') or address_data.get('neighbourhood'):
                    parts.append(address_data.get('suburb') or address_data.get('neighbourhood'))
                if address_data.get('city') or address_data.get('town') or address_data.get('village'):
                    parts.append(address_data.get('city') or address_data.get('town') or address_data.get('village'))
                if address_data.get('postcode'):
                    parts.append(address_data['postcode'])
                
                if parts:
                    return ', '.join(parts)
            
            return None
            
        except Exception as e:
            print(f"⚠️ Reverse geocoding error: {e}")
            return None
    
    def _find_with_overpass(
        self,
        lat: float,
        lng: float,
        radius: int,
        max_results: int
    ) -> List[Hospital]:
        """Find hospitals using Overpass API (FREE!)"""
        try:
            # Overpass QL query to find hospitals, clinics, and doctors
            query = f"""
            [out:json][timeout:10];
            (
              node["amenity"="hospital"](around:{radius},{lat},{lng});
              node["amenity"="clinic"](around:{radius},{lat},{lng});
              node["amenity"="doctors"](around:{radius},{lat},{lng});
              way["amenity"="hospital"](around:{radius},{lat},{lng});
              way["amenity"="clinic"](around:{radius},{lat},{lng});
            );
            out body;
            >;
            out skel qt;
            """
            
            response = requests.post(
                self.overpass_url,
                data=query,
                headers=self.headers,
                timeout=15
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            elements = data.get('elements', [])
            
            # Process results
            hospitals = []
            seen_names = set()  # Avoid duplicates
            
            for element in elements:
                if element.get('type') not in ['node', 'way']:
                    continue
                
                tags = element.get('tags', {})
                name = tags.get('name', tags.get('operator', 'Medical Facility'))
                
                # Skip duplicates
                if name in seen_names:
                    continue
                seen_names.add(name)
                
                # Get coordinates
                if element.get('type') == 'node':
                    elem_lat = element.get('lat')
                    elem_lng = element.get('lon')
                elif element.get('type') == 'way':
                    # For ways, use center point (approximate)
                    elem_lat = element.get('center', {}).get('lat')
                    elem_lng = element.get('center', {}).get('lon')
                else:
                    continue
                
                if not elem_lat or not elem_lng:
                    continue
                
                # Calculate distance
                distance_km = self._calculate_distance(lat, lng, elem_lat, elem_lng)
                
                # Build address - Enhanced with multiple fallbacks
                address_parts = []
                
                # Try structured address first
                if tags.get('addr:street'):
                    address_parts.append(tags.get('addr:street'))
                if tags.get('addr:suburb') or tags.get('addr:neighbourhood'):
                    address_parts.append(tags.get('addr:suburb') or tags.get('addr:neighbourhood'))
                if tags.get('addr:city'):
                    address_parts.append(tags.get('addr:city'))
                if tags.get('addr:postcode'):
                    address_parts.append(tags.get('addr:postcode'))
                
                # If no structured address, try reverse geocoding
                if not address_parts and elem_lat and elem_lng:
                    reverse_address = self._reverse_geocode(elem_lat, elem_lng)
                    if reverse_address:
                        address = reverse_address
                    else:
                        address = f"Near {location}"  # Fallback to search location
                else:
                    address = ', '.join(address_parts) if address_parts else f"Near {location}"
                
                # Create hospital object
                hospital = Hospital(
                    name=name,
                    address=address,
                    distance=f"{distance_km:.1f} km",
                    phone=tags.get('phone', tags.get('contact:phone')),
                    lat=elem_lat,
                    lng=elem_lng,
                    place_id=str(element.get('id'))
                )
                
                hospitals.append(hospital)
                
                if len(hospitals) >= max_results:
                    break
            
            # Sort by distance
            hospitals.sort(key=lambda h: float(h.distance.replace(' km', '')))
            
            print(f"✅ Found {len(hospitals)} hospitals via OpenStreetMap")
            return hospitals[:max_results]
            
        except Exception as e:
            print(f"⚠️ Overpass API error: {e}")
            return []
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points in km"""
        R = 6371  # Earth's radius in km
        
        lat1, lng1, lat2, lng2 = map(radians, [lat1, lng1, lat2, lng2])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlng/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return R * c
    
    def _get_fallback_hospitals(self, location: str, max_results: int) -> List[Hospital]:
        """Fallback: Static database for major Indian cities"""
        
        # Pincode to city mapping
        pincode_to_city = {
            '400': 'mumbai', '110': 'delhi', '560': 'bangalore',
            '411': 'pune', '412': 'pune', '600': 'chennai', '500': 'hyderabad',
        }
        
        # Static database
        static_hospitals = {
            'mumbai': [
                Hospital('Lilavati Hospital', 'Bandra West, Mumbai, 400050', '2.3 km', 4.5, '+91 22 2640 5000'),
                Hospital('Breach Candy Hospital', 'Bhulabhai Desai Rd, Mumbai, 400026', '3.1 km', 4.4, '+91 22 2367 1888'),
                Hospital('Jaslok Hospital', 'Dr. G Deshmukh Marg, Mumbai, 400026', '3.5 km', 4.3, '+91 22 6657 3333'),
                Hospital('Hinduja Hospital', 'Mahim, Mumbai, 400016', '4.2 km', 4.6, '+91 22 2444 9199'),
                Hospital('Kokilaben Hospital', 'Four Bungalows, Mumbai, 400053', '5.1 km', 4.7, '+91 22 4269 6969'),
            ],
            'delhi': [
                Hospital('AIIMS Delhi', 'Ansari Nagar, New Delhi, 110029', '2.5 km', 4.6, '+91 11 2658 8500'),
                Hospital('Max Hospital', 'Saket, New Delhi, 110017', '3.2 km', 4.5, '+91 11 2651 5050'),
                Hospital('Fortis Hospital', 'Vasant Kunj, New Delhi, 110070', '4.1 km', 4.4, '+91 11 4277 6222'),
                Hospital('Apollo Hospital', 'Sarita Vihar, New Delhi, 110076', '5.0 km', 4.5, '+91 11 2692 5858'),
                Hospital('Sir Ganga Ram Hospital', 'Rajinder Nagar, New Delhi, 110060', '3.8 km', 4.6, '+91 11 2575 0000'),
            ],
            'bangalore': [
                Hospital('Manipal Hospital', 'HAL Airport Road, Bangalore, 560017', '2.8 km', 4.5, '+91 80 2502 4444'),
                Hospital('Fortis Hospital', 'Bannerghatta Road, Bangalore, 560076', '3.5 km', 4.4, '+91 80 6621 4444'),
                Hospital('Apollo Hospital', 'Bannerghatta Road, Bangalore, 560076', '3.6 km', 4.5, '+91 80 2630 0100'),
                Hospital('Columbia Asia Hospital', 'Hebbal, Bangalore, 560024', '4.2 km', 4.3, '+91 80 6614 6614'),
                Hospital('Narayana Health City', 'Bommasandra, Bangalore, 560099', '8.5 km', 4.6, '+91 80 7122 2222'),
            ],
            'pune': [
                Hospital('Ruby Hall Clinic', '40, Sassoon Road, Pune, 411001', '2.1 km', 4.5, '+91 20 2626 1111'),
                Hospital('Sahyadri Hospital', 'Erandwane, Pune, 411004', '3.2 km', 4.4, '+91 20 6720 3000'),
                Hospital('Deenanath Mangeshkar Hospital', 'Erandwane, Pune, 411004', '3.4 km', 4.5, '+91 20 2416 2000'),
                Hospital('KEM Hospital', 'Rasta Peth, Pune, 411011', '2.8 km', 4.3, '+91 20 2612 5000'),
                Hospital('Jehangir Hospital', 'Sassoon Road, Pune, 411001', '2.3 km', 4.4, '+91 20 2605 5000'),
            ],
            'chennai': [
                Hospital('Apollo Hospital', 'Greams Lane, Chennai, 600006', '2.5 km', 4.6, '+91 44 2829 3333'),
                Hospital('Fortis Malar Hospital', 'Adyar, Chennai, 600020', '3.8 km', 4.4, '+91 44 4289 8900'),
                Hospital('MIOT International', 'Mount Poonamallee Road, Chennai, 600089', '5.2 km', 4.5, '+91 44 4200 2288'),
                Hospital('Kauvery Hospital', 'Alwarpet, Chennai, 600018', '3.1 km', 4.3, '+91 44 4000 6000'),
                Hospital('Vijaya Hospital', 'Vadapalani, Chennai, 600026', '4.5 km', 4.4, '+91 44 2361 2727'),
            ],
            'hyderabad': [
                Hospital('Apollo Hospital', 'Jubilee Hills, Hyderabad, 500033', '3.2 km', 4.5, '+91 40 2360 7777'),
                Hospital('KIMS Hospital', 'Secunderabad, 500003', '4.1 km', 4.4, '+91 40 4488 8888'),
                Hospital('Yashoda Hospital', 'Somajiguda, Hyderabad, 500082', '2.9 km', 4.5, '+91 40 2344 0000'),
                Hospital('Care Hospital', 'Banjara Hills, Hyderabad, 500034', '3.5 km', 4.3, '+91 40 6165 6565'),
                Hospital('Continental Hospital', 'IT & Financial District, Hyderabad, 500032', '6.8 km', 4.6, '+91 40 6767 6767'),
            ]
        }
        
        # Match city name
        location_lower = location.lower().strip()
        for city, hospitals in static_hospitals.items():
            if city in location_lower:
                print(f"✅ Using fallback hospitals for: {city}")
                return hospitals[:max_results]
        
        # Match pincode
        if location.strip().isdigit() and len(location.strip()) >= 3:
            pincode_prefix = location.strip()[:3]
            if pincode_prefix in pincode_to_city:
                city = pincode_to_city[pincode_prefix]
                print(f"✅ Using fallback hospitals for pincode {location} → {city}")
                return static_hospitals[city][:max_results]
        
        # Extract pincode from text
        import re
        pincode_match = re.search(r'\b(\d{6})\b', location)
        if pincode_match:
            pincode_prefix = pincode_match.group(1)[:3]
            if pincode_prefix in pincode_to_city:
                city = pincode_to_city[pincode_prefix]
                print(f"✅ Using fallback hospitals for extracted pincode → {city}")
                return static_hospitals[city][:max_results]
        
        # Default to Mumbai
        print(f"⚠️ No match for {location}, using Mumbai fallback")
        return static_hospitals['mumbai'][:max_results]


# Singleton instance
_hospital_finder = None

def get_hospital_finder() -> HospitalFinder:
    """Get singleton instance of hospital finder"""
    global _hospital_finder
    if _hospital_finder is None:
        _hospital_finder = HospitalFinder()
    return _hospital_finder
