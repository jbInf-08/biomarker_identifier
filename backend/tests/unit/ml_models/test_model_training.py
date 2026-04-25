"""
Unit tests for model training module.
"""

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC

from app.ml_models.model_training import ModelEvaluator, ModelTrainer


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


class TestModelTrainer:
    """Test ModelTrainer class."""

    def test_init(self):
        """Test ModelTrainer initialization."""
        trainer = ModelTrainer(random_state=42, n_jobs=1)
        assert trainer.random_state == 42
        assert trainer.n_jobs == 1
        assert trainer.trained_models_ == {}
        assert trainer.training_results_ == {}

    def test_get_default_models(self, sample_data):
        """Test getting default models."""
        X, y = sample_data
        trainer = ModelTrainer(random_state=42, n_jobs=1)
        models = trainer._get_default_models()

        assert "logistic_regression" in models
        assert "random_forest" in models
        assert "svm" in models
        assert "xgboost" in models

        assert isinstance(models["logistic_regression"]["model"], LogisticRegression)
        assert isinstance(models["random_forest"]["model"], RandomForestClassifier)
        assert isinstance(models["svm"]["model"], SVC)
        assert isinstance(models["xgboost"]["model"], xgb.XGBClassifier)

    def test_train_models_without_optimization(self, sample_data):
        """Test training models without hyperparameter optimization."""
        X, y = sample_data
        trainer = ModelTrainer(random_state=42, n_jobs=1)

        models = {
            "logistic_regression": {
                "model": LogisticRegression(random_state=42, max_iter=1000),
                "params": {},
            }
        }

        results = trainer.train_models(
            X, y, models=models, optimize_hyperparameters=False
        )

        assert "logistic_regression" in results
        assert "model" in results["logistic_regression"]
        assert "best_params" in results["logistic_regression"]
        assert "best_score" in results["logistic_regression"]
        assert "model_type" in results["logistic_regression"]

    def test_train_models_with_optimization(self, sample_data):
        """Test training models with hyperparameter optimization."""
        X, y = sample_data
        trainer = ModelTrainer(random_state=42, n_jobs=1)

        models = {
            "logistic_regression": {
                "model": LogisticRegression(random_state=42, max_iter=1000),
                "params": {"C": [0.1, 1, 10]},
            }
        }

        results = trainer.train_models(
            X, y, models=models, optimize_hyperparameters=True, cv_folds=3
        )

        assert "logistic_regression" in results
        assert "best_params" in results["logistic_regression"]
        assert results["logistic_regression"]["best_params"] != {}

    def test_get_best_model(self, sample_data):
        """Test getting best model."""
        X, y = sample_data
        trainer = ModelTrainer(random_state=42, n_jobs=1)

        models = {
            "logistic_regression": {
                "model": LogisticRegression(random_state=42, max_iter=1000),
                "params": {},
            }
        }

        trainer.train_models(X, y, models=models, optimize_hyperparameters=False)

        model_name, model = trainer.get_best_model()
        assert model_name == "logistic_regression"
        assert model is not None

    def test_save_and_load_models(self, sample_data, tmp_path):
        """Test saving and loading models."""
        X, y = sample_data
        trainer = ModelTrainer(random_state=42, n_jobs=1)

        models = {
            "logistic_regression": {
                "model": LogisticRegression(random_state=42, max_iter=1000),
                "params": {},
            }
        }

        trainer.train_models(X, y, models=models, optimize_hyperparameters=False)

        filepath = tmp_path / "models.joblib"
        trainer.save_models(str(filepath))
        assert filepath.exists()

        trainer2 = ModelTrainer(random_state=42, n_jobs=1)
        trainer2.load_models(str(filepath))
        assert "logistic_regression" in trainer2.trained_models_


class TestModelEvaluator:
    """Test ModelEvaluator class."""

    def test_init(self):
        """Test ModelEvaluator initialization."""
        evaluator = ModelEvaluator(random_state=42)
        assert evaluator.random_state == 42
        assert evaluator.evaluation_results_ == {}

    def test_evaluate_models(self, sample_data):
        """Test evaluating models."""
        X, y = sample_data
        evaluator = ModelEvaluator(random_state=42)

        model = LogisticRegression(random_state=42, max_iter=1000)
        model.fit(X, y)

        models = {"logistic_regression": model}
        results = evaluator.evaluate_models(models, X, y, cv_folds=3)

        assert "logistic_regression" in results
        assert "cv_results" in results["logistic_regression"]
        assert "full_results" in results["logistic_regression"]
        assert "model_type" in results["logistic_regression"]

    def test_compare_models(self, sample_data):
        """Test comparing models."""
        X, y = sample_data
        evaluator = ModelEvaluator(random_state=42)

        model1 = LogisticRegression(random_state=42, max_iter=1000)
        model1.fit(X, y)

        model2 = RandomForestClassifier(random_state=42, n_estimators=10)
        model2.fit(X, y)

        models = {"logistic_regression": model1, "random_forest": model2}

        evaluator.evaluate_models(models, X, y, cv_folds=3)
        comparison = evaluator.compare_models()

        assert isinstance(comparison, pd.DataFrame)
        assert len(comparison) > 0

    def test_get_evaluation_summary(self, sample_data):
        """Test getting evaluation summary."""
        X, y = sample_data
        evaluator = ModelEvaluator(random_state=42)

        model = LogisticRegression(random_state=42, max_iter=1000)
        model.fit(X, y)

        models = {"logistic_regression": model}
        evaluator.evaluate_models(models, X, y, cv_folds=3)

        summary = evaluator.get_evaluation_summary()
        assert isinstance(summary, pd.DataFrame)
        assert len(summary) > 0

    def test_save_and_load_results(self, sample_data, tmp_path):
        """Test saving and loading evaluation results."""
        X, y = sample_data
        evaluator = ModelEvaluator(random_state=42)

        model = LogisticRegression(random_state=42, max_iter=1000)
        model.fit(X, y)

        models = {"logistic_regression": model}
        evaluator.evaluate_models(models, X, y, cv_folds=3)

        filepath = tmp_path / "evaluation_results.joblib"
        evaluator.save_results(str(filepath))
        assert filepath.exists()

        evaluator2 = ModelEvaluator(random_state=42)
        evaluator2.load_results(str(filepath))
        assert "logistic_regression" in evaluator2.evaluation_results_
