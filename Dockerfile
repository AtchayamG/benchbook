FROM python:3.11-slim as base

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8001

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY services/repair_service /app/services/repair_service

RUN pip install --no-cache-dir -e /app/services/repair_service

EXPOSE 8001

CMD ["uvicorn", "benchbook.interfaces.http.app:app", "--host", "0.0.0.0", "--port", "8001"]
