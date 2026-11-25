# syntax=docker/dockerfile:1.7
# AirSense API - FastAPI + trained model. Build context: repository root.
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

# Application code + versioned artefacts (processed data, trained model, evaluation results)
COPY backend/ backend/
COPY data/processed/ data/processed/
COPY data/interim/ data/interim/
COPY data/external/ data/external/
COPY models/ models/
COPY reports/data_quality/ reports/data_quality/
COPY reports/model_results/sarima_daily.json reports/model_results/sarima_daily.json

RUN useradd --create-home --uid 10001 airsense && mkdir -p data/raw && chown -R airsense /app
USER airsense
WORKDIR /app/backend
ENV PYTHONPATH=/app/backend AIRSENSE_ENV=production PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s CMD curl -fsS http://localhost:${PORT}/health || exit 1
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
