# Supported Scope

## Pilot User Types

- Taxpayer demo users.
- Reviewer users who inspect validation, tax, and package outputs.
- Admin users who review provider diagnostics and pilot readiness.

## Supported ITR Coverage

- ITR-1: salaried resident individual with simple income.
- ITR-2: individual with capital gains or foreign asset flags requiring review.
- ITR-3: individual/proprietor business income classification for pilot review.
- ITR-4: presumptive business or professional income classification.

Entity classification is limited to pilot workflow support. It is not a complete
enterprise entity filing module.

## Supported Documents

- CSV and XLSX-style structured data.
- Text PDF or Form16-like extracted text where parser support exists.
- AIS-like and Form 26AS-like samples.
- Capital gains statement samples.
- Synthetic files under `demo_data/documents/`.

## Supported Features

- Taxpayer profile capture.
- Demo document upload and extraction review.
- ITR recommendation and explanations.
- Validation report generation.
- Tax computation summary.
- Draft filing package generation.
- Schema export preview.
- Reviewer/admin approval workflow.
- Mock/sandbox filing readiness diagnostics.

## Deployment Mode

Supported deployment for Phase 13 is demo or controlled pilot mode. Live
government filing is disabled.
