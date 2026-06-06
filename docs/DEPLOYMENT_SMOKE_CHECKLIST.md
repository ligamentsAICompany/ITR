# Deployment Smoke Checklist

## Pre-Deploy

- [ ] Confirm branch contains latest accepted Phase 12 baseline.
- [ ] Confirm no credentials, tokens, private keys, or actual taxpayer data are
  present in source.
- [ ] Confirm demo deployment can boot with no Google Cloud Secrets, GCS, Cloud
  SQL, JWT/OAuth, ERI credentials, sandbox credentials, or government filing
  credentials.
- [ ] Confirm defaults are `ENVIRONMENT=demo`, `AUTH_MODE=demo`,
  `PERSISTENCE_BACKEND=sqlite`, `DATABASE_URL=sqlite:////tmp/itr_demo.db`,
  `STORAGE_BACKEND=local`, `FILING_PROVIDER=mock`,
  `FILING_PROVIDER_MODE=mock`, `ALLOW_LIVE_FILING=false`,
  `ALLOW_SANDBOX_PROVIDER_CALLS=false`, and `DEBUG=false`.
- [ ] Run backend tests, ruff, compileall, frontend tests, build, lint, and audit.

## Application Smoke

- [ ] Open the frontend and verify the pilot-mode banner is visible.
- [ ] Select or confirm demo user context.
- [ ] Enter or load the synthetic taxpayer profile: PAN `ABCDE1234F`, Aadhaar
  `123456789012`, Individual, Resident, Salary `1000000`, PY `2025-26`,
  AY `2026-27`, mandatory filing reason.
- [ ] Confirm `/v1/normalize` returns HTTP 200 and a canonical profile.
- [ ] Upload a synthetic document sample.
- [ ] Review and accept extracted values.
- [ ] Run ITR recommendation, validation, and tax computation; expected
  recommendation is deterministic for the synthetic profile, typically ITR-1.
- [ ] Generate filing package and schema export preview.
- [ ] Open filing readiness and provider diagnostics.
- [ ] Confirm provider is mock, live filing is false, and sandbox calls are false.
- [ ] Confirm no live government filing, payment, e-verification, or real
  acknowledgement retrieval occurs.

## Demo Limitations

- [ ] Data is temporary local demo data and not production durable storage.
- [ ] Demo auth/storage are not production authentication or storage.
- [ ] Real filing, ERI, sandbox execution, e-verification, and acknowledgement
  retrieval are not verified and remain disabled.

## Privacy Smoke

- [ ] Logs do not contain secrets.
- [ ] Demo screens use fake PAN/Aadhaar only.
- [ ] Provider diagnostics do not print credential values.
- [ ] API responses and logs do not expose raw PAN/Aadhaar beyond intentional
  synthetic inputs, raw document text, internal storage paths, Secret Manager
  names, provider tokens, private keys, or certificate material.

## Rollback Checklist

- [ ] Revert deployment to previous known-good image or commit.
- [ ] Disable demo access if unexpected data exposure is suspected.
- [ ] Preserve logs for investigation without exporting sensitive data.
- [ ] Notify pilot owner and document the rollback reason.
