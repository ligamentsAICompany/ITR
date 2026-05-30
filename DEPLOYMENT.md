# Production Deployment

## Single-Container Cloud Run Deployment

The root `Dockerfile` builds a full-stack container:

- Next.js frontend is served at `/`
- FastAPI backend runs inside the same container
- API traffic is proxied through the frontend server at `/v1/*`

This is the correct Dockerfile to use when deploying one Cloud Run service:

```bash
docker build -t itr-platform .
docker run --rm -p 8080:8080 itr-platform
```

Open:

- Frontend: `http://localhost:8080`
- Backend health through the same service: `http://localhost:8080/v1/health`

## Backend-Only Dockerfile

`Dockerfile.backend` is retained for backend-only deployments and for Docker Compose.

```bash
docker build -f Dockerfile.backend -t itr-backend .
docker run --rm -p 8000:8000 itr-backend
```

## Local Docker Compose

```bash
docker compose up --build
```

Open:

- Frontend: `http://localhost:3000`
- Backend health: `http://localhost:8000/v1/health`

## Production Environment

Production deployments must set these backend runtime values:

- `ENVIRONMENT=production`
- `DEBUG=false`
- `AUTH_MODE=jwt` for a production JWT/OIDC provider, or `AUTH_MODE=google` for Google Identity once configured
- `JWT_ISSUER`, `JWT_AUDIENCE`, and either `JWT_JWKS_URL` or `JWT_SECRET` when `AUTH_MODE=jwt`
- `PERSISTENCE_BACKEND=postgres`
- `DATABASE_URL` from Secret Manager, for PostgreSQL or Cloud SQL
- `STORAGE_BACKEND=gcs`
- `GCS_BUCKET_NAME=<private-bucket>`
- `CORS_ALLOWED_ORIGINS=https://<frontend-origin>`
- `API_BASE_URL=https://<backend-origin>` when backend-generated links need an external base URL
- `RATE_LIMIT_PER_MINUTE=120` or the approved production limit
- `MAX_REQUEST_BYTES=1048576` or the approved production request limit
- `MAX_UPLOAD_BYTES=10485760` or the approved upload limit
- `FILING_PROVIDER=mock` unless an approved ERI sandbox/live rollout is being tested
- `FILING_PROVIDER_MODE=mock`, `sandbox`, or `live`
- `SECRET_BACKEND=env` for local/demo or `SECRET_BACKEND=gcp_secret_manager` for Cloud Run
- `GCP_PROJECT_ID=<project>` when `SECRET_BACKEND=gcp_secret_manager`
- `ALLOW_SANDBOX_PROVIDER_CALLS=false` unless controlled sandbox execution is approved
- `ALLOW_LIVE_FILING=false` unless live filing has explicit written approval
- `LIVE_FILING_APPROVAL_TICKET`, `LIVE_FILING_APPROVED_BY`, and
  `LIVE_FILING_APPROVED_AT` when `ALLOW_LIVE_FILING=true`

Do not deploy production with `AUTH_MODE=demo` unless a temporary controlled
acceptance environment explicitly sets `ALLOW_DEMO_AUTH_IN_PRODUCTION=true`.
Production startup rejects wildcard CORS, `DEBUG=true`, missing PostgreSQL URLs,
missing GCS bucket names, missing JWT/Google provider configuration, and
localhost public API URLs.

## ERI Provider Configuration

Phase 11 adds controlled ERI sandbox execution without enabling live filing by default.
Mock filing remains the default and live filing is blocked unless all of these
are true:

- `FILING_PROVIDER=eri_live`
- `FILING_PROVIDER_MODE=live`
- `ALLOW_LIVE_FILING=true`
- `LIVE_FILING_APPROVAL_TICKET`, `LIVE_FILING_APPROVED_BY`, and
  `LIVE_FILING_APPROVED_AT` are set
- `ENVIRONMENT=production`
- All required ERI configuration values are present

Sandbox mode uses `FILING_PROVIDER=eri_sandbox` and
`FILING_PROVIDER_MODE=sandbox`. Sandbox/live modes require an active provider
spec plus Secret Manager-backed credentials. Sandbox provider calls are blocked
unless `ALLOW_SANDBOX_PROVIDER_CALLS=true`; live provider calls remain blocked
unless the live approval metadata is complete and `ALLOW_LIVE_FILING=true`.
Tests must not call live government or ERI endpoints.

Store provider secrets in Secret Manager, not in source files or `.env`
commits:

- `ERI_CLIENT_SECRET`
- `ERI_CLIENT_ID_SECRET_NAME`
- `ERI_CLIENT_SECRET_SECRET_NAME`
- `ERI_PRIVATE_KEY_SECRET_NAME`
- `ERI_CERT_SECRET_NAME`
- `ERI_SANDBOX_CLIENT_ID_SECRET_NAME`
- `ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME`
- `ERI_SANDBOX_PRIVATE_KEY_SECRET_NAME`
- `ERI_SANDBOX_CERT_SECRET_NAME`
- certificate/private-key material referenced by `ERI_CERT_PATH` or a future
  provider-specific secret

Non-secret provider values can be configured as environment variables:

- `ERI_BASE_URL`
- `ERI_TOKEN_URL`
- `ERI_CLIENT_ID`
- `ERI_CALLBACK_URL`
- `ERI_TIMEOUT_SECONDS`
- `ERI_RETRY_COUNT`
- `ERI_RETRY_BACKOFF_SECONDS`
- `ERI_STATUS_POLL_INTERVAL_SECONDS`
- `STORE_PROVIDER_RAW_PAYLOADS=false`
- `PROVIDER_RAW_PAYLOAD_RETENTION_DAYS=30`

Provider callback signatures are verified with configured provider secret
material. Unsigned callbacks fail closed in production unless a controlled
acceptance environment explicitly sets `ALLOW_UNSIGNED_PROVIDER_CALLBACKS=true`.
Do not log raw provider payloads, tokens, PAN/Aadhaar, certificate contents, or
internal storage paths. If raw provider payload retention is required later,
store it only in encrypted, access-controlled storage with a dedicated retention
policy.

### ERI Sandbox Setup

1. Create an active provider spec for provider `eri` and mode `sandbox` with
   non-secret values only: base URL, token URL, callback URL, supported
   operations, auth type, signature type, payload format, and status mapping
   version.
2. Store sandbox credentials in Secret Manager or environment-backed secrets:
   `ERI_SANDBOX_CLIENT_ID_SECRET_NAME`,
   `ERI_SANDBOX_CLIENT_SECRET_SECRET_NAME`, and any certificate/private-key
   secret reference required by the approved provider spec. For local demo only,
   `SECRET_BACKEND=env` reads those secret-name values as environment variable
   names.
3. Keep `ALLOW_LIVE_FILING=false`.
4. Set `ALLOW_SANDBOX_PROVIDER_CALLS=true` only for controlled sandbox execution.
5. Run provider contract tests. If real sandbox credentials are unavailable,
   the result must remain `NOT VERIFIED`; do not mark real provider contracts
   as passed.
6. Verify `/v1/filing/provider-diagnostics` shows safe fields only and does not
   include raw provider payloads, PAN/Aadhaar, credentials, or internal paths.

### Live Rollout Control Checklist

Live filing cannot be enabled until every item below is complete:

- Signed provider/ERI agreement complete.
- Legal approval complete.
- Compliance approval complete.
- Senior engineering approval complete.
- Production credentials and signing material provisioned in Secret Manager.
- Cloud Run service account has secret access scoped to the required provider
  secrets only.
- Active live provider spec approved.
- Callback signature verification enabled and fail-closed in production.
- Sandbox contract tests passed against approved credentials.
- Monitoring and alerting configured.
- Rollback tested.
- Incident owner assigned.
- `LIVE_FILING_APPROVAL_TICKET`, `LIVE_FILING_APPROVED_BY`, and
  `LIVE_FILING_APPROVED_AT` set to the approved rollout record.
- `ALLOW_LIVE_FILING=true`, `FILING_PROVIDER=eri_live`,
  `FILING_PROVIDER_MODE=live`, and `ENVIRONMENT=production` are set only for
  the approved production rollout.

If `ALLOW_LIVE_FILING=true` is set without the approval metadata above, startup
fails safely. Diagnostics also report live filing as disabled until the approval
metadata and provider configuration are complete.

### Secret Manager Requirements

Store all credentials and private material in Secret Manager. The runtime
service account needs `roles/secretmanager.secretAccessor` scoped only to the
specific ERI, database, JWT, and certificate secrets it must read. Never commit
provider credentials, private keys, certificate contents, tokens, or `.env`
files.

### Required IAM Roles

- Runtime service account: `roles/cloudsql.client` for Cloud SQL PostgreSQL.
- Runtime service account: object create/read/delete permissions scoped to the
  private GCS bucket.
- Runtime service account: `roles/secretmanager.secretAccessor` scoped to
  approved secrets only.
- Deployer: Artifact Registry writer plus Cloud Run deployer/admin permissions.
- Operators: read access to logs/audit dashboards without access to raw
  provider payloads or secrets.

### Provider Callback URL Setup

Configure provider callback URLs to point to
`/v1/filing/provider-callbacks/{provider}` where provider is `eri_sandbox` or
`eri_live`. Use HTTPS only. Register the exact callback URL in the provider
portal and in the active provider spec. Callback payloads are parsed and mapped
to internal statuses, but raw callback bodies are not returned from public APIs.

### Callback Signature Config

Production callbacks must be signed. HMAC signatures use
`X-Provider-Signature: sha256=<digest>`. When `X-Provider-Timestamp` and
`X-Provider-Nonce` are present, they are included in verification and replayed
nonce/timestamp pairs are rejected. Unsigned or invalid signatures are rejected
in production unless a controlled acceptance environment explicitly opts into
`ALLOW_UNSIGNED_PROVIDER_CALLBACKS=true`.

### Rollback Plan

1. Set `ALLOW_LIVE_FILING=false`.
2. Switch `FILING_PROVIDER=mock` and `FILING_PROVIDER_MODE=mock` if provider
   traffic must stop immediately.
3. Deactivate the active live provider spec.
4. Redeploy the previous known-good image if application behavior is suspect.
5. Review provider audit events and confirm no unacknowledged live submission
   remains in an ambiguous state.

### Incident Runbook

For provider incidents, preserve audit logs, disable live filing, stop retries
for non-idempotent operations, and notify legal/business owners. Do not expose
raw provider payloads in tickets or chat. Use request IDs, provider mode,
operation, normalized status, retry count, and safe error code for triage.

### Failed Submission Handling

Provider failures map to safe internal statuses and messages. Schema or invalid
payload failures are not retried. Retryable provider unavailability, timeout,
or rate-limit errors may be retried within the configured policy. Do not claim
filed/submitted/verified/acknowledged unless the provider confirms it.

### Duplicate Submission Handling

Duplicate submission responses are treated as non-retryable and require manual
review against provider reference IDs and audit events. Do not submit again
until the provider state is reconciled.

### Rate Limit Handling

Rate-limit responses use `ERI_RETRY_COUNT`, `ERI_RETRY_BACKOFF_SECONDS`, and
provider retry-after guidance when available. Operators should wait for the
provider interval and avoid manual rapid retries.

### Timeout Handling

Timeouts are safe retryable errors for status-like operations. For submission
operations, reconcile provider status before retrying to avoid duplicate
filings.

### Data Retention Policy

`STORE_PROVIDER_RAW_PAYLOADS=false` is the default and production-safe setting.
If raw provider payload retention is approved later, encrypted storage,
restricted IAM, redaction, retention enforcement, and legal approval are
required before enablement.

### Logs / Audit Review Process

Provider observability must include safe fields only: provider, mode,
operation, status, duration, retry count, error code, normalized status,
request ID, and submission ID. Logs and audit events must not include
PAN/Aadhaar, raw document text, raw provider payloads, credentials, or internal
storage paths.

### Legal / Business Approval Checklist

- Legal confirms provider agreement and live filing authority.
- Business owner approves the release window and rollback owner.
- Security approves Secret Manager, IAM, callback signature, and logging setup.
- Senior engineering approves live provider spec and contract-test evidence.
- Support has failed submission, duplicate submission, rate-limit, and timeout
  playbooks ready.

Initialize persistence before first traffic:

```bash
python -m app.db.init_db
```

For Cloud SQL PostgreSQL, run the command from the deployed image with the same
`DATABASE_URL` secret and network access that the service uses.

Production frontend builds must set:

- `NEXT_PUBLIC_API_BASE_URL=` for full-stack/same-origin deployments so the browser calls `/v1/*`
- `NEXT_PUBLIC_API_BASE_URL=https://<backend-origin>` for split frontend/backend deployments
- `NEXT_PUBLIC_AUTH_MODE=jwt` or `google` in production so demo controls are not rendered
- `NEXT_PUBLIC_DEMO_AUTH_ENABLED=false` in production
- `BACKEND_INTERNAL_URL=http://127.0.0.1:8000` for full-stack single-container deployments
- `BACKEND_INTERNAL_URL=https://<backend-origin>` for split frontend/backend deployments

Do not ship a production frontend bundle with `NEXT_PUBLIC_API_BASE_URL` set to
`localhost`, `127.0.0.1`, or a stale backend URL. `NEXT_PUBLIC_*` values are
baked into the client bundle at build time, so rebuild the frontend image after
changing them.

Full-stack/same-origin deployment:

- Leave `NEXT_PUBLIC_API_BASE_URL` empty or unset so the browser calls `/v1/*`
- `BACKEND_INTERNAL_URL` defaults to `http://127.0.0.1:8000`
- If the frontend container should call a separately deployed backend, pass it at build time:

```bash
docker build \
  --build-arg BACKEND_INTERNAL_URL=https://your-backend-service.run.app \
  -t itr-platform .
```

## Cloud Run Deployment Checklist

Set variables for the current project and services:

```bash
PROJECT_ID=your-gcp-project
REGION=asia-south1
TAG=$(git rev-parse --short HEAD)
FRONTEND_ORIGIN=https://your-frontend-service.run.app
BACKEND_ORIGIN=https://your-backend-service.run.app
```

Single Cloud Run service from the root `Dockerfile`:

```bash
docker build -t "gcr.io/$PROJECT_ID/itr-platform:$TAG" .
docker push "gcr.io/$PROJECT_ID/itr-platform:$TAG"
gcloud run deploy itr-platform \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --image "gcr.io/$PROJECT_ID/itr-platform:$TAG" \
  --allow-unauthenticated \
  --service-account "itr-runtime@$PROJECT_ID.iam.gserviceaccount.com" \
  --set-env-vars "ENVIRONMENT=production,DEBUG=false,AUTH_MODE=jwt,API_BASE_URL=$FRONTEND_ORIGIN,CORS_ALLOWED_ORIGINS=$FRONTEND_ORIGIN,RATE_LIMIT_PER_MINUTE=120,MAX_REQUEST_BYTES=1048576,MAX_UPLOAD_BYTES=10485760,PERSISTENCE_BACKEND=postgres,STORAGE_BACKEND=gcs,GCS_BUCKET_NAME=$GCS_BUCKET_NAME,JWT_ISSUER=$JWT_ISSUER,JWT_AUDIENCE=$JWT_AUDIENCE,NEXT_PUBLIC_AUTH_MODE=jwt,NEXT_PUBLIC_DEMO_AUTH_ENABLED=false" \
  --set-secrets "DATABASE_URL=itr-database-url:latest,JWT_JWKS_URL=itr-jwks-url:latest"
```

Split backend/frontend Cloud Run services:

```bash
docker build -f Dockerfile.backend -t "gcr.io/$PROJECT_ID/itr-backend:$TAG" .
docker push "gcr.io/$PROJECT_ID/itr-backend:$TAG"
gcloud run deploy itr-backend \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --image "gcr.io/$PROJECT_ID/itr-backend:$TAG" \
  --allow-unauthenticated \
  --service-account "itr-runtime@$PROJECT_ID.iam.gserviceaccount.com" \
  --set-env-vars "ENVIRONMENT=production,DEBUG=false,AUTH_MODE=jwt,API_BASE_URL=$BACKEND_ORIGIN,CORS_ALLOWED_ORIGINS=$FRONTEND_ORIGIN,RATE_LIMIT_PER_MINUTE=120,MAX_REQUEST_BYTES=1048576,MAX_UPLOAD_BYTES=10485760,PERSISTENCE_BACKEND=postgres,STORAGE_BACKEND=gcs,GCS_BUCKET_NAME=$GCS_BUCKET_NAME,JWT_ISSUER=$JWT_ISSUER,JWT_AUDIENCE=$JWT_AUDIENCE" \
  --set-secrets "DATABASE_URL=itr-database-url:latest,JWT_JWKS_URL=itr-jwks-url:latest"

docker build -f frontend/Dockerfile \
  --build-arg "NEXT_PUBLIC_API_BASE_URL=$BACKEND_ORIGIN" \
  --build-arg "NEXT_PUBLIC_AUTH_MODE=jwt" \
  --build-arg "BACKEND_INTERNAL_URL=$BACKEND_ORIGIN" \
  -t "gcr.io/$PROJECT_ID/itr-frontend:$TAG" \
  frontend
docker push "gcr.io/$PROJECT_ID/itr-frontend:$TAG"
gcloud run deploy itr-frontend \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --image "gcr.io/$PROJECT_ID/itr-frontend:$TAG" \
  --allow-unauthenticated \
  --set-env-vars "NEXT_PUBLIC_API_BASE_URL=$BACKEND_ORIGIN,NEXT_PUBLIC_AUTH_MODE=jwt,NEXT_PUBLIC_DEMO_AUTH_ENABLED=false,BACKEND_INTERNAL_URL=$BACKEND_ORIGIN"
```

Required Google Cloud IAM:

- Runtime service account: `roles/cloudsql.client` for Cloud SQL PostgreSQL.
- Runtime service account: `roles/storage.objectAdmin` scoped to the private GCS bucket, or tighter custom permissions for object create/read/delete.
- Deployer: Artifact Registry writer and Cloud Run admin/developer permissions.
- Secret access: grant the runtime service account `roles/secretmanager.secretAccessor` only for the database/JWT secrets it needs.

Production does not require a `.env` file. Configure non-secret values directly
on Cloud Run and keep `DATABASE_URL`, JWT private signing secrets, and external
provider secret URLs in Secret Manager.

After deployment, verify:

```bash
curl -fsS "$BACKEND_ORIGIN/v1/health"
curl -fsS -X POST "$BACKEND_ORIGIN/v1/uploads" -o /dev/null -w "%{http_code}\n"
```

The health response must include safe fields only: `status`, `api_version`,
`environment`, `persistence_backend`, `storage_backend`, and `auth_mode`.
Unauthenticated protected API calls must return `401`. In the browser, hard
refresh the frontend and verify demo identity controls are absent, invalid
Aadhaar is blocked before any `/v1/*` request, valid Aadhaar submits with real
auth, blank Aadhaar submits, and cross-user artifact access returns `403`.

## HTTPS

Terminate HTTPS at the ingress, reverse proxy, or load balancer. Keep
`CORS_ALLOWED_ORIGINS` restricted to the deployed frontend origin.

## Redis

Redis is included behind the `future-rate-limit` profile for later distributed
rate limiting:

```bash
docker compose --profile future-rate-limit up --build
```
