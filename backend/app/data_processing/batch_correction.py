"""
Batch correction utilities for expression data.
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class BatchCorrection:
    """
    Handles batch correction for expression data.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the batch correction module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.correction_params = {}
        self.corrected_data = None
        self.batch_effects = None

    def detect_batch_effects(
        self,
        expression_data: pd.DataFrame,
        batch_info: pd.Series,
        covariates: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Detect batch effects in expression data.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample
            covariates: Additional covariates to consider

        Returns:
            Batch effect detection results
        """
        try:
            results = {}

            # Basic batch statistics
            batch_stats = self._calculate_batch_statistics(expression_data, batch_info)
            results["batch_statistics"] = batch_stats

            # PCA-based batch effect detection
            pca_results = self._pca_batch_detection(expression_data, batch_info)
            results["pca_analysis"] = pca_results

            # ANOVA-based batch effect detection
            anova_results = self._anova_batch_detection(expression_data, batch_info)
            results["anova_analysis"] = anova_results

            # Correlation analysis
            correlation_results = self._correlation_batch_analysis(
                expression_data, batch_info, covariates
            )
            results["correlation_analysis"] = correlation_results

            # Overall batch effect score
            overall_score = self._calculate_batch_effect_score(results)
            results["overall_batch_effect_score"] = overall_score

            logger.info(f"Batch effects detected with score: {overall_score:.3f}")

            return results

        except Exception as e:
            logger.error(f"Failed to detect batch effects: {str(e)}")
            raise

    def _calculate_batch_statistics(
        self, expression_data: pd.DataFrame, batch_info: pd.Series
    ) -> Dict[str, Any]:
        """
        Calculate basic batch statistics.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample

        Returns:
            Batch statistics dictionary
        """
        batch_stats = {}

        # Number of batches
        unique_batches = batch_info.unique()
        batch_stats["n_batches"] = len(unique_batches)
        batch_stats["batch_sizes"] = batch_info.value_counts().to_dict()

        # Mean expression per batch
        batch_means = {}
        batch_stds = {}

        for batch in unique_batches:
            batch_samples = batch_info[batch_info == batch].index
            batch_data = expression_data[batch_samples]
            batch_means[batch] = float(batch_data.mean().mean())
            batch_stds[batch] = float(batch_data.std().mean())

        batch_stats["batch_means"] = batch_means
        batch_stats["batch_stds"] = batch_stds

        # Coefficient of variation across batches
        cv_values = []
        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]
            batch_means_gene = []
            for batch in unique_batches:
                batch_samples = batch_info[batch_info == batch].index
                batch_mean = gene_data[batch_samples].mean()
                batch_means_gene.append(batch_mean)
            cv = (
                np.std(batch_means_gene) / np.mean(batch_means_gene)
                if np.mean(batch_means_gene) > 0
                else 0
            )
            cv_values.append(cv)

        batch_stats["mean_cv_across_batches"] = float(np.mean(cv_values))
        batch_stats["cv_distribution"] = {
            "mean": float(np.mean(cv_values)),
            "std": float(np.std(cv_values)),
            "median": float(np.median(cv_values)),
            "q25": float(np.percentile(cv_values, 25)),
            "q75": float(np.percentile(cv_values, 75)),
        }

        return batch_stats

    def _pca_batch_detection(
        self,
        expression_data: pd.DataFrame,
        batch_info: pd.Series,
        n_components: int = 10,
    ) -> Dict[str, Any]:
        """
        Detect batch effects using PCA.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample
            n_components: Number of PCA components to analyze

        Returns:
            PCA-based batch detection results
        """
        # Standardize data
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(expression_data.T)

        # Perform PCA
        pca = PCA(n_components=min(n_components, scaled_data.shape[1]))
        pca_result = pca.fit_transform(scaled_data)

        # Calculate batch effect scores for each component
        batch_scores = []
        for i in range(pca_result.shape[1]):
            component_data = pca_result[:, i]
            batch_effect_score = self._calculate_component_batch_score(
                component_data, batch_info
            )
            batch_scores.append(batch_effect_score)

        # Overall batch effect score
        overall_score = np.mean(batch_scores)

        return {
            "n_components": n_components,
            "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
            "cumulative_variance_ratio": np.cumsum(
                pca.explained_variance_ratio_
            ).tolist(),
            "batch_scores_per_component": batch_scores,
            "overall_batch_score": float(overall_score),
            "top_batch_components": [
                i for i, score in enumerate(batch_scores) if score > 0.1
            ],
        }

    def _calculate_component_batch_score(
        self, component_data: np.ndarray, batch_info: pd.Series
    ) -> float:
        """
        Calculate batch effect score for a single component.

        Args:
            component_data: Component values
            batch_info: Batch information for each sample

        Returns:
            Batch effect score
        """
        unique_batches = batch_info.unique()

        if len(unique_batches) < 2:
            return 0.0

        # Calculate between-batch variance
        overall_mean = np.mean(component_data)
        between_batch_var = 0

        for batch in unique_batches:
            batch_samples = batch_info[batch_info == batch].index
            batch_mean = np.mean(component_data[batch_samples])
            batch_size = len(batch_samples)
            between_batch_var += batch_size * (batch_mean - overall_mean) ** 2

        between_batch_var /= len(component_data)

        # Calculate total variance
        total_var = np.var(component_data)

        # Calculate batch effect score (proportion of variance explained by batch)
        if total_var > 0:
            batch_score = between_batch_var / total_var
        else:
            batch_score = 0.0

        return float(batch_score)

    def _anova_batch_detection(
        self, expression_data: pd.DataFrame, batch_info: pd.Series, alpha: float = 0.05
    ) -> Dict[str, Any]:
        """
        Detect batch effects using ANOVA.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample
            alpha: Significance level

        Returns:
            ANOVA-based batch detection results
        """
        from scipy import stats

        significant_genes = []
        p_values = []
        f_values = []

        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]

            # Group data by batch
            batch_groups = []
            for batch in batch_info.unique():
                batch_samples = batch_info[batch_info == batch].index
                batch_data = gene_data[batch_samples].values
                batch_groups.append(batch_data)

            # Perform one-way ANOVA
            try:
                f_stat, p_val = stats.f_oneway(*batch_groups)
                f_values.append(f_stat)
                p_values.append(p_val)

                if p_val < alpha:
                    significant_genes.append(gene)

            except:
                f_values.append(np.nan)
                p_values.append(1.0)

        # Calculate FDR
        from statsmodels.stats.multitest import multipletests

        _, p_adjusted, _, _ = multipletests(p_values, method="fdr_bh")

        significant_genes_fdr = [
            gene
            for gene, p_adj in zip(expression_data.index, p_adjusted)
            if p_adj < alpha
        ]

        return {
            "n_significant_genes": len(significant_genes),
            "n_significant_genes_fdr": len(significant_genes_fdr),
            "proportion_significant": len(significant_genes) / len(expression_data),
            "proportion_significant_fdr": len(significant_genes_fdr)
            / len(expression_data),
            "mean_f_statistic": float(np.nanmean(f_values)),
            "median_p_value": float(np.nanmedian(p_values)),
            "significant_genes": significant_genes,
            "significant_genes_fdr": significant_genes_fdr,
        }

    def _correlation_batch_analysis(
        self,
        expression_data: pd.DataFrame,
        batch_info: pd.Series,
        covariates: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Analyze correlation between expression and batch/covariates.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample
            covariates: Additional covariates

        Returns:
            Correlation analysis results
        """
        # Create batch dummy variables
        batch_dummies = pd.get_dummies(batch_info, prefix="batch")

        # Combine batch and covariates
        if covariates is not None:
            design_matrix = pd.concat([batch_dummies, covariates], axis=1)
        else:
            design_matrix = batch_dummies

        # Calculate correlations
        correlations = {}
        for col in design_matrix.columns:
            col_correlations = []
            for gene in expression_data.index:
                gene_data = expression_data.loc[gene]
                correlation = np.corrcoef(gene_data, design_matrix[col])[0, 1]
                if not np.isnan(correlation):
                    col_correlations.append(abs(correlation))

            correlations[col] = {
                "mean_correlation": float(np.mean(col_correlations)),
                "median_correlation": float(np.median(col_correlations)),
                "max_correlation": float(np.max(col_correlations)),
                "n_high_correlation": len([c for c in col_correlations if c > 0.3]),
            }

        return {
            "correlations": correlations,
            "overall_batch_correlation": float(
                np.mean([v["mean_correlation"] for v in correlations.values()])
            ),
        }

    def _calculate_batch_effect_score(self, results: Dict[str, Any]) -> float:
        """
        Calculate overall batch effect score.

        Args:
            results: Batch effect detection results

        Returns:
            Overall batch effect score
        """
        scores = []

        # PCA score
        if "pca_analysis" in results:
            pca_score = results["pca_analysis"]["overall_batch_score"]
            scores.append(pca_score)

        # ANOVA score
        if "anova_analysis" in results:
            anova_score = results["anova_analysis"]["proportion_significant_fdr"]
            scores.append(anova_score)

        # Correlation score
        if "correlation_analysis" in results:
            corr_score = results["correlation_analysis"]["overall_batch_correlation"]
            scores.append(corr_score)

        # CV score
        if "batch_statistics" in results:
            cv_score = min(
                1.0, results["batch_statistics"]["mean_cv_across_batches"] / 0.5
            )
            scores.append(cv_score)

        return float(np.mean(scores)) if scores else 0.0

    def correct_batch_effects(
        self,
        expression_data: pd.DataFrame,
        batch_info: pd.Series,
        method: str = "combat",
        covariates: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Correct batch effects in expression data.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample
            method: Batch correction method
            covariates: Additional covariates to consider
            **kwargs: Additional method-specific parameters

        Returns:
            Batch-corrected expression data
        """
        try:
            if method == "combat":
                corrected_data = self._combat_correction(
                    expression_data, batch_info, covariates, **kwargs
                )
            elif method == "limma":
                corrected_data = self._limma_correction(
                    expression_data, batch_info, covariates, **kwargs
                )
            elif method == "pca":
                corrected_data = self._pca_correction(
                    expression_data, batch_info, **kwargs
                )
            elif method == "linear_regression":
                corrected_data = self._linear_regression_correction(
                    expression_data, batch_info, covariates, **kwargs
                )
            elif method == "mean_centering":
                corrected_data = self._mean_centering_correction(
                    expression_data, batch_info, **kwargs
                )
            else:
                raise ValueError(f"Unknown batch correction method: {method}")

            self.corrected_data = corrected_data
            logger.info(f"Batch effects corrected using {method} method")

            return corrected_data

        except Exception as e:
            logger.error(f"Failed to correct batch effects: {str(e)}")
            raise

    def _combat_correction(
        self,
        expression_data: pd.DataFrame,
        batch_info: pd.Series,
        covariates: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        ComBat batch correction.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample
            covariates: Additional covariates
            **kwargs: Additional parameters

        Returns:
            ComBat corrected data
        """
        # This is a simplified implementation
        # For full ComBat, consider using pycombat or similar library

        corrected_data = expression_data.copy()

        # Calculate batch means and variances
        batch_means = {}
        batch_vars = {}

        for batch in batch_info.unique():
            batch_samples = batch_info[batch_info == batch].index
            batch_data = expression_data[batch_samples]
            batch_means[batch] = batch_data.mean(axis=1)
            batch_vars[batch] = batch_data.var(axis=1)

        # Calculate global mean and variance
        global_mean = expression_data.mean(axis=1)
        global_var = expression_data.var(axis=1)

        # Apply correction
        for batch in batch_info.unique():
            batch_samples = batch_info[batch_info == batch].index
            batch_mean = batch_means[batch]
            batch_var = batch_vars[batch]

            # Standardize within batch
            batch_data = expression_data[batch_samples]
            standardized = (batch_data.T - batch_mean) / np.sqrt(batch_var)

            # Transform to global scale
            corrected = standardized.T * np.sqrt(global_var) + global_mean

            corrected_data[batch_samples] = corrected

        # Store correction parameters
        self.correction_params["combat"] = {
            "method": "combat",
            "batch_means": {k: v.to_dict() for k, v in batch_means.items()},
            "batch_vars": {k: v.to_dict() for k, v in batch_vars.items()},
            "global_mean": global_mean.to_dict(),
            "global_var": global_var.to_dict(),
        }

        return corrected_data

    def _limma_correction(
        self,
        expression_data: pd.DataFrame,
        batch_info: pd.Series,
        covariates: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Limma batch correction.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample
            covariates: Additional covariates
            **kwargs: Additional parameters

        Returns:
            Limma corrected data
        """
        # Simplified Limma implementation
        # For full implementation, consider using rpy2 with limma R package

        corrected_data = expression_data.copy()

        # Create design matrix
        batch_dummies = pd.get_dummies(batch_info, prefix="batch")
        if covariates is not None:
            design_matrix = pd.concat([batch_dummies, covariates], axis=1)
        else:
            design_matrix = batch_dummies

        # Fit linear model for each gene
        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]

            # Fit linear regression
            model = LinearRegression()
            model.fit(design_matrix, gene_data)

            # Get batch effects
            batch_effects = model.predict(design_matrix)

            # Remove batch effects
            corrected_data.loc[gene] = gene_data - batch_effects + gene_data.mean()

        # Store correction parameters
        self.correction_params["limma"] = {
            "method": "limma",
            "design_matrix_columns": design_matrix.columns.tolist(),
        }

        return corrected_data

    def _pca_correction(
        self,
        expression_data: pd.DataFrame,
        batch_info: pd.Series,
        n_components: int = 10,
        **kwargs,
    ) -> pd.DataFrame:
        """
        PCA-based batch correction.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample
            n_components: Number of components to remove
            **kwargs: Additional parameters

        Returns:
            PCA corrected data
        """
        # Standardize data
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(expression_data.T)

        # Perform PCA
        pca = PCA(n_components=min(n_components, scaled_data.shape[1]))
        pca_result = pca.fit_transform(scaled_data)

        # Identify batch-associated components
        batch_components = []
        for i in range(pca_result.shape[1]):
            component_data = pca_result[:, i]
            batch_score = self._calculate_component_batch_score(
                component_data, batch_info
            )
            if batch_score > 0.1:  # Threshold for batch effect
                batch_components.append(i)

        # Remove batch-associated components
        if batch_components:
            # Reconstruct data without batch components
            pca_result_corrected = pca_result.copy()
            pca_result_corrected[:, batch_components] = 0
            corrected_scaled = pca.inverse_transform(pca_result_corrected)

            # Transform back to original scale
            corrected_data = scaler.inverse_transform(corrected_scaled).T
            corrected_data = pd.DataFrame(
                corrected_data,
                index=expression_data.index,
                columns=expression_data.columns,
            )
        else:
            corrected_data = expression_data.copy()

        # Store correction parameters
        self.correction_params["pca"] = {
            "method": "pca",
            "n_components": n_components,
            "batch_components_removed": batch_components,
            "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        }

        return corrected_data

    def _linear_regression_correction(
        self,
        expression_data: pd.DataFrame,
        batch_info: pd.Series,
        covariates: Optional[pd.DataFrame] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """
        Linear regression-based batch correction.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample
            covariates: Additional covariates
            **kwargs: Additional parameters

        Returns:
            Linear regression corrected data
        """
        corrected_data = expression_data.copy()

        # Create design matrix
        batch_dummies = pd.get_dummies(batch_info, prefix="batch")
        if covariates is not None:
            design_matrix = pd.concat([batch_dummies, covariates], axis=1)
        else:
            design_matrix = batch_dummies

        # Fit linear regression for each gene
        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]

            # Fit linear regression
            model = LinearRegression()
            model.fit(design_matrix, gene_data)

            # Get batch effects
            batch_effects = model.predict(design_matrix)

            # Remove batch effects
            corrected_data.loc[gene] = gene_data - batch_effects + gene_data.mean()

        # Store correction parameters
        self.correction_params["linear_regression"] = {
            "method": "linear_regression",
            "design_matrix_columns": design_matrix.columns.tolist(),
            "coefficients": {
                gene: model.coef_.tolist() for gene in expression_data.index
            },
        }

        return corrected_data

    def _mean_centering_correction(
        self, expression_data: pd.DataFrame, batch_info: pd.Series, **kwargs
    ) -> pd.DataFrame:
        """
        Mean centering batch correction.

        Args:
            expression_data: Expression data matrix
            batch_info: Batch information for each sample
            **kwargs: Additional parameters

        Returns:
            Mean centering corrected data
        """
        corrected_data = expression_data.copy()

        # Calculate batch means
        batch_means = {}
        for batch in batch_info.unique():
            batch_samples = batch_info[batch_info == batch].index
            batch_data = expression_data[batch_samples]
            batch_means[batch] = batch_data.mean(axis=1)

        # Calculate global mean
        global_mean = expression_data.mean(axis=1)

        # Apply correction
        for batch in batch_info.unique():
            batch_samples = batch_info[batch_info == batch].index
            batch_mean = batch_means[batch]

            # Center within batch and shift to global mean
            batch_data = expression_data[batch_samples]
            corrected = batch_data.T - batch_mean + global_mean

            corrected_data[batch_samples] = corrected.T

        # Store correction parameters
        self.correction_params["mean_centering"] = {
            "method": "mean_centering",
            "batch_means": {k: v.to_dict() for k, v in batch_means.items()},
            "global_mean": global_mean.to_dict(),
        }

        return corrected_data

    def evaluate_correction(
        self,
        original_data: pd.DataFrame,
        corrected_data: pd.DataFrame,
        batch_info: pd.Series,
    ) -> Dict[str, Any]:
        """
        Evaluate batch correction effectiveness.

        Args:
            original_data: Original expression data
            corrected_data: Corrected expression data
            batch_info: Batch information for each sample

        Returns:
            Correction evaluation results
        """
        try:
            # Detect batch effects in original data
            original_effects = self.detect_batch_effects(original_data, batch_info)

            # Detect batch effects in corrected data
            corrected_effects = self.detect_batch_effects(corrected_data, batch_info)

            # Calculate improvement
            improvement = {
                "pca_score_improvement": original_effects["pca_analysis"][
                    "overall_batch_score"
                ]
                - corrected_effects["pca_analysis"]["overall_batch_score"],
                "anova_score_improvement": original_effects["anova_analysis"][
                    "proportion_significant_fdr"
                ]
                - corrected_effects["anova_analysis"]["proportion_significant_fdr"],
                "correlation_score_improvement": original_effects[
                    "correlation_analysis"
                ]["overall_batch_correlation"]
                - corrected_effects["correlation_analysis"][
                    "overall_batch_correlation"
                ],
                "overall_score_improvement": original_effects[
                    "overall_batch_effect_score"
                ]
                - corrected_effects["overall_batch_effect_score"],
            }

            evaluation_results = {
                "original_batch_effects": original_effects,
                "corrected_batch_effects": corrected_effects,
                "improvement": improvement,
                "correction_effective": improvement["overall_score_improvement"] > 0.1,
            }

            logger.info(
                f"Batch correction evaluation completed. Improvement: {improvement['overall_score_improvement']:.3f}"
            )

            return evaluation_results

        except Exception as e:
            logger.error(f"Failed to evaluate correction: {str(e)}")
            raise

    def get_correction_summary(self) -> Dict[str, Any]:
        """
        Get summary of batch correction results.

        Returns:
            Correction summary dictionary
        """
        if self.corrected_data is None:
            return {"status": "No correction performed"}

        summary = {
            "method": list(self.correction_params.keys())[0]
            if self.correction_params
            else "unknown",
            "original_shape": self.corrected_data.shape,
            "value_range": {
                "min": float(self.corrected_data.min().min()),
                "max": float(self.corrected_data.max().max()),
                "mean": float(self.corrected_data.mean().mean()),
                "std": float(self.corrected_data.std().mean()),
            },
            "parameters": self.correction_params,
        }

        return summary

    def save_corrected_data(self, output_path: str, format: str = "tsv") -> str:
        """
        Save corrected data to file.

        Args:
            output_path: Output file path
            format: Output format (tsv, csv, h5)

        Returns:
            Path to saved file
        """
        if self.corrected_data is None:
            raise ValueError("No corrected data to save")

        try:
            if format.lower() == "tsv":
                self.corrected_data.to_csv(output_path, sep="\t")
            elif format.lower() == "csv":
                self.corrected_data.to_csv(output_path)
            elif format.lower() == "h5":
                self.corrected_data.to_hdf(output_path, key="corrected_data")
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Corrected data saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save corrected data: {str(e)}")
            raise
