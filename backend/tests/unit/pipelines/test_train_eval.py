"""
Comprehensive unit tests for model training and evaluation pipeline.
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from app.pipelines.train_eval import ModelTrainingPipeline


class TestModelTrainingPipeline:
    """Test cases for ModelTrainingPipeline."""

    def test_model_training_pipeline_initialization(self):
        """Test ModelTrainingPipeline initialization."""
        pipeline = ModelTrainingPipeline()
        assert pipeline is not None
        assert pipeline.config == {}
        assert pipeline.training_results == {}

    def test_model_training_pipeline_initialization_with_config(self):
        """Test ModelTrainingPipeline initialization with config."""
        config = {"test": "value"}
        pipeline = ModelTrainingPipeline(config=config)
        assert pipeline.config == config

    def test_train_and_evaluate_logistic_regression(self):
        """Test training and evaluating logistic regression model."""
        pipeline = ModelTrainingPipeline()

        # Create sample data
        np.random.seed(42)
        n_samples = 100
        n_features = 20
        expression_data = pd.DataFrame(
            np.random.randn(n_features, n_samples),
            index=[f"GENE{i:03d}" for i in range(n_features)],
            columns=[f"SAMPLE{i:03d}" for i in range(n_samples)],
        )
        labels = pd.Series(np.random.choice([0, 1], n_samples))

        results = pipeline.train_and_evaluate(
            expression_data=expression_data,
            labels=labels,
            model_type="logistic_regression",
            cv_folds=3,
            test_size=0.2,
        )

        assert results is not None
        assert "model_type" in results
        assert "model_performance" in results
        assert "cross_validation" in results
        assert "model" in results

    def test_train_and_evaluate_random_forest(self):
        """Test training and evaluating random forest model."""
        pipeline = ModelTrainingPipeline()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(20, 100),
            index=[f"GENE{i:03d}" for i in range(20)],
            columns=[f"SAMPLE{i:03d}" for i in range(100)],
        )
        labels = pd.Series(np.random.choice([0, 1], 100))

        results = pipeline.train_and_evaluate(
            expression_data=expression_data,
            labels=labels,
            model_type="random_forest",
            cv_folds=3,
        )

        assert results is not None
        assert results["model_type"] == "random_forest"

    def test_train_and_evaluate_with_selected_features(self):
        """Test training with selected features."""
        pipeline = ModelTrainingPipeline()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(20, 100),
            index=[f"GENE{i:03d}" for i in range(20)],
            columns=[f"SAMPLE{i:03d}" for i in range(100)],
        )
        labels = pd.Series(np.random.choice([0, 1], 100))

        selected_features = ["GENE000", "GENE001", "GENE002"]
        results = pipeline.train_and_evaluate(
            expression_data=expression_data,
            labels=labels,
            selected_features=selected_features,
            model_type="logistic_regression",
        )

        assert results is not None
        assert results["selected_features"] == selected_features

    def test_train_model(self):
        """Test training a model."""
        pipeline = ModelTrainingPipeline()

        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(50, 10))
        y = pd.Series(np.random.choice([0, 1], 50))

        model = pipeline._train_model(X, y, "logistic_regression")
        assert model is not None

    def test_evaluate_model(self):
        """Test evaluating a model."""
        pipeline = ModelTrainingPipeline()

        np.random.seed(42)
        X_train = pd.DataFrame(np.random.randn(50, 10))
        y_train = pd.Series(np.random.choice([0, 1], 50))
        X_test = pd.DataFrame(np.random.randn(20, 10))
        y_test = pd.Series(np.random.choice([0, 1], 20))

        model = pipeline._train_model(X_train, y_train, "logistic_regression")
        performance = pipeline._evaluate_model(model, X_test, y_test)

        assert performance is not None
        assert "accuracy" in performance or "roc_auc" in performance

    def test_cross_validate_model(self):
        """Test cross-validating a model."""
        pipeline = ModelTrainingPipeline()

        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(100, 10))
        y = pd.Series(np.random.choice([0, 1], 100))

        model = pipeline._train_model(X, y, "logistic_regression")
        cv_results = pipeline._cross_validate_model(
            model, X, y, cv_folds=3, random_state=42
        )

        assert cv_results is not None
        assert (
            "accuracy" in cv_results
            or "f1_score" in cv_results
            or "mean_score" in cv_results
        )

    def test_perform_permutation_test(self):
        """Test performing permutation test."""
        pipeline = ModelTrainingPipeline()

        np.random.seed(42)
        X = pd.DataFrame(np.random.randn(50, 10))
        y = pd.Series(np.random.choice([0, 1], 50))

        model = pipeline._train_model(X, y, "logistic_regression")
        perm_results = pipeline._permutation_test(model, X, y, n_permutations=10)

        assert perm_results is not None
        assert (
            "p_value" in perm_results
            or "permutation_scores" in perm_results
            or "observed_score" in perm_results
        )

    def test_calibrate_model(self):
        """Test calibrating a model."""
        pipeline = ModelTrainingPipeline()

        np.random.seed(42)
        X_train = pd.DataFrame(np.random.randn(50, 10))
        y_train = pd.Series(np.random.choice([0, 1], 50))
        X_test = pd.DataFrame(np.random.randn(20, 10))
        y_test = pd.Series(np.random.choice([0, 1], 20))

        model = pipeline._train_model(X_train, y_train, "logistic_regression")
        calibration = pipeline._calibrate_model(model, X_test, y_test)

        assert calibration is not None
        assert isinstance(calibration, dict)
