# Contributing to MedAid

Thanks for taking the time to contribute. This document covers the workflow,
the code standards, and the one rule that is not negotiable: **changes to the
safety layer need tests.**

## Getting set up

Follow the [Installation Guide](README.md#installation) in the README. You will
need Python 3.12+, Node 18+, and at minimum a `GOOGLE_API_KEY` for anything that
touches the LLM paths.

Verify your environment before you start:

```bash
cd backend && python manage.py test        # 360+ backend tests
cd frontend && CI=true npm run build              # type-check + lint + build
```

## Branching strategy

We use **GitHub Flow** — `main` is always releasable.

```
main
 └── feat/short-description      new capability
 └── fix/short-description       bug fix
 └── safety/short-description    anything touching api/safety/ or the guardrails
 └── docs/short-description      documentation only
 └── chore/short-description     tooling, deps, refactors with no behaviour change
```

Branch from `main`, keep the branch focused, and open a pull request. Direct
pushes to `main` are discouraged.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/), so the changelog
can be assembled mechanically:

```
feat(triage): add negation-aware emergency keyword screen
fix(chat): stop rendering raw model prose above the assessment card
safety(reports): escalate critical lab values to the assigned clinician
docs(readme): document the OCR fallback chain
test(quota): cover the per-user daily ceiling
chore(deps): bump Django to 4.2.27
```

Scope is the module or app area. Breaking changes get a `!` (`feat(api)!: …`)
and a `BREAKING CHANGE:` footer.

## Code style

**Python**

- PEP 8, 4-space indent, ~100 column soft limit.
- Type hints on anything crossing a module boundary.
- Every module gets a docstring saying *why it exists*, not what it does. Look at
  [`api/lab_reference.py`](backend/api/lab_reference.py) for the standard —
  it cites the evidence for its design decision.
- Structured logging only: `logger.info("triage.assessment_complete", extra={...})`.
  **Never log symptom text, patient names, or report contents.**

**TypeScript / React**

- Function components with typed props. No `any` on a public prop.
- Tailwind utilities styled from the design tokens in
  [`src/styles/medaidTokens.ts`](frontend/src/styles/medaidTokens.ts) — use
  `medaidClasses` and `riskStyles` rather than hardcoding colours, so light/dark
  and the risk palette stay in one place.
- Risk colour is semantic. Never use the brand teal for a risk state, and never
  use a risk hue for chrome.
- Comments explain intent. Match the density of the file you are editing.

## Testing requirements

| Change touches | Required |
| --- | --- |
| `api/safety/`, `assessment_quality.py`, `triage_engine_v2.py` | Test proving the guardrail holds, **and** a test proving it still holds when the LLM is unavailable |
| Any new API endpoint | Auth test (401 unauthenticated), happy path, and one failure path |
| Any model change | Migration, plus a test if the field carries clinical meaning |
| Frontend components | Build must pass with `CI=true` (warnings are errors) |

Run the full backend suite before opening a PR. Some LLM-quota tests key on the
current minute and can be flaky under a slow machine — re-run once before
investigating.

## Pull request checklist

- [ ] Tests pass locally (backend suite + frontend build)
- [ ] New behaviour is covered by a test
- [ ] No secrets, API keys, or patient data in the diff
- [ ] `.env.example` updated if you added a setting
- [ ] README/docs updated if you changed the architecture or setup
- [ ] Safety-relevant changes explain the failure mode they protect against

## What not to do

- Do not weaken or bypass the emergency short-circuit, the degraded-risk floor,
  or confidence calibration to make output "look better".
- Do not let the LLM decide anything arithmetic — lab values are classified by
  [`lab_reference.py`](backend/api/lab_reference.py), not by a model.
