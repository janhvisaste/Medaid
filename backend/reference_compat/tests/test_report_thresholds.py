import unittest

from reference_compat.thresholds import find_report_emergency


class ReportThresholdTests(unittest.TestCase):
    def test_spo2_strict_boundary(self):
        self.assertIsNotNone(find_report_emergency({
            "medical_tests": [{"test_name": "SpO2", "value": 89}]
        }))
        self.assertIsNone(find_report_emergency({
            "medical_tests": [{"test_name": "SpO2", "value": 90}]
        }))

    def test_hemoglobin_strict_boundary(self):
        self.assertIsNotNone(find_report_emergency({
            "medical_tests": [{"test_name": "Hb", "value": 5.9}]
        }))
        self.assertIsNone(find_report_emergency({
            "medical_tests": [{"test_name": "Hb", "value": 6.0}]
        }))

    def test_only_first_fifty_tests_are_scanned(self):
        tests = [{"test_name": "normal", "value": 1}] * 50
        tests.append({"test_name": "SpO2", "value": 89})
        self.assertIsNone(find_report_emergency({"medical_tests": tests}))
