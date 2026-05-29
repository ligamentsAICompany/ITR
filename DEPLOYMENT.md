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
- `CORS_ALLOWED_ORIGINS=https://<frontend-origin>`
- `API_BASE_URL=https://<backend-origin>` when backend-generated links need an external base URL
- `RATE_LIMIT_PER_MINUTE=120` or the approved production limit
- `MAX_REQUEST_BYTES=1048576` or the approved production request limit

Production frontend builds must set:

- `NEXT_PUBLIC_API_BASE_URL=` for full-stack/same-origin deployments so the browser calls `/v1/*`
- `NEXT_PUBLIC_API_BASE_URL=https://<backend-origin>` for split frontend/backend deployments
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
  --set-env-vars "ENVIRONMENT=production,DEBUG=false,API_BASE_URL=$FRONTEND_ORIGIN,CORS_ALLOWED_ORIGINS=$FRONTEND_ORIGIN,RATE_LIMIT_PER_MINUTE=120,MAX_REQUEST_BYTES=1048576"
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
  --set-env-vars "ENVIRONMENT=production,DEBUG=false,API_BASE_URL=$BACKEND_ORIGIN,CORS_ALLOWED_ORIGINS=$FRONTEND_ORIGIN,RATE_LIMIT_PER_MINUTE=120,MAX_REQUEST_BYTES=1048576"

docker build -f frontend/Dockerfile \
  --build-arg "NEXT_PUBLIC_API_BASE_URL=$BACKEND_ORIGIN" \
  --build-arg "BACKEND_INTERNAL_URL=$BACKEND_ORIGIN" \
  -t "gcr.io/$PROJECT_ID/itr-frontend:$TAG" \
  frontend
docker push "gcr.io/$PROJECT_ID/itr-frontend:$TAG"
gcloud run deploy itr-frontend \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --image "gcr.io/$PROJECT_ID/itr-frontend:$TAG" \
  --allow-unauthenticated \
  --set-env-vars "NEXT_PUBLIC_API_BASE_URL=$BACKEND_ORIGIN,BACKEND_INTERNAL_URL=$BACKEND_ORIGIN"
```

After deployment, verify:

```bash
curl -fsS "$BACKEND_ORIGIN/v1/health"
```

The response must include `"environment":"production"`. In the browser, hard
refresh the frontend and verify invalid Aadhaar is blocked before any `/v1/*`
request, valid Aadhaar submits, and blank Aadhaar submits.

## HTTPS

Terminate HTTPS at the ingress, reverse proxy, or load balancer. Keep
`CORS_ALLOWED_ORIGINS` restricted to the deployed frontend origin.

## Redis

Redis is included behind the `future-rate-limit` profile for later distributed
rate limiting:

```bash
docker compose --profile future-rate-limit up --build
```
