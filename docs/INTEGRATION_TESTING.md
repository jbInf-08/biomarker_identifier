## Integration & End-to-End Testing Strategy

This document describes the integration and end-to-end (E2E) testing approach
implemented during Weeks 5–6 to validate complete application workflows.

### Scope

Integration tests focus on:

- End-to-end biomarker identification workflows
- Multi-omics data processing and fusion pipelines
- Clinical annotation and reporting workflows
- Authentication, authorization, and multi-tenant isolation
- Error recovery and resilience scenarios

### Structure

Backend tests are organized under `backend/tests`:

- `tests/integration/` – API and workflow integration tests
- `tests/e2e/` – high-level E2E scenarios that simulate user journeys
- `tests/performance/` – Locust-based performance/load tests

Examples of covered scenarios:

- Upload data → run pipeline → retrieve biomarkers → generate report
- Multi-omics dataset ingestion, fusion, and downstream analysis
- Tenant-scoped operations verifying isolation between tenants
- Authentication + authorization flows for protected routes

### Tooling

- **pytest** for integration and E2E tests
- **pytest-asyncio** for async FastAPI endpoints
- **pytest-cov** for coverage metrics
- **Locust** for performance and load tests

All integration and E2E suites run in CI via the `backend-tests` and
`performance-tests` jobs defined in `.github/workflows/ci.yml`.

