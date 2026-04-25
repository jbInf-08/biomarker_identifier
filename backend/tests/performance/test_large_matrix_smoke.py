"""
Smoke tests for in-memory scalability (no full pipeline / no R).
Run with: pytest tests/performance/test_large_matrix_smoke.py -m slow
"""

import numpy as np
import pytest


@pytest.mark.slow
def test_large_expression_matrix_allocation():
    """Ensure we can allocate and reduce a moderately large matrix (CI-safe)."""
    n_genes = 2000
    n_samples = 400
    rng = np.random.default_rng(42)
    x = rng.lognormal(mean=5.0, sigma=1.0, size=(n_genes, n_samples))
    row_mean = x.mean(axis=1)
    assert row_mean.shape == (n_genes,)
    assert np.isfinite(row_mean).all()


@pytest.mark.slow
def test_large_matrix_correlation_subsample():
    """Pairwise correlation on a subsample of genes (memory-conscious)."""
    n_genes = 500
    n_samples = 200
    rng = np.random.default_rng(0)
    x = rng.normal(size=(n_genes, n_samples))
    sub = x[:50, :]
    c = np.corrcoef(sub)
    assert c.shape == (50, 50)
