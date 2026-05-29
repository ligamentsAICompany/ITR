# Production Deployment

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

## HTTPS

Terminate HTTPS at the ingress, reverse proxy, or load balancer. Keep
`CORS_ALLOWED_ORIGINS` restricted to the deployed frontend origin.

## Redis

Redis is included behind the `future-rate-limit` profile for later distributed
rate limiting:

```bash
docker compose --profile future-rate-limit up --build
```
