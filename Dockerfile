# Stage 1: Build Vite Frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/apps/web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

# Stage 2: Production Runtime
FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    BENCHBOOK_STATIC_DIR=/app/apps/web/dist

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/repair_service /app/services/repair_service
COPY --from=frontend-builder /app/apps/web/dist /app/apps/web/dist

RUN pip install --no-cache-dir -e /app/services/repair_service

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

CMD ["sh", "-c", "exec uvicorn benchbook.interfaces.http.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
