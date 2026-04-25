"""
Permutation Tests for Biomarker Model Validation.

This module provides comprehensive permutation testing capabilities including:
- Feature importance permutation tests
- Model performance permutation tests
- Statistical significance testing
- Multiple comparison correction
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import permutation_test
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score
from tqdm import tqdm

logger = logging.getLogger(__name__)


class PermutationTester:
    """
    Comprehensive permutation testing for biomarker models.

    Provides feature importance testing, model validation, and statistical significance.
    """

    def __init__(self, random_state: int = 42, n_jobs: int = -1):
        """
        Initialize permutation tester.

        Args:
            random_state: Random seed for reproducibility
            n_jobs: Number of parallel jobs
        """
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.permutation_results_ = {}

    def feature_importance_permutation_test(
        self,
        model: Any,
        X: pd.DataFrame,
        y: pd.Series,
        n_permutations: int = 1000,
        scoring: str = "roc_auc",
        cv_folds: int = 5,
    ) -> Dict[str, Any]:
        """
        Test feature importance using permutation testing.

        Args:
            model: Trained model
            X: Feature matrix
            y: Target variable
            n_permutations: Number of permutations
            scoring: Scoring metric
            cv_folds: Number of CV folds

        Returns:
            Dictionary with permutation test results
        """
        logger.info(
            f"Starting feature importance permutation test with {n_permutations} permutations"
        )

        # Get baseline performance
        cv_strategy = StratifiedKFold(
            n_splits=cv_folds, shuffle=True, random_state=self.random_state
        )
        baseline_scores = cross_val_score(
            model, X, y, cv=cv_strategy, scoring=scoring, n_jobs=self.n_jobs
        )
        baseline_performance = np.mean(baseline_scores)

        logger.info(f"Baseline performance: {baseline_performance:.4f}")

        # Test each feature
        feature_results = {}

        for feature in tqdm(X.columns, desc="Testing features"):
            try:
                # Create permuted dataset
                X_permuted = X.copy()
                X_permuted[feature] = np.random.permutation(X_permuted[feature].values)

                # Calculate permuted performance
                permuted_scores = cross_val_score(
                    model,
                    X_permuted,
                    y,
                    cv=cv_strategy,
                    scoring=scoring,
                    n_jobs=self.n_jobs,
                )
                permuted_performance = np.mean(permuted_scores)

                # Calculate importance (baseline - permuted)
                importance = baseline_performance - permuted_performance

                feature_results[feature] = {
                    "baseline_performance": baseline_performance,
                    "permuted_performance": permuted_performance,
                    "importance": importance,
                    "baseline_scores": baseline_scores.tolist(),
                    "permuted_scores": permuted_scores.tolist(),
                }

            except Exception as e:
                logger.error(f"Error testing feature {feature}: {str(e)}")
                continue

        # Statistical significance testing
        significance_results = self._test_feature_significance(
            feature_results, n_permutations
        )

        # Store results
        self.permutation_results_["feature_importance"] = {
            "baseline_performance": baseline_performance,
            "feature_results": feature_results,
            "significance_results": significance_results,
        }

        logger.info("Feature importance permutation test completed")
        return self.permutation_results_["feature_importance"]

    def _test_feature_significance(
        self, feature_results: Dict[str, Any], n_permutations: int
    ) -> Dict[str, Any]:
        """Test statistical significance of feature importance."""

        # Extract importance scores
        importance_scores = [
            result["importance"] for result in feature_results.values()
        ]
        feature_names = list(feature_results.keys())

        # Calculate statistics
        mean_importance = np.mean(importance_scores)
        std_importance = np.std(importance_scores)

        # One-sample t-test against zero
        t_stat, p_value = stats.ttest_1samp(importance_scores, 0)

        # Multiple comparison correction (Bonferroni)
        n_features = len(feature_names)
        corrected_p_value = min(p_value * n_features, 1.0)

        # Effect size (Cohen's d)
        cohens_d = mean_importance / std_importance if std_importance > 0 else 0

        return {
            "mean_importance": mean_importance,
            "std_importance": std_importance,
            "t_statistic": t_stat,
            "p_value": p_value,
            "corrected_p_value": corrected_p_value,
            "cohens_d": cohens_d,
            "n_features": n_features,
            "significant_features": [
                feature
                for feature, result in feature_results.items()
                if result["importance"] > mean_importance + 2 * std_importance
            ],
        }

    def model_performance_permutation_test(
        self,
        model: Any,
        X: pd.DataFrame,
        y: pd.Series,
        n_permutations: int = 1000,
        scoring: str = "roc_auc",
        cv_folds: int = 5,
    ) -> Dict[str, Any]:
        """
        Test model performance using permutation testing.

        Args:
            model: Model to test
            X: Feature matrix
            y: Target variable
            n_permutations: Number of permutations
            scoring: Scoring metric
            cv_folds: Number of CV folds

        Returns:
            Dictionary with permutation test results
        """
        logger.info(
            f"Starting model performance permutation test with {n_permutations} permutations"
        )

        # Get baseline performance
        cv_strategy = StratifiedKFold(
            n_splits=cv_folds, shuffle=True, random_state=self.random_state
        )
        baseline_scores = cross_val_score(
            model, X, y, cv=cv_strategy, scoring=scoring, n_jobs=self.n_jobs
        )
        baseline_performance = np.mean(baseline_scores)

        logger.info(f"Baseline performance: {baseline_performance:.4f}")

        # Generate permuted labels
        permuted_scores = []

        for i in tqdm(range(n_permutations), desc="Permuting labels"):
            try:
                # Permute labels
                y_permuted = np.random.permutation(y.values)

                # Calculate permuted performance
                permuted_cv_scores = cross_val_score(
                    model,
                    X,
                    y_permuted,
                    cv=cv_strategy,
                    scoring=scoring,
                    n_jobs=self.n_jobs,
                )
                permuted_scores.append(np.mean(permuted_cv_scores))

            except Exception as e:
                logger.error(f"Error in permutation {i}: {str(e)}")
                continue

        # Calculate p-value
        permuted_scores = np.array(permuted_scores)
        p_value = np.mean(permuted_scores >= baseline_performance)

        # Calculate effect size
        effect_size = baseline_performance - np.mean(permuted_scores)

        # Store results
        self.permutation_results_["model_performance"] = {
            "baseline_performance": baseline_performance,
            "baseline_scores": baseline_scores.tolist(),
            "permuted_scores": permuted_scores.tolist(),
            "p_value": p_value,
            "effect_size": effect_size,
            "n_permutations": n_permutations,
            "significant": p_value < 0.05,
        }

        logger.info(
            f"Model performance permutation test completed. P-value: {p_value:.4f}"
        )
        return self.permutation_results_["model_performance"]

    def stability_permutation_test(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        feature_selector: Any,
        n_permutations: int = 100,
        n_features: int = 50,
    ) -> Dict[str, Any]:
        """
        Test feature selection stability using permutation testing.

        Args:
            X: Feature matrix
            y: Target variable
            feature_selector: Feature selector to test
            n_permutations: Number of permutations
            n_features: Number of features to select

        Returns:
            Dictionary with stability test results
        """
        logger.info(
            f"Starting stability permutation test with {n_permutations} permutations"
        )

        # Get baseline feature selection
        feature_selector.fit(X, y, n_features=n_features)
        baseline_features = set(feature_selector.selected_features_["features"])

        # Test stability across permutations
        stability_results = []
        feature_frequencies = {}

        for i in tqdm(range(n_permutations), desc="Testing stability"):
            try:
                # Permute labels
                y_permuted = np.random.permutation(y.values)

                # Run feature selection on permuted data
                feature_selector.fit(X, y_permuted, n_features=n_features)
                permuted_features = set(feature_selector.selected_features_["features"])

                # Calculate overlap with baseline
                overlap = len(baseline_features.intersection(permuted_features))
                stability = overlap / len(baseline_features)
                stability_results.append(stability)

                # Track feature frequencies
                for feature in permuted_features:
                    feature_frequencies[feature] = (
                        feature_frequencies.get(feature, 0) + 1
                    )

            except Exception as e:
                logger.error(f"Error in stability permutation {i}: {str(e)}")
                continue

        # Calculate statistics
        mean_stability = np.mean(stability_results)
        std_stability = np.std(stability_results)

        # Calculate p-value (one-sample t-test against random chance)
        random_chance = n_features / len(X.columns)
        t_stat, p_value = stats.ttest_1samp(stability_results, random_chance)

        # Store results
        self.permutation_results_["stability"] = {
            "baseline_features": list(baseline_features),
            "mean_stability": mean_stability,
            "std_stability": std_stability,
            "stability_scores": stability_results,
            "p_value": p_value,
            "t_statistic": t_stat,
            "random_chance": random_chance,
            "feature_frequencies": feature_frequencies,
            "n_permutations": n_permutations,
        }

        logger.info(
            f"Stability permutation test completed. Mean stability: {mean_stability:.4f}"
        )
        return self.permutation_results_["stability"]

    def multiple_comparison_correction(
        self, p_values: List[float], method: str = "bonferroni"
    ) -> List[float]:
        """
        Apply multiple comparison correction to p-values.

        Args:
            p_values: List of p-values
            method: Correction method ('bonferroni', 'fdr_bh', 'holm')

        Returns:
            List of corrected p-values
        """
        from statsmodels.stats.multitest import multipletests

        if method == "bonferroni":
            corrected_p_values = [min(p * len(p_values), 1.0) for p in p_values]
        elif method == "fdr_bh":
            _, corrected_p_values, _, _ = multipletests(p_values, method="fdr_bh")
        elif method == "holm":
            _, corrected_p_values, _, _ = multipletests(p_values, method="holm")
        else:
            raise ValueError(f"Unknown correction method: {method}")

        return corrected_p_values

    def get_permutation_summary(self) -> pd.DataFrame:
        """Get summary of all permutation test results."""

        if not self.permutation_results_:
            return pd.DataFrame()

        summary_data = []

        for test_type, results in self.permutation_results_.items():
            if test_type == "feature_importance":
                row = {
                    "test_type": "Feature Importance",
                    "baseline_performance": results["baseline_performance"],
                    "mean_importance": results["significance_results"][
                        "mean_importance"
                    ],
                    "p_value": results["significance_results"]["p_value"],
                    "corrected_p_value": results["significance_results"][
                        "corrected_p_value"
                    ],
                    "significant": results["significance_results"]["corrected_p_value"]
                    < 0.05,
                }
            elif test_type == "model_performance":
                row = {
                    "test_type": "Model Performance",
                    "baseline_performance": results["baseline_performance"],
                    "p_value": results["p_value"],
                    "effect_size": results["effect_size"],
                    "significant": results["significant"],
                }
            elif test_type == "stability":
                row = {
                    "test_type": "Feature Stability",
                    "mean_stability": results["mean_stability"],
                    "p_value": results["p_value"],
                    "random_chance": results["random_chance"],
                    "significant": results["p_value"] < 0.05,
                }
            else:
                continue

            summary_data.append(row)

        return pd.DataFrame(summary_data)

    def save_results(self, filepath: str):
        """Save permutation test results to file."""

        if not self.permutation_results_:
            raise ValueError("No results to save")

        joblib.dump(self.permutation_results_, filepath)
        logger.info(f"Permutation test results saved to {filepath}")

    def load_results(self, filepath: str):
        """Load permutation test results from file."""

        self.permutation_results_ = joblib.load(filepath)
        logger.info(f"Permutation test results loaded from {filepath}")


class PermutationTestSuite:
    """
    Comprehensive permutation test suite for biomarker validation.
    """

    def __init__(self, random_state: int = 42, n_jobs: int = -1):
        """Initialize permutation test suite."""
        self.tester = PermutationTester(random_state=random_state, n_jobs=n_jobs)

    def run_full_validation(
        self,
        model: Any,
        X: pd.DataFrame,
        y: pd.Series,
        feature_selector: Any = None,
        n_permutations: int = 1000,
    ) -> Dict[str, Any]:
        """
        Run comprehensive permutation validation suite.

        Args:
            model: Trained model
            X: Feature matrix
            y: Target variable
            feature_selector: Feature selector (optional)
            n_permutations: Number of permutations

        Returns:
            Dictionary with all validation results
        """
        logger.info("Starting comprehensive permutation validation suite")

        validation_results = {}

        # 1. Model performance permutation test
        logger.info("Running model performance permutation test...")
        validation_results[
            "model_performance"
        ] = self.tester.model_performance_permutation_test(
            model, X, y, n_permutations=n_permutations
        )

        # 2. Feature importance permutation test
        logger.info("Running feature importance permutation test...")
        validation_results[
            "feature_importance"
        ] = self.tester.feature_importance_permutation_test(
            model, X, y, n_permutations=n_permutations
        )

        # 3. Stability permutation test (if feature selector provided)
        if feature_selector is not None:
            logger.info("Running stability permutation test...")
            validation_results["stability"] = self.tester.stability_permutation_test(
                X, y, feature_selector, n_permutations=n_permutations // 10
            )

        # 4. Generate summary
        validation_results["summary"] = self.tester.get_permutation_summary()

        logger.info("Comprehensive permutation validation suite completed")
        return validation_results
