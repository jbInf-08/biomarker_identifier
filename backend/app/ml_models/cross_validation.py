"""
Cross-Validation and Model Evaluation for Biomarker Discovery.

This module provides comprehensive cross-validation capabilities including:
- Stratified k-fold cross-validation
- Nested cross-validation for hyperparameter tuning
- Performance metrics calculation
- Statistical significance testing
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy import stats
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import (
    GridSearchCV,
    KFold,
    RandomizedSearchCV,
    StratifiedKFold,
    cross_val_score,
)
from sklearn.svm import SVC

logger = logging.getLogger(__name__)


class CrossValidator:
    """
    Comprehensive cross-validation for biomarker models.

    Provides nested cross-validation, performance metrics, and statistical testing.
    """

    def __init__(self, random_state: int = 42, n_jobs: int = -1):
        """
        Initialize cross-validator.

        Args:
            random_state: Random seed for reproducibility
            n_jobs: Number of parallel jobs
        """
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.cv_results_ = {}
        self.best_models_ = {}
        self.performance_metrics_ = {}

    def nested_cross_validation(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        models: Dict[str, Any] = None,
        cv_folds: int = 5,
        inner_cv_folds: int = 3,
        scoring: str = "roc_auc",
    ) -> Dict[str, Any]:
        """
        Perform nested cross-validation for model selection and evaluation.

        Args:
            X: Feature matrix
            y: Target variable
            models: Dictionary of models to evaluate
            cv_folds: Number of outer CV folds
            inner_cv_folds: Number of inner CV folds for hyperparameter tuning
            scoring: Scoring metric

        Returns:
            Dictionary with CV results
        """
        if models is None:
            models = self._get_default_models()

        logger.info(f"Starting nested cross-validation with {cv_folds} outer folds")
        logger.info(f"Models to evaluate: {list(models.keys())}")

        # Determine CV strategy
        if y.nunique() <= 10:  # Classification
            cv_strategy = StratifiedKFold(
                n_splits=cv_folds, shuffle=True, random_state=self.random_state
            )
            inner_cv_strategy = StratifiedKFold(
                n_splits=inner_cv_folds, shuffle=True, random_state=self.random_state
            )
        else:  # Regression
            cv_strategy = KFold(
                n_splits=cv_folds, shuffle=True, random_state=self.random_state
            )
            inner_cv_strategy = KFold(
                n_splits=inner_cv_folds, shuffle=True, random_state=self.random_state
            )

        # Store results
        cv_results = {
            "model_scores": {},
            "best_params": {},
            "cv_scores": {},
            "performance_metrics": {},
        }

        # Evaluate each model
        for model_name, model_config in models.items():
            logger.info(f"Evaluating {model_name}...")

            try:
                # Get model and parameter grid
                model = model_config["model"]
                param_grid = model_config.get("params", {})

                # Nested CV
                if param_grid:
                    # With hyperparameter tuning
                    grid_search = GridSearchCV(
                        model,
                        param_grid,
                        cv=inner_cv_strategy,
                        scoring=scoring,
                        n_jobs=self.n_jobs,
                        verbose=0,
                    )

                    # Outer CV
                    cv_scores = cross_val_score(
                        grid_search,
                        X,
                        y,
                        cv=cv_strategy,
                        scoring=scoring,
                        n_jobs=self.n_jobs,
                    )

                    # Fit on full data to get best params
                    grid_search.fit(X, y)
                    best_params = grid_search.best_params_
                    best_model = grid_search.best_estimator_

                else:
                    # Without hyperparameter tuning
                    cv_scores = cross_val_score(
                        model, X, y, cv=cv_strategy, scoring=scoring, n_jobs=self.n_jobs
                    )
                    best_params = {}
                    best_model = model

                # Calculate performance metrics
                performance_metrics = self._calculate_performance_metrics(
                    best_model, X, y, cv_strategy
                )

                # Store results
                cv_results["model_scores"][model_name] = {
                    "mean": np.mean(cv_scores),
                    "std": np.std(cv_scores),
                    "scores": cv_scores.tolist(),
                }
                cv_results["best_params"][model_name] = best_params
                cv_results["cv_scores"][model_name] = cv_scores
                cv_results["performance_metrics"][model_name] = performance_metrics

                # Store best model
                self.best_models_[model_name] = best_model

                logger.info(
                    f"{model_name}: {np.mean(cv_scores):.3f} ± {np.std(cv_scores):.3f}"
                )

            except Exception as e:
                logger.error(f"Error evaluating {model_name}: {str(e)}")
                continue

        self.cv_results_ = cv_results
        return cv_results

    def _get_default_models(self) -> Dict[str, Dict]:
        """Get default models for evaluation."""

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
        }

    def _calculate_performance_metrics(
        self, model: Any, X: pd.DataFrame, y: pd.Series, cv_strategy
    ) -> Dict[str, Any]:
        """Calculate comprehensive performance metrics."""

        metrics = {}

        # Cross-validation metrics
        cv_metrics = [
            "accuracy",
            "precision_macro",
            "recall_macro",
            "f1_macro",
            "roc_auc",
            "average_precision",
            "balanced_accuracy",
            "matthews_corrcoef",
        ]

        for metric in cv_metrics:
            try:
                scores = cross_val_score(
                    model, X, y, cv=cv_strategy, scoring=metric, n_jobs=self.n_jobs
                )
                metrics[f"cv_{metric}"] = {
                    "mean": np.mean(scores),
                    "std": np.std(scores),
                    "scores": scores.tolist(),
                }
            except Exception as e:
                logger.warning(f"Could not calculate {metric}: {str(e)}")
                continue

        # Additional metrics for classification
        if y.nunique() <= 10:  # Classification
            try:
                # Fit model and get predictions
                model.fit(X, y)
                y_pred = model.predict(X)
                y_pred_proba = (
                    model.predict_proba(X)[:, 1]
                    if hasattr(model, "predict_proba")
                    else None
                )

                # Confusion matrix
                cm = confusion_matrix(y, y_pred)
                metrics["confusion_matrix"] = cm.tolist()

                # Classification report
                metrics["classification_report"] = classification_report(
                    y, y_pred, output_dict=True
                )

                # ROC AUC if probabilities available
                if y_pred_proba is not None:
                    try:
                        roc_auc = roc_auc_score(y, y_pred_proba)
                        metrics["roc_auc_full"] = roc_auc
                    except:
                        pass

                # Average precision
                if y_pred_proba is not None:
                    try:
                        avg_precision = average_precision_score(y, y_pred_proba)
                        metrics["average_precision"] = avg_precision
                    except:
                        pass

            except Exception as e:
                logger.warning(
                    f"Could not calculate additional classification metrics: {str(e)}"
                )

        return metrics

    def compare_models(self, significance_level: float = 0.05) -> pd.DataFrame:
        """
        Compare models using statistical tests.

        Args:
            significance_level: Significance level for tests

        Returns:
            DataFrame with comparison results
        """
        if not self.cv_results_:
            raise ValueError(
                "No CV results available. Run nested_cross_validation first."
            )

        model_names = list(self.cv_results_["cv_scores"].keys())
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

                scores1 = self.cv_results_["cv_scores"][model1]
                scores2 = self.cv_results_["cv_scores"][model2]

                # Paired t-test
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

    def get_best_model(self, metric: str = "roc_auc") -> Tuple[str, Any]:
        """
        Get the best performing model.

        Args:
            metric: Metric to use for selection

        Returns:
            Tuple of (model_name, model)
        """
        if not self.cv_results_:
            raise ValueError(
                "No CV results available. Run nested_cross_validation first."
            )

        best_model_name = None
        best_score = -np.inf

        for model_name, scores in self.cv_results_["model_scores"].items():
            # Nested CV stores aggregate mean/std for whatever ``scoring`` was used.
            if "mean" in scores:
                score = float(scores["mean"])
                if score > best_score:
                    best_score = score
                    best_model_name = model_name

        if best_model_name is None:
            raise ValueError(f"Metric {metric} not found in results")

        return best_model_name, self.best_models_[best_model_name]

    def get_cv_summary(self) -> pd.DataFrame:
        """Get cross-validation summary."""

        if not self.cv_results_:
            return pd.DataFrame()

        summary_data = []
        for model_name, scores in self.cv_results_["model_scores"].items():
            row = {
                "model": model_name,
                "mean_score": scores["mean"],
                "std_score": scores["std"],
                "best_params": str(self.cv_results_["best_params"][model_name]),
            }
            summary_data.append(row)

        return pd.DataFrame(summary_data).sort_values("mean_score", ascending=False)

    def save_results(self, filepath: str):
        """Save CV results to file."""

        if not self.cv_results_:
            raise ValueError("No results to save")

        # Save results (excluding models)
        results_to_save = {
            "cv_results": self.cv_results_,
            "performance_metrics": self.performance_metrics_,
        }

        joblib.dump(results_to_save, filepath)
        logger.info(f"CV results saved to {filepath}")

    def load_results(self, filepath: str):
        """Load CV results from file."""

        data = joblib.load(filepath)
        self.cv_results_ = data["cv_results"]
        self.performance_metrics_ = data["performance_metrics"]
        logger.info(f"CV results loaded from {filepath}")
