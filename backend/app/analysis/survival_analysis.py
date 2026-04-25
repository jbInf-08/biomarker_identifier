"""
Survival Analysis Module

This module provides functionality for survival analysis including Cox proportional
hazards models, Kaplan-Meier curves, and survival-related biomarker discovery.
"""

import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# from sklearn.linear_model import CoxnetSurvivalAnalysis  # Not available in standard sklearn
from lifelines import CoxPHFitter, KaplanMeierFitter
from lifelines.statistics import multivariate_logrank_test
from lifelines.utils import concordance_index
from scipy import stats
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class SurvivalAnalyzer:
    """
    Survival analysis for biomarker discovery and validation.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize survival analyzer.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.survival_data = None
        self.cox_results = {}
        self.km_results = {}

    def load_survival_data(
        self,
        clinical_file: str,
        expression_file: Optional[str] = None,
        time_column: str = "overall_survival_time",
        event_column: str = "overall_survival_event",
        **kwargs,
    ) -> pd.DataFrame:
        """
        Load survival data from clinical and expression files.

        Args:
            clinical_file: Path to clinical data file
            expression_file: Path to expression data file (optional)
            time_column: Column name for survival time
            event_column: Column name for survival event
            **kwargs: Additional arguments for pandas read functions

        Returns:
            Combined survival data DataFrame
        """
        try:
            # Load clinical data
            clinical_data = pd.read_csv(clinical_file, **kwargs)

            # Check required columns
            if time_column not in clinical_data.columns:
                raise ValueError(
                    f"Time column '{time_column}' not found in clinical data"
                )
            if event_column not in clinical_data.columns:
                raise ValueError(
                    f"Event column '{event_column}' not found in clinical data"
                )

            # Clean survival data
            survival_data = clinical_data.copy()

            # Convert time to numeric
            survival_data[time_column] = pd.to_numeric(
                survival_data[time_column], errors="coerce"
            )

            # Convert event to binary
            survival_data[event_column] = survival_data[event_column].astype(int)

            # Remove missing values
            survival_data = survival_data.dropna(subset=[time_column, event_column])

            # Remove negative or zero times
            survival_data = survival_data[survival_data[time_column] > 0]

            # Load expression data if provided
            if expression_file:
                expression_data = pd.read_csv(expression_file, index_col=0, **kwargs)

                # Align samples
                common_samples = set(survival_data.index) & set(expression_data.columns)
                if len(common_samples) > 0:
                    survival_data = survival_data.loc[list(common_samples)]
                    expression_data = expression_data[list(common_samples)]

                    # Add expression data
                    survival_data = pd.concat(
                        [survival_data, expression_data.T], axis=1
                    )
                    logger.info(
                        f"Added expression data: {expression_data.shape[0]} genes"
                    )
                else:
                    logger.warning(
                        "No common samples found between clinical and expression data"
                    )

            self.survival_data = survival_data
            logger.info(f"Loaded survival data: {survival_data.shape}")

            return survival_data

        except Exception as e:
            logger.error(f"Failed to load survival data: {str(e)}")
            raise

    def prepare_survival_data(
        self,
        time_column: str = "overall_survival_time",
        event_column: str = "overall_survival_event",
        covariates: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Prepare survival data for analysis.

        Args:
            time_column: Column name for survival time
            event_column: Column name for survival event
            covariates: List of covariate columns

        Returns:
            Prepared survival data
        """
        try:
            if self.survival_data is None:
                raise ValueError("No survival data loaded")

            # Select relevant columns
            columns = [time_column, event_column]
            if covariates:
                columns.extend(covariates)

            # Filter available columns
            available_columns = [
                col for col in columns if col in self.survival_data.columns
            ]
            survival_data = self.survival_data[available_columns].copy()

            # Remove missing values
            survival_data = survival_data.dropna()

            # Standardize covariates
            if covariates:
                covariate_cols = [
                    col for col in covariates if col in survival_data.columns
                ]
                if covariate_cols:
                    scaler = StandardScaler()
                    survival_data[covariate_cols] = scaler.fit_transform(
                        survival_data[covariate_cols]
                    )

            logger.info(f"Prepared survival data: {survival_data.shape}")

            return survival_data

        except Exception as e:
            logger.error(f"Failed to prepare survival data: {str(e)}")
            raise

    def cox_proportional_hazards(
        self,
        time_column: str = "overall_survival_time",
        event_column: str = "overall_survival_event",
        covariates: Optional[List[str]] = None,
        penalizer: float = 0.1,
    ) -> Dict[str, Any]:
        """
        Perform Cox proportional hazards analysis.

        Args:
            time_column: Column name for survival time
            event_column: Column name for survival event
            covariates: List of covariate columns
            penalizer: L2 penalizer for regularization

        Returns:
            Cox analysis results
        """
        try:
            # Prepare data
            survival_data = self.prepare_survival_data(
                time_column, event_column, covariates
            )

            # Separate time, event, and covariates
            time_data = survival_data[time_column]
            event_data = survival_data[event_column]

            if covariates:
                covariate_data = survival_data[covariates]
            else:
                covariate_data = pd.DataFrame(index=survival_data.index)

            # Fit Cox model
            cph = CoxPHFitter(penalizer=penalizer)
            cph.fit(survival_data, duration_col=time_column, event_col=event_column)

            # Get results
            cox_results = {
                "model": cph,
                "summary": cph.summary,
                "concordance_index": cph.concordance_index_,
                "log_likelihood": cph.log_likelihood_,
                "n_events": event_data.sum(),
                "n_samples": len(survival_data),
                "covariates": covariates or [],
                "penalizer": penalizer,
            }

            # Calculate hazard ratios
            if not covariate_data.empty:
                hazard_ratios = np.exp(cph.params_)
                cox_results["hazard_ratios"] = hazard_ratios.to_dict()

                # Identify significant covariates (lifelines uses index for covariate names)
                sig_mask = cph.summary["p"] < 0.05
                significant_covariates = cph.summary.loc[sig_mask].index.tolist()
                cox_results["significant_covariates"] = significant_covariates

            self.cox_results["main"] = cox_results
            logger.info(
                f"Cox analysis completed: C-index = {cox_results['concordance_index']:.3f}"
            )

            return cox_results

        except Exception as e:
            logger.error(f"Cox proportional hazards analysis failed: {str(e)}")
            raise

    def univariate_cox_analysis(
        self,
        time_column: str = "overall_survival_time",
        event_column: str = "overall_survival_event",
        gene_columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Perform univariate Cox analysis for each gene.

        Args:
            time_column: Column name for survival time
            event_column: Column name for survival event
            gene_columns: List of gene columns (if None, auto-detect)

        Returns:
            Univariate Cox results DataFrame
        """
        try:
            if self.survival_data is None:
                raise ValueError("No survival data loaded")

            # Auto-detect gene columns if not provided
            if gene_columns is None:
                # Assume columns that look like gene names
                gene_columns = [
                    col
                    for col in self.survival_data.columns
                    if col not in [time_column, event_column]
                    and not col.startswith("clinical_")
                ]

            # Prepare base data
            base_data = self.survival_data[[time_column, event_column]].copy()
            base_data = base_data.dropna()

            univariate_results = []

            for gene in gene_columns:
                if gene not in self.survival_data.columns:
                    continue

                try:
                    # Prepare data for this gene
                    gene_data = base_data.copy()
                    gene_data[gene] = self.survival_data.loc[gene_data.index, gene]
                    gene_data = gene_data.dropna()

                    if len(gene_data) < 10:  # Need minimum samples
                        continue

                    # Fit Cox model
                    cph = CoxPHFitter()
                    cph.fit(gene_data, duration_col=time_column, event_col=event_column)

                    # Extract results
                    gene_results = cph.summary.loc[gene]

                    univariate_results.append(
                        {
                            "gene": gene,
                            "coef": gene_results["coef"],
                            "exp_coef": gene_results["exp(coef)"],
                            "se_coef": gene_results["se(coef)"],
                            "p_value": gene_results["p"],
                            "lower_ci": gene_results["exp(coef) lower 95%"],
                            "upper_ci": gene_results["exp(coef) upper 95%"],
                            "concordance_index": cph.concordance_index_,
                            "n_samples": len(gene_data),
                            "n_events": gene_data[event_column].sum(),
                        }
                    )

                except Exception as e:
                    logger.warning(f"Failed to analyze gene {gene}: {str(e)}")
                    continue

            # Create results DataFrame
            results_df = pd.DataFrame(univariate_results)

            if not results_df.empty:
                # Sort by p-value
                results_df = results_df.sort_values("p_value")

                # Add significance flags
                results_df["significant"] = results_df["p_value"] < 0.05
                results_df["highly_significant"] = results_df["p_value"] < 0.001

                # Add hazard ratio interpretation
                results_df["hazard_interpretation"] = results_df["exp_coef"].apply(
                    lambda x: "Protective" if x < 1 else "Risk" if x > 1 else "Neutral"
                )

            logger.info(
                f"Univariate Cox analysis completed: {len(results_df)} genes analyzed"
            )

            return results_df

        except Exception as e:
            logger.error(f"Univariate Cox analysis failed: {str(e)}")
            raise

    def kaplan_meier_analysis(
        self,
        time_column: str = "overall_survival_time",
        event_column: str = "overall_survival_event",
        group_column: str = "risk_group",
        groups: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Perform Kaplan-Meier survival analysis.

        Args:
            time_column: Column name for survival time
            event_column: Column name for survival event
            group_column: Column name for grouping
            groups: Dictionary defining groups (if None, auto-detect)

        Returns:
            Kaplan-Meier analysis results
        """
        try:
            if self.survival_data is None:
                raise ValueError("No survival data loaded")

            # Prepare data
            survival_data = self.survival_data[[time_column, event_column]].copy()
            survival_data = survival_data.dropna()

            # Create groups if not provided
            if groups is None:
                # Use median split for continuous variables
                if group_column in self.survival_data.columns:
                    median_value = self.survival_data[group_column].median()
                    groups = {
                        "Low": self.survival_data[group_column] <= median_value,
                        "High": self.survival_data[group_column] > median_value,
                    }
                else:
                    raise ValueError(f"Group column '{group_column}' not found")

            # Perform Kaplan-Meier analysis for each group
            km_results = {}

            for group_name, group_mask in groups.items():
                try:
                    # Get group data
                    group_data = survival_data[group_mask]

                    if len(group_data) < 5:  # Need minimum samples
                        continue

                    # Fit Kaplan-Meier
                    kmf = KaplanMeierFitter()
                    kmf.fit(
                        group_data[time_column],
                        group_data[event_column],
                        label=group_name,
                    )

                    # Calculate statistics
                    median_survival = kmf.median_survival_time_
                    survival_at_1yr = kmf.survival_function_.iloc[
                        min(365, len(kmf.survival_function_) - 1), 0
                    ]
                    survival_at_5yr = kmf.survival_function_.iloc[
                        min(1825, len(kmf.survival_function_) - 1), 0
                    ]

                    km_results[group_name] = {
                        "kmf": kmf,
                        "median_survival": median_survival,
                        "survival_at_1yr": survival_at_1yr,
                        "survival_at_5yr": survival_at_5yr,
                        "n_samples": len(group_data),
                        "n_events": group_data[event_column].sum(),
                    }

                except Exception as e:
                    logger.warning(f"Failed to analyze group {group_name}: {str(e)}")
                    continue

            # Perform log-rank test if multiple groups
            if len(km_results) > 1:
                try:
                    # Prepare data for log-rank test
                    all_times = []
                    all_events = []
                    all_groups = []

                    for group_name, group_mask in groups.items():
                        group_data = survival_data[group_mask]
                        all_times.extend(group_data[time_column].tolist())
                        all_events.extend(group_data[event_column].tolist())
                        all_groups.extend([group_name] * len(group_data))

                    # Perform log-rank test
                    logrank_test = multivariate_logrank_test(
                        all_times, all_groups, all_events
                    )

                    km_results["logrank_test"] = {
                        "test_statistic": logrank_test.test_statistic,
                        "p_value": logrank_test.p_value,
                        "degrees_of_freedom": logrank_test.degrees_of_freedom,
                    }

                except Exception as e:
                    logger.warning(f"Log-rank test failed: {str(e)}")

            self.km_results["main"] = km_results
            logger.info(f"Kaplan-Meier analysis completed: {len(km_results)} groups")

            return km_results

        except Exception as e:
            logger.error(f"Kaplan-Meier analysis failed: {str(e)}")
            raise

    def create_survival_plots(
        self,
        output_dir: str,
        time_column: str = "overall_survival_time",
        event_column: str = "overall_survival_event",
    ):
        """
        Create survival analysis plots.

        Args:
            output_dir: Output directory for plots
            time_column: Column name for survival time
            event_column: Column name for survival event
        """
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create Kaplan-Meier plot
            if "main" in self.km_results:
                km_results = self.km_results["main"]

                plt.figure(figsize=(10, 8))

                for group_name, group_results in km_results.items():
                    if group_name == "logrank_test":
                        continue

                    kmf = group_results["kmf"]
                    kmf.plot_survival_function()

                plt.title("Kaplan-Meier Survival Curves")
                plt.xlabel("Time (days)")
                plt.ylabel("Survival Probability")
                plt.legend()
                plt.grid(True, alpha=0.3)

                # Add log-rank test p-value if available
                if "logrank_test" in km_results:
                    p_value = km_results["logrank_test"]["p_value"]
                    plt.text(
                        0.05,
                        0.05,
                        f"Log-rank p-value: {p_value:.4f}",
                        transform=plt.gca().transAxes,
                        fontsize=12,
                        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
                    )

                plt.tight_layout()

                # Save plot
                plot_file = output_dir / "kaplan_meier_curves.png"
                plt.savefig(plot_file, dpi=300, bbox_inches="tight")
                plt.close()

                logger.info(f"Kaplan-Meier plot saved: {plot_file}")

            # Create Cox model summary plot
            if "main" in self.cox_results:
                cox_results = self.cox_results["main"]

                if "summary" in cox_results and not cox_results["summary"].empty:
                    plt.figure(figsize=(12, 8))

                    # Create forest plot
                    summary = cox_results["summary"]

                    # Plot hazard ratios with confidence intervals
                    y_pos = range(len(summary))
                    hazard_ratios = summary["exp(coef)"]
                    lower_ci = summary["exp(coef) lower 95%"]
                    upper_ci = summary["exp(coef) upper 95%"]

                    plt.errorbar(
                        hazard_ratios,
                        y_pos,
                        xerr=[hazard_ratios - lower_ci, upper_ci - hazard_ratios],
                        fmt="o",
                        capsize=5,
                        capthick=2,
                    )

                    plt.axvline(x=1, color="red", linestyle="--", alpha=0.7)
                    plt.yticks(y_pos, summary.index)
                    plt.xlabel("Hazard Ratio")
                    plt.title("Cox Proportional Hazards Model - Forest Plot")
                    plt.grid(True, alpha=0.3)

                    plt.tight_layout()

                    # Save plot
                    plot_file = output_dir / "cox_forest_plot.png"
                    plt.savefig(plot_file, dpi=300, bbox_inches="tight")
                    plt.close()

                    logger.info(f"Cox forest plot saved: {plot_file}")

        except Exception as e:
            logger.error(f"Failed to create survival plots: {str(e)}")

    def survival_biomarker_discovery(
        self,
        time_column: str = "overall_survival_time",
        event_column: str = "overall_survival_event",
        gene_columns: Optional[List[str]] = None,
        top_n: int = 100,
    ) -> pd.DataFrame:
        """
        Discover survival-related biomarkers.

        Args:
            time_column: Column name for survival time
            event_column: Column name for survival event
            gene_columns: List of gene columns
            top_n: Number of top biomarkers to return

        Returns:
            Top survival biomarkers DataFrame
        """
        try:
            # Perform univariate Cox analysis
            univariate_results = self.univariate_cox_analysis(
                time_column, event_column, gene_columns
            )

            if univariate_results.empty:
                logger.warning("No genes could be analyzed")
                return pd.DataFrame()

            # Filter significant genes
            significant_genes = univariate_results[
                univariate_results["significant"]
            ].copy()

            # Sort by p-value and concordance index
            significant_genes = significant_genes.sort_values(
                ["p_value", "concordance_index"], ascending=[True, False]
            )

            # Select top biomarkers
            top_biomarkers = significant_genes.head(top_n)

            # Add biomarker interpretation
            top_biomarkers["biomarker_type"] = top_biomarkers[
                "hazard_interpretation"
            ].apply(
                lambda x: "Prognostic" if x in ["Risk", "Protective"] else "Neutral"
            )

            # Calculate effect size
            top_biomarkers["effect_size"] = np.abs(top_biomarkers["exp_coef"] - 1)

            logger.info(f"Discovered {len(top_biomarkers)} survival biomarkers")

            return top_biomarkers

        except Exception as e:
            logger.error(f"Survival biomarker discovery failed: {str(e)}")
            raise

    def get_survival_summary(self) -> Dict[str, Any]:
        """
        Get summary of survival analysis results.

        Returns:
            Survival analysis summary
        """
        try:
            summary = {
                "survival_data_loaded": self.survival_data is not None,
                "cox_analyses_performed": len(self.cox_results),
                "km_analyses_performed": len(self.km_results),
                "analysis_timestamp": datetime.now().isoformat(),
            }

            if self.survival_data is not None:
                summary["n_samples"] = len(self.survival_data)
                summary["n_events"] = self.survival_data.get(
                    "overall_survival_event", pd.Series()
                ).sum()

            if "main" in self.cox_results:
                cox_results = self.cox_results["main"]
                summary["cox_concordance_index"] = cox_results.get("concordance_index")
                summary["cox_n_events"] = cox_results.get("n_events")
                summary["cox_n_samples"] = cox_results.get("n_samples")

            if "main" in self.km_results:
                km_results = self.km_results["main"]
                summary["km_groups"] = len(
                    [k for k in km_results.keys() if k != "logrank_test"]
                )
                if "logrank_test" in km_results:
                    summary["logrank_p_value"] = km_results["logrank_test"]["p_value"]

            return summary

        except Exception as e:
            logger.error(f"Failed to get survival summary: {str(e)}")
            raise


def main():
    """Main function for testing survival analysis."""
    # Create sample survival data
    np.random.seed(42)
    n_samples = 100

    # Generate synthetic survival data
    survival_data = pd.DataFrame(
        {
            "overall_survival_time": np.random.exponential(scale=1000, size=n_samples),
            "overall_survival_event": np.random.binomial(1, 0.7, size=n_samples),
            "age": np.random.normal(65, 15, size=n_samples),
            "stage": np.random.choice(["I", "II", "III", "IV"], size=n_samples),
            "GENE_001": np.random.normal(0, 1, size=n_samples),
            "GENE_002": np.random.normal(0, 1, size=n_samples),
            "GENE_003": np.random.normal(0, 1, size=n_samples),
        }
    )

    # Test survival analysis
    analyzer = SurvivalAnalyzer()

    try:
        # Load data
        analyzer.survival_data = survival_data

        # Cox analysis
        cox_results = analyzer.cox_proportional_hazards(
            covariates=["age", "GENE_001", "GENE_002", "GENE_003"]
        )
        print(f"Cox analysis C-index: {cox_results['concordance_index']:.3f}")

        # Univariate Cox analysis
        univariate_results = analyzer.univariate_cox_analysis()
        print(f"Univariate Cox analysis: {len(univariate_results)} genes")

        # Kaplan-Meier analysis
        km_results = analyzer.kaplan_meier_analysis(
            group_column="GENE_001",
            groups={
                "Low": survival_data["GENE_001"] <= survival_data["GENE_001"].median(),
                "High": survival_data["GENE_001"] > survival_data["GENE_001"].median(),
            },
        )
        print(f"Kaplan-Meier analysis: {len(km_results)} groups")

        # Biomarker discovery
        biomarkers = analyzer.survival_biomarker_discovery()
        print(f"Survival biomarkers: {len(biomarkers)} genes")

        # Get summary
        summary = analyzer.get_survival_summary()
        print(f"Survival analysis summary: {summary}")

        print("Survival analysis test completed successfully!")

    except Exception as e:
        logger.error(f"Survival analysis test failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
