# Production readiness (implemented)

## Runtime vs development (Python / Docker)

- `backend/requirements-prod.txt` — production runtime only (no pytest, linters).
- `backend/requirements-dev.txt` — includes `-r requirements-prod.txt` plus tests and linters.
- `backend/requirements.txt` — defaults to `-r requirements-dev.txt` for local/CI.
- `backend/Dockerfile` — multi-stage: `production` target installs **only** `requirements-prod.txt`; Python **3.11** matches CI (`.github/workflows/ci.yml`).

## Database

- **Alembic** is the source of truth for PostgreSQL: `migrate` service in Compose runs `alembic upgrade head` before API/Celery; the app skips `create_all` on startup when using PostgreSQL without `DEBUG`.
- **Connection pool**: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` in `app/core/config.py` and `app/core/database.py`.
- **Backups**: `scripts/ops/backup_postgres.sh`, `restore_postgres.sh`, `verify_backup.sh` (schedule via cron or your orchestrator).

## TLS / edge / network isolation

- `nginx/nginx.prod.conf` — reverse proxy to `backend:8000` and `frontend:80`.
- `docker-compose.prod.yml` — Postgres and Redis have **no** host port mappings; only nginx (and optional monitoring) publish ports on the host.

## CI/CD

- `.github/workflows/ci.yml` — lint, tests, Semgrep (non-blocking), Bandit (blocking), Alembic migration step, **docker-verify** (build `production` image + Trivy table report), optional Docker Hub push, deployment gated on `docker-verify`.

## Observability

- `LOG_JSON` — JSON logs + `CorrelationIdMiddleware` (`X-Request-ID`) and `CorrelationIdFilter` in `app/utils/logging_config.py`.
- Prometheus scrape list trimmed to the backend job by default; optional exporters documented in `monitoring/prometheus.yml`.
- Alert rules in `monitoring/alert_rules.yml` focus on HTTP metrics and backend `up`; node/postgres/redis rules are commented until exporters exist.

## Celery / Redis

- Redis: AOF enabled in Compose (`redis-server --appendonly yes`) and in `k8s/redis.yaml` ConfigMap.
- Celery: broker/backend use `REDIS_URL`, retries, `task_reject_on_worker_lost`, transport options in `app/services/celery_service.py`.

## Kubernetes

- `k8s/backend.yaml` — liveness `/health/live`, readiness `/health/ready`.
- `k8s/backend-hpa.yaml` — CPU/memory HPA (requires metrics-server).

## Security

- `.github/dependabot.yml` — weekly pip/npm/GitHub Actions updates.
- CI runs Bandit, Semgrep, pip-audit/safety artifacts, Trivy on the built image.
