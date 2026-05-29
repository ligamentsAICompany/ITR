FROM node:22-slim AS frontend-deps
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

FROM node:22-slim AS frontend-builder
WORKDIR /frontend
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_BASE_URL=""
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
COPY --from=frontend-deps /frontend/node_modules ./node_modules
COPY frontend ./
RUN npm run build

FROM node:22-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV BACKEND_INTERNAL_URL=https://liga-platform-itr-backend-489651394276.us-central1.run.app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY itr_engine ./itr_engine
COPY scripts/start-fullstack.sh ./scripts/start-fullstack.sh

COPY --from=frontend-builder /frontend/public ./frontend/public
COPY --from=frontend-builder /frontend/.next/standalone ./frontend
COPY --from=frontend-builder /frontend/.next/static ./frontend/.next/static

RUN chmod +x ./scripts/start-fullstack.sh

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:${PORT:-8080}/v1/health || exit 1

CMD ["./scripts/start-fullstack.sh"]
