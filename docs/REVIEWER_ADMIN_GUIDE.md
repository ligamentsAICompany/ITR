# Reviewer And Admin Guide

## Roles

Reviewers validate taxpayer-entered values, extracted document values, ITR
recommendations, validation issues, tax computation summaries, and draft filing
packages. Admins review provider diagnostics, sandbox readiness, and operational
configuration.

## Validation Issues

Issues are shown by severity. Critical and high-severity items should block
approval until corrected or explicitly marked for follow-up within pilot policy.
Conflicts between profile and extracted values require reviewer judgement.

## Filing Package Approval

Reviewers should inspect package status, warnings, draft payload preview, and
artifacts before approval. Use `needs_review` when values require clarification,
reject when the package is unsafe, and request corrections when taxpayer input is
incomplete.

## Tax Computation Review

Review totals, selected regime, warnings, and computation steps. Treat outputs as
pilot estimates derived from approved demo data, not as legal advice.

## Export And Provider Diagnostics

Schema export previews must pass validation before they are considered ready for
pilot handoff. Provider diagnostics should show mock readiness or approved
sandbox readiness without leaking secrets.

## Audit Trail Expectations

For a production-grade pilot, retain who approved values, who generated packages,
which artifacts were reviewed, and why corrections or rejections were issued.
Phase 13 documents these expectations but does not enable live filing.
