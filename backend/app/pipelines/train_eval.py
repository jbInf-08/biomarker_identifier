"""
Model training and evaluation pipeline for biomarker identification.
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_val_score
from sklearn.svm import SVC

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class ModelTrainingPipeline:
    """
    Handles model training and evaluation for biomarker identification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ModelTrainingPipeline module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.training_results = {}

    def train_and_evaluate(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        selected_features: List[str] = None,
        model_type: str = "logistic_regression",
        cv_folds: int = 5,
        test_size: float = 0.2,
        random_state: int = 42,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Train and evaluate a model using selected features.

        Args:
            expression_data: Expression data matrix
            labels: Sample labels
            selected_features: List of selected features (if None, use all)
            model_type: Type of model to train
            cv_folds: Number of cross-validation folds
            test_size: Proportion of data for testing
            random_state: Random seed
            **kwargs: Additional parameters

        Returns:
            Training and evaluation results
        """
        try:
            # Prepare data
            if selected_features:
                X = expression_data.loc[selected_features].T
            else:
                X = expression_data.T

            y = labels

            # Split data
            from sklearn.model_selection import train_test_split

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=test_size, random_state=random_state, stratify=y
            )

            results = {
                "model_type": model_type,
                "selected_features": selected_features,
                "data_split": {
                    "train_size": len(X_train),
                    "test_size": len(X_test),
                    "cv_folds": cv_folds,
                },
                "model_performance": {},
                "cross_validation": {},
                "calibration": {},
                "permutation_test": {},
            }

            # Train model
            model = self._train_model(X_train, y_train, model_type, **kwargs)
            results["model"] = model

            # Evaluate on test set
            test_performance = self._evaluate_model(model, X_test, y_test)
            results["model_performance"] = test_performance

            # Cross-validation
            cv_results = self._cross_validate_model(model, X, y, cv_folds, random_state)
            results["cross_validation"] = cv_results

            # Calibration analysis
            calibration_results = self._calibrate_model(model, X_test, y_test)
            results["calibration"] = calibration_results

            # Permutation test
            permutation_results = self._permutation_test(
                model, X_test, y_test, n_permutations=100
            )
            results["permutation_test"] = permutation_results

            # Generate plots
            plots = self._generate_evaluation_plots(results)
            results["plots"] = plots

            # Generate summary
            summary = self._generate_evaluation_summary(results)
            results["summary"] = summary

            self.training_results = results
            logger.info("Model training and evaluation completed")

            return results

        except Exception as e:
            logger.error(f"Failed to train and evaluate model: {str(e)}")
            raise

    def _train_model(
        self, X_train: pd.DataFrame, y_train: pd.Series, model_type: str, **kwargs
    ) -> Any:
        """
        Train a model based on the specified type.

        Args:
            X_train: Training features
            y_train: Training labels
            model_type: Type of model to train
            **kwargs: Additional parameters

        Returns:
            Trained model
        """
        if model_type == "logistic_regression":
            model = LogisticRegression(
                random_state=kwargs.get("random_state", 42),
                max_iter=kwargs.get("max_iter", 1000),
                C=kwargs.get("C", 1.0),
                penalty=kwargs.get("penalty", "l2"),
                solver=kwargs.get("solver", "lbfgs"),
            )
        elif model_type == "random_forest":
            model = RandomForestClassifier(
                n_estimators=kwargs.get("n_estimators", 100),
                max_depth=kwargs.get("max_depth", None),
                random_state=kwargs.get("random_state", 42),
                n_jobs=kwargs.get("n_jobs", -1),
            )
        elif model_type == "svm":
            model = SVC(
                kernel=kwargs.get("kernel", "rbf"),
                C=kwargs.get("C", 1.0),
                probability=True,
                random_state=kwargs.get("random_state", 42),
            )
        elif model_type == "elastic_net":
            model = LogisticRegression(
                penalty="elasticnet",
                solver="saga",
                l1_ratio=kwargs.get("l1_ratio", 0.5),
                C=kwargs.get("C", 1.0),
                random_state=kwargs.get("random_state", 42),
                max_iter=kwargs.get("max_iter", 1000),
            )
        else:
            raise ValueError(f"Unsupported model type: {model_type}")

        model.fit(X_train, y_train)
        return model

    def _evaluate_model(
        self, model: Any, X_test: pd.DataFrame, y_test: pd.Series
    ) -> Dict[str, Any]:
        """
        Evaluate model performance on test set.

        Args:
            model: Trained model
            X_test: Test features
            y_test: Test labels

        Returns:
            Performance metrics
        """
        # Predictions
        y_pred = model.predict(X_test)
        y_pred_proba = (
            model.predict_proba(X_test)[:, 1]
            if hasattr(model, "predict_proba")
            else None
        )

        # Basic metrics
        accuracy = accuracy_score(y_test, y_pred)
        precision = precision_score(y_test, y_pred, average="weighted")
        recall = recall_score(y_test, y_pred, average="weighted")
        f1 = f1_score(y_test, y_pred, average="weighted")

        # ROC AUC
        roc_auc = None
        if y_pred_proba is not None:
            roc_auc = roc_auc_score(y_test, y_pred_proba)

        # Confusion matrix
        cm = confusion_matrix(y_test, y_pred)

        # Classification report
        class_report = classification_report(y_test, y_pred, output_dict=True)

        # ROC curve data
        roc_curve_data = None
        if y_pred_proba is not None:
            fpr, tpr, thresholds = roc_curve(y_test, y_pred_proba)
            roc_curve_data = {
                "fpr": fpr.tolist(),
                "tpr": tpr.tolist(),
                "thresholds": thresholds.tolist(),
            }

        # Precision-recall curve data
        pr_curve_data = None
        if y_pred_proba is not None:
            precision_curve, recall_curve, pr_thresholds = precision_recall_curve(
                y_test, y_pred_proba
            )
            pr_curve_data = {
                "precision": precision_curve.tolist(),
                "recall": recall_curve.tolist(),
                "thresholds": pr_thresholds.tolist(),
            }

        mcc = matthews_corrcoef(y_test, y_pred)
        bal_acc = balanced_accuracy_score(y_test, y_pred)

        return {
            "accuracy": float(accuracy),
            "balanced_accuracy": float(bal_acc),
            "matthews_corrcoef": float(mcc),
            "precision": float(precision),
            "recall": float(recall),
            "f1_score": float(f1),
            "roc_auc": float(roc_auc) if roc_auc is not None else None,
            "confusion_matrix": cm.tolist(),
            "classification_report": class_report,
            "roc_curve": roc_curve_data,
            "pr_curve": pr_curve_data,
            "predictions": {
                "y_pred": y_pred.tolist(),
                "y_pred_proba": y_pred_proba.tolist()
                if y_pred_proba is not None
                else None,
            },
        }

    def _cross_validate_model(
        self,
        model: Any,
        X: pd.DataFrame,
        y: pd.Series,
        cv_folds: int,
        random_state: int,
    ) -> Dict[str, Any]:
        """
        Perform cross-validation on the model.

        Args:
            model: Model to cross-validate
            X: Features
            y: Labels
            cv_folds: Number of CV folds
            random_state: Random seed

        Returns:
            Cross-validation results
        """
        cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=random_state)

        # Cross-validation scores
        cv_accuracy = cross_val_score(model, X, y, cv=cv, scoring="accuracy")
        cv_precision = cross_val_score(model, X, y, cv=cv, scoring="precision_weighted")
        cv_recall = cross_val_score(model, X, y, cv=cv, scoring="recall_weighted")
        cv_f1 = cross_val_score(model, X, y, cv=cv, scoring="f1_weighted")

        # ROC AUC if possible
        cv_roc_auc = None
        try:
            cv_roc_auc = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
        except:
            pass

        return {
            "accuracy": {
                "scores": cv_accuracy.tolist(),
                "mean": float(cv_accuracy.mean()),
                "std": float(cv_accuracy.std()),
            },
            "precision": {
                "scores": cv_precision.tolist(),
                "mean": float(cv_precision.mean()),
                "std": float(cv_precision.std()),
            },
            "recall": {
                "scores": cv_recall.tolist(),
                "mean": float(cv_recall.mean()),
                "std": float(cv_recall.std()),
            },
            "f1_score": {
                "scores": cv_f1.tolist(),
                "mean": float(cv_f1.mean()),
                "std": float(cv_f1.std()),
            },
            "roc_auc": {
                "scores": cv_roc_auc.tolist() if cv_roc_auc is not None else None,
                "mean": float(cv_roc_auc.mean()) if cv_roc_auc is not None else None,
                "std": float(cv_roc_auc.std()) if cv_roc_auc is not None else None,
            }
            if cv_roc_auc is not None
            else None,
        }

    def _calibrate_model(
        self, model: Any, X_test: pd.DataFrame, y_test: pd.Series
    ) -> Dict[str, Any]:
        """
        Perform model calibration analysis.

        Args:
            model: Trained model
            X_test: Test features
            y_test: Test labels

        Returns:
            Calibration results
        """
        try:
            if hasattr(model, "predict_proba"):
                y_pred_proba = model.predict_proba(X_test)[:, 1]

                # Calibration curve
                fraction_of_positives, mean_predicted_value = calibration_curve(
                    y_test, y_pred_proba, n_bins=10
                )

                # Brier score
                from sklearn.metrics import brier_score_loss

                brier_score = brier_score_loss(y_test, y_pred_proba)

                return {
                    "fraction_of_positives": fraction_of_positives.tolist(),
                    "mean_predicted_value": mean_predicted_value.tolist(),
                    "brier_score": float(brier_score),
                    "calibration_curve": {
                        "fraction_of_positives": fraction_of_positives.tolist(),
                        "mean_predicted_value": mean_predicted_value.tolist(),
                    },
                }
            else:
                return {"error": "Model does not support probability predictions"}

        except Exception as e:
            return {"error": f"Calibration failed: {str(e)}"}

    def _permutation_test(
        self,
        model: Any,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        n_permutations: int = 100,
    ) -> Dict[str, Any]:
        """
        Perform permutation test to assess significance.

        Args:
            model: Trained model
            X_test: Test features
            y_test: Test labels
            n_permutations: Number of permutations

        Returns:
            Permutation test results
        """
        try:
            # Original performance
            original_score = accuracy_score(y_test, model.predict(X_test))

            # Permuted scores
            permuted_scores = []
            for _ in range(n_permutations):
                y_permuted = np.random.permutation(y_test)
                permuted_score = accuracy_score(y_permuted, model.predict(X_test))
                permuted_scores.append(permuted_score)

            permuted_scores = np.array(permuted_scores)

            # Calculate p-value
            p_value = np.mean(permuted_scores >= original_score)

            return {
                "original_score": float(original_score),
                "permuted_scores": permuted_scores.tolist(),
                "p_value": float(p_value),
                "n_permutations": n_permutations,
                "permuted_mean": float(permuted_scores.mean()),
                "permuted_std": float(permuted_scores.std()),
            }

        except Exception as e:
            return {"error": f"Permutation test failed: {str(e)}"}

    def _generate_evaluation_plots(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate evaluation plots.

        Args:
            results: Evaluation results

        Returns:
            Dictionary of plot objects
        """
        plots = {}

        try:
            import plotly.express as px
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # ROC curve
            if results["model_performance"].get("roc_curve"):
                roc_data = results["model_performance"]["roc_curve"]
                fig_roc = go.Figure()
                fig_roc.add_trace(
                    go.Scatter(
                        x=roc_data["fpr"],
                        y=roc_data["tpr"],
                        mode="lines",
                        name=f'ROC (AUC = {results["model_performance"]["roc_auc"]:.3f})',
                    )
                )
                fig_roc.add_trace(
                    go.Scatter(
                        x=[0, 1],
                        y=[0, 1],
                        mode="lines",
                        name="Random",
                        line=dict(dash="dash"),
                    )
                )
                fig_roc.update_layout(
                    title="ROC Curve",
                    xaxis_title="False Positive Rate",
                    yaxis_title="True Positive Rate",
                )
                plots["roc_curve"] = fig_roc

            # Precision-Recall curve
            if results["model_performance"].get("pr_curve"):
                pr_data = results["model_performance"]["pr_curve"]
                fig_pr = go.Figure()
                fig_pr.add_trace(
                    go.Scatter(
                        x=pr_data["recall"],
                        y=pr_data["precision"],
                        mode="lines",
                        name="Precision-Recall",
                    )
                )
                fig_pr.update_layout(
                    title="Precision-Recall Curve",
                    xaxis_title="Recall",
                    yaxis_title="Precision",
                )
                plots["pr_curve"] = fig_pr

            # Confusion matrix
            cm = results["model_performance"]["confusion_matrix"]
            fig_cm = px.imshow(
                cm,
                text_auto=True,
                aspect="auto",
                title="Confusion Matrix",
                labels=dict(x="Predicted", y="Actual"),
            )
            plots["confusion_matrix"] = fig_cm

            # Calibration curve
            if results["calibration"].get("calibration_curve"):
                cal_data = results["calibration"]["calibration_curve"]
                fig_cal = go.Figure()
                fig_cal.add_trace(
                    go.Scatter(
                        x=cal_data["mean_predicted_value"],
                        y=cal_data["fraction_of_positives"],
                        mode="lines+markers",
                        name="Model",
                    )
                )
                fig_cal.add_trace(
                    go.Scatter(
                        x=[0, 1],
                        y=[0, 1],
                        mode="lines",
                        name="Perfectly Calibrated",
                        line=dict(dash="dash"),
                    )
                )
                fig_cal.update_layout(
                    title="Calibration Curve",
                    xaxis_title="Mean Predicted Probability",
                    yaxis_title="Fraction of Positives",
                )
                plots["calibration_curve"] = fig_cal

            # Cross-validation scores
            cv_results = results["cross_validation"]
            cv_data = []
            for metric, data in cv_results.items():
                if data and "scores" in data:
                    for score in data["scores"]:
                        cv_data.append({"metric": metric, "score": score})

            if cv_data:
                cv_df = pd.DataFrame(cv_data)
                fig_cv = px.box(
                    cv_df, x="metric", y="score", title="Cross-Validation Scores"
                )
                plots["cv_scores"] = fig_cv

            # Permutation test
            if results["permutation_test"].get("permuted_scores"):
                perm_data = results["permutation_test"]
                fig_perm = px.histogram(
                    x=perm_data["permuted_scores"],
                    title="Permutation Test Results",
                    labels={"x": "Accuracy Score", "y": "Count"},
                )
                fig_perm.add_vline(
                    x=perm_data["original_score"],
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"Original Score: {perm_data['original_score']:.3f}",
                )
                plots["permutation_test"] = fig_perm

        except ImportError:
            logger.warning("Plotly not available, skipping evaluation plots")

        return plots

    def _generate_evaluation_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate evaluation summary.

        Args:
            results: Evaluation results

        Returns:
            Evaluation summary
        """
        summary = {
            "model_type": results["model_type"],
            "n_features": len(results["selected_features"])
            if results["selected_features"]
            else "all",
            "test_performance": {
                "accuracy": results["model_performance"]["accuracy"],
                "balanced_accuracy": results["model_performance"].get(
                    "balanced_accuracy"
                ),
                "matthews_corrcoef": results["model_performance"].get(
                    "matthews_corrcoef"
                ),
                "precision": results["model_performance"]["precision"],
                "recall": results["model_performance"]["recall"],
                "f1_score": results["model_performance"]["f1_score"],
                "roc_auc": results["model_performance"]["roc_auc"],
            },
            "cross_validation": {},
            "calibration": {},
            "permutation_test": {},
        }

        # CV summary
        cv_results = results["cross_validation"]
        for metric, data in cv_results.items():
            if data and "mean" in data:
                summary["cross_validation"][metric] = {
                    "mean": data["mean"],
                    "std": data["std"],
                }

        # Calibration summary
        if "brier_score" in results["calibration"]:
            summary["calibration"]["brier_score"] = results["calibration"][
                "brier_score"
            ]

        # Permutation test summary
        if "p_value" in results["permutation_test"]:
            summary["permutation_test"]["p_value"] = results["permutation_test"][
                "p_value"
            ]
            summary["permutation_test"]["significant"] = (
                results["permutation_test"]["p_value"] < 0.05
            )

        return summary

    def save_model(self, model_path: str):
        """
        Save the trained model.

        Args:
            model_path: Path to save the model
        """
        if not self.training_results or "model" not in self.training_results:
            raise ValueError("No trained model to save")

        try:
            import joblib

            joblib.dump(self.training_results["model"], model_path)
            logger.info(f"Model saved to {model_path}")
        except Exception as e:
            logger.error(f"Failed to save model: {str(e)}")
            raise

    def load_model(self, model_path: str):
        """
        Load a trained model.

        Args:
            model_path: Path to the model file
        """
        try:
            import joblib

            model = joblib.load(model_path)
            self.training_results["model"] = model
            logger.info(f"Model loaded from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {str(e)}")
            raise

    def save_evaluation_results(self, output_path: str, format: str = "json"):
        """
        Save evaluation results to file.

        Args:
            output_path: Output file path
            format: Output format

        Returns:
            Path to saved file
        """
        if not self.training_results:
            raise ValueError("No evaluation results to save")

        try:
            if format.lower() == "json":
                import json

                with open(output_path, "w") as f:
                    json.dump(self.training_results, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Evaluation results saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save evaluation results: {str(e)}")
            raise

    def get_evaluation_summary(self) -> Dict[str, Any]:
        """
        Get evaluation summary.

        Returns:
            Evaluation summary dictionary
        """
        if not self.training_results:
            return {"status": "No evaluation performed"}

        return self.training_results.get("summary", {"status": "unknown"})
