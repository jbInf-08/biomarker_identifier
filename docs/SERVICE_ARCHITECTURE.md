## Service Layer Architecture

This document summarizes the service-layer design and the Week 1–2 improvements
described in the weekly progress reports.

### Overview

The backend is organized around a set of focused service modules that encapsulate
business logic and orchestration for the FastAPI routes:

- `clinical_decision_support.py` – clinical annotation and scoring workflows
- `export_service.py` – export to CSV / JSON / Excel / PDF formats
- `monitoring_service.py` – metrics, health checks, and system status
- `cache_service.py` – Redis-backed caching and invalidation
- `celery_service.py` – task submission, tracking, and retries
- `federated_learning_service.py` – scaffolding for federated-learning workflows

Each service is injected into API routes and pipelines rather than accessed
directly, which keeps endpoints thin and testable.

### Responsibilities and Cross-Cutting Concerns

- **Configuration**: services read from the central settings module (Pydantic v2)
  and avoid hard-coded constants.
- **Logging**: all services use the shared logging configuration defined in
  `logging_config.py` for structured JSON logs.
- **Error handling**: recoverable failures are converted to domain-specific
  exceptions and surfaced as 4xx/5xx responses by the API layer.
- **Background work**: long-running operations are pushed into Celery tasks via
  `celery_service.py` and monitored by `monitoring_service.py`.

### Testing Strategy

Service modules have dedicated unit tests that:

- Mock external APIs (Redis, Celery, third‑party services)
- Cover success, error, and edge‑case paths
- Target ≥85% line coverage for each service

These tests are executed as part of the backend CI job (`backend-tests`), with
coverage reported via pytest‑cov and uploaded as HTML and XML reports.

