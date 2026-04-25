"""
Feature selection utilities for biomarker identification.
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.feature_selection import (
    RFE,
    SelectFromModel,
    SelectKBest,
    VarianceThreshold,
    f_classif,
    f_regression,
    mutual_info_classif,
    mutual_info_regression,
)
from sklearn.linear_model import ElasticNet, Lasso, LinearRegression, LogisticRegression
from sklearn.metrics import accuracy_score, mean_squared_error, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score
from sklearn.svm import LinearSVC, LinearSVR

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


def _flatten_linear_coefs(coefficients: np.ndarray) -> np.ndarray:
    """Reduce sklearn linear model coef_ to shape (n_features,) for multiclass/binary."""
    arr = np.asarray(coefficients)
    if arr.ndim == 1:
        return arr
    # LogisticRegression: (n_classes, n_features); take max |coef| across classes
    return np.max(np.abs(arr), axis=0)


class FeatureSelection:
    """
    Handles feature selection for biomarker identification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the feature selection module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.selection_results = {}
        self.selected_features = []
        self.feature_scores = {}

    def filter_methods(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        methods: List[str] = None,
        n_features: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Apply filter-based feature selection methods.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            methods: List of filter methods to apply
            n_features: Number of top features to select
            **kwargs: Additional method-specific parameters

        Returns:
            Filter selection results
        """
        kw = dict(kwargs)
        legacy_method = kw.pop("method", None)
        if methods is None and legacy_method is not None:
            methods = [legacy_method]
        if methods is None:
            methods = ["variance", "f_test", "mutual_info", "correlation"]

        kwargs = kw

        results = {}

        for method in methods:
            try:
                if method == "variance":
                    selected = self._variance_filter(
                        expression_data, n_features, **kwargs
                    )
                elif method == "f_test":
                    selected = self._f_test_filter(
                        expression_data, labels, n_features, **kwargs
                    )
                elif method == "mutual_info":
                    selected = self._mutual_info_filter(
                        expression_data, labels, n_features, **kwargs
                    )
                elif method == "correlation":
                    selected = self._correlation_filter(
                        expression_data, labels, n_features, **kwargs
                    )
                elif method == "anova":
                    selected = self._anova_filter(
                        expression_data, labels, n_features, **kwargs
                    )
                elif method == "chi2":
                    selected = self._chi2_filter(
                        expression_data, labels, n_features, **kwargs
                    )
                else:
                    logger.warning(f"Unknown filter method: {method}")
                    continue

                results[method] = selected
                logger.info(
                    f"Filter method {method} selected {len(selected['selected_features'])} features"
                )

            except Exception as e:
                logger.error(f"Failed to apply {method} filter: {str(e)}")
                results[method] = {"error": str(e)}

        return results

    def _variance_filter(
        self,
        expression_data: pd.DataFrame,
        n_features: int,
        threshold: Optional[float] = None,
        **_: Any,
    ) -> Dict[str, Any]:
        """
        Variance-based feature selection.

        Args:
            expression_data: Expression data matrix
            n_features: Number of features to select
            threshold: Variance threshold (if None, select top n_features)

        Returns:
            Variance filter results
        """
        if threshold is None:
            # Select top n_features by variance
            variances = expression_data.var(axis=1)
            threshold = variances.nlargest(n_features).min()

        selector = VarianceThreshold(threshold=threshold)
        selector.fit(expression_data.T)

        selected_features = expression_data.index[selector.get_support()].tolist()
        feature_scores = expression_data.var(axis=1).to_dict()

        return {
            "method": "variance",
            "threshold": threshold,
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "n_selected": len(selected_features),
        }

    def _f_test_filter(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        n_features: int,
        **_: Any,
    ) -> Dict[str, Any]:
        """
        F-test based feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            n_features: Number of features to select

        Returns:
            F-test filter results
        """
        # Determine if classification or regression
        if labels.dtype == "object" or len(labels.unique()) < 10:
            # Classification
            selector = SelectKBest(score_func=f_classif, k=n_features)
        else:
            # Regression
            selector = SelectKBest(score_func=f_regression, k=n_features)

        selector.fit(expression_data.T, labels)

        selected_features = expression_data.index[selector.get_support()].tolist()
        feature_scores = dict(zip(expression_data.index, selector.scores_))

        return {
            "method": "f_test",
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "n_selected": len(selected_features),
            "p_values": dict(zip(expression_data.index, selector.pvalues_)),
        }

    def _mutual_info_filter(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        n_features: int,
        **_: Any,
    ) -> Dict[str, Any]:
        """
        Mutual information based feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            n_features: Number of features to select

        Returns:
            Mutual information filter results
        """
        # Determine if classification or regression
        if labels.dtype == "object" or len(labels.unique()) < 10:
            # Classification
            selector = SelectKBest(score_func=mutual_info_classif, k=n_features)
        else:
            # Regression
            selector = SelectKBest(score_func=mutual_info_regression, k=n_features)

        selector.fit(expression_data.T, labels)

        selected_features = expression_data.index[selector.get_support()].tolist()
        feature_scores = dict(zip(expression_data.index, selector.scores_))

        return {
            "method": "mutual_info",
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "n_selected": len(selected_features),
        }

    def _correlation_filter(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        n_features: int,
        **_: Any,
    ) -> Dict[str, Any]:
        """
        Correlation-based feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            n_features: Number of features to select

        Returns:
            Correlation filter results
        """
        # Calculate correlation with target
        correlations = []
        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]
            if labels.dtype == "object":
                # For categorical labels, use correlation with encoded labels
                from sklearn.preprocessing import LabelEncoder

                le = LabelEncoder()
                encoded_labels = le.fit_transform(labels)
                corr = np.corrcoef(gene_data, encoded_labels)[0, 1]
            else:
                corr = np.corrcoef(gene_data, labels)[0, 1]

            correlations.append(abs(corr) if not np.isnan(corr) else 0)

        # Select top features
        feature_scores = dict(zip(expression_data.index, correlations))
        sorted_features = sorted(
            feature_scores.items(), key=lambda x: x[1], reverse=True
        )
        selected_features = [feature for feature, score in sorted_features[:n_features]]

        return {
            "method": "correlation",
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "n_selected": len(selected_features),
        }

    def _anova_filter(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        n_features: int,
        **_: Any,
    ) -> Dict[str, Any]:
        """
        ANOVA-based feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            n_features: Number of features to select

        Returns:
            ANOVA filter results
        """
        from scipy import stats

        f_scores = []
        p_values = []

        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]

            # Group by labels
            unique_labels = labels.unique()
            groups = [gene_data[labels == label] for label in unique_labels]

            # Perform one-way ANOVA
            try:
                f_stat, p_val = stats.f_oneway(*groups)
                f_scores.append(f_stat)
                p_values.append(p_val)
            except:
                f_scores.append(0)
                p_values.append(1.0)

        # Select top features by F-score
        feature_scores = dict(zip(expression_data.index, f_scores))
        sorted_features = sorted(
            feature_scores.items(), key=lambda x: x[1], reverse=True
        )
        selected_features = [feature for feature, score in sorted_features[:n_features]]

        return {
            "method": "anova",
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "p_values": dict(zip(expression_data.index, p_values)),
            "n_selected": len(selected_features),
        }

    def _chi2_filter(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        n_features: int,
        **_: Any,
    ) -> Dict[str, Any]:
        """
        Chi-squared based feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            n_features: Number of features to select

        Returns:
            Chi-squared filter results
        """
        from sklearn.feature_selection import chi2

        # Chi-squared requires non-negative features
        # Add minimum value to make all features non-negative
        min_val = expression_data.min().min()
        if min_val < 0:
            expression_data_adj = expression_data - min_val
        else:
            expression_data_adj = expression_data

        selector = SelectKBest(score_func=chi2, k=n_features)
        selector.fit(expression_data_adj.T, labels)

        selected_features = expression_data.index[selector.get_support()].tolist()
        feature_scores = dict(zip(expression_data.index, selector.scores_))

        return {
            "method": "chi2",
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "p_values": dict(zip(expression_data.index, selector.pvalues_)),
            "n_selected": len(selected_features),
        }

    def wrapper_methods(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        methods: List[str] = None,
        n_features: int = 50,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Apply wrapper-based feature selection methods.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            methods: List of wrapper methods to apply
            n_features: Number of features to select
            **kwargs: Additional method-specific parameters

        Returns:
            Wrapper selection results
        """
        if methods is None:
            methods = ["rfe", "sequential_forward", "sequential_backward"]

        results = {}

        for method in methods:
            try:
                if method == "rfe":
                    selected = self._rfe_wrapper(
                        expression_data, labels, n_features, **kwargs
                    )
                elif method == "sequential_forward":
                    selected = self._sequential_forward_wrapper(
                        expression_data, labels, n_features, **kwargs
                    )
                elif method == "sequential_backward":
                    selected = self._sequential_backward_wrapper(
                        expression_data, labels, n_features, **kwargs
                    )
                else:
                    logger.warning(f"Unknown wrapper method: {method}")
                    continue

                results[method] = selected
                logger.info(
                    f"Wrapper method {method} selected {len(selected['selected_features'])} features"
                )

            except Exception as e:
                logger.error(f"Failed to apply {method} wrapper: {str(e)}")
                results[method] = {"error": str(e)}

        return results

    def _rfe_wrapper(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        n_features: int,
        estimator_type: str = "logistic",
    ) -> Dict[str, Any]:
        """
        Recursive Feature Elimination wrapper.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            n_features: Number of features to select
            estimator_type: Type of estimator to use

        Returns:
            RFE wrapper results
        """
        # Select estimator
        if estimator_type == "logistic":
            estimator = LogisticRegression(random_state=42, max_iter=1000)
        elif estimator_type == "linear":
            estimator = LinearRegression()
        elif estimator_type == "svm":
            estimator = LinearSVC(random_state=42, max_iter=1000)
        else:
            estimator = LogisticRegression(random_state=42, max_iter=1000)

        # Apply RFE
        selector = RFE(estimator=estimator, n_features_to_select=n_features)
        selector.fit(expression_data.T, labels)

        selected_features = expression_data.index[selector.get_support()].tolist()
        feature_ranking = dict(zip(expression_data.index, selector.ranking_))

        return {
            "method": "rfe",
            "estimator_type": estimator_type,
            "selected_features": selected_features,
            "feature_ranking": feature_ranking,
            "n_selected": len(selected_features),
        }

    def _sequential_forward_wrapper(
        self, expression_data: pd.DataFrame, labels: pd.Series, n_features: int
    ) -> Dict[str, Any]:
        """
        Sequential Forward Selection wrapper.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            n_features: Number of features to select

        Returns:
            Sequential forward wrapper results
        """
        # Simplified implementation
        # For full implementation, consider using mlxtend.feature_selection

        selected_features = []
        remaining_features = list(expression_data.index)

        for i in range(min(n_features, len(remaining_features))):
            best_score = -1
            best_feature = None

            for feature in remaining_features:
                # Add feature to current selection
                current_features = selected_features + [feature]
                current_data = expression_data.loc[current_features].T

                # Evaluate with cross-validation
                try:
                    estimator = LogisticRegression(random_state=42, max_iter=1000)
                    scores = cross_val_score(
                        estimator, current_data, labels, cv=3, scoring="accuracy"
                    )
                    score = scores.mean()

                    if score > best_score:
                        best_score = score
                        best_feature = feature
                except:
                    continue

            if best_feature is not None:
                selected_features.append(best_feature)
                remaining_features.remove(best_feature)
            else:
                break

        return {
            "method": "sequential_forward",
            "selected_features": selected_features,
            "n_selected": len(selected_features),
        }

    def _sequential_backward_wrapper(
        self, expression_data: pd.DataFrame, labels: pd.Series, n_features: int
    ) -> Dict[str, Any]:
        """
        Sequential Backward Selection wrapper.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            n_features: Number of features to select

        Returns:
            Sequential backward wrapper results
        """
        # Simplified implementation
        # For full implementation, consider using mlxtend.feature_selection

        selected_features = list(expression_data.index)

        while len(selected_features) > n_features:
            worst_score = float("inf")
            worst_feature = None

            for feature in selected_features:
                # Remove feature from current selection
                current_features = [f for f in selected_features if f != feature]
                current_data = expression_data.loc[current_features].T

                # Evaluate with cross-validation
                try:
                    estimator = LogisticRegression(random_state=42, max_iter=1000)
                    scores = cross_val_score(
                        estimator, current_data, labels, cv=3, scoring="accuracy"
                    )
                    score = scores.mean()

                    if score < worst_score:
                        worst_score = score
                        worst_feature = feature
                except:
                    continue

            if worst_feature is not None:
                selected_features.remove(worst_feature)
            else:
                break

        return {
            "method": "sequential_backward",
            "selected_features": selected_features,
            "n_selected": len(selected_features),
        }

    def embedded_methods(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        methods: List[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Apply embedded feature selection methods.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            methods: List of embedded methods to apply
            **kwargs: Additional method-specific parameters

        Returns:
            Embedded selection results
        """
        if methods is None:
            methods = ["lasso", "elastic_net", "random_forest", "svm"]

        results = {}

        for method in methods:
            try:
                if method == "lasso":
                    # Filter kwargs to only pass lasso-specific ones
                    lasso_kwargs = {k: v for k, v in kwargs.items() if k == "alpha"}
                    selected = self._lasso_embedded(
                        expression_data, labels, **lasso_kwargs
                    )
                elif method == "elastic_net":
                    # Filter kwargs to only pass elastic_net-specific ones
                    en_kwargs = {
                        k: v for k, v in kwargs.items() if k in ["alpha", "l1_ratio"]
                    }
                    selected = self._elastic_net_embedded(
                        expression_data, labels, **en_kwargs
                    )
                elif method == "random_forest":
                    rf_kwargs = {
                        k: v for k, v in kwargs.items() if k == "n_estimators"
                    }
                    selected = self._random_forest_embedded(
                        expression_data, labels, **rf_kwargs
                    )
                elif method == "svm":
                    svm_kwargs = {k: v for k, v in kwargs.items() if k == "C"}
                    selected = self._svm_embedded(expression_data, labels, **svm_kwargs)
                else:
                    logger.warning(f"Unknown embedded method: {method}")
                    continue

                results[method] = selected
                logger.info(
                    f"Embedded method {method} selected {len(selected['selected_features'])} features"
                )

            except Exception as e:
                logger.error(f"Failed to apply {method} embedded method: {str(e)}")
                results[method] = {"error": str(e)}

        return results

    def _lasso_embedded(
        self, expression_data: pd.DataFrame, labels: pd.Series, alpha: float = 0.01
    ) -> Dict[str, Any]:
        """
        LASSO embedded feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            alpha: Regularization parameter

        Returns:
            LASSO embedded results
        """
        # Determine if classification or regression
        if labels.dtype == "object" or len(labels.unique()) < 10:
            # Classification
            estimator = LogisticRegression(
                penalty="l1", C=1 / alpha, solver="liblinear", random_state=42
            )
        else:
            # Regression
            estimator = Lasso(alpha=alpha, random_state=42)

        estimator.fit(expression_data.T, labels)

        # Get non-zero coefficients
        if hasattr(estimator, "coef_"):
            coefficients = _flatten_linear_coefs(estimator.coef_)
        else:
            coefficients = np.asarray(estimator.feature_importances_)

        selected_features = expression_data.index[coefficients != 0].tolist()
        feature_scores = dict(zip(expression_data.index, np.abs(coefficients)))

        return {
            "method": "lasso",
            "alpha": alpha,
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "n_selected": len(selected_features),
        }

    def _elastic_net_embedded(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        alpha: float = 0.01,
        l1_ratio: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Elastic Net embedded feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            alpha: Regularization parameter
            l1_ratio: L1 ratio parameter

        Returns:
            Elastic Net embedded results
        """
        # Determine if classification or regression
        if labels.dtype == "object" or len(labels.unique()) < 10:
            # Classification
            estimator = LogisticRegression(
                penalty="elasticnet",
                C=1 / alpha,
                l1_ratio=l1_ratio,
                solver="saga",
                random_state=42,
            )
        else:
            # Regression
            estimator = ElasticNet(alpha=alpha, l1_ratio=l1_ratio, random_state=42)

        estimator.fit(expression_data.T, labels)

        # Get non-zero coefficients
        if hasattr(estimator, "coef_"):
            coefficients = _flatten_linear_coefs(estimator.coef_)
        else:
            coefficients = np.asarray(estimator.feature_importances_)

        selected_features = expression_data.index[coefficients != 0].tolist()
        feature_scores = dict(zip(expression_data.index, np.abs(coefficients)))

        return {
            "method": "elastic_net",
            "alpha": alpha,
            "l1_ratio": l1_ratio,
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "n_selected": len(selected_features),
        }

    def _random_forest_embedded(
        self, expression_data: pd.DataFrame, labels: pd.Series, n_estimators: int = 100
    ) -> Dict[str, Any]:
        """
        Random Forest embedded feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            n_estimators: Number of trees

        Returns:
            Random Forest embedded results
        """
        # Determine if classification or regression
        if labels.dtype == "object" or len(labels.unique()) < 10:
            # Classification
            estimator = RandomForestClassifier(
                n_estimators=n_estimators, random_state=42
            )
        else:
            # Regression
            estimator = RandomForestRegressor(
                n_estimators=n_estimators, random_state=42
            )

        estimator.fit(expression_data.T, labels)

        # Get feature importances
        feature_importances = estimator.feature_importances_

        # Select features with importance > mean
        importance_threshold = feature_importances.mean()
        selected_features = expression_data.index[
            feature_importances > importance_threshold
        ].tolist()
        feature_scores = dict(zip(expression_data.index, feature_importances))

        return {
            "method": "random_forest",
            "n_estimators": n_estimators,
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "n_selected": len(selected_features),
            "importance_threshold": importance_threshold,
        }

    def _svm_embedded(
        self, expression_data: pd.DataFrame, labels: pd.Series, C: float = 1.0
    ) -> Dict[str, Any]:
        """
        SVM embedded feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            C: Regularization parameter

        Returns:
            SVM embedded results
        """
        # Determine if classification or regression
        if labels.dtype == "object" or len(labels.unique()) < 10:
            # Classification
            estimator = LinearSVC(C=C, random_state=42, max_iter=1000)
        else:
            # Regression
            estimator = LinearSVR(C=C, max_iter=1000)

        estimator.fit(expression_data.T, labels)

        # Get coefficients
        coefficients = (
            estimator.coef_[0] if len(estimator.coef_.shape) > 1 else estimator.coef_
        )

        # Select features with non-zero coefficients
        selected_features = expression_data.index[coefficients != 0].tolist()
        feature_scores = dict(zip(expression_data.index, abs(coefficients)))

        return {
            "method": "svm",
            "C": C,
            "selected_features": selected_features,
            "feature_scores": feature_scores,
            "n_selected": len(selected_features),
        }

    def stability_selection(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        n_bootstrap: int = 100,
        threshold: float = 0.5,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Stability selection for feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            n_bootstrap: Number of bootstrap samples
            threshold: Selection threshold
            **kwargs: Additional parameters

        Returns:
            Stability selection results
        """
        from sklearn.utils import resample

        feature_selection_counts = {feature: 0 for feature in expression_data.index}

        # Check if bootstrapping is feasible
        if len(labels) < 2:
            logger.warning(
                f"Not enough samples for stability selection (need at least 2, have {len(labels)})"
            )
            return {
                "method": "stability_selection",
                "error": f"Not enough samples for bootstrapping (need at least 2, have {len(labels)})",
                "selected_features": [],
                "feature_scores": {},
                "n_selected": 0,
            }

        successful_bootstraps = 0
        for i in range(n_bootstrap):
            # Bootstrap sample
            try:
                indices = resample(
                    range(len(labels)),
                    n_samples=len(labels),
                    stratify=labels if len(labels.unique()) > 1 else None,
                    random_state=i,
                )
                # Convert indices to list to ensure proper indexing
                indices_list = list(indices)
                # Select columns (samples) by position - ensure we get a DataFrame
                bootstrap_data = expression_data.iloc[:, indices_list]
                bootstrap_labels = labels.iloc[indices_list]

                # Check if bootstrap_labels has at least two classes
                if len(bootstrap_labels.unique()) < 2:
                    logger.warning(
                        f"Skipping bootstrap iteration {i}: Only one class found in bootstrap sample."
                    )
                    continue

                # Apply feature selection (using LASSO as example)
                # Filter kwargs to only pass lasso-specific ones
                lasso_kwargs = {k: v for k, v in kwargs.items() if k == "alpha"}
                selection_result = self._lasso_embedded(
                    bootstrap_data, bootstrap_labels, **lasso_kwargs
                )
                selected_features = selection_result["selected_features"]

                # Count selections
                for feature in selected_features:
                    feature_selection_counts[feature] += 1

                successful_bootstraps += 1
            except Exception as e:
                logger.warning(f"Bootstrap iteration {i} failed: {str(e)}")
                continue

        # Calculate selection probabilities (use successful bootstraps)
        if successful_bootstraps == 0:
            logger.warning(
                "No successful bootstrap iterations. Cannot calculate selection probabilities."
            )
            return {
                "method": "stability_selection",
                "error": "No successful bootstrap iterations",
                "selected_features": [],
                "feature_scores": {},
                "n_selected": 0,
            }

        selection_probabilities = {
            feature: count / successful_bootstraps
            for feature, count in feature_selection_counts.items()
        }

        # Select stable features
        stable_features = [
            feature
            for feature, prob in selection_probabilities.items()
            if prob >= threshold
        ]

        return {
            "method": "stability_selection",
            "n_bootstrap": n_bootstrap,
            "threshold": threshold,
            "selected_features": stable_features,
            "selection_probabilities": selection_probabilities,
            "n_selected": len(stable_features),
        }

    def ensemble_selection(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        methods: List[str] = None,
        voting_threshold: float = 0.5,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Ensemble feature selection combining multiple methods.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            methods: List of selection methods to combine
            voting_threshold: Threshold for ensemble voting
            **kwargs: Additional parameters

        Returns:
            Ensemble selection results
        """
        if methods is None:
            methods = ["f_test", "mutual_info", "lasso", "random_forest"]

        # Apply individual methods
        all_results = {}

        # Filter methods
        filter_results = self.filter_methods(
            expression_data,
            labels,
            methods=[
                m
                for m in methods
                if m
                in ["variance", "f_test", "mutual_info", "correlation", "anova", "chi2"]
            ],
            **kwargs,
        )
        all_results.update(filter_results)

        # Embedded methods
        embedded_results = self.embedded_methods(
            expression_data,
            labels,
            methods=[
                m
                for m in methods
                if m in ["lasso", "elastic_net", "random_forest", "svm"]
            ],
            **kwargs,
        )
        all_results.update(embedded_results)

        # Count feature selections across methods
        feature_votes = {feature: 0 for feature in expression_data.index}

        for method, result in all_results.items():
            if "error" not in result and "selected_features" in result:
                for feature in result["selected_features"]:
                    feature_votes[feature] += 1

        # Select features that meet voting threshold
        n_methods = len([r for r in all_results.values() if "error" not in r])
        min_votes = int(voting_threshold * n_methods)

        ensemble_features = [
            feature for feature, votes in feature_votes.items() if votes >= min_votes
        ]

        return {
            "method": "ensemble",
            "individual_methods": all_results,
            "voting_threshold": voting_threshold,
            "min_votes": min_votes,
            "selected_features": ensemble_features,
            "feature_votes": feature_votes,
            "n_selected": len(ensemble_features),
        }

    def get_selection_summary(self) -> Dict[str, Any]:
        """
        Get summary of feature selection results.

        Returns:
            Selection summary dictionary
        """
        if not self.selection_results:
            return {"status": "No selection performed"}

        summary = {
            "methods_applied": list(self.selection_results.keys()),
            "total_features_selected": len(
                set().union(
                    *[
                        result.get("selected_features", [])
                        for result in self.selection_results.values()
                        if "error" not in result
                    ]
                )
            ),
            "method_results": self.selection_results,
        }

        return summary

    def save_selection_results(self, output_path: str) -> str:
        """
        Save feature selection results to file.

        Args:
            output_path: Output file path

        Returns:
            Path to saved file
        """
        import json

        try:
            with open(output_path, "w") as f:
                json.dump(self.selection_results, f, indent=2, default=str)

            logger.info(f"Selection results saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save selection results: {str(e)}")
            raise
