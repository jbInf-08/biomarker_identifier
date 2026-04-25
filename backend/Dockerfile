# Multi-stage build: production uses requirements-prod.txt only (no pytest/linters).
# Python 3.11 aligns with CI (.github/workflows/ci.yml).
#
# Build production image:
#   docker build --target production -t biomarker-backend:prod .
# Development image (tests + linters in image — not for production runtime):
#   docker build --target development -t biomarker-backend:dev .

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    libpq-dev \
    r-base \
    r-base-dev \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libcairo2-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libfreetype6-dev \
    libpng-dev \
    libtiff5-dev \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

RUN R -e "install.packages(c('BiocManager', 'devtools'), repos='https://cran.rstudio.com/')" && \
    R -e "BiocManager::install(c('DESeq2', 'edgeR', 'limma'), update=FALSE, ask=FALSE)" && \
    R -e "install.packages(c('survival', 'survminer', 'ggplot2', 'dplyr', 'RColorBrewer', 'pheatmap', 'VennDiagram'), repos='https://cran.rstudio.com/')"

WORKDIR /app

# --- Production dependencies only ---
FROM base AS deps-prod
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# --- Development / CI image (optional): includes tests + linters ---
FROM base AS deps-dev
COPY requirements-prod.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

FROM deps-prod AS production
COPY . .
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
# Liveness: process responds (orchestrator readiness uses /health/ready)
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

FROM deps-dev AS development
COPY . .
RUN groupadd -r appuser && useradd -r -g appuser appuser \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8000/health/live || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
