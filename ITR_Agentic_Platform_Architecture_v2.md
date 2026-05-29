# ITR Agentic Platform Architecture v2

## 1. Document purpose

This is the corrected **v2 architecture document** for the Indian Income Tax Return (ITR) agentic platform. It replaces the earlier 1-10 write-up with a version that is safer, more enterprise-ready, and better aligned with:

- the official AY 2026-27 Income Tax Department help and downloads material,
- the current portal transition state around the Income-tax Act, 2025 and Income-tax Rules, 2026,
- the offline utility / JSON filing workflow,
- and the uploaded ITR utility workbooks.

This document is meant to be the architecture reference for product, engineering, platform, tax-domain, and AI/agent teams.

---

## 2. What changed from v1

The core philosophy from v1 remains correct:

- the final ITR decision must be deterministic,
- the AI/SLM layer must support, not replace, tax logic,
- the system should be modular, scalable, explainable, and auditable.

However, v2 makes several important corrections:

1. **Help pages are not enough**  
   Official help pages explicitly say they are only an overview and are not exhaustive. Therefore, the platform cannot rely on them as the sole source of truth.

2. **The platform must be versioned by legal pack and form pack**  
   AY-based versioning alone is not enough. The system must resolve applicable legal content, forms, schemas, validations, and utilities by year and release pack.

3. **The UI must be schedule-driven, not just form-driven**  
   The uploaded ITR utilities show that each ITR is really a pack of schedules, hidden tabs, helper tabs, validations, and summary layers.

4. **There must be deterministic calculation and validation engines**  
   ITR selection alone is not sufficient. The system must also deterministically handle schedule applicability, calculations, and filing-readiness validation.

5. **The uploaded `.xlsm` utilities are references, not runtime dependencies**  
   We should study them, extract structure from them, and align with their field flow where useful, but not embed Excel macros into production.

---

## 3. Project statement

We are building a **versioned, enterprise-grade, AI-assisted ITR classification and filing-readiness platform**.

At a high level:

- a user interacts with a secure frontend that looks like a guided tax intake experience,
- the system collects structured and semi-structured tax information,
- a deterministic engine decides which ITR applies,
- the system activates only relevant schedules,
- the AI layer asks follow-up questions when information is missing or ambiguous,
- the backend computes filing-readiness and validation status,
- the result is explainable, auditable, and reviewable,
- and later phases may support prefill, JSON generation, submission, e-verification, and acknowledgement via official flows.

This is **not** a free-form chatbot.  
This is **not** a model deciding tax law.  
This is a **tax decision platform with an agentic assistance layer**.

---

## 4. Product goals

### Primary goals
- Classify a taxpayer into the correct ITR bucket from **ITR-1 to ITR-7**
- Ask only the minimum required clarification questions
- Activate only the schedules relevant to the taxpayer
- Produce an explainable result with machine-readable reason codes
- Support human review for edge cases and high-risk scenarios
- Remain stable across assessment years and legal/form changes

### Secondary goals
- Support document-assisted classification and reconciliation
- Generate portal-compatible JSON when filing integration is enabled
- Integrate with prefill and ERI-based submission flows later
- Keep latency and cost low by using multiple small models where appropriate

### Non-goals
- Letting an LLM “decide” the final ITR form without deterministic rules
- Shipping a runtime that depends on Excel macros
- Treating a static help page as the complete legal truth
- Building all filing workflows before the classification engine is stable

---

## 5. Source-of-truth hierarchy

The platform must always evaluate inputs using this hierarchy:

1. **Notified form/PDF + Act/Rules/Notifications**
2. **Official schema / validation / utility pack**
3. **Official portal workflow / user manual / JSON process docs**
4. **Official help pages**
5. **AI explanation layer**

### Why this matters
Help pages are useful for overview and UX copy, but they are not exhaustive.  
Utility packs and official validations reflect the actual data structure and filing behavior.  
Therefore, the decision engine must be pinned to **legal pack + form pack + validation pack**.

---

## 6. Official ITR applicability backbone to encode

The first production rules pack should encode the current official high-level applicability model:

- **ITR-1**: Resident individual other than RNOR, total income up to ₹50 lakh, with limited sources such as salary/pension, specified house property income, other sources, agricultural income up to the permitted threshold, and limited capital gain eligibility. Exclusions apply.
- **ITR-2**: Individual or HUF not eligible for ITR-1 and without business/profession income.
- **ITR-3**: Individual or HUF with business/profession income and not eligible for ITR-1, ITR-2, or ITR-4.
- **ITR-4**: Resident individual, resident HUF, or resident firm other than LLP, total income up to ₹50 lakh, with presumptive business/profession income and specified other sources. Exclusions apply.
- **ITR-5**: Non-company persons such as firms, LLPs, AOPs, BOIs, AJPs, local authorities, representative assessees, cooperative societies, societies, estates, business trusts, investment funds, and related entities that are not filing ITR-7.
- **ITR-6**: Companies other than those claiming exemption under section 11.
- **ITR-7**: Persons including companies required to file under the specified exempt / trust / political party / institutional provisions.

### Important consequence
The first classifier is **not** “Which ITR?”  
The first classifier is:

- What is the **entity type**?
- What is the **residential status**?
- Is there **business/profession income**?
- Is the business/profession income **presumptive**?
- Are there **exclusions** that disqualify the simpler forms?
- Is this a **trust / institution / exempt / political / university / research** case?
- Are there **foreign assets / foreign income / special disclosures / capital gains edge cases**?

---

## 7. Findings from the uploaded utility workbooks

I inspected the uploaded `.xlsm` utilities as structural references.

| Uploaded workbook | AY in filename | Approx. sheets | Examples of visible / key tabs | Architecture takeaway |
|---|---:|---:|---|---|
| `ITR1_AY_26-27_V1.0.xlsm` | AY 2026-27 | 21 | Income Details, HP, TDS, TCS, Taxes Paid and Verification | Current-year individual utility; already split into visible and hidden schedules. |
| `ITR2_AY_26-27_V1.0.xlsm` | AY 2026-27 | 65 | Home, PART A - General, Schedule S, House Property, CG | Current-year complex individual/HUF utility with many schedules and hidden supporting tabs. |
| `ITR4_AY_26-27_V1.0.xlsm` | AY 2026-27 | 24 | Income Details, HP, 44AE, BP | Current-year presumptive taxation utility with dedicated business schedules. |
| `ITR3_AY 2020_21_PR 5.7.xlsm` | AY 2020-21 | 58 | Home, PART A - General, Part A - BS, Trading Account | Older-year utility; useful as a structural reference, not as a production rules source. |
| `ITR5_AY 2020-21_PR4.8.xlsm` | AY 2020-21 | 56 | HOME, PART A - GENERAL, BALANCE_SHEET, PROFIT_LOSS | Older-year non-company utility; useful for schedule inventory only. |
| `ITR6_2020_PR4.2.xlsm` | AY 2020-21 | 62 | Home, PART A - GENERAL, GENERAL2, BALANCE SHEET | Older-year company utility; useful for complexity estimation only. |
| `ITR7_2020_PR3.9.xlsm` | AY 2020-21 | 41 | Home, PI, Audit, Schedule I | Older-year exempt/institution utility; useful for structural understanding only. |

### Implications
- Even “simple” ITRs are not single flat forms.
- Hidden tabs, helper tables, reference lists, schedules, summaries, and validations are common.
- The UI and backend must therefore be **schedule-driven and metadata-driven**, not hard-coded as a single monolithic page.
- Since the uploaded set mixes **AY 2026-27** with **AY 2020-21**, older files must be treated as **structural references only**, never as final legal or validation truth for current production.

---

## 8. Architecture principles

1. **Deterministic authority, agentic assistance**
2. **Version everything**
3. **Prefer structured intake over free-form conversation**
4. **Ask the smallest next question**
5. **Escalate uncertainty instead of guessing**
6. **Separate rules, calculation, validation, explanation, and submission**
7. **Treat PII and tax data as high-sensitivity data**
8. **Keep models swappable**
9. **Make every decision auditable**
10. **Design for current-year pack ingestion, not one-time coding**

---

## 9. High-level system architecture

```text
User / Taxpayer / Reviewer
        |
        v
Schedule-driven Frontend (Next.js)
        |
        v
API Gateway / BFF
        |
        +--> Intake & Normalization Service
        |
        +--> Legal-Pack Resolver
        |
        +--> Form-Pack Registry / Ingestion Service
        |
        +--> Deterministic Decision Service
        |       - entity classification
        |       - ITR eligibility
        |       - schedule applicability
        |       - reason codes
        |
        +--> Deterministic Calculation Service
        |
        +--> Deterministic Validation Service
        |
        +--> Agentic Clarification / Explanation Graph
        |       - next question selection
        |       - evidence explanation
        |       - reason narration
        |       - review summary
        |
        +--> Document Ingestion / Extraction / Reconciliation
        |
        +--> Audit / Review / Case Management
        |
        +--> JSON Generator / Prefill Importer
        |
        +--> ERI Adapter (later phase)
```

---

## 10. Module catalog

### 10.1 Frontend module
Purpose:
- Collect taxpayer inputs
- Render only relevant schedules
- Provide masked and validated fields
- Show reasoned ITR result and review status

Key characteristics:
- Schedule-driven rendering
- Progressive disclosure
- Strong client-side validation
- PII masking
- Save draft / resume
- Human reviewer mode

### 10.2 Intake and normalization module
Purpose:
- Convert raw inputs into canonical tax profile objects

Responsibilities:
- normalize PAN, Aadhaar, dates, status flags
- map user-entered values to canonical field names
- detect missing mandatory values
- derive base flags from raw answers

### 10.3 Legal-pack resolver
Purpose:
- Decide which legal/reference pack applies for the current run

Responsibilities:
- resolve AY
- resolve legal framework / transition mode
- resolve notification set
- resolve rule pack version
- make the active pack explicit in every decision run

### 10.4 Form-pack ingestion and registry
Purpose:
- Ingest and version official forms, utilities, schemas, validations, and schedule metadata

Responsibilities:
- track pack version and release date
- extract field inventory
- extract schedule inventory
- maintain pack compatibility matrix
- expose machine-readable metadata to frontend and decision services

### 10.5 Deterministic decision service
Purpose:
- Determine entity class, ITR eligibility, schedule applicability, and review triggers

Recommended implementation:
- DMN decision tables for stable and reviewable eligibility logic
- FEEL / rule expressions where necessary
- version-tagged decision packs

### 10.6 Deterministic calculation service
Purpose:
- Produce authoritative calculations and derived tax values

Responsibilities:
- section-specific computation
- set-off / carry-forward / schedule totals
- tax, cess, surcharge, interest, balance/refund computations
- filing-readiness derivations

### 10.7 Deterministic validation service
Purpose:
- Determine whether the return payload is complete, internally consistent, and pack-valid

Responsibilities:
- schema validation
- cross-field validation
- schedule-level validation
- calculation consistency validation
- JSON readiness validation

### 10.8 Agentic clarification and explanation module
Purpose:
- Handle ambiguity resolution, minimum-questioning, explanation, and reviewer summaries

Responsibilities:
- decide next clarification question
- rewrite tax logic into user-friendly language
- explain why a form was chosen
- explain why a simpler form was rejected
- summarize evidence conflicts
- prepare handoff packets for human review

### 10.9 Document ingestion and reconciliation module
Purpose:
- Use uploaded evidence to confirm or challenge user-entered data

Examples:
- Form 16
- AIS
- 26AS
- salary slips
- bank statements
- deduction proofs
- business ledgers
- audit reports

### 10.10 Review and case management module
Purpose:
- Manage uncertain, high-risk, or non-automatable cases

Responsibilities:
- create review tickets
- capture evidence
- store reviewer comments
- track approval / rejection / request for more data
- maintain full audit trail

### 10.11 JSON generation and portal compatibility module
Purpose:
- Generate pack-compatible payloads for later filing stages

Responsibilities:
- map canonical profile -> official payload structure
- import portal prefill JSON
- export validated portal JSON
- surface incompatible/missing fields

### 10.12 ERI integration adapter
Purpose:
- Encapsulate official API-based interactions away from core decision logic

Responsibilities:
- login
- add client
- prefill
- validate and submit
- e-verify
- fetch acknowledgement

This module must remain **decoupled** from ITR eligibility logic.

---

## 11. Service catalog

| Service | Main responsibility | Inputs | Outputs |
|---|---|---|---|
| `frontend-bff` | UI orchestration and API aggregation | user session, draft state | page payloads, validation hints |
| `tax-profile-service` | normalization and canonical profile creation | raw form inputs | canonical tax profile |
| `legal-pack-service` | resolve current applicable pack | AY, feature flags | legal pack ID |
| `form-pack-service` | retrieve field/schedule/validation metadata | legal pack ID, form type | form metadata |
| `itr-decision-service` | entity + ITR + schedule decisioning | canonical profile | ITR result, reason codes |
| `tax-calc-service` | calculations | canonical profile, schedule data | computed outputs |
| `tax-validation-service` | readiness checks | profile + calc outputs | errors, warnings, pass/fail |
| `clarification-graph-service` | next question + explanation | current profile, missing fields | prompts, explanations |
| `doc-recon-service` | document extraction and cross-check | uploaded evidence | extracted facts, conflict set |
| `review-service` | reviewer workflow | case packet | status, notes, escalation |
| `payload-service` | import/export JSON | profile + active pack | portal-compatible JSON |
| `eri-adapter-service` | submission workflows | consented credentials, payload | submission status |

---

## 12. Rules vs AI responsibility split

### Deterministic layer owns
- final ITR selection
- entity type classification
- disqualification logic
- schedule applicability
- mandatory field enforcement
- calculations
- validations
- filing-readiness
- reason codes
- human review triggers

### AI / SLM layer owns
- parsing messy user language
- mapping narrative answers to structured fields
- deciding the smallest next clarification question
- summarizing uploaded documents
- explaining the result in plain language
- preparing a case summary for reviewers
- deciding whether to call a tool when rules request more data

### Hard boundary
The AI layer may **assist**, but it may not override the deterministic engine’s final legal selection.

---

## 13. Agent topology

### Agent 1: Intake normalizer
Goal:
- Convert raw user language and sparse inputs into canonical fields

Allowed tools:
- `validate_pan_format`
- `validate_aadhaar_format`
- `normalize_currency_values`
- `normalize_dates`
- `detect_entity_type`
- `detect_residential_status`
- `compute_income_profile_stub`

### Agent 2: Eligibility clarifier
Goal:
- Ask the minimum number of clarifying questions needed to enable a deterministic decision

Allowed tools:
- `run_itr_eligibility`
- `get_missing_fields`
- `get_disqualification_reasons`
- `retrieve_rule_snippet`
- `question_bank_lookup`
- `resolve_schedule_dependencies`

### Agent 3: Evidence reviewer
Goal:
- Extract facts from uploaded evidence and compare them against user entries

Allowed tools:
- `extract_document_fields`
- `cross_check_user_vs_document`
- `flag_conflicts`
- `build_reviewer_summary`

### Agent 4: Explanation generator
Goal:
- Explain the result and rejected alternatives clearly

Allowed tools:
- `fetch_reason_codes`
- `fetch_rule_trace`
- `generate_plain_language_explanation`
- `generate_reviewer_packet`

### Agent 5: Submission integrator (later)
Allowed tools:
- `eri_login`
- `eri_add_client`
- `eri_prefill`
- `eri_validate_submit_itr`
- `eri_everify`
- `eri_get_acknowledgement`

---

## 14. Model strategy

Start with a small, controlled multi-model pool.

### Recommended starter pool
- **Router / cheap triage**: Qwen3-0.6B
- **Clarification / explanation / structured normalization**: Granite 3.3 2B Instruct
- **Long-context document reviewer**: Qwen3.5-4B
- **Judge / hallucination and response checker**: Granite Guardian 3.3 8B

### Why not start with 8-9 models
- more operational complexity
- more routing risk
- harder evaluation and rollback
- little value before evals are mature

### Model usage policy
- default to smallest viable model
- route to larger model only for document-heavy or ambiguity-heavy tasks
- every model call must produce structured output
- every externally visible explanation should pass a judge check in high-risk flows

---

## 15. Frontend design

The frontend should be built as a **schedule-driven form-pack renderer**, not as one fixed HTML form per ITR.

### Key frontend capabilities
- entity-type-aware onboarding
- progressive disclosure
- schedule activation from backend metadata
- section-level save and resume
- inline validation
- guided clarifications
- evidence upload zones
- review mode
- explanation mode
- reason code display for internal users / reviewer users

### UX principle
The user should feel that the system is asking only relevant questions, not forcing them through all seven ITRs.

---

## 16. Decisioning design

### Decision layers
1. **Entity classification**
2. **Primary ITR eligibility**
3. **ITR disqualification**
4. **Schedule applicability**
5. **Human review decision**
6. **Submission readiness decision**

### Suggested DMN assets
- `entity_type_ay_2026_27`
- `residential_status_ay_2026_27`
- `individual_itr_selection_ay_2026_27`
- `individual_itr_disqualification_ay_2026_27`
- `non_company_itr_selection_ay_2026_27`
- `company_itr_selection_ay_2026_27`
- `schedule_activation_ay_2026_27`
- `human_review_rules_ay_2026_27`
- `submission_readiness_ay_2026_27`

### Rule trace output
Every decision run should return:
- selected ITR
- rejected alternatives
- triggered conditions
- missing conditions
- active legal pack
- active form pack
- active validation pack
- review_required flag
- reason codes

---

## 17. Calculation and validation design

### Calculation engine responsibilities
- income aggregation
- schedule totals
- carry-forward / set-off support
- deductions and relief computations
- tax, surcharge, cess, interest
- payable / refundable outcomes

### Validation engine responsibilities
- field-level validation
- schedule-level validation
- cross-schedule validation
- range validation
- mutual exclusivity validation
- pack compatibility validation
- payload export validation

### Output contract
Each validation result should include:
- `severity`: error / warning / info
- `code`
- `message`
- `field_path`
- `schedule_id`
- `blocking`
- `suggested_next_action`

---

## 18. Data model (high level)

### Core entities
- `user`
- `tax_profile`
- `draft_return`
- `decision_run`
- `reason_code`
- `legal_pack`
- `form_pack`
- `validation_pack`
- `document_asset`
- `document_extraction`
- `review_case`
- `submission_attempt`
- `audit_event`

### Canonical tax profile structure
```json
{
  "assessment_year": "2026-27",
  "entity_type": "individual|huf|firm|llp|company|trust|society|aop|boi|local_authority|other",
  "residential_status": "resident|rnor|non_resident",
  "income_heads": {
    "salary": {},
    "house_property": [],
    "business_profession": {},
    "capital_gains": {},
    "other_sources": {},
    "agricultural_income": {}
  },
  "special_flags": {
    "director_in_company": false,
    "unlisted_equity_held": false,
    "foreign_assets": false,
    "foreign_income": false,
    "esop_tax_deferred": false,
    "brought_forward_losses": false,
    "presumptive_taxation": false
  },
  "deductions": {},
  "tax_payments": {},
  "documents": [],
  "consents": {}
}
```

---

## 19. Security, privacy, and governance

This application processes high-sensitivity financial and identity data.

### Required controls
- encryption in transit and at rest
- field-level encryption for PAN, Aadhaar, bank details, and sensitive identifiers
- masked display in UI
- RBAC for taxpayers, reviewers, tax professionals, admins
- consent tracking for prefill and ERI operations
- immutable audit log for decision runs and reviewer actions
- secure file upload scanning
- region-aware storage and retention policies
- model prompt redaction for PII where possible

### Governance principle
No explanation shown to a user should hide the fact that the final selection came from rules and not from free-form AI judgment.

---

## 20. Recommended enterprise stack

### Frontend
- Next.js
- TypeScript
- React
- Zod
- component library of choice for secure enterprise forms

### Backend
- FastAPI
- Pydantic
- Python decision and integration services

### Orchestration / rules
- Camunda 8 for BPMN + DMN where workflow and decision governance matter
- LangGraph for clarification/explanation/evidence graphs
- vLLM for self-hosted open-weight model serving

### Data / infra
- PostgreSQL
- Redis
- object storage for uploaded evidence
- Kubernetes
- KEDA
- OpenTelemetry
- centralized logs + metrics + trace backend

### Why this stack
It gives:
- deterministic decisioning,
- stateful workflow orchestration,
- swappable model serving,
- strong API contracts,
- and enterprise-grade deployment patterns.

---

## 21. API design sketch

### Classification flow
- `POST /drafts`
- `PATCH /drafts/{id}/profile`
- `POST /drafts/{id}/classify`
- `GET /drafts/{id}/result`

### Clarification flow
- `POST /drafts/{id}/clarify/next-question`
- `POST /drafts/{id}/clarify/answer`

### Document flow
- `POST /drafts/{id}/documents`
- `POST /drafts/{id}/documents/reconcile`

### Review flow
- `POST /drafts/{id}/review-case`
- `POST /review-cases/{id}/approve`
- `POST /review-cases/{id}/request-info`

### Filing readiness flow
- `POST /drafts/{id}/validate`
- `POST /drafts/{id}/export-json`

### ERI flow (later)
- `POST /eri/login`
- `POST /eri/add-client`
- `POST /eri/prefill`
- `POST /eri/submit`
- `POST /eri/everify`
- `GET /eri/acknowledgement`

---

## 22. Observability requirements

Track at least:

### Business metrics
- classification success rate
- human review rate
- clarification question count per completed case
- document conflict rate
- pack-version usage

### Technical metrics
- latency per service
- token usage per model
- tool call success rate
- validation failure categories
- ERI adapter failure rates

### Audit trace requirements
Every case should answer:
- what inputs were used,
- which rules were evaluated,
- which model was called,
- which tools were invoked,
- why the final ITR was chosen,
- and why any case was escalated.

---

## 23. Phase-wise build plan

### Phase 0 — Foundation and pack ingestion
Goal:
- establish trustworthy foundations before classification logic is exposed to end users

Deliverables:
- legal-pack registry
- form-pack registry
- validation-pack registry
- field dictionary
- schedule registry
- uploaded workbook structural analysis
- current-year official pack ingestion pipeline
- canonical tax profile schema
- audit/event schema

Exit criteria:
- all active rule packs are versioned
- source-of-truth hierarchy is encoded
- current-year production pack is identifiable

### Phase 1 — ITR classification MVP
Goal:
- deterministic selection of ITR-1 to ITR-7 with explanation and review triggers

Deliverables:
- guided intake UI
- normalization service
- entity and residential status decisions
- ITR eligibility decisions
- reason codes
- clarification graph
- review queue
- minimal admin/reviewer dashboard

Exit criteria:
- system can classify the correct ITR for golden test cases
- system explains why a simpler or alternative ITR was rejected
- system never silently guesses under ambiguity

### Phase 2 — Schedule activation and filing-readiness
Goal:
- activate relevant schedules and identify what remains missing for a filing-ready state

Deliverables:
- schedule applicability engine
- schedule-driven frontend renderer
- deterministic calculations for in-scope schedules
- validation engine
- filing-readiness report

Exit criteria:
- each active case shows required schedules, missing fields, and blocking issues

### Phase 3 — Document-assisted classification and reconciliation
Goal:
- use uploaded evidence to reduce manual input and improve confidence

Deliverables:
- document ingestion
- extraction pipelines
- cross-check engine
- evidence conflict UI
- reviewer packet generation

Exit criteria:
- the system can extract and compare key facts from supported document types
- evidence conflicts trigger review correctly

### Phase 4 — JSON export and prefill
Goal:
- produce portal-compatible payloads without yet tightly coupling submission

Deliverables:
- prefill JSON import
- portal JSON generation
- payload validation against active pack
- draft import/export compatibility tests

Exit criteria:
- export is pack-valid and reproducible
- prefill import merges safely with user-entered data

### Phase 5 — ERI / submission integration
Goal:
- support consented submission workflows where business model and compliance allow

Deliverables:
- consent management
- ERI adapter
- submission workflow
- e-verify flow
- acknowledgement retrieval

Exit criteria:
- end-to-end submission succeeds in controlled environments
- all integration steps are auditable and reversible at the workflow level

### Phase 6 — Production hardening
Goal:
- move from feature completeness to operational reliability

Deliverables:
- scale testing
- pack rollover runbooks
- drift detection
- rollback strategies
- security hardening
- SRE playbooks
- compliance audit artifacts

---

## 24. Human review triggers

Hard-code review triggers for at least:

- foreign assets or foreign income
- ambiguous residency
- trust / exempt / political party / institution cases
- unclear entity type
- business vs profession ambiguity
- presumptive taxation ambiguity
- document-vs-user-input mismatch
- capital gains edge cases
- carry-forward / brought-forward loss complexity
- incomplete or conflicting mandatory disclosures
- low-confidence AI extraction
- mixed legal-pack / pack-resolution conflicts

The right failure mode is **pause and escalate**, not **guess and proceed**.

---

## 25. Testing strategy

### Golden datasets
Create curated case sets for:
- salaried resident individuals
- resident individuals with disqualifiers
- HUF without business income
- individuals with business/profession income
- presumptive taxation cases
- firm vs LLP cases
- AOP/BOI/trust/entity cases
- domestic company
- foreign company
- exempt/institutional ITR-7 cases

### Tests required
- rule tests
- pack-version tests
- API contract tests
- UI schedule activation tests
- extraction reconciliation tests
- end-to-end workflow tests
- regression tests for every legal/form pack update

---

## 26. Key delivery risks and mitigations

### Risk: relying on help pages alone
Mitigation:
- use source-of-truth hierarchy and pack registry

### Risk: mixed-year utility inputs
Mitigation:
- only current-year packs can power production decisions and validations

### Risk: agent overreach
Mitigation:
- deterministic authority and tool scopes

### Risk: portal pack changes
Mitigation:
- form-pack ingestion service + versioned rollout

### Risk: user fatigue from long questionnaires
Mitigation:
- clarification graph asks the smallest next question

### Risk: tax-sensitive hallucination in explanations
Mitigation:
- reason codes + judge model + reviewer escalation

---

## 27. Definition of done for the platform

The platform is “done” for a phase only when:

- the active legal/form/validation pack is explicit,
- deterministic outputs are traceable,
- explanations are tied back to reason codes,
- pack changes do not silently break prior behavior,
- and high-risk ambiguity routes to review rather than silent automation.

---

## 28. Immediate next implementation artifacts to create

After this v2 architecture, the next concrete artifacts should be:

1. field inventory and canonical schema
2. decision tables for entity + ITR selection
3. schedule registry
4. API contracts
5. database schema
6. review trigger rules
7. clarification graph nodes
8. golden test cases
9. pack-ingestion runbook
10. security and consent model

---

## 29. Source appendix

### Official sources used to correct the architecture
- Income Tax Department help: Salaried Individuals for AY 2026-27
- Income Tax Department help: Individual having Income from Business / Profession for AY 2026-27
- Income Tax Department help: Partnership Firm / LLP for AY 2026-27
- Income Tax Department help: AOP / BOI / Trust / AJP for AY 2026-27
- Income Tax Department help: Domestic Company for AY 2026-27
- Income Tax Department help: Foreign Company for AY 2026-27
- Income Tax Department downloads: Income Tax Returns
- Income Tax Department help: Offline Utility for ITRs
- Income Tax Department API specifications / ERI references
- Income Tax India: Income-tax Act, 2025 / Rules, 2026 portal material
- Current portal announcements regarding AY 2026-27 and transition state

### Uploaded files used as structural references
- `Pasted text.txt`
- `ITR1_AY_26-27_V1.0.xlsm`
- `ITR2_AY_26-27_V1.0.xlsm`
- `ITR3_AY 2020_21_PR 5.7.xlsm`
- `ITR4_AY_26-27_V1.0.xlsm`
- `ITR5_AY 2020-21_PR4.8.xlsm`
- `ITR6_2020_PR4.2.xlsm`
- `ITR7_2020_PR3.9.xlsm`


### Reference URLs
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
