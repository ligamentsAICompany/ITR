# Unsupported Scope And Limitations

## Not Supported In Phase 13

- Real government filing or live Income Tax portal submission.
- Live ERI integration.
- Production e-verification.
- Real acknowledgement retrieval.
- Tax payment workflow.
- GST, MCA, or other statutory modules.
- New tax logic, new ITR rules, or tax formula changes.
- Use of actual taxpayer data in demos.

## Provider And Sandbox Limits

Approved sandbox credentials, provider specs, callback rules, and contract tests
must be supplied before sandbox claims can be verified. Until then diagnostics
must remain `NOT_VERIFIED`.

## Document Limits

Structured CSV/XLSX/text-like documents are the safest pilot inputs. OCR for
scanned PDFs can miss fields and should be treated as a future enhancement unless
validated separately.

## Legal And Compliance Limits

The platform is not represented as government-approved, does not guarantee
official filing acceptance, and requires tax/legal review before any production
filing use.
