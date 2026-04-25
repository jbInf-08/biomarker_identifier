"""
Unit tests for cross-validation module.
"""

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from app.ml_models.cross_validation import CrossValidator


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    np.random.seed(42)
    n_samples = 100
    n_features = 20

    X = pd.DataFrame(
        np.random.randn(n_samples, n_features),
        columns=[f"feature_{i}" for i in range(n_features)],
    )
    y = pd.Series(np.random.randint(0, 2, n_samples))

    return X, y


class TestCrossValidator:
    """Test CrossValidator class."""

    def test_init(self):
        """Test CrossValidator initialization."""
        validator = CrossValidator(random_state=42, n_jobs=1)
        assert validator.random_state == 42
        assert validator.n_jobs == 1
        assert validator.cv_results_ == {}
        assert validator.best_models_ == {}
        assert validator.performance_metrics_ == {}

    def test_get_default_models(self):
        """Test getting default models."""
        validator = CrossValidator(random_state=42, n_jobs=1)
        models = validator._get_default_models()

        assert "logistic_regression" in models
        assert "random_forest" in models
        assert "svm" in models
        assert "xgboost" in models

    def test_nested_cross_validation(self, sample_data):
        """Test nested cross-validation."""
        X, y = sample_data
        validator = CrossValidator(random_state=42, n_jobs=1)

        models = {
            "logistic_regression": {
                "model": LogisticRegression(random_state=42, max_iter=1000),
                "params": {"C": [0.1, 1, 10]},
            }
        }

        results = validator.nested_cross_validation(
            X, y, models=models, cv_folds=3, inner_cv_folds=2, scoring="roc_auc"
        )

        assert "model_scores" in results
        assert "best_params" in results
        assert "cv_scores" in results
        assert "performance_metrics" in results
        assert "logistic_regression" in results["model_scores"]

    def test_compare_models(self, sample_data):
        """Test comparing models."""
        X, y = sample_data
        validator = CrossValidator(random_state=42, n_jobs=1)

        models = {
            "logistic_regression": {
                "model": LogisticRegression(random_state=42, max_iter=1000),
                "params": {},
            },
            "random_forest": {
                "model": RandomForestClassifier(random_state=42, n_estimators=10),
                "params": {},
            },
        }

        validator.nested_cross_validation(X, y, models=models, cv_folds=3)
        comparison = validator.compare_models()

        assert isinstance(comparison, pd.DataFrame)
        assert len(comparison) > 0

    def test_get_best_model(self, sample_data):
        """Test getting best model."""
        X, y = sample_data
        validator = CrossValidator(random_state=42, n_jobs=1)

        models = {
            "logistic_regression": {
                "model": LogisticRegression(random_state=42, max_iter=1000),
                "params": {},
            }
        }

        validator.nested_cross_validation(X, y, models=models, cv_folds=3)
        model_name, model = validator.get_best_model()

        assert model_name == "logistic_regression"
        assert model is not None

    def test_get_cv_summary(self, sample_data):
        """Test getting CV summary."""
        X, y = sample_data
        validator = CrossValidator(random_state=42, n_jobs=1)

        models = {
            "logistic_regression": {
                "model": LogisticRegression(random_state=42, max_iter=1000),
                "params": {},
            }
        }

        validator.nested_cross_validation(X, y, models=models, cv_folds=3)
        summary = validator.get_cv_summary()

        assert isinstance(summary, pd.DataFrame)
        assert len(summary) > 0

    def test_save_and_load_results(self, sample_data, tmp_path):
        """Test saving and loading CV results."""
        X, y = sample_data
        validator = CrossValidator(random_state=42, n_jobs=1)

        models = {
            "logistic_regression": {
                "model": LogisticRegression(random_state=42, max_iter=1000),
                "params": {},
            }
        }

        validator.nested_cross_validation(X, y, models=models, cv_folds=3)

        filepath = tmp_path / "cv_results.joblib"
        validator.save_results(str(filepath))
        assert filepath.exists()

        validator2 = CrossValidator(random_state=42, n_jobs=1)
        validator2.load_results(str(filepath))
        assert "model_scores" in validator2.cv_results_
