## Frequently Asked Questions (FAQ)

This FAQ is for new users and support; keep it aligned with the rest of the docs in this folder.

### 1. What data formats are supported?

- Expression and label files in `.csv`, `.tsv`, or `.txt` with tabular data.
- See `USER_MANUAL.md` and `TESTING_GUIDE.md` (repo root) for detailed schemas and test data notes.

### 2. How long does a typical analysis run?

- Depends on dataset size and selected methods.
- For typical gene‑expression cohorts (hundreds of samples), runs usually
  complete in minutes; larger multi‑omics analyses may take longer but are
  executed via background tasks.

### 3. Where can I see the status of my analyses?

- Use the **Dashboard** and **Pipeline Monitoring** pages in the frontend.
- Programmatically, call the status endpoints under `/api/biomarkers/runs/{run_id}/status` or the versioned equivalents under `/api/v1/biomarkers/...` and `/api/v2/biomarkers/...` (same handlers; use `Authorization: Bearer` after login).

### 4. How do I interpret biomarker scores?

- Scores combine statistical significance and model‑based importance.
- The `Results` page and `USER_GUIDE.md` describe how p‑values, fold‑change,
  and model scores fit together.

### 5. What happens if an analysis fails?

- The run is marked as failed and error details are recorded in logs and
  monitoring dashboards.
- Support procedures in `OPERATIONS_AND_RUNBOOKS.md` explain how to triage
  and recover from failures.

### 6. How is test coverage and quality ensured?

- See `TESTING_GUIDE.md` (repo root), `docs/INTEGRATION_TESTING.md`, and
  `docs/CONTRIBUTOR_TESTING_GUIDE.md` for how tests are organized and how to
  run them locally or in CI.

