"""
Comprehensive unit tests for advanced ML models.
"""
import numpy as np
import pandas as pd
import pytest

from app.ml_models.advanced_models import AdvancedBiomarkerModel, ModelPerformance


class TestAdvancedBiomarkerModel:
    """Test cases for AdvancedBiomarkerModel."""

    def test_model_initialization(self):
        """Test model initialization."""
        model = AdvancedBiomarkerModel()
        assert model is not None
        assert model.model_type == "ensemble"
        assert model.model is None
        assert model.is_trained is False

    def test_model_initialization_with_type(self):
        """Test model initialization with specific type."""
        model = AdvancedBiomarkerModel(model_type="neural_network")
        assert model.model_type == "neural_network"

    def test_train_ensemble_model(self):
        """Test training ensemble model."""
        model = AdvancedBiomarkerModel(model_type="ensemble")

        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.choice([0, 1], 100)

        performance = model.train(X, y, hyperparameter_tuning=False)

        assert isinstance(performance, ModelPerformance)
        assert model.is_trained is True
        assert model.model is not None
        assert performance.accuracy >= 0.0
        assert performance.accuracy <= 1.0

    def test_train_neural_network(self):
        """Test training neural network model."""
        model = AdvancedBiomarkerModel(model_type="neural_network")

        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.choice([0, 1], 100)

        performance = model.train(X, y, hyperparameter_tuning=False)

        assert isinstance(performance, ModelPerformance)
        assert model.is_trained is True

    def test_train_gradient_boosting(self):
        """Test training gradient boosting model."""
        model = AdvancedBiomarkerModel(model_type="gradient_boosting")

        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.choice([0, 1], 100)

        performance = model.train(X, y, hyperparameter_tuning=False)

        assert isinstance(performance, ModelPerformance)
        assert model.is_trained is True

    def test_train_svm(self):
        """Test training SVM model."""
        model = AdvancedBiomarkerModel(model_type="svm")

        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.choice([0, 1], 100)

        performance = model.train(X, y, hyperparameter_tuning=False)

        assert isinstance(performance, ModelPerformance)
        assert model.is_trained is True

    def test_train_with_feature_names(self):
        """Test training with feature names."""
        model = AdvancedBiomarkerModel()

        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.choice([0, 1], 100)
        feature_names = [f"feature_{i}" for i in range(10)]

        performance = model.train(
            X, y, feature_names=feature_names, hyperparameter_tuning=False
        )

        assert model.feature_names == feature_names
        assert model.is_trained is True

    def test_predict(self):
        """Test making predictions."""
        model = AdvancedBiomarkerModel()

        np.random.seed(42)
        X_train = np.random.randn(100, 10)
        y_train = np.random.choice([0, 1], 100)

        model.train(X_train, y_train, hyperparameter_tuning=False)

        X_test = np.random.randn(20, 10)
        predictions = model.predict(X_test)

        assert predictions is not None
        assert len(predictions) == 20
        assert all(p in [0, 1] for p in predictions)

    def test_predict_proba(self):
        """Test predicting probabilities."""
        model = AdvancedBiomarkerModel()

        np.random.seed(42)
        X_train = np.random.randn(100, 10)
        y_train = np.random.choice([0, 1], 100)

        model.train(X_train, y_train, hyperparameter_tuning=False)

        X_test = np.random.randn(20, 10)
        probabilities = model.predict_proba(X_test)

        assert probabilities is not None
        assert probabilities.shape[0] == 20
        assert probabilities.shape[1] == 2

    def test_get_feature_importance(self):
        """Test getting feature importance."""
        model = AdvancedBiomarkerModel()

        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.choice([0, 1], 100)
        feature_names = [f"feature_{i}" for i in range(10)]

        model.train(X, y, feature_names=feature_names, hyperparameter_tuning=False)

        importance = model.get_feature_importance()

        assert importance is not None
        assert isinstance(importance, dict)

    def test_save_and_load_model(self, tmp_path):
        """Test saving and loading model."""
        model = AdvancedBiomarkerModel()

        np.random.seed(42)
        X = np.random.randn(100, 10)
        y = np.random.choice([0, 1], 100)

        model.train(X, y, hyperparameter_tuning=False)

        model_path = tmp_path / "test_model.pkl"
        model.save_model(str(model_path))

        assert model_path.exists()

        # Load model
        loaded_model = AdvancedBiomarkerModel()
        loaded_model.load_model(str(model_path))

        assert loaded_model.is_trained is True
        assert loaded_model.model is not None

    def test_create_ensemble_model(self):
        """Test creating ensemble model."""
        model = AdvancedBiomarkerModel()
        ensemble = model._create_ensemble_model()

        assert ensemble is not None

    def test_create_neural_network(self):
        """Test creating neural network."""
        model = AdvancedBiomarkerModel()
        nn = model._create_neural_network()

        assert nn is not None

    def test_tune_hyperparameters(self):
        """Test hyperparameter tuning."""
        model = AdvancedBiomarkerModel()

        np.random.seed(42)
        X = np.random.randn(50, 5)  # Smaller dataset for faster tuning
        y = np.random.choice([0, 1], 50)

        tuned_model = model._tune_hyperparameters(X, y)

        assert tuned_model is not None
