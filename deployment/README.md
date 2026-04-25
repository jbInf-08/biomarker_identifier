# Cancer Biomarker Identifier — deployment notes

This folder does **not** ship a separate Compose stack. Use the **repository root** as the source of truth:

| Topic | Document |
|--------|----------|
| First-time local run | [HOW_TO_RUN.md](../HOW_TO_RUN.md) |
| Default stack (`postgres`, `redis`, `migrate`, `backend`, `celery-worker`, `celery-beat`, `flower`, `frontend`) | [docker-compose.yml](../docker-compose.yml) |
| Production-style stack (images, nginx, Prometheus, Grafana) | [docker-compose.prod.yml](../docker-compose.prod.yml) |
| Deployment narrative and CI | [DEPLOYMENT.md](../DEPLOYMENT.md) |
| Detailed deployment patterns | [docs/DEPLOYMENT_GUIDE.md](../docs/DEPLOYMENT_GUIDE.md) |
| Kubernetes examples | [k8s/](../k8s/) |
| Monitoring configs (used by prod compose) | [monitoring/](../monitoring/) |
| Nginx for production compose | [nginx/](../nginx/) |
| Tests | [TESTING_GUIDE.md](../TESTING_GUIDE.md) |

There are **no** Docker Compose “profiles” (`--profile dev`, etc.) in this repository.

## Quick start (from repo root)

```bash
git clone https://github.com/jbInf-08/biomarker_identifier.git
cd biomarker_identifier
docker compose up -d --build
```

- **UI:** http://localhost (default compose)
- **API docs:** http://localhost:8000/docs
- **Flower (Celery):** http://localhost:5555

```bash
docker compose ps
```

## Local API without full Docker stack

See [HOW_TO_RUN.md](../HOW_TO_RUN.md) **Path B**: Postgres + Redis via compose, then `uvicorn` and Celery from `backend/`, and `npm start` from `frontend/`.

## Production

Build/push images as required by `docker-compose.prod.yml` (`BIOMARKER_DOCKER_USERNAME`, secrets, TLS under `nginx/ssl/`). Step-by-step guidance is in [DEPLOYMENT.md](../DEPLOYMENT.md) and [docs/DEPLOYMENT_GUIDE.md](../docs/DEPLOYMENT_GUIDE.md).

## Support

- [README.md](../README.md) (support links)
- [GitHub Issues](https://github.com/jbInf-08/biomarker_identifier/issues)
