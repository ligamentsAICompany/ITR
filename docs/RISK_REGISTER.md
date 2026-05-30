# Risk Register

| Risk | Severity | Mitigation | Owner | Status |
| --- | --- | --- | --- | --- |
| Client assumes demo means live filing is available. | High | Banner, demo script, release notes, and unsupported scope state live filing is disabled. | Product | Open |
| Actual taxpayer data is used in demos. | High | Use `demo_data/` synthetic personas only; require legal/security approval for any real data pilot. | Pilot Lead | Open |
| Sandbox readiness is overstated without approved credentials/specs. | High | Provider diagnostics use `NOT_VERIFIED` until approved sandbox evidence exists. | Engineering | Open |
| AI extraction errors create incorrect filing values. | Medium | Human review required before extracted values are merged. | Reviewer | Open |
| Scanned PDF/OCR quality causes missing fields. | Medium | Prefer structured CSV/XLSX/text samples; document OCR as a limitation. | Product | Open |
| Tax/legal interpretation is treated as advice. | Medium | Position outputs as pilot estimates requiring reviewer/legal review. | Compliance | Open |
| Secrets or credentials are committed. | High | Demo files contain no credentials; sandbox onboarding requires secret manager. | Engineering | Open |
| Audit trail expectations exceed current pilot implementation. | Medium | Document reviewer/admin expectations and make enterprise audit hardening a follow-up. | Product | Open |
| Official schema/export expectations drift. | Medium | Do not change official schema export logic in Phase 13. | Engineering | Mitigated |
