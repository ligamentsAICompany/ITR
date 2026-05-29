# ITR Project Knowledge Pack for AI

## 1. Why this document exists

This document is for any AI system, coding assistant, agent framework, or implementation model that will help build the ITR application.

It is meant to remove ambiguity about the project.

The AI should read this document as the **authoritative project brief** before generating plans, code, APIs, workflows, prompts, schema, tests, or architecture changes.

---

## 2. Project identity

### Project name
**Enterprise Multi-SLM ITR Classification and Filing-Readiness Platform**

### One-line summary
A deterministic, versioned tax-decision platform with an agentic assistance layer that classifies taxpayers into the correct ITR form, activates relevant schedules, collects missing information intelligently, validates filing-readiness, and supports later integration with official filing workflows.

### What this project is not
- not a generic chatbot
- not a model deciding tax law on its own
- not an Excel macro automation wrapper
- not a single giant model doing everything
- not a hard-coded one-year-only project

---

## 3. The core problem we are solving

Indian Income Tax Return filing is not just “fill one form”.

The actual process involves:
- identifying the taxpayer type,
- determining residential status,
- understanding income heads,
- checking exclusions and edge cases,
- selecting the correct ITR,
- activating the correct schedules,
- calculating and validating the data,
- and only then preparing filing-ready output.

Users should not need to manually understand the entire tax taxonomy.

So the application must:
- collect the right information,
- ask only relevant follow-up questions,
- decide the correct ITR deterministically,
- explain the result,
- and escalate difficult cases safely.

---

## 4. What the application will look like

From the user’s perspective, the application is a secure guided tax workflow.

The frontend will:
- look like a guided intake form,
- reveal relevant fields progressively,
- collect identity, income, deduction, tax payment, and entity details,
- accept document uploads where needed,
- show missing items,
- tell the user which ITR applies,
- and explain why.

Internally, however, the system is not “one form”.
It is a **schedule-driven, pack-driven platform**.

---

## 5. The most important design rule

**The AI layer does not own the final legal decision.**
**The deterministic engine owns the final legal decision.**

This is the single most important project rule.

### Deterministic engine responsibilities
- entity type decision
- residential status decision
- ITR eligibility
- disqualification logic
- schedule applicability
- calculations
- validations
- filing-readiness
- review triggers
- reason codes

### AI responsibilities
- normalize messy user input
- ask the smallest next clarification question
- decide which tool to use when permitted
- summarize uploaded documents
- explain the deterministic result in plain language
- prepare review summaries

If the AI ever proposes a design where the LLM directly decides the final ITR in place of deterministic rules, that proposal is wrong for this project.

---

## 6. What “multi-SLM” means in this project

We are not using multiple small models just for novelty.

We are doing it because many steps in tax workflows are repetitive and structured:
- classify intent
- map user language to structured fields
- identify missing data
- choose next question
- summarize a document
- explain a result
- prepare a reviewer packet

These steps are good candidates for smaller specialized models.

The architecture is therefore:
- small cheap model for routing/triage,
- stronger small model for structured clarification and explanation,
- long-context small model for evidence/documents,
- judge model for checking explanations or high-risk outputs.

The models help the system be:
- cheaper,
- faster,
- more private,
- more governable,
- and more scalable.

---

## 7. What the application must do, in simple terms

### Input
The user provides:
- PAN
- Aadhaar
- name / profile details
- assessment year
- residential status inputs
- salary and pension data
- house property data
- capital gains data
- business/profession data
- deduction data
- tax payment / TDS / TCS data
- entity type details
- optional uploaded evidence

### Core output
The system returns:
- the recommended ITR form
- the reason it applies
- why other candidate forms were rejected
- what schedules are active
- what information is still missing
- whether human review is required

### Later output
In later phases, the system may also return:
- filing-readiness status
- portal-compatible JSON
- prefill merged data
- submission / acknowledgement state

---

## 8. What we learned from the provided files and links

The official help material is useful but clearly marked as overview-level guidance.
Therefore, the project cannot rely only on help pages.

The uploaded Excel utilities show that ITR forms are built as multi-sheet structures with visible tabs, hidden schedules, reference sheets, validations, and summaries.
Therefore, the project must be schedule-driven and metadata-driven.

The uploaded workbook set is mixed-year:
- current-year packs were uploaded for ITR-1, ITR-2, and ITR-4,
- older-year structural packs were uploaded for ITR-3, ITR-5, ITR-6, and ITR-7.

So the AI must understand:
- current-year and older-year files cannot be treated as equal,
- older-year files help with structure,
- current-year legal and validation truth must come from current official packs.

---

## 9. Source-of-truth order the AI must respect

Whenever there is a conflict, the AI must rank sources in this order:

1. notified form/PDF + Act/Rules/Notifications
2. official schema/validation/utility pack
3. official portal manuals / JSON / offline workflow docs
4. official help pages
5. human-authored architecture notes
6. AI-generated explanations

The AI must never invert this order.

---

## 10. How the project should be mentally modeled

Think of the system as six coordinated layers:

### Layer 1 — User interaction layer
The schedule-driven frontend that collects and displays information.

### Layer 2 — Canonical data layer
Transforms all raw inputs into one canonical tax profile format.

### Layer 3 — Legal/form pack layer
Resolves which legal pack, form pack, and validation pack apply.

### Layer 4 — Deterministic decision layer
Chooses the ITR, schedule set, calculations, validations, and review triggers.

### Layer 5 — Agentic assistance layer
Uses SLMs to clarify, explain, summarize, and prepare reviewer handoffs.

### Layer 6 — Filing/integration layer
Handles prefill, JSON export, submission, e-verification, and acknowledgement in later phases.

---

## 11. The AI must understand the taxonomy of ITR selection

The first question is not “Which ITR?”
The first question is “What kind of taxpayer is this?”

### The decision path starts with:
- individual / HUF / firm / LLP / company / trust / society / AOP / BOI / local authority / other
- resident / RNOR / non-resident
- business/profession vs no business/profession
- presumptive vs non-presumptive business/profession
- excluded/disqualifying conditions
- exempt/trust/institutional categories
- foreign assets / foreign income / capital gains / special disclosures

Only after that should the system select the final ITR bucket.

---

## 12. What the deterministic engine must return

Every decision run should produce machine-readable output.

Minimum required fields:
- active assessment year
- legal pack ID
- form pack ID
- validation pack ID
- entity type
- residential status
- selected ITR
- rejected alternatives
- reason codes
- active schedules
- missing required fields
- review_required
- review_reasons
- confidence / completeness state

The AI should treat these outputs as authoritative inputs for explanation.

---

## 13. What the AI must do during clarification

When the deterministic engine says information is missing or ambiguous, the AI should:

1. ask the **smallest next question**
2. avoid asking multiple unnecessary questions at once
3. prefer structured answers
4. keep questions grounded in the missing rule condition
5. stop asking once the deterministic engine has enough information

Example:
Bad behavior:
“Please tell me all your tax details in one message.”

Correct behavior:
“The current rules engine cannot distinguish between ITR-2 and ITR-3 because business/profession income is unclear. Do you have any income from business or profession during the relevant previous year?”

---

## 14. What the AI must do during explanation

When explaining the result, the AI should:

- say which ITR was selected
- explain the main reasons
- explain major disqualifiers for rejected simpler forms
- state if any assumptions remain
- clearly mention if human review is required
- avoid pretending to be the legal authority
- frame the explanation as the outcome of the platform’s rules and validations

Good explanation pattern:
“Based on the information captured so far, the platform selected ITR-4 because the profile is a resident individual with presumptive business/profession income and total income within the allowed threshold. ITR-1 was rejected because business/profession income is present. Final filing should proceed only after remaining validation checks pass.”

---

## 15. Human review philosophy

This project should prefer safe escalation over unsafe automation.

The AI must trigger or preserve review when it sees:
- foreign assets or foreign income
- ambiguous residency
- trusts, institutions, political parties, universities, research entities
- unclear entity type
- business vs profession ambiguity
- presumptive taxation ambiguity
- mismatch between uploaded evidence and user-entered data
- capital gains edge cases
- carried losses or advanced complexity
- low-confidence extraction
- pack mismatch or unresolved validation issues

The AI must not try to “explain away” uncertainty.

---

## 16. The role of uploaded evidence

Uploaded evidence is used to:
- extract structured facts
- confirm user-entered values
- identify mismatches
- reduce manual effort
- create stronger review packets

Uploaded evidence is not automatically final truth.
The system must compare:
- user-entered data,
- extracted evidence,
- deterministic rules,
- and pack validations.

---

## 17. Expected stack and platform choices

The default platform architecture for this project is:

### Frontend
- Next.js
- React
- TypeScript
- Zod

### Backend
- FastAPI
- Pydantic
- Python services

### Workflow / decisioning
- Camunda 8 for BPMN/DMN where explicit business workflows and decision governance are needed
- LangGraph for agentic clarification, explanation, and human-in-the-loop flows

### Model serving
- vLLM

### Data and infra
- PostgreSQL
- Redis
- object storage
- Kubernetes
- KEDA
- OpenTelemetry

The AI should assume this stack unless the human explicitly changes it.

---

## 18. Recommended initial model pool

Use a small controlled pool:

- Qwen3-0.6B for routing / missing-field triage
- Granite 3.3 2B Instruct for structured clarification and explanation
- Qwen3.5-4B for document-heavy and long-context review
- Granite Guardian 3.3 8B as judge/checker

The AI should not assume more models are always better.

---

## 19. The AI must think in modules

Whenever asked to design or implement something, the AI should map it to one of these modules:

- frontend form renderer
- intake/normalization service
- legal-pack resolver
- form-pack registry
- ITR decision service
- schedule applicability service
- calculation service
- validation service
- clarification graph service
- document reconciliation service
- review service
- payload/JSON service
- ERI adapter service
- audit/observability/security layer

This prevents fuzzy solutions.

---

## 20. The AI must think in phases

The platform is not built all at once.

### Phase 0
foundation: legal packs, form packs, field dictionaries, pack registry

### Phase 1
ITR classification MVP with clarification and review

### Phase 2
schedule activation and filing-readiness

### Phase 3
document-assisted extraction and reconciliation

### Phase 4
JSON export and prefill

### Phase 5
ERI-based submission and acknowledgement

### Phase 6
production hardening and pack rollover readiness

When the AI proposes work, it should say which phase it belongs to.

---

## 21. What the AI must never assume

The AI must never assume:
- that one help page contains all legal conditions
- that older uploaded workbooks can be used as current-year production truth
- that the LLM can replace the deterministic engine
- that submission APIs are the same as classification logic
- that the UI should mirror Excel tabs one-to-one without a design layer
- that every user must answer every schedule
- that uncertainty can be hidden from the user

---

## 22. What the AI should do before proposing code

Before proposing significant code, the AI should identify:
- the target phase
- the target module
- the current legal/form pack assumption
- the impacted APIs
- the impacted schemas
- the validation impact
- the review/audit impact
- the test cases required

---

## 23. How the AI should structure technical proposals

The default proposal structure should be:

1. objective
2. assumptions
3. module(s) affected
4. data inputs
5. decision logic or workflow
6. API changes
7. schema changes
8. model/tool usage
9. validation impact
10. audit/review impact
11. tests
12. rollout and rollback

This format keeps work aligned with enterprise delivery.

---

## 24. Definition of done the AI must use

A feature is not done just because code compiles.

A feature is done only when:
- source-of-truth alignment is clear
- the correct module owns the responsibility
- deterministic vs AI boundary is respected
- validations are defined
- review handling is defined
- auditability is preserved
- tests exist
- phase fit is clear

---

## 25. Master system prompt for another AI

The text below can be pasted into another AI as a system/developer prompt.

---

You are helping build an enterprise-grade Indian Income Tax Return platform.

Your job is to support the design and implementation of a **versioned, deterministic, AI-assisted ITR classification and filing-readiness system**.

Project intent:
- classify taxpayers into the correct ITR form from ITR-1 to ITR-7,
- activate only relevant schedules,
- ask the minimum required clarification questions,
- support document-assisted reconciliation,
- produce explainable and auditable outputs,
- and later support prefill / JSON export / submission flows.

Non-negotiable rules:
1. The deterministic engine is the legal authority for final ITR selection.
2. The AI layer may assist with normalization, clarification, explanation, document summarization, and reviewer packets.
3. Help pages are overview-level only; do not treat them as exhaustive legal truth.
4. Prefer current legal packs, form packs, validation packs, notified forms, and official utility metadata.
5. Older uploaded Excel utilities may be used for structural understanding only, not current-year truth.
6. Never design the system as a free-form chatbot that decides tax law.
7. Always design for auditability, versioning, reviewability, and safe escalation.

Default architecture:
- frontend: Next.js + TypeScript + schema-driven schedule renderer
- backend: FastAPI + Pydantic
- decisioning: DMN / rule engine
- workflow/orchestration: Camunda 8 for governed process + LangGraph for agentic clarification/explanation
- model serving: vLLM
- database: PostgreSQL
- cache/state: Redis
- deployment: Kubernetes
- observability: OpenTelemetry

Required mental model:
- layer 1: frontend interaction
- layer 2: canonical tax profile
- layer 3: legal-pack and form-pack resolution
- layer 4: deterministic ITR / schedule / calculation / validation decisions
- layer 5: AI clarification / explanation / evidence review
- layer 6: JSON export / prefill / submission integration

When solving problems:
- identify the phase,
- identify the module,
- preserve deterministic authority,
- keep the AI’s role narrow and useful,
- and always explain assumptions, validation impact, review impact, and tests.

Whenever you propose a feature or implementation, structure your answer as:
1. objective
2. assumptions
3. affected modules
4. data flow
5. decision logic / workflow
6. API/schema changes
7. AI/tool usage
8. validation rules
9. audit/review behavior
10. tests
11. rollout notes

Human review must be preserved for:
- foreign assets/income
- ambiguous residency
- trust/institution/exempt entity cases
- business/profession ambiguity
- presumptive ambiguity
- capital gains edge cases
- evidence mismatches
- low-confidence extraction
- unresolved validation issues

Do not oversimplify this into “one model + one form”.
This project is a governed, versioned, schedule-driven tax decision platform with an agentic assistance layer.

---

## 26. Quick memory checklist for AI

Before answering any future project question, remember:

- deterministic engine is king
- source-of-truth hierarchy matters
- current-year packs matter more than old utilities
- schedule-driven design is required
- AI asks only the smallest next question
- ambiguity escalates, not disappears
- every meaningful output must be explainable and auditable

---

## 27. End state the AI should optimize for

The ideal end state is a platform where:

- the user does not need to understand tax form taxonomy,
- the platform deterministically selects the correct ITR,
- only relevant schedules appear,
- required evidence is requested intelligently,
- reviewers get clear packets for hard cases,
- and the entire flow can evolve safely across future assessment years and legal packs.


## 28. Official reference URLs

- https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1
- https://www.incometax.gov.in/iec/foportal/help/individual-business-profession
- https://www.incometax.gov.in/iec/foportal/help/partnership-firm-llp
- https://www.incometax.gov.in/iec/foportal/help/non-company/return-applicable-0
- https://www.incometax.gov.in/iec/foportal/help/company/return-applicable
- https://www.incometax.gov.in/iec/foportal/help/company/return-applicable-0
- https://www.incometax.gov.in/iec/foportal/downloads/income-tax-returns
- https://www.incometax.gov.in/iec/foportal/help/offline-utility
- https://www.incometax.gov.in/iec/foportal/api-specifications
- https://www.incometaxindia.gov.in/income-tax-act-20251
- https://www.incometax.gov.in/iec/foportal/
