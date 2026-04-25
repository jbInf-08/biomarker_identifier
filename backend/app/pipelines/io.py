"""
Input/Output utilities for biomarker pipeline.
"""

import hashlib
import json
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import yaml

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class DataIO:
    """
    Handles data input/output, validation, and ID mapping.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the DataIO module.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.expression_data = None
        self.labels = None
        self.metadata = None
        self.validation_results = {}

    def load_data(
        self,
        expression_file: str,
        labels_file: str,
        metadata_file: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Load and validate input data files.

        Args:
            expression_file: Path to expression matrix file
            labels_file: Path to labels file
            metadata_file: Path to metadata file (optional)
            **kwargs: Additional loading parameters

        Returns:
            Dictionary containing loaded data and validation results
        """
        try:
            # Load expression data
            self.expression_data = self._load_expression_data(expression_file, **kwargs)

            # Load labels
            self.labels = self._load_labels(labels_file, **kwargs)

            # Load metadata if provided
            if metadata_file:
                self.metadata = self._load_metadata(metadata_file)

            # Validate data
            validation_results = self._validate_data()

            # Generate dataset hash
            dataset_hash = self._generate_dataset_hash()

            results = {
                "expression_data": self.expression_data,
                "labels": self.labels,
                "metadata": self.metadata,
                "validation_results": validation_results,
                "dataset_hash": dataset_hash,
                "data_summary": self._generate_data_summary(),
            }

            logger.info(f"Data loaded successfully. Dataset hash: {dataset_hash}")
            return results

        except Exception as e:
            logger.error(f"Failed to load data: {str(e)}")
            raise

    def _load_expression_data(self, file_path: str, **kwargs) -> pd.DataFrame:
        """
        Load expression data matrix.

        Args:
            file_path: Path to expression file
            **kwargs: Additional parameters

        Returns:
            Expression data matrix
        """
        # Detect file format
        file_ext = Path(file_path).suffix.lower()

        if file_ext in [".tsv", ".txt"]:
            sep = "\t"
        elif file_ext == ".csv":
            sep = ","
        else:
            sep = "\t"  # Default to tab-separated

        # Filter out pipeline-specific kwargs that pd.read_csv doesn't accept
        csv_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k
            in [
                "header",
                "skiprows",
                "nrows",
                "usecols",
                "dtype",
                "na_values",
                "keep_default_na",
                "skip_blank_lines",
                "comment",
                "encoding",
                "engine",
                "low_memory",
            ]
        }

        # Load data
        expression_data = pd.read_csv(file_path, sep=sep, index_col=0, **csv_kwargs)

        # Convert numeric columns only (skip any non-numeric columns)
        # This handles cases where gene names might be in a column
        numeric_cols = expression_data.select_dtypes(include=[np.number]).columns

        # If we have numeric columns, use them; otherwise try to convert all columns
        if len(numeric_cols) > 0:
            # Some columns are numeric, use them
            expression_data = expression_data[numeric_cols]
        else:
            # No numeric columns found, try converting all columns to numeric
            logger.warning(
                "No numeric columns found, attempting to convert all columns to numeric"
            )
            for col in expression_data.columns:
                expression_data[col] = pd.to_numeric(
                    expression_data[col], errors="coerce"
                )
            # After conversion, select only numeric columns
            numeric_cols = expression_data.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) > 0:
                expression_data = expression_data[numeric_cols]

        # Ensure all remaining columns are numeric (convert to float, handling any remaining non-numeric values)
        if len(expression_data.columns) > 0:
            for col in expression_data.columns:
                # Only convert if not already numeric
                if not pd.api.types.is_numeric_dtype(expression_data[col]):
                    expression_data[col] = pd.to_numeric(
                        expression_data[col], errors="coerce"
                    )

        # Drop rows/columns that are all NaN (but keep at least some data)
        initial_shape = expression_data.shape
        expression_data = expression_data.dropna(how="all").dropna(axis=1, how="all")

        if expression_data.empty:
            logger.error(
                f"Expression data became empty after processing. Initial shape: {initial_shape}"
            )
            raise ValueError("Expression data is empty after loading and processing")

        # Transpose if genes are columns (make genes rows)
        if expression_data.shape[0] < expression_data.shape[1]:
            expression_data = expression_data.T

        logger.info(
            f"Expression data loaded: {expression_data.shape[0]} genes, {expression_data.shape[1]} samples"
        )
        return expression_data

    def _load_labels(self, file_path: str, **kwargs) -> pd.Series:
        """
        Load sample labels.

        Args:
            file_path: Path to labels file
            **kwargs: Additional parameters

        Returns:
            Sample labels series
        """
        # Detect file format
        file_ext = Path(file_path).suffix.lower()

        if file_ext in [".tsv", ".txt"]:
            sep = "\t"
        elif file_ext == ".csv":
            sep = ","
        else:
            sep = "\t"  # Default to tab-separated

        # Filter out pipeline-specific kwargs that pd.read_csv doesn't accept
        csv_kwargs = {
            k: v
            for k, v in kwargs.items()
            if k
            in [
                "header",
                "skiprows",
                "nrows",
                "usecols",
                "dtype",
                "na_values",
                "keep_default_na",
                "skip_blank_lines",
                "comment",
                "encoding",
                "engine",
                "low_memory",
            ]
        }

        # Load labels
        labels_df = pd.read_csv(file_path, sep=sep, **csv_kwargs)

        # Extract sample ID and label columns
        sample_col = kwargs.get("sample_column", "sample_id")
        label_col = kwargs.get("label_column", "class_label")

        if sample_col not in labels_df.columns:
            raise ValueError(f"Sample column '{sample_col}' not found in labels file")
        if label_col not in labels_df.columns:
            raise ValueError(f"Label column '{label_col}' not found in labels file")

        # Create labels series
        labels = pd.Series(labels_df[label_col].values, index=labels_df[sample_col])

        logger.info(
            f"Labels loaded: {len(labels)} samples, {len(labels.unique())} classes"
        )
        return labels

    def _load_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Load metadata file.

        Args:
            file_path: Path to metadata file

        Returns:
            Metadata dictionary
        """
        file_ext = Path(file_path).suffix.lower()

        if file_ext in [".yaml", ".yml"]:
            with open(file_path, "r") as f:
                metadata = yaml.safe_load(f)
        elif file_ext == ".json":
            with open(file_path, "r") as f:
                metadata = json.load(f)
        else:
            raise ValueError(f"Unsupported metadata file format: {file_ext}")

        logger.info(f"Metadata loaded: {len(metadata)} fields")
        return metadata

    def _validate_data(self) -> Dict[str, Any]:
        """
        Validate loaded data.

        Returns:
            Validation results dictionary
        """
        validation_results = {
            "status": "passed",
            "errors": [],
            "warnings": [],
            "checks": {},
        }

        try:
            # Check data types
            self._check_data_types(validation_results)

            # Check sample intersection
            self._check_sample_intersection(validation_results)

            # Check for duplicates
            self._check_duplicates(validation_results)

            # Check missing values
            self._check_missing_values(validation_results)

            # Check data quality
            self._check_data_quality(validation_results)

            # Check label distribution
            self._check_label_distribution(validation_results)

            # Update status based on errors
            if validation_results["errors"]:
                validation_results["status"] = "failed"
            elif validation_results["warnings"]:
                validation_results["status"] = "warning"

            logger.info(f"Data validation completed: {validation_results['status']}")
            return validation_results

        except Exception as e:
            validation_results["status"] = "error"
            validation_results["errors"].append(f"Validation failed: {str(e)}")
            logger.error(f"Data validation failed: {str(e)}")
            return validation_results

    def _check_data_types(self, validation_results: Dict[str, Any]):
        """Check data types and structure."""
        checks = {}

        # Check expression data
        if self.expression_data is not None:
            checks["expression_numeric"] = self.expression_data.dtypes.apply(
                lambda x: pd.api.types.is_numeric_dtype(x)
            ).all()
            checks["expression_shape"] = (
                self.expression_data.shape[0] > 0 and self.expression_data.shape[1] > 0
            )

            if not checks["expression_numeric"]:
                validation_results["errors"].append(
                    "Expression data contains non-numeric values"
                )
            if not checks["expression_shape"]:
                validation_results["errors"].append("Expression data is empty")

        # Check labels
        if self.labels is not None:
            checks["labels_not_empty"] = len(self.labels) > 0
            checks["labels_unique_samples"] = len(self.labels) == len(
                self.labels.index.unique()
            )

            if not checks["labels_not_empty"]:
                validation_results["errors"].append("Labels are empty")
            if not checks["labels_unique_samples"]:
                validation_results["errors"].append("Duplicate sample IDs in labels")

        validation_results["checks"]["data_types"] = checks

    def _check_sample_intersection(self, validation_results: Dict[str, Any]):
        """Check sample intersection between expression and labels."""
        if self.expression_data is not None and self.labels is not None:
            expr_samples = set(self.expression_data.columns)
            label_samples = set(self.labels.index)

            intersection = expr_samples & label_samples
            expr_only = expr_samples - label_samples
            label_only = label_samples - expr_samples

            validation_results["checks"]["sample_intersection"] = {
                "intersection_size": len(intersection),
                "expression_only": len(expr_only),
                "labels_only": len(label_only),
                "intersection_ratio": len(intersection) / len(expr_samples)
                if expr_samples
                else 0,
            }

            if len(intersection) == 0:
                validation_results["errors"].append(
                    "No sample intersection between expression and labels"
                )
            elif len(intersection) < len(expr_samples) * 0.9:
                validation_results["warnings"].append(
                    f"Low sample intersection: {len(intersection)}/{len(expr_samples)} samples"
                )

            if expr_only:
                validation_results["warnings"].append(
                    f"{len(expr_only)} samples in expression but not in labels"
                )
            if label_only:
                validation_results["warnings"].append(
                    f"{len(label_only)} samples in labels but not in expression"
                )

    def _check_duplicates(self, validation_results: Dict[str, Any]):
        """Check for duplicate IDs."""
        checks = {}

        if self.expression_data is not None:
            # Check for duplicate gene IDs
            duplicate_genes = self.expression_data.index.duplicated()
            checks["duplicate_genes"] = duplicate_genes.sum()

            if checks["duplicate_genes"] > 0:
                validation_results["warnings"].append(
                    f"{checks['duplicate_genes']} duplicate gene IDs found"
                )

        if self.labels is not None:
            # Check for duplicate sample IDs
            duplicate_samples = self.labels.index.duplicated()
            checks["duplicate_samples"] = duplicate_samples.sum()

            if checks["duplicate_samples"] > 0:
                validation_results["errors"].append(
                    f"{checks['duplicate_samples']} duplicate sample IDs found"
                )

        validation_results["checks"]["duplicates"] = checks

    def _check_missing_values(self, validation_results: Dict[str, Any]):
        """Check for missing values."""
        checks = {}

        if (
            self.expression_data is not None
            and self.expression_data.shape[0] > 0
            and self.expression_data.shape[1] > 0
        ):
            # Check expression data missing values
            missing_expr = self.expression_data.isnull().sum().sum()
            total_cells = self.expression_data.shape[0] * self.expression_data.shape[1]
            missing_ratio = missing_expr / total_cells if total_cells > 0 else 0.0

            checks["missing_expression"] = missing_expr
            checks["missing_expression_ratio"] = missing_ratio

            if missing_ratio > 0.1:
                validation_results["warnings"].append(
                    f"High missing value ratio in expression data: {missing_ratio:.2%}"
                )

        if self.labels is not None:
            # Check labels missing values
            missing_labels = self.labels.isnull().sum()
            checks["missing_labels"] = missing_labels

            if missing_labels > 0:
                validation_results["warnings"].append(
                    f"{missing_labels} missing values in labels"
                )

        validation_results["checks"]["missing_values"] = checks

    def _check_data_quality(self, validation_results: Dict[str, Any]):
        """Check data quality metrics."""
        if self.expression_data is not None:
            checks = {}

            # Check for infinite values
            inf_count = np.isinf(self.expression_data).sum().sum()
            checks["infinite_values"] = inf_count

            if inf_count > 0:
                validation_results["warnings"].append(
                    f"{inf_count} infinite values found in expression data"
                )

            # Check for negative values
            neg_count = (self.expression_data < 0).sum().sum()
            checks["negative_values"] = neg_count

            if neg_count > 0:
                validation_results["warnings"].append(
                    f"{neg_count} negative values found in expression data"
                )

            # Check variance
            gene_var = self.expression_data.var(axis=1)
            zero_var_genes = (gene_var == 0).sum()
            checks["zero_variance_genes"] = zero_var_genes

            if zero_var_genes > 0:
                validation_results["warnings"].append(
                    f"{zero_var_genes} genes with zero variance"
                )

            validation_results["checks"]["data_quality"] = checks

    def _check_label_distribution(self, validation_results: Dict[str, Any]):
        """Check label distribution."""
        if self.labels is not None:
            label_counts = self.labels.value_counts()
            checks = {
                "n_classes": len(label_counts),
                "class_counts": label_counts.to_dict(),
                "min_class_size": label_counts.min(),
                "max_class_size": label_counts.max(),
                "class_imbalance_ratio": label_counts.max() / label_counts.min()
                if label_counts.min() > 0
                else float("inf"),
            }

            # Check for class imbalance
            if checks["class_imbalance_ratio"] > 3:
                validation_results["warnings"].append(
                    f"Class imbalance detected: ratio = {checks['class_imbalance_ratio']:.2f}"
                )

            # Check minimum class size
            if checks["min_class_size"] < 5:
                validation_results["warnings"].append(
                    f"Small class size: {checks['min_class_size']} samples"
                )

            validation_results["checks"]["label_distribution"] = checks

    def _generate_dataset_hash(self) -> str:
        """Generate a hash for the dataset."""
        if self.expression_data is not None and self.labels is not None:
            # Create a hash from expression data and labels
            expr_hash = hashlib.md5(self.expression_data.values.tobytes()).hexdigest()[
                :8
            ]
            label_hash = hashlib.md5(self.labels.values.tobytes()).hexdigest()[:8]
            return f"{expr_hash}_{label_hash}"
        return "unknown"

    def _generate_data_summary(self) -> Dict[str, Any]:
        """Generate a summary of the loaded data."""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "dataset_hash": self._generate_dataset_hash(),
        }

        if self.expression_data is not None:
            summary["expression"] = {
                "n_genes": self.expression_data.shape[0],
                "n_samples": self.expression_data.shape[1],
                "value_range": {
                    "min": float(self.expression_data.min().min()),
                    "max": float(self.expression_data.max().max()),
                    "mean": float(self.expression_data.mean().mean()),
                    "std": float(self.expression_data.std().mean()),
                },
            }

        if self.labels is not None:
            summary["labels"] = {
                "n_samples": len(self.labels),
                "n_classes": len(self.labels.unique()),
                "class_distribution": self.labels.value_counts().to_dict(),
            }

        if self.metadata is not None:
            summary["metadata"] = {
                "n_fields": len(self.metadata),
                "fields": list(self.metadata.keys()),
            }

        return summary

    def map_gene_ids(
        self,
        expression_data: pd.DataFrame,
        from_type: str = "ensembl",
        to_type: str = "symbol",
        reference_file: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Map gene IDs between different formats.

        Args:
            expression_data: Expression data matrix
            from_type: Current ID type
            to_type: Target ID type
            reference_file: Path to reference mapping file

        Returns:
            Expression data with mapped gene IDs
        """
        # Load reference mapping
        if reference_file:
            mapping = self._load_gene_mapping(reference_file)
        else:
            mapping = self._get_default_gene_mapping()

        # Create mapping dictionary
        if from_type in mapping and to_type in mapping[from_type]:
            id_map = mapping[from_type][to_type]

            # Map gene IDs
            mapped_genes = []
            for gene in expression_data.index:
                if gene in id_map:
                    mapped_genes.append(id_map[gene])
                else:
                    mapped_genes.append(gene)  # Keep original if no mapping

            # Update index
            mapped_data = expression_data.copy()
            mapped_data.index = mapped_genes

            # Handle duplicates by aggregating
            if mapped_data.index.duplicated().any():
                logger.warning("Duplicate gene IDs after mapping, aggregating by mean")
                mapped_data = mapped_data.groupby(mapped_data.index).mean()

            logger.info(f"Gene ID mapping completed: {from_type} -> {to_type}")
            return mapped_data

        else:
            logger.warning(f"No mapping available from {from_type} to {to_type}")
            return expression_data

    def _load_gene_mapping(
        self, file_path: str
    ) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Load gene ID mapping from file."""
        file_ext = Path(file_path).suffix.lower()

        if file_ext in [".tsv", ".txt"]:
            mapping_df = pd.read_csv(file_path, sep="\t")
        elif file_ext == ".csv":
            mapping_df = pd.read_csv(file_path)
        else:
            raise ValueError(f"Unsupported mapping file format: {file_ext}")

        # Assume columns are: from_id, to_id, from_type, to_type
        mapping = {}
        for _, row in mapping_df.iterrows():
            from_type = row.get("from_type", "ensembl")
            to_type = row.get("to_type", "symbol")
            from_id = row.get("from_id", "")
            to_id = row.get("to_id", "")

            if from_type not in mapping:
                mapping[from_type] = {}
            if to_type not in mapping[from_type]:
                mapping[from_type][to_type] = {}

            mapping[from_type][to_type][from_id] = to_id

        return mapping

    def _get_default_gene_mapping(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Get default gene ID mapping (placeholder)."""
        # This would typically load from a reference database
        # For now, return empty mapping
        return {}

    def save_processed_data(
        self, data: pd.DataFrame, output_path: str, format: str = "tsv"
    ) -> str:
        """
        Save processed data to file.

        Args:
            data: Data to save
            output_path: Output file path
            format: Output format

        Returns:
            Path to saved file
        """
        try:
            if format.lower() == "tsv":
                data.to_csv(output_path, sep="\t")
            elif format.lower() == "csv":
                data.to_csv(output_path)
            elif format.lower() == "h5":
                data.to_hdf(output_path, key="data")
            else:
                raise ValueError(f"Unsupported format: {format}")

            logger.info(f"Data saved to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to save data: {str(e)}")
            raise

    def get_validation_summary(self) -> Dict[str, Any]:
        """
        Get validation summary.

        Returns:
            Validation summary dictionary
        """
        if not self.validation_results:
            return {"status": "No validation performed"}

        return {
            "status": self.validation_results.get("status", "unknown"),
            "n_errors": len(self.validation_results.get("errors", [])),
            "n_warnings": len(self.validation_results.get("warnings", [])),
            "checks": self.validation_results.get("checks", {}),
            "errors": self.validation_results.get("errors", []),
            "warnings": self.validation_results.get("warnings", []),
        }
