## Pipeline Components

This document describes the core analysis pipeline modules and the enhancements
completed during Weeks 2–3.

### Module Overview

- `io.py` – loading/saving multi‑omics datasets from TSV/CSV/Excel, schema checks
- `qc.py` – quality‑control metrics, outlier detection, and sample/gene filtering
- `normalize.py` – log‑CPM, quantile, z‑score, TMM and related normalization
- `stats.py` – univariate tests, multiple testing correction, effect sizes
- `ml_select.py` – model selection and feature‑importance aggregation
- `pathways.py` – pathway and gene‑set enrichment analysis helpers
- `annotate.py` – annotation hooks into external resources (ClinVar, COSMIC, etc.)
- `report.py` – helpers for producing structured result objects for reporting

These modules are orchestrated by `biomarker_pipeline.py`, which manages
end‑to‑end runs (data loading → QC → normalization → statistics → ML → pathways
→ annotation → report).

### Performance and Reliability

The pipeline implements:

- Parallel execution for selected normalization and statistics steps
- Caching of expensive intermediate computations (e.g., summary statistics)
- Lazy loading of large files to reduce memory footprint
- Robust error handling and recovery at stage boundaries

### Testing

Each pipeline component has focused unit tests and higher‑level integration
tests that exercise realistic workflows:

- Synthetic and small real datasets are used to verify numerical stability
- Edge cases (empty inputs, invalid labels, extreme values) are covered
- Coverage targets of ≥85% per module, contributing to the global coverage
  milestones reported in Weeks 2–3

