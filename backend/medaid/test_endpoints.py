import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000/api"

def print_result(name, passed, details=""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"{status} - {name}")
    if not passed and details:
        print(f"   Details: {details}")

def login():
    # Helper to get token if needed, but the views might be protected
    # Checking views.py: assess_symptoms uses @permission_classes([IsAuthenticated])?
    # Let's check views.py content from memory or view it.
    # Most likely yes.
    # Let's try to login as the user 'shiva' (email from previous context?) or create a temp user.
    # For now, let's try to hit endpoints. If 401, we know we need auth.
    pass

def test_triage_formatting():
    # Logic: We need an authenticated user. 
    # Let's assume we can use a test token or just create a user on the fly?
    # We can use the existing 'login' endpoint.
    
    # 1. Login/Signup
    email = "test_auto@example.com"
    password = "SafePassword123!"
    
    # Try login first
    resp = requests.post(f"{BASE_URL}/auth/login/", json={"email": email, "password": password})
    if resp.status_code != 200:
        # Try signup
        resp = requests.post(f"{BASE_URL}/auth/signup/", json={
            "full_name": "Test User",
            "email": email,
            "password": password,
            "confirm_password": password,
            "age": 30,
            "gender": "Male"
        })
    
    if resp.status_code not in [200, 201]:
        print_result("Authentication", False, f"Could not login or signup: {resp.text}")
        return
        
    token = resp.json().get('access')
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Test Triage (Symptoms: Fever)
    print("\nTesting Triage Assessment (Symptoms: 'Fever, headache')...")
    payload = {
        "current_symptoms": "I have high fever and headache for 2 days",
        "past_history": [],
        "age": 30
    }
    
    try:
        triage_resp = requests.post(f"{BASE_URL}/triage/assess/", json=payload, headers=headers)
        if triage_resp.status_code in [200, 201]:
            data = triage_resp.json()
            conditions = data.get("possible_conditions", [])
            
            # Check if conditions have probability
            has_prob = False
            if conditions and len(conditions) > 0:
                first = conditions[0]
                # Expecting objects with 'disease_name' that contains '%'
                # Logic in triage_engine.py: formatted_conditions.append({"disease_name": label})
                
                # Check structure
                if isinstance(first, dict):
                    d_name = first.get("disease_name", "")
                    if "%" in d_name:
                        has_prob = True
                    else:
                         print(f"   Structure match but no '%': {d_name}")
                elif isinstance(first, str):
                    if "%" in first:
                        has_prob = True
            
            print_result("Triage Output Format", has_prob, f"Response: {json.dumps(conditions)}")
            print_result("Triage Risk Level", "risk_level" in data, f"Risk: {data.get('risk_level')}")
        else:
            print_result("Triage API Call", False, f"Status: {triage_resp.status_code}, Body: {triage_resp.text}")
    except Exception as e:
        print_result("Triage API Exception", False, str(e))

    # 3. Test Nearby Facilities
    print("\nTesting Nearby Facilities (Location: 'Pune')...")
    try:
        # Note: endpoint is get_nearby_facilities_view at /facilities/nearby/
        fac_resp = requests.get(f"{BASE_URL}/facilities/nearby/?location=Pune&risk_level=medium", headers=headers)
        if fac_resp.status_code == 200:
            fac_data = fac_resp.json()
            facilities = fac_data.get('facilities', [])
            has_items = len(facilities) > 0
            is_valid = False
            if has_items:
                # Check for keys: name, address, distance_km
                f = facilities[0]
                if "name" in f and "distance_km" in f:
                    is_valid = True
            
            print_result("Nearby Facilities", has_items and is_valid, f"Count: {len(facilities)}, Sample: {facilities[0] if has_items else 'None'}")
        else:
             print_result("Facilities API Call", False, f"Status: {fac_resp.status_code}, Body: {fac_resp.text}")
    except Exception as e:
         print_result("Facilities API Exception", False, str(e))

if __name__ == "__main__":
    try:
        test_triage_formatting()
    except Exception as e:
        print(f"Test script error: {e}")
