"""
Normalization utilities for biomarker pipeline.
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler, StandardScaler

from ..data_processing.batch_correction import BatchCorrection
from ..data_processing.data_transformation import DataTransformation
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class Normalization:
    """
    Handles data normalization and preprocessing.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the Normalization module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.normalization_results = {}
        self.transformer = DataTransformation(config)
        self.batch_corrector = BatchCorrection(config)

    def normalize_data(
        self,
        expression_data: pd.DataFrame,
        labels: Optional[pd.Series] = None,
        batch_info: Optional[pd.Series] = None,
        normalization_method: str = "log2",
        batch_correction: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive data normalization.

        Args:
            expression_data: Expression data matrix
            labels: Sample labels (optional)
            batch_info: Batch information (optional)
            normalization_method: Normalization method
            batch_correction: Batch correction method (optional)
            **kwargs: Additional parameters

        Returns:
            Normalization results
        """
        try:
            results = {
                "original_data": expression_data.copy(),
                "normalization_method": normalization_method,
                "batch_correction": batch_correction,
            }

            # Step 1: Data transformation
            if normalization_method != "none":
                transformed_data = self._apply_transformation(
                    expression_data, normalization_method, **kwargs
                )
                results["transformed_data"] = transformed_data
                results[
                    "transformation_params"
                ] = self.transformer.transformation_params
            else:
                transformed_data = expression_data.copy()
                results["transformed_data"] = transformed_data

            # Step 2: Batch correction
            if batch_correction and batch_info is not None:
                corrected_data = self._apply_batch_correction(
                    transformed_data, batch_info, batch_correction, **kwargs
                )
                results["corrected_data"] = corrected_data
                results[
                    "batch_correction_params"
                ] = self.batch_corrector.correction_params
            else:
                corrected_data = transformed_data.copy()
                results["corrected_data"] = corrected_data

            # Step 3: Final normalization
            final_data = self._apply_final_normalization(corrected_data, **kwargs)
            results["final_data"] = final_data

            # Step 4: Generate normalization summary
            normalization_summary = self._generate_normalization_summary(results)
            results["summary"] = normalization_summary

            # Step 5: Generate comparison plots
            comparison_plots = self._generate_comparison_plots(
                results, labels, batch_info
            )
            results["plots"] = comparison_plots

            self.normalization_results = results
            logger.info(
                f"Normalization completed: {normalization_method} + {batch_correction if batch_correction else 'no batch correction'}"
            )

            return results

        except Exception as e:
            logger.error(f"Failed to normalize data: {str(e)}")
            raise

    def _apply_transformation(
        self, expression_data: pd.DataFrame, method: str, **kwargs
    ) -> pd.DataFrame:
        """
        Apply data transformation.

        Args:
            expression_data: Expression data matrix
            method: Transformation method
            **kwargs: Additional parameters

        Returns:
            Transformed data
        """
        try:
            # Filter kwargs to only pass transformation-specific ones
            transform_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k
                in [
                    "offset",
                    "scale",
                    "quantile",
                    "robust",
                    "clip_values",
                    "clip_min",
                    "clip_max",
                    "pseudocount",
                    "prior_count",
                ]
            }
            transformed_data = self.transformer.transform_data(
                expression_data, method, **transform_kwargs
            )
            return transformed_data
        except Exception as e:
            logger.error(f"Failed to apply transformation {method}: {str(e)}")
            raise

    def _apply_batch_correction(
        self,
        expression_data: pd.DataFrame,
        batch_info: pd.Series,
        method: str,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Apply batch correction.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information
            method: Batch correction method
            **kwargs: Additional parameters

        Returns:
            Batch-corrected data
        """
        try:
            # First detect batch effects
            batch_effects = self.batch_corrector.detect_batch_effects(
                expression_data, batch_info
            )

            # Apply correction
            corrected_data = self.batch_corrector.correct_batch_effects(
                expression_data, batch_info, method, **kwargs
            )

            # Evaluate correction effectiveness
            evaluation = self.batch_corrector.evaluate_correction(
                expression_data, corrected_data, batch_info
            )

            return corrected_data
        except Exception as e:
            logger.error(f"Failed to apply batch correction {method}: {str(e)}")
            raise

    def _apply_final_normalization(
        self, expression_data: pd.DataFrame, final_normalization: str = "none", **kwargs
    ) -> pd.DataFrame:
        """
        Apply final normalization step.

        Args:
            expression_data: Expression data matrix
            final_normalization: Final normalization method
            **kwargs: Additional parameters

        Returns:
            Final normalized data
        """
        if final_normalization == "none":
            return expression_data.copy()

        try:
            if final_normalization == "zscore":
                # Z-score normalization per gene
                scaler = StandardScaler()
                normalized_data = pd.DataFrame(
                    scaler.fit_transform(expression_data.T).T,
                    index=expression_data.index,
                    columns=expression_data.columns,
                )
            elif final_normalization == "robust_zscore":
                # Robust Z-score normalization per gene
                scaler = RobustScaler()
                normalized_data = pd.DataFrame(
                    scaler.fit_transform(expression_data.T).T,
                    index=expression_data.index,
                    columns=expression_data.columns,
                )
            elif final_normalization == "quantile":
                # Quantile normalization
                normalized_data = self._quantile_normalize(expression_data)
            elif final_normalization == "median_ratio":
                # Median ratio normalization
                normalized_data = self._median_ratio_normalize(expression_data)
            else:
                logger.warning(
                    f"Unknown final normalization method: {final_normalization}"
                )
                return expression_data.copy()

            return normalized_data

        except Exception as e:
            logger.error(
                f"Failed to apply final normalization {final_normalization}: {str(e)}"
            )
            return expression_data.copy()

    def _quantile_normalize(self, expression_data: pd.DataFrame) -> pd.DataFrame:
        """
        Perform quantile normalization.

        Args:
            expression_data: Expression data matrix

        Returns:
            Quantile normalized data
        """
        from scipy import stats

        arr = np.asarray(expression_data, dtype=float)
        n_genes, n_samples = arr.shape
        if n_genes == 0 or n_samples == 0:
            return expression_data.copy()

        sorted_data = np.sort(arr, axis=0)
        mean_sorted = np.mean(sorted_data, axis=1)
        ranks = np.zeros_like(arr, dtype=int)
        for j in range(n_samples):
            ranks[:, j] = stats.rankdata(arr[:, j], method="ordinal").astype(int) - 1
        idx = np.clip(ranks, 0, mean_sorted.shape[0] - 1)
        normalized_data = mean_sorted[idx]

        return pd.DataFrame(
            normalized_data,
            index=expression_data.index,
            columns=expression_data.columns,
        )

    def _median_ratio_normalize(self, expression_data: pd.DataFrame) -> pd.DataFrame:
        """
        Perform median ratio normalization.

        Args:
            expression_data: Expression data matrix

        Returns:
            Median ratio normalized data
        """
        # Calculate geometric mean per gene
        geometric_means = np.exp(
            np.mean(np.log(expression_data.values + 1e-10), axis=1)
        )

        # Calculate size factors
        size_factors = np.median(
            expression_data.values / geometric_means[:, np.newaxis], axis=0
        )

        # Apply normalization
        normalized_data = expression_data.values / size_factors[np.newaxis, :]

        return pd.DataFrame(
            normalized_data,
            index=expression_data.index,
            columns=expression_data.columns,
        )

    def _generate_normalization_summary(
        self, results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate normalization summary.

        Args:
            results: Normalization results

        Returns:
            Normalization summary
        """
        summary = {
            "status": "completed",
            "steps_applied": [],
            "data_statistics": {},
            "improvements": {},
        }

        # Track steps applied
        if "transformation_params" in results:
            summary["steps_applied"].append(
                f"Transformation: {results['normalization_method']}"
            )

        if "batch_correction_params" in results:
            summary["steps_applied"].append(
                f"Batch correction: {results['batch_correction']}"
            )

        # Calculate statistics for each step
        original_data = results["original_data"]
        final_data = results["final_data"]

        summary["data_statistics"] = {
            "original": {
                "mean": float(original_data.mean().mean()),
                "std": float(original_data.std().mean()),
                "min": float(original_data.min().min()),
                "max": float(original_data.max().max()),
                "median": float(original_data.median().median()),
            },
            "final": {
                "mean": float(final_data.mean().mean()),
                "std": float(final_data.std().mean()),
                "min": float(final_data.min().min()),
                "max": float(final_data.max().max()),
                "median": float(final_data.median().median()),
            },
        }

        # Calculate improvements
        if "transformed_data" in results:
            transformed_data = results["transformed_data"]
            summary["improvements"]["transformation"] = {
                "mean": float(transformed_data.mean().mean()),
                "std": float(transformed_data.std().mean()),
                "skewness": float(transformed_data.skew(axis=1).mean()),
                "kurtosis": float(transformed_data.kurtosis(axis=1).mean()),
            }

        if "corrected_data" in results and "transformed_data" in results:
            corrected_data = results["corrected_data"]
            transformed_data = results["transformed_data"]

            # Calculate batch effect reduction
            if "batch_correction_params" in results:
                summary["improvements"]["batch_correction"] = {
                    "mean": float(corrected_data.mean().mean()),
                    "std": float(corrected_data.std().mean()),
                    "batch_effect_reduction": "Applied",  # Would need batch info for quantitative measure
                }

        return summary

    def _generate_comparison_plots(
        self,
        results: Dict[str, Any],
        labels: Optional[pd.Series] = None,
        batch_info: Optional[pd.Series] = None,
    ) -> Dict[str, Any]:
        """
        Generate comparison plots for normalization steps.

        Args:
            results: Normalization results
            labels: Sample labels (optional)
            batch_info: Batch information (optional)

        Returns:
            Dictionary of plot objects
        """
        plots = {}

        try:
            import plotly.express as px
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # Box plots comparing distributions
            if "original_data" in results and "final_data" in results:
                original_data = results["original_data"]
                final_data = results["final_data"]

                # Sample box plots
                fig_box = make_subplots(
                    rows=1,
                    cols=2,
                    subplot_titles=("Original Data", "Normalized Data"),
                    specs=[[{"type": "box"}, {"type": "box"}]],
                )

                # Original data box plot
                for i, sample in enumerate(
                    original_data.columns[: min(20, len(original_data.columns))]
                ):
                    fig_box.add_trace(
                        go.Box(y=original_data[sample], name=sample, showlegend=False),
                        row=1,
                        col=1,
                    )

                # Final data box plot
                for i, sample in enumerate(
                    final_data.columns[: min(20, len(final_data.columns))]
                ):
                    fig_box.add_trace(
                        go.Box(y=final_data[sample], name=sample, showlegend=False),
                        row=1,
                        col=2,
                    )

                fig_box.update_layout(title="Sample Expression Distributions")
                plots["sample_distributions"] = fig_box

            # PCA plots comparing before/after
            if "original_data" in results and "final_data" in results:
                original_data = results["original_data"]
                final_data = results["final_data"]

                # PCA for original data
                if original_data.shape[1] > 2:
                    pca_original = PCA(n_components=2)
                    pca_original_result = pca_original.fit_transform(original_data.T)

                    # PCA for final data
                    pca_final = PCA(n_components=2)
                    pca_final_result = pca_final.fit_transform(final_data.T)

                    # Create comparison plot
                    fig_pca = make_subplots(
                        rows=1,
                        cols=2,
                        subplot_titles=("Original Data PCA", "Normalized Data PCA"),
                        specs=[[{"type": "scatter"}, {"type": "scatter"}]],
                    )

                    # Color by labels or batch
                    color_col = None
                    if labels is not None:
                        color_col = labels.values
                    elif batch_info is not None:
                        color_col = batch_info.values

                    # Original PCA
                    fig_pca.add_trace(
                        go.Scatter(
                            x=pca_original_result[:, 0],
                            y=pca_original_result[:, 1],
                            mode="markers",
                            marker=dict(color=color_col),
                            name="Original",
                            showlegend=False,
                        ),
                        row=1,
                        col=1,
                    )

                    # Final PCA
                    fig_pca.add_trace(
                        go.Scatter(
                            x=pca_final_result[:, 0],
                            y=pca_final_result[:, 1],
                            mode="markers",
                            marker=dict(color=color_col),
                            name="Normalized",
                            showlegend=False,
                        ),
                        row=1,
                        col=2,
                    )

                    fig_pca.update_layout(title="PCA Comparison")
                    plots["pca_comparison"] = fig_pca

            # Distribution comparison
            if "original_data" in results and "final_data" in results:
                original_data = results["original_data"]
                final_data = results["final_data"]

                # Flatten data for histogram
                original_flat = original_data.values.flatten()
                final_flat = final_data.values.flatten()

                fig_dist = make_subplots(
                    rows=1,
                    cols=2,
                    subplot_titles=("Original Distribution", "Normalized Distribution"),
                    specs=[[{"type": "histogram"}, {"type": "histogram"}]],
                )

                fig_dist.add_trace(
                    go.Histogram(x=original_flat, name="Original", showlegend=False),
                    row=1,
                    col=1,
                )

                fig_dist.add_trace(
                    go.Histogram(x=final_flat, name="Normalized", showlegend=False),
                    row=1,
                    col=2,
                )

                fig_dist.update_layout(title="Expression Distribution Comparison")
                plots["distribution_comparison"] = fig_dist

        except ImportError:
            logger.warning("Plotly not available, skipping comparison plots")

        return plots

    def get_normalization_summary(self) -> Dict[str, Any]:
        """
        Get normalization summary.

        Returns:
            Normalization summary dictionary
        """
        if not self.normalization_results:
            return {"status": "No normalization performed"}

        return self.normalization_results.get("summary", {"status": "unknown"})

    def save_normalized_data(self, output_path: str, format: str = "tsv") -> str:
        """
        Save normalized data to file.

        Args:
            output_path: Output file path
            format: Output format

        Returns:
            Path to saved file
        """
        if (
            not self.normalization_results
            or "final_data" not in self.normalization_results
        ):
            raise ValueError("No normalized data to save")

        try:
            final_data = self.normalization_results["final_data"]

            if format.lower() == "tsv":
                final_data.to_csv(output_path, sep="\t")
            elif format.lower() == "csv":
                final_data.to_csv(output_path)
            elif format.lower() == "h5":
                final_data.to_hdf(output_path, key="normalized_data")
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Normalized data saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save normalized data: {str(e)}")
            raise

    def save_normalization_report(self, output_path: str, format: str = "html") -> str:
        """
        Save normalization report.

        Args:
            output_path: Output file path
            format: Output format

        Returns:
            Path to saved report
        """
        if not self.normalization_results:
            raise ValueError("No normalization results to save")

        try:
            if format.lower() == "html":
                # Generate HTML report
                html_content = self._generate_html_report()
                with open(output_path, "w") as f:
                    f.write(html_content)
            elif format.lower() == "json":
                # Save as JSON
                import json

                with open(output_path, "w") as f:
                    json.dump(self.normalization_results, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Normalization report saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save normalization report: {str(e)}")
            raise

    def _generate_html_report(self) -> str:
        """Generate HTML normalization report."""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Normalization Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .section {{ margin: 20px 0; padding: 10px; border: 1px solid #ddd; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Normalization Report</h1>
            <div class="section">
                <h2>Steps Applied</h2>
                <ul>{steps}</ul>
            </div>
            <div class="section">
                <h2>Data Statistics</h2>
                <table>
                    <tr><th>Metric</th><th>Original</th><th>Final</th></tr>
                    {statistics}
                </table>
            </div>
            <div class="section">
                <h2>Improvements</h2>
                {improvements}
            </div>
        </body>
        </html>
        """

        summary = self.normalization_results.get("summary", {})

        # Format steps
        steps_html = "".join(
            [f"<li>{step}</li>" for step in summary.get("steps_applied", [])]
        )

        # Format statistics
        stats = summary.get("data_statistics", {})
        statistics_html = ""
        if "original" in stats and "final" in stats:
            for metric in ["mean", "std", "min", "max", "median"]:
                if metric in stats["original"] and metric in stats["final"]:
                    statistics_html += f"<tr><td>{metric}</td><td>{stats['original'][metric]:.4f}</td><td>{stats['final'][metric]:.4f}</td></tr>"

        # Format improvements
        improvements = summary.get("improvements", {})
        improvements_html = ""
        for step, metrics in improvements.items():
            improvements_html += f"<h3>{step.title()}</h3><ul>"
            for metric, value in metrics.items():
                if isinstance(value, float):
                    improvements_html += f"<li>{metric}: {value:.4f}</li>"
                else:
                    improvements_html += f"<li>{metric}: {value}</li>"
            improvements_html += "</ul>"

        return html_template.format(
            steps=steps_html, statistics=statistics_html, improvements=improvements_html
        )
