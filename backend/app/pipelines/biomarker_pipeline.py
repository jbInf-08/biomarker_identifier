"""
Main biomarker identification pipeline.
"""

import hashlib
import json
import os
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import yaml

from ..utils.logging_config import get_logger
from .io import DataIO
from .ml_select import MLSelectionPipeline
from .normalize import Normalization
from .qc import QualityControl
from .stats import StatisticalPipeline

logger = get_logger(__name__)


class BiomarkerPipeline:
    """
    Main pipeline for biomarker identification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the BiomarkerPipeline.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.pipeline_results = {}
        self.run_id = None

        # Initialize pipeline components
        self.data_io = DataIO(config)
        self.qc = QualityControl(config)
        self.normalizer = Normalization(config)
        self.stats_pipeline = StatisticalPipeline(config)
        self.ml_pipeline = MLSelectionPipeline(config)

    def run_pipeline(
        self,
        expression_file: str,
        labels_file: str,
        metadata_file: Optional[str] = None,
        output_dir: str = "results",
        run_name: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run the complete biomarker identification pipeline.

        Args:
            expression_file: Path to expression matrix file
            labels_file: Path to labels file
            metadata_file: Path to metadata file (optional)
            output_dir: Output directory for results
            run_name: Name for this run (optional)
            **kwargs: Additional pipeline parameters

        Returns:
            Complete pipeline results
        """
        try:
            # Generate run ID
            self.run_id = self._generate_run_id(run_name)
            logger.info(f"Starting biomarker pipeline run: {self.run_id}")

            # Create output directory
            run_output_dir = os.path.join(output_dir, self.run_id)
            os.makedirs(run_output_dir, exist_ok=True)

            # Initialize results
            results = {
                "run_id": self.run_id,
                "run_name": run_name,
                "timestamp": datetime.now().isoformat(),
                "config": self.config,
                "pipeline_steps": [],
            }

            # Step 1: Data Loading and Validation
            logger.info("Step 1: Loading and validating data")
            data_results = self.data_io.load_data(
                expression_file, labels_file, metadata_file, **kwargs
            )
            results["data_loading"] = data_results
            results["pipeline_steps"].append("data_loading")

            # Check validation status
            if data_results["validation_results"]["status"] == "failed":
                errors = data_results["validation_results"].get("errors", [])
                warnings = data_results["validation_results"].get("warnings", [])
                error_msg = "Data validation failed. Please check your input files."
                if errors:
                    error_msg += f"\nErrors: {errors}"
                if warnings:
                    error_msg += f"\nWarnings: {warnings}"
                logger.error(error_msg)
                raise ValueError(error_msg)

            expression_data = data_results["expression_data"]
            labels = data_results["labels"]
            metadata = data_results.get("metadata", {})

            # Step 2: Quality Control
            logger.info("Step 2: Performing quality control")
            qc_results = self.qc.perform_qc_analysis(expression_data, labels, **kwargs)
            results["quality_control"] = qc_results
            results["pipeline_steps"].append("quality_control")

            # Step 3: Data Filtering (with adaptive parameters)
            logger.info("Step 3: Filtering data")
            from ..utils.adaptive_parameters import AdaptiveParameters

            filter_params = AdaptiveParameters.get_filtering_parameters(
                expression_data.shape[1], expression_data.shape[0]
            )
            filtered_data, filtering_summary = self.qc.filter_data(
                expression_data,
                min_detection_rate=kwargs.get(
                    "min_detection_rate", filter_params.get("min_detection_rate", 0.1)
                ),
                min_variance=kwargs.get(
                    "min_variance", filter_params.get("min_variance", 0.0)
                ),
                max_missing_ratio=kwargs.get(
                    "max_missing_ratio", filter_params.get("max_missing_ratio", 0.5)
                ),
            )
            results["data_filtering"] = {
                "filtered_data_shape": filtered_data.shape,
                "filtering_summary": filtering_summary,
            }
            results["pipeline_steps"].append("data_filtering")

            # Step 4: Normalization (with adaptive parameters)
            logger.info("Step 4: Normalizing data")
            from ..utils.adaptive_parameters import AdaptiveParameters

            norm_params = AdaptiveParameters.get_normalization_parameters(
                filtered_data.shape[1], filtered_data.shape[0]
            )
            normalization_method = kwargs.pop("normalization_method", "log2")
            # Override batch_correction if not recommended for this dataset size
            batch_correction = kwargs.pop("batch_correction", None)
            if batch_correction is None and not norm_params.get(
                "batch_correction", False
            ):
                batch_correction = None  # Disable if not recommended
            batch_info = metadata.get("batch_info") if metadata else None

            norm_results = self.normalizer.normalize_data(
                filtered_data,
                labels,
                batch_info,
                normalization_method,
                batch_correction,
                **kwargs,
            )
            results["normalization"] = norm_results
            results["pipeline_steps"].append("normalization")

            normalized_data = norm_results["final_data"]

            # Step 5: Statistical Analysis
            logger.info("Step 5: Performing statistical analysis")
            stats_methods = kwargs.pop("stats_methods", None)
            alpha = kwargs.pop("alpha", 0.05)

            stats_results = self.stats_pipeline.run_statistical_analysis(
                normalized_data, labels, stats_methods, alpha, **kwargs
            )
            results["statistical_analysis"] = stats_results
            results["pipeline_steps"].append("statistical_analysis")

            # Step 6: Machine Learning Feature Selection
            logger.info("Step 6: Performing ML-based feature selection")
            selection_methods = kwargs.pop("selection_methods", None)
            n_features = kwargs.pop("n_features", 100)
            stability_bootstraps = kwargs.pop("stability_bootstraps", 100)

            ml_results = self.ml_pipeline.run_ml_selection(
                normalized_data,
                labels,
                selection_methods,
                n_features,
                stability_bootstraps,
                **kwargs,
            )
            results["ml_selection"] = ml_results
            results["pipeline_steps"].append("ml_selection")

            # Step 7: Generate Final Biomarker List
            logger.info("Step 7: Generating final biomarker list")
            biomarker_list = self._generate_biomarker_list(
                stats_results, ml_results, **kwargs
            )
            results["biomarker_list"] = biomarker_list
            results["pipeline_steps"].append("biomarker_list")

            # Step 8: Generate Summary
            logger.info("Step 8: Generating pipeline summary")
            pipeline_summary = self._generate_pipeline_summary(results)
            results["pipeline_summary"] = pipeline_summary

            # Step 9: Save Results
            logger.info("Step 9: Saving results")
            self._save_pipeline_results(results, run_output_dir)

            self.pipeline_results = results
            logger.info(f"Biomarker pipeline completed successfully: {self.run_id}")

            return results

        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            raise

    def _generate_run_id(self, run_name: Optional[str] = None) -> str:
        """
        Generate a unique run ID.

        Args:
            run_name: Optional run name

        Returns:
            Unique run ID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if run_name:
            # Clean run name for file system compatibility
            clean_name = "".join(
                c for c in run_name if c.isalnum() or c in (" ", "-", "_")
            ).rstrip()
            clean_name = clean_name.replace(" ", "_")
            return f"{clean_name}_{timestamp}"
        else:
            return f"biomarker_run_{timestamp}"

    def _generate_biomarker_list(
        self, stats_results: Dict[str, Any], ml_results: Dict[str, Any], **kwargs
    ) -> Dict[str, Any]:
        """
        Generate final biomarker list combining statistical and ML results.

        Args:
            stats_results: Statistical analysis results
            ml_results: ML selection results
            **kwargs: Additional parameters

        Returns:
            Biomarker list dictionary
        """
        biomarker_list = {"biomarkers": [], "summary": {}}

        # Get significant features from statistical analysis
        significant_features = {}
        for method, method_result in stats_results.get("method_results", {}).items():
            if "error" not in method_result:
                if "significant_features_adjusted" in method_result:
                    significant = method_result["significant_features_adjusted"]
                elif "significant_features" in method_result:
                    significant = method_result["significant_features"]
                else:
                    significant = []
                significant_features[method] = significant

        de_union: set = set()
        for features in significant_features.values():
            de_union.update(features)

        # Get consensus features from ML selection
        consensus_block = ml_results.get("consensus_features") or {}
        consensus_features = consensus_block.get("consensus_features", [])
        consensus_scores_map = consensus_block.get("consensus_scores") or {}

        # Combine features
        all_features = set()
        for features in significant_features.values():
            all_features.update(features)
        for feature_info in consensus_features:
            all_features.add(feature_info["feature"])

        # If nothing passed strict DE / consensus gates, still surface top ML-voted genes as official biomarkers
        # (real data often yields sparse FDR hits at small n).
        if not all_features and consensus_scores_map:
            top_k = int(kwargs.get("biomarker_fallback_top_k", 50))
            ranked = sorted(
                consensus_scores_map.items(), key=lambda x: x[1], reverse=True
            )[:top_k]
            all_features = {feat for feat, _ in ranked}
        elif (
            not de_union
            and consensus_scores_map
            and len(all_features) > int(kwargs.get("biomarker_fallback_top_k", 50))
        ):
            top_k = int(kwargs.get("biomarker_fallback_top_k", 50))
            ranked = sorted(
                consensus_scores_map.items(), key=lambda x: x[1], reverse=True
            )[:top_k]
            all_features = {feat for feat, _ in ranked}

        # Create biomarker entries
        biomarkers = []
        for feature in all_features:
            biomarker_entry = {
                "gene": feature,
                "statistical_evidence": {},
                "ml_evidence": {},
                "consensus_score": 0.0,
                "final_rank": 0,
            }

            # Add statistical evidence
            for method, features in significant_features.items():
                biomarker_entry["statistical_evidence"][method] = feature in features

            # Add ML evidence
            for feature_info in consensus_features:
                if feature_info["feature"] == feature:
                    biomarker_entry["ml_evidence"] = {
                        "consensus_score": feature_info["consensus_score"],
                        "selection_count": feature_info["selection_count"],
                        "methods": feature_info["methods"],
                    }
                    biomarker_entry["consensus_score"] = feature_info["consensus_score"]
                    break
            if (
                not biomarker_entry["ml_evidence"]
                and feature in consensus_scores_map
            ):
                sc = float(consensus_scores_map[feature])
                biomarker_entry["ml_evidence"] = {
                    "consensus_score": sc,
                    "selection_count": 0,
                    "methods": ["ranked_fallback"],
                }
                biomarker_entry["consensus_score"] = sc

            biomarkers.append(biomarker_entry)

        # Calculate final ranking score
        for biomarker in biomarkers:
            # Combine statistical and ML evidence
            stat_score = (
                sum(biomarker["statistical_evidence"].values())
                / len(biomarker["statistical_evidence"])
                if biomarker["statistical_evidence"]
                else 0
            )
            ml_score = biomarker["consensus_score"]

            # Weighted combination (can be adjusted)
            final_score = 0.6 * stat_score + 0.4 * ml_score
            biomarker["final_score"] = final_score

        # Sort by final score
        biomarkers.sort(key=lambda x: x["final_score"], reverse=True)

        # Add ranks
        for i, biomarker in enumerate(biomarkers):
            biomarker["final_rank"] = i + 1

        biomarker_list["biomarkers"] = biomarkers
        biomarker_list["summary"] = {
            "total_biomarkers": len(biomarkers),
            "statistically_significant": sum(
                1 for b in biomarkers if any(b["statistical_evidence"].values())
            ),
            "ml_selected": sum(1 for b in biomarkers if b["consensus_score"] > 0),
            "high_confidence": sum(1 for b in biomarkers if b["final_score"] > 0.7),
        }

        return biomarker_list

    def _generate_pipeline_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate comprehensive pipeline summary.

        Args:
            results: Pipeline results

        Returns:
            Pipeline summary
        """
        summary = {
            "run_id": results["run_id"],
            "run_name": results.get("run_name"),
            "timestamp": results["timestamp"],
            "pipeline_steps": results["pipeline_steps"],
            "data_summary": {},
            "results_summary": {},
        }

        # Data summary
        if "data_loading" in results:
            data_loading = results["data_loading"]
            summary["data_summary"] = {
                "n_genes": data_loading["expression_data"].shape[0],
                "n_samples": data_loading["expression_data"].shape[1],
                "n_classes": len(data_loading["labels"].unique()),
                "validation_status": data_loading["validation_results"]["status"],
            }

        # Results summary
        if "biomarker_list" in results:
            biomarker_list = results["biomarker_list"]
            summary["results_summary"] = biomarker_list["summary"]

        # Step summaries
        step_summaries = {}

        if "quality_control" in results:
            qc_summary = results["quality_control"].get("summary", {})
            step_summaries["quality_control"] = {
                "status": qc_summary.get("status", "unknown"),
                "n_warnings": len(qc_summary.get("warnings", [])),
                "n_recommendations": len(qc_summary.get("recommendations", [])),
            }

        if "statistical_analysis" in results:
            stats_summary = results["statistical_analysis"].get("summary", {})
            step_summaries["statistical_analysis"] = {
                "n_significant_features": stats_summary.get(
                    "total_significant_features", 0
                ),
                "methods_applied": stats_summary.get("methods_applied", []),
            }

        if "ml_selection" in results:
            ml_summary = results["ml_selection"].get("summary", {})
            best_cv_roc = None
            ev = ml_summary.get("evaluation_summary") or {}
            for v in ev.values():
                if isinstance(v, dict):
                    r = v.get("roc_auc")
                    if isinstance(r, (int, float)):
                        rr = float(r)
                        if best_cv_roc is None or rr > best_cv_roc:
                            best_cv_roc = rr
            step_summaries["ml_selection"] = {
                "consensus_features_count": ml_summary.get(
                    "consensus_features_count", 0
                ),
                "methods_applied": ml_summary.get("methods_applied", []),
                "best_cv_roc_auc_mean": best_cv_roc,
            }

        summary["step_summaries"] = step_summaries

        return summary

    def _save_pipeline_results(self, results: Dict[str, Any], output_dir: str):
        """
        Save all pipeline results to files.

        Args:
            results: Pipeline results
            output_dir: Output directory
        """
        try:
            # Save main results JSON
            results_file = os.path.join(output_dir, "pipeline_results.json")
            with open(results_file, "w") as f:
                json.dump(results, f, indent=2, default=str)

            # Save biomarker list CSV
            if "biomarker_list" in results:
                biomarker_file = os.path.join(output_dir, "biomarker_list.csv")
                biomarkers = results["biomarker_list"]["biomarkers"]
                if biomarkers:
                    df = pd.DataFrame(biomarkers)
                    df.to_csv(biomarker_file, index=False)

            # Save normalized data
            if "normalization" in results:
                norm_file = os.path.join(output_dir, "normalized_data.tsv")
                normalized_data = results["normalization"]["final_data"]
                normalized_data.to_csv(norm_file, sep="\t")

            # Save QC report
            if "quality_control" in results:
                qc_report_file = os.path.join(output_dir, "qc_report.html")
                self.qc.save_qc_report(qc_report_file)

            # Save normalization report
            if "normalization" in results:
                norm_report_file = os.path.join(output_dir, "normalization_report.html")
                self.normalizer.save_normalization_report(norm_report_file)

            # Save statistical analysis results
            if "statistical_analysis" in results:
                stats_file = os.path.join(output_dir, "statistical_analysis.json")
                self.stats_pipeline.save_analysis_results(stats_file)

            # Save ML selection results
            if "ml_selection" in results:
                ml_file = os.path.join(output_dir, "ml_selection.json")
                self.ml_pipeline.save_selection_results(ml_file)

            # Save pipeline summary
            summary_file = os.path.join(output_dir, "pipeline_summary.json")
            with open(summary_file, "w") as f:
                json.dump(results["pipeline_summary"], f, indent=2, default=str)

            logger.info(f"Pipeline results saved to {output_dir}")

        except Exception as e:
            logger.error(f"Failed to save pipeline results: {str(e)}")
            raise

    def get_biomarker_list(self, top_n: int = 50) -> List[Dict[str, Any]]:
        """
        Get top biomarkers from the pipeline.

        Args:
            top_n: Number of top biomarkers to return

        Returns:
            List of top biomarkers
        """
        if not self.pipeline_results or "biomarker_list" not in self.pipeline_results:
            return []

        biomarkers = self.pipeline_results["biomarker_list"]["biomarkers"]
        return biomarkers[:top_n]

    def get_pipeline_summary(self) -> Dict[str, Any]:
        """
        Get pipeline summary.

        Returns:
            Pipeline summary dictionary
        """
        if not self.pipeline_results:
            return {"status": "No pipeline run performed"}

        if "pipeline_summary" in self.pipeline_results:
            return self.pipeline_results["pipeline_summary"]

        pr = self.pipeline_results
        return {
            "run_id": pr.get("run_id"),
            "run_name": pr.get("run_name"),
            "pipeline_steps": pr.get("pipeline_steps", []),
            "status": "completed",
        }

    def load_config_from_file(self, config_file: str):
        """
        Load configuration from YAML file.

        Args:
            config_file: Path to configuration file
        """
        try:
            with open(config_file, "r") as f:
                self.config = yaml.safe_load(f)
            logger.info(f"Configuration loaded from {config_file}")
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}")
            raise

    def save_config_to_file(self, config_file: str):
        """
        Save current configuration to YAML file.

        Args:
            config_file: Path to configuration file
        """
        try:
            with open(config_file, "w") as f:
                yaml.safe_dump(self.config, f, sort_keys=False)
            logger.info(f"Configuration saved to {config_file}")
        except Exception as e:
            logger.error(f"Failed to save configuration: {str(e)}")
            raise
