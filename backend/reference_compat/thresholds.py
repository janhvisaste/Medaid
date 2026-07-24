"""Report emergency thresholds copied from the reference assessment flow."""

SPO2_EMERGENCY_THRESHOLD = 90
HEMOGLOBIN_EMERGENCY_THRESHOLD = 6.0
MAX_MEDICAL_TESTS_SCANNED = 50


def _medical_tests(report_data):
    if not isinstance(report_data, dict):
        return []
    tests = report_data.get("medical_tests", []) or []
    return tests if isinstance(tests, list) else []


def find_report_emergency(report_data):
    """Return the reference emergency reason or None.

    Source: Shivanikinagi/Medaid/backend_processing.py::
    integrate_report_and_run_assessment. The reference scans only the first
    50 tests and uses strict less-than comparisons for both thresholds.
    """
    for test in _medical_tests(report_data)[:MAX_MEDICAL_TESTS_SCANNED]:
        if not isinstance(test, dict):
            continue
        name = str(test.get("test_name", "")).lower()
        value = test.get("value")

        if "spo2" in name or "oxygen" in name:
            try:
                if float(value) < SPO2_EMERGENCY_THRESHOLD:
                    return "Low oxygen saturation detected in report"
            except (TypeError, ValueError):
                pass

        if "hemoglobin" in name or name == "hb":
            try:
                if float(value) < HEMOGLOBIN_EMERGENCY_THRESHOLD:
                    return "Severely low hemoglobin in report"
            except (TypeError, ValueError):
                pass

    return None
