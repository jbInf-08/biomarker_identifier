"""
Quality control utilities for biomarker pipeline.
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
from plotly.subplots import make_subplots
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.preprocessing import StandardScaler

from ..utils.adaptive_parameters import AdaptiveParameters
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class QualityControl:
    """
    Handles quality control analysis for expression data.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the QualityControl module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.qc_results = {}
        self.plots = {}

    def perform_qc_analysis(
        self,
        expression_data: pd.DataFrame,
        labels: Optional[pd.Series] = None,
        batch_info: Optional[pd.Series] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Perform comprehensive quality control analysis.

        Args:
            expression_data: Expression data matrix
            labels: Sample labels (optional)
            batch_info: Batch information (optional)
            **kwargs: Additional parameters

        Returns:
            QC analysis results
        """
        try:
            results = {}

            # Basic QC metrics
            basic_qc = self._calculate_basic_qc_metrics(expression_data)
            results["basic_qc"] = basic_qc

            # Sample-level QC
            sample_qc = self._calculate_sample_qc_metrics(expression_data)
            results["sample_qc"] = sample_qc

            # Gene-level QC
            gene_qc = self._calculate_gene_qc_metrics(expression_data)
            results["gene_qc"] = gene_qc

            # Distribution analysis
            distribution_qc = self._analyze_distributions(expression_data)
            results["distribution_qc"] = distribution_qc

            # Dimensionality reduction (adaptive based on dataset size)
            qc_params = AdaptiveParameters.get_qc_parameters(
                expression_data.shape[1], expression_data.shape[0]
            )
            if expression_data.shape[1] >= qc_params["min_samples_for_pca"]:
                dim_reduction = self._perform_dimensionality_reduction(
                    expression_data, labels, batch_info, qc_params
                )
                results["dimensionality_reduction"] = dim_reduction

            # Outlier detection
            outliers = self._detect_outliers(expression_data, sample_qc, gene_qc)
            results["outliers"] = outliers

            # Generate QC plots
            plots = self._generate_qc_plots(
                expression_data, labels, batch_info, results
            )
            results["plots"] = plots

            # QC summary
            qc_summary = self._generate_qc_summary(results)
            results["summary"] = qc_summary

            self.qc_results = results
            logger.info("QC analysis completed successfully")

            return results

        except Exception as e:
            logger.error(f"Failed to perform QC analysis: {str(e)}")
            raise

    def _calculate_basic_qc_metrics(
        self, expression_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Calculate basic QC metrics.

        Args:
            expression_data: Expression data matrix

        Returns:
            Basic QC metrics
        """
        metrics = {
            "n_genes": expression_data.shape[0],
            "n_samples": expression_data.shape[1],
            "total_values": expression_data.size,
            "missing_values": expression_data.isnull().sum().sum(),
            "missing_ratio": expression_data.isnull().sum().sum()
            / expression_data.size,
            "zero_values": (expression_data == 0).sum().sum(),
            "zero_ratio": (expression_data == 0).sum().sum() / expression_data.size,
            "infinite_values": np.isinf(expression_data).sum().sum(),
            "negative_values": (expression_data < 0).sum().sum(),
            "value_range": {
                "min": float(expression_data.min().min()),
                "max": float(expression_data.max().max()),
                "mean": float(expression_data.mean().mean()),
                "median": float(expression_data.median().median()),
                "std": float(expression_data.std().mean()),
            },
        }

        return metrics

    def _calculate_sample_qc_metrics(
        self, expression_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate sample-level QC metrics.

        Args:
            expression_data: Expression data matrix

        Returns:
            Sample QC metrics DataFrame
        """
        sample_metrics = pd.DataFrame(index=expression_data.columns)

        # Library size (sum of expression)
        sample_metrics["library_size"] = expression_data.sum()

        # Number of detected genes (non-zero)
        sample_metrics["detected_genes"] = (expression_data > 0).sum()

        # Detection rate
        sample_metrics["detection_rate"] = (
            sample_metrics["detected_genes"] / expression_data.shape[0]
        )

        # Mean expression
        sample_metrics["mean_expression"] = expression_data.mean()

        # Median expression
        sample_metrics["median_expression"] = expression_data.median()

        # Standard deviation
        sample_metrics["std_expression"] = expression_data.std()

        # Coefficient of variation
        sample_metrics["cv_expression"] = (
            sample_metrics["std_expression"] / sample_metrics["mean_expression"]
        )

        # Missing values
        sample_metrics["missing_values"] = expression_data.isnull().sum()

        # Zero values
        sample_metrics["zero_values"] = (expression_data == 0).sum()

        # Zero ratio
        sample_metrics["zero_ratio"] = (
            sample_metrics["zero_values"] / expression_data.shape[0]
        )

        return sample_metrics

    def _calculate_gene_qc_metrics(self, expression_data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate gene-level QC metrics.

        Args:
            expression_data: Expression data matrix

        Returns:
            Gene QC metrics DataFrame
        """
        gene_metrics = pd.DataFrame(index=expression_data.index)

        # Mean expression per gene
        gene_metrics["mean_expression"] = expression_data.mean(axis=1)

        # Median expression per gene
        gene_metrics["median_expression"] = expression_data.median(axis=1)

        # Standard deviation per gene
        gene_metrics["std_expression"] = expression_data.std(axis=1)

        # Variance per gene
        gene_metrics["variance"] = expression_data.var(axis=1)

        # Coefficient of variation per gene
        gene_metrics["cv_expression"] = (
            gene_metrics["std_expression"] / gene_metrics["mean_expression"]
        )

        # Number of samples with non-zero expression
        gene_metrics["detected_samples"] = (expression_data > 0).sum(axis=1)

        # Detection rate per gene
        gene_metrics["detection_rate"] = (
            gene_metrics["detected_samples"] / expression_data.shape[1]
        )

        # Missing values per gene
        gene_metrics["missing_values"] = expression_data.isnull().sum(axis=1)

        # Zero values per gene
        gene_metrics["zero_values"] = (expression_data == 0).sum(axis=1)

        # Zero ratio per gene
        gene_metrics["zero_ratio"] = (
            gene_metrics["zero_values"] / expression_data.shape[1]
        )

        return gene_metrics

    def _analyze_distributions(self, expression_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Analyze expression distributions.

        Args:
            expression_data: Expression data matrix

        Returns:
            Distribution analysis results
        """
        # Sample-level distributions
        sample_distributions = {
            "library_size": {
                "mean": float(expression_data.sum().mean()),
                "std": float(expression_data.sum().std()),
                "median": float(expression_data.sum().median()),
                "q25": float(expression_data.sum().quantile(0.25)),
                "q75": float(expression_data.sum().quantile(0.75)),
                "min": float(expression_data.sum().min()),
                "max": float(expression_data.sum().max()),
            },
            "detection_rate": {
                "mean": float(
                    (expression_data > 0).sum(axis=0).mean()
                    / max(expression_data.shape[0], 1)
                ),
                "std": float(
                    (expression_data > 0).sum(axis=0).std()
                    / max(expression_data.shape[0], 1)
                ),
                "median": float(
                    (expression_data > 0).sum(axis=0).median()
                    / max(expression_data.shape[0], 1)
                ),
            },
        }

        # Gene-level distributions
        gene_distributions = {
            "mean_expression": {
                "mean": float(expression_data.mean(axis=1).mean()),
                "std": float(expression_data.mean(axis=1).std()),
                "median": float(expression_data.mean(axis=1).median()),
                "q25": float(expression_data.mean(axis=1).quantile(0.25)),
                "q75": float(expression_data.mean(axis=1).quantile(0.75)),
            },
            "variance": {
                "mean": float(expression_data.var(axis=1).mean()),
                "std": float(expression_data.var(axis=1).std()),
                "median": float(expression_data.var(axis=1).median()),
            },
            "detection_rate": {
                "mean": float(
                    (expression_data > 0).sum(axis=1).mean()
                    / max(expression_data.shape[1], 1)
                ),
                "std": float(
                    (expression_data > 0).sum(axis=1).std()
                    / max(expression_data.shape[1], 1)
                ),
                "median": float(
                    (expression_data > 0).sum(axis=1).median()
                    / max(expression_data.shape[1], 1)
                ),
            },
        }

        return {
            "sample_distributions": sample_distributions,
            "gene_distributions": gene_distributions,
        }

    def _perform_dimensionality_reduction(
        self,
        expression_data: pd.DataFrame,
        labels: Optional[pd.Series] = None,
        batch_info: Optional[pd.Series] = None,
        qc_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Perform dimensionality reduction for visualization.

        Args:
            expression_data: Expression data matrix
            labels: Sample labels (optional)
            batch_info: Batch information (optional)
            qc_params: Adaptive QC parameters (optional)

        Returns:
            Dimensionality reduction results
        """
        if qc_params is None:
            qc_params = AdaptiveParameters.get_qc_parameters(
                expression_data.shape[1], expression_data.shape[0]
            )

        # Standardize data
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(expression_data.T)

        results = {}

        # PCA (adaptive components)
        n_components = qc_params.get(
            "pca_components", min(10, scaled_data.shape[0], scaled_data.shape[1])
        )
        if n_components > 0 and scaled_data.shape[0] >= qc_params.get(
            "min_samples_for_pca", 2
        ):
            try:
                # Ensure n_components doesn't exceed data dimensions
                n_components = min(
                    n_components, scaled_data.shape[0], scaled_data.shape[1]
                )
                if n_components > 0:
                    pca = PCA(n_components=n_components)
                    pca_result = pca.fit_transform(scaled_data)

                    results["pca"] = {
                        "components": pca_result,
                        "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
                        "cumulative_variance_ratio": np.cumsum(
                            pca.explained_variance_ratio_
                        ).tolist(),
                        "n_components": pca.n_components_,
                    }
            except Exception as e:
                logger.warning(f"PCA failed: {str(e)}")

        # t-SNE (if enabled and enough samples)
        if qc_params.get("tsne_enabled", False) and scaled_data.shape[0] >= 4:
            try:
                perplexity = qc_params.get("tsne_perplexity")
                if perplexity is None:
                    perplexity = min(30, max(3, scaled_data.shape[0] - 1))
                # Ensure perplexity is valid
                perplexity = min(perplexity, scaled_data.shape[0] - 1)
                if perplexity >= 1:
                    tsne = TSNE(n_components=2, random_state=42, perplexity=perplexity)
                    tsne_result = tsne.fit_transform(scaled_data)
                    results["tsne"] = {"components": tsne_result, "n_components": 2}
            except Exception as e:
                logger.warning(f"t-SNE failed: {str(e)}")

        return results

    def _detect_outliers(
        self,
        expression_data: pd.DataFrame,
        sample_qc: pd.DataFrame,
        gene_qc: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Detect outliers in samples and genes.

        Args:
            expression_data: Expression data matrix
            sample_qc: Sample QC metrics
            gene_qc: Gene QC metrics

        Returns:
            Outlier detection results
        """
        outliers = {"samples": {}, "genes": {}}

        # Sample outliers
        for metric in ["library_size", "detection_rate", "mean_expression"]:
            if metric in sample_qc.columns:
                values = sample_qc[metric]
                q1 = values.quantile(0.25)
                q3 = values.quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                outlier_samples = values[
                    (values < lower_bound) | (values > upper_bound)
                ]
                outliers["samples"][metric] = {
                    "outlier_samples": outlier_samples.index.tolist(),
                    "n_outliers": len(outlier_samples),
                    "thresholds": {
                        "lower": float(lower_bound),
                        "upper": float(upper_bound),
                    },
                }

        # Gene outliers
        for metric in ["mean_expression", "variance", "detection_rate"]:
            if metric in gene_qc.columns:
                values = gene_qc[metric]
                q1 = values.quantile(0.25)
                q3 = values.quantile(0.75)
                iqr = q3 - q1
                lower_bound = q1 - 1.5 * iqr
                upper_bound = q3 + 1.5 * iqr

                outlier_genes = values[(values < lower_bound) | (values > upper_bound)]
                outliers["genes"][metric] = {
                    "outlier_genes": outlier_genes.index.tolist(),
                    "n_outliers": len(outlier_genes),
                    "thresholds": {
                        "lower": float(lower_bound),
                        "upper": float(upper_bound),
                    },
                }

        return outliers

    def _generate_qc_plots(
        self,
        expression_data: pd.DataFrame,
        labels: Optional[pd.Series] = None,
        batch_info: Optional[pd.Series] = None,
        qc_results: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate QC plots.

        Args:
            expression_data: Expression data matrix
            labels: Sample labels (optional)
            batch_info: Batch information (optional)
            qc_results: QC analysis results (optional)

        Returns:
            Dictionary of plot objects
        """
        plots = {}

        # Sample QC plots
        if qc_results and "sample_qc" in qc_results:
            sample_qc = qc_results["sample_qc"]

            if not isinstance(sample_qc, pd.DataFrame):
                sample_qc = None

            # Library size distribution
            if sample_qc is not None and "library_size" in sample_qc.columns:
                fig_lib_size = px.histogram(
                    x=sample_qc["library_size"],
                    title="Library Size Distribution",
                    labels={"x": "Library Size", "y": "Count"},
                )
                plots["library_size_distribution"] = fig_lib_size

            # Detection rate distribution
            if sample_qc is not None and "detection_rate" in sample_qc.columns:
                fig_detection = px.histogram(
                    x=sample_qc["detection_rate"],
                    title="Gene Detection Rate Distribution",
                    labels={"x": "Detection Rate", "y": "Count"},
                )
                plots["detection_rate_distribution"] = fig_detection

        # Gene QC plots
        if qc_results and "gene_qc" in qc_results:
            gene_qc = qc_results["gene_qc"]
            if not isinstance(gene_qc, pd.DataFrame):
                gene_qc = None

            # Mean expression distribution
            if gene_qc is not None and "mean_expression" in gene_qc.columns:
                fig_mean_expr = px.histogram(
                    x=gene_qc["mean_expression"],
                    title="Mean Expression Distribution",
                    labels={"x": "Mean Expression", "y": "Count"},
                )
                plots["mean_expression_distribution"] = fig_mean_expr

            # Variance distribution
            if gene_qc is not None and "variance" in gene_qc.columns:
                fig_variance = px.histogram(
                    x=gene_qc["variance"],
                    title="Expression Variance Distribution",
                    labels={"x": "Variance", "y": "Count"},
                )
                plots["variance_distribution"] = fig_variance

        # PCA plots
        if qc_results and "dimensionality_reduction" in qc_results:
            dim_red = qc_results["dimensionality_reduction"]

            if "pca" in dim_red:
                pca_result = dim_red["pca"]["components"]

                # PCA scatter plot
                if labels is not None:
                    color_col = labels.values
                    color_name = "Class"
                elif batch_info is not None:
                    color_col = batch_info.values
                    color_name = "Batch"
                else:
                    color_col = None
                    color_name = None

                if pca_result.shape[1] >= 2:
                    fig_pca = px.scatter(
                        x=pca_result[:, 0],
                        y=pca_result[:, 1],
                        color=color_col,
                        title="PCA Plot (PC1 vs PC2)",
                        labels={"x": "PC1", "y": "PC2", "color": color_name},
                    )
                else:
                    fig_pca = px.scatter(
                        x=np.arange(pca_result.shape[0]),
                        y=pca_result[:, 0],
                        color=color_col,
                        title="PCA Plot (PC1 only)",
                        labels={"x": "Sample index", "y": "PC1", "color": color_name},
                    )
                plots["pca_plot"] = fig_pca

                # Explained variance plot
                fig_var = px.line(
                    x=list(
                        range(1, len(dim_red["pca"]["explained_variance_ratio"]) + 1)
                    ),
                    y=dim_red["pca"]["explained_variance_ratio"],
                    title="PCA Explained Variance Ratio",
                    labels={
                        "x": "Principal Component",
                        "y": "Explained Variance Ratio",
                    },
                )
                plots["pca_explained_variance"] = fig_var

        # Correlation heatmap (sample correlation) - adaptive
        qc_params = AdaptiveParameters.get_qc_parameters(
            expression_data.shape[1], expression_data.shape[0]
        )
        if (
            qc_params.get("correlation_heatmap", False)
            and expression_data.shape[1] <= 50
        ):
            try:
                corr_matrix = expression_data.T.corr()
                fig_corr = px.imshow(
                    corr_matrix,
                    title="Sample Correlation Heatmap",
                    labels={"x": "Sample", "y": "Sample"},
                )
                plots["sample_correlation"] = fig_corr
            except Exception as e:
                logger.warning(f"Correlation heatmap generation failed: {str(e)}")

        return plots

    def _generate_qc_summary(self, qc_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate QC summary.

        Args:
            qc_results: QC analysis results

        Returns:
            QC summary
        """
        summary = {"status": "passed", "warnings": [], "recommendations": []}

        # Check basic metrics
        if "basic_qc" in qc_results:
            basic_qc = qc_results["basic_qc"]
            missing_ratio = basic_qc.get(
                "missing_ratio",
                basic_qc.get("missing_percentage", 0) / 100.0
                if isinstance(basic_qc.get("missing_percentage"), (int, float))
                else 0,
            )
            zero_ratio = basic_qc.get(
                "zero_ratio",
                basic_qc.get("zero_percentage", 0) / 100.0
                if isinstance(basic_qc.get("zero_percentage"), (int, float))
                else 0,
            )

            # Check missing values
            if missing_ratio > 0.1:
                summary["warnings"].append(
                    f"High missing value ratio: {missing_ratio:.2%}"
                )
                summary["recommendations"].append(
                    "Consider imputation or removal of samples/genes with high missing rates"
                )

            # Check zero inflation
            if zero_ratio > 0.8:
                summary["warnings"].append(
                    f"High zero inflation: {zero_ratio:.2%}"
                )
                summary["recommendations"].append(
                    "Consider zero-inflated models or filtering low-expressed genes"
                )

            # Check negative values
            neg = basic_qc.get("negative_values", 0)
            if neg > 0:
                summary["warnings"].append(
                    f"Negative values detected: {neg}"
                )
                summary["recommendations"].append(
                    "Check data preprocessing and consider log transformation"
                )

        # Check sample QC
        if "sample_qc" in qc_results:
            sample_qc = qc_results["sample_qc"]
            if isinstance(sample_qc, pd.DataFrame) and not sample_qc.empty:
                if "library_size" in sample_qc.columns:
                    lib_size_cv = (
                        sample_qc["library_size"].std()
                        / (sample_qc["library_size"].mean() + 1e-12)
                    )
                    if lib_size_cv > 0.5:
                        summary["warnings"].append(
                            f"High library size variation (CV: {lib_size_cv:.2f})"
                        )
                        summary["recommendations"].append(
                            "Consider library size normalization"
                        )

                if "detection_rate" in sample_qc.columns:
                    det_rate_cv = (
                        sample_qc["detection_rate"].std()
                        / (sample_qc["detection_rate"].mean() + 1e-12)
                    )
                    if det_rate_cv > 0.3:
                        summary["warnings"].append(
                            f"High detection rate variation (CV: {det_rate_cv:.2f})"
                        )
                        summary["recommendations"].append(
                            "Check for technical artifacts or batch effects"
                        )

        # Check gene QC
        if "gene_qc" in qc_results:
            gene_qc = qc_results["gene_qc"]
            if isinstance(gene_qc, pd.DataFrame) and not gene_qc.empty:
                if "variance" in gene_qc.columns:
                    low_var_genes = (gene_qc["variance"] == 0).sum()
                    if low_var_genes > 0:
                        summary["warnings"].append(
                            f"{low_var_genes} genes with zero variance"
                        )
                        summary["recommendations"].append(
                            "Remove genes with zero variance before analysis"
                        )

                if "detection_rate" in gene_qc.columns:
                    low_det_genes = (gene_qc["detection_rate"] < 0.1).sum()
                    if low_det_genes > 0:
                        summary["warnings"].append(
                            f"{low_det_genes} genes detected in <10% of samples"
                        )
                        summary["recommendations"].append(
                            "Consider filtering low-detection genes"
                        )

        # Check outliers
        if "outliers" in qc_results:
            outliers = qc_results["outliers"]
            samples_block = outliers.get("samples", {})
            if isinstance(samples_block, dict) and samples_block:
                total_sample_outliers = sum(
                    len(samples_block[m].get("outlier_samples", []))
                    for m in samples_block
                    if isinstance(samples_block.get(m), dict)
                )
                if total_sample_outliers > 0:
                    summary["warnings"].append(
                        f"{total_sample_outliers} sample outliers detected"
                    )
                    summary["recommendations"].append(
                        "Review outlier samples for technical issues"
                    )

        # Update status
        if summary["warnings"]:
            summary["status"] = "warning"

        return summary

    def filter_data(
        self,
        expression_data: pd.DataFrame,
        min_detection_rate: float = 0.1,
        min_variance: float = 0.0,
        max_missing_ratio: float = 0.5,
        **kwargs,
    ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Filter expression data based on QC metrics.

        Args:
            expression_data: Expression data matrix
            min_detection_rate: Minimum detection rate for genes
            min_variance: Minimum variance for genes
            max_missing_ratio: Maximum missing value ratio
            **kwargs: Additional filtering parameters

        Returns:
            Filtered expression data and filtering summary
        """
        original_shape = expression_data.shape
        filtered_data = expression_data.copy()

        # Calculate gene QC metrics
        gene_qc = self._calculate_gene_qc_metrics(filtered_data)

        # Filter by detection rate
        if min_detection_rate > 0:
            keep_genes = gene_qc["detection_rate"] >= min_detection_rate
            filtered_data = filtered_data[keep_genes]
            logger.info(
                f"Filtered by detection rate: {keep_genes.sum()}/{len(keep_genes)} genes kept"
            )

        # Filter by variance
        if min_variance > 0:
            keep_genes = gene_qc.loc[filtered_data.index, "variance"] >= min_variance
            filtered_data = filtered_data[keep_genes]
            logger.info(
                f"Filtered by variance: {keep_genes.sum()}/{len(keep_genes)} genes kept"
            )

        # Filter by missing values
        if max_missing_ratio < 1.0:
            missing_ratio = filtered_data.isnull().sum(axis=1) / filtered_data.shape[1]
            keep_genes = missing_ratio <= max_missing_ratio
            filtered_data = filtered_data[keep_genes]
            logger.info(
                f"Filtered by missing values: {keep_genes.sum()}/{len(keep_genes)} genes kept"
            )

        # Generate filtering summary
        filtering_summary = {
            "original_shape": original_shape,
            "filtered_shape": filtered_data.shape,
            "genes_removed": original_shape[0] - filtered_data.shape[0],
            "samples_removed": original_shape[1] - filtered_data.shape[1],
            "filtering_criteria": {
                "min_detection_rate": min_detection_rate,
                "min_variance": min_variance,
                "max_missing_ratio": max_missing_ratio,
            },
        }

        logger.info(
            f"Data filtering completed: {filtered_data.shape[0]} genes, {filtered_data.shape[1]} samples"
        )
        return filtered_data, filtering_summary

    def get_qc_summary(self) -> Dict[str, Any]:
        """
        Get QC summary.

        Returns:
            QC summary dictionary
        """
        if not self.qc_results:
            return {"status": "No QC analysis performed"}

        return self.qc_results.get("summary", {"status": "unknown"})

    def save_qc_report(self, output_path: str, format: str = "html") -> str:
        """
        Save QC report.

        Args:
            output_path: Output file path
            format: Output format

        Returns:
            Path to saved report
        """
        if not self.qc_results:
            raise ValueError("No QC results to save")

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
                    json.dump(self.qc_results, f, indent=2, default=str)
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"QC report saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save QC report: {str(e)}")
            raise

    def _generate_html_report(self) -> str:
        """Generate HTML QC report."""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Quality Control Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .section {{ margin: 20px 0; padding: 10px; border: 1px solid #ddd; }}
                .warning {{ background-color: #fff3cd; border-color: #ffeaa7; }}
                .error {{ background-color: #f8d7da; border-color: #f5c6cb; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>Quality Control Report</h1>
            <div class="section">
                <h2>Summary</h2>
                <p><strong>Status:</strong> {status}</p>
                <p><strong>Warnings:</strong> {n_warnings}</p>
                <p><strong>Recommendations:</strong> {n_recommendations}</p>
            </div>
            <div class="section">
                <h2>Basic Metrics</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    {basic_metrics}
                </table>
            </div>
            <div class="section">
                <h2>Warnings</h2>
                <ul>{warnings}</ul>
            </div>
            <div class="section">
                <h2>Recommendations</h2>
                <ul>{recommendations}</ul>
            </div>
        </body>
        </html>
        """

        summary = self.qc_results.get("summary", {})
        basic_qc = self.qc_results.get("basic_qc", {})

        # Format basic metrics
        basic_metrics_html = ""
        for key, value in basic_qc.items():
            if isinstance(value, dict):
                for subkey, subvalue in value.items():
                    basic_metrics_html += (
                        f"<tr><td>{key}.{subkey}</td><td>{subvalue}</td></tr>"
                    )
            else:
                basic_metrics_html += f"<tr><td>{key}</td><td>{value}</td></tr>"

        # Format warnings and recommendations
        warnings_html = "".join(
            [f"<li>{warning}</li>" for warning in summary.get("warnings", [])]
        )
        recommendations_html = "".join(
            [f"<li>{rec}</li>" for rec in summary.get("recommendations", [])]
        )

        return html_template.format(
            status=summary.get("status", "unknown"),
            n_warnings=len(summary.get("warnings", [])),
            n_recommendations=len(summary.get("recommendations", [])),
            basic_metrics=basic_metrics_html,
            warnings=warnings_html,
            recommendations=recommendations_html,
        )
