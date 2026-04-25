"""
Data transformation utilities for expression data.
"""

import warnings
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import PowerTransformer, QuantileTransformer

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class DataTransformation:
    """
    Handles various data transformations for expression data.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data transformation module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.transformation_params = {}
        self.transformed_data = None

    def transform_data(
        self, expression_data: pd.DataFrame, method: str = "log2", **kwargs
    ) -> pd.DataFrame:
        """
        Transform expression data using specified method.

        Args:
            expression_data: Expression data matrix
            method: Transformation method
            **kwargs: Additional method-specific parameters

        Returns:
            Transformed expression data
        """
        try:
            if method == "log2":
                transformed_data = self._log2_transform(expression_data, **kwargs)
            elif method == "log10":
                transformed_data = self._log10_transform(expression_data, **kwargs)
            elif method == "sqrt":
                transformed_data = self._sqrt_transform(expression_data, **kwargs)
            elif method == "box_cox":
                transformed_data = self._box_cox_transform(expression_data, **kwargs)
            elif method == "yeo_johnson":
                transformed_data = self._yeo_johnson_transform(
                    expression_data, **kwargs
                )
            elif method == "quantile":
                transformed_data = self._quantile_transform(expression_data, **kwargs)
            elif method == "rank":
                transformed_data = self._rank_transform(expression_data, **kwargs)
            elif method == "z_score":
                transformed_data = self._z_score_transform(expression_data, **kwargs)
            elif method == "robust_z_score":
                transformed_data = self._robust_z_score_transform(
                    expression_data, **kwargs
                )
            elif method == "custom":
                transformed_data = self._custom_transform(expression_data, **kwargs)
            else:
                raise ValueError(f"Unknown transformation method: {method}")

            self.transformed_data = transformed_data
            logger.info(f"Data transformed using {method} method")

            return transformed_data

        except Exception as e:
            logger.error(f"Failed to transform data: {str(e)}")
            raise

    def _log2_transform(
        self, expression_data: pd.DataFrame, prior_count: float = 1.0
    ) -> pd.DataFrame:
        """
        Log2 transformation.

        Args:
            expression_data: Expression data matrix
            prior_count: Prior count to add before log transformation

        Returns:
            Log2 transformed data
        """
        transformed_data = np.log2(expression_data + prior_count)

        # Store transformation parameters
        self.transformation_params["log2"] = {
            "method": "log2",
            "prior_count": prior_count,
        }

        return transformed_data

    def _log10_transform(
        self, expression_data: pd.DataFrame, prior_count: float = 1.0
    ) -> pd.DataFrame:
        """
        Log10 transformation.

        Args:
            expression_data: Expression data matrix
            prior_count: Prior count to add before log transformation

        Returns:
            Log10 transformed data
        """
        transformed_data = np.log10(expression_data + prior_count)

        # Store transformation parameters
        self.transformation_params["log10"] = {
            "method": "log10",
            "prior_count": prior_count,
        }

        return transformed_data

    def _sqrt_transform(self, expression_data: pd.DataFrame) -> pd.DataFrame:
        """
        Square root transformation.

        Args:
            expression_data: Expression data matrix

        Returns:
            Square root transformed data
        """
        transformed_data = np.sqrt(expression_data)

        # Store transformation parameters
        self.transformation_params["sqrt"] = {"method": "sqrt"}

        return transformed_data

    def _box_cox_transform(
        self, expression_data: pd.DataFrame, method: str = "yeo-johnson"
    ) -> pd.DataFrame:
        """
        Box-Cox or Yeo-Johnson transformation.

        Args:
            expression_data: Expression data matrix
            method: Transformation method ('box-cox' or 'yeo-johnson')

        Returns:
            Power transformed data
        """
        # Use Yeo-Johnson by default as it handles negative values
        if method == "box-cox":
            transformer = PowerTransformer(method="box-cox")
        else:
            transformer = PowerTransformer(method="yeo-johnson")

        # Transform data
        transformed_array = transformer.fit_transform(expression_data.T).T
        transformed_data = pd.DataFrame(
            transformed_array,
            index=expression_data.index,
            columns=expression_data.columns,
        )

        # Store transformation parameters
        self.transformation_params["box_cox"] = {
            "method": "box_cox",
            "transformer_method": method,
            "lambdas": transformer.lambdas_.tolist(),
        }

        return transformed_data

    def _yeo_johnson_transform(self, expression_data: pd.DataFrame) -> pd.DataFrame:
        """
        Yeo-Johnson transformation.

        Args:
            expression_data: Expression data matrix

        Returns:
            Yeo-Johnson transformed data
        """
        return self._box_cox_transform(expression_data, method="yeo-johnson")

    def _quantile_transform(
        self,
        expression_data: pd.DataFrame,
        output_distribution: str = "uniform",
        n_quantiles: int = 1000,
    ) -> pd.DataFrame:
        """
        Quantile transformation.

        Args:
            expression_data: Expression data matrix
            output_distribution: Output distribution ('uniform' or 'normal')
            n_quantiles: Number of quantiles to compute

        Returns:
            Quantile transformed data
        """
        transformer = QuantileTransformer(
            output_distribution=output_distribution,
            n_quantiles=min(n_quantiles, expression_data.shape[0]),
        )

        # Transform data
        transformed_array = transformer.fit_transform(expression_data.T).T
        transformed_data = pd.DataFrame(
            transformed_array,
            index=expression_data.index,
            columns=expression_data.columns,
        )

        # Store transformation parameters
        self.transformation_params["quantile"] = {
            "method": "quantile",
            "output_distribution": output_distribution,
            "n_quantiles": n_quantiles,
            "quantiles": transformer.quantiles_.tolist(),
        }

        return transformed_data

    def _rank_transform(
        self, expression_data: pd.DataFrame, method: str = "average"
    ) -> pd.DataFrame:
        """
        Rank transformation.

        Args:
            expression_data: Expression data matrix
            method: Ranking method ('average', 'min', 'max', 'dense', 'ordinal')

        Returns:
            Rank transformed data
        """
        # Apply ranking to each gene
        transformed_data = expression_data.copy()

        for gene in expression_data.index:
            gene_data = expression_data.loc[gene]
            ranks = gene_data.rank(method=method)
            transformed_data.loc[gene] = ranks

        # Store transformation parameters
        self.transformation_params["rank"] = {
            "method": "rank",
            "ranking_method": method,
        }

        return transformed_data

    def _z_score_transform(self, expression_data: pd.DataFrame) -> pd.DataFrame:
        """
        Z-score transformation (standardization).

        Args:
            expression_data: Expression data matrix

        Returns:
            Z-score transformed data
        """
        # Calculate mean and std for each gene
        gene_means = expression_data.mean(axis=1)
        gene_stds = expression_data.std(axis=1)

        # Apply z-score transformation
        transformed_data = (expression_data.T - gene_means) / gene_stds
        transformed_data = transformed_data.T

        # Store transformation parameters
        self.transformation_params["z_score"] = {
            "method": "z_score",
            "gene_means": gene_means.to_dict(),
            "gene_stds": gene_stds.to_dict(),
        }

        return transformed_data

    def _robust_z_score_transform(self, expression_data: pd.DataFrame) -> pd.DataFrame:
        """
        Robust Z-score transformation using median and MAD.

        Args:
            expression_data: Expression data matrix

        Returns:
            Robust Z-score transformed data
        """
        # Calculate median and MAD for each gene
        gene_medians = expression_data.median(axis=1)
        gene_mads = expression_data.mad(axis=1)

        # Apply robust z-score transformation
        transformed_data = (expression_data.T - gene_medians) / gene_mads
        transformed_data = transformed_data.T

        # Store transformation parameters
        self.transformation_params["robust_z_score"] = {
            "method": "robust_z_score",
            "gene_medians": gene_medians.to_dict(),
            "gene_mads": gene_mads.to_dict(),
        }

        return transformed_data

    def _custom_transform(
        self, expression_data: pd.DataFrame, transform_func: Callable, **kwargs
    ) -> pd.DataFrame:
        """
        Custom transformation using a user-defined function.

        Args:
            expression_data: Expression data matrix
            transform_func: Custom transformation function
            **kwargs: Additional arguments for the transformation function

        Returns:
            Custom transformed data
        """
        transformed_data = transform_func(expression_data, **kwargs)

        # Store transformation parameters
        self.transformation_params["custom"] = {
            "method": "custom",
            "transform_func": str(transform_func),
            "kwargs": kwargs,
        }

        return transformed_data

    def detect_best_transformation(
        self, expression_data: pd.DataFrame, methods: List[str] = None
    ) -> Dict[str, Any]:
        """
        Detect the best transformation method based on normality tests.

        Args:
            expression_data: Expression data matrix
            methods: List of transformation methods to test

        Returns:
            Best transformation method and scores
        """
        if methods is None:
            methods = ["log2", "sqrt", "box_cox", "quantile", "rank"]

        results = {}

        for method in methods:
            try:
                # Apply transformation
                transformed_data = self.transform_data(expression_data, method)

                # Calculate normality scores
                normality_scores = self._calculate_normality_scores(transformed_data)

                results[method] = {
                    "normality_score": normality_scores["overall_score"],
                    "skewness": normality_scores["mean_skewness"],
                    "kurtosis": normality_scores["mean_kurtosis"],
                    "shapiro_wilk": normality_scores["mean_shapiro_p"],
                }

                # Reset for next method
                self.transformed_data = None
                self.transformation_params = {}

            except Exception as e:
                logger.warning(f"Failed to test {method}: {str(e)}")
                results[method] = {"error": str(e)}

        # Find best method
        valid_results = {k: v for k, v in results.items() if "error" not in v}
        if valid_results:
            best_method = max(
                valid_results.keys(), key=lambda x: valid_results[x]["normality_score"]
            )
            best_score = valid_results[best_method]["normality_score"]
        else:
            best_method = None
            best_score = 0

        return {
            "best_method": best_method,
            "best_score": best_score,
            "all_results": results,
        }

    def _calculate_normality_scores(
        self, expression_data: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Calculate normality scores for transformed data.

        Args:
            expression_data: Expression data matrix

        Returns:
            Normality scores dictionary
        """
        # Sample genes for efficiency
        n_genes = min(1000, expression_data.shape[0])
        sample_genes = np.random.choice(expression_data.index, n_genes, replace=False)
        sample_data = expression_data.loc[sample_genes]

        # Calculate skewness and kurtosis
        skewness = sample_data.skew(axis=1)
        kurtosis = sample_data.kurtosis(axis=1)

        # Calculate Shapiro-Wilk p-values
        shapiro_p_values = []
        for gene in sample_data.index:
            gene_data = sample_data.loc[gene]
            try:
                _, p_value = stats.shapiro(gene_data)
                shapiro_p_values.append(p_value)
            except:
                shapiro_p_values.append(0.0)

        # Calculate overall normality score
        mean_skewness = abs(skewness.mean())
        mean_kurtosis = abs(kurtosis.mean())
        mean_shapiro_p = np.mean(shapiro_p_values)

        # Normalize scores (lower is better for skewness and kurtosis, higher is better for Shapiro)
        skewness_score = max(0, 1 - mean_skewness / 2)  # Normalize to 0-1
        kurtosis_score = max(0, 1 - mean_kurtosis / 10)  # Normalize to 0-1
        shapiro_score = mean_shapiro_p  # Already 0-1

        overall_score = (skewness_score + kurtosis_score + shapiro_score) / 3

        return {
            "overall_score": overall_score,
            "mean_skewness": mean_skewness,
            "mean_kurtosis": mean_kurtosis,
            "mean_shapiro_p": mean_shapiro_p,
            "skewness_score": skewness_score,
            "kurtosis_score": kurtosis_score,
            "shapiro_score": shapiro_score,
        }

    def compare_transformations(
        self, expression_data: pd.DataFrame, methods: List[str] = None
    ) -> Dict[str, Any]:
        """
        Compare different transformation methods.

        Args:
            expression_data: Expression data matrix
            methods: List of transformation methods to compare

        Returns:
            Comparison results dictionary
        """
        if methods is None:
            methods = ["log2", "sqrt", "box_cox", "quantile", "rank", "z_score"]

        comparison_results = {}

        for method in methods:
            try:
                # Apply transformation
                transformed_data = self.transform_data(expression_data, method)

                # Calculate statistics
                stats_summary = self._calculate_transformation_stats(transformed_data)

                comparison_results[method] = stats_summary

                # Reset for next method
                self.transformed_data = None
                self.transformation_params = {}

            except Exception as e:
                logger.warning(f"Failed to apply {method}: {str(e)}")
                comparison_results[method] = {"error": str(e)}

        return comparison_results

    def _calculate_transformation_stats(
        self, expression_data: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Calculate statistics for transformed data.

        Args:
            expression_data: Expression data matrix

        Returns:
            Statistics summary dictionary
        """
        # Basic statistics
        basic_stats = {
            "mean": float(expression_data.mean().mean()),
            "std": float(expression_data.std().mean()),
            "min": float(expression_data.min().min()),
            "max": float(expression_data.max().max()),
            "median": float(expression_data.median().median()),
        }

        # Distribution statistics
        skewness = expression_data.skew(axis=1)
        kurtosis = expression_data.kurtosis(axis=1)

        dist_stats = {
            "mean_skewness": float(skewness.mean()),
            "std_skewness": float(skewness.std()),
            "mean_kurtosis": float(kurtosis.mean()),
            "std_kurtosis": float(kurtosis.std()),
        }

        # Missing and infinite values
        missing_stats = {
            "missing_values": int(expression_data.isna().sum().sum()),
            "infinite_values": int(np.isinf(expression_data).sum().sum()),
            "negative_values": int((expression_data < 0).sum().sum()),
        }

        return {
            "basic_stats": basic_stats,
            "distribution_stats": dist_stats,
            "missing_stats": missing_stats,
        }

    def get_transformation_summary(self) -> Dict[str, Any]:
        """
        Get summary of transformation results.

        Returns:
            Transformation summary dictionary
        """
        if self.transformed_data is None:
            return {"status": "No transformation performed"}

        summary = {
            "method": list(self.transformation_params.keys())[0]
            if self.transformation_params
            else "unknown",
            "transformed_shape": self.transformed_data.shape,
            "value_range": {
                "min": float(self.transformed_data.min().min()),
                "max": float(self.transformed_data.max().max()),
                "mean": float(self.transformed_data.mean().mean()),
                "std": float(self.transformed_data.std().mean()),
            },
            "parameters": self.transformation_params,
        }

        return summary

    def save_transformed_data(self, output_path: str, format: str = "tsv") -> str:
        """
        Save transformed data to file.

        Args:
            output_path: Output file path
            format: Output format (tsv, csv, h5)

        Returns:
            Path to saved file
        """
        if self.transformed_data is None:
            raise ValueError("No transformed data to save")

        try:
            if format.lower() == "tsv":
                self.transformed_data.to_csv(output_path, sep="\t")
            elif format.lower() == "csv":
                self.transformed_data.to_csv(output_path)
            elif format.lower() == "h5":
                self.transformed_data.to_hdf(output_path, key="transformed_data")
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Transformed data saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save transformed data: {str(e)}")
            raise
