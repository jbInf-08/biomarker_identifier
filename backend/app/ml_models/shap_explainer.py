"""
SHAP (SHapley Additive exPlanations) Integration for Model Explainability.

This module provides comprehensive SHAP-based model explainability including:
- Global feature importance
- Local explanations
- Feature interaction analysis
- Visualization utilities
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

import joblib
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression

logger = logging.getLogger(__name__)


class SHAPExplainer:
    """
    Comprehensive SHAP-based model explainability for biomarker discovery.

    Provides global and local explanations for various model types.
    """

    def __init__(self, random_state: int = 42):
        """
        Initialize SHAP explainer.

        Args:
            random_state: Random seed for reproducibility
        """
        self.random_state = random_state
        self.explainer_ = None
        self.shap_values_ = None
        self.explanation_results_ = {}

    def fit_explainer(
        self, model: Any, X: pd.DataFrame, sample_size: int = 1000
    ) -> "SHAPExplainer":
        """
        Fit SHAP explainer to model and data.

        Args:
            model: Trained model
            X: Feature matrix
            sample_size: Size of background sample for explainer

        Returns:
            Self
        """
        logger.info(f"Fitting SHAP explainer for {type(model).__name__}")

        # Sample background data
        if len(X) > sample_size:
            background_indices = np.random.choice(
                len(X), size=sample_size, replace=False
            )
            background_data = X.iloc[background_indices]
        else:
            background_data = X

        # Create appropriate explainer based on model type
        if isinstance(model, (RandomForestClassifier, RandomForestRegressor)):
            self.explainer_ = shap.TreeExplainer(model)
        elif isinstance(model, LogisticRegression):
            self.explainer_ = shap.LinearExplainer(model, background_data)
        elif isinstance(model, xgb.XGBClassifier):
            self.explainer_ = shap.TreeExplainer(model)
        else:
            # Use KernelExplainer as fallback
            self.explainer_ = shap.KernelExplainer(model.predict_proba, background_data)

        logger.info("SHAP explainer fitted successfully")
        return self

    def explain_global(self, X: pd.DataFrame, max_display: int = 20) -> Dict[str, Any]:
        """
        Generate global feature importance explanations.

        Args:
            X: Feature matrix to explain
            max_display: Maximum number of features to display

        Returns:
            Dictionary with global explanations
        """
        if self.explainer_ is None:
            raise ValueError("Explainer not fitted. Call fit_explainer first.")

        logger.info("Generating global SHAP explanations")

        # Calculate SHAP values
        self.shap_values_ = self.explainer_.shap_values(X)

        # Handle multi-class case
        if isinstance(self.shap_values_, list):
            # Multi-class: use first class
            shap_values = self.shap_values_[0]
        else:
            shap_values = self.shap_values_

        # Calculate global feature importance
        feature_importance = np.abs(shap_values).mean(axis=0)

        # Create feature importance DataFrame
        feature_names = X.columns.tolist()
        importance_df = pd.DataFrame(
            {"feature": feature_names, "importance": feature_importance}
        ).sort_values("importance", ascending=False)

        # Get top features
        top_features = importance_df.head(max_display)

        # Calculate summary statistics
        summary_stats = {
            "total_features": len(feature_names),
            "mean_importance": np.mean(feature_importance),
            "std_importance": np.std(feature_importance),
            "max_importance": np.max(feature_importance),
            "min_importance": np.min(feature_importance),
        }

        # Store results
        self.explanation_results_["global"] = {
            "feature_importance": importance_df.to_dict("records"),
            "top_features": top_features.to_dict("records"),
            "summary_stats": summary_stats,
            "shap_values": shap_values.tolist()
            if shap_values.ndim <= 2
            else shap_values.tolist(),
        }

        logger.info(f"Global explanations generated for {len(feature_names)} features")
        return self.explanation_results_["global"]

    def explain_local(
        self, X: pd.DataFrame, sample_indices: List[int] = None, max_display: int = 10
    ) -> Dict[str, Any]:
        """
        Generate local explanations for specific samples.

        Args:
            X: Feature matrix
            sample_indices: Indices of samples to explain
            max_display: Maximum number of features to display per sample

        Returns:
            Dictionary with local explanations
        """
        if self.explainer_ is None:
            raise ValueError("Explainer not fitted. Call fit_explainer first.")

        if sample_indices is None:
            # Select random samples
            n_samples = min(10, len(X))
            sample_indices = np.random.choice(len(X), size=n_samples, replace=False)

        logger.info(
            f"Generating local SHAP explanations for {len(sample_indices)} samples"
        )

        # Calculate SHAP values if not already calculated
        if self.shap_values_ is None:
            self.shap_values_ = self.explainer_.shap_values(X)

        # Handle multi-class case
        if isinstance(self.shap_values_, list):
            shap_values = self.shap_values_[0]
        else:
            shap_values = self.shap_values_

        # Get explanations for selected samples
        local_explanations = {}

        for idx in sample_indices:
            if idx >= len(X):
                continue

            # Get SHAP values for this sample
            sample_shap_values = shap_values[idx]

            # Create feature explanation DataFrame
            feature_names = X.columns.tolist()
            explanation_df = pd.DataFrame(
                {
                    "feature": feature_names,
                    "shap_value": sample_shap_values,
                    "feature_value": X.iloc[idx].values,
                }
            ).sort_values("shap_value", key=abs, ascending=False)

            # Get top features
            top_features = explanation_df.head(max_display)

            # Calculate sample statistics
            sample_stats = {
                "sample_index": int(idx),
                "prediction": self.explainer_.expected_value
                + np.sum(sample_shap_values),
                "sum_shap_values": np.sum(sample_shap_values),
                "max_contribution": np.max(np.abs(sample_shap_values)),
                "n_positive_features": np.sum(sample_shap_values > 0),
                "n_negative_features": np.sum(sample_shap_values < 0),
            }

            local_explanations[f"sample_{idx}"] = {
                "explanation": explanation_df.to_dict("records"),
                "top_features": top_features.to_dict("records"),
                "sample_stats": sample_stats,
            }

        # Store results
        self.explanation_results_["local"] = local_explanations

        logger.info(f"Local explanations generated for {len(sample_indices)} samples")
        return self.explanation_results_["local"]

    def explain_interactions(
        self, X: pd.DataFrame, max_display: int = 20
    ) -> Dict[str, Any]:
        """
        Generate feature interaction explanations.

        Args:
            X: Feature matrix
            max_display: Maximum number of interactions to display

        Returns:
            Dictionary with interaction explanations
        """
        if self.explainer_ is None:
            raise ValueError("Explainer not fitted. Call fit_explainer first.")

        logger.info("Generating SHAP interaction explanations")

        # Calculate SHAP interaction values
        try:
            interaction_values = self.explainer_.shap_interaction_values(X)

            # Handle multi-class case
            if isinstance(interaction_values, list):
                interaction_values = interaction_values[0]

            # Calculate interaction importance
            interaction_importance = np.abs(interaction_values).mean(axis=0)

            # Create interaction DataFrame
            feature_names = X.columns.tolist()
            n_features = len(feature_names)

            interaction_data = []
            for i in range(n_features):
                for j in range(i + 1, n_features):
                    interaction_data.append(
                        {
                            "feature1": feature_names[i],
                            "feature2": feature_names[j],
                            "interaction_importance": interaction_importance[i, j],
                        }
                    )

            interaction_df = pd.DataFrame(interaction_data).sort_values(
                "interaction_importance", ascending=False
            )

            # Get top interactions
            top_interactions = interaction_df.head(max_display)

            # Calculate summary statistics
            summary_stats = {
                "total_interactions": len(interaction_data),
                "mean_interaction_importance": np.mean(interaction_importance),
                "max_interaction_importance": np.max(interaction_importance),
            }

            # Store results
            self.explanation_results_["interactions"] = {
                "interaction_importance": interaction_df.to_dict("records"),
                "top_interactions": top_interactions.to_dict("records"),
                "summary_stats": summary_stats,
            }

            logger.info(
                f"Interaction explanations generated for {len(interaction_data)} feature pairs"
            )
            return self.explanation_results_["interactions"]

        except Exception as e:
            logger.warning(f"Could not calculate interactions: {str(e)}")
            return {"error": str(e)}

    def get_feature_importance_ranking(self) -> pd.DataFrame:
        """Get feature importance ranking from SHAP values."""

        if "global" not in self.explanation_results_:
            raise ValueError(
                "Global explanations not available. Call explain_global first."
            )

        global_results = self.explanation_results_["global"]
        importance_df = pd.DataFrame(global_results["feature_importance"])

        return importance_df.sort_values("importance", ascending=False)

    def get_sample_explanations(self, sample_index: int) -> Dict[str, Any]:
        """Get explanations for a specific sample."""

        if "local" not in self.explanation_results_:
            raise ValueError(
                "Local explanations not available. Call explain_local first."
            )

        local_results = self.explanation_results_["local"]
        sample_key = f"sample_{sample_index}"

        if sample_key not in local_results:
            raise ValueError(f"Sample {sample_index} not found in local explanations")

        return local_results[sample_key]

    def generate_explanation_summary(self) -> Dict[str, Any]:
        """Generate comprehensive explanation summary."""

        if not self.explanation_results_:
            raise ValueError("No explanations available. Generate explanations first.")

        summary = {
            "explanation_types": list(self.explanation_results_.keys()),
            "timestamp": pd.Timestamp.now().isoformat(),
        }

        # Add global summary
        if "global" in self.explanation_results_:
            global_results = self.explanation_results_["global"]
            summary["global_summary"] = {
                "total_features": global_results["summary_stats"]["total_features"],
                "top_feature": global_results["top_features"][0]["feature"]
                if global_results["top_features"]
                else None,
                "max_importance": global_results["summary_stats"]["max_importance"],
            }

        # Add local summary
        if "local" in self.explanation_results_:
            local_results = self.explanation_results_["local"]
            summary["local_summary"] = {
                "n_samples_explained": len(local_results),
                "sample_indices": [
                    int(key.split("_")[1]) for key in local_results.keys()
                ],
            }

        # Add interaction summary
        if "interactions" in self.explanation_results_:
            interaction_results = self.explanation_results_["interactions"]
            summary["interaction_summary"] = {
                "total_interactions": interaction_results["summary_stats"][
                    "total_interactions"
                ],
                "top_interaction": interaction_results["top_interactions"][0]
                if interaction_results["top_interactions"]
                else None,
            }

        return summary

    def save_explanations(self, filepath: str):
        """Save explanation results to file."""

        if not self.explanation_results_:
            raise ValueError("No explanations to save")

        # Save results (excluding explainer object)
        results_to_save = {
            "explanation_results": self.explanation_results_,
            "feature_names": getattr(self, "feature_names_", None),
        }

        joblib.dump(results_to_save, filepath)
        logger.info(f"SHAP explanations saved to {filepath}")

    def load_explanations(self, filepath: str):
        """Load explanation results from file."""

        data = joblib.load(filepath)
        self.explanation_results_ = data["explanation_results"]
        if "feature_names" in data:
            self.feature_names_ = data["feature_names"]
        logger.info(f"SHAP explanations loaded from {filepath}")


class SHAPVisualizer:
    """
    SHAP visualization utilities for biomarker discovery.
    """

    def __init__(self, explainer: SHAPExplainer):
        """Initialize SHAP visualizer."""
        self.explainer = explainer

    def plot_feature_importance(
        self, max_display: int = 20, figsize: Tuple[int, int] = (10, 8)
    ):
        """Plot feature importance summary."""

        if "global" not in self.explainer.explanation_results_:
            raise ValueError("Global explanations not available")

        import matplotlib.pyplot as plt

        global_results = self.explainer.explanation_results_["global"]
        top_features = global_results["top_features"][:max_display]

        features = [f["feature"] for f in top_features]
        importance = [f["importance"] for f in top_features]

        plt.figure(figsize=figsize)
        plt.barh(range(len(features)), importance)
        plt.yticks(range(len(features)), features)
        plt.xlabel("SHAP Feature Importance")
        plt.title("Top Features by SHAP Importance")
        plt.gca().invert_yaxis()
        plt.tight_layout()

        return plt.gcf()

    def plot_waterfall(self, sample_index: int, max_display: int = 10):
        """Plot waterfall plot for a specific sample."""

        if "local" not in self.explainer.explanation_results_:
            raise ValueError("Local explanations not available")

        sample_key = f"sample_{sample_index}"
        if sample_key not in self.explainer.explanation_results_["local"]:
            raise ValueError(f"Sample {sample_index} not found")

        sample_data = self.explainer.explanation_results_["local"][sample_key]
        top_features = sample_data["top_features"][:max_display]

        import matplotlib.pyplot as plt

        features = [f["feature"] for f in top_features]
        shap_values = [f["shap_value"] for f in top_features]

        plt.figure(figsize=(10, 6))
        colors = ["red" if x < 0 else "blue" for x in shap_values]
        plt.barh(range(len(features)), shap_values, color=colors)
        plt.yticks(range(len(features)), features)
        plt.xlabel("SHAP Value")
        plt.title(f"SHAP Waterfall Plot - Sample {sample_index}")
        plt.axvline(x=0, color="black", linestyle="-", alpha=0.3)
        plt.tight_layout()

        return plt.gcf()
