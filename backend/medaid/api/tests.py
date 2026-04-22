import pytest
from unittest.mock import patch, MagicMock
from api.triage_engine_v2 import TriageEngineV2
from api.hospital_finder import HospitalFinder
from api.models import User, UserProfile

@pytest.fixture
def triage_engine():
    return TriageEngineV2()

@pytest.fixture
def hospital_finder():
    return HospitalFinder()

@pytest.fixture
def mock_user_data():
    return {
        "age": 45,
        "gender": "Male",
        "past_history": ["Hypertension"]
    }

@pytest.mark.django_db
def test_triage_branching_contradictory_data(triage_engine, mock_user_data):
    """
    Test how the triage engine handles contradictory symptoms in user descriptions.
    We check if both contradictory concepts appear in the final generated prompt.
    """
    symptoms = "I am experiencing severe chest pain but I feel absolutely fine and have no pain."
    prompt = triage_engine._build_assessment_prompt(symptoms, mock_user_data, "", "")
    
    assert "severe chest pain" in prompt
    assert "absolutely fine" in prompt

@pytest.mark.django_db
@patch('api.hospital_finder.requests.get')
def test_hospital_routing_ocean_coordinates(mock_get, hospital_finder):
    """
    Test routing when geocoding fails or returns an ocean coordinate.
    The finder should fallback to static databases.
    """
    # Mock finding nothing from Nominatim
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = []
    mock_get.return_value = mock_response

    hospitals = hospital_finder.find_nearby_hospitals(location="Middle of Atlantic Ocean")
    
    # Should fallback to Mumbai due to default fallback logic when name matching fails
    assert len(hospitals) > 0
    assert hospitals[0].name == 'Lilavati Hospital'

@pytest.mark.django_db
def test_hospital_routing_invalid_pincode(hospital_finder):
    """
    Test routing with an invalid pincode to ensure error handling falls back gracefully.
    """
    hospitals = hospital_finder.find_nearby_hospitals(location="000000")
    
    # 000 prefix is not in pincode_to_city, so it defaults to Mumbai
    assert len(hospitals) > 0
    assert hospitals[0].name == 'Lilavati Hospital'
