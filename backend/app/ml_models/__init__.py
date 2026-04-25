"""
Machine Learning Models for Cancer Biomarker Identification.

This module provides comprehensive machine learning capabilities for biomarker discovery,
including feature selection, model training (ML, deep learning), evaluation, and explainability.
"""

from .cross_validation import CrossValidator
from .evaluation_utils import (
    bootstrap_paired_auc_delta,
    compute_binary_classification_metrics,
    holdout_multimodel_report,
    mcnemar_test,
)
from .feature_selection import ConsensusFeatureSelector, FeatureSelector
from .graph_augmented import (
    ShallowGeneGATClassifier,
    adjacency_from_named_edges,
    augment_expression_with_graph,
)
from .ml_pipeline import MLPipeline
from .model_training import ModelEvaluator, ModelTrainer
from .permutation_tests import PermutationTester, PermutationTestSuite
from .shap_explainer import SHAPExplainer

try:
    from .deep_models import PyTorchTabularClassifier, get_deep_learning_wrapper
except ImportError:
    PyTorchTabularClassifier = None  # type: ignore
    get_deep_learning_wrapper = None  # type: ignore

__all__ = [
    "FeatureSelector",
    "ConsensusFeatureSelector",
    "ModelTrainer",
    "ModelEvaluator",
    "SHAPExplainer",
    "CrossValidator",
    "PermutationTester",
    "PermutationTestSuite",
    "MLPipeline",
    "PyTorchTabularClassifier",
    "get_deep_learning_wrapper",
    "compute_binary_classification_metrics",
    "holdout_multimodel_report",
    "mcnemar_test",
    "bootstrap_paired_auc_delta",
    "augment_expression_with_graph",
    "adjacency_from_named_edges",
    "ShallowGeneGATClassifier",
]
