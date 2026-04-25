"""
Normalization methods for expression data.
"""

import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import RobustScaler, StandardScaler

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class Normalization:
    """
    Handles various normalization methods for expression data.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the normalization module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.normalization_params = {}
        self.normalized_data = None

    def normalize_data(
        self, expression_data: pd.DataFrame, method: str = "log_cpm", **kwargs
    ) -> pd.DataFrame:
        """
        Normalize expression data using specified method.

        Args:
            expression_data: Expression data matrix
            method: Normalization method
            **kwargs: Additional method-specific parameters

        Returns:
            Normalized expression data
        """
        try:
            if expression_data is None or expression_data.size == 0:
                raise ValueError("Expression data is empty")

            if method == "log_cpm":
                normalized_data = self._log_cpm_normalization(expression_data, **kwargs)
            elif method == "log_tpm":
                normalized_data = self._log_tpm_normalization(expression_data, **kwargs)
            elif method == "quantile":
                normalized_data = self._quantile_normalization(
                    expression_data, **kwargs
                )
            elif method == "z_score":
                normalized_data = self._z_score_normalization(expression_data, **kwargs)
            elif method == "robust_z_score":
                normalized_data = self._robust_z_score_normalization(
                    expression_data, **kwargs
                )
            elif method == "min_max":
                normalized_data = self._min_max_normalization(expression_data, **kwargs)
            elif method == "median_ratio":
                normalized_data = self._median_ratio_normalization(
                    expression_data, **kwargs
                )
            elif method == "tmm":
                normalized_data = self._tmm_normalization(expression_data, **kwargs)
            else:
                raise ValueError(f"Unknown normalization method: {method}")

            self.normalized_data = normalized_data
            logger.info(f"Data normalized using {method} method")

            return normalized_data

        except Exception as e:
            logger.error(f"Failed to normalize data: {str(e)}")
            raise

    def _log_cpm_normalization(
        self, expression_data: pd.DataFrame, prior_count: float = 1.0
    ) -> pd.DataFrame:
        """
        Log CPM (Counts Per Million) normalization.

        Args:
            expression_data: Expression data matrix
            prior_count: Prior count to add before log transformation

        Returns:
            Log CPM normalized data
        """
        # Calculate library sizes
        library_sizes = expression_data.sum(axis=0)

        # Calculate CPM
        cpm = (expression_data * 1e6) / library_sizes

        # Log transformation with prior count
        # Ensure result is a DataFrame with same index and columns
        log_cpm = np.log2(cpm + prior_count)

        # Convert back to DataFrame if needed, preserving index and columns
        if not isinstance(log_cpm, pd.DataFrame):
            log_cpm = pd.DataFrame(
                log_cpm, index=expression_data.index, columns=expression_data.columns
            )

        # Store normalization parameters
        self.normalization_params["log_cpm"] = {
            "library_sizes": library_sizes.to_dict(),
            "prior_count": prior_count,
            "method": "log_cpm",
        }

        return log_cpm

    def _log_tpm_normalization(
        self, expression_data: pd.DataFrame, prior_count: float = 1.0
    ) -> pd.DataFrame:
        """
        Log TPM (Transcripts Per Million) normalization.

        Args:
            expression_data: Expression data matrix (assumed to be TPM)
            prior_count: Prior count to add before log transformation

        Returns:
            Log TPM normalized data
        """
        # Log transformation with prior count
        log_tpm = np.log2(expression_data + prior_count)

        # Store normalization parameters
        self.normalization_params["log_tpm"] = {
            "prior_count": prior_count,
            "method": "log_tpm",
        }

        return log_tpm

    def _quantile_normalization(self, expression_data: pd.DataFrame) -> pd.DataFrame:
        """
        Quantile normalization (Bolstad et al.). Rows = features (genes), columns = samples.

        Args:
            expression_data: Expression data matrix

        Returns:
            Quantile normalized data
        """
        arr = np.asarray(expression_data, dtype=float)
        n_genes, n_samples = arr.shape
        if n_genes == 0 or n_samples == 0:
            raise ValueError("Cannot quantile-normalize empty matrix")

        # Sort each column (each sample's distribution across genes)
        sorted_data = np.sort(arr, axis=0)
        mean_sorted = np.mean(sorted_data, axis=1)

        ranks = np.zeros_like(arr, dtype=int)
        for j in range(n_samples):
            ranks[:, j] = stats.rankdata(arr[:, j], method="ordinal").astype(int) - 1

        idx_clipped = np.clip(ranks, 0, mean_sorted.shape[0] - 1)
        normalized = mean_sorted[idx_clipped]

        result = pd.DataFrame(
            normalized,
            index=expression_data.index,
            columns=expression_data.columns,
        )

        self.normalization_params["quantile"] = {
            "method": "quantile",
            "mean_sorted_values": mean_sorted.tolist(),
        }

        return result

    def _z_score_normalization(self, expression_data: pd.DataFrame) -> pd.DataFrame:
        """
        Z-score normalization (standardization).

        Args:
            expression_data: Expression data matrix

        Returns:
            Z-score normalized data
        """
        scaler = StandardScaler()
        normalized_data = scaler.fit_transform(expression_data.T).T

        result = pd.DataFrame(
            normalized_data,
            index=expression_data.index,
            columns=expression_data.columns,
        )

        # Store normalization parameters
        self.normalization_params["z_score"] = {
            "method": "z_score",
            "mean": scaler.mean_.tolist(),
            "scale": scaler.scale_.tolist(),
        }

        return result

    def _robust_z_score_normalization(
        self, expression_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Robust Z-score normalization using median and MAD.

        Args:
            expression_data: Expression data matrix

        Returns:
            Robust Z-score normalized data
        """
        scaler = RobustScaler()
        normalized_data = scaler.fit_transform(expression_data.T).T

        result = pd.DataFrame(
            normalized_data,
            index=expression_data.index,
            columns=expression_data.columns,
        )

        # Store normalization parameters
        self.normalization_params["robust_z_score"] = {
            "method": "robust_z_score",
            "center": scaler.center_.tolist(),
            "scale": scaler.scale_.tolist(),
        }

        return result

    def _min_max_normalization(
        self, expression_data: pd.DataFrame, feature_range: Tuple[float, float] = (0, 1)
    ) -> pd.DataFrame:
        """
        Min-max normalization.

        Args:
            expression_data: Expression data matrix
            feature_range: Range for normalization

        Returns:
            Min-max normalized data
        """
        min_val = expression_data.min().min()
        max_val = expression_data.max().max()

        normalized_data = (expression_data - min_val) / (max_val - min_val)
        normalized_data = (
            normalized_data * (feature_range[1] - feature_range[0]) + feature_range[0]
        )

        # Store normalization parameters
        self.normalization_params["min_max"] = {
            "method": "min_max",
            "min_val": min_val,
            "max_val": max_val,
            "feature_range": feature_range,
        }

        return normalized_data

    def _median_ratio_normalization(
        self, expression_data: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Median ratio normalization (similar to DESeq2).

        Args:
            expression_data: Expression data matrix

        Returns:
            Median ratio normalized data
        """
        # Calculate geometric mean for each gene
        geometric_means = np.exp(np.mean(np.log(expression_data + 1), axis=1))

        # Calculate size factors
        size_factors = np.median((expression_data.T / geometric_means).T, axis=0)

        # Normalize data
        normalized_data = expression_data / size_factors

        # Store normalization parameters
        self.normalization_params["median_ratio"] = {
            "method": "median_ratio",
            "geometric_means": geometric_means.tolist(),
            "size_factors": size_factors.tolist(),
        }

        return normalized_data

    def _tmm_normalization(
        self, expression_data: pd.DataFrame, ref_sample: Optional[str] = None
    ) -> pd.DataFrame:
        """
        TMM (Trimmed Mean of M-values) normalization.

        Args:
            expression_data: Expression data matrix
            ref_sample: Reference sample (if None, use median sample)

        Returns:
            TMM normalized data
        """
        # If no reference sample specified, use the sample with median library size
        if ref_sample is None:
            library_sizes = expression_data.sum(axis=0)
            median_size = library_sizes.median()
            # Find sample closest to median library size
            ref_sample = (library_sizes - median_size).abs().idxmin()

        # Calculate M and A values
        ref_data = expression_data[ref_sample]

        # Calculate size factors for each sample
        size_factors = []
        for sample in expression_data.columns:
            if sample == ref_sample:
                size_factors.append(1.0)
            else:
                sample_data = expression_data[sample]

                # Calculate M and A values
                m_values = np.log2(sample_data + 1) - np.log2(ref_data + 1)
                a_values = 0.5 * (np.log2(sample_data + 1) + np.log2(ref_data + 1))

                # Trim extreme values (top and bottom 30%)
                trim_percentile = 30
                lower_trim = np.percentile(a_values, trim_percentile)
                upper_trim = np.percentile(a_values, 100 - trim_percentile)

                # Filter M and A values
                mask = (a_values >= lower_trim) & (a_values <= upper_trim)
                filtered_m = m_values[mask]
                filtered_a = a_values[mask]

                # Calculate weighted mean of M values
                weights = 1 / (1 + filtered_a)
                size_factor = np.exp(np.average(filtered_m, weights=weights))
                size_factors.append(size_factor)

        # Normalize data
        normalized_data = expression_data / size_factors

        # Store normalization parameters
        self.normalization_params["tmm"] = {
            "method": "tmm",
            "ref_sample": ref_sample,
            "size_factors": dict(zip(expression_data.columns, size_factors)),
        }

        return normalized_data

    def detect_normalization_method(self, expression_data: pd.DataFrame) -> str:
        """
        Detect the most likely normalization method used in the data.

        Args:
            expression_data: Expression data matrix

        Returns:
            Detected normalization method
        """
        # Check for negative values
        has_negative = (expression_data < 0).any().any()

        # Check for decimal values
        has_decimals = ((expression_data % 1) != 0).any().any()

        # Check value range
        min_val = expression_data.min().min()
        max_val = expression_data.max().max()
        mean_val = expression_data.mean().mean()

        # Check for log-like distribution
        log_likeness = self._check_log_distribution(expression_data)

        # Decision logic
        if has_negative:
            return "z_score"  # Likely already normalized
        elif not has_decimals and min_val >= 0 and max_val < 100:
            return "raw_counts"  # Likely raw counts
        elif log_likeness > 0.7:
            return "log_transformed"  # Likely log-transformed
        elif has_decimals and min_val >= 0:
            return "tpm_fpkm"  # Likely TPM/FPKM
        else:
            return "unknown"

    def _check_log_distribution(self, expression_data: pd.DataFrame) -> float:
        """
        Check how well the data follows a log-normal distribution.

        Args:
            expression_data: Expression data matrix

        Returns:
            Log-likeness score (0-1)
        """
        # Sample a subset of genes for efficiency
        n_genes = min(1000, expression_data.shape[0])
        sample_genes = np.random.choice(expression_data.index, n_genes, replace=False)
        sample_data = expression_data.loc[sample_genes]

        # Calculate skewness for each gene
        skewness = sample_data.skew(axis=1)

        # Count genes with positive skewness (log-normal characteristic)
        positive_skew = (skewness > 0).sum()

        return positive_skew / len(skewness)

    def get_normalization_summary(self) -> Dict[str, Any]:
        """
        Get summary of normalization results.

        Returns:
            Normalization summary dictionary
        """
        if self.normalized_data is None:
            return {"status": "No normalization performed"}

        summary = {
            "method": list(self.normalization_params.keys())[0]
            if self.normalization_params
            else "unknown",
            "original_shape": None,  # Would be set if original data was stored
            "normalized_shape": self.normalized_data.shape,
            "value_range": {
                "min": float(self.normalized_data.min().min()),
                "max": float(self.normalized_data.max().max()),
                "mean": float(self.normalized_data.mean().mean()),
                "std": float(self.normalized_data.std().mean()),
            },
            "missing_values": self.normalized_data.isna().sum().sum(),
            "zero_values": (self.normalized_data == 0).sum().sum(),
            "negative_values": (self.normalized_data < 0).sum().sum(),
            "parameters": self.normalization_params,
        }

        return summary

    def save_normalized_data(self, output_path: str, format: str = "tsv") -> str:
        """
        Save normalized data to file.

        Args:
            output_path: Output file path
            format: Output format (tsv, csv, h5)

        Returns:
            Path to saved file
        """
        if self.normalized_data is None:
            raise ValueError("No normalized data to save")

        try:
            if format.lower() == "tsv":
                self.normalized_data.to_csv(output_path, sep="\t")
            elif format.lower() == "csv":
                self.normalized_data.to_csv(output_path)
            elif format.lower() == "h5":
                self.normalized_data.to_hdf(output_path, key="normalized_data")
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Normalized data saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save normalized data: {str(e)}")
            raise

    def compare_normalization_methods(
        self, expression_data: pd.DataFrame, methods: List[str] = None
    ) -> Dict[str, Any]:
        """
        Compare different normalization methods.

        Args:
            expression_data: Expression data matrix
            methods: List of normalization methods to compare

        Returns:
            Comparison results dictionary
        """
        if methods is None:
            methods = ["log_cpm", "quantile", "z_score", "robust_z_score"]

        comparison_results = {}

        for method in methods:
            try:
                normalized_data = self.normalize_data(expression_data, method)
                summary = self.get_normalization_summary()
                comparison_results[method] = summary

                # Reset for next method
                self.normalized_data = None
                self.normalization_params = {}

            except Exception as e:
                logger.warning(f"Failed to apply {method}: {str(e)}")
                comparison_results[method] = {"error": str(e)}

        return comparison_results
