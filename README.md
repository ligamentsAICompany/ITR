# Agentic ITR Platform

An enterprise-grade Indian Income Tax Return (ITR) classification platform that combines a deterministic tax-rule engine with a strictly assistive agentic layer. The system is designed to select the correct ITR form using versioned rules, preserve auditability through reason codes, and use AI only for normalization, clarification, and explanation.

The deterministic backend remains the authority for every tax decision. The agent and SLM services do not decide the ITR form; they help collect missing information, structure user input, and explain the rule-based result.

## What This Project Is

This project helps classify Indian taxpayers into the appropriate ITR form, from ITR-1 through ITR-7, using a canonical tax profile and deterministic eligibility rules.

Core goals:

- Classify ITR forms through explicit, auditable rules.
- Keep legal thresholds in versioned legal-pack configuration.
- Normalize messy user input into a canonical tax profile.
- Ask clarification questions only when required data is missing or ambiguous.
- Explain final decisions in user-friendly, CA-style language.
- Preserve deterministic authority by preventing the AI layer from making tax decisions.
- Provide a production-ready backend, frontend, tests, Docker setup, and deployment notes.

## Tech Stack

Backend:

- Python
- FastAPI
- Pydantic
- LangGraph
- Uvicorn
- Pytest
- Ruff

Frontend:

- Next.js App Router
- React
- TypeScript
- Tailwind CSS
- ESLint

Architecture and deployment:

- Deterministic rule engine in `itr_engine/`
- API and service layer in `app/`
- Canonical JSON schema in `canonical_tax_profile.schema.json`
- Docker and Docker Compose
- Versioned legal-pack configuration for thresholds and rule limits

## Step-by-Step Workflow

1. User enters taxpayer details in the frontend.

   The intake form collects identity, residency, income heads, capital-gains subtype details, business or professional income, foreign assets or income, deductions, and special-condition flags.

2. Frontend sends raw intake data to the backend.

   The frontend calls `POST /v1/normalize` with the raw form state. This endpoint converts user-facing fields into the canonical tax profile structure.

3. Backend builds a canonical tax profile.

   The normalization service maps the raw input into structured sections such as:

   - `user_identity`
   - `residency_status`
   - `income_heads`
   - `deductions`
   - `foreign_assets`
   - `special_conditions`
   - `exemptions_flags`

4. Deterministic engine evaluates ITR eligibility.

   The frontend calls `POST /v1/itr-decision`. The backend passes the canonical profile to the deterministic classifier in `itr_engine/`.

   The engine applies hard exclusions, eligibility checks, and priority ordering across ITR forms. It returns:

   - `candidate_itr`
   - `reason_codes`
   - `missing_fields`
   - `confidence`

5. Missing fields are checked.

   The frontend calls `POST /v1/missing-fields`. If required fields are missing, the workflow routes to clarification before explanation or escalation.

6. Agent asks a targeted clarification question when needed.

   If missing or ambiguous data exists, the frontend calls `POST /v1/clarify`. The SLM layer generates a narrow question for the next required field. The final ITR decision still remains rule-based.

7. Backend explains the decision.

   Once required fields are complete, the frontend calls `POST /v1/explain`. The explanation service converts deterministic reason codes into human-readable language.

8. Frontend displays the result.

   The UI shows the candidate ITR, confidence, missing fields, explanation, workflow log, and escalation status if expert review is needed.

## How The Agentic System Works

The agentic system is a controlled orchestration layer around the deterministic tax engine. It coordinates the workflow but does not make tax decisions.

Main responsibilities:

- Normalize user input into a canonical profile.
- Run deterministic ITR classification.
- Detect missing or ambiguous fields.
- Ask one focused clarification question at a time.
- Re-run the deterministic workflow after the user answers.
- Generate plain-language explanations from reason codes.
- Escalate only when confidence or review signals require expert attention.

The LangGraph flow is intentionally conservative:

1. Normalize the profile.
2. Run deterministic classification.
3. Check missing fields.
4. If information is missing, ask clarification first.
5. If information is complete, generate explanation.
6. If confidence is low or review flags are present, escalate for expert review.

The SLM is restricted to assistive tasks:

- It may explain reason codes.
- It may ask clarification questions.
- It may help normalize unstructured input.
- It must not override the deterministic classifier.
- It must not invent tax rules or select an ITR form independently.

## Rule Engine

The deterministic engine lives in `itr_engine/`.

Important components:

- `classifier.py`: public classifier entrypoint.
- `evaluator.py`: disqualification, eligibility, priority, and reason-code orchestration.
- `rules.py`: reusable tax-rule predicates.
- `legal_packs.py`: versioned legal thresholds and limits.
- `formatter.py`: final response shaping.

The engine uses reason codes for traceability. For example, an ITR-1 case with allowed section 112A LTCG can include:

- `ITR1_ELIGIBLE_SIMPLE_RESIDENT_INDIVIDUAL`
- `ITR1_ALLOWED_112A_LTCG_WITHIN_THRESHOLD`
- `ITR1_ALLOWED_AGRICULTURAL_INCOME_WITHIN_THRESHOLD`

## API Endpoints

Backend base URL:

```bash
http://localhost:8000
```

Available endpoints:

- `GET /v1/health`
- `POST /v1/normalize`
- `POST /v1/itr-decision`
- `POST /v1/missing-fields`
- `POST /v1/explain`
- `POST /v1/clarify`

## Running Locally

Backend:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open:

```bash
http://localhost:3000
```

## Running With Docker

```bash
docker compose up --build
```

Open:

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:8000/v1/health`

## Verification

Backend tests and checks:

```bash
python -m pytest
python -m ruff check .
python -m compileall app itr_engine tests
```

Frontend checks:

```bash
npm run build --prefix frontend
npm run lint --prefix frontend
```

## Security And Compliance Notes

- Sensitive validation errors are sanitized.
- Request payloads are size-limited.
- Rate limiting middleware is included.
- CORS origins are configurable.
- The frontend masks sensitive profile fields where appropriate.
- The deterministic engine exposes reason codes for auditability.

## Project Status

The platform currently includes:

- Deterministic ITR classification from ITR-1 to ITR-7.
- Granular capital-gains handling for ITR-1 and ITR-4.
- Versioned legal-pack thresholds.
- FastAPI backend.
- LangGraph orchestration.
- Next.js frontend.
- Security middleware.
- Docker deployment setup.
- Regression tests for core classification scenarios.
