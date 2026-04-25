# Product roadmap and status

**Last updated:** April 2026

This file is the **single place** the README and maintenance docs point to for product themes and how they map to the current codebase. Update it when delivery priorities or implementation status change.

## Quick links

| Topic | Where |
|--------|--------|
| Run the app locally | [HOW_TO_RUN.md](../HOW_TO_RUN.md) (repo root) |
| Operations cadence, maintenance | [MAINTENANCE_ROADMAP.md](MAINTENANCE_ROADMAP.md) |
| Federated / MPC research direction | [FEDERATED_FULL_MPC_ROADMAP.md](FEDERATED_FULL_MPC_ROADMAP.md) |
| Deployment | [DEPLOYMENT.md](../DEPLOYMENT.md) · [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) |
| API surface | [API_DOCUMENTATION.md](API_DOCUMENTATION.md) and `/docs` on a running server |

## Themes (from README, still accurate)

- Multi-tenant foundation (`tenant_id` on users, tenant API routes, policy helpers)
- Advanced ML, stability / consensus scoring, and pathway context
- Real-time pipeline progress (WebSockets under `/api/ws/...`)
- Versioned HTTP APIs: `/api/v1/...` and `/api/v2/...` (legacy `/api/...` retained)
- Optional observability: Prometheus (`/metrics`), Grafana when included in `docker-compose.prod.yml`
- Federated learning routes and capability advertising (`/api/v1/federated/capabilities` — see code)
- Integrations and research project routes under `/api/v1/integrations`, `/api/v1/research`, etc.

## Current implementation snapshot

- **Containers:** `docker-compose.yml` (dev-friendly: Postgres 13 on host port **5433**, backend **8000**, frontend **80**, optional Flower **5555**, Celery beat). `docker-compose.prod.yml` is production-oriented (Nginx, Prometheus, Grafana, scaled workers) and expects images from `${BIOMARKER_DOCKER_USERNAME}/...`.
- **Celery app:** Workers use `celery -A app.services.celery_service:celery_app` (see Compose files). An older `app.core.celery_app` module exists; **Compose and tests expect the service app.**
- **User model:** `User` has `email`, `name`, `hashed_password`, `role` (e.g. `researcher` / `admin`), optional `institution` and `tenant_id` — not a separate `username` or `is_admin` flag.
- **Health:** Liveness/readiness: `GET /health/live`, `GET /health/ready`, `GET /health`. App summary: `GET /api/status`. Richer JSON: `GET /api/v1/system/health` and `GET /api/v2/system/health`.
- **WebSockets (progress):** `WS /api/ws/progress/{run_id}` (and related routes in `app/websocket/routes.py`).
- **Tests:** Backend uses `backend/pytest.ini` (`[pytest]`). Frontend Jest global thresholds are defined in `frontend/package.json` (`jest.coverageThreshold`) and are not the same as legacy “70%” README text — check that file for the current gate.

## What this file is not

It does not replace runbooks, compliance checklists, or the detailed deployment steps in the repo; use the linked documents for those.
