"""
Advanced Machine Learning Models
Advanced ML models and clinical annotation capabilities.
Clinical annotations use real APIs only (COSMIC, ClinVar, OncoKB). No mock data.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np

from app.services.clinical_api_client import (
    fetch_clinvar_variants,
    fetch_cosmic_mutations,
    fetch_oncokb_cancer_genes,
    fetch_oncokb_drugs,
)
import pandas as pd
from sklearn.ensemble import (
    GradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC

logger = logging.getLogger(__name__)


@dataclass
class ModelPerformance:
    """Model performance metrics"""

    accuracy: float
    precision: float
    recall: float
    f1_score: float
    roc_auc: float
    confusion_matrix: np.ndarray
    classification_report: str
    cross_val_scores: List[float]
    training_time: float
    prediction_time: float


class AdvancedBiomarkerModel:
    """Advanced machine learning model for biomarker identification"""

    def __init__(self, model_type: str = "ensemble"):
        self.model_type = model_type
        self.model = None
        self.feature_importance = None
        self.feature_names = None
        self.is_trained = False
        self.performance_metrics = None

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        feature_names: Optional[List[str]] = None,
        hyperparameter_tuning: bool = True,
    ) -> ModelPerformance:
        """
        Train the model

        Args:
            X: Feature matrix
            y: Target labels
            feature_names: Names of features
            hyperparameter_tuning: Whether to perform hyperparameter tuning

        Returns:
            Model performance metrics
        """
        try:
            import time

            start_time = time.time()

            self.feature_names = feature_names or [
                f"feature_{i}" for i in range(X.shape[1])
            ]

            if self.model_type == "ensemble":
                self.model = self._create_ensemble_model()
            elif self.model_type == "neural_network":
                self.model = self._create_neural_network()
            elif self.model_type == "gradient_boosting":
                self.model = GradientBoostingClassifier(
                    n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42
                )
            elif self.model_type == "svm":
                self.model = SVC(kernel="rbf", probability=True, random_state=42)
            else:
                self.model = RandomForestClassifier(
                    n_estimators=100, max_depth=10, random_state=42
                )

            # Hyperparameter tuning
            if hyperparameter_tuning:
                self.model = self._tune_hyperparameters(X, y)

            # Train model
            self.model.fit(X, y)

            # Feature importance
            if hasattr(self.model, "feature_importances_"):
                self.feature_importance = dict(
                    zip(self.feature_names, self.model.feature_importances_)
                )
            elif hasattr(self.model, "named_estimators_"):
                acc = np.zeros(len(self.feature_names), dtype=float)
                n_imp = 0
                for est in self.model.named_estimators_.values():
                    if hasattr(est, "feature_importances_"):
                        acc += np.asarray(est.feature_importances_, dtype=float)
                        n_imp += 1
                if n_imp:
                    acc /= n_imp
                    self.feature_importance = dict(zip(self.feature_names, acc))

            # Cross-validation
            cv_scores = cross_val_score(
                self.model,
                X,
                y,
                cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
                scoring="accuracy",
            )

            # Predictions
            y_pred = self.model.predict(X)
            y_pred_proba = (
                self.model.predict_proba(X)[:, 1]
                if hasattr(self.model, "predict_proba")
                else None
            )

            # Performance metrics
            accuracy = accuracy_score(y, y_pred)
            precision = precision_score(y, y_pred, average="weighted", zero_division=0)
            recall = recall_score(y, y_pred, average="weighted", zero_division=0)
            f1 = f1_score(y, y_pred, average="weighted", zero_division=0)

            roc_auc = None
            if y_pred_proba is not None and len(np.unique(y)) == 2:
                try:
                    roc_auc = roc_auc_score(y, y_pred_proba)
                except:
                    pass

            training_time = time.time() - start_time

            # Test prediction time
            pred_start = time.time()
            _ = self.model.predict(X[:10])
            prediction_time = (time.time() - pred_start) / 10

            self.performance_metrics = ModelPerformance(
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                f1_score=f1,
                roc_auc=roc_auc or 0.0,
                confusion_matrix=confusion_matrix(y, y_pred),
                classification_report=classification_report(y, y_pred),
                cross_val_scores=cv_scores.tolist(),
                training_time=training_time,
                prediction_time=prediction_time,
            )

            self.is_trained = True

            logger.info(
                f"Model trained successfully. Accuracy: {accuracy:.4f}, F1: {f1:.4f}"
            )

            return self.performance_metrics

        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            raise

    def _create_ensemble_model(self):
        """Create ensemble model"""
        rf = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
        gb = GradientBoostingClassifier(
            n_estimators=100, learning_rate=0.1, random_state=42
        )
        svm = SVC(kernel="rbf", probability=True, random_state=42)

        ensemble = VotingClassifier(
            estimators=[("rf", rf), ("gb", gb), ("svm", svm)],
            voting="soft",
            weights=[2, 2, 1],
        )

        return ensemble

    def _create_neural_network(self):
        """Create neural network model"""
        return MLPClassifier(
            hidden_layer_sizes=(100, 50),
            activation="relu",
            solver="adam",
            alpha=0.001,
            learning_rate="adaptive",
            max_iter=500,
            random_state=42,
        )

    def _tune_hyperparameters(self, X: np.ndarray, y: np.ndarray):
        """Tune hyperparameters"""
        try:
            if self.model is None:
                if self.model_type == "ensemble":
                    self.model = self._create_ensemble_model()
                elif self.model_type == "neural_network":
                    self.model = self._create_neural_network()
                elif self.model_type == "gradient_boosting":
                    self.model = GradientBoostingClassifier(
                        n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42
                    )
                elif self.model_type == "svm":
                    self.model = SVC(kernel="rbf", probability=True, random_state=42)
                else:
                    self.model = RandomForestClassifier(
                        n_estimators=100, max_depth=10, random_state=42
                    )

            if self.model_type == "random_forest":
                param_grid = {
                    "n_estimators": [50, 100, 200],
                    "max_depth": [5, 10, 15],
                    "min_samples_split": [2, 5, 10],
                }
                base_model = RandomForestClassifier(random_state=42)

            elif self.model_type == "gradient_boosting":
                param_grid = {
                    "n_estimators": [50, 100],
                    "learning_rate": [0.01, 0.1],
                    "max_depth": [3, 5, 7],
                }
                base_model = GradientBoostingClassifier(random_state=42)

            else:
                # Use default model without tuning for other types
                return self.model

            grid_search = GridSearchCV(
                base_model,
                param_grid,
                cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=42),
                scoring="accuracy",
                n_jobs=-1,
                verbose=0,
            )

            grid_search.fit(X, y)

            logger.info(f"Best parameters: {grid_search.best_params_}")
            logger.info(f"Best score: {grid_search.best_score_:.4f}")

            return grid_search.best_estimator_

        except Exception as e:
            logger.warning(
                f"Hyperparameter tuning failed: {str(e)}, using default parameters"
            )
            return self.model

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions"""
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")

        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Get prediction probabilities"""
        if not self.is_trained:
            raise ValueError("Model must be trained before making predictions")

        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba(X)
        else:
            raise ValueError("Model does not support probability predictions")

    def get_feature_importance(self, top_n: int = 20) -> Dict[str, float]:
        """Top feature importances as a dictionary (name -> score)."""
        if not self.feature_importance:
            return {}

        sorted_features = sorted(
            self.feature_importance.items(), key=lambda x: x[1], reverse=True
        )

        return dict(sorted_features[:top_n])

    def save(self, filepath: str):
        """Save model to file"""
        if not self.is_trained or self.model is None:
            raise ValueError("Model must be trained before saving")
        try:
            parent = os.path.dirname(filepath)
            if parent:
                os.makedirs(parent, exist_ok=True)
            joblib.dump(
                {
                    "model": self.model,
                    "model_type": self.model_type,
                    "feature_names": self.feature_names,
                    "feature_importance": self.feature_importance,
                    "performance_metrics": self.performance_metrics,
                    "is_trained": self.is_trained,
                },
                filepath,
            )

            logger.info(f"Model saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving model: {str(e)}")
            raise

    @classmethod
    def load(cls, filepath: str) -> "AdvancedBiomarkerModel":
        """Load model from file"""
        try:
            data = joblib.load(filepath)

            instance = cls(model_type=data["model_type"])
            instance.model = data["model"]
            instance.feature_names = data["feature_names"]
            instance.feature_importance = data["feature_importance"]
            instance.performance_metrics = data["performance_metrics"]
            instance.is_trained = data["is_trained"]

            logger.info(f"Model loaded from {filepath}")

            return instance

        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise

    def save_model(self, filepath: str) -> None:
        """Alias for ``save()`` (tests / legacy API)."""
        self.save(filepath)

    def load_model(self, filepath: str) -> None:
        """Load weights into this instance from ``filepath``."""
        loaded = AdvancedBiomarkerModel.load(filepath)
        self.model_type = loaded.model_type
        self.model = loaded.model
        self.feature_names = loaded.feature_names
        self.feature_importance = loaded.feature_importance
        self.performance_metrics = loaded.performance_metrics
        self.is_trained = loaded.is_trained


class ClinicalAnnotationService:
    """Advanced clinical annotation service"""

    def __init__(self):
        self.annotation_sources = {
            "cosmic": self._annotate_cosmic,
            "clinvar": self._annotate_clinvar,
            "oncokb": self._annotate_oncokb,
            "pubmed": self._annotate_pubmed,
        }

    async def annotate_biomarker(
        self, biomarker: str, sources: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Annotate biomarker with clinical information

        Args:
            biomarker: Biomarker identifier
            sources: List of annotation sources to use

        Returns:
            Annotated biomarker data
        """
        try:
            if sources is None:
                sources = list(self.annotation_sources.keys())

            annotations = {}

            for source in sources:
                if source in self.annotation_sources:
                    try:
                        annotation = await self.annotation_sources[source](biomarker)
                        annotations[source] = annotation
                    except Exception as e:
                        logger.warning(f"Error annotating with {source}: {str(e)}")
                        annotations[source] = {"error": str(e)}

            # Combine annotations
            combined_annotation = self._combine_annotations(biomarker, annotations)

            return combined_annotation

        except Exception as e:
            logger.error(f"Error annotating biomarker: {str(e)}")
            raise

    async def _annotate_cosmic(self, biomarker: str) -> Dict[str, Any]:
        """Annotate using COSMIC database via real API."""
        import asyncio
        data = await asyncio.to_thread(fetch_cosmic_mutations, gene_symbol=biomarker, limit=50)
        if data.get("data_source") == "unavailable":
            return {"source": "cosmic", "mutations": [], "cancer_types": [], "frequency": None, "clinical_significance": "unknown"}
        mutations = data.get("mutations", [])
        cancer_types = list({m.get("cancer_type") for m in mutations if m.get("cancer_type")})
        return {
            "source": "cosmic",
            "mutations": mutations,
            "cancer_types": cancer_types,
            "frequency": data.get("total_count"),
            "clinical_significance": "high" if mutations else "unknown",
        }

    async def _annotate_clinvar(self, biomarker: str) -> Dict[str, Any]:
        """Annotate using ClinVar database via real API."""
        import asyncio
        data = await asyncio.to_thread(fetch_clinvar_variants, gene_symbol=biomarker, limit=50)
        if data.get("data_source") == "unavailable":
            return {"source": "clinvar", "variants": [], "clinical_significance": "unknown", "review_status": "unknown"}
        variants = data.get("variants", [])
        sig = "high" if variants else "unknown"
        return {
            "source": "clinvar",
            "variants": variants,
            "clinical_significance": sig,
            "review_status": "reviewed" if variants else "unknown",
        }

    async def _annotate_oncokb(self, biomarker: str) -> Dict[str, Any]:
        """Annotate using OncoKB database via real API."""
        import asyncio
        data = await asyncio.to_thread(fetch_oncokb_cancer_genes, limit=500)
        genes = data.get("cancer_genes", []) if data.get("data_source") == "api" else []
        gene_info = next((g for g in genes if (g.get("gene_symbol") or g.get("hugoSymbol", "")) == biomarker), None)
        drugs_data = await asyncio.to_thread(fetch_oncokb_drugs, gene_symbol=biomarker)
        drug_list = drugs_data.get("drugs", []) if drugs_data.get("data_source") == "api" else []
        therapeutic = [d.get("drug_name", "") for d in drug_list if d.get("drug_name")]
        return {
            "source": "oncokb",
            "oncogenic": gene_info.get("oncogenic", "unknown") if gene_info else "unknown",
            "therapeutic_implications": therapeutic,
            "drug_targets": therapeutic,
        }

    async def _annotate_pubmed(self, biomarker: str) -> Dict[str, Any]:
        """Annotate using PubMed. No real API integration yet - returns empty to avoid fake data."""
        return {
            "source": "pubmed",
            "publications": [],
            "citation_count": 0,
            "recent_publications": [],
        }

    def _combine_annotations(
        self, biomarker: str, annotations: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine annotations from multiple sources"""

        combined = {
            "biomarker": biomarker,
            "sources": list(annotations.keys()),
            "clinical_significance": "unknown",
            "therapeutic_implications": [],
            "publications": [],
            "confidence_score": 0.0,
            "timestamp": datetime.now().isoformat(),
        }

        # Combine clinical significance
        significance_scores = []
        for source, annotation in annotations.items():
            if isinstance(annotation, dict) and "clinical_significance" in annotation:
                sig = annotation["clinical_significance"]
                if sig == "high":
                    significance_scores.append(3)
                elif sig == "moderate":
                    significance_scores.append(2)
                elif sig == "low":
                    significance_scores.append(1)

        if significance_scores:
            avg_score = np.mean(significance_scores)
            if avg_score >= 2.5:
                combined["clinical_significance"] = "high"
            elif avg_score >= 1.5:
                combined["clinical_significance"] = "moderate"
            else:
                combined["clinical_significance"] = "low"

            combined["confidence_score"] = min(1.0, avg_score / 3.0)

        # Combine therapeutic implications
        for source, annotation in annotations.items():
            if isinstance(annotation, dict):
                if "therapeutic_implications" in annotation:
                    combined["therapeutic_implications"].extend(
                        annotation["therapeutic_implications"]
                    )
                if "drug_targets" in annotation:
                    combined["therapeutic_implications"].extend(
                        annotation["drug_targets"]
                    )

        # Remove duplicates
        combined["therapeutic_implications"] = list(
            set(combined["therapeutic_implications"])
        )

        # Combine publications
        for source, annotation in annotations.items():
            if isinstance(annotation, dict) and "publications" in annotation:
                combined["publications"].extend(annotation["publications"])

        return combined


# Global instances
advanced_biomarker_model = AdvancedBiomarkerModel()
clinical_annotation_service = ClinicalAnnotationService()
