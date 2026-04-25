"""
Complete ML Pipeline for Biomarker Discovery.

This module integrates all ML components into a comprehensive pipeline:
- Feature selection with consensus scoring
- Model training with hyperparameter optimization
- Cross-validation and performance evaluation
- Permutation testing for validation
- SHAP explainability analysis
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from .cross_validation import CrossValidator
from .evaluation_utils import holdout_multimodel_report
from .feature_selection import ConsensusFeatureSelector, FeatureSelector
from .graph_augmented import augment_expression_with_graph
from .model_training import ModelEvaluator, ModelTrainer
from .permutation_tests import PermutationTester, PermutationTestSuite
from .shap_explainer import SHAPExplainer

logger = logging.getLogger(__name__)


class MLPipeline:
    """
    Complete ML pipeline for biomarker discovery.

    Integrates feature selection, model training, evaluation, and explainability.
    """

    def __init__(self, random_state: int = 42, n_jobs: int = -1):
        """
        Initialize ML pipeline.

        Args:
            random_state: Random seed for reproducibility
            n_jobs: Number of parallel jobs
        """
        self.random_state = random_state
        self.n_jobs = n_jobs

        # Initialize components
        self.feature_selector = FeatureSelector(
            random_state=random_state, n_jobs=n_jobs
        )
        self.consensus_selector = ConsensusFeatureSelector(
            random_state=random_state, n_jobs=n_jobs
        )
        self.model_trainer = ModelTrainer(
            random_state=random_state, n_jobs=n_jobs, mlp_use_focal_loss=False
        )
        self.model_evaluator = ModelEvaluator(random_state=random_state)
        self.cross_validator = CrossValidator(random_state=random_state, n_jobs=n_jobs)
        self.permutation_tester = PermutationTester(
            random_state=random_state, n_jobs=n_jobs
        )
        self.shap_explainer = SHAPExplainer(random_state=random_state)

        # Results storage
        self.pipeline_results_ = {}
        self.selected_features_ = None
        self.trained_models_ = {}
        self.best_model_ = None
        self.explanations_ = {}
        self.model_selection_log_: Dict[str, Any] = {}

    @staticmethod
    def _resolve_graph_adjacency(
        X_before_fs: pd.DataFrame,
        X_after_fs: pd.DataFrame,
        graph_adjacency: Optional[np.ndarray],
        graph_adjacency_pre_selection: Optional[np.ndarray],
    ) -> Optional[np.ndarray]:
        """
        If ``graph_adjacency_pre_selection`` is set (square, order matches
        ``X_before_fs.columns``), subset rows/cols to selected genes.
        Otherwise return ``graph_adjacency`` (must already match ``X_after_fs``).
        """
        if graph_adjacency_pre_selection is not None:
            if graph_adjacency_pre_selection.shape != (
                X_before_fs.shape[1],
                X_before_fs.shape[1],
            ):
                raise ValueError(
                    "graph_adjacency_pre_selection must be (n_genes, n_genes) "
                    "matching X columns before feature selection"
                )
            cols_all = list(X_before_fs.columns)
            sel = list(X_after_fs.columns)
            idx = [cols_all.index(c) for c in sel]
            return graph_adjacency_pre_selection[np.ix_(idx, idx)]
        return graph_adjacency

    def run_complete_pipeline(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        n_features: int = 50,
        use_consensus_selection: bool = True,
        n_bootstrap: int = 100,
        cv_folds: int = 5,
        n_permutations: int = 1000,
        run_shap_analysis: bool = True,
        consensus_methods: Optional[List[str]] = None,
        graph_adjacency: Optional[np.ndarray] = None,
        graph_adjacency_pre_selection: Optional[np.ndarray] = None,
        graph_augment_mode: Optional[str] = None,
        mlp_use_focal_loss: bool = False,
        optimize_hyperparameters: bool = True,
        run_nested_cross_validation: bool = True,
        leak_safe_mode: bool = False,
        leak_safe_test_size: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Run complete ML pipeline for biomarker discovery.

        Args:
            X: Feature matrix
            y: Target variable
            n_features: Number of features to select
            use_consensus_selection: Whether to use consensus feature selection
            n_bootstrap: Number of bootstrap samples for consensus
            cv_folds: Number of CV folds
            n_permutations: Number of permutations for testing
            run_shap_analysis: Whether to run SHAP analysis
            consensus_methods: Optional subset of consensus selectors (ablation studies)
            graph_adjacency: Gene–gene adjacency aligned with **selected** columns
            graph_adjacency_pre_selection: Full adjacency aligned with **input** ``X``
                columns; subset automatically after feature selection
            graph_augment_mode: ``concat``, ``smooth_only``, or None to skip
            mlp_use_focal_loss: Focal loss for the PyTorch MLP (optional imbalance baseline)
            optimize_hyperparameters: Whether to run expensive model search in training
            run_nested_cross_validation: If False, skip nested CV (often hours on large panels)
            leak_safe_mode: If True, consensus fits on training data only; models train
                and CV run on the train split; unbiased metrics on a held-out test split.
            leak_safe_test_size: Fraction held out when ``leak_safe_mode`` is True.

        Returns:
            Dictionary with complete pipeline results
        """
        logger.info("Starting complete ML pipeline for biomarker discovery")
        logger.info(f"Input data shape: {X.shape}")
        logger.info(f"Target distribution: {y.value_counts().to_dict()}")

        pipeline_start_time = datetime.now()
        results = {
            "pipeline_config": {
                "n_features": n_features,
                "use_consensus_selection": use_consensus_selection,
                "n_bootstrap": n_bootstrap,
                "cv_folds": cv_folds,
                "n_permutations": n_permutations,
                "run_shap_analysis": run_shap_analysis,
                "consensus_methods": consensus_methods,
                "graph_augment_mode": graph_augment_mode,
                "graph_adjacency_pre_selection": graph_adjacency_pre_selection
                is not None,
                "mlp_use_focal_loss": mlp_use_focal_loss,
                "optimize_hyperparameters": optimize_hyperparameters,
                "run_nested_cross_validation": run_nested_cross_validation,
                "leak_safe_mode": leak_safe_mode,
                "leak_safe_test_size": leak_safe_test_size,
                "random_state": self.random_state,
            },
            "timestamps": {"start_time": pipeline_start_time.isoformat()},
            "timing": {},
        }

        try:
            self.model_trainer = ModelTrainer(
                random_state=self.random_state,
                n_jobs=self.n_jobs,
                mlp_use_focal_loss=mlp_use_focal_loss,
            )

            if leak_safe_mode:
                return self._run_leak_safe_pipeline(
                    X,
                    y,
                    n_features=n_features,
                    use_consensus_selection=use_consensus_selection,
                    n_bootstrap=n_bootstrap,
                    cv_folds=cv_folds,
                    n_permutations=n_permutations,
                    run_shap_analysis=run_shap_analysis,
                    consensus_methods=consensus_methods,
                    graph_adjacency=graph_adjacency,
                    graph_adjacency_pre_selection=graph_adjacency_pre_selection,
                    graph_augment_mode=graph_augment_mode,
                    mlp_use_focal_loss=mlp_use_focal_loss,
                    leak_safe_test_size=leak_safe_test_size,
                    pipeline_start_time=pipeline_start_time,
                    results=results,
                )

            # Step 1: Feature Selection
            logger.info("Step 1: Feature Selection")
            feature_selection_start = datetime.now()

            if use_consensus_selection:
                logger.info("Using consensus feature selection with bootstrap sampling")
                self.consensus_selector.fit(
                    X,
                    y,
                    n_bootstrap=n_bootstrap,
                    n_features=n_features,
                    consensus_methods=consensus_methods,
                )
                X_selected = self.consensus_selector.transform(X)
                self.selected_features_ = self.consensus_selector.consensus_results_[
                    "features"
                ]

                results["feature_selection"] = {
                    "method": "consensus",
                    "selected_features": self.selected_features_,
                    "consensus_summary": self.consensus_selector.get_consensus_summary().to_dict(
                        "records"
                    ),
                    "n_bootstrap": n_bootstrap,
                }
            else:
                logger.info("Using standard feature selection")
                self.feature_selector.fit(X, y, n_features=n_features)
                X_selected = self.feature_selector.transform(X)
                self.selected_features_ = self.feature_selector.selected_features_[
                    "features"
                ]

                results["feature_selection"] = {
                    "method": "standard",
                    "selected_features": self.selected_features_,
                    "feature_importance": self.feature_selector.get_feature_importance().to_dict(
                        "records"
                    ),
                }

            feature_selection_time = (
                datetime.now() - feature_selection_start
            ).total_seconds()
            results["timestamps"][
                "feature_selection_completed"
            ] = datetime.now().isoformat()
            results["timing"]["feature_selection_seconds"] = feature_selection_time

            logger.info(
                f"Feature selection completed in {feature_selection_time:.2f} seconds"
            )
            logger.info(f"Selected {len(self.selected_features_)} features")

            adj_resolved = self._resolve_graph_adjacency(
                X,
                X_selected,
                graph_adjacency,
                graph_adjacency_pre_selection,
            )
            if adj_resolved is not None and graph_augment_mode:
                if adj_resolved.shape[0] != X_selected.shape[1]:
                    raise ValueError(
                        "Resolved graph adjacency must match selected feature columns"
                    )
                logger.info(
                    "Applying graph augmentation (%s) for relational features",
                    graph_augment_mode,
                )
                X_selected = augment_expression_with_graph(
                    X_selected,
                    list(X_selected.columns),
                    adj_resolved,
                    mode=graph_augment_mode,
                )

            # Step 2: Model Training
            logger.info("Step 2: Model Training")
            training_start = datetime.now()

            training_results = self.model_trainer.train_models(
                X_selected,
                y,
                optimize_hyperparameters=optimize_hyperparameters,
                cv_folds=cv_folds,
            )
            self.trained_models_ = self.model_trainer.trained_models_

            training_time = (datetime.now() - training_start).total_seconds()
            results["timestamps"]["training_completed"] = datetime.now().isoformat()
            results["timing"]["training_seconds"] = training_time
            results["model_training"] = training_results

            logger.info(f"Model training completed in {training_time:.2f} seconds")
            logger.info(f"Trained {len(training_results)} models")

            # Step 3: Model Evaluation and Automated Selection
            logger.info("Step 3: Model Evaluation and Selection")
            evaluation_start = datetime.now()

            evaluation_results = self.model_evaluator.evaluate_models(
                self.trained_models_, X_selected, y, cv_folds=cv_folds
            )

            evaluation_time = (datetime.now() - evaluation_start).total_seconds()
            results["timestamps"]["evaluation_completed"] = datetime.now().isoformat()
            results["timing"]["evaluation_seconds"] = evaluation_time
            results["model_evaluation"] = evaluation_results

            # Lightweight automated model selection summary
            self.model_selection_log_ = {
                "candidate_models": list(self.trained_models_.keys()),
                "criteria": "best cross-validation score",
            }
            results["model_selection"] = self.model_selection_log_

            logger.info(
                f"Model evaluation and selection completed in {evaluation_time:.2f} seconds"
            )

            # Step 4: Cross-Validation (optional; nested CV is very expensive on wide matrices)
            if run_nested_cross_validation:
                logger.info("Step 4: Nested Cross-Validation")
                cv_start = datetime.now()

                cv_results = self.cross_validator.nested_cross_validation(
                    X_selected, y, cv_folds=cv_folds
                )

                cv_time = (datetime.now() - cv_start).total_seconds()
                results["timestamps"][
                    "cross_validation_completed"
                ] = datetime.now().isoformat()
                results["timing"]["cross_validation_seconds"] = cv_time
                results["cross_validation"] = cv_results

                logger.info(f"Cross-validation completed in {cv_time:.2f} seconds")
            else:
                logger.info("Skipping nested cross-validation (run_nested_cross_validation=False)")
                results["cross_validation"] = {"skipped": True}

            # Step 5: Get Best Model
            best_model_name, best_model = self.model_trainer.get_best_model()
            self.best_model_ = best_model
            results["best_model"] = {
                "name": best_model_name,
                "type": type(best_model).__name__,
                "performance": training_results[best_model_name]["best_score"],
            }

            logger.info(f"Best model: {best_model_name} ({type(best_model).__name__})")

            # Step 6: Permutation Testing
            if n_permutations and n_permutations > 0:
                logger.info("Step 6: Permutation Testing")
                permutation_start = datetime.now()

                permutation_results = (
                    self.permutation_tester.model_performance_permutation_test(
                        best_model, X_selected, y, n_permutations=n_permutations
                    )
                )

                permutation_time = (datetime.now() - permutation_start).total_seconds()
                results["timestamps"][
                    "permutation_testing_completed"
                ] = datetime.now().isoformat()
                results["timing"]["permutation_testing_seconds"] = permutation_time
                results["permutation_testing"] = permutation_results

                logger.info(
                    f"Permutation testing completed in {permutation_time:.2f} seconds"
                )
                logger.info(
                    f"Model significance p-value: {permutation_results['p_value']:.4f}"
                )
            else:
                logger.info("Skipping permutation testing (n_permutations=0)")
                results["permutation_testing"] = {"skipped": True}

            # Step 7: SHAP Analysis (Optional)
            if run_shap_analysis:
                logger.info("Step 7: SHAP Explainability Analysis")
                shap_start = datetime.now()

                try:
                    self.shap_explainer.fit_explainer(
                        best_model, X_selected, sample_size=min(1000, len(X_selected))
                    )

                    # Global explanations
                    global_explanations = self.shap_explainer.explain_global(
                        X_selected, max_display=20
                    )

                    # Local explanations for top samples
                    sample_indices = np.random.choice(
                        len(X_selected), size=min(10, len(X_selected)), replace=False
                    )
                    local_explanations = self.shap_explainer.explain_local(
                        X_selected, sample_indices=sample_indices
                    )

                    # Feature interactions (if supported)
                    try:
                        interaction_explanations = (
                            self.shap_explainer.explain_interactions(
                                X_selected, max_display=20
                            )
                        )
                    except Exception as e:
                        interaction_explanations = {
                            "error": f"Interactions not supported: {e}"
                        }

                    self.explanations_ = {
                        "global": global_explanations,
                        "local": local_explanations,
                        "interactions": interaction_explanations,
                    }

                    shap_time = (datetime.now() - shap_start).total_seconds()
                    results["timestamps"][
                        "shap_analysis_completed"
                    ] = datetime.now().isoformat()
                    results["timing"]["shap_analysis_seconds"] = shap_time
                    results["shap_explanations"] = self.explanations_

                    logger.info(f"SHAP analysis completed in {shap_time:.2f} seconds")

                except Exception as e:
                    logger.error(f"SHAP analysis failed: {str(e)}")
                    results["shap_explanations"] = {"error": str(e)}
            else:
                logger.info("Skipping SHAP analysis")
                results["shap_explanations"] = {"skipped": True}

            # Step 8: Generate Summary
            logger.info("Step 8: Generating Pipeline Summary")
            summary = self._generate_pipeline_summary(results)
            results["pipeline_summary"] = summary

            # Calculate total time
            total_time = (datetime.now() - pipeline_start_time).total_seconds()
            results["timestamps"]["pipeline_completed"] = datetime.now().isoformat()
            results["timing"]["total_pipeline_seconds"] = total_time

            logger.info(f"Complete ML pipeline finished in {total_time:.2f} seconds")

            # Store results
            self.pipeline_results_ = results

            return results

        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            results["error"] = str(e)
            results["timestamps"]["pipeline_failed"] = datetime.now().isoformat()
            return results

    def _run_leak_safe_pipeline(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        *,
        n_features: int,
        use_consensus_selection: bool,
        n_bootstrap: int,
        cv_folds: int,
        n_permutations: int,
        run_shap_analysis: bool,
        consensus_methods: Optional[List[str]],
        graph_adjacency: Optional[np.ndarray],
        graph_adjacency_pre_selection: Optional[np.ndarray],
        graph_augment_mode: Optional[str],
        mlp_use_focal_loss: bool,
        leak_safe_test_size: float,
        pipeline_start_time: datetime,
        results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Consensus and model fitting on training split only; report held-out test metrics.
        """
        try:
            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=leak_safe_test_size,
                stratify=y,
                random_state=self.random_state,
            )
            results["leak_safe_split"] = {
                "n_train": int(len(X_train)),
                "n_test": int(len(X_test)),
                "test_size_fraction": leak_safe_test_size,
            }
            results["leak_safe_mode"] = True

            fs_start = datetime.now()
            if use_consensus_selection:
                self.consensus_selector.fit(
                    X_train,
                    y_train,
                    n_bootstrap=n_bootstrap,
                    n_features=n_features,
                    consensus_methods=consensus_methods,
                )
                X_tr = self.consensus_selector.transform(X_train)
                X_te = self.consensus_selector.transform(X_test)
                self.selected_features_ = self.consensus_selector.consensus_results_[
                    "features"
                ]
                results["feature_selection"] = {
                    "method": "consensus",
                    "scope": "train_only",
                    "selected_features": self.selected_features_,
                    "consensus_summary": self.consensus_selector.get_consensus_summary().to_dict(
                        "records"
                    ),
                    "n_bootstrap": n_bootstrap,
                }
            else:
                self.feature_selector.fit(X_train, y_train, n_features=n_features)
                X_tr = self.feature_selector.transform(X_train)
                X_te = self.feature_selector.transform(X_test)
                self.selected_features_ = self.feature_selector.selected_features_[
                    "features"
                ]
                results["feature_selection"] = {
                    "method": "standard",
                    "scope": "train_only",
                    "selected_features": self.selected_features_,
                }

            results["timing"]["feature_selection_seconds"] = (
                datetime.now() - fs_start
            ).total_seconds()

            adj_r = self._resolve_graph_adjacency(
                X_train,
                X_tr,
                graph_adjacency,
                graph_adjacency_pre_selection,
            )
            if adj_r is not None and graph_augment_mode:
                if adj_r.shape[0] != X_tr.shape[1]:
                    raise ValueError(
                        "Resolved graph adjacency must match selected train columns"
                    )
                cols = list(X_tr.columns)
                X_tr = augment_expression_with_graph(
                    X_tr, cols, adj_r, mode=graph_augment_mode
                )
                X_te = augment_expression_with_graph(
                    X_te, cols, adj_r, mode=graph_augment_mode
                )

            self.model_trainer = ModelTrainer(
                random_state=self.random_state,
                n_jobs=self.n_jobs,
                mlp_use_focal_loss=mlp_use_focal_loss,
            )
            tr_start = datetime.now()
            training_results = self.model_trainer.train_models(
                X_tr, y_train, optimize_hyperparameters=True, cv_folds=cv_folds
            )
            self.trained_models_ = self.model_trainer.trained_models_
            results["model_training"] = training_results
            results["timing"]["training_seconds"] = (
                datetime.now() - tr_start
            ).total_seconds()

            ev_start = datetime.now()
            results["model_evaluation"] = self.model_evaluator.evaluate_models(
                self.trained_models_, X_tr, y_train, cv_folds=cv_folds
            )
            results["timing"]["evaluation_seconds"] = (
                datetime.now() - ev_start
            ).total_seconds()

            cv_start = datetime.now()
            results["cross_validation"] = (
                self.cross_validator.nested_cross_validation(
                    X_tr, y_train, cv_folds=cv_folds
                )
            )
            results["timing"]["cross_validation_seconds"] = (
                datetime.now() - cv_start
            ).total_seconds()

            best_model_name, best_model = self.model_trainer.get_best_model()
            self.best_model_ = best_model
            results["best_model"] = {
                "name": best_model_name,
                "type": type(best_model).__name__,
                "performance": training_results[best_model_name]["best_score"],
            }

            perm_start = datetime.now()
            results["permutation_testing"] = (
                self.permutation_tester.model_performance_permutation_test(
                    best_model, X_tr, y_train, n_permutations=n_permutations
                )
            )
            results["timing"]["permutation_testing_seconds"] = (
                datetime.now() - perm_start
            ).total_seconds()

            if run_shap_analysis:
                shap_start = datetime.now()
                try:
                    self.shap_explainer.fit_explainer(
                        best_model, X_tr, sample_size=min(1000, len(X_tr))
                    )
                    global_explanations = self.shap_explainer.explain_global(
                        X_tr, max_display=20
                    )
                    sample_indices = np.random.default_rng(self.random_state).choice(
                        len(X_tr), size=min(10, len(X_tr)), replace=False
                    )
                    local_explanations = self.shap_explainer.explain_local(
                        X_tr, sample_indices=sample_indices
                    )
                    try:
                        interaction_explanations = (
                            self.shap_explainer.explain_interactions(
                                X_tr, max_display=20
                            )
                        )
                    except Exception as e:
                        interaction_explanations = {"error": str(e)}
                    self.explanations_ = {
                        "global": global_explanations,
                        "local": local_explanations,
                        "interactions": interaction_explanations,
                    }
                    results["shap_explanations"] = self.explanations_
                    results["timing"]["shap_analysis_seconds"] = (
                        datetime.now() - shap_start
                    ).total_seconds()
                except Exception as e:
                    results["shap_explanations"] = {"error": str(e)}
            else:
                results["shap_explanations"] = {"skipped": True}

            fitted = {
                k: v["model"]
                for k, v in training_results.items()
                if v.get("model") is not None
            }
            results["holdout_test_evaluation"] = holdout_multimodel_report(
                fitted, X_te, y_test, mcnemar_pairs=None
            )
            results["pipeline_summary"] = self._generate_pipeline_summary(results)
            if best_model_name in results["holdout_test_evaluation"]["per_model"]:
                results["pipeline_summary"]["holdout_test_metrics"] = results[
                    "holdout_test_evaluation"
                ]["per_model"][best_model_name]

            results["timestamps"]["pipeline_completed"] = datetime.now().isoformat()
            results["timing"]["total_pipeline_seconds"] = (
                datetime.now() - pipeline_start_time
            ).total_seconds()
            self.pipeline_results_ = results
            return results
        except Exception as e:
            logger.error(f"Leak-safe pipeline failed: {str(e)}")
            results["error"] = str(e)
            results["timestamps"]["pipeline_failed"] = datetime.now().isoformat()
            return results

    def run_stratified_holdout_evaluation(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        *,
        test_size: float = 0.2,
        n_features: int = 50,
        n_bootstrap: int = 50,
        consensus_methods: Optional[List[str]] = None,
        graph_adjacency: Optional[np.ndarray] = None,
        graph_adjacency_pre_selection: Optional[np.ndarray] = None,
        graph_augment_mode: Optional[str] = None,
        train_shallow_gcn: bool = False,
        train_deep_gcn: bool = False,
        mlp_use_focal_loss: bool = False,
        optimize_hyperparameters: bool = False,
        mcnemar_pairs: Optional[List[Tuple[str, str]]] = None,
        cv_folds: int = 5,
    ) -> Dict[str, Any]:
        """
        Train on a stratified train split only (consensus fit on training data),
        evaluate on held-out test with imbalance-aware metrics and optional McNemar.

        Optional shallow GCN uses the same gene graph adjacency as relational features.
        """
        X_train, X_test, y_train, y_test = train_test_split(
            X,
            y,
            test_size=test_size,
            stratify=y,
            random_state=self.random_state,
        )

        selector = ConsensusFeatureSelector(
            random_state=self.random_state, n_jobs=self.n_jobs
        )
        selector.fit(
            X_train,
            y_train,
            n_bootstrap=n_bootstrap,
            n_features=n_features,
            consensus_methods=consensus_methods,
        )
        X_tr = selector.transform(X_train)
        X_te = selector.transform(X_test)

        adj_r = self._resolve_graph_adjacency(
            X_train,
            X_tr,
            graph_adjacency,
            graph_adjacency_pre_selection,
        )
        if adj_r is not None and graph_augment_mode:
            if adj_r.shape[0] != X_tr.shape[1]:
                raise ValueError("Resolved graph adjacency must match selected features")
            cols = list(X_tr.columns)
            X_tr = augment_expression_with_graph(
                X_tr, cols, adj_r, mode=graph_augment_mode
            )
            X_te = augment_expression_with_graph(
                X_te, cols, adj_r, mode=graph_augment_mode
            )

        trainer = ModelTrainer(
            random_state=self.random_state,
            n_jobs=self.n_jobs,
            mlp_use_focal_loss=mlp_use_focal_loss,
        )
        training = trainer.train_models(
            X_tr,
            y_train,
            optimize_hyperparameters=optimize_hyperparameters,
            cv_folds=cv_folds,
        )
        fitted: Dict[str, Any] = {
            k: v["model"] for k, v in training.items() if v.get("model") is not None
        }

        if train_deep_gcn and adj_r is not None:
            from .graph_augmented import DeepGeneGCNClassifier

            X_tr_expr = selector.transform(X_train)
            X_te_expr = selector.transform(X_test)
            if adj_r.shape[0] != X_tr_expr.shape[1]:
                raise ValueError("GCN adjacency must match selected genes")
            gcn = DeepGeneGCNClassifier(
                adjacency=adj_r,
                random_state=self.random_state,
            )
            gcn.fit(X_tr_expr, y_train)
            report = holdout_multimodel_report(
                fitted, X_te, y_test, mcnemar_pairs=mcnemar_pairs
            )
            gcn_metrics = holdout_multimodel_report(
                {"deep_gcn": gcn},
                X_te_expr,
                y_test,
                mcnemar_pairs=None,
            )
            report["per_model"]["deep_gcn"] = gcn_metrics["per_model"]["deep_gcn"]
        elif train_shallow_gcn and adj_r is not None:
            from .graph_augmented import ShallowGeneGCNClassifier

            # GCN on expression-only features (pre-augmentation matrix)
            X_tr_expr = selector.transform(X_train)
            X_te_expr = selector.transform(X_test)
            if adj_r.shape[0] != X_tr_expr.shape[1]:
                raise ValueError("GCN adjacency must match selected genes")
            gcn = ShallowGeneGCNClassifier(
                adjacency=adj_r,
                random_state=self.random_state,
            )
            gcn.fit(X_tr_expr, y_train)
            report = holdout_multimodel_report(
                fitted, X_te, y_test, mcnemar_pairs=mcnemar_pairs
            )
            gcn_metrics = holdout_multimodel_report(
                {"shallow_gcn": gcn},
                X_te_expr,
                y_test,
                mcnemar_pairs=None,
            )
            report["per_model"]["shallow_gcn"] = gcn_metrics["per_model"]["shallow_gcn"]
        else:
            report = holdout_multimodel_report(
                fitted, X_te, y_test, mcnemar_pairs=mcnemar_pairs
            )

        return {
            "holdout_config": {
                "test_size": test_size,
                "n_features": n_features,
                "consensus_methods": consensus_methods,
                "graph_augment_mode": graph_augment_mode,
                "train_shallow_gcn": train_shallow_gcn,
                "train_deep_gcn": train_deep_gcn,
                "mlp_use_focal_loss": mlp_use_focal_loss,
            },
            "training_summary": training,
            "evaluation": report,
            "n_train": int(len(X_train)),
            "n_test": int(len(X_test)),
        }

    def _generate_pipeline_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive pipeline summary."""

        summary = {
            "pipeline_status": "completed",
            "total_features_selected": len(self.selected_features_),
            "models_trained": len(self.trained_models_),
            "best_model": results["best_model"],
            "performance_metrics": {},
            "statistical_significance": {},
            "feature_insights": {},
        }

        # Performance metrics
        if "model_evaluation" in results:
            best_model_name = results["best_model"]["name"]
            if best_model_name in results["model_evaluation"]:
                eval_results = results["model_evaluation"][best_model_name][
                    "cv_results"
                ]
                summary["performance_metrics"] = {
                    "accuracy": eval_results.get("accuracy", {}).get("mean", 0),
                    "precision": eval_results.get("precision_macro", {}).get("mean", 0),
                    "recall": eval_results.get("recall_macro", {}).get("mean", 0),
                    "f1_score": eval_results.get("f1_macro", {}).get("mean", 0),
                    "roc_auc": eval_results.get("roc_auc", {}).get("mean", 0),
                    "average_precision": eval_results.get("average_precision", {}).get(
                        "mean", 0
                    ),
                    "balanced_accuracy": eval_results.get("balanced_accuracy", {}).get(
                        "mean", 0
                    ),
                    "matthews_corrcoef": eval_results.get(
                        "matthews_corrcoef", {}
                    ).get("mean", 0),
                }

        # Statistical significance
        if "permutation_testing" in results:
            perm_results = results["permutation_testing"]
            if perm_results.get("skipped"):
                summary["statistical_significance"] = {"skipped": True}
            else:
                summary["statistical_significance"] = {
                    "model_significant": perm_results["significant"],
                    "p_value": perm_results["p_value"],
                    "effect_size": perm_results["effect_size"],
                }

        # Feature insights
        if "shap_explanations" in results and "global" in results["shap_explanations"]:
            global_explanations = results["shap_explanations"]["global"]
            if (
                "top_features" in global_explanations
                and global_explanations["top_features"]
            ):
                top_feature = global_explanations["top_features"][0]
                summary["feature_insights"] = {
                    "top_feature": top_feature["feature"],
                    "top_feature_importance": top_feature["importance"],
                    "total_features_analyzed": global_explanations["summary_stats"][
                        "total_features"
                    ],
                }

        return summary

    def get_feature_importance_summary(self) -> pd.DataFrame:
        """Get comprehensive feature importance summary."""

        if self.selected_features_ is None:
            raise ValueError("Pipeline not run. Call run_complete_pipeline first.")

        # Get feature importance from different sources
        importance_data = []

        for feature in self.selected_features_:
            row = {"feature": feature}

            # From feature selection
            if (
                hasattr(self, "feature_selector")
                and self.feature_selector.selected_features_
            ):
                if (
                    feature
                    in self.feature_selector.selected_features_["consensus_scores"]
                ):
                    row[
                        "selection_consensus_score"
                    ] = self.feature_selector.selected_features_["consensus_scores"][
                        feature
                    ]
                if (
                    feature
                    in self.feature_selector.selected_features_["stability_scores"]
                ):
                    row[
                        "selection_stability_score"
                    ] = self.feature_selector.selected_features_["stability_scores"][
                        feature
                    ]

            # From consensus selection
            if (
                hasattr(self, "consensus_selector")
                and self.consensus_selector.consensus_results_
            ):
                if feature in self.consensus_selector.consensus_results_["mean_scores"]:
                    row[
                        "consensus_mean_score"
                    ] = self.consensus_selector.consensus_results_["mean_scores"][
                        feature
                    ]
                if (
                    feature
                    in self.consensus_selector.consensus_results_["selection_frequency"]
                ):
                    row[
                        "consensus_frequency"
                    ] = self.consensus_selector.consensus_results_[
                        "selection_frequency"
                    ][
                        feature
                    ]

            # From SHAP
            if (
                "shap_explanations" in self.pipeline_results_
                and "global" in self.pipeline_results_["shap_explanations"]
            ):
                global_explanations = self.pipeline_results_["shap_explanations"][
                    "global"
                ]
                if "feature_importance" in global_explanations:
                    for importance_item in global_explanations["feature_importance"]:
                        if importance_item["feature"] == feature:
                            row["shap_importance"] = importance_item["importance"]
                            break

            importance_data.append(row)

        return pd.DataFrame(importance_data)

    def save_pipeline_results(self, filepath: str):
        """Save complete pipeline results to file."""

        if not self.pipeline_results_:
            raise ValueError("No pipeline results to save. Run pipeline first.")

        # Prepare data for saving (exclude non-serializable objects)
        results_to_save = {
            "pipeline_results": self.pipeline_results_,
            "selected_features": self.selected_features_,
            "best_model_name": self.best_model_.__class__.__name__
            if self.best_model_
            else None,
            "explanations": self.explanations_,
        }

        joblib.dump(results_to_save, filepath)
        logger.info(f"Pipeline results saved to {filepath}")

    def load_pipeline_results(self, filepath: str):
        """Load pipeline results from file."""

        data = joblib.load(filepath)
        self.pipeline_results_ = data["pipeline_results"]
        self.selected_features_ = data["selected_features"]
        self.explanations_ = data["explanations"]
        logger.info(f"Pipeline results loaded from {filepath}")

    def get_pipeline_report(self) -> Dict[str, Any]:
        """Generate comprehensive pipeline report."""

        if not self.pipeline_results_:
            raise ValueError("No pipeline results available. Run pipeline first.")

        report = {
            "executive_summary": self.pipeline_results_["pipeline_summary"],
            "feature_selection_summary": self.pipeline_results_["feature_selection"],
            "model_performance": self.pipeline_results_["model_evaluation"],
            "statistical_validation": self.pipeline_results_["permutation_testing"],
            "feature_importance": self.get_feature_importance_summary().to_dict(
                "records"
            ),
            "timing_analysis": self.pipeline_results_["timing"],
            "recommendations": self._generate_recommendations(),
        }

        return report

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on pipeline results."""

        recommendations = []

        # Performance recommendations
        if "pipeline_summary" in self.pipeline_results_:
            summary = self.pipeline_results_["pipeline_summary"]

            if "performance_metrics" in summary:
                roc_auc = summary["performance_metrics"].get("roc_auc", 0)
                if roc_auc < 0.7:
                    recommendations.append(
                        "Model performance is below 0.7 ROC-AUC. Consider feature engineering or different algorithms."
                    )
                elif roc_auc > 0.9:
                    recommendations.append(
                        "Excellent model performance achieved. Consider validation on independent datasets."
                    )

            if "statistical_significance" in summary:
                if not summary["statistical_significance"].get(
                    "model_significant", False
                ):
                    recommendations.append(
                        "Model is not statistically significant. Results may be due to chance."
                    )

        # Feature recommendations
        if self.selected_features_:
            if len(self.selected_features_) < 10:
                recommendations.append(
                    "Few features selected. Consider relaxing selection criteria."
                )
            elif len(self.selected_features_) > 100:
                recommendations.append(
                    "Many features selected. Consider more stringent selection criteria."
                )

        return recommendations
