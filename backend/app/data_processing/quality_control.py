"""
Quality control and filtering for expression data.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
from plotly.subplots import make_subplots

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class QualityControl:
    """
    Performs quality control on expression data and generates QC reports.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the quality control module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.qc_results = {}
        self.filtered_data = None

    def calculate_qc_metrics(
        self, expression_data: pd.DataFrame, labels: Optional[pd.DataFrame] = None
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive QC metrics for expression data.

        Args:
            expression_data: Expression data matrix
            labels: Clinical labels (optional)

        Returns:
            QC metrics dictionary
        """
        qc_metrics = {
            "data_summary": {},
            "sample_metrics": {},
            "gene_metrics": {},
            "quality_flags": {},
            "filtering_recommendations": {},
        }

        try:
            # Data summary
            qc_metrics["data_summary"] = {
                "n_genes": expression_data.shape[0],
                "n_samples": expression_data.shape[1],
                "total_values": expression_data.size,
                "missing_values": expression_data.isna().sum().sum(),
                "missing_percentage": (
                    expression_data.isna().sum().sum() / expression_data.size
                )
                * 100,
                "zero_values": (expression_data == 0).sum().sum(),
                "zero_percentage": (
                    (expression_data == 0).sum().sum() / expression_data.size
                )
                * 100,
                "negative_values": (expression_data < 0).sum().sum(),
                "negative_percentage": (
                    (expression_data < 0).sum().sum() / expression_data.size
                )
                * 100,
            }

            # Sample-level metrics
            sample_metrics = {}
            for sample in expression_data.columns:
                sample_data = expression_data[sample]
                sample_metrics[sample] = {
                    "total_genes": len(sample_data),
                    "missing_genes": sample_data.isna().sum(),
                    "missing_percentage": (sample_data.isna().sum() / len(sample_data))
                    * 100,
                    "zero_genes": (sample_data == 0).sum(),
                    "zero_percentage": ((sample_data == 0).sum() / len(sample_data))
                    * 100,
                    "mean_expression": sample_data.mean(),
                    "median_expression": sample_data.median(),
                    "std_expression": sample_data.std(),
                    "library_size": sample_data.sum(),
                    "log_library_size": np.log2(sample_data.sum() + 1),
                }

            qc_metrics["sample_metrics"] = sample_metrics

            # Gene-level metrics
            gene_metrics = {}
            for gene in expression_data.index:
                gene_data = expression_data.loc[gene]
                gene_metrics[gene] = {
                    "total_samples": len(gene_data),
                    "missing_samples": gene_data.isna().sum(),
                    "missing_percentage": (gene_data.isna().sum() / len(gene_data))
                    * 100,
                    "zero_samples": (gene_data == 0).sum(),
                    "zero_percentage": ((gene_data == 0).sum() / len(gene_data)) * 100,
                    "mean_expression": gene_data.mean(),
                    "median_expression": gene_data.median(),
                    "std_expression": gene_data.std(),
                    "variance": gene_data.var(),
                    "cv": gene_data.std() / gene_data.mean()
                    if gene_data.mean() > 0
                    else 0,
                }

            qc_metrics["gene_metrics"] = gene_metrics

            # Quality flags
            qc_metrics["quality_flags"] = self._identify_quality_issues(qc_metrics)

            # Filtering recommendations
            qc_metrics[
                "filtering_recommendations"
            ] = self._generate_filtering_recommendations(qc_metrics)

            self.qc_results = qc_metrics
            logger.info("QC metrics calculated successfully")

            return qc_metrics

        except Exception as e:
            logger.error(f"Failed to calculate QC metrics: {str(e)}")
            raise

    def _identify_quality_issues(self, qc_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Identify quality issues in the data.

        Args:
            qc_metrics: QC metrics dictionary

        Returns:
            Quality flags dictionary
        """
        flags = {"sample_issues": [], "gene_issues": [], "data_issues": []}

        # Sample-level issues
        sample_metrics = qc_metrics["sample_metrics"]
        for sample, metrics in sample_metrics.items():
            if metrics["missing_percentage"] > 50:
                flags["sample_issues"].append(
                    f"Sample {sample}: High missing rate ({metrics['missing_percentage']:.1f}%)"
                )

            if metrics["zero_percentage"] > 90:
                flags["sample_issues"].append(
                    f"Sample {sample}: High zero rate ({metrics['zero_percentage']:.1f}%)"
                )

            if metrics["library_size"] < 1000:
                flags["sample_issues"].append(
                    f"Sample {sample}: Low library size ({metrics['library_size']:.0f})"
                )

        # Gene-level issues
        gene_metrics = qc_metrics["gene_metrics"]
        for gene, metrics in gene_metrics.items():
            if metrics["missing_percentage"] > 50:
                flags["gene_issues"].append(
                    f"Gene {gene}: High missing rate ({metrics['missing_percentage']:.1f}%)"
                )

            if metrics["zero_percentage"] > 90:
                flags["gene_issues"].append(
                    f"Gene {gene}: High zero rate ({metrics['zero_percentage']:.1f}%)"
                )

            if metrics["variance"] == 0:
                flags["gene_issues"].append(f"Gene {gene}: Zero variance")

        # Data-level issues
        data_summary = qc_metrics["data_summary"]
        if data_summary["missing_percentage"] > 20:
            flags["data_issues"].append(
                f"High overall missing rate: {data_summary['missing_percentage']:.1f}%"
            )

        if data_summary["zero_percentage"] > 80:
            flags["data_issues"].append(
                f"High overall zero rate: {data_summary['zero_percentage']:.1f}%"
            )

        if data_summary["negative_percentage"] > 5:
            flags["data_issues"].append(
                f"Unexpected negative values: {data_summary['negative_percentage']:.1f}%"
            )

        return flags

    def _generate_filtering_recommendations(
        self, qc_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate filtering recommendations based on QC metrics.

        Args:
            qc_metrics: QC metrics dictionary

        Returns:
            Filtering recommendations dictionary
        """
        recommendations = {"sample_filters": {}, "gene_filters": {}, "thresholds": {}}

        # Sample filtering recommendations
        sample_metrics = qc_metrics["sample_metrics"]
        missing_rates = [
            metrics["missing_percentage"] for metrics in sample_metrics.values()
        ]
        zero_rates = [metrics["zero_percentage"] for metrics in sample_metrics.values()]
        library_sizes = [metrics["library_size"] for metrics in sample_metrics.values()]

        recommendations["sample_filters"] = {
            "max_missing_rate": min(50, np.percentile(missing_rates, 95)),
            "max_zero_rate": min(90, np.percentile(zero_rates, 95)),
            "min_library_size": max(1000, np.percentile(library_sizes, 5)),
        }

        # Gene filtering recommendations
        gene_metrics = qc_metrics["gene_metrics"]
        gene_missing_rates = [
            metrics["missing_percentage"] for metrics in gene_metrics.values()
        ]
        gene_zero_rates = [
            metrics["zero_percentage"] for metrics in gene_metrics.values()
        ]
        gene_variances = [metrics["variance"] for metrics in gene_metrics.values()]

        recommendations["gene_filters"] = {
            "max_missing_rate": min(50, np.percentile(gene_missing_rates, 95)),
            "max_zero_rate": min(90, np.percentile(gene_zero_rates, 95)),
            "min_variance": np.percentile(gene_variances, 10),
        }

        # Suggested thresholds
        recommendations["thresholds"] = {
            "min_genes_per_sample": max(
                1000, qc_metrics["data_summary"]["n_genes"] * 0.1
            ),
            "min_samples_per_gene": max(
                5, qc_metrics["data_summary"]["n_samples"] * 0.1
            ),
            "min_variance_genes": min(
                10000, qc_metrics["data_summary"]["n_genes"] * 0.8
            ),
        }

        return recommendations

    def filter_data(
        self,
        expression_data: pd.DataFrame,
        labels: Optional[pd.DataFrame] = None,
        sample_filters: Optional[Dict[str, Any]] = None,
        gene_filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Filter expression data based on QC metrics.

        Args:
            expression_data: Expression data matrix
            labels: Clinical labels (optional)
            sample_filters: Sample filtering criteria
            gene_filters: Gene filtering criteria

        Returns:
            Tuple of (filtered_expression, filtered_labels)
        """
        try:
            # Use default filters if not provided
            if sample_filters is None:
                sample_filters = {
                    "max_missing_rate": 50,
                    "max_zero_rate": 90,
                    "min_library_size": 1000,
                }

            if gene_filters is None:
                gene_filters = {
                    "max_missing_rate": 50,
                    "max_zero_rate": 90,
                    "min_variance": 0,
                }

            # Calculate QC metrics if not already done
            if not self.qc_results:
                self.calculate_qc_metrics(expression_data, labels)

            # Filter samples
            sample_metrics = self.qc_results["sample_metrics"]
            good_samples = []

            for sample in expression_data.columns:
                metrics = sample_metrics[sample]
                if (
                    metrics["missing_percentage"] <= sample_filters["max_missing_rate"]
                    and metrics["zero_percentage"] <= sample_filters["max_zero_rate"]
                    and metrics["library_size"] >= sample_filters["min_library_size"]
                ):
                    good_samples.append(sample)

            # Filter genes
            gene_metrics = self.qc_results["gene_metrics"]
            good_genes = []

            for gene in expression_data.index:
                metrics = gene_metrics[gene]
                if (
                    metrics["missing_percentage"] <= gene_filters["max_missing_rate"]
                    and metrics["zero_percentage"] <= gene_filters["max_zero_rate"]
                    and metrics["variance"] >= gene_filters["min_variance"]
                ):
                    good_genes.append(gene)

            # Apply filters
            filtered_expr = expression_data.loc[good_genes, good_samples]

            # Filter labels if provided
            filtered_labels = None
            if labels is not None:
                filtered_labels = labels.loc[good_samples]

            # Store filtered data
            self.filtered_data = {
                "expression": filtered_expr,
                "labels": filtered_labels,
                "filtering_summary": {
                    "original_genes": expression_data.shape[0],
                    "filtered_genes": filtered_expr.shape[0],
                    "genes_removed": expression_data.shape[0] - filtered_expr.shape[0],
                    "original_samples": expression_data.shape[1],
                    "filtered_samples": filtered_expr.shape[1],
                    "samples_removed": expression_data.shape[1]
                    - filtered_expr.shape[1],
                },
            }

            logger.info(
                f"Data filtering completed: {filtered_expr.shape[0]} genes, {filtered_expr.shape[1]} samples"
            )

            return filtered_expr, filtered_labels

        except Exception as e:
            logger.error(f"Failed to filter data: {str(e)}")
            raise

    def filter_low_quality_samples(
        self,
        expression_data: pd.DataFrame,
        min_library_size: float = 1000.0,
        min_detected_genes: int = 100,
        labels: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Remove samples failing library size or detection thresholds."""
        self.calculate_qc_metrics(expression_data, labels)
        keep_cols = []
        for col in expression_data.columns:
            s = expression_data[col]
            lib = float(s.sum(skipna=True))
            detected = int((s > 0).sum())
            if lib >= min_library_size and detected >= min_detected_genes:
                keep_cols.append(col)
        return expression_data[keep_cols]

    def filter_low_quality_genes(
        self,
        expression_data: pd.DataFrame,
        min_variance: float = 0.1,
        min_detection_rate: float = 0.1,
        labels: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """Remove genes failing variance or detection-rate thresholds."""
        self.calculate_qc_metrics(expression_data, labels)
        n_samples = expression_data.shape[1]
        keep_idx = []
        for gene in expression_data.index:
            row = expression_data.loc[gene]
            var = float(row.var(skipna=True))
            dr = float((row > 0).sum()) / max(n_samples, 1)
            if var >= min_variance and dr >= min_detection_rate:
                keep_idx.append(gene)
        return expression_data.loc[keep_idx]

    def generate_qc_plots(self, output_dir: str, prefix: str = "qc") -> Dict[str, str]:
        """
        Generate QC plots and save them to files.

        Args:
            output_dir: Output directory
            prefix: File prefix

        Returns:
            Dictionary of saved plot file paths
        """
        if not self.qc_results:
            raise ValueError("QC metrics must be calculated before generating plots")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        plot_files = {}

        try:
            # Sample-level plots
            sample_metrics = self.qc_results["sample_metrics"]
            sample_df = pd.DataFrame(sample_metrics).T

            # Library size distribution
            fig = px.histogram(
                sample_df,
                x="library_size",
                nbins=30,
                title="Library Size Distribution",
                labels={"library_size": "Library Size", "count": "Number of Samples"},
            )
            fig.write_html(output_dir / f"{prefix}_library_size_dist.html")
            plot_files["library_size_dist"] = str(
                output_dir / f"{prefix}_library_size_dist.html"
            )

            # Missing rate distribution
            fig = px.histogram(
                sample_df,
                x="missing_percentage",
                nbins=30,
                title="Sample Missing Rate Distribution",
                labels={
                    "missing_percentage": "Missing Rate (%)",
                    "count": "Number of Samples",
                },
            )
            fig.write_html(output_dir / f"{prefix}_sample_missing_dist.html")
            plot_files["sample_missing_dist"] = str(
                output_dir / f"{prefix}_sample_missing_dist.html"
            )

            # Zero rate distribution
            fig = px.histogram(
                sample_df,
                x="zero_percentage",
                nbins=30,
                title="Sample Zero Rate Distribution",
                labels={
                    "zero_percentage": "Zero Rate (%)",
                    "count": "Number of Samples",
                },
            )
            fig.write_html(output_dir / f"{prefix}_sample_zero_dist.html")
            plot_files["sample_zero_dist"] = str(
                output_dir / f"{prefix}_sample_zero_dist.html"
            )

            # Gene-level plots
            gene_metrics = self.qc_results["gene_metrics"]
            gene_df = pd.DataFrame(gene_metrics).T

            # Gene variance distribution
            fig = px.histogram(
                gene_df,
                x="variance",
                nbins=50,
                title="Gene Variance Distribution",
                labels={"variance": "Variance", "count": "Number of Genes"},
            )
            fig.update_xaxes(type="log")
            fig.write_html(output_dir / f"{prefix}_gene_variance_dist.html")
            plot_files["gene_variance_dist"] = str(
                output_dir / f"{prefix}_gene_variance_dist.html"
            )

            # Gene missing rate distribution
            fig = px.histogram(
                gene_df,
                x="missing_percentage",
                nbins=30,
                title="Gene Missing Rate Distribution",
                labels={
                    "missing_percentage": "Missing Rate (%)",
                    "count": "Number of Genes",
                },
            )
            fig.write_html(output_dir / f"{prefix}_gene_missing_dist.html")
            plot_files["gene_missing_dist"] = str(
                output_dir / f"{prefix}_gene_missing_dist.html"
            )

            # Gene zero rate distribution
            fig = px.histogram(
                gene_df,
                x="zero_percentage",
                nbins=30,
                title="Gene Zero Rate Distribution",
                labels={"zero_percentage": "Zero Rate (%)", "count": "Number of Genes"},
            )
            fig.write_html(output_dir / f"{prefix}_gene_zero_dist.html")
            plot_files["gene_zero_dist"] = str(
                output_dir / f"{prefix}_gene_zero_dist.html"
            )

            # Summary plots
            if self.filtered_data:
                # Before/after comparison
                fig = make_subplots(
                    rows=1,
                    cols=2,
                    subplot_titles=["Before Filtering", "After Filtering"],
                )

                # Add sample metrics comparison
                fig.add_trace(
                    go.Bar(
                        x=list(sample_df.index),
                        y=sample_df["missing_percentage"],
                        name="Missing Rate",
                        marker_color="red",
                    ),
                    row=1,
                    col=1,
                )
                fig.add_trace(
                    go.Bar(
                        x=list(sample_df.index),
                        y=sample_df["zero_percentage"],
                        name="Zero Rate",
                        marker_color="blue",
                    ),
                    row=1,
                    col=1,
                )

                fig.update_layout(title="Sample Quality Metrics Comparison", height=500)
                fig.write_html(output_dir / f"{prefix}_filtering_comparison.html")
                plot_files["filtering_comparison"] = str(
                    output_dir / f"{prefix}_filtering_comparison.html"
                )

            logger.info(f"QC plots generated and saved to {output_dir}")
            return plot_files

        except Exception as e:
            logger.error(f"Failed to generate QC plots: {str(e)}")
            raise

    def generate_qc_report(self, output_dir: str, prefix: str = "qc") -> str:
        """
        Generate a comprehensive QC report.

        Args:
            output_dir: Output directory
            prefix: File prefix

        Returns:
            Path to the generated report
        """
        if not self.qc_results:
            raise ValueError("QC metrics must be calculated before generating report")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Generate plots first
            plot_files = self.generate_qc_plots(output_dir, prefix)

            # Create HTML report
            report_content = self._create_html_report(plot_files)

            report_file = output_dir / f"{prefix}_report.html"
            with open(report_file, "w") as f:
                f.write(report_content)

            logger.info(f"QC report generated: {report_file}")
            return str(report_file)

        except Exception as e:
            logger.error(f"Failed to generate QC report: {str(e)}")
            raise

    def _create_html_report(self, plot_files: Dict[str, str]) -> str:
        """
        Create HTML content for QC report.

        Args:
            plot_files: Dictionary of plot file paths

        Returns:
            HTML content string
        """
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Quality Control Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; }}
                .metric {{ display: inline-block; margin: 10px; padding: 10px; background: #f5f5f5; }}
                .warning {{ color: orange; font-weight: bold; }}
                .error {{ color: red; font-weight: bold; }}
                .success {{ color: green; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>Quality Control Report</h1>
            
            <div class="section">
                <h2>Data Summary</h2>
                <div class="metric">
                    <strong>Genes:</strong> {self.qc_results['data_summary']['n_genes']:,}
                </div>
                <div class="metric">
                    <strong>Samples:</strong> {self.qc_results['data_summary']['n_samples']:,}
                </div>
                <div class="metric">
                    <strong>Missing Rate:</strong> {self.qc_results['data_summary']['missing_percentage']:.1f}%
                </div>
                <div class="metric">
                    <strong>Zero Rate:</strong> {self.qc_results['data_summary']['zero_percentage']:.1f}%
                </div>
            </div>
            
            <div class="section">
                <h2>Quality Issues</h2>
                <h3>Sample Issues ({len(self.qc_results['quality_flags']['sample_issues'])}):</h3>
                <ul>
                    {''.join([f'<li class="warning">{issue}</li>' for issue in self.qc_results['quality_flags']['sample_issues']])}
                </ul>
                
                <h3>Gene Issues ({len(self.qc_results['quality_flags']['gene_issues'])}):</h3>
                <ul>
                    {''.join([f'<li class="warning">{issue}</li>' for issue in self.qc_results['quality_flags']['gene_issues']])}
                </ul>
                
                <h3>Data Issues ({len(self.qc_results['quality_flags']['data_issues'])}):</h3>
                <ul>
                    {''.join([f'<li class="error">{issue}</li>' for issue in self.qc_results['quality_flags']['data_issues']])}
                </ul>
            </div>
            
            <div class="section">
                <h2>Filtering Recommendations</h2>
                <h3>Sample Filters:</h3>
                <ul>
                    <li>Max Missing Rate: {self.qc_results['filtering_recommendations']['sample_filters']['max_missing_rate']:.1f}%</li>
                    <li>Max Zero Rate: {self.qc_results['filtering_recommendations']['sample_filters']['max_zero_rate']:.1f}%</li>
                    <li>Min Library Size: {self.qc_results['filtering_recommendations']['sample_filters']['min_library_size']:.0f}</li>
                </ul>
                
                <h3>Gene Filters:</h3>
                <ul>
                    <li>Max Missing Rate: {self.qc_results['filtering_recommendations']['gene_filters']['max_missing_rate']:.1f}%</li>
                    <li>Max Zero Rate: {self.qc_results['filtering_recommendations']['gene_filters']['max_zero_rate']:.1f}%</li>
                    <li>Min Variance: {self.qc_results['filtering_recommendations']['gene_filters']['min_variance']:.6f}</li>
                </ul>
            </div>
            
            <div class="section">
                <h2>QC Plots</h2>
                <iframe src="{plot_files.get('library_size_dist', '')}" width="100%" height="400"></iframe>
                <iframe src="{plot_files.get('sample_missing_dist', '')}" width="100%" height="400"></iframe>
                <iframe src="{plot_files.get('gene_variance_dist', '')}" width="100%" height="400"></iframe>
            </div>
        </body>
        </html>
        """

        return html_content
