"""Django-compatible behavioral adapter for the Streamlit MedAid reference."""

from .assess import integrate_report_and_run_assessment

__all__ = ["integrate_report_and_run_assessment"]
