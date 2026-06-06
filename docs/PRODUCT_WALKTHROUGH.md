# Product Walkthrough

## Audience

This walkthrough is for client stakeholders, pilot reviewers, and admins
evaluating the platform as an AI-assisted tax filing preparation workflow.

## Workflow

Users enter a taxpayer profile, upload supported demo documents, review extracted
values, run ITR recommendation, validate the profile, compute tax, generate a
draft filing package, create a schema export preview, and inspect mock/sandbox
filing readiness.

## AI Role

AI assists with extraction review and user-facing explanations. It does not
replace reviewer approval, deterministic validation, tax computation, or legal
review.

## Deterministic Rules

ITR recommendation, validation, tax computation, filing package generation, and
readiness gates are controlled by application rules. Higher-risk facts such as
foreign assets, business income, or capital gains are surfaced for reviewer
attention.

## Filing Package And Export

The filing package is a draft artifact for pilot review. Schema export is a
preview of structured filing data and does not change official schema export
logic.

## Mock And Sandbox Readiness

Mock readiness shows whether the workflow can reach the filing handoff stage
without calling live government systems. Sandbox readiness remains unverified
until approved provider specs and credentials are supplied.

## Reviewer Approval

Reviewers inspect validation issues, tax computation summaries, package warnings,
and provider diagnostics before approving a pilot package. Live submission is not
available in this phase.

## What Clients Can Test Today

- Synthetic persona walkthroughs in `demo_data/`.
- Document upload and extraction review using CSV samples.
- ITR recommendation and validation.
- Tax computation and draft package generation.
- Schema export preview.
- Mock/sandbox readiness diagnostics with live filing disabled.
