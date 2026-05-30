# Deployment Smoke Checklist

## Pre-Deploy

- [ ] Confirm branch contains latest accepted Phase 12 baseline.
- [ ] Confirm no credentials, tokens, private keys, or actual taxpayer data are
  present in source.
- [ ] Confirm environment mode is demo/pilot and live filing remains disabled.
- [ ] Run backend tests, ruff, compileall, frontend tests, build, lint, and audit.

## Application Smoke

- [ ] Open the frontend and verify the pilot-mode banner is visible.
- [ ] Select or confirm demo user context.
- [ ] Enter or load a synthetic taxpayer profile.
- [ ] Upload a synthetic document sample.
- [ ] Review and accept extracted values.
- [ ] Run ITR recommendation, validation, and tax computation.
- [ ] Generate filing package and schema export preview.
- [ ] Open filing readiness and provider diagnostics.
- [ ] Confirm no live government filing, payment, e-verification, or real
  acknowledgement retrieval occurs.

## Privacy Smoke

- [ ] Logs do not contain secrets.
- [ ] Demo screens use fake PAN/Aadhaar only.
- [ ] Provider diagnostics do not print credential values.

## Rollback Checklist

- [ ] Revert deployment to previous known-good image or commit.
- [ ] Disable demo access if unexpected data exposure is suspected.
- [ ] Preserve logs for investigation without exporting sensitive data.
- [ ] Notify pilot owner and document the rollback reason.
