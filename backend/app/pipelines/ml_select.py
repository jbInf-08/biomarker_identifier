"""
Machine learning selection pipeline for biomarker identification.
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_score

from ..data_processing.feature_selection import FeatureSelection
from ..utils.adaptive_parameters import AdaptiveParameters
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class MLSelectionPipeline:
    """
    Handles machine learning-based feature selection for biomarker identification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the MLSelectionPipeline module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.feature_selector = FeatureSelection(config)
        self.selection_results = {}

    def run_ml_selection(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        selection_methods: List[str] = None,
        n_features: int = 100,
        stability_bootstraps: int = 100,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comprehensive ML-based feature selection.

        Args:
            expression_data: Expression data matrix
            labels: Sample labels
            selection_methods: List of selection methods to apply
            n_features: Number of features to select
            stability_bootstraps: Number of bootstrap samples for stability selection
            **kwargs: Additional parameters

        Returns:
            ML selection results
        """
        try:
            # Get adaptive parameters based on dataset size
            n_classes = len(labels.unique()) if labels is not None else 2
            ml_params = AdaptiveParameters.get_ml_parameters(
                expression_data.shape[1], expression_data.shape[0], n_classes
            )

            # Adjust n_features based on adaptive parameters
            max_features = ml_params.get("max_features", n_features)
            n_features = min(n_features, max_features, expression_data.shape[0])

            # Adjust stability_bootstraps based on adaptive parameters
            if not ml_params.get("bootstrap_enabled", True):
                stability_bootstraps = 0
            else:
                max_bootstraps = ml_params.get("n_bootstraps", stability_bootstraps)
                stability_bootstraps = min(stability_bootstraps, max_bootstraps)

            if selection_methods is None:
                # Select methods based on adaptive parameters
                selection_methods = []
                if ml_params.get("filter_methods", True):
                    selection_methods.extend(["f_test", "mutual_info"])
                if ml_params.get("embedded_methods", True):
                    selection_methods.extend(["lasso", "random_forest"])
                if ml_params.get("wrapper_methods", False):
                    selection_methods.append("rfe")
                if not selection_methods:
                    # Fallback to basic methods
                    selection_methods = ["f_test", "lasso"]

            results = {
                "expression_data": expression_data,
                "labels": labels,
                "selection_methods": selection_methods,
                "n_features": n_features,
                "adaptive_parameters": ml_params,
                "method_results": {},
            }

            # Step 1: Filter methods (if enabled)
            if ml_params.get("filter_methods", True):
                filter_methods = [
                    m
                    for m in selection_methods
                    if m
                    in [
                        "variance",
                        "f_test",
                        "mutual_info",
                        "correlation",
                        "anova",
                        "chi2",
                    ]
                ]
                if filter_methods:
                    filter_results = self.feature_selector.filter_methods(
                        expression_data, labels, filter_methods, n_features, **kwargs
                    )
                    results["method_results"]["filter"] = filter_results

            # Step 2: Wrapper methods (if enabled)
            if ml_params.get("wrapper_methods", False):
                wrapper_methods = [
                    m
                    for m in selection_methods
                    if m in ["rfe", "sequential_forward", "sequential_backward"]
                ]
                if wrapper_methods:
                    wrapper_results = self.feature_selector.wrapper_methods(
                        expression_data, labels, wrapper_methods, n_features, **kwargs
                    )
                    results["method_results"]["wrapper"] = wrapper_results

            # Step 3: Embedded methods (if enabled)
            if ml_params.get("embedded_methods", True):
                embedded_methods = [
                    m
                    for m in selection_methods
                    if m in ["lasso", "elastic_net", "random_forest", "svm"]
                ]
                if embedded_methods:
                    embedded_results = self.feature_selector.embedded_methods(
                        expression_data, labels, embedded_methods, **kwargs
                    )
                    results["method_results"]["embedded"] = embedded_results

            # Step 4: Stability selection (if enabled)
            if ml_params.get("stability_selection", False) and stability_bootstraps > 0:
                stability_results = self.feature_selector.stability_selection(
                    expression_data, labels, stability_bootstraps, **kwargs
                )
                results["method_results"]["stability"] = stability_results

            # Step 5: Ensemble selection
            ensemble_kwargs = dict(kwargs)
            ensemble_kwargs.setdefault("n_features", n_features)
            ensemble_results = self.feature_selector.ensemble_selection(
                expression_data, labels, selection_methods, **ensemble_kwargs
            )
            results["method_results"]["ensemble"] = ensemble_results

            # Step 6: Generate consensus features
            consensus_features = self._generate_consensus_features(results)
            results["consensus_features"] = consensus_features

            # Step 7: Evaluate selected features
            evaluation_results = self._evaluate_selected_features(
                expression_data, labels, consensus_features, ml_params
            )
            results["evaluation"] = evaluation_results

            # Step 8: Generate summary
            summary = self._generate_selection_summary(results)
            results["summary"] = summary

            # Step 9: Generate plots
            plots = self._generate_selection_plots(results)
            results["plots"] = plots

            self.selection_results = results
            logger.info("ML selection pipeline completed")

            return results

        except Exception as e:
            logger.error(f"Failed to run ML selection pipeline: {str(e)}")
            raise

    def get_selected_features(self, top_n: int = 20) -> List[str]:
        """Return top consensus features from the last ``run_ml_selection`` call."""
        if not self.selection_results:
            return []
        consensus = self.selection_results.get("consensus_features") or {}
        entries = consensus.get("consensus_features") or []
        names: List[str] = []
        for item in entries[:top_n]:
            if isinstance(item, dict) and "feature" in item:
                names.append(str(item["feature"]))
            elif isinstance(item, str):
                names.append(item)
        return names

    def _generate_consensus_features(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate consensus features from multiple methods.

        Args:
            results: Selection results

        Returns:
            Consensus features dictionary
        """
        all_selected_features = {}

        # Collect features from all methods
        for category, category_results in results["method_results"].items():
            if not isinstance(category_results, dict):
                continue
            # Categories like stability and ensemble store one result dict at the top level
            # (with selected_features), not nested by sub-method like filter/embedded.
            top_sel = category_results.get("selected_features")
            if (
                isinstance(top_sel, (list, tuple))
                and "error" not in category_results
            ):
                all_selected_features[category] = list(top_sel)
                continue

            for method, method_result in category_results.items():
                # Handle case where method_result might be an int or other non-dict type
                if (
                    isinstance(method_result, dict)
                    and "error" not in method_result
                    and "selected_features" in method_result
                ):
                    all_selected_features[f"{category}_{method}"] = method_result[
                        "selected_features"
                    ]

        # Calculate feature frequency across methods
        feature_counts = {}
        for method_features in all_selected_features.values():
            for feature in method_features:
                feature_counts[feature] = feature_counts.get(feature, 0) + 1

        # Calculate consensus score
        n_methods = len(all_selected_features)
        consensus_features = []
        consensus_scores = {}

        for feature, count in feature_counts.items():
            consensus_score = count / n_methods
            consensus_scores[feature] = consensus_score

            # Require agreement across a modest fraction of method buckets (filter / embedded / stability / ensemble).
            min_consensus = float(self.config.get("consensus_threshold", 0.25))
            if consensus_score >= min_consensus:
                consensus_features.append(
                    {
                        "feature": feature,
                        "consensus_score": consensus_score,
                        "selection_count": count,
                        "methods": [
                            method
                            for method, features in all_selected_features.items()
                            if feature in features
                        ],
                    }
                )

        # Sort by consensus score
        consensus_features.sort(key=lambda x: x["consensus_score"], reverse=True)

        return {
            "consensus_features": consensus_features,
            "consensus_scores": consensus_scores,
            "feature_counts": feature_counts,
            "method_features": all_selected_features,
        }

    def _evaluate_selected_features(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        consensus_features: Dict[str, Any],
        ml_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate selected features using cross-validation.

        Args:
            expression_data: Expression data matrix
            labels: Sample labels
            consensus_features: Consensus features dictionary
            ml_params: Adaptive ML parameters (optional)

        Returns:
            Evaluation results
        """
        if ml_params is None:
            n_classes = len(labels.unique()) if labels is not None else 2
            ml_params = AdaptiveParameters.get_ml_parameters(
                expression_data.shape[1], expression_data.shape[0], n_classes
            )
        evaluation_results = {}

        # Get top consensus features
        top_features = [
            f["feature"] for f in consensus_features["consensus_features"][:50]
        ]

        if not top_features:
            return {"error": "No consensus features found"}

        # Prepare data
        X = expression_data.loc[top_features].T
        y = labels

        # Evaluate with different numbers of features
        feature_numbers = [10, 20, 30, 50]
        if len(top_features) < 50:
            feature_numbers = [min(n, len(top_features)) for n in feature_numbers]

        for n_features in feature_numbers:
            try:
                # Select top n features
                selected_features = top_features[:n_features]
                X_subset = X[selected_features]

                # Cross-validation with simple classifier (adaptive folds)
                from sklearn.linear_model import LogisticRegression
                from sklearn.model_selection import cross_val_score

                # Get adaptive CV folds
                cv_folds = ml_params.get("cv_folds", 5)
                min_samples_for_cv = ml_params.get("min_samples_for_cv", 3)
                use_stratified = ml_params.get("stratified_cv", True)

                # Adjust CV based on sample size
                if len(y) < min_samples_for_cv:
                    logger.warning(
                        f"Not enough samples for CV (need {min_samples_for_cv}, have {len(y)})"
                    )
                    continue

                # Ensure cv_folds doesn't exceed sample size
                cv_folds = min(cv_folds, len(y))
                if cv_folds < 2:
                    cv_folds = 2

                # Use stratified CV if enabled and possible
                if use_stratified and len(y.unique()) >= 2:
                    from sklearn.model_selection import StratifiedKFold

                    cv = StratifiedKFold(
                        n_splits=cv_folds, shuffle=True, random_state=42
                    )
                else:
                    from sklearn.model_selection import KFold

                    cv = KFold(n_splits=cv_folds, shuffle=True, random_state=42)

                clf = LogisticRegression(random_state=42, max_iter=1000)

                # Calculate various metrics
                cv_scores = cross_val_score(clf, X_subset, y, cv=cv, scoring="accuracy")
                roc_scores = cross_val_score(clf, X_subset, y, cv=cv, scoring="roc_auc")
                f1_scores = cross_val_score(
                    clf, X_subset, y, cv=cv, scoring="f1_weighted"
                )

                evaluation_results[f"n_features_{n_features}"] = {
                    "selected_features": selected_features,
                    "accuracy_mean": float(cv_scores.mean()),
                    "accuracy_std": float(cv_scores.std()),
                    "roc_auc_mean": float(roc_scores.mean()),
                    "roc_auc_std": float(roc_scores.std()),
                    "f1_mean": float(f1_scores.mean()),
                    "f1_std": float(f1_scores.std()),
                }

            except Exception as e:
                logger.warning(f"Failed to evaluate {n_features} features: {str(e)}")
                evaluation_results[f"n_features_{n_features}"] = {"error": str(e)}

        return evaluation_results

    def _generate_selection_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate selection summary.

        Args:
            results: Selection results

        Returns:
            Selection summary
        """
        summary = {
            "n_genes": results["expression_data"].shape[0],
            "n_samples": results["expression_data"].shape[1],
            "methods_applied": list(results["method_results"].keys()),
            "consensus_features_count": len(
                results.get("consensus_features", {}).get("consensus_features", [])
            ),
            "method_summary": {},
        }

        # Summarize each method category
        for category, category_results in results["method_results"].items():
            summary["method_summary"][category] = {
                "n_methods": len(category_results),
                "methods": list(category_results.keys()),
                "total_features": sum(
                    len(method_result.get("selected_features", []))
                    if isinstance(method_result, dict)
                    else 0
                    for method_result in category_results.values()
                    if isinstance(method_result, dict) and "error" not in method_result
                ),
            }

        # Add evaluation summary
        if "evaluation" in results:
            evaluation = results["evaluation"]
            summary["evaluation_summary"] = {}
            for key, eval_result in evaluation.items():
                # Handle case where eval_result might not be a dict
                if isinstance(eval_result, dict) and "error" not in eval_result:
                    summary["evaluation_summary"][key] = {
                        "accuracy": eval_result.get("accuracy_mean", 0),
                        "roc_auc": eval_result.get("roc_auc_mean", 0),
                        "f1_score": eval_result.get("f1_mean", 0),
                    }

        return summary

    def _generate_selection_plots(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate selection plots.

        Args:
            results: Selection results

        Returns:
            Dictionary of plot objects
        """
        plots = {}

        try:
            import plotly.express as px
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # Consensus score distribution
            consensus_features = results.get("consensus_features", {})
            if consensus_features and isinstance(consensus_features, dict):
                # consensus_features is a dict of {feature: score}
                if len(consensus_features) > 0:
                    consensus_df = pd.DataFrame(
                        list(consensus_features.items()),
                        columns=["feature", "consensus_score"],
                    )
                    if (
                        not consensus_df.empty
                        and "consensus_score" in consensus_df.columns
                    ):
                        try:
                            fig_consensus = px.histogram(
                                consensus_df,
                                x="consensus_score",
                                title="Consensus Score Distribution",
                                labels={
                                    "consensus_score": "Consensus Score",
                                    "count": "Count",
                                },
                            )
                            plots["consensus_distribution"] = fig_consensus
                        except Exception as e:
                            logger.warning(
                                f"Failed to generate consensus histogram: {e}"
                            )

                # Top consensus features
                top_consensus = consensus_df.head(20)
                fig_top = px.bar(
                    top_consensus,
                    x="feature",
                    y="consensus_score",
                    title="Top Consensus Features",
                    labels={"feature": "Feature", "consensus_score": "Consensus Score"},
                )
                fig_top.update_xaxes(tickangle=45)
                plots["top_consensus_features"] = fig_top

            # Method comparison
            method_summary = results.get("summary", {}).get("method_summary", {})
            if method_summary:
                comparison_data = []
                for category, summary in method_summary.items():
                    comparison_data.append(
                        {
                            "category": category,
                            "n_methods": summary["n_methods"],
                            "total_features": summary["total_features"],
                        }
                    )

                if comparison_data:
                    comparison_df = pd.DataFrame(comparison_data)

                    fig_methods = px.bar(
                        comparison_df,
                        x="category",
                        y="total_features",
                        title="Features Selected by Method Category",
                        labels={
                            "category": "Method Category",
                            "total_features": "Total Features",
                        },
                    )
                    plots["method_comparison"] = fig_methods

            # Evaluation plots
            evaluation = results.get("evaluation", {})
            if evaluation:
                eval_data = []
                for key, eval_result in evaluation.items():
                    # Handle case where eval_result might not be a dict or key might not have expected format
                    if isinstance(eval_result, dict) and "error" not in eval_result:
                        try:
                            n_features = int(key.split("_")[-1])
                        except (ValueError, IndexError):
                            # Key doesn't have expected format, skip
                            continue
                        eval_data.append(
                            {
                                "n_features": n_features,
                                "accuracy": eval_result.get("accuracy_mean", 0),
                                "roc_auc": eval_result.get("roc_auc_mean", 0),
                                "f1_score": eval_result.get("f1_mean", 0),
                            }
                        )

                if eval_data:
                    eval_df = pd.DataFrame(eval_data)

                    # Performance vs number of features
                    fig_performance = px.line(
                        eval_df,
                        x="n_features",
                        y=["accuracy", "roc_auc", "f1_score"],
                        title="Performance vs Number of Features",
                        labels={
                            "n_features": "Number of Features",
                            "value": "Score",
                            "variable": "Metric",
                        },
                    )
                    plots["performance_vs_features"] = fig_performance

        except ImportError:
            logger.warning("Plotly not available, skipping selection plots")

        return plots

    def get_consensus_features(self, min_consensus_score: float = 0.5) -> List[str]:
        """
        Get consensus features above a minimum score.

        Args:
            min_consensus_score: Minimum consensus score threshold

        Returns:
            List of consensus features
        """
        if not self.selection_results:
            return []

        consensus_features = self.selection_results.get("consensus_features", {})
        if "consensus_features" not in consensus_features:
            return []

        return [
            f["feature"]
            for f in consensus_features["consensus_features"]
            if f["consensus_score"] >= min_consensus_score
        ]

    def get_top_features(self, n_features: int = 20) -> List[str]:
        """
        Get top consensus features.

        Args:
            n_features: Number of top features to return

        Returns:
            List of top features
        """
        if not self.selection_results:
            return []

        consensus_features = self.selection_results.get("consensus_features", {})
        if "consensus_features" not in consensus_features:
            return []

        return [
            f["feature"] for f in consensus_features["consensus_features"][:n_features]
        ]

    def save_selection_results(self, output_path: str, format: str = "json") -> str:
        """
        Save selection results to file.

        Args:
            output_path: Output file path
            format: Output format

        Returns:
            Path to saved file
        """
        if not self.selection_results:
            raise ValueError("No selection results to save")

        try:
            if format.lower() == "json":
                import json

                with open(output_path, "w") as f:
                    json.dump(self.selection_results, f, indent=2, default=str)
            elif format.lower() == "csv":
                # Save consensus features as CSV
                consensus_features = self.selection_results.get(
                    "consensus_features", {}
                )
                if "consensus_features" in consensus_features:
                    df = pd.DataFrame(consensus_features["consensus_features"])
                    df.to_csv(output_path, index=False)
                else:
                    # Create empty CSV with headers
                    pd.DataFrame(
                        columns=[
                            "feature",
                            "consensus_score",
                            "selection_count",
                            "methods",
                        ]
                    ).to_csv(output_path, index=False)
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Selection results saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save selection results: {str(e)}")
            raise

    def get_selection_summary(self) -> Dict[str, Any]:
        """
        Get selection summary.

        Returns:
            Selection summary dictionary
        """
        if not self.selection_results:
            return {"status": "No selection performed"}

        return self.selection_results.get("summary", {"status": "unknown"})

    # Additional methods from the blueprint
    def rfe_selection(
        self, X: pd.DataFrame, y: pd.Series, n_features: int = 100
    ) -> pd.Series:
        """
        Recursive Feature Elimination selection.

        Args:
            X: Feature matrix
            y: Target labels
            n_features: Number of features to select

        Returns:
            Feature selection mask
        """
        from sklearn.feature_selection import RFE
        from sklearn.svm import LinearSVC

        base = LinearSVC(dual=False, max_iter=5000)
        selector = RFE(base, n_features_to_select=n_features, step=0.1)
        selector.fit(X, y)

        return pd.Series(selector.support_, index=X.columns, name="rfe_support")

    def l1_logreg_importance(self, X: pd.DataFrame, y: pd.Series) -> pd.Series:
        """
        L1-regularized logistic regression importance.

        Args:
            X: Feature matrix
            y: Target labels

        Returns:
            Feature importance scores
        """
        from sklearn.linear_model import LogisticRegression

        lr = LogisticRegression(penalty="l1", solver="liblinear", max_iter=5000)
        lr.fit(X, y)
        imp = pd.Series(np.abs(lr.coef_).ravel(), index=X.columns)
        return imp

    def rf_importance(self, X: pd.DataFrame, y: pd.Series) -> pd.Series:
        """
        Random Forest importance.

        Args:
            X: Feature matrix
            y: Target labels

        Returns:
            Feature importance scores
        """
        from sklearn.ensemble import RandomForestClassifier

        rf = RandomForestClassifier(
            n_estimators=500, class_weight="balanced", n_jobs=-1
        )
        rf.fit(X, y)
        return pd.Series(rf.feature_importances_, index=X.columns)

    def xgb_importance(self, X: pd.DataFrame, y: pd.Series) -> pd.Series:
        """
        XGBoost importance.

        Args:
            X: Feature matrix
            y: Target labels

        Returns:
            Feature importance scores
        """
        try:
            from xgboost import XGBClassifier

            xgb = XGBClassifier(
                max_depth=4, eta=0.1, subsample=0.8, n_estimators=500, n_jobs=-1
            )
            xgb.fit(X, y)
            return pd.Series(xgb.feature_importances_, index=X.columns)
        except ImportError:
            logger.warning("XGBoost not available, using Random Forest instead")
            return self.rf_importance(X, y)
