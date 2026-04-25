"""
Statistical analysis utilities for biomarker identification.
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import kruskal, mannwhitneyu, pearsonr, spearmanr
from sklearn.preprocessing import LabelEncoder
from statsmodels.stats.multitest import multipletests

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


def _resolve_multipletests_method(fdr_method: Optional[str]) -> str:
    """Map API / config names (e.g. benjamini_hochberg) to statsmodels ``method``."""
    if not fdr_method:
        return "fdr_bh"
    key = str(fdr_method).lower().replace("-", "_").strip()
    mapping = {
        "benjamini_hochberg": "fdr_bh",
        "fdr_bh": "fdr_bh",
        "bh": "fdr_bh",
        "bonferroni": "bonferroni",
        "holm": "holm",
        "hommel": "hommel",
        "sidak": "sidak",
        "holm_sidak": "holm-sidak",
        "fdr_by": "fdr_by",
        "fdr_tsbh": "fdr_tsbh",
        "fdr_tsbky": "fdr_tsbky",
        "fdr_gbs": "fdr_gbs",
    }
    return mapping.get(key, "fdr_bh")


class StatisticalAnalysis:
    """
    Handles statistical analysis for biomarker identification.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the statistical analysis module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.analysis_results = {}
        self.significant_features = []

    def differential_expression_analysis(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        method: str = "t_test",
        alpha: float = 0.05,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Perform differential expression analysis.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            method: Statistical test method
            alpha: Significance level
            **kwargs: Additional method-specific parameters

        Returns:
            Differential expression analysis results
        """
        try:
            common = expression_data.columns.intersection(labels.index)
            if len(common) == 0:
                raise ValueError(
                    "No overlapping sample IDs between expression columns and labels index"
                )
            expression_data = expression_data.loc[:, common]
            labels = labels.loc[common]

            if method == "t_test":
                results = self._t_test_analysis(
                    expression_data, labels, alpha, **kwargs
                )
            elif method == "wilcoxon":
                results = self._wilcoxon_analysis(
                    expression_data, labels, alpha, **kwargs
                )
            elif method == "anova":
                results = self._anova_analysis(expression_data, labels, alpha, **kwargs)
            elif method == "kruskal":
                results = self._kruskal_analysis(
                    expression_data, labels, alpha, **kwargs
                )
            elif method == "correlation":
                results = self._correlation_analysis(
                    expression_data, labels, alpha, **kwargs
                )
            elif method == "regression":
                results = self._regression_analysis(
                    expression_data, labels, alpha, **kwargs
                )
            else:
                raise ValueError(f"Unknown statistical method: {method}")

            self.analysis_results[method] = results
            logger.info(f"Differential expression analysis completed using {method}")

            return results

        except Exception as e:
            logger.error(
                f"Failed to perform differential expression analysis: {str(e)}"
            )
            raise

    def _t_test_analysis(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        alpha: float = 0.05,
        test_type: str = "independent",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        T-test analysis for differential expression.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            alpha: Significance level
            test_type: Type of t-test ('independent' or 'paired')
            **kwargs: Absorbs pipeline kwargs (e.g. fdr_method) not used here yet.

        Returns:
            T-test analysis results
        """
        # Handle binary classification
        if len(labels.unique()) != 2:
            raise ValueError("T-test requires exactly 2 groups")

        unique_labels = sorted(labels.unique())
        group1, group2 = unique_labels[0], unique_labels[1]

        results = {
            "method": "t_test",
            "test_type": test_type,
            "alpha": alpha,
            "groups": [group1, group2],
            "statistics": {},
            "significant_features": [],
            "effect_sizes": {},
        }

        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]

            # Split data by groups
            group1_data = gene_data[labels == group1]
            group2_data = gene_data[labels == group2]

            # Perform t-test
            if test_type == "independent":
                t_stat, p_value = stats.ttest_ind(group1_data, group2_data)
            else:
                # Paired t-test (requires same order)
                t_stat, p_value = stats.ttest_rel(group1_data, group2_data)

            # Calculate effect size (Cohen's d)
            pooled_std = np.sqrt(
                (
                    (len(group1_data) - 1) * group1_data.var()
                    + (len(group2_data) - 1) * group2_data.var()
                )
                / (len(group1_data) + len(group2_data) - 2)
            )
            cohens_d = (group1_data.mean() - group2_data.mean()) / pooled_std

            # Store results
            results["statistics"][gene] = {
                "t_statistic": float(t_stat),
                "p_value": float(p_value),
                "group1_mean": float(group1_data.mean()),
                "group2_mean": float(group2_data.mean()),
                "group1_std": float(group1_data.std()),
                "group2_std": float(group2_data.std()),
                "n_group1": len(group1_data),
                "n_group2": len(group2_data),
            }

            results["effect_sizes"][gene] = float(cohens_d)

            if p_value < alpha:
                results["significant_features"].append(gene)

        # Multiple testing correction
        p_values = [
            results["statistics"][gene]["p_value"] for gene in expression_data.index
        ]
        _, p_adjusted, _, _ = multipletests(
            p_values,
            method=_resolve_multipletests_method(kwargs.get("fdr_method")),
            alpha=alpha,
        )

        # Update with adjusted p-values
        for i, gene in enumerate(expression_data.index):
            results["statistics"][gene]["p_adjusted"] = float(p_adjusted[i])

        # Significant features after correction
        results["significant_features_adjusted"] = [
            gene
            for gene in expression_data.index
            if results["statistics"][gene]["p_adjusted"] < alpha
        ]

        results["n_significant"] = len(results["significant_features"])
        results["n_significant_adjusted"] = len(
            results["significant_features_adjusted"]
        )

        return results

    def _wilcoxon_analysis(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        alpha: float = 0.05,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Wilcoxon rank-sum test analysis for differential expression.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            alpha: Significance level

        Returns:
            Wilcoxon analysis results
        """
        # Handle binary classification
        if len(labels.unique()) != 2:
            raise ValueError("Wilcoxon test requires exactly 2 groups")

        unique_labels = sorted(labels.unique())
        group1, group2 = unique_labels[0], unique_labels[1]

        results = {
            "method": "wilcoxon",
            "alpha": alpha,
            "groups": [group1, group2],
            "statistics": {},
            "significant_features": [],
            "effect_sizes": {},
        }

        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]

            # Split data by groups
            group1_data = gene_data[labels == group1]
            group2_data = gene_data[labels == group2]

            # Perform Wilcoxon test
            u_stat, p_value = mannwhitneyu(
                group1_data, group2_data, alternative="two-sided"
            )

            # Calculate effect size (Cliff's delta)
            n1, n2 = len(group1_data), len(group2_data)
            cliff_delta = (2 * u_stat) / (n1 * n2) - 1

            # Store results
            results["statistics"][gene] = {
                "u_statistic": float(u_stat),
                "p_value": float(p_value),
                "group1_median": float(group1_data.median()),
                "group2_median": float(group2_data.median()),
                "group1_mean": float(group1_data.mean()),
                "group2_mean": float(group2_data.mean()),
                "n_group1": len(group1_data),
                "n_group2": len(group2_data),
            }

            results["effect_sizes"][gene] = float(cliff_delta)

            if p_value < alpha:
                results["significant_features"].append(gene)

        # Multiple testing correction
        p_values = [
            results["statistics"][gene]["p_value"] for gene in expression_data.index
        ]
        _, p_adjusted, _, _ = multipletests(
            p_values,
            method=_resolve_multipletests_method(kwargs.get("fdr_method")),
            alpha=alpha,
        )

        # Update with adjusted p-values
        for i, gene in enumerate(expression_data.index):
            results["statistics"][gene]["p_adjusted"] = float(p_adjusted[i])

        # Significant features after correction
        results["significant_features_adjusted"] = [
            gene
            for gene in expression_data.index
            if results["statistics"][gene]["p_adjusted"] < alpha
        ]

        results["n_significant"] = len(results["significant_features"])
        results["n_significant_adjusted"] = len(
            results["significant_features_adjusted"]
        )

        return results

    def _anova_analysis(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        alpha: float = 0.05,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        One-way ANOVA analysis for differential expression.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            alpha: Significance level

        Returns:
            ANOVA analysis results
        """
        if len(labels.unique()) < 2:
            raise ValueError("ANOVA requires at least 2 groups")

        unique_labels = sorted(labels.unique())

        results = {
            "method": "anova",
            "alpha": alpha,
            "groups": unique_labels,
            "statistics": {},
            "significant_features": [],
            "effect_sizes": {},
        }

        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]

            # Group data by labels
            groups = [gene_data[labels == label] for label in unique_labels]

            # Perform one-way ANOVA
            f_stat, p_value = stats.f_oneway(*groups)

            # Calculate effect size (eta-squared)
            total_ss = np.sum((gene_data - gene_data.mean()) ** 2)
            between_ss = sum(
                len(group) * (group.mean() - gene_data.mean()) ** 2 for group in groups
            )
            eta_squared = between_ss / total_ss if total_ss > 0 else 0

            # Store results
            results["statistics"][gene] = {
                "f_statistic": float(f_stat),
                "p_value": float(p_value),
                "group_means": {
                    label: float(gene_data[labels == label].mean())
                    for label in unique_labels
                },
                "group_stds": {
                    label: float(gene_data[labels == label].std())
                    for label in unique_labels
                },
                "group_sizes": {
                    label: len(gene_data[labels == label]) for label in unique_labels
                },
            }

            results["effect_sizes"][gene] = float(eta_squared)

            if p_value < alpha:
                results["significant_features"].append(gene)

        # Multiple testing correction
        p_values = [
            results["statistics"][gene]["p_value"] for gene in expression_data.index
        ]
        _, p_adjusted, _, _ = multipletests(
            p_values,
            method=_resolve_multipletests_method(kwargs.get("fdr_method")),
            alpha=alpha,
        )

        # Update with adjusted p-values
        for i, gene in enumerate(expression_data.index):
            results["statistics"][gene]["p_adjusted"] = float(p_adjusted[i])

        # Significant features after correction
        results["significant_features_adjusted"] = [
            gene
            for gene in expression_data.index
            if results["statistics"][gene]["p_adjusted"] < alpha
        ]

        results["n_significant"] = len(results["significant_features"])
        results["n_significant_adjusted"] = len(
            results["significant_features_adjusted"]
        )

        return results

    def _kruskal_analysis(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        alpha: float = 0.05,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Kruskal-Wallis H-test analysis for differential expression.

        Args:
            expression_data: Expression data matrix
            labels: Target labels
            alpha: Significance level

        Returns:
            Kruskal-Wallis analysis results
        """
        if len(labels.unique()) < 2:
            raise ValueError("Kruskal-Wallis test requires at least 2 groups")

        unique_labels = sorted(labels.unique())

        results = {
            "method": "kruskal",
            "alpha": alpha,
            "groups": unique_labels,
            "statistics": {},
            "significant_features": [],
            "effect_sizes": {},
        }

        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]

            # Group data by labels
            groups = [gene_data[labels == label] for label in unique_labels]

            # Perform Kruskal-Wallis test
            h_stat, p_value = kruskal(*groups)

            # Calculate effect size (epsilon-squared)
            n_total = len(gene_data)
            epsilon_squared = (h_stat - len(unique_labels) + 1) / (
                n_total - len(unique_labels)
            )
            epsilon_squared = max(0, epsilon_squared)  # Ensure non-negative

            # Store results
            results["statistics"][gene] = {
                "h_statistic": float(h_stat),
                "p_value": float(p_value),
                "group_medians": {
                    label: float(gene_data[labels == label].median())
                    for label in unique_labels
                },
                "group_means": {
                    label: float(gene_data[labels == label].mean())
                    for label in unique_labels
                },
                "group_sizes": {
                    label: len(gene_data[labels == label]) for label in unique_labels
                },
            }

            results["effect_sizes"][gene] = float(epsilon_squared)

            if p_value < alpha:
                results["significant_features"].append(gene)

        # Multiple testing correction
        p_values = [
            results["statistics"][gene]["p_value"] for gene in expression_data.index
        ]
        _, p_adjusted, _, _ = multipletests(
            p_values,
            method=_resolve_multipletests_method(kwargs.get("fdr_method")),
            alpha=alpha,
        )

        # Update with adjusted p-values
        for i, gene in enumerate(expression_data.index):
            results["statistics"][gene]["p_adjusted"] = float(p_adjusted[i])

        # Significant features after correction
        results["significant_features_adjusted"] = [
            gene
            for gene in expression_data.index
            if results["statistics"][gene]["p_adjusted"] < alpha
        ]

        results["n_significant"] = len(results["significant_features"])
        results["n_significant_adjusted"] = len(
            results["significant_features_adjusted"]
        )

        return results

    def _correlation_analysis(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        alpha: float = 0.05,
        method: str = "pearson",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Correlation analysis for continuous outcomes.

        Args:
            expression_data: Expression data matrix
            labels: Target labels (continuous)
            alpha: Significance level
            method: Correlation method ('pearson' or 'spearman')

        Returns:
            Correlation analysis results
        """
        # Convert labels to numeric if needed
        if labels.dtype == "object":
            le = LabelEncoder()
            labels_numeric = le.fit_transform(labels)
        else:
            labels_numeric = labels

        results = {
            "method": f"correlation_{method}",
            "alpha": alpha,
            "statistics": {},
            "significant_features": [],
            "effect_sizes": {},
        }

        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]

            # Calculate correlation
            if method == "pearson":
                corr, p_value = pearsonr(gene_data, labels_numeric)
            else:
                corr, p_value = spearmanr(gene_data, labels_numeric)

            # Store results
            results["statistics"][gene] = {
                "correlation": float(corr),
                "p_value": float(p_value),
                "mean_expression": float(gene_data.mean()),
                "std_expression": float(gene_data.std()),
            }

            results["effect_sizes"][gene] = abs(float(corr))

            if p_value < alpha:
                results["significant_features"].append(gene)

        # Multiple testing correction
        p_values = [
            results["statistics"][gene]["p_value"] for gene in expression_data.index
        ]
        _, p_adjusted, _, _ = multipletests(
            p_values,
            method=_resolve_multipletests_method(kwargs.get("fdr_method")),
            alpha=alpha,
        )

        # Update with adjusted p-values
        for i, gene in enumerate(expression_data.index):
            results["statistics"][gene]["p_adjusted"] = float(p_adjusted[i])

        # Significant features after correction
        results["significant_features_adjusted"] = [
            gene
            for gene in expression_data.index
            if results["statistics"][gene]["p_adjusted"] < alpha
        ]

        results["n_significant"] = len(results["significant_features"])
        results["n_significant_adjusted"] = len(
            results["significant_features_adjusted"]
        )

        return results

    def _regression_analysis(
        self,
        expression_data: pd.DataFrame,
        labels: pd.Series,
        alpha: float = 0.05,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Linear regression analysis for continuous outcomes.

        Args:
            expression_data: Expression data matrix
            labels: Target labels (continuous)
            alpha: Significance level

        Returns:
            Regression analysis results
        """
        from sklearn.linear_model import LinearRegression
        from sklearn.metrics import r2_score

        # Convert labels to numeric if needed
        if labels.dtype == "object":
            le = LabelEncoder()
            labels_numeric = le.fit_transform(labels)
        else:
            labels_numeric = labels

        results = {
            "method": "regression",
            "alpha": alpha,
            "statistics": {},
            "significant_features": [],
            "effect_sizes": {},
        }

        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]

            # Fit linear regression
            X = gene_data.values.reshape(-1, 1)
            y = labels_numeric.values

            model = LinearRegression()
            model.fit(X, y)

            # Calculate predictions and R-squared
            y_pred = model.predict(X)
            r_squared = r2_score(y, y_pred)

            # Calculate p-value using F-test
            n = len(y)
            p = 1  # Number of predictors
            f_stat = (r_squared / p) / ((1 - r_squared) / (n - p - 1))
            p_value = 1 - stats.f.cdf(f_stat, p, n - p - 1)

            # Store results
            results["statistics"][gene] = {
                "coefficient": float(model.coef_[0]),
                "intercept": float(model.intercept_),
                "r_squared": float(r_squared),
                "f_statistic": float(f_stat),
                "p_value": float(p_value),
                "mean_expression": float(gene_data.mean()),
                "std_expression": float(gene_data.std()),
            }

            results["effect_sizes"][gene] = float(r_squared)

            if p_value < alpha:
                results["significant_features"].append(gene)

        # Multiple testing correction
        p_values = [
            results["statistics"][gene]["p_value"] for gene in expression_data.index
        ]
        _, p_adjusted, _, _ = multipletests(
            p_values,
            method=_resolve_multipletests_method(kwargs.get("fdr_method")),
            alpha=alpha,
        )

        # Update with adjusted p-values
        for i, gene in enumerate(expression_data.index):
            results["statistics"][gene]["p_adjusted"] = float(p_adjusted[i])

        # Significant features after correction
        results["significant_features_adjusted"] = [
            gene
            for gene in expression_data.index
            if results["statistics"][gene]["p_adjusted"] < alpha
        ]

        results["n_significant"] = len(results["significant_features"])
        results["n_significant_adjusted"] = len(
            results["significant_features_adjusted"]
        )

        return results

    def volcano_plot_data(
        self,
        analysis_results: Dict[str, Any],
        fold_change_threshold: float = 1.5,
        p_value_threshold: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Prepare data for volcano plot visualization.

        Args:
            analysis_results: Results from differential expression analysis
            fold_change_threshold: Log2 fold change threshold
            p_value_threshold: P-value threshold

        Returns:
            Volcano plot data
        """
        method = analysis_results["method"]

        if method in ["t_test", "wilcoxon"]:
            # Binary comparison
            group1, group2 = analysis_results["groups"]
            volcano_data = []

            for gene in analysis_results["statistics"].keys():
                stats = analysis_results["statistics"][gene]

                # Calculate fold change
                if method == "t_test":
                    fold_change = stats["group1_mean"] - stats["group2_mean"]
                else:
                    fold_change = stats["group1_median"] - stats["group2_median"]

                # Log2 fold change
                log2_fc = np.log2(abs(fold_change) + 1) * np.sign(fold_change)

                # P-value
                p_value = stats.get("p_adjusted", stats["p_value"])

                # Significance
                significant = (abs(log2_fc) >= np.log2(fold_change_threshold)) and (
                    p_value <= p_value_threshold
                )

                volcano_data.append(
                    {
                        "gene": gene,
                        "log2_fold_change": float(log2_fc),
                        "p_value": float(p_value),
                        "significant": significant,
                        "effect_size": float(analysis_results["effect_sizes"][gene]),
                    }
                )

        elif method in ["anova", "kruskal"]:
            # Multiple groups - use effect size vs p-value
            volcano_data = []

            for gene in analysis_results["statistics"].keys():
                stats = analysis_results["statistics"][gene]
                p_value = stats.get("p_adjusted", stats["p_value"])
                effect_size = analysis_results["effect_sizes"][gene]

                # Significance based on effect size and p-value
                significant = (effect_size >= 0.1) and (p_value <= p_value_threshold)

                volcano_data.append(
                    {
                        "gene": gene,
                        "effect_size": float(effect_size),
                        "p_value": float(p_value),
                        "significant": significant,
                        "f_statistic": float(
                            stats.get("f_statistic", stats.get("h_statistic", 0))
                        ),
                    }
                )

        elif method.startswith("correlation"):
            # Correlation analysis
            volcano_data = []

            for gene in analysis_results["statistics"].keys():
                stats = analysis_results["statistics"][gene]
                p_value = stats.get("p_adjusted", stats["p_value"])
                correlation = stats["correlation"]

                # Significance
                significant = (abs(correlation) >= 0.3) and (
                    p_value <= p_value_threshold
                )

                volcano_data.append(
                    {
                        "gene": gene,
                        "correlation": float(correlation),
                        "p_value": float(p_value),
                        "significant": significant,
                        "abs_correlation": abs(float(correlation)),
                    }
                )

        else:
            # Default case
            volcano_data = []

            for gene in analysis_results["statistics"].keys():
                stats = analysis_results["statistics"][gene]
                p_value = stats.get("p_adjusted", stats["p_value"])
                effect_size = analysis_results["effect_sizes"][gene]

                significant = p_value <= p_value_threshold

                volcano_data.append(
                    {
                        "gene": gene,
                        "effect_size": float(effect_size),
                        "p_value": float(p_value),
                        "significant": significant,
                    }
                )

        return {
            "method": method,
            "data": volcano_data,
            "n_significant": sum(1 for item in volcano_data if item["significant"]),
            "fold_change_threshold": fold_change_threshold,
            "p_value_threshold": p_value_threshold,
        }

    def rank_features(
        self, analysis_results: Dict[str, Any], ranking_method: str = "combined"
    ) -> Dict[str, Any]:
        """
        Rank features based on statistical results.

        Args:
            analysis_results: Results from differential expression analysis
            ranking_method: Method for ranking ('p_value', 'effect_size', 'combined')

        Returns:
            Feature ranking results
        """
        method = analysis_results["method"]

        # Prepare ranking data
        ranking_data = []

        for gene in analysis_results["statistics"].keys():
            stats = analysis_results["statistics"][gene]
            effect_size = analysis_results["effect_sizes"][gene]

            # Get p-value (prefer adjusted)
            p_value = stats.get("p_adjusted", stats["p_value"])

            # Calculate ranking score
            if ranking_method == "p_value":
                score = -np.log10(p_value + 1e-10)  # Avoid log(0)
            elif ranking_method == "effect_size":
                score = abs(effect_size)
            elif ranking_method == "combined":
                # Combine p-value and effect size
                p_score = -np.log10(p_value + 1e-10)
                effect_score = abs(effect_size)
                score = p_score * effect_score
            else:
                score = 0

            ranking_data.append(
                {
                    "gene": gene,
                    "score": float(score),
                    "p_value": float(p_value),
                    "effect_size": float(effect_size),
                    "significant": gene
                    in analysis_results.get("significant_features_adjusted", []),
                }
            )

        # Sort by score
        ranking_data.sort(key=lambda x: x["score"], reverse=True)

        # Add ranks
        for i, item in enumerate(ranking_data):
            item["rank"] = i + 1

        return {
            "method": method,
            "ranking_method": ranking_method,
            "ranked_features": ranking_data,
            "top_features": ranking_data[: min(50, len(ranking_data))],
        }

    def get_analysis_summary(self) -> Dict[str, Any]:
        """
        Get summary of statistical analysis results.

        Returns:
            Analysis summary dictionary
        """
        if not self.analysis_results:
            return {"status": "No analysis performed"}

        summary = {
            "methods_applied": list(self.analysis_results.keys()),
            "total_significant_features": sum(
                len(results.get("significant_features_adjusted", []))
                for results in self.analysis_results.values()
            ),
            "method_results": {},
        }

        for method, results in self.analysis_results.items():
            summary["method_results"][method] = {
                "n_significant": results.get("n_significant", 0),
                "n_significant_adjusted": results.get("n_significant_adjusted", 0),
                "alpha": results.get("alpha", 0.05),
            }

        return summary

    def save_analysis_results(self, output_path: str) -> str:
        """
        Save statistical analysis results to file.

        Args:
            output_path: Output file path

        Returns:
            Path to saved file
        """
        import json

        try:
            with open(output_path, "w") as f:
                json.dump(self.analysis_results, f, indent=2, default=str)

            logger.info(f"Analysis results saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save analysis results: {str(e)}")
            raise
