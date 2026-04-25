## Automated Model Selection

This document describes the automated model comparison and selection
capabilities referenced in the Week 6 report.

### Overview

The ML pipeline supports multiple classical and advanced models (see
`backend/app/ml_models`). Automated model selection is responsible for:

- Training a collection of candidate models on the same dataset
- Evaluating them with consistent cross-validation
- Recording performance metrics
- Selecting and persisting the best-performing configuration

### Current Implementation

- The selection logic is orchestrated in the ML pipeline modules
  (`ml_pipeline.py`, `model_training.py`, and `feature_selection.py`).
- Hyperparameter search is implemented via pluggable backends:
  - Grid / random search using scikit-learn tools
  - Hooks are provided for more advanced optimizers (e.g., Optuna) without
    making them a hard dependency.
- Model performance metrics (AUC, accuracy, F1, etc.) are stored alongside
  biomarker results for later inspection.

### Extensibility

- Additional search strategies (e.g., Bayesian optimization) can be enabled
  by:
  - Implementing a small adapter that yields candidate parameter sets
  - Plugging it into the existing training/evaluation loop
- Ensemble strategies such as voting and stacking can be layered on top of
  the selected base models.

This file documents behavior at a high level so that the Week 6 narrative is
reflected in the repository, even as specific algorithms and libraries may
evolve over time.

