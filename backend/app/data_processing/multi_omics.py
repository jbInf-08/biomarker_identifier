"""
Multi-Omics Data Processing Module

This module provides functionality to process and integrate multiple omics data types
including gene expression, methylation, copy number variation, and proteomics data.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.preprocessing import RobustScaler, StandardScaler

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class MultiOmicsProcessor:
    """
    Process and integrate multiple omics data types for biomarker discovery.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize multi-omics processor.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.processed_data = {}
        self.integration_results = {}

    def load_expression_data(self, file_path: str, **kwargs) -> pd.DataFrame:
        """
        Load gene expression data.

        Args:
            file_path: Path to expression data file
            **kwargs: Additional arguments for pandas read functions

        Returns:
            Expression data DataFrame
        """
        try:
            file_path = Path(file_path)

            if file_path.suffix.lower() in [".csv", ".txt"]:
                with open(file_path, "r") as f:
                    first_line = f.readline().strip()

                if "\t" in first_line:
                    df = pd.read_csv(file_path, sep="\t", index_col=0, **kwargs)
                else:
                    df = pd.read_csv(file_path, index_col=0, **kwargs)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")

            # Basic preprocessing
            df = df.loc[(df != 0).any(axis=1) & df.notna().any(axis=1)]

            self.processed_data["expression"] = df
            logger.info(f"Loaded expression data: {df.shape}")

            return df

        except Exception as e:
            logger.error(f"Failed to load expression data: {str(e)}")
            raise

    def load_methylation_data(
        self, file_path: str, beta_threshold: float = 0.3, **kwargs
    ) -> pd.DataFrame:
        """
        Load DNA methylation data (beta values).

        Args:
            file_path: Path to methylation data file
            beta_threshold: Threshold for filtering low-variance probes
            **kwargs: Additional arguments for pandas read functions

        Returns:
            Methylation data DataFrame
        """
        try:
            file_path = Path(file_path)

            if file_path.suffix.lower() in [".csv", ".txt"]:
                with open(file_path, "r") as f:
                    first_line = f.readline().strip()

                if "\t" in first_line:
                    df = pd.read_csv(file_path, sep="\t", index_col=0, **kwargs)
                else:
                    df = pd.read_csv(file_path, index_col=0, **kwargs)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")

            # Filter probes with low variance
            probe_variance = df.var(axis=1)
            high_var_probes = probe_variance > beta_threshold
            df = df[high_var_probes]

            # Remove probes with missing values
            df = df.dropna()

            self.processed_data["methylation"] = df
            logger.info(f"Loaded methylation data: {df.shape}")

            return df

        except Exception as e:
            logger.error(f"Failed to load methylation data: {str(e)}")
            raise

    def load_copy_number_data(
        self, file_path: str, cnv_threshold: float = 0.3, **kwargs
    ) -> pd.DataFrame:
        """
        Load copy number variation data.

        Args:
            file_path: Path to CNV data file
            cnv_threshold: Threshold for filtering low-variance segments
            **kwargs: Additional arguments for pandas read functions

        Returns:
            CNV data DataFrame
        """
        try:
            file_path = Path(file_path)

            if file_path.suffix.lower() in [".csv", ".txt"]:
                with open(file_path, "r") as f:
                    first_line = f.readline().strip()

                if "\t" in first_line:
                    df = pd.read_csv(file_path, sep="\t", index_col=0, **kwargs)
                else:
                    df = pd.read_csv(file_path, index_col=0, **kwargs)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")

            # Filter segments with low variance
            segment_variance = df.var(axis=1)
            high_var_segments = segment_variance > cnv_threshold
            df = df[high_var_segments]

            # Remove segments with missing values
            df = df.dropna()

            self.processed_data["copy_number"] = df
            logger.info(f"Loaded copy number data: {df.shape}")

            return df

        except Exception as e:
            logger.error(f"Failed to load copy number data: {str(e)}")
            raise

    def load_proteomics_data(
        self, file_path: str, intensity_threshold: float = 1e5, **kwargs
    ) -> pd.DataFrame:
        """
        Load proteomics data.

        Args:
            file_path: Path to proteomics data file
            intensity_threshold: Threshold for filtering low-intensity proteins
            **kwargs: Additional arguments for pandas read functions

        Returns:
            Proteomics data DataFrame
        """
        try:
            file_path = Path(file_path)

            if file_path.suffix.lower() in [".csv", ".txt"]:
                with open(file_path, "r") as f:
                    first_line = f.readline().strip()

                if "\t" in first_line:
                    df = pd.read_csv(file_path, sep="\t", index_col=0, **kwargs)
                else:
                    df = pd.read_csv(file_path, index_col=0, **kwargs)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")

            # Filter proteins with low intensity
            protein_max = df.max(axis=1)
            high_intensity_proteins = protein_max > intensity_threshold
            df = df[high_intensity_proteins]

            # Log2 transform
            df = np.log2(df + 1)

            # Remove proteins with missing values
            df = df.dropna()

            self.processed_data["proteomics"] = df
            logger.info(f"Loaded proteomics data: {df.shape}")

            return df

        except Exception as e:
            logger.error(f"Failed to load proteomics data: {str(e)}")
            raise

    def normalize_omics_data(
        self, data_type: str, method: str = "quantile", **kwargs
    ) -> pd.DataFrame:
        """
        Normalize omics data.

        Args:
            data_type: Type of omics data ('expression', 'methylation', etc.)
            method: Normalization method
            **kwargs: Additional arguments for normalization

        Returns:
            Normalized data DataFrame
        """
        try:
            if data_type not in self.processed_data:
                raise ValueError(f"No {data_type} data loaded")

            data = self.processed_data[data_type].copy()

            if method == "quantile":
                # Quantile normalization
                data_ranked = data.rank(axis=1, method="average")
                data_normalized = data_ranked.apply(
                    lambda x: np.percentile(data.values.flatten(), x * 100 / len(x))
                )

            elif method == "zscore":
                # Z-score normalization
                scaler = StandardScaler()
                data_normalized = pd.DataFrame(
                    scaler.fit_transform(data), index=data.index, columns=data.columns
                )

            elif method == "robust":
                # Robust scaling
                scaler = RobustScaler()
                data_normalized = pd.DataFrame(
                    scaler.fit_transform(data), index=data.index, columns=data.columns
                )

            elif method == "log2":
                # Log2 transformation
                data_normalized = np.log2(data + 1)

            else:
                raise ValueError(f"Unknown normalization method: {method}")

            self.processed_data[f"{data_type}_normalized"] = data_normalized
            logger.info(f"Normalized {data_type} data using {method}")

            return data_normalized

        except Exception as e:
            logger.error(f"Failed to normalize {data_type} data: {str(e)}")
            raise

    def align_omics_data(
        self, reference_data_type: str = "expression"
    ) -> Dict[str, pd.DataFrame]:
        """
        Align multiple omics datasets by common samples.

        Args:
            reference_data_type: Reference data type for alignment

        Returns:
            Dictionary of aligned datasets
        """
        try:
            if reference_data_type not in self.processed_data:
                raise ValueError(f"No {reference_data_type} data available")

            # Get reference samples
            reference_samples = set(self.processed_data[reference_data_type].columns)

            aligned_data = {}

            for data_type, data in self.processed_data.items():
                if data_type == reference_data_type:
                    aligned_data[data_type] = data
                    continue

                # Find common samples
                data_samples = set(data.columns)
                common_samples = reference_samples & data_samples

                if len(common_samples) > 0:
                    # Align data
                    aligned_data[data_type] = data[list(common_samples)]
                    logger.info(
                        f"Aligned {data_type}: {len(common_samples)} common samples"
                    )
                else:
                    logger.warning(f"No common samples found for {data_type}")

            self.processed_data["aligned"] = aligned_data
            logger.info(f"Aligned {len(aligned_data)} datasets")

            return aligned_data

        except Exception as e:
            logger.error(f"Failed to align omics data: {str(e)}")
            raise

    def integrate_omics_data(
        self,
        integration_method: str = "concatenation",
        feature_selection: bool = True,
        n_features: int = 1000,
    ) -> pd.DataFrame:
        """
        Integrate multiple omics datasets.

        Args:
            integration_method: Method for integration ('concatenation', 'pca', 'mofa')
            feature_selection: Whether to perform feature selection
            n_features: Number of features to select

        Returns:
            Integrated data DataFrame
        """
        try:
            if "aligned" not in self.processed_data:
                self.align_omics_data()

            aligned_data = self.processed_data["aligned"]

            if integration_method == "concatenation":
                # Simple concatenation
                integrated_data = pd.concat(
                    [data for data in aligned_data.values()], axis=0
                )

            elif integration_method == "pca":
                # PCA-based integration
                integrated_data = self._pca_integration(aligned_data)

            elif integration_method == "mofa":
                # MOFA-based integration (simplified version)
                integrated_data = self._mofa_integration(aligned_data)

            else:
                raise ValueError(f"Unknown integration method: {integration_method}")

            # Feature selection if requested
            if feature_selection:
                integrated_data = self._select_integrated_features(
                    integrated_data, n_features
                )

            self.integration_results["integrated_data"] = integrated_data
            self.integration_results["integration_method"] = integration_method

            logger.info(f"Integrated omics data: {integrated_data.shape}")

            return integrated_data

        except Exception as e:
            logger.error(f"Failed to integrate omics data: {str(e)}")
            raise

    def _pca_integration(self, aligned_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        PCA-based integration of omics data.

        Args:
            aligned_data: Dictionary of aligned datasets

        Returns:
            PCA-integrated data
        """
        try:
            pca_results = []

            for data_type, data in aligned_data.items():
                # Standardize data
                scaler = StandardScaler()
                data_scaled = scaler.fit_transform(data.T)

                # Apply PCA
                pca = PCA(n_components=min(50, data.shape[0], data.shape[1]))
                pca_data = pca.fit_transform(data_scaled)

                # Create DataFrame
                pca_df = pd.DataFrame(
                    pca_data,
                    index=data.columns,
                    columns=[f"{data_type}_PC{i+1}" for i in range(pca_data.shape[1])],
                )

                pca_results.append(pca_df)

            # Concatenate PCA results
            integrated_data = pd.concat(pca_results, axis=1)

            return integrated_data.T

        except Exception as e:
            logger.error(f"PCA integration failed: {str(e)}")
            raise

    def _mofa_integration(self, aligned_data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """
        MOFA-based integration (simplified version).

        Args:
            aligned_data: Dictionary of aligned datasets

        Returns:
            MOFA-integrated data
        """
        try:
            # Simplified MOFA: concatenate standardized data
            standardized_data = []

            for data_type, data in aligned_data.items():
                # Standardize data
                scaler = StandardScaler()
                data_scaled = pd.DataFrame(
                    scaler.fit_transform(data), index=data.index, columns=data.columns
                )

                # Add data type prefix
                data_scaled.index = [f"{data_type}_{idx}" for idx in data_scaled.index]
                standardized_data.append(data_scaled)

            # Concatenate
            integrated_data = pd.concat(standardized_data, axis=0)

            return integrated_data

        except Exception as e:
            logger.error(f"MOFA integration failed: {str(e)}")
            raise

    def _select_integrated_features(
        self, integrated_data: pd.DataFrame, n_features: int
    ) -> pd.DataFrame:
        """
        Select top features from integrated data.

        Args:
            integrated_data: Integrated omics data
            n_features: Number of features to select

        Returns:
            Feature-selected data
        """
        try:
            # Calculate feature variance
            feature_variance = integrated_data.var(axis=1)

            # Select top features
            top_features = feature_variance.nlargest(n_features).index
            selected_data = integrated_data.loc[top_features]

            logger.info(f"Selected {len(top_features)} features from integrated data")

            return selected_data

        except Exception as e:
            logger.error(f"Feature selection failed: {str(e)}")
            raise

    def calculate_omics_correlations(self, data_types: List[str]) -> pd.DataFrame:
        """
        Calculate correlations between different omics data types.

        Args:
            data_types: List of data types to correlate

        Returns:
            Correlation matrix
        """
        try:
            if "aligned" not in self.processed_data:
                self.align_omics_data()

            aligned_data = self.processed_data["aligned"]

            # Calculate pairwise correlations
            correlations = {}

            for i, data_type1 in enumerate(data_types):
                if data_type1 not in aligned_data:
                    continue

                for j, data_type2 in enumerate(data_types):
                    if data_type2 not in aligned_data or i >= j:
                        continue

                    data1 = aligned_data[data_type1]
                    data2 = aligned_data[data_type2]

                    # Calculate correlation between datasets
                    correlation = np.corrcoef(
                        data1.values.flatten(), data2.values.flatten()
                    )[0, 1]

                    correlations[f"{data_type1}_{data_type2}"] = correlation

            # Create correlation matrix
            correlation_df = pd.DataFrame(
                list(correlations.items()), columns=["Data Types", "Correlation"]
            )

            return correlation_df

        except Exception as e:
            logger.error(f"Failed to calculate omics correlations: {str(e)}")
            raise

    def visualize_omics_integration(self, output_dir: str):
        """
        Create visualizations for omics data integration.

        Args:
            output_dir: Output directory for plots
        """
        try:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            if "aligned" not in self.processed_data:
                logger.warning("No aligned data available for visualization")
                return

            aligned_data = self.processed_data["aligned"]

            # Create overview plot
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle("Multi-Omics Data Integration Overview", fontsize=16)

            # Plot 1: Data dimensions
            data_types = list(aligned_data.keys())
            dimensions = [data.shape for data in aligned_data.values()]

            axes[0, 0].bar(data_types, [d[0] for d in dimensions])
            axes[0, 0].set_title("Number of Features by Data Type")
            axes[0, 0].set_ylabel("Number of Features")
            axes[0, 0].tick_params(axis="x", rotation=45)

            # Plot 2: Sample counts
            axes[0, 1].bar(data_types, [d[1] for d in dimensions])
            axes[0, 1].set_title("Number of Samples by Data Type")
            axes[0, 1].set_ylabel("Number of Samples")
            axes[0, 1].tick_params(axis="x", rotation=45)

            # Plot 3: Data distribution (if integrated data available)
            if "integrated_data" in self.integration_results:
                integrated_data = self.integration_results["integrated_data"]

                # Sample a subset for visualization
                sample_data = integrated_data.sample(n=min(1000, len(integrated_data)))

                axes[1, 0].hist(sample_data.values.flatten(), bins=50, alpha=0.7)
                axes[1, 0].set_title("Integrated Data Distribution")
                axes[1, 0].set_xlabel("Value")
                axes[1, 0].set_ylabel("Frequency")

            # Plot 4: Correlation heatmap (if multiple data types)
            if len(data_types) > 1:
                correlations = self.calculate_omics_correlations(data_types)

                if not correlations.empty:
                    # Create correlation matrix
                    corr_matrix = correlations.pivot_table(
                        values="Correlation", index="Data Types", columns="Data Types"
                    )

                    sns.heatmap(
                        corr_matrix,
                        annot=True,
                        cmap="coolwarm",
                        center=0,
                        ax=axes[1, 1],
                    )
                    axes[1, 1].set_title("Inter-Omics Correlations")

            plt.tight_layout()

            # Save plot
            plot_file = output_dir / "multi_omics_integration_overview.png"
            plt.savefig(plot_file, dpi=300, bbox_inches="tight")
            plt.close()

            logger.info(f"Multi-omics visualization saved: {plot_file}")

        except Exception as e:
            logger.error(f"Failed to create multi-omics visualizations: {str(e)}")

    def get_integration_summary(self) -> Dict[str, Any]:
        """
        Get summary of multi-omics integration.

        Returns:
            Integration summary dictionary
        """
        try:
            summary = {
                "data_types_loaded": list(self.processed_data.keys()),
                "integration_timestamp": None,
                "integration_method": None,
                "integrated_data_shape": None,
                "aligned_samples": None,
            }

            if "aligned" in self.processed_data:
                aligned_data = self.processed_data["aligned"]
                summary["aligned_samples"] = len(list(aligned_data.values())[0].columns)
                summary["data_types_aligned"] = list(aligned_data.keys())

            if "integrated_data" in self.integration_results:
                integrated_data = self.integration_results["integrated_data"]
                summary["integrated_data_shape"] = integrated_data.shape
                summary["integration_method"] = self.integration_results[
                    "integration_method"
                ]
                summary["integration_timestamp"] = datetime.now().isoformat()

            return summary

        except Exception as e:
            logger.error(f"Failed to get integration summary: {str(e)}")
            raise


def main():
    """Main function for testing multi-omics processing."""
    # Create sample data
    np.random.seed(42)

    # Sample expression data
    expression_data = pd.DataFrame(
        np.random.lognormal(mean=5, sigma=1, size=(100, 50)),
        index=[f"GENE_{i:03d}" for i in range(100)],
        columns=[f"SAMPLE_{i:03d}" for i in range(50)],
    )

    # Sample methylation data
    methylation_data = pd.DataFrame(
        np.random.beta(2, 2, size=(50, 50)),
        index=[f"PROBE_{i:03d}" for i in range(50)],
        columns=[f"SAMPLE_{i:03d}" for i in range(50)],
    )

    # Sample copy number data
    copy_number_data = pd.DataFrame(
        np.random.normal(0, 0.5, size=(30, 50)),
        index=[f"SEGMENT_{i:03d}" for i in range(30)],
        columns=[f"SAMPLE_{i:03d}" for i in range(50)],
    )

    # Test multi-omics processing
    processor = MultiOmicsProcessor()

    try:
        # Load data
        processor.processed_data["expression"] = expression_data
        processor.processed_data["methylation"] = methylation_data
        processor.processed_data["copy_number"] = copy_number_data

        # Align data
        aligned_data = processor.align_omics_data()
        print(f"Aligned data: {len(aligned_data)} datasets")

        # Integrate data
        integrated_data = processor.integrate_omics_data()
        print(f"Integrated data shape: {integrated_data.shape}")

        # Get summary
        summary = processor.get_integration_summary()
        print(f"Integration summary: {summary}")

        print("Multi-omics processing test completed successfully!")

    except Exception as e:
        logger.error(f"Multi-omics processing test failed: {str(e)}")
        raise


if __name__ == "__main__":
    main()
