# Sandbox Credential Onboarding

Phase 12 prepares the Liga AI Tax Platform for approved ERI sandbox pilots only.
It does not enable live filing, submit real tax returns, or call live government
endpoints.

## Approved Sandbox Credential Checklist

- [ ] Provider/ERI agreement approved.
- [ ] Sandbox API specs received, including base URL, token/auth endpoint,
  callback URL, signing requirements, payload format, and status codes.
- [ ] E-verification support confirmed, or marked unsupported in the provider spec.
- [ ] Acknowledgement support confirmed, or marked unsupported in the provider spec.
- [ ] Required credential names identified without storing values in source.
- [ ] Credentials stored in Secret Manager.
- [ ] Cloud Run runtime service account granted secret access only to required
  sandbox secrets.
- [ ] Callback URL registered with the provider.
- [ ] Callback signing configured and fail-closed.
- [ ] Non-secret sandbox provider spec registered with
  `python -m app.tools.register_provider_spec --file sandbox_provider_spec.json`.
- [ ] Secret access verified with `python -m app.tools.verify_secrets`.
- [ ] Sandbox contract tests run with
  `python -m app.tools.run_provider_contract_tests --provider eri --mode sandbox`.
- [ ] Sandbox submit smoke test run with `python -m app.tools.run_sandbox_smoke`.
- [ ] Status check verified against the approved sandbox, or marked `NOT_VERIFIED`.
- [ ] E-verification verified, or marked unsupported.
- [ ] Acknowledgement verified, or marked unsupported.
- [ ] No real taxpayer data used in sandbox tests.

## Safe Spec File

The provider spec file must contain no secrets. Allowed fields include
`provider_name`, `provider_mode`, `spec_version`, `base_url`, `token_url`,
`callback_url`, `supported_operations`, `auth_type`, `signature_type`,
`payload_format`, and `status_mapping_version`.

Reject any field or value that looks like a credential, token, password, private
key, API key, or secret. Store all values that authenticate the application in
Secret Manager instead.

## Verification Policy

If approved sandbox credentials or specs are unavailable, mark sandbox execution
as `NOT_VERIFIED`. Do not fake success, do not claim real provider verification,
and do not use real taxpayer PAN/Aadhaar or raw document text in test payloads.

Client pilot readiness means the app is ready for a controlled sandbox/demo
acceptance gate. Client pilot readiness does not mean live filing is enabled.
