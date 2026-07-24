from django.test import TestCase
from unittest.mock import patch, MagicMock
from api.triage_engine_v2 import TriageEngineV2
from api.hospital_finder import HospitalFinder


class TriageAndHospitalRoutingTests(TestCase):
    def setUp(self):
        self.triage_engine = TriageEngineV2()
        self.hospital_finder = HospitalFinder()
        self.mock_user_data = {
            "age": 45,
            "gender": "Male",
            "past_history": ["Hypertension"],
        }

    def test_triage_branching_contradictory_data(self):
        """
        Test how the triage engine handles contradictory symptoms in user descriptions.
        We check if both contradictory concepts appear in the final generated prompt.
        """
        symptoms = "I am experiencing severe chest pain but I feel absolutely fine and have no pain."
        prompt = self.triage_engine._build_assessment_prompt(symptoms, self.mock_user_data, "", "")

        self.assertIn("severe chest pain", prompt)
        self.assertIn("absolutely fine", prompt)

    @patch('api.hospital_finder.requests.get')
    def test_hospital_routing_ocean_coordinates(self, mock_get):
        """
        Test routing when geocoding fails or returns an ocean coordinate.
        The finder should fallback to static databases.
        """
        # Mock finding nothing from Nominatim
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        hospitals = self.hospital_finder.find_nearby_hospitals(location="Middle of Atlantic Ocean")

        # Should fallback to Mumbai due to default fallback logic when name matching fails
        self.assertGreater(len(hospitals), 0)
        self.assertEqual(hospitals[0].name, 'Lilavati Hospital')

    @patch('api.hospital_finder.requests.get')
    def test_hospital_routing_invalid_pincode(self, mock_get):
        """
        Test routing with an invalid pincode to ensure error handling falls back gracefully.

        Nominatim is mocked out: unmocked, it geocodes "000000, India" to a real
        location and returns live hospitals, so the static-fallback path this
        test exists to cover is never reached and the assertion depends on a
        third party's data.
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response

        hospitals = self.hospital_finder.find_nearby_hospitals(location="000000")

        # 000 prefix is not in pincode_to_city, so it defaults to Mumbai
        self.assertGreater(len(hospitals), 0)
        self.assertEqual(hospitals[0].name, 'Lilavati Hospital')
