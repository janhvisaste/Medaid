# MedAid
> Describe your symptoms in plain English. MedAid returns a risk-stratified assessment — and the model is deliberately the least trusted part of the system that produces it.

> [!WARNING]
> **Research prototype, not a medical device.** Not clinically validated, not regulatory-reviewed. Never a substitute for professional diagnosis. In an emergency, contact local emergency services.

Published at **IEEE ICTBIG 2025** — [read the paper](https://ieeexplore.ieee.org/document/11323835) · [cite it](#citation)

---

## What Is This?

An LLM-driven triage agent for under-resourced healthcare settings, where the first triage decision is normally made by the patient with no information — they delay care that's needed, seek emergency care that isn't, and clinicians receive intake with no priority signal at all.

You describe your symptoms; MedAid:
1. screens the text for emergency keywords **before any model call**,
2. asks Google Gemini to produce a structured differential — conditions, confidence, reasoning, next steps,
3. **grounds** that output against deterministic checks — a confidence ceiling based on how much you actually said, condition names validated against ICD-10-CM, lab values classified by arithmetic rather than the model,
4. and escalates to a clinician automatically when the risk is high.

Because the grounding step runs on every response, a hallucinated condition or an overconfident number gets caught before a patient sees it, rather than trusted because it came from a model.

**The governing idea:** the LLM is the least trustworthy component in the system, so it is given the smallest possible amount of authority. Every safety check below still works with zero API keys configured.

---

## Key Features

| Feature | What it does |
|---|---|
| **Multi-stage triage** | Free-text symptoms → risk tier, ranked differential, reasoning, next steps, when-to-seek-care guidance |
| **Pre-LLM emergency screen** | Negation-aware keyword match runs before any model call and short-circuits straight to emergency routing |
| **Confidence calibration** | Self-reported model confidence is capped against how specific the patient's actual input was — "I feel bad" cannot score 90% |
| **ICD-10-CM validation** | Condition names checked against a curated list, then a vendored ICD-10-CM index, in-process, no network call |
| **Cross-provider failover** | Gemini primary, OpenRouter failover resolved from a pre-warmed free-model catalogue — adds no latency to a live request |
| **Deterministic lab grounding** | Reference ranges and normal/low/high/critical classification come from arithmetic against a knowledge base, never the LLM |
| **Clinician escalation** | High-risk assessments and critical lab values auto-create an alert and auto-assign the least-loaded clinician |
| **3-tier OCR** | Apple Vision (macOS) → Tesseract → NVIDIA vision, each tier logging which one served the request |
| **Chat workspace** | Conversational triage with clarifying questions, file attachments, voice input, per-turn assessment cards |
| **LLM quota guards** | Reserve-then-check counters with global and per-user ceilings on every LLM call site |

Also included: condition-aware dietary guidance, risk-weighted nearby-facility lookup with maps, PDF health-passport export, and a token-driven design system with a WCAG-AA risk palette in light and dark.

---

## Architecture

```mermaid
flowchart TD
    PATIENT(["👤 Patient"]) -->|"symptoms / report"| API

    API["⚙️ Django REST API<br/>JWT auth · quota guard"]
    API --> SCREEN

    SCREEN{{"🚨 Emergency keyword screen<br/><i>deterministic — runs before any LLM call</i>"}}
    SCREEN -->|"match"| ESCALATE["⛔ Immediate escalation<br/>no model call · &lt; 50 ms"]
    SCREEN -->|"no match"| ENGINE

    ENGINE["🧠 Triage Engine v2<br/>builds prompt + patient history"]
    ENGINE --> GEMINI

    GEMINI["Google Gemini<br/><b>primary provider</b>"]
    GEMINI -.->|"on failure"| OPENROUTER["OpenRouter<br/><b>failover</b>"]
    GEMINI --> GROUND
    OPENROUTER --> GROUND

    GROUND["🛡️ Grounding layer — deterministic<br/>confidence cap · ICD-10 validation · risk floor"]
    GROUND --> DB

    DB[("💾 PostgreSQL<br/>TriageRecord · alerts · history")]
    ESCALATE --> DB

    DB -->|"risk = high / emergency"| ALERT["👩‍⚕️ ClinicianAlert<br/>+ auto-assign least-loaded"]
    DB -->|"always"| PATIENT2(["📋 Assessment card<br/>+ PDF report"])

    classDef entry fill:#e0f2fe,stroke:#0369a1,stroke-width:2px,color:#0c4a6e
    classDef api fill:#ccfbf1,stroke:#0f766e,stroke-width:2px,color:#134e4a
    classDef safety fill:#fef2f2,stroke:#b91c1c,stroke-width:3px,color:#7f1d1d
    classDef engine fill:#f3e8ff,stroke:#7e22ce,stroke-width:2px,color:#581c87
    classDef data fill:#f1f5f9,stroke:#475569,stroke-width:2px,color:#1e293b

    class PATIENT,PATIENT2 entry
    class API api
    class SCREEN,ESCALATE,GROUND,ALERT safety
    class ENGINE,GEMINI,OPENROUTER engine
    class DB data
```

**Safety control:** the emergency screen and the post-generation grounding (confidence cap, ICD-10 validation, risk floor) are pure code — no model in the loop — so they hold even during a full provider outage. A degraded response is floored at `medium` risk and flagged `requires_human_review`; it can never quietly present as `low`.

**Failover:** exactly one cross-provider attempt against OpenRouter, resolved from a catalogue a Celery beat job refreshes every 30 minutes — so discovering a fallback model costs no extra latency on the request path.

**Not a RAG pipeline.** Retrieval here is exact-match and arithmetic, not vector similarity: a lab reference range is a fact to look up, not a nearest neighbour to approximate. The [Lab-AI study](https://arxiv.org/abs/2409.18986) found unaugmented LLMs answer lab reference-range questions at 38.4% accuracy, rising to 99.3% when grounded in retrieved source data — so classification is arithmetic, and the model only ever writes prose about a value already verified.

---

## Safety & Guardrails

The part of the system that matters most, in the order a request passes through it:

1. **Emergency screen** — [`api/safety/emergency_check.py`](backend/api/safety/emergency_check.py), the single source of truth, called from every entry point (direct triage, chat, guided flow) so routing is identical no matter how a patient entered. Negation-aware: "no chest pain" does not fire the chest-pain rule.
2. **Input specificity gate** — sparse descriptions produce clarifying questions instead of a low-evidence guess, once per conversation.
3. **Confidence calibration** — the API returns both `reported_confidence` (the model's claim) and the calibrated `confidence`, plus `confidence_explanation`, so the UI can say *why* a result is uncertain rather than showing a bare number.
4. **Condition validation** — curated list, then ICD-10-CM. An unrecognised name is flagged, never silently dropped and never presented with the authority of a validated term.
5. **Risk floor** — model risk is raised to `high` if emergency keywords are present; a degraded response never falls below `medium`. The floor only ever moves up.
6. **Deterministic critical-value escalation** — a critically low lab value reaches a clinician on arithmetic classification, regardless of how the model's prose reads it.

**Honest limitation:** critical-value coverage is bounded by the knowledge base — an analyte with no reference data classifies as `unknown`, never `critical`. This raises the floor substantially; it is not a complete safety net.

---

## Getting Started

### 1. Clone
```bash
git clone https://github.com/janhvisaste/Medaid.git
cd Medaid
```

### 2. Install
```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

cd frontend && npm install --legacy-peer-deps && cd ..
```

### 3. Configure
```bash
cp backend/.env.example backend/.env      # add your GOOGLE_API_KEY
cp frontend/.env.example frontend/.env.local
```
Get a free key from [Google AI Studio](https://aistudio.google.com/). Every other feature — OpenRouter failover, facility lookup, dietary advice — has a documented, silent fallback if left unset; see `.env.example` for the full list.

### 4. Run
```bash
cd backend && python manage.py migrate && python manage.py runserver 8001
# new terminal
cd frontend && npm start
```
Frontend at `localhost:3000`, API at `127.0.0.1:8001/api`. Or run `./start-medaid.sh` (`.\start-medaid.ps1` on Windows) to start both.

---

## How It Works

1. **Complete your profile** — pincode (prefills facility search) and medical history feed directly into the assessment prompt.
2. **Describe your symptoms** in the AI workspace, in plain language.
3. **Answer clarifying questions** if your description is too sparse to support a confident answer.
4. **Read the assessment card** — risk badge, calibrated confidence, leading condition, next steps, and (for high/emergency risk) a **Call 112** / **Find nearest facility** banner.
5. **Attach a report** — PDF or image — and it's OCR'd, lab values classified deterministically, findings explained alongside your message.
6. **Download the PDF** to hand to your doctor.

Clinicians get a separate dashboard: assigned patients, priority-ordered alerts, and private notes per case.

---

## API & Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/auth/signup/`, `/api/auth/login/` | Register / authenticate (JWT) |
| `POST` | `/api/triage/assess/` | Run a full triage assessment |
| `GET` | `/api/triage/history/` | Assessment history |
| `GET` | `/api/models/available` | Allow-listed selectable models |
| `POST` | `/api/reports/analyze/` | OCR + structure an uploaded medical report |
| `POST` | `/api/chat/conversations/<id>/messages/` | Send a chat turn (multipart for attachments) |
| `GET` | `/api/facilities/nearby/` | Risk-weighted nearby-facility search |
| `GET` | `/api/recommendations/dietary/` | Condition-aware dietary advice |
| `GET` | `/api/reports/download/<triage_id>/` | Assessment PDF |
| `GET` | `/api/clinician/{stats,patients,alerts}/` | Clinician dashboard data |

<details>
<summary><b>Example — <code>POST /api/triage/assess/</code></b></summary>

```jsonc
// response (abridged)
{
  "risk_level": "low",
  "confidence": 0.42,                 // calibrated
  "reported_confidence": 0.85,        // what the model claimed
  "confidence_was_capped": true,
  "possible_conditions": [
    { "disease": "Post-Viral Cough", "confidence": 0.35 }
  ],
  "recommendations": ["Stay hydrated and use a humidifier at night"],
  "requires_human_review": false,
  "assessment_source": "ai_v2"
}
```

An emergency short-circuit returns `"assessment_source": "emergency_rule"` and never calls a model.

</details>

---

## Tech Stack

**Frontend:** React 19 · TypeScript · Tailwind CSS · React Router · Framer Motion · Leaflet
**Backend:** Django 4.2 · Django REST Framework · SimpleJWT · Celery + beat · django-redis
**Database:** PostgreSQL (production) · SQLite (development) — selected by `DB_ENGINE`, no default
**LLM:** Google Gemini (primary) · OpenRouter (cross-provider failover) · NVIDIA vision (report images)
**OCR:** Apple Vision (PyObjC sidecar) · Tesseract · PyMuPDF
**Medical data:** Vendored ICD-10-CM tabular list (CMS/NCHS, public domain) · lab reference knowledge base
**Infra:** Redis (cache, Celery broker, cross-worker quotas) · ReportLab · GitHub Actions

---

## Project Layout

```
backend/
├── manage.py · requirements.txt
├── medaid/                     settings · urls · celery
└── api/
    ├── models.py                13 models: users, triage, reports, clinician
    ├── views.py                 REST endpoints
    ├── triage_engine_v2.py      multi-stage assessment + provider failover
    ├── chat_service.py          conversational triage
    ├── report_processor.py      OCR → insight orchestration
    ├── safety/                  emergency_check · critical_findings · clinician_alerts
    ├── assessment_quality.py    confidence calibration + name validation
    ├── icd10.py, lab_reference.py   deterministic grounding
    ├── llm_providers/           gemini · openrouter · catalog
    └── test_*.py                 33 modules, 343 tests

frontend/src/
├── styles/medaidTokens.ts       single source of design truth
├── services/                    apiService · authService
└── components/
    ├── Dashboard/                AI workspace (chat + assessments)
    ├── Results/                  AssessmentCard · DietaryAdvice
    └── Clinician/ Profile/ PatientHistory/ Reports/ Auth/ Layout/ ui/

ocr-service/                     Apple Vision OCR sidecar (macOS only)
```

---

## Testing

343 tests, every provider call mocked — the suite runs with **no API keys**, which also proves the degraded paths work without credentials.

```bash
cd backend && python manage.py test         # full suite
cd frontend && CI=true npm run build        # type-check + lint + build
```

Coverage concentrates on risk: `test_emergency_check`, `test_critical_findings`, `test_confidence_cap`, `test_icd10_validation`, `test_provider_fallback`, plus end-to-end flow tests. See [`.github/workflows/ci.yml`](.github/workflows/ci.yml) for what runs on every push.

---

## Known Limitations

Stated plainly, because a triage system that overstates itself is the failure mode that matters.

- **Not clinically validated** — no prospective study, no regulatory review.
- **Emergency detection is keyword-based** — negation-aware, but a patient using words the list doesn't contain falls through to the LLM path.
- **Critical-value coverage is bounded by the knowledge base** — an out-of-scope lab test never classifies as `critical`.
- **English only**, with a few transliterated Hindi terms in the keyword list.
- **OCR tier 1 is macOS-only** — Linux runs on Tesseract, measurably weaker on photographed reports.

---

## Roadmap

- Docker Compose for one-command full-stack startup
- OpenAPI schema + browsable Swagger UI
- Observability (Sentry, OpenTelemetry, metrics)
- Multilingual triage (Hindi, Marathi)
- Clinician feedback loop measured against calibration accuracy

---

## Citation

Published research — cite the paper if you build on this work:

```bibtex
@inproceedings{kinagi2025medaid,
  title     = {Medaid: A Safety-First AI Triage System for Rural Healthcare},
  author    = {Kinagi, Shivani and Jain, Sayyam and Saste, Janhvi and
               Sakhare, Nitin and Yenkikar, Anuradha and Pandit, Pranjal and
               Sable, Nilesh},
  booktitle = {2025 IEEE 5th International Conference on ICT in Business
               Industry \& Government (ICTBIG)},
  year      = {2025}, publisher = {IEEE},
  doi       = {10.1109/ICTBIG68706.2025.11323835}
}
```

**Author:** Janhvi Saste — [@janhvisaste](https://github.com/janhvisaste). Contributing? See [CONTRIBUTING.md](CONTRIBUTING.md) — the one hard rule: anything touching the safety layer needs a test proving the guardrail holds when the LLM is unavailable. Licensed under [MIT](LICENSE).
