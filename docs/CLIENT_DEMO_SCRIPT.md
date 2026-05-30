# Client Demo Script

## Opening Pitch

Liga AI Tax Platform is an AI-assisted tax filing preparation and pilot workflow
platform with mock/sandbox filing readiness. It helps taxpayers and reviewers
prepare, validate, package, and review filing data before any approved live
provider integration exists.

## Product Positioning

The product demonstrates a controlled preparation workflow: document intake,
AI-assisted extraction, deterministic ITR recommendation, validation, tax
computation, reviewer approval, schema export preview, and mock/sandbox filing
readiness diagnostics.

## What It Does

- Guides users through taxpayer profile capture and document upload.
- Extracts candidate values from safe demo documents for human review.
- Recommends ITR-1, ITR-2, ITR-3, or ITR-4 based on deterministic rules.
- Runs validation and tax computation using the existing engine.
- Builds a draft filing package and export preview for reviewer approval.
- Shows mock/sandbox readiness and provider diagnostics.

## What It Does Not Do

- It does not file real government returns.
- It does not call the Income Tax portal or a live ERI.
- It does not perform live e-verification, payments, or acknowledgement
  retrieval.
- It does not guarantee official filing acceptance without an approved live
  provider and legal review.

## Demo Persona And Data

Use only `demo_data/` synthetic records. Recommended opening persona:
`salaried_it1`, a fake resident salaried user with synthetic Form 16, AIS, and
26AS-like CSV samples. For advanced questions, switch to `freelancer_itr4`,
`foreign_assets_itr2`, or `business_itr3`.

## Step-By-Step Workflow

1. Login or select a demo user. Explain that demo authentication is for pilot
   evaluation only.
2. Open taxpayer profile. Show fake PAN/Aadhaar and confirm that no actual client
   taxpayer data is used.
3. Upload synthetic document samples from `demo_data/documents/`.
4. Review extracted fields. Accept only values the reviewer agrees with.
5. Run ITR recommendation. Explain deterministic rule outputs and escalation
   when higher-risk attributes appear.
6. Run validation. Highlight missing fields, conflicts, and severity ordering.
7. Run tax computation. Present estimated totals as pilot workflow output, not
   legal advice.
8. Generate filing package. Show artifacts, warnings, and reviewer approval
   status.
9. Generate schema export preview. Clarify that official schema export logic is
   unchanged and live filing is disabled.
10. Run filing readiness or mock submission. Show that the mock/sandbox path
    demonstrates readiness only.
11. Open provider diagnostics/pilot readiness. Explain missing sandbox
    credentials/specs as `NOT_VERIFIED` until approved.

## Screen Talking Points

- Profile: "We start with structured data and never require actual taxpayer data
  for this demo."
- Upload: "AI helps extract candidate values; humans approve before use."
- Recommendation: "ITR selection is deterministic and explainable."
- Validation: "Reviewers see blockers before package generation."
- Tax: "The computation panel shows a traceable estimate from approved values."
- Package/export: "Artifacts are draft pilot outputs and not official filing."
- Filing readiness: "Live government filing remains disabled."
- Diagnostics: "Sandbox readiness is transparent; unverified items are not
  hidden."

## Expected Outputs

- Candidate ITR displayed with explanation.
- Validation status and issue list visible.
- Tax computation summary visible.
- Draft filing package generated when validation allows.
- Export preview generated without live submission.
- Mock/sandbox readiness shown with live filing disabled.
- Provider diagnostics visible with safe `NOT_VERIFIED` states when applicable.

## Client Questions

- "Can this file returns today?" No. It prepares and validates data. Live filing
  is disabled until an approved provider integration, credentials, compliance
  review, and production controls are complete.
- "Is the AI deciding tax law?" No. AI assists extraction and explanation.
  Deterministic rules and reviewers control filing decisions.
- "Can we test with our own data?" For pilot demos, use synthetic or explicitly
  approved test data only. Actual taxpayer data requires security, legal, and
  privacy approvals.
- "What happens if sandbox credentials are missing?" Diagnostics show
  `NOT_VERIFIED`; the demo does not fake provider success.

## Objections And Answers

- "This is not live filing." Correct. Phase 13 is a client pilot launch pack for
  preparation and mock/sandbox readiness.
- "OCR may miss scanned PDFs." Correct. CSV/XLSX/text-like samples are best
  supported; scanned OCR is a known limitation.
- "Can this replace tax review?" No. Reviewer/admin approval remains required.

## Closing Pitch

The pilot proves the end-to-end preparation workflow with fake data, transparent
limitations, and no unsafe live filing claims. The next decision is whether the
client wants to run a controlled pilot using approved synthetic or sandbox data.
