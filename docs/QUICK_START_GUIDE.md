## Quick Start Guide

This guide gives new users a concise path from login to a first biomarker
analysis. For a full local install, see [HOW_TO_RUN.md](../HOW_TO_RUN.md) in
the repository root.

### 1. Access the Application

1. Open the frontend URL provided for your environment.
2. Log in with your assigned credentials (or follow the onboarding flow if
   self‑registration is enabled).

### 2. Prepare Your Data

- **Expression matrix**: genes as rows, samples as columns (`.csv`/`.tsv`).
- **Labels file**: sample ID → phenotype/clinical label (`.csv`/`.tsv`).

See [USER_MANUAL.md](USER_MANUAL.md) (Data requirements) for detailed formats.

### 3. Run a Biomarker Analysis

1. Navigate to the **Data Upload** page.
2. Upload expression and label files.
3. Choose normalization, statistical test, and ML models.
4. Start the pipeline and follow progress on the **Dashboard** / **Pipeline
   Monitoring** pages.

### 4. Review Results

- Open the **Results** view for your run:
  - Inspect ranked biomarkers, p‑values, and effect sizes.
  - Explore charts and pathway/annotation views.
  - Export results (CSV/JSON/Excel/PDF) as needed.

### 5. Get Help

- Use in‑app tooltips and guided tours for contextual help.
- Refer to:
  - [USER_GUIDE.md](USER_GUIDE.md) for feature overviews
  - [FAQ.md](FAQ.md) for common questions
  - [USER_TRAINING_GUIDE.md](USER_TRAINING_GUIDE.md) for longer walkthroughs

