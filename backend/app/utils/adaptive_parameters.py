"""
Adaptive parameter selection based on dataset size.
Ensures all analysis steps work from smallest to largest datasets.
"""

from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class AdaptiveParameters:
    """
    Determines appropriate parameters based on dataset size.
    """

    @staticmethod
    def get_dataset_size_category(n_samples: int, n_features: int) -> str:
        """
        Categorize dataset size.

        Args:
            n_samples: Number of samples
            n_features: Number of features

        Returns:
            Size category: 'tiny', 'small', 'medium', 'large', 'very_large'
        """
        if n_samples < 5:
            return "tiny"
        elif n_samples < 20:
            return "small"
        elif n_samples < 100:
            return "medium"
        elif n_samples < 500:
            return "large"
        else:
            return "very_large"

    @staticmethod
    def get_qc_parameters(n_samples: int, n_features: int) -> Dict[str, Any]:
        """
        Get adaptive QC parameters.

        Args:
            n_samples: Number of samples
            n_features: Number of features

        Returns:
            QC parameters dictionary
        """
        size_cat = AdaptiveParameters.get_dataset_size_category(n_samples, n_features)

        params = {
            "tiny": {
                "pca_components": min(2, n_samples - 1, n_features),
                "tsne_enabled": False,  # t-SNE needs at least 4 samples
                "tsne_perplexity": None,
                "batch_detection": False,
                "correlation_heatmap": False,
                "min_samples_for_pca": 2,
            },
            "small": {
                "pca_components": min(5, n_samples - 1, n_features),
                "tsne_enabled": n_samples >= 4,
                "tsne_perplexity": min(5, max(3, n_samples // 3)),
                "batch_detection": n_samples >= 6,
                "correlation_heatmap": n_samples <= 50,
                "min_samples_for_pca": 2,
            },
            "medium": {
                "pca_components": min(10, n_samples - 1, n_features),
                "tsne_enabled": True,
                "tsne_perplexity": min(30, max(5, n_samples // 3)),
                "batch_detection": True,
                "correlation_heatmap": n_samples <= 50,
                "min_samples_for_pca": 3,
            },
            "large": {
                "pca_components": min(50, n_samples - 1, n_features),
                "tsne_enabled": True,
                "tsne_perplexity": min(50, max(10, n_samples // 4)),
                "batch_detection": True,
                "correlation_heatmap": False,
                "min_samples_for_pca": 3,
            },
            "very_large": {
                "pca_components": min(100, n_samples - 1, n_features),
                "tsne_enabled": False,  # Too slow for very large datasets
                "tsne_perplexity": None,
                "batch_detection": True,
                "correlation_heatmap": False,
                "min_samples_for_pca": 3,
            },
        }

        return params[size_cat]

    @staticmethod
    def get_statistical_parameters(
        n_samples: int, n_features: int, n_classes: int = 2
    ) -> Dict[str, Any]:
        """
        Get adaptive statistical analysis parameters.

        Args:
            n_samples: Number of samples
            n_features: Number of features
            n_classes: Number of classes

        Returns:
            Statistical parameters dictionary
        """
        size_cat = AdaptiveParameters.get_dataset_size_category(n_samples, n_features)
        min_samples_per_class = n_samples // n_classes if n_classes > 0 else n_samples

        params = {
            "tiny": {
                "fdr_method": "none",  # No correction for tiny datasets
                "alpha": 0.1,  # More lenient threshold
                "min_samples_per_class": 1,
                "use_permutation": False,
                "n_permutations": 0,
                "effect_size_threshold": 0.0,  # No threshold
                "warn_small_sample": True,
            },
            "small": {
                "fdr_method": "fdr_bh" if n_features > 10 else "none",
                "alpha": 0.05,
                "min_samples_per_class": 2,
                "use_permutation": min_samples_per_class >= 3,
                "n_permutations": min(100, n_samples * 10)
                if min_samples_per_class >= 3
                else 0,
                "effect_size_threshold": 0.0,
                "warn_small_sample": True,
            },
            "medium": {
                "fdr_method": "fdr_bh",
                "alpha": 0.05,
                "min_samples_per_class": 5,
                "use_permutation": True,
                "n_permutations": 1000,
                "effect_size_threshold": 0.1,
                "warn_small_sample": False,
            },
            "large": {
                "fdr_method": "fdr_bh",
                "alpha": 0.05,
                "min_samples_per_class": 10,
                "use_permutation": True,
                "n_permutations": 10000,
                "effect_size_threshold": 0.2,
                "warn_small_sample": False,
            },
            "very_large": {
                "fdr_method": "fdr_bh",
                "alpha": 0.05,
                "min_samples_per_class": 20,
                "use_permutation": True,
                "n_permutations": 10000,
                "effect_size_threshold": 0.3,
                "warn_small_sample": False,
            },
        }

        return params[size_cat]

    @staticmethod
    def get_ml_parameters(
        n_samples: int, n_features: int, n_classes: int = 2
    ) -> Dict[str, Any]:
        """
        Get adaptive ML selection parameters.

        Args:
            n_samples: Number of samples
            n_features: Number of features
            n_classes: Number of classes

        Returns:
            ML parameters dictionary
        """
        size_cat = AdaptiveParameters.get_dataset_size_category(n_samples, n_features)
        min_samples_per_class = n_samples // n_classes if n_classes > 0 else n_samples

        params = {
            "tiny": {
                "cv_folds": 2,  # Leave-one-out or 2-fold
                "stratified_cv": False,
                "bootstrap_enabled": False,
                "n_bootstraps": 0,
                "stability_selection": False,
                "wrapper_methods": False,  # Too slow for tiny datasets
                "embedded_methods": True,
                "filter_methods": True,
                "max_features": min(10, n_features),
                "min_samples_for_cv": 2,
            },
            "small": {
                "cv_folds": min(3, max(2, n_samples // 2)),
                "stratified_cv": min_samples_per_class >= 2,
                "bootstrap_enabled": n_samples >= 4,
                "n_bootstraps": min(50, max(10, n_samples * 5))
                if n_samples >= 4
                else 0,
                "stability_selection": n_samples >= 6,
                "wrapper_methods": n_samples >= 8,
                "embedded_methods": True,
                "filter_methods": True,
                "max_features": min(50, n_features),
                "min_samples_for_cv": 3,
            },
            "medium": {
                "cv_folds": min(5, max(3, n_samples // 5)),
                "stratified_cv": True,
                "bootstrap_enabled": True,
                "n_bootstraps": min(100, max(50, n_samples * 2)),
                "stability_selection": True,
                "wrapper_methods": True,
                "embedded_methods": True,
                "filter_methods": True,
                "max_features": min(200, n_features),
                "min_samples_for_cv": 5,
            },
            "large": {
                "cv_folds": min(10, max(5, n_samples // 10)),
                "stratified_cv": True,
                "bootstrap_enabled": True,
                "n_bootstraps": 100,
                "stability_selection": True,
                "wrapper_methods": True,
                "embedded_methods": True,
                "filter_methods": True,
                "max_features": min(500, n_features),
                "min_samples_for_cv": 10,
            },
            "very_large": {
                "cv_folds": 10,
                "stratified_cv": True,
                "bootstrap_enabled": True,
                "n_bootstraps": 100,
                "stability_selection": True,
                "wrapper_methods": False,  # Too slow for very large
                "embedded_methods": True,
                "filter_methods": True,
                "max_features": min(1000, n_features),
                "min_samples_for_cv": 20,
            },
        }

        return params[size_cat]

    @staticmethod
    def get_filtering_parameters(n_samples: int, n_features: int) -> Dict[str, Any]:
        """
        Get adaptive data filtering parameters.

        Args:
            n_samples: Number of samples
            n_features: Number of features

        Returns:
            Filtering parameters dictionary
        """
        size_cat = AdaptiveParameters.get_dataset_size_category(n_samples, n_features)

        params = {
            "tiny": {
                "min_detection_rate": 0.0,  # Don't filter with tiny datasets
                "min_variance": 0.0,
                "max_missing_ratio": 1.0,  # Allow all missing
                "min_samples": 1,
            },
            "small": {
                "min_detection_rate": 0.01,  # Very lenient
                "min_variance": 0.0,
                "max_missing_ratio": 0.99,
                "min_samples": 1,
            },
            "medium": {
                "min_detection_rate": 0.1,
                "min_variance": 0.0,
                "max_missing_ratio": 0.5,
                "min_samples": 2,
            },
            "large": {
                "min_detection_rate": 0.1,
                "min_variance": 0.0,
                "max_missing_ratio": 0.3,
                "min_samples": 3,
            },
            "very_large": {
                "min_detection_rate": 0.1,
                "min_variance": 0.0,
                "max_missing_ratio": 0.2,
                "min_samples": 5,
            },
        }

        return params[size_cat]

    @staticmethod
    def get_normalization_parameters(n_samples: int, n_features: int) -> Dict[str, Any]:
        """
        Get adaptive normalization parameters.

        Args:
            n_samples: Number of samples
            n_features: Number of features

        Returns:
            Normalization parameters dictionary
        """
        size_cat = AdaptiveParameters.get_dataset_size_category(n_samples, n_features)

        params = {
            "tiny": {
                "batch_correction": False,  # Need more samples
                "quantile_normalization": False,  # Needs many samples
                "recommended_methods": ["log2", "z_score"],
            },
            "small": {
                "batch_correction": n_samples >= 6,
                "quantile_normalization": False,
                "recommended_methods": ["log2", "z_score"],
            },
            "medium": {
                "batch_correction": True,
                "quantile_normalization": True,
                "recommended_methods": ["log2", "quantile", "z_score"],
            },
            "large": {
                "batch_correction": True,
                "quantile_normalization": True,
                "recommended_methods": ["log2", "quantile", "z_score"],
            },
            "very_large": {
                "batch_correction": True,
                "quantile_normalization": True,
                "recommended_methods": ["log2", "quantile", "z_score"],
            },
        }

        return params[size_cat]

    @staticmethod
    def get_all_parameters(
        expression_data: pd.DataFrame, labels: pd.Series
    ) -> Dict[str, Any]:
        """
        Get all adaptive parameters for a dataset.

        Args:
            expression_data: Expression data matrix
            labels: Sample labels

        Returns:
            Dictionary of all adaptive parameters
        """
        n_samples = expression_data.shape[1]
        n_features = expression_data.shape[0]
        n_classes = len(labels.unique()) if labels is not None else 2

        return {
            "dataset_size": {
                "n_samples": n_samples,
                "n_features": n_features,
                "n_classes": n_classes,
                "category": AdaptiveParameters.get_dataset_size_category(
                    n_samples, n_features
                ),
            },
            "qc": AdaptiveParameters.get_qc_parameters(n_samples, n_features),
            "statistical": AdaptiveParameters.get_statistical_parameters(
                n_samples, n_features, n_classes
            ),
            "ml": AdaptiveParameters.get_ml_parameters(
                n_samples, n_features, n_classes
            ),
            "filtering": AdaptiveParameters.get_filtering_parameters(
                n_samples, n_features
            ),
            "normalization": AdaptiveParameters.get_normalization_parameters(
                n_samples, n_features
            ),
        }
