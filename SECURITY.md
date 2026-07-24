# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for a security vulnerability.

Report it privately through
[GitHub Security Advisories](https://github.com/janhvisaste/Medaid/security/advisories/new),
or by email to the maintainer listed in the README. Include a description, the
affected component, and steps to reproduce. You can expect an acknowledgement
within 5 working days.

## Scope

MedAid is a research prototype and is **not** deployed as a production medical
service. Reports are still welcome for:

- Authentication and authorisation flaws (JWT handling, role checks, object-level
  access on patient records)
- Prompt injection that defeats the safety layer (see
  [Safety & Guardrails](README.md#safety--guardrails))
- PHI leakage through logs, error responses, or generated PDFs
- Dependency vulnerabilities with a demonstrated path to exploitation here

## Handling secrets

No credential belongs in this repository. Every configurable secret is declared
in [`backend/.env.example`](backend/.env.example) and read from the
environment at runtime.

If you commit a secret by accident, treat it as compromised the moment it is
pushed: **rotate the credential first**, then purge it from history
(`git filter-repo` or the GitHub support flow). Removing the file in a later
commit does not remove it from history.

## Known security posture

- Passwords are hashed by Django's default PBKDF2 hasher.
- API access uses short-lived JWT access tokens with refresh rotation
  (`djangorestframework-simplejwt`).
- Production hardening (`SECURE_SSL_REDIRECT`, HSTS, secure cookies) is derived
  from `DJANGO_DEBUG` and can be overridden per-variable.
- Startup fails hard if `DJANGO_DEBUG=False` and `DJANGO_SECRET_KEY` is still
  the development placeholder.
- The reference-parity endpoint (`ENABLE_REFERENCE_COMPAT_API`) deliberately
  bypasses the safety layer and is **off by default**. It must never be enabled
  on an instance serving real users.
