# Reference Compatibility Deviations

This module targets behavioral and contract parity while preserving the
existing Django/React architecture.

- Authentication: the endpoint requires existing Django JWT authentication.
  The Streamlit patient flow accepts an email/name session without a password;
  that zero-auth behavior is not replicated for security.
- Clinician access: the reference uses a shared Streamlit password, default
  medaid123. The Django role-based clinician API is retained instead.
- Storage: this module performs no database writes, matching the reference
  assessment function. The surrounding product persists data in PostgreSQL
  rather than local_db.json or MongoDB.
- UI/runtime: no Streamlit, rerun, or st.session_state behavior is added.
- Voice, language UI, facility recommendations, and PDF generation are out of
  scope for this triage compatibility module.
- Threshold boundaries: source inspection verifies strict less-than
  comparisons; SpO2 90 and hemoglobin 6.0 are not emergency thresholds.
- Fallback naming: the reference integration converts LLM errors to a
  Medium/Unknown object. This module exposes that integration fallback as
  normalize.get_fallback_response.
