"""
Model Training and Evaluation for Biomarker Discovery.

This module provides comprehensive model training capabilities including:
- Multiple model types (Logistic Regression, Random Forest, SVM, XGBoost)
- Hyperparameter optimization
- Model evaluation and comparison
- Performance metrics calculation
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV, cross_val_score
from sklearn.svm import SVC, SVR

from .deep_models import get_deep_learning_wrapper

logger = logging.getLogger(__name__)


class ModelTrainer:
    """
    Comprehensive model training for biomarker discovery.

    Supports multiple model types with hyperparameter optimization.
    """

    def __init__(
        self,
        random_state: int = 42,
        n_jobs: int = -1,
        mlp_use_focal_loss: bool = False,
        focal_gamma: float = 2.0,
        focal_alpha: Optional[float] = None,
    ):
        """
        Initialize model trainer.

        Args:
            random_state: Random seed for reproducibility
            n_jobs: Number of parallel jobs
            mlp_use_focal_loss: Use focal loss for the PyTorch MLP head (imbalance)
            focal_gamma: Focal loss focusing parameter
            focal_alpha: Weight on positive class; None = inverse frequency
        """
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.mlp_use_focal_loss = mlp_use_focal_loss
        self.focal_gamma = focal_gamma
        self.focal_alpha = focal_alpha
        self.trained_models_ = {}
        self.training_results_ = {}

    def train_models(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        models: Dict[str, Dict] = None,
        optimize_hyperparameters: bool = True,
        cv_folds: int = 5,
    ) -> Dict[str, Any]:
        """
        Train multiple models with optional hyperparameter optimization.

        Args:
            X: Feature matrix
            y: Target variable
            models: Dictionary of models to train
            optimize_hyperparameters: Whether to optimize hyperparameters
            cv_folds: Number of CV folds for optimization

        Returns:
            Dictionary with training results
        """
        if models is None:
            models = self._get_default_models()

        logger.info(
            f"Training {len(models)} models with hyperparameter optimization: {optimize_hyperparameters}"
        )

        training_results = {}

        for model_name, model_config in models.items():
            logger.info(f"Training {model_name}...")

            try:
                # Get model and parameters
                model = model_config["model"]
                if model is None:
                    logger.info(
                        f"Skipping {model_name} (not available, e.g. missing dependencies)"
                    )
                    continue
                param_grid = model_config.get("params", {})

                # Train model (DL uses fit + CV score; no GridSearchCV)
                if optimize_hyperparameters and param_grid:
                    # With hyperparameter optimization
                    grid_search = GridSearchCV(
                        model,
                        param_grid,
                        cv=cv_folds,
                        scoring="roc_auc",
                        n_jobs=self.n_jobs,
                        verbose=0,
                    )
                    grid_search.fit(X, y)

                    best_model = grid_search.best_estimator_
                    best_params = grid_search.best_params_
                    best_score = grid_search.best_score_

                else:
                    # Without hyperparameter optimization
                    model.fit(X, y)
                    best_model = model
                    best_params = {}
                    best_score = cross_val_score(
                        model, X, y, cv=cv_folds, scoring="roc_auc"
                    ).mean()

                # Store results
                training_results[model_name] = {
                    "model": best_model,
                    "best_params": best_params,
                    "best_score": best_score,
                    "model_type": type(best_model).__name__,
                }

                # Store trained model
                self.trained_models_[model_name] = best_model

                logger.info(
                    f"{model_name} trained successfully. Best score: {best_score:.4f}"
                )

            except Exception as e:
                logger.error(f"Error training {model_name}: {str(e)}")
                continue

        self.training_results_ = training_results
        return training_results

    def _get_default_models(self) -> Dict[str, Dict]:
        """Get default models for training."""

        return {
            "logistic_regression": {
                "model": LogisticRegression(
                    random_state=self.random_state, max_iter=1000
                ),
                "params": {
                    "C": [0.001, 0.01, 0.1, 1, 10, 100],
                    "penalty": ["l1", "l2"],
                    "solver": ["liblinear", "saga"],
                },
            },
            "random_forest": {
                "model": RandomForestClassifier(
                    random_state=self.random_state, n_jobs=self.n_jobs
                ),
                "params": {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [None, 10, 20, 30],
                    "min_samples_split": [2, 5, 10],
                    "min_samples_leaf": [1, 2, 4],
                },
            },
            "svm": {
                "model": SVC(random_state=self.random_state, probability=True),
                "params": {
                    "C": [0.1, 1, 10, 100],
                    "gamma": ["scale", "auto", 0.001, 0.01, 0.1, 1],
                    "kernel": ["rbf", "linear"],
                },
            },
            "xgboost": {
                "model": xgb.XGBClassifier(
                    random_state=self.random_state, eval_metric="logloss"
                ),
                "params": {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [3, 6, 9],
                    "learning_rate": [0.01, 0.1, 0.2],
                    "subsample": [0.8, 0.9, 1.0],
                },
            },
            "deep_learning": {
                "model": get_deep_learning_wrapper(
                    random_state=self.random_state,
                    hidden_dims=(256, 128, 64),
                    max_epochs=80,
                    batch_size=32,
                    use_focal_loss=self.mlp_use_focal_loss,
                    focal_gamma=self.focal_gamma,
                    focal_alpha=self.focal_alpha,
                ),
                "params": {},  # DL uses internal early stopping; no GridSearchCV
            },
        }

    def get_best_model(self, metric: str = "roc_auc") -> Tuple[str, Any]:
        """
        Get the best performing model.

        Args:
            metric: Metric to use for selection

        Returns:
            Tuple of (model_name, model)
        """
        if not self.training_results_:
            raise ValueError("No training results available. Train models first.")

        best_model_name = None
        best_score = -np.inf

        for model_name, results in self.training_results_.items():
            score = results["best_score"]
            if score > best_score:
                best_score = score
                best_model_name = model_name

        if best_model_name is None:
            raise ValueError("No models available")

        return best_model_name, self.trained_models_[best_model_name]

    def save_models(self, filepath: str):
        """Save trained models to file."""

        if not self.trained_models_:
            raise ValueError("No models to save")

        joblib.dump(self.trained_models_, filepath)
        logger.info(f"Models saved to {filepath}")

    def load_models(self, filepath: str):
        """Load trained models from file."""

        self.trained_models_ = joblib.load(filepath)
        logger.info(f"Models loaded from {filepath}")


class ModelEvaluator:
    """
    Comprehensive model evaluation for biomarker discovery.

    Provides detailed performance metrics and statistical analysis.
    """

    def __init__(self, random_state: int = 42):
        """Initialize model evaluator."""
        self.random_state = random_state
        self.evaluation_results_ = {}

    def evaluate_models(
        self, models: Dict[str, Any], X: pd.DataFrame, y: pd.Series, cv_folds: int = 5
    ) -> Dict[str, Any]:
        """
        Evaluate multiple models comprehensively.

        Args:
            models: Dictionary of trained models
            X: Feature matrix
            y: Target variable
            cv_folds: Number of CV folds

        Returns:
            Dictionary with evaluation results
        """
        logger.info(f"Evaluating {len(models)} models")

        evaluation_results = {}

        for model_name, model in models.items():
            logger.info(f"Evaluating {model_name}...")

            try:
                # Cross-validation evaluation
                cv_results = self._cross_validation_evaluation(model, X, y, cv_folds)

                # Full dataset evaluation
                full_results = self._full_dataset_evaluation(model, X, y)

                # Store results
                evaluation_results[model_name] = {
                    "cv_results": cv_results,
                    "full_results": full_results,
                    "model_type": type(model).__name__,
                }

                logger.info(f"{model_name} evaluation completed")

            except Exception as e:
                logger.error(f"Error evaluating {model_name}: {str(e)}")
                continue

        self.evaluation_results_ = evaluation_results
        return evaluation_results

    def _cross_validation_evaluation(
        self, model: Any, X: pd.DataFrame, y: pd.Series, cv_folds: int
    ) -> Dict[str, Any]:
        """Perform cross-validation evaluation."""

        from sklearn.model_selection import StratifiedKFold

        # Determine CV strategy
        if y.nunique() <= 10:  # Classification
            cv_strategy = StratifiedKFold(
                n_splits=cv_folds, shuffle=True, random_state=self.random_state
            )
        else:  # Regression
            from sklearn.model_selection import KFold

            cv_strategy = KFold(
                n_splits=cv_folds, shuffle=True, random_state=self.random_state
            )

        # Metrics to evaluate (imbalance-aware set mirrors conference paper reproduce.py)
        metrics = [
            "accuracy",
            "precision_macro",
            "recall_macro",
            "f1_macro",
            "roc_auc",
            "average_precision",
            "balanced_accuracy",
            "matthews_corrcoef",
        ]

        cv_results = {}
        for metric in metrics:
            try:
                scores = cross_val_score(
                    model, X, y, cv=cv_strategy, scoring=metric, n_jobs=-1
                )
                cv_results[metric] = {
                    "mean": np.mean(scores),
                    "std": np.std(scores),
                    "scores": scores.tolist(),
                }
            except Exception as e:
                logger.warning(f"Could not calculate {metric}: {str(e)}")
                continue

        return cv_results

    def _full_dataset_evaluation(
        self, model: Any, X: pd.DataFrame, y: pd.Series
    ) -> Dict[str, Any]:
        """Perform full dataset evaluation."""

        # Fit model
        model.fit(X, y)

        # Get predictions
        y_pred = model.predict(X)

        # Calculate metrics
        results = {
            "accuracy": accuracy_score(y, y_pred),
            "precision_macro": precision_score(y, y_pred, average="macro"),
            "recall_macro": recall_score(y, y_pred, average="macro"),
            "f1_macro": f1_score(y, y_pred, average="macro"),
            "balanced_accuracy": balanced_accuracy_score(y, y_pred),
            "matthews_corrcoef": matthews_corrcoef(y, y_pred),
        }

        # Add probability-based metrics if available
        if hasattr(model, "predict_proba"):
            y_pred_proba = model.predict_proba(X)[:, 1]
            try:
                results["roc_auc"] = roc_auc_score(y, y_pred_proba)
                results["average_precision"] = average_precision_score(y, y_pred_proba)
            except ValueError:
                # Single class or insufficient samples for ROC/PR
                pass

        # Add confusion matrix
        results["confusion_matrix"] = confusion_matrix(y, y_pred).tolist()

        # Add classification report
        results["classification_report"] = classification_report(
            y, y_pred, output_dict=True
        )

        return results

    def compare_models(self, significance_level: float = 0.05) -> pd.DataFrame:
        """
        Compare models using statistical tests.

        Args:
            significance_level: Significance level for tests

        Returns:
            DataFrame with comparison results
        """
        if not self.evaluation_results_:
            raise ValueError("No evaluation results available. Evaluate models first.")

        model_names = list(self.evaluation_results_.keys())
        n_models = len(model_names)

        if n_models < 2:
            logger.warning("Need at least 2 models for comparison")
            return pd.DataFrame()

        # Create comparison matrix
        comparison_data = []

        for i, model1 in enumerate(model_names):
            for j, model2 in enumerate(model_names):
                if i >= j:
                    continue

                # Get ROC AUC scores for comparison
                scores1 = self.evaluation_results_[model1]["cv_results"]["roc_auc"][
                    "scores"
                ]
                scores2 = self.evaluation_results_[model2]["cv_results"]["roc_auc"][
                    "scores"
                ]

                # Paired t-test
                from scipy import stats

                t_stat, p_value = stats.ttest_rel(scores1, scores2)

                # Effect size (Cohen's d)
                pooled_std = np.sqrt((np.var(scores1) + np.var(scores2)) / 2)
                cohens_d = (np.mean(scores1) - np.mean(scores2)) / pooled_std

                # Significance
                significant = p_value < significance_level

                comparison_data.append(
                    {
                        "model1": model1,
                        "model2": model2,
                        "model1_mean": np.mean(scores1),
                        "model2_mean": np.mean(scores2),
                        "difference": np.mean(scores1) - np.mean(scores2),
                        "t_statistic": t_stat,
                        "p_value": p_value,
                        "cohens_d": cohens_d,
                        "significant": significant,
                    }
                )

        return pd.DataFrame(comparison_data)

    def get_evaluation_summary(self) -> pd.DataFrame:
        """Get evaluation summary."""

        if not self.evaluation_results_:
            return pd.DataFrame()

        summary_data = []
        for model_name, results in self.evaluation_results_.items():
            cv_results = results["cv_results"]
            row = {
                "model": model_name,
                "model_type": results["model_type"],
                "accuracy": cv_results.get("accuracy", {}).get("mean", 0),
                "precision": cv_results.get("precision_macro", {}).get("mean", 0),
                "recall": cv_results.get("recall_macro", {}).get("mean", 0),
                "f1_score": cv_results.get("f1_macro", {}).get("mean", 0),
                "roc_auc": cv_results.get("roc_auc", {}).get("mean", 0),
            }
            summary_data.append(row)

        return pd.DataFrame(summary_data).sort_values("roc_auc", ascending=False)

    def save_results(self, filepath: str):
        """Save evaluation results to file."""

        if not self.evaluation_results_:
            raise ValueError("No results to save")

        joblib.dump(self.evaluation_results_, filepath)
        logger.info(f"Evaluation results saved to {filepath}")

    def load_results(self, filepath: str):
        """Load evaluation results from file."""

        self.evaluation_results_ = joblib.load(filepath)
        logger.info(f"Evaluation results loaded from {filepath}")
