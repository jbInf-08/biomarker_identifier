"""
Statistical analysis pipeline for biomarker identification.
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from ..data_processing.statistical_analysis import StatisticalAnalysis
from ..utils.adaptive_parameters import AdaptiveParameters
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class StatisticalPipeline:
    """
    Handles statistical analysis pipeline for biomarker identification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the StatisticalPipeline module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.stats_analyzer = StatisticalAnalysis(config)
        self.analysis_results = {}

    def run_statistical_analysis(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        analysis_methods: List[str] = None,
        alpha: float = 0.05,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Run comprehensive statistical analysis.

        Args:
            expression_data: Expression data matrix
            labels: Sample labels
            analysis_methods: List of statistical methods to apply
            alpha: Significance level
            **kwargs: Additional parameters

        Returns:
            Statistical analysis results
        """
        try:
            common = expression_data.columns.intersection(labels.index)
            if len(common) == 0:
                raise ValueError(
                    "No overlapping sample IDs between expression columns and labels index"
                )
            expression_data = expression_data.loc[:, common]
            labels = labels.loc[common]

            # Get adaptive parameters based on dataset size
            n_classes = len(labels.unique()) if labels is not None else 2
            stats_params = AdaptiveParameters.get_statistical_parameters(
                expression_data.shape[1], expression_data.shape[0], n_classes
            )

            # Override alpha with adaptive value if not explicitly provided
            if "alpha" not in kwargs or kwargs.get("alpha") == 0.05:
                alpha = stats_params.get("alpha", alpha)

            # Check minimum samples per class
            min_samples_per_class = stats_params.get("min_samples_per_class", 1)
            class_counts = labels.value_counts()
            if class_counts.min() < min_samples_per_class:
                logger.warning(
                    f"Some classes have fewer than {min_samples_per_class} samples. "
                    f"Statistical power may be limited."
                )

            if analysis_methods is None:
                # Determine appropriate methods based on data
                if len(labels.unique()) == 2:
                    analysis_methods = ["t_test", "wilcoxon"]
                elif len(labels.unique()) > 2:
                    analysis_methods = ["anova", "kruskal"]
                else:
                    analysis_methods = ["correlation"]

            results = {
                "expression_data": expression_data,
                "labels": labels,
                "analysis_methods": analysis_methods,
                "alpha": alpha,
                "adaptive_parameters": stats_params,
                "method_results": {},
            }

            # Run each statistical method
            # Filter out kwargs that statistical analysis doesn't accept
            stats_kwargs = {
                k: v
                for k, v in kwargs.items()
                if k
                in [
                    "fdr_method",
                    "effect_size",
                    "paired",
                    "alternative",
                    "correction_method",
                    "min_samples_per_group",
                    "test_type",
                ]
            }

            # Add adaptive FDR method if not specified
            if "fdr_method" not in stats_kwargs:
                stats_kwargs["fdr_method"] = stats_params.get("fdr_method", "fdr_bh")

            for method in analysis_methods:
                try:
                    method_result = (
                        self.stats_analyzer.differential_expression_analysis(
                            expression_data, labels, method, alpha, **stats_kwargs
                        )
                    )
                    results["method_results"][method] = method_result
                    logger.info(f"Statistical analysis {method} completed")
                except Exception as e:
                    logger.error(f"Failed to run {method}: {str(e)}")
                    results["method_results"][method] = {"error": str(e)}

            # Generate volcano plot data
            volcano_data = {}
            for method in analysis_methods:
                if (
                    method in results["method_results"]
                    and "error" not in results["method_results"][method]
                ):
                    try:
                        volcano_data[method] = self.stats_analyzer.volcano_plot_data(
                            results["method_results"][method]
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to generate volcano data for {method}: {str(e)}"
                        )

            results["volcano_data"] = volcano_data

            # Rank features
            ranking_results = {}
            for method in analysis_methods:
                if (
                    method in results["method_results"]
                    and "error" not in results["method_results"][method]
                ):
                    try:
                        ranking_results[method] = self.stats_analyzer.rank_features(
                            results["method_results"][method]
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to rank features for {method}: {str(e)}"
                        )

            results["ranking_results"] = ranking_results

            # Generate summary
            summary = self._generate_analysis_summary(results)
            results["summary"] = summary

            # Generate plots
            plots = self._generate_analysis_plots(results)
            results["plots"] = plots

            self.analysis_results = results
            logger.info("Statistical analysis pipeline completed")

            return results

        except Exception as e:
            logger.error(f"Failed to run statistical analysis pipeline: {str(e)}")
            raise

    def _generate_analysis_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate analysis summary.

        Args:
            results: Analysis results

        Returns:
            Analysis summary
        """
        summary = {
            "status": "completed",
            "n_genes": results["expression_data"].shape[0],
            "n_samples": results["expression_data"].shape[1],
            "n_classes": len(results["labels"].unique()),
            "methods_applied": list(results["method_results"].keys()),
            "significant_features": {},
            "top_features": {},
        }

        # Collect significant features from each method
        for method, method_result in results["method_results"].items():
            if "error" not in method_result:
                if "significant_features_adjusted" in method_result:
                    significant = method_result["significant_features_adjusted"]
                elif "significant_features" in method_result:
                    significant = method_result["significant_features"]
                else:
                    significant = []

                summary["significant_features"][method] = {
                    "n_significant": len(significant),
                    "significant_genes": significant[:50],  # Top 50
                }

        # Collect top features from ranking
        for method, ranking_result in results.get("ranking_results", {}).items():
            if "top_features" in ranking_result:
                summary["top_features"][method] = ranking_result["top_features"][
                    :20
                ]  # Top 20

        return summary

    def _generate_analysis_plots(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate analysis plots.

        Args:
            results: Analysis results

        Returns:
            Dictionary of plot objects
        """
        plots = {}

        try:
            import plotly.express as px
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots

            # Volcano plots
            volcano_data = results.get("volcano_data", {})
            for method, data in volcano_data.items():
                if "data" in data:
                    volcano_df = pd.DataFrame(data["data"])

                    # Create volcano plot
                    fig = px.scatter(
                        volcano_df,
                        x="log2_fold_change"
                        if "log2_fold_change" in volcano_df.columns
                        else "effect_size",
                        y="p_value",
                        color="significant",
                        title=f"Volcano Plot - {method}",
                        labels={
                            "log2_fold_change": "Log2 Fold Change",
                            "effect_size": "Effect Size",
                            "p_value": "-log10(p-value)",
                            "significant": "Significant",
                        },
                    )

                    # Add significance lines
                    fig.add_hline(
                        y=-np.log10(results["alpha"]),
                        line_dash="dash",
                        line_color="red",
                    )

                    plots[f"volcano_{method}"] = fig

            # Ranking plots
            ranking_results = results.get("ranking_results", {})
            for method, ranking_result in ranking_results.items():
                if "ranked_features" in ranking_result:
                    ranked_df = pd.DataFrame(ranking_result["ranked_features"])

                    # Top features plot
                    top_features = ranked_df.head(20)
                    fig = px.bar(
                        top_features,
                        x="gene",
                        y="score",
                        title=f"Top Features - {method}",
                        labels={"gene": "Gene", "score": "Score"},
                    )
                    fig.update_xaxes(tickangle=45)
                    plots[f"ranking_{method}"] = fig

            # Method comparison plot
            if len(results["method_results"]) > 1:
                comparison_data = []
                for method, method_result in results["method_results"].items():
                    if "error" not in method_result:
                        n_sig = len(
                            method_result.get("significant_features_adjusted", [])
                        )
                        comparison_data.append(
                            {"method": method, "n_significant": n_sig}
                        )

                if comparison_data:
                    comparison_df = pd.DataFrame(comparison_data)
                    fig = px.bar(
                        comparison_df,
                        x="method",
                        y="n_significant",
                        title="Significant Features by Method",
                        labels={
                            "method": "Method",
                            "n_significant": "Number of Significant Features",
                        },
                    )
                    plots["method_comparison"] = fig

        except ImportError:
            logger.warning("Plotly not available, skipping analysis plots")

        return plots

    def get_significant_features(
        self, method: str = None, top_n: int = 50
    ) -> Dict[str, Any]:
        """
        Get significant features from analysis.

        Args:
            method: Specific method to use (if None, use all)
            top_n: Number of top features to return

        Returns:
            Significant features dictionary
        """
        if not self.analysis_results:
            return {"error": "No analysis results available"}

        if method is None:
            # Return significant features from all methods
            significant_features = {}
            for method_name, method_result in self.analysis_results[
                "method_results"
            ].items():
                if "error" not in method_result:
                    if "significant_features_adjusted" in method_result:
                        significant = method_result["significant_features_adjusted"]
                    elif "significant_features" in method_result:
                        significant = method_result["significant_features"]
                    else:
                        significant = []

                    significant_features[method_name] = significant[:top_n]

            return significant_features
        else:
            # Return significant features from specific method
            if method not in self.analysis_results["method_results"]:
                return {"error": f"Method {method} not found"}

            method_result = self.analysis_results["method_results"][method]
            if "error" in method_result:
                return {"error": method_result["error"]}

            if "significant_features_adjusted" in method_result:
                significant = method_result["significant_features_adjusted"]
            elif "significant_features" in method_result:
                significant = method_result["significant_features"]
            else:
                significant = []

            return {method: significant[:top_n]}

    def get_top_features(self, method: str = None, top_n: int = 20) -> Dict[str, Any]:
        """
        Get top ranked features from analysis.

        Args:
            method: Specific method to use (if None, use all)
            top_n: Number of top features to return

        Returns:
            Top features dictionary
        """
        if not self.analysis_results:
            return {"error": "No analysis results available"}

        ranking_results = self.analysis_results.get("ranking_results", {})

        if method is None:
            # Return top features from all methods
            top_features = {}
            for method_name, ranking_result in ranking_results.items():
                if "ranked_features" in ranking_result:
                    ranked_features = ranking_result["ranked_features"][:top_n]
                    top_features[method_name] = ranked_features

            return top_features
        else:
            # Return top features from specific method
            if method not in ranking_results:
                return {"error": f"Method {method} not found"}

            ranking_result = ranking_results[method]
            if "ranked_features" in ranking_result:
                ranked_features = ranking_result["ranked_features"][:top_n]
                return {method: ranked_features}
            else:
                return {"error": f"No ranking results for method {method}"}

    def save_analysis_results(self, output_path: str, format: str = "json") -> str:
        """
        Save analysis results to file.

        Args:
            output_path: Output file path
            format: Output format

        Returns:
            Path to saved file
        """
        if not self.analysis_results:
            raise ValueError("No analysis results to save")

        try:
            if format.lower() == "json":
                import json

                with open(output_path, "w") as f:
                    json.dump(self.analysis_results, f, indent=2, default=str)
            elif format.lower() == "csv":
                # Save significant features as CSV
                significant_features = self.get_significant_features()
                all_features = []
                for method, features in significant_features.items():
                    for feature in features:
                        all_features.append({"method": method, "gene": feature})

                if all_features:
                    df = pd.DataFrame(all_features)
                    df.to_csv(output_path, index=False)
                else:
                    # Create empty CSV with headers
                    pd.DataFrame(columns=["method", "gene"]).to_csv(
                        output_path, index=False
                    )
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Analysis results saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save analysis results: {str(e)}")
            raise

    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        Get analysis summary.

        Returns:
            Analysis summary dictionary
        """
        if not self.analysis_results:
            return {"status": "No analysis performed"}

        return self.analysis_results.get("summary", {"status": "unknown"})

    def welch_ttest(self, expr: pd.DataFrame, labels: pd.Series) -> pd.DataFrame:
        """
        Perform Welch t-test (from the blueprint example).

        Args:
            expr: Expression data matrix
            labels: Sample labels

        Returns:
            T-test results DataFrame
        """
        from scipy import stats

        classes = labels.unique()
        assert len(classes) == 2, "Welch t-test is for binary tasks."

        g0 = expr.loc[:, labels == classes[0]]
        g1 = expr.loc[:, labels == classes[1]]

        t = stats.ttest_ind(g1, g0, equal_var=False, axis=1, nan_policy="omit")
        log2fc = np.log2(g1.mean(axis=1) + 1e-9) - np.log2(g0.mean(axis=1) + 1e-9)

        res = pd.DataFrame({"gene": expr.index, "pvalue": t.pvalue, "log2fc": log2fc})
        res = res.sort_values("pvalue").reset_index(drop=True)

        m = len(res)
        res["fdr"] = (res["pvalue"] * m / (np.arange(m) + 1)).clip(upper=1.0)

        return res.set_index("gene")
