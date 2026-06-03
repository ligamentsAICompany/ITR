FROM node:22-slim AS frontend-deps
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:22-slim AS frontend-builder
WORKDIR /frontend
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_BASE_URL=""
ARG NEXT_PUBLIC_AUTH_MODE="demo"
ARG NEXT_PUBLIC_DEMO_AUTH_ENABLED="true"
ARG BACKEND_INTERNAL_URL="http://127.0.0.1:8000"
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NEXT_PUBLIC_AUTH_MODE=${NEXT_PUBLIC_AUTH_MODE}
ENV NEXT_PUBLIC_DEMO_AUTH_ENABLED=${NEXT_PUBLIC_DEMO_AUTH_ENABLED}
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}
COPY --from=frontend-deps /frontend/node_modules ./node_modules
COPY frontend ./
RUN npm run build

FROM node:22-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBUG=false
ENV ENVIRONMENT=demo
ENV AUTH_MODE=demo
ENV PERSISTENCE_BACKEND=sqlite
ENV DATABASE_URL=sqlite:////tmp/itr_demo.db
ENV STORAGE_BACKEND=local
ENV FILING_PROVIDER=mock
ENV FILING_PROVIDER_MODE=mock
ENV ALLOW_LIVE_FILING=false
ENV ALLOW_SANDBOX_PROVIDER_CALLS=false
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ARG BACKEND_INTERNAL_URL="http://127.0.0.1:8000"
ENV BACKEND_INTERNAL_URL=${BACKEND_INTERNAL_URL}

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY demo_data ./demo_data
COPY itr_engine ./itr_engine
COPY scripts/start-fullstack.sh ./scripts/start-fullstack.sh

COPY --from=frontend-builder /frontend/public ./frontend/public
COPY --from=frontend-builder /frontend/.next/standalone ./frontend
COPY --from=frontend-builder /frontend/.next/static ./frontend/.next/static

RUN sed -i 's/\r$//' ./scripts/start-fullstack.sh \
    && chmod +x ./scripts/start-fullstack.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8080}/v1/health || exit 1

CMD ["sh", "./scripts/start-fullstack.sh"]
