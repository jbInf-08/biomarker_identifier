"""
Feature Selection Algorithms for Biomarker Discovery.

This module implements various feature selection methods including:
- Random Forest feature importance
- LASSO regularization
- XGBoost feature selection
- Stability selection
- Consensus scoring
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy import stats
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.feature_selection import SelectKBest, f_classif, mutual_info_classif
from sklearn.linear_model import LassoCV, LogisticRegressionCV
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


def _thread_pool_workers(n_jobs: int) -> int:
    """``ThreadPoolExecutor`` requires ``max_workers > 0``; ``-1`` follows sklearn-style 'all'."""
    if n_jobs is None or n_jobs < 0:
        return min(32, (os.cpu_count() or 1) + 4)
    if n_jobs == 0:
        return 1
    return n_jobs


class FeatureSelector:
    """
    Comprehensive feature selection for biomarker discovery.

    Implements multiple feature selection methods and provides consensus scoring.
    """

    def __init__(self, random_state: int = 42, n_jobs: int = -1):
        """
        Initialize feature selector.

        Args:
            random_state: Random seed for reproducibility
            n_jobs: Number of parallel jobs
        """
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.scaler = StandardScaler()
        self.feature_scores_ = {}
        self.selected_features_ = {}
        self.consensus_scores_ = None

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        methods: List[str] = None,
        n_features: int = 50,
        stability_threshold: float = 0.6,
    ) -> "FeatureSelector":
        """
        Fit feature selection methods.

        Args:
            X: Feature matrix (samples x features)
            y: Target variable
            methods: List of methods to use
            n_features: Number of features to select
            stability_threshold: Threshold for stability selection

        Returns:
            Self
        """
        if methods is None:
            methods = ["random_forest", "lasso", "xgboost", "mutual_info", "f_test"]

        logger.info(f"Starting feature selection with methods: {methods}")
        logger.info(f"Input data shape: {X.shape}")

        # Store feature names
        self.feature_names_ = X.columns.tolist()

        # Scale features
        X_scaled = pd.DataFrame(
            self.scaler.fit_transform(X), columns=X.columns, index=X.index
        )

        # Run feature selection methods
        for method in methods:
            try:
                logger.info(f"Running {method} feature selection...")
                scores = self._run_method(X_scaled, y, method, n_features)
                self.feature_scores_[method] = scores
                logger.info(f"Completed {method}: selected {len(scores)} features")
            except Exception as e:
                logger.error(f"Error in {method}: {str(e)}")
                continue

        # Compute consensus scores
        self._compute_consensus_scores()

        # Select final features
        self._select_final_features(n_features, stability_threshold)

        logger.info(
            f"Feature selection completed. Final selection: {len(self.selected_features_)} features"
        )
        return self

    def _run_method(
        self, X: pd.DataFrame, y: pd.Series, method: str, n_features: int
    ) -> Dict[str, float]:
        """Run individual feature selection method."""

        if method == "random_forest":
            return self._random_forest_selection(X, y, n_features)
        elif method == "lasso":
            return self._lasso_selection(X, y, n_features)
        elif method == "xgboost":
            return self._xgboost_selection(X, y, n_features)
        elif method == "mutual_info":
            return self._mutual_info_selection(X, y, n_features)
        elif method == "f_test":
            return self._f_test_selection(X, y, n_features)
        else:
            raise ValueError(f"Unknown method: {method}")

    def _random_forest_selection(
        self, X: pd.DataFrame, y: pd.Series, n_features: int
    ) -> Dict[str, float]:
        """Random Forest feature importance selection."""

        # Determine if classification or regression
        if y.nunique() <= 10:  # Classification
            model = RandomForestClassifier(
                n_estimators=100, random_state=self.random_state, n_jobs=self.n_jobs
            )
        else:  # Regression
            model = RandomForestRegressor(
                n_estimators=100, random_state=self.random_state, n_jobs=self.n_jobs
            )

        model.fit(X, y)

        # Get feature importance
        importance = model.feature_importances_

        # Create feature scores dictionary
        feature_scores = dict(zip(X.columns, importance))

        # Select top features
        top_features = sorted(feature_scores.items(), key=lambda x: x[1], reverse=True)[
            :n_features
        ]

        return dict(top_features)

    def _lasso_selection(
        self, X: pd.DataFrame, y: pd.Series, n_features: int
    ) -> Dict[str, float]:
        """LASSO regularization feature selection."""

        # Determine if classification or regression
        if y.nunique() <= 10:  # Classification
            model = LogisticRegressionCV(
                penalty="l1",
                solver="liblinear",
                cv=5,
                random_state=self.random_state,
                n_jobs=self.n_jobs,
            )
        else:  # Regression
            model = LassoCV(cv=5, random_state=self.random_state, n_jobs=self.n_jobs)

        model.fit(X, y)

        # Get coefficients
        if hasattr(model, "coef_"):
            coef = model.coef_.flatten()
        else:
            coef = model.coef_

        # Create feature scores dictionary (absolute values)
        feature_scores = dict(zip(X.columns, np.abs(coef)))

        # Select top features
        top_features = sorted(feature_scores.items(), key=lambda x: x[1], reverse=True)[
            :n_features
        ]

        return dict(top_features)

    def _xgboost_selection(
        self, X: pd.DataFrame, y: pd.Series, n_features: int
    ) -> Dict[str, float]:
        """XGBoost feature importance selection."""

        # Determine if classification or regression
        if y.nunique() <= 10:  # Classification
            model = xgb.XGBClassifier(
                n_estimators=100,
                random_state=self.random_state,
                n_jobs=self.n_jobs,
                eval_metric="logloss",
            )
        else:  # Regression
            model = xgb.XGBRegressor(
                n_estimators=100, random_state=self.random_state, n_jobs=self.n_jobs
            )

        model.fit(X, y)

        # Get feature importance
        importance = model.feature_importances_

        # Create feature scores dictionary
        feature_scores = dict(zip(X.columns, importance))

        # Select top features
        top_features = sorted(feature_scores.items(), key=lambda x: x[1], reverse=True)[
            :n_features
        ]

        return dict(top_features)

    def _mutual_info_selection(
        self, X: pd.DataFrame, y: pd.Series, n_features: int
    ) -> Dict[str, float]:
        """Mutual information feature selection."""

        # Calculate mutual information
        mi_scores = mutual_info_classif(X, y, random_state=self.random_state)

        # Create feature scores dictionary
        feature_scores = dict(zip(X.columns, mi_scores))

        # Select top features
        top_features = sorted(feature_scores.items(), key=lambda x: x[1], reverse=True)[
            :n_features
        ]

        return dict(top_features)

    def _f_test_selection(
        self, X: pd.DataFrame, y: pd.Series, n_features: int
    ) -> Dict[str, float]:
        """F-test feature selection."""

        # Calculate F-test scores
        f_scores, _ = f_classif(X, y)

        # Create feature scores dictionary
        feature_scores = dict(zip(X.columns, f_scores))

        # Select top features
        top_features = sorted(feature_scores.items(), key=lambda x: x[1], reverse=True)[
            :n_features
        ]

        return dict(top_features)

    def _compute_consensus_scores(self):
        """Compute consensus scores across all methods."""

        if not self.feature_scores_:
            logger.warning("No feature scores available for consensus")
            return

        # Get all unique features
        all_features = set()
        for method_scores in self.feature_scores_.values():
            all_features.update(method_scores.keys())

        # Compute consensus scores
        consensus_scores = {}
        for feature in all_features:
            scores = []
            for method_scores in self.feature_scores_.values():
                if feature in method_scores:
                    scores.append(method_scores[feature])

            if scores:
                # Use mean of normalized scores
                normalized_scores = []
                for method, method_scores in self.feature_scores_.items():
                    if feature in method_scores:
                        # Normalize by max score in method
                        max_score = max(method_scores.values())
                        normalized_scores.append(method_scores[feature] / max_score)

                consensus_scores[feature] = np.mean(normalized_scores)

        self.consensus_scores_ = consensus_scores
        logger.info(f"Computed consensus scores for {len(consensus_scores)} features")

    def _select_final_features(self, n_features: int, stability_threshold: float):
        """Select final features based on consensus scores and stability."""

        if self.consensus_scores_ is None:
            logger.warning("No consensus scores available")
            return

        # Sort features by consensus score
        sorted_features = sorted(
            self.consensus_scores_.items(), key=lambda x: x[1], reverse=True
        )

        # Calculate stability for each feature
        feature_stability = {}
        for feature, _ in sorted_features:
            stability_scores = []
            for method_scores in self.feature_scores_.values():
                if feature in method_scores:
                    # Check if feature is in top n_features for this method
                    method_top_features = sorted(
                        method_scores.items(), key=lambda x: x[1], reverse=True
                    )[:n_features]

                    if feature in [f[0] for f in method_top_features]:
                        stability_scores.append(1.0)
                    else:
                        stability_scores.append(0.0)

            feature_stability[feature] = np.mean(stability_scores)

        # Select features based on consensus score and stability
        selected_features = []
        for feature, consensus_score in sorted_features:
            if len(selected_features) >= n_features:
                break

            stability = feature_stability.get(feature, 0.0)
            if stability >= stability_threshold:
                selected_features.append((feature, consensus_score, stability))

        self.selected_features_ = {
            "features": [f[0] for f in selected_features],
            "consensus_scores": {f[0]: f[1] for f in selected_features},
            "stability_scores": {f[0]: f[2] for f in selected_features},
        }

        logger.info(
            f"Selected {len(selected_features)} features with stability >= {stability_threshold}"
        )

    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance summary."""

        if not self.selected_features_:
            return pd.DataFrame()

        features = self.selected_features_["features"]
        consensus_scores = self.selected_features_["consensus_scores"]
        stability_scores = self.selected_features_["stability_scores"]

        # Create summary DataFrame
        summary_data = []
        for feature in features:
            row = {
                "feature": feature,
                "consensus_score": consensus_scores[feature],
                "stability_score": stability_scores[feature],
                "rank": features.index(feature) + 1,
            }

            # Add individual method scores
            for method, method_scores in self.feature_scores_.items():
                row[f"{method}_score"] = method_scores.get(feature, 0.0)

            summary_data.append(row)

        return pd.DataFrame(summary_data)

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transform data to selected features."""

        if not self.selected_features_:
            raise ValueError("Feature selector not fitted")

        selected_features = self.selected_features_["features"]
        return X[selected_features]


class ConsensusFeatureSelector:
    """
    Advanced consensus feature selection with stability analysis.
    """

    def __init__(self, random_state: int = 42, n_jobs: int = -1):
        """Initialize consensus feature selector."""
        self.random_state = random_state
        self.n_jobs = n_jobs
        self.selector = FeatureSelector(random_state=random_state, n_jobs=n_jobs)

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_bootstrap: int = 100,
        n_features: int = 50,
        stability_threshold: float = 0.6,
        consensus_methods: Optional[List[str]] = None,
    ) -> "ConsensusFeatureSelector":
        """
        Fit consensus feature selection with bootstrap sampling.

        Args:
            X: Feature matrix
            y: Target variable
            n_bootstrap: Number of bootstrap samples
            n_features: Number of features to select
            stability_threshold: Stability threshold
            consensus_methods: Subset of
                random_forest, lasso, xgboost, mutual_info, f_test
                (ablation: omit one or more methods)

        Returns:
            Self
        """
        logger.info(
            f"Starting consensus feature selection with {n_bootstrap} bootstrap samples"
        )

        # Store original data
        self.feature_names_ = X.columns.tolist()
        self.n_features_ = n_features
        default_m = ["random_forest", "lasso", "xgboost", "mutual_info", "f_test"]
        self.consensus_methods_ = list(consensus_methods) if consensus_methods else default_m

        # Bootstrap sampling
        bootstrap_results = []

        with ThreadPoolExecutor(max_workers=_thread_pool_workers(self.n_jobs)) as executor:
            futures = []

            for i in range(n_bootstrap):
                # Bootstrap sample
                np.random.seed(self.random_state + i)
                indices = np.random.choice(len(X), size=len(X), replace=True)
                X_boot = X.iloc[indices]
                y_boot = y.iloc[indices]

                # Submit feature selection task
                future = executor.submit(
                    self._bootstrap_selection, X_boot, y_boot, n_features
                )
                futures.append(future)

            # Collect results
            for future in as_completed(futures):
                try:
                    result = future.result()
                    bootstrap_results.append(result)
                except Exception as e:
                    logger.error(f"Bootstrap selection failed: {str(e)}")

        # Compute consensus
        self._compute_bootstrap_consensus(bootstrap_results, stability_threshold)

        logger.info(f"Consensus feature selection completed")
        return self

    def _bootstrap_selection(
        self, X: pd.DataFrame, y: pd.Series, n_features: int
    ) -> Dict[str, float]:
        """Run feature selection on bootstrap sample."""

        selector = FeatureSelector(random_state=self.random_state)
        selector.fit(
            X,
            y,
            n_features=n_features,
            methods=self.consensus_methods_,
        )

        return selector.consensus_scores_

    def _compute_bootstrap_consensus(
        self, bootstrap_results: List[Dict], stability_threshold: float
    ):
        """Compute consensus from bootstrap results."""

        # Get all features
        all_features = set()
        for result in bootstrap_results:
            all_features.update(result.keys())

        # Compute selection frequency and mean scores
        selection_frequency = {}
        mean_scores = {}

        for feature in all_features:
            scores = []
            for result in bootstrap_results:
                if feature in result:
                    scores.append(result[feature])

            selection_frequency[feature] = len(scores) / len(bootstrap_results)
            mean_scores[feature] = np.mean(scores) if scores else 0.0

        # Select features based on frequency and scores
        selected_features = []
        for feature in all_features:
            frequency = selection_frequency[feature]
            if frequency >= stability_threshold:
                selected_features.append((feature, mean_scores[feature], frequency))

        # Sort by mean score
        selected_features.sort(key=lambda x: x[1], reverse=True)
        selected_features = selected_features[: self.n_features_]

        self.consensus_results_ = {
            "features": [f[0] for f in selected_features],
            "mean_scores": {f[0]: f[1] for f in selected_features},
            "selection_frequency": {f[0]: f[2] for f in selected_features},
            "all_frequencies": selection_frequency,
            "all_scores": mean_scores,
        }

    def get_consensus_summary(self) -> pd.DataFrame:
        """Get consensus feature selection summary."""

        if not hasattr(self, "consensus_results_"):
            return pd.DataFrame()

        features = self.consensus_results_["features"]
        mean_scores = self.consensus_results_["mean_scores"]
        frequencies = self.consensus_results_["selection_frequency"]

        summary_data = []
        for i, feature in enumerate(features):
            row = {
                "feature": feature,
                "rank": i + 1,
                "mean_score": mean_scores[feature],
                "selection_frequency": frequencies[feature],
            }
            summary_data.append(row)

        return pd.DataFrame(summary_data)

    def transform(self, X: pd.DataFrame) -> pd.DataFrame:
        """Transform data to consensus selected features."""

        if not hasattr(self, "consensus_results_"):
            raise ValueError("Consensus selector not fitted")

        selected_features = self.consensus_results_["features"]
        return X[selected_features]
