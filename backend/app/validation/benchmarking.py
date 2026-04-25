"""
Benchmarking Module for Biomarker Discovery Pipeline

This module provides functionality to benchmark the biomarker discovery pipeline
against established tools like DESeq2, edgeR, and limma.
"""

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from ..ml_models.feature_selection import FeatureSelector
from ..pipelines.stats import StatisticalAnalysis
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class BiomarkerBenchmarking:
    """
    Benchmarking class for comparing biomarker discovery methods.
    """

    def __init__(self, output_dir: str = "results/benchmarking"):
        """
        Initialize benchmarking module.

        Args:
            output_dir: Directory to save benchmarking results
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Known biomarkers for validation
        self.known_biomarkers = {
            "breast_cancer": [
                "TP53",
                "BRCA1",
                "BRCA2",
                "PIK3CA",
                "GATA3",
                "CDH1",
                "MAP3K1",
            ],
            "lung_cancer": ["TP53", "KRAS", "EGFR", "ALK", "BRAF", "MET", "RET"],
            "colon_cancer": [
                "APC",
                "TP53",
                "KRAS",
                "PIK3CA",
                "SMAD4",
                "BRAF",
                "CTNNB1",
            ],
            "prostate_cancer": ["TP53", "PTEN", "RB1", "AR", "MYC", "ERG", "TMPRSS2"],
        }

    def prepare_data_for_deseq2(
        self, expression_data: pd.DataFrame, labels: pd.Series, output_dir: str
    ) -> Dict[str, str]:
        """
        Prepare data for DESeq2 analysis.

        Args:
            expression_data: Gene expression DataFrame
            labels: Sample labels
            output_dir: Output directory for files

        Returns:
            Dictionary with file paths
        """
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Prepare count matrix (rounded to integers)
            count_matrix = expression_data.round().astype(int)
            count_matrix = count_matrix.loc[
                (count_matrix > 0).any(axis=1)
            ]  # Remove zero genes

            # Save count matrix
            count_file = output_dir / "count_matrix.tsv"
            count_matrix.to_csv(count_file, sep="\t")

            # Prepare sample metadata
            sample_metadata = pd.DataFrame(
                {
                    "sample_id": labels.index,
                    "condition": labels.values,
                    "batch": "batch1",  # Simplified for now
                }
            )

            metadata_file = output_dir / "sample_metadata.tsv"
            sample_metadata.to_csv(metadata_file, sep="\t", index=False)

            # Create DESeq2 R script
            r_script = f"""
library(DESeq2)
library(ggplot2)

# Read data
count_matrix <- read.table("{count_file}", header=TRUE, row.names=1, sep="\\t")
sample_metadata <- read.table("{metadata_file}", header=TRUE, sep="\\t", row.names=1)

# Create DESeq2 object
dds <- DESeqDataSetFromMatrix(countData = count_matrix,
                             colData = sample_metadata,
                             design = ~ condition)

# Filter low count genes
keep <- rowSums(counts(dds)) >= 10
dds <- dds[keep,]

# Run DESeq2 analysis
dds <- DESeq(dds)

# Get results
res <- results(dds, contrast=c("condition", "TUMOR", "NORMAL"))
res <- res[order(res$pvalue),]

# Save results
write.table(res, "{output_dir}/deseq2_results.tsv", sep="\\t", quote=FALSE)

# Create volcano plot
pdf("{output_dir}/deseq2_volcano.pdf")
plot(res$log2FoldChange, -log10(res$pvalue), 
     xlab="Log2 Fold Change", ylab="-Log10 P-value",
     main="DESeq2 Volcano Plot")
abline(h=-log10(0.05), col="red", lty=2)
abline(v=c(-1, 1), col="red", lty=2)
dev.off()

# Summary statistics
summary_stats <- data.frame(
    total_genes = nrow(res),
    significant_genes = sum(res$pvalue < 0.05, na.rm=TRUE),
    upregulated = sum(res$log2FoldChange > 1 & res$pvalue < 0.05, na.rm=TRUE),
    downregulated = sum(res$log2FoldChange < -1 & res$pvalue < 0.05, na.rm=TRUE)
)

write.table(summary_stats, "{output_dir}/deseq2_summary.tsv", sep="\\t", quote=FALSE)
"""

            script_file = output_dir / "deseq2_analysis.R"
            with open(script_file, "w") as f:
                f.write(r_script)

            return {
                "count_file": str(count_file),
                "metadata_file": str(metadata_file),
                "script_file": str(script_file),
                "results_file": str(output_dir / "deseq2_results.tsv"),
                "summary_file": str(output_dir / "deseq2_summary.tsv"),
            }

        except Exception as e:
            logger.error(f"Failed to prepare data for DESeq2: {str(e)}")
            raise

    def run_deseq2_analysis(
        self, expression_data: pd.DataFrame, labels: pd.Series, output_dir: str
    ) -> Dict[str, Any]:
        """
        Run DESeq2 analysis.

        Args:
            expression_data: Gene expression DataFrame
            labels: Sample labels
            output_dir: Output directory

        Returns:
            DESeq2 results
        """
        try:
            # Prepare data
            files = self.prepare_data_for_deseq2(expression_data, labels, output_dir)

            # Run R script
            logger.info("Running DESeq2 analysis...")
            result = subprocess.run(
                ["Rscript", files["script_file"]],
                capture_output=True,
                text=True,
                cwd=output_dir,
            )

            if result.returncode != 0:
                logger.error(f"DESeq2 analysis failed: {result.stderr}")
                raise RuntimeError(f"DESeq2 analysis failed: {result.stderr}")

            # Read results
            if os.path.exists(files["results_file"]):
                deseq2_results = pd.read_csv(
                    files["results_file"], sep="\t", index_col=0
                )

                # Read summary
                summary = {}
                if os.path.exists(files["summary_file"]):
                    summary_df = pd.read_csv(
                        files["summary_file"], sep="\t", index_col=0
                    )
                    summary = summary_df.iloc[0].to_dict()

                return {
                    "results": deseq2_results,
                    "summary": summary,
                    "method": "DESeq2",
                    "status": "success",
                }
            else:
                raise FileNotFoundError("DESeq2 results file not found")

        except Exception as e:
            logger.error(f"DESeq2 analysis failed: {str(e)}")
            return {"method": "DESeq2", "status": "failed", "error": str(e)}

    def run_our_pipeline(
        self, expression_data: pd.DataFrame, labels: pd.Series
    ) -> Dict[str, Any]:
        """
        Run our biomarker discovery pipeline.

        Args:
            expression_data: Gene expression DataFrame
            labels: Sample labels

        Returns:
            Pipeline results
        """
        try:
            logger.info("Running our biomarker discovery pipeline...")

            # Statistical analysis
            stats_analyzer = StatisticalAnalysis()
            stats_results = stats_analyzer.differential_expression_analysis(
                expression_data, labels
            )

            # Feature selection
            feature_selector = FeatureSelector(random_state=42)
            feature_selector.fit(expression_data.T, labels, n_features=1000)

            # Get feature importance
            feature_importance = feature_selector.get_feature_importance()

            # Combine results
            combined_results = pd.DataFrame(
                {
                    "gene": feature_importance["feature"],
                    "consensus_score": feature_importance["consensus_score"],
                    "stability_score": feature_importance["stability_score"],
                    "rank": feature_importance["rank"],
                }
            )

            # Add statistical results if available
            if "t_test" in stats_results:
                t_test_results = stats_results["t_test"]
                combined_results = combined_results.merge(
                    t_test_results[["gene", "p_value", "log2_fold_change"]],
                    on="gene",
                    how="left",
                )

            # Calculate summary
            total_genes = len(combined_results)
            significant_genes = len(
                combined_results[combined_results["p_value"] < 0.05]
            )
            upregulated = len(
                combined_results[
                    (combined_results["log2_fold_change"] > 1)
                    & (combined_results["p_value"] < 0.05)
                ]
            )
            downregulated = len(
                combined_results[
                    (combined_results["log2_fold_change"] < -1)
                    & (combined_results["p_value"] < 0.05)
                ]
            )

            summary = {
                "total_genes": total_genes,
                "significant_genes": significant_genes,
                "upregulated": upregulated,
                "downregulated": downregulated,
            }

            return {
                "results": combined_results,
                "summary": summary,
                "method": "Our Pipeline",
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Our pipeline analysis failed: {str(e)}")
            return {"method": "Our Pipeline", "status": "failed", "error": str(e)}

    def compare_methods(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        cancer_type: str,
        output_dir: str,
    ) -> Dict[str, Any]:
        """
        Compare different biomarker discovery methods.

        Args:
            expression_data: Gene expression DataFrame
            labels: Sample labels
            cancer_type: Type of cancer
            output_dir: Output directory

        Returns:
            Comparison results
        """
        try:
            logger.info(f"Comparing biomarker discovery methods for {cancer_type}")

            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Run our pipeline
            our_results = self.run_our_pipeline(expression_data, labels)

            # Run DESeq2 (if R is available)
            deseq2_results = None
            try:
                deseq2_results = self.run_deseq2_analysis(
                    expression_data, labels, str(output_dir / "deseq2")
                )
            except Exception as e:
                logger.warning(f"DESeq2 analysis skipped: {str(e)}")

            # Compare results
            comparison_results = {
                "cancer_type": cancer_type,
                "dataset_shape": expression_data.shape,
                "n_tumor_samples": (labels == "TUMOR").sum(),
                "n_normal_samples": (labels == "NORMAL").sum(),
                "our_pipeline": our_results,
                "deseq2": deseq2_results,
                "comparison_timestamp": datetime.now().isoformat(),
            }

            # Validate known biomarkers
            known_genes = self.known_biomarkers.get(cancer_type, [])
            if known_genes and our_results["status"] == "success":
                validation_results = self.validate_known_biomarkers(
                    our_results["results"], known_genes
                )
                comparison_results["known_biomarker_validation"] = validation_results

            # Save comparison results
            results_file = output_dir / f"comparison_results_{cancer_type}.json"
            with open(results_file, "w") as f:
                json.dump(comparison_results, f, indent=2, default=str)

            # Create comparison plots
            self.create_comparison_plots(comparison_results, output_dir)

            logger.info(f"Comparison completed: {results_file}")

            return comparison_results

        except Exception as e:
            logger.error(f"Method comparison failed: {str(e)}")
            raise

    def validate_known_biomarkers(
        self, results: pd.DataFrame, known_genes: List[str]
    ) -> Dict[str, Any]:
        """
        Validate that known biomarkers are identified.

        Args:
            results: Analysis results DataFrame
            known_genes: List of known biomarker genes

        Returns:
            Validation results
        """
        try:
            validation_results = {}

            for gene in known_genes:
                if gene in results["gene"].values:
                    gene_results = results[results["gene"] == gene].iloc[0]

                    validation_results[gene] = {
                        "found": True,
                        "rank": gene_results.get("rank", "N/A"),
                        "consensus_score": gene_results.get("consensus_score", "N/A"),
                        "p_value": gene_results.get("p_value", "N/A"),
                        "log2_fold_change": gene_results.get("log2_fold_change", "N/A"),
                        "significant": gene_results.get("p_value", 1) < 0.05,
                    }
                else:
                    validation_results[gene] = {
                        "found": False,
                        "rank": "N/A",
                        "consensus_score": "N/A",
                        "p_value": "N/A",
                        "log2_fold_change": "N/A",
                        "significant": False,
                    }

            # Calculate validation metrics
            found_genes = sum(1 for v in validation_results.values() if v["found"])
            significant_genes = sum(
                1 for v in validation_results.values() if v.get("significant", False)
            )

            validation_summary = {
                "total_known_genes": len(known_genes),
                "found_genes": found_genes,
                "significant_genes": significant_genes,
                "discovery_rate": found_genes / len(known_genes),
                "significance_rate": significant_genes / len(known_genes),
            }

            return {
                "individual_results": validation_results,
                "summary": validation_summary,
            }

        except Exception as e:
            logger.error(f"Known biomarker validation failed: {str(e)}")
            raise

    def create_comparison_plots(
        self, comparison_results: Dict[str, Any], output_dir: Path
    ):
        """
        Create comparison plots.

        Args:
            comparison_results: Comparison results dictionary
            output_dir: Output directory
        """
        try:
            # Set up plotting style
            plt.style.use("default")
            sns.set_palette("husl")

            # Create summary comparison plot
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle(
                f"Biomarker Discovery Method Comparison - {comparison_results['cancer_type']}",
                fontsize=16,
            )

            # Plot 1: Method comparison summary
            methods = []
            significant_genes = []

            if comparison_results["our_pipeline"]["status"] == "success":
                methods.append("Our Pipeline")
                significant_genes.append(
                    comparison_results["our_pipeline"]["summary"]["significant_genes"]
                )

            if (
                comparison_results.get("deseq2")
                and comparison_results["deseq2"]["status"] == "success"
            ):
                methods.append("DESeq2")
                significant_genes.append(
                    comparison_results["deseq2"]["summary"]["significant_genes"]
                )

            if methods:
                axes[0, 0].bar(methods, significant_genes)
                axes[0, 0].set_title("Significant Genes by Method")
                axes[0, 0].set_ylabel("Number of Significant Genes")

            # Plot 2: Known biomarker validation
            if "known_biomarker_validation" in comparison_results:
                validation = comparison_results["known_biomarker_validation"]
                summary = validation["summary"]

                categories = ["Found", "Significant"]
                values = [summary["found_genes"], summary["significant_genes"]]

                axes[0, 1].bar(categories, values)
                axes[0, 1].set_title("Known Biomarker Validation")
                axes[0, 1].set_ylabel("Number of Genes")

            # Plot 3: Dataset characteristics
            dataset_info = [
                comparison_results["n_tumor_samples"],
                comparison_results["n_normal_samples"],
                comparison_results["dataset_shape"][0],  # number of genes
            ]
            dataset_labels = ["Tumor Samples", "Normal Samples", "Total Genes"]

            axes[1, 0].bar(dataset_labels, dataset_info)
            axes[1, 0].set_title("Dataset Characteristics")
            axes[1, 0].set_ylabel("Count")
            axes[1, 0].tick_params(axis="x", rotation=45)

            # Plot 4: Performance metrics
            if "known_biomarker_validation" in comparison_results:
                validation = comparison_results["known_biomarker_validation"]
                summary = validation["summary"]

                metrics = ["Discovery Rate", "Significance Rate"]
                values = [summary["discovery_rate"], summary["significance_rate"]]

                axes[1, 1].bar(metrics, values)
                axes[1, 1].set_title("Validation Metrics")
                axes[1, 1].set_ylabel("Rate")
                axes[1, 1].set_ylim(0, 1)

            plt.tight_layout()

            # Save plot
            plot_file = (
                output_dir / f"comparison_plots_{comparison_results['cancer_type']}.png"
            )
            plt.savefig(plot_file, dpi=300, bbox_inches="tight")
            plt.close()

            logger.info(f"Comparison plots saved: {plot_file}")

        except Exception as e:
            logger.error(f"Failed to create comparison plots: {str(e)}")

    def run_comprehensive_benchmark(
        self, datasets: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Run comprehensive benchmark across multiple datasets.

        Args:
            datasets: List of dataset dictionaries with expression_data, labels, cancer_type

        Returns:
            Comprehensive benchmark results
        """
        try:
            logger.info(f"Running comprehensive benchmark on {len(datasets)} datasets")

            benchmark_results = {
                "datasets": [],
                "overall_summary": {},
                "benchmark_timestamp": datetime.now().isoformat(),
            }

            for i, dataset in enumerate(datasets):
                try:
                    logger.info(
                        f"Processing dataset {i+1}/{len(datasets)}: {dataset['cancer_type']}"
                    )

                    # Run comparison
                    comparison_results = self.compare_methods(
                        dataset["expression_data"],
                        dataset["labels"],
                        dataset["cancer_type"],
                        str(self.output_dir / dataset["cancer_type"]),
                    )

                    benchmark_results["datasets"].append(comparison_results)

                except Exception as e:
                    logger.error(
                        f"Failed to process dataset {dataset['cancer_type']}: {str(e)}"
                    )
                    benchmark_results["datasets"].append(
                        {
                            "cancer_type": dataset["cancer_type"],
                            "status": "failed",
                            "error": str(e),
                        }
                    )

            # Calculate overall summary
            successful_datasets = [
                d for d in benchmark_results["datasets"] if d.get("status") != "failed"
            ]

            if successful_datasets:
                # Calculate average metrics
                total_genes = sum(d["dataset_shape"][0] for d in successful_datasets)
                total_significant = sum(
                    d["our_pipeline"]["summary"]["significant_genes"]
                    for d in successful_datasets
                )

                # Known biomarker validation
                validation_rates = []
                for d in successful_datasets:
                    if "known_biomarker_validation" in d:
                        rate = d["known_biomarker_validation"]["summary"][
                            "discovery_rate"
                        ]
                        validation_rates.append(rate)

                benchmark_results["overall_summary"] = {
                    "total_datasets": len(datasets),
                    "successful_datasets": len(successful_datasets),
                    "average_genes_per_dataset": total_genes / len(successful_datasets),
                    "average_significant_genes": total_significant
                    / len(successful_datasets),
                    "average_discovery_rate": np.mean(validation_rates)
                    if validation_rates
                    else 0,
                }

            # Save comprehensive results
            results_file = self.output_dir / "comprehensive_benchmark_results.json"
            with open(results_file, "w") as f:
                json.dump(benchmark_results, f, indent=2, default=str)

            logger.info(f"Comprehensive benchmark completed: {results_file}")

            return benchmark_results

        except Exception as e:
            logger.error(f"Comprehensive benchmark failed: {str(e)}")
            raise


def main():
    """
    Standalone benchmark test runner. Uses SYNTHETIC data only.
    NOT for production - only for validating benchmarking logic.
    Production pipelines must use real expression data.
    """
    # Synthetic data for benchmark testing ONLY - never used in production
    np.random.seed(42)
    n_genes = 1000
    n_samples = 50

    # Generate synthetic expression data
    expression_data = pd.DataFrame(
        np.random.lognormal(mean=5, sigma=1, size=(n_genes, n_samples)),
        index=[f"GENE_{i:04d}" for i in range(n_genes)],
        columns=[f"SAMPLE_{i:03d}" for i in range(n_samples)],
    )

    # Create labels (25 tumor, 25 normal)
    labels = pd.Series(["TUMOR"] * 25 + ["NORMAL"] * 25, index=expression_data.columns)

    # Add some differential expression for known genes
    known_genes = ["TP53", "BRCA1", "BRCA2"]
    for gene in known_genes:
        if gene in expression_data.index:
            # Make tumor samples have higher expression
            expression_data.loc[gene, labels == "TUMOR"] *= 2

    # Run benchmarking
    benchmarker = BiomarkerBenchmarking()

    try:
        results = benchmarker.compare_methods(
            expression_data, labels, "breast_cancer", "test_benchmark"
        )

        print("Benchmarking completed successfully!")
        print(f"Results: {json.dumps(results, indent=2, default=str)}")

    except Exception as e:
        logger.error(f"Benchmarking test failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
