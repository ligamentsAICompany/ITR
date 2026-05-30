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
- `ALLOW_LIVE_FILING=false` unless live filing has explicit written approval

Do not deploy production with `AUTH_MODE=demo` unless a temporary controlled
acceptance environment explicitly sets `ALLOW_DEMO_AUTH_IN_PRODUCTION=true`.
Production startup rejects wildcard CORS, `DEBUG=true`, missing PostgreSQL URLs,
missing GCS bucket names, missing JWT/Google provider configuration, and
localhost public API URLs.

## ERI Provider Configuration

Phase 9 only prepares the ERI integration foundation. Mock filing remains the
default and live filing is blocked unless all of these are true:

- `FILING_PROVIDER=eri_live`
- `FILING_PROVIDER_MODE=live`
- `ALLOW_LIVE_FILING=true`
- `ENVIRONMENT=production`
- All required ERI configuration values are present

Sandbox mode uses `FILING_PROVIDER=eri_sandbox` and
`FILING_PROVIDER_MODE=sandbox`. It still requires provider configuration, but
the Phase 9 adapter returns mocked sandbox responses when official ERI sandbox
transport is unavailable. Tests must not call live government or ERI endpoints.

Store provider secrets in Secret Manager, not in source files or `.env`
commits:

- `ERI_CLIENT_SECRET`
- `ERI_PRIVATE_KEY_SECRET_NAME`
- certificate/private-key material referenced by `ERI_CERT_PATH` or a future
  provider-specific secret

Non-secret provider values can be configured as environment variables:

- `ERI_BASE_URL`
- `ERI_TOKEN_URL`
- `ERI_CLIENT_ID`
- `ERI_CALLBACK_URL`
- `ERI_TIMEOUT_SECONDS`
- `ERI_RETRY_COUNT`
- `ERI_STATUS_POLL_INTERVAL_SECONDS`

Provider callback signatures are verified with configured provider secret
material. Unsigned callbacks fail closed in production unless a controlled
acceptance environment explicitly sets `ALLOW_UNSIGNED_PROVIDER_CALLBACKS=true`.
Do not log raw provider payloads, tokens, PAN/Aadhaar, certificate contents, or
internal storage paths. If raw provider payload retention is required later,
store it only in encrypted, access-controlled storage with a dedicated retention
policy.

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
