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

## Environment

Backend:

- `API_BASE_URL`
- `DEBUG=false`
- `ENVIRONMENT=production`
- `RATE_LIMIT_PER_MINUTE`
- `MAX_REQUEST_BYTES`
- `CORS_ALLOWED_ORIGINS`

Frontend:

- `NEXT_PUBLIC_API_BASE_URL`

Full-stack/same-origin deployment:

- Leave `NEXT_PUBLIC_API_BASE_URL` empty or unset so the browser calls `/v1/*`
- `BACKEND_INTERNAL_URL` defaults to `http://127.0.0.1:8000`
- If the frontend container should call a separately deployed backend, pass it at build time:

```bash
docker build \
  --build-arg BACKEND_INTERNAL_URL=https://your-backend-service.run.app \
  -t itr-platform .
```

## HTTPS

Terminate HTTPS at the ingress, reverse proxy, or load balancer. Keep
`CORS_ALLOWED_ORIGINS` restricted to the deployed frontend origin.

## Redis

Redis is included behind the `future-rate-limit` profile for later distributed
rate limiting:

```bash
docker compose --profile future-rate-limit up --build
```
