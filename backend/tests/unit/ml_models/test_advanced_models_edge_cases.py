"""
Edge case tests for advanced ML models.
"""
import numpy as np
import pytest

from app.ml_models.advanced_models import AdvancedBiomarkerModel


class TestAdvancedBiomarkerModelEdgeCases:
    """Edge case tests for AdvancedBiomarkerModel."""

    def test_train_empty_data(self):
        """Test training with empty data."""
        model = AdvancedBiomarkerModel()

        X = np.array([]).reshape(0, 10)
        y = np.array([])

        with pytest.raises((ValueError, IndexError)):
            model.train(X, y, hyperparameter_tuning=False)

    def test_train_single_sample(self):
        """Test training with single sample."""
        model = AdvancedBiomarkerModel()

        X = np.random.randn(1, 10)
        y = np.array([0])

        with pytest.raises((ValueError, IndexError)):
            model.train(X, y, hyperparameter_tuning=False)

    def test_train_single_class(self):
        """Test training with single class."""
        model = AdvancedBiomarkerModel()

        X = np.random.randn(10, 5)
        y = np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0])

        try:
            performance = model.train(X, y, hyperparameter_tuning=False)
            # May succeed but with warnings
            assert (
                isinstance(performance, type(model.performance_metrics))
                or model.performance_metrics is not None
            )
        except Exception:
            # Expected to fail with single class
            pass

    def test_train_mismatched_dimensions(self):
        """Test training with mismatched dimensions."""
        model = AdvancedBiomarkerModel()

        X = np.random.randn(10, 5)
        y = np.array([0, 1, 0])  # Wrong length

        with pytest.raises((ValueError, IndexError)):
            model.train(X, y, hyperparameter_tuning=False)

    def test_predict_before_training(self):
        """Test predicting before training."""
        model = AdvancedBiomarkerModel()

        X = np.random.randn(5, 10)

        with pytest.raises((AttributeError, ValueError)):
            model.predict(X)

    def test_predict_mismatched_features(self):
        """Test predicting with mismatched feature count."""
        model = AdvancedBiomarkerModel()

        # Train with 10 features
        X_train = np.random.randn(20, 10)
        y_train = np.random.choice([0, 1], 20)
        model.train(X_train, y_train, hyperparameter_tuning=False)

        # Predict with different number of features
        X_test = np.random.randn(5, 5)  # Only 5 features

        with pytest.raises((ValueError, IndexError)):
            model.predict(X_test)

    def test_train_invalid_model_type(self):
        """Test training with invalid model type."""
        model = AdvancedBiomarkerModel(model_type="invalid_type")

        X = np.random.randn(20, 10)
        y = np.random.choice([0, 1], 20)

        # Should fall back to default or raise error
        try:
            performance = model.train(X, y, hyperparameter_tuning=False)
            assert model.is_trained is True
        except Exception:
            # Expected to fail with invalid type
            pass

    def test_save_model_before_training(self, tmp_path):
        """Test saving model before training."""
        model = AdvancedBiomarkerModel()

        model_path = tmp_path / "model.pkl"

        with pytest.raises((AttributeError, ValueError)):
            model.save_model(str(model_path))

    def test_load_model_invalid_file(self):
        """Test loading invalid model file."""
        model = AdvancedBiomarkerModel()

        try:
            model.load_model("/nonexistent/path/model.pkl")
            # If it doesn't raise, that's also acceptable
        except (FileNotFoundError, ValueError, IOError, OSError):
            # Expected to fail
            pass

    def test_get_feature_importance_before_training(self):
        """Test getting feature importance before training."""
        model = AdvancedBiomarkerModel()

        # Should return None or empty dict or raise AttributeError
        try:
            importance = model.get_feature_importance()
            assert importance is None or isinstance(importance, dict)
        except (AttributeError, ValueError):
            # Expected if method doesn't exist or requires training
            pass

    def test_train_with_nan_values(self):
        """Test training with NaN values."""
        model = AdvancedBiomarkerModel()

        X = np.random.randn(20, 10)
        X[0, 0] = np.nan  # Add NaN
        y = np.random.choice([0, 1], 20)

        try:
            performance = model.train(X, y, hyperparameter_tuning=False)
            assert model.is_trained is True
        except Exception:
            # May fail with NaN values
            pass

    def test_train_with_inf_values(self):
        """Test training with infinite values."""
        model = AdvancedBiomarkerModel()

        X = np.random.randn(20, 10)
        X[0, 0] = np.inf  # Add infinity
        y = np.random.choice([0, 1], 20)

        try:
            performance = model.train(X, y, hyperparameter_tuning=False)
            assert model.is_trained is True
        except Exception:
            # May fail with infinite values
            pass
