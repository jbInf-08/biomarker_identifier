"""
Unit tests for ML feature selection module.
"""

import numpy as np
import pandas as pd
import pytest

from app.ml_models.feature_selection import ConsensusFeatureSelector, FeatureSelector


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    np.random.seed(42)
    n_samples = 100
    n_features = 50

    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f"feature_{i}" for i in range(n_features)],
    )
    y = pd.Series(np.random.randint(0, 2, n_samples))

    return X, y


class TestFeatureSelector:
    """Test FeatureSelector class."""

    def test_init(self):
        """Test FeatureSelector initialization."""
        selector = FeatureSelector(random_state=42, n_jobs=1)
        assert selector.random_state == 42
        assert selector.n_jobs == 1
        assert selector.feature_scores_ == {}
        assert selector.selected_features_ == {}
        assert selector.consensus_scores_ is None

    def test_fit(self, sample_data):
        """Test fitting feature selector."""
        X, y = sample_data
        selector = FeatureSelector(random_state=42, n_jobs=1)

        selector.fit(X, y, methods=["random_forest"], n_features=10)

        assert selector.feature_scores_ != {}
        assert selector.selected_features_ != {}
        assert selector.consensus_scores_ is not None

    def test_get_feature_importance(self, sample_data):
        """Test getting feature importance."""
        X, y = sample_data
        selector = FeatureSelector(random_state=42, n_jobs=1)

        selector.fit(X, y, methods=["random_forest"], n_features=10)
        importance = selector.get_feature_importance()

        assert isinstance(importance, pd.DataFrame)
        assert len(importance) > 0

    def test_transform(self, sample_data):
        """Test transforming data."""
        X, y = sample_data
        selector = FeatureSelector(random_state=42, n_jobs=1)

        selector.fit(X, y, methods=["random_forest"], n_features=10)
        X_transformed = selector.transform(X)

        assert isinstance(X_transformed, pd.DataFrame)
        assert len(X_transformed.columns) == 10


class TestConsensusFeatureSelector:
    """Test ConsensusFeatureSelector class."""

    def test_init(self):
        """Test ConsensusFeatureSelector initialization."""
        selector = ConsensusFeatureSelector(random_state=42, n_jobs=1)
        assert selector.random_state == 42
        assert selector.n_jobs == 1
        assert selector.selector is not None

    def test_fit(self, sample_data):
        """Test fitting consensus feature selector."""
        X, y = sample_data
        selector = ConsensusFeatureSelector(random_state=42, n_jobs=1)

        selector.fit(X, y, n_bootstrap=10, n_features=10)

        assert hasattr(selector, "consensus_results_")
        assert "features" in selector.consensus_results_

    def test_get_consensus_summary(self, sample_data):
        """Test getting consensus summary."""
        X, y = sample_data
        selector = ConsensusFeatureSelector(random_state=42, n_jobs=1)

        selector.fit(X, y, n_bootstrap=10, n_features=10)
        summary = selector.get_consensus_summary()

        assert isinstance(summary, pd.DataFrame)
        assert len(summary) > 0

    def test_transform(self, sample_data):
        """Test transforming data."""
        X, y = sample_data
        selector = ConsensusFeatureSelector(random_state=42, n_jobs=1)

        selector.fit(X, y, n_bootstrap=10, n_features=10)
        X_transformed = selector.transform(X)

        assert isinstance(X_transformed, pd.DataFrame)
        assert len(X_transformed.columns) == 10
