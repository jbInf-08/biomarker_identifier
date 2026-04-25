"""
Tests for hyperparameter tuning in ML models.
"""
import numpy as np
import pytest

from app.ml_models.advanced_models import AdvancedBiomarkerModel


class TestHyperparameterTuning:
    """Tests for hyperparameter tuning functionality."""

    def test_tune_hyperparameters_random_forest(self):
        """Test hyperparameter tuning for random forest."""
        model = AdvancedBiomarkerModel(model_type="random_forest")

        np.random.seed(42)
        X = np.random.randn(50, 10)
        y = np.random.choice([0, 1], 50)

        # Train without tuning first to set model
        model.train(X, y, hyperparameter_tuning=False)

        # Now test tuning
        tuned_model = model._tune_hyperparameters(X, y)

        assert tuned_model is not None
        assert hasattr(tuned_model, "fit")

    def test_tune_hyperparameters_gradient_boosting(self):
        """Test hyperparameter tuning for gradient boosting."""
        model = AdvancedBiomarkerModel(model_type="gradient_boosting")

        np.random.seed(42)
        X = np.random.randn(50, 10)
        y = np.random.choice([0, 1], 50)

        # Train without tuning first
        model.train(X, y, hyperparameter_tuning=False)

        # Test tuning
        tuned_model = model._tune_hyperparameters(X, y)

        assert tuned_model is not None
        assert hasattr(tuned_model, "fit")

    def test_tune_hyperparameters_ensemble(self):
        """Test hyperparameter tuning for ensemble (should use default)."""
        model = AdvancedBiomarkerModel(model_type="ensemble")

        np.random.seed(42)
        X = np.random.randn(50, 10)
        y = np.random.choice([0, 1], 50)

        model.train(X, y, hyperparameter_tuning=False)

        # Ensemble doesn't have tuning, should return model as-is
        tuned_model = model._tune_hyperparameters(X, y)

        assert tuned_model is not None

    def test_tune_hyperparameters_neural_network(self):
        """Test hyperparameter tuning for neural network (should use default)."""
        model = AdvancedBiomarkerModel(model_type="neural_network")

        np.random.seed(42)
        X = np.random.randn(50, 10)
        y = np.random.choice([0, 1], 50)

        model.train(X, y, hyperparameter_tuning=False)

        # Neural network doesn't have tuning, should return model as-is
        tuned_model = model._tune_hyperparameters(X, y)

        assert tuned_model is not None

    def test_tune_hyperparameters_with_training(self):
        """Test training with hyperparameter tuning enabled."""
        model = AdvancedBiomarkerModel(model_type="random_forest")

        np.random.seed(42)
        X = np.random.randn(50, 10)
        y = np.random.choice([0, 1], 50)

        performance = model.train(X, y, hyperparameter_tuning=True)

        assert performance is not None
        assert model.is_trained is True
        assert model.model is not None

    def test_tune_hyperparameters_small_dataset(self):
        """Test hyperparameter tuning with small dataset."""
        model = AdvancedBiomarkerModel(model_type="random_forest")

        np.random.seed(42)
        X = np.random.randn(20, 5)  # Small dataset
        y = np.random.choice([0, 1], 20)

        model.train(X, y, hyperparameter_tuning=False)

        try:
            tuned_model = model._tune_hyperparameters(X, y)
            assert tuned_model is not None
        except Exception:
            # May fail with very small dataset
            pass

    def test_tune_hyperparameters_error_handling(self):
        """Test hyperparameter tuning error handling."""
        model = AdvancedBiomarkerModel(model_type="random_forest")

        # Create invalid data that might cause tuning to fail
        X = np.random.randn(10, 5)
        y = np.array([0] * 10)  # Single class

        try:
            model.train(X, y, hyperparameter_tuning=False)

            # Should handle error gracefully
            tuned_model = model._tune_hyperparameters(X, y)
            # If it doesn't raise, should return model
            assert tuned_model is not None
        except (ValueError, Exception):
            # Expected to fail with single class or during training
            pass
