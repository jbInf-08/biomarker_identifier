"""
SHAP tools for model explainability in biomarker identification.
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class SHAPExplainer:
    """
    Handles SHAP-based model explainability for biomarker identification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the SHAPExplainer module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.shap_results = {}

    def compute_shap_values(
        self,
        model: Any,
        X: pd.DataFrame,
        background_data: Optional[pd.DataFrame] = None,
        explainer_type: str = "auto",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Compute SHAP values for model explainability.

        Args:
            model: Trained model
            X: Feature matrix
            background_data: Background data for explainer (optional)
            explainer_type: Type of SHAP explainer
            **kwargs: Additional parameters

        Returns:
            SHAP analysis results
        """
        try:
            import shap

            results = {
                "explainer_type": explainer_type,
                "shap_values": None,
                "expected_value": None,
                "feature_names": list(X.columns),
                "global_analysis": {},
                "local_analysis": {},
            }

            # Determine explainer type if auto
            if explainer_type == "auto":
                explainer_type = self._determine_explainer_type(model)

            # Create explainer
            explainer = self._create_explainer(
                model, X, background_data, explainer_type, **kwargs
            )
            results["explainer"] = explainer

            # Compute SHAP values
            if background_data is not None:
                shap_values = explainer.shap_values(X)
            else:
                shap_values = explainer(X)

            # Handle different output formats
            if isinstance(shap_values, list):
                shap_values = shap_values[1] if len(shap_values) > 1 else shap_values[0]

            results["shap_values"] = shap_values
            results["expected_value"] = explainer.expected_value

            # Global analysis
            global_analysis = self._compute_global_analysis(shap_values, X, **kwargs)
            results["global_analysis"] = global_analysis

            # Local analysis
            local_analysis = self._compute_local_analysis(shap_values, X, **kwargs)
            results["local_analysis"] = local_analysis

            self.shap_results = results
            logger.info("SHAP analysis completed")

            return results

        except ImportError:
            logger.error(
                "SHAP library not available. Please install with: pip install shap"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to compute SHAP values: {str(e)}")
            raise

    def _determine_explainer_type(self, model: Any) -> str:
        """
        Automatically determine the best SHAP explainer type for the model.

        Args:
            model: Trained model

        Returns:
            Explainer type
        """
        model_type = type(model).__name__.lower()

        if (
            "tree" in model_type
            or "forest" in model_type
            or "xgboost" in model_type
            or "lightgbm" in model_type
        ):
            return "tree"
        elif "linear" in model_type or "logistic" in model_type:
            return "linear"
        else:
            return "kernel"

    def _create_explainer(
        self,
        model: Any,
        X: pd.DataFrame,
        background_data: Optional[pd.DataFrame],
        explainer_type: str,
        **kwargs,
    ) -> Any:
        """
        Create appropriate SHAP explainer.

        Args:
            model: Trained model
            X: Feature matrix
            background_data: Background data
            explainer_type: Type of explainer
            **kwargs: Additional parameters

        Returns:
            SHAP explainer
        """
        import shap

        if explainer_type == "tree":
            return shap.TreeExplainer(model, **kwargs)
        elif explainer_type == "linear":
            return shap.LinearExplainer(model, X, **kwargs)
        elif explainer_type == "kernel":
            background = (
                background_data if background_data is not None else shap.kmeans(X, 100)
            )
            return shap.KernelExplainer(model.predict, background, **kwargs)
        else:
            raise ValueError(f"Unsupported explainer type: {explainer_type}")

    def _compute_global_analysis(
        self, shap_values: np.ndarray, X: pd.DataFrame, **kwargs
    ) -> Dict[str, Any]:
        """
        Compute global SHAP analysis.

        Args:
            shap_values: SHAP values
            X: Feature matrix
            **kwargs: Additional parameters

        Returns:
            Global analysis results
        """
        # Feature importance (mean absolute SHAP values)
        feature_importance = np.abs(shap_values).mean(axis=0)
        feature_importance_df = pd.DataFrame(
            {"feature": X.columns, "importance": feature_importance}
        ).sort_values("importance", ascending=False)

        # Summary statistics
        summary_stats = {
            "mean_shap": np.mean(shap_values, axis=0),
            "std_shap": np.std(shap_values, axis=0),
            "min_shap": np.min(shap_values, axis=0),
            "max_shap": np.max(shap_values, axis=0),
        }

        # Interaction analysis (if supported)
        interaction_analysis = self._compute_interaction_analysis(
            shap_values, X, **kwargs
        )

        return {
            "feature_importance": feature_importance_df.to_dict("records"),
            "summary_stats": {k: v.tolist() for k, v in summary_stats.items()},
            "interaction_analysis": interaction_analysis,
            "top_features": feature_importance_df.head(20).to_dict("records"),
        }

    def _compute_local_analysis(
        self, shap_values: np.ndarray, X: pd.DataFrame, **kwargs
    ) -> Dict[str, Any]:
        """
        Compute local SHAP analysis.

        Args:
            shap_values: SHAP values
            X: Feature matrix
            **kwargs: Additional parameters

        Returns:
            Local analysis results
        """
        # Sample-level analysis
        sample_analysis = []
        for i in range(min(10, len(X))):  # Analyze first 10 samples
            sample_shap = shap_values[i]
            sample_features = X.iloc[i]

            # Get top contributing features for this sample
            feature_contributions = pd.DataFrame(
                {
                    "feature": X.columns,
                    "shap_value": sample_shap,
                    "feature_value": sample_features.values,
                    "abs_contribution": np.abs(sample_shap),
                }
            ).sort_values("abs_contribution", ascending=False)

            sample_analysis.append(
                {
                    "sample_index": i,
                    "top_contributors": feature_contributions.head(10).to_dict(
                        "records"
                    ),
                    "total_contribution": np.sum(sample_shap),
                }
            )

        # Feature dependence analysis
        dependence_analysis = self._compute_dependence_analysis(
            shap_values, X, **kwargs
        )

        return {
            "sample_analysis": sample_analysis,
            "dependence_analysis": dependence_analysis,
        }

    def _compute_interaction_analysis(
        self, shap_values: np.ndarray, X: pd.DataFrame, **kwargs
    ) -> Dict[str, Any]:
        """
        Compute SHAP interaction analysis.

        Args:
            shap_values: SHAP values
            X: Feature matrix
            **kwargs: Additional parameters

        Returns:
            Interaction analysis results
        """
        try:
            import shap

            # This is a simplified interaction analysis
            # For full interaction analysis, you would need to compute SHAP interaction values
            # which is computationally expensive

            # Compute correlation between SHAP values and feature values
            interactions = {}
            for i, feature in enumerate(X.columns):
                feature_values = X[feature].values
                shap_values_feature = shap_values[:, i]

                # Correlation
                correlation = np.corrcoef(feature_values, shap_values_feature)[0, 1]

                # Non-linear relationship (using mutual information approximation)
                from sklearn.feature_selection import mutual_info_regression

                mi_score = mutual_info_regression(
                    feature_values.reshape(-1, 1), shap_values_feature, random_state=42
                )[0]

                interactions[feature] = {
                    "correlation": float(correlation)
                    if not np.isnan(correlation)
                    else 0.0,
                    "mutual_info": float(mi_score),
                }

            return interactions

        except Exception as e:
            logger.warning(f"Interaction analysis failed: {str(e)}")
            return {}

    def _compute_dependence_analysis(
        self, shap_values: np.ndarray, X: pd.DataFrame, **kwargs
    ) -> Dict[str, Any]:
        """
        Compute SHAP dependence analysis.

        Args:
            shap_values: SHAP values
            X: Feature matrix
            **kwargs: Additional parameters

        Returns:
            Dependence analysis results
        """
        # Analyze dependence for top features
        top_features = kwargs.get("top_features", 10)
        feature_importance = np.abs(shap_values).mean(axis=0)
        top_feature_indices = np.argsort(feature_importance)[-top_features:]

        dependence_data = {}
        for idx in top_feature_indices:
            feature_name = X.columns[idx]
            feature_values = X.iloc[:, idx].values
            shap_values_feature = shap_values[:, idx]

            # Create dependence plot data
            dependence_df = pd.DataFrame(
                {"feature_value": feature_values, "shap_value": shap_values_feature}
            ).sort_values("feature_value")

            dependence_data[feature_name] = {
                "feature_values": dependence_df["feature_value"].tolist(),
                "shap_values": dependence_df["shap_value"].tolist(),
                "correlation": float(
                    np.corrcoef(feature_values, shap_values_feature)[0, 1]
                ),
            }

        return dependence_data

    def generate_shap_plots(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate SHAP visualization plots.

        Args:
            results: SHAP analysis results

        Returns:
            Dictionary of plot objects
        """
        plots = {}

        try:
            import plotly.express as px
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            shap_values = results["shap_values"]
            X = pd.DataFrame(results.get("feature_names", []))

            # Summary plot (beeswarm)
            if "global_analysis" in results:
                global_analysis = results["global_analysis"]
                if "feature_importance" in global_analysis:
                    importance_df = pd.DataFrame(global_analysis["feature_importance"])

                    fig_summary = px.bar(
                        importance_df.head(20),
                        x="importance",
                        y="feature",
                        orientation="h",
                        title="SHAP Feature Importance (Global)",
                    )
                    plots["shap_summary"] = fig_summary

            # Waterfall plot for a sample
            if "local_analysis" in results:
                local_analysis = results["local_analysis"]
                if (
                    "sample_analysis" in local_analysis
                    and local_analysis["sample_analysis"]
                ):
                    sample_data = local_analysis["sample_analysis"][0]

                    # Create waterfall plot
                    contributors = sample_data["top_contributors"][:10]
                    features = [c["feature"] for c in contributors]
                    values = [c["shap_value"] for c in contributors]

                    fig_waterfall = go.Figure(
                        go.Waterfall(
                            name="SHAP Values",
                            orientation="h",
                            measure=["relative"] * len(features),
                            x=values,
                            textposition="outside",
                            text=[f"{v:.3f}" for v in values],
                            y=features,
                            connector={"line": {"color": "rgb(63, 63, 63)"}},
                        )
                    )

                    fig_waterfall.update_layout(
                        title="SHAP Waterfall Plot (Sample)",
                        xaxis_title="SHAP Value",
                        yaxis_title="Feature",
                    )
                    plots["shap_waterfall"] = fig_waterfall

            # Dependence plots
            if (
                "local_analysis" in results
                and "dependence_analysis" in results["local_analysis"]
            ):
                dependence_data = results["local_analysis"]["dependence_analysis"]

                for feature, data in list(dependence_data.items())[
                    :5
                ]:  # Top 5 features
                    fig_dep = px.scatter(
                        x=data["feature_values"],
                        y=data["shap_values"],
                        title=f"SHAP Dependence Plot - {feature}",
                        labels={"x": f"{feature} Value", "y": "SHAP Value"},
                    )
                    plots[f"dependence_{feature}"] = fig_dep

            # Force plot (simplified)
            if "expected_value" in results:
                expected_value = results["expected_value"]
                if isinstance(expected_value, list):
                    expected_value = (
                        expected_value[1]
                        if len(expected_value) > 1
                        else expected_value[0]
                    )

                # Create a simplified force plot representation
                fig_force = go.Figure()
                fig_force.add_annotation(
                    x=0.5,
                    y=0.5,
                    text=f"Expected Value: {expected_value:.3f}",
                    showarrow=False,
                    font=dict(size=20),
                )
                fig_force.update_layout(
                    title="SHAP Force Plot (Expected Value)",
                    xaxis=dict(showgrid=False, showticklabels=False),
                    yaxis=dict(showgrid=False, showticklabels=False),
                )
                plots["shap_force"] = fig_force

        except ImportError:
            logger.warning("Plotly not available, skipping SHAP plots")

        return plots

    def get_feature_importance(self, top_n: int = 20) -> List[Dict[str, Any]]:
        """
        Get top feature importance from SHAP analysis.

        Args:
            top_n: Number of top features to return

        Returns:
            List of top features with importance scores
        """
        if not self.shap_results or "global_analysis" not in self.shap_results:
            return []

        global_analysis = self.shap_results["global_analysis"]
        if "feature_importance" not in global_analysis:
            return []

        feature_importance = global_analysis["feature_importance"]
        return feature_importance[:top_n]

    def get_sample_explanation(self, sample_index: int = 0) -> Dict[str, Any]:
        """
        Get SHAP explanation for a specific sample.

        Args:
            sample_index: Index of the sample to explain

        Returns:
            Sample explanation
        """
        if not self.shap_results or "local_analysis" not in self.shap_results:
            return {"error": "No SHAP analysis results available"}

        local_analysis = self.shap_results["local_analysis"]
        if "sample_analysis" not in local_analysis:
            return {"error": "No sample analysis available"}

        sample_analysis = local_analysis["sample_analysis"]
        if sample_index >= len(sample_analysis):
            return {"error": f"Sample index {sample_index} out of range"}

        return sample_analysis[sample_index]

    def save_shap_results(self, output_path: str, format: str = "json") -> str:
        """
        Save SHAP results to file.

        Args:
            output_path: Output file path
            format: Output format

        Returns:
            Path to saved file
        """
        if not self.shap_results:
            raise ValueError("No SHAP results to save")

        try:
            if format.lower() == "json":
                import json

                # Convert numpy arrays to lists for JSON serialization
                results_copy = self._prepare_results_for_serialization(
                    self.shap_results
                )
                with open(output_path, "w") as f:
                    json.dump(results_copy, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"SHAP results saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save SHAP results: {str(e)}")
            raise

    def _prepare_results_for_serialization(
        self, results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare results for JSON serialization by converting numpy arrays to lists.

        Args:
            results: Results dictionary

        Returns:
            Serialization-ready results
        """
        import copy

        results_copy = copy.deepcopy(results)

        def convert_numpy(obj):
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy(item) for item in obj]
            else:
                return obj

        return convert_numpy(results_copy)

    def get_shap_summary(self) -> Dict[str, Any]:
        """
        Get SHAP analysis summary.

        Returns:
            SHAP summary dictionary
        """
        if not self.shap_results:
            return {"status": "No SHAP analysis performed"}

        summary = {
            "explainer_type": self.shap_results.get("explainer_type"),
            "n_features": len(self.shap_results.get("feature_names", [])),
            "expected_value": self.shap_results.get("expected_value"),
        }

        if "global_analysis" in self.shap_results:
            global_analysis = self.shap_results["global_analysis"]
            if "top_features" in global_analysis:
                summary["top_features"] = global_analysis["top_features"][:10]

        return summary
