# Phase 13 Demo Data

All files in this folder are synthetic and created only for client demo and pilot
workflow validation. They are not actual taxpayer records, do not contain
credentials, and must not be used for live government filing.

## Contents

- `personas/`: fake taxpayer personas covering ITR-1, ITR-2, ITR-3, and ITR-4
  pilot scenarios.
- `documents/`: small CSV samples that resemble Form 16, AIS, Form 26AS, and
  capital gains extracts.
- `expected_outputs/`: expected demo workflow outcomes for recommendation,
  validation, tax summary, package generation, schema export, and mock filing
  readiness.

## Safety Rules

- Use these records only in demo, test, or approved pilot sandbox workflows.
- Do not mix these files with actual client taxpayer data.
- Live government filing, real e-verification, payment, and acknowledgement
  retrieval remain disabled.
- Demo loader utilities print safe summaries only and do not seed production
  databases.
