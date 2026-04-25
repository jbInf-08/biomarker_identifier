"""
Data loading and validation for the Cancer Biomarker Identifier application.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class DataLoader:
    """
    Handles data loading, validation, and preprocessing for biomarker analysis.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the data loader.

        Args:
            config: Configuration dictionary
        """
        self.config = config or {}
        self.expression_data = None
        self.labels = None
        self.metadata = None
        self.validation_results = {}

    def load_expression_data(self, file_path: str, **kwargs) -> pd.DataFrame:
        """
        Load expression data from various file formats.

        Args:
            file_path: Path to expression data file
            **kwargs: Additional arguments for pandas read functions

        Returns:
            Expression data as DataFrame
        """
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                raise FileNotFoundError(f"Expression file not found: {file_path}")

            # Determine file format and load
            if file_path.suffix.lower() in [".csv", ".txt", ".tsv"]:
                # Try to detect delimiter
                with open(file_path, "r") as f:
                    first_line = f.readline().strip()

                if "\t" in first_line or file_path.suffix.lower() == ".tsv":
                    df = pd.read_csv(file_path, sep="\t", index_col=0, **kwargs)
                else:
                    df = pd.read_csv(file_path, index_col=0, **kwargs)

            elif file_path.suffix.lower() in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path, index_col=0, **kwargs)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")

            # Basic validation
            if df.empty:
                raise ValueError("Expression data is empty")

            if df.shape[0] < 10:
                raise ValueError("Expression data has too few genes (< 10)")

            if df.shape[1] < 5:
                raise ValueError("Expression data has too few samples (< 5)")

            # Ensure numeric data
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            if len(numeric_cols) != len(df.columns):
                logger.warning(
                    f"Non-numeric columns found: {set(df.columns) - set(numeric_cols)}"
                )
                df = df[numeric_cols]

            # Remove genes with all zeros or NaNs
            df = df.loc[(df != 0).any(axis=1) & df.notna().any(axis=1)]

            self.expression_data = df
            logger.info(
                f"Loaded expression data: {df.shape[0]} genes, {df.shape[1]} samples"
            )

            return df

        except Exception as e:
            logger.error(f"Failed to load expression data: {str(e)}")
            raise

    def load_labels(
        self,
        file_path: str,
        sample_id_col: str = "sample_id",
        label_col: str = "class_label",
        **kwargs,
    ) -> pd.DataFrame:
        """
        Load clinical labels and metadata.

        Args:
            file_path: Path to labels file
            sample_id_col: Name of sample ID column
            label_col: Name of label column
            **kwargs: Additional arguments for pandas read functions

        Returns:
            Labels data as DataFrame
        """
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                raise FileNotFoundError(f"Labels file not found: {file_path}")

            # Load labels file
            if file_path.suffix.lower() in [".csv", ".txt", ".tsv"]:
                with open(file_path, "r") as f:
                    first_line = f.readline().strip()

                if "\t" in first_line or file_path.suffix.lower() == ".tsv":
                    df = pd.read_csv(file_path, sep="\t", **kwargs)
                else:
                    df = pd.read_csv(file_path, **kwargs)

            elif file_path.suffix.lower() in [".xlsx", ".xls"]:
                df = pd.read_excel(file_path, **kwargs)
            else:
                raise ValueError(f"Unsupported file format: {file_path.suffix}")

            # Validate required columns
            if sample_id_col not in df.columns:
                raise ValueError(f"Sample ID column '{sample_id_col}' not found")

            if label_col not in df.columns:
                raise ValueError(f"Label column '{label_col}' not found")

            # Set sample_id as index
            df = df.set_index(sample_id_col)

            # Basic validation
            if df.empty:
                raise ValueError("Labels data is empty")

            if df[label_col].isna().all():
                raise ValueError("All labels are missing")

            # Check for duplicate sample IDs
            if df.index.duplicated().any():
                raise ValueError("Duplicate sample IDs found")

            self.labels = df
            logger.info(
                f"Loaded labels: {len(df)} samples, {len(df.columns)} variables"
            )

            return df

        except Exception as e:
            logger.error(f"Failed to load labels: {str(e)}")
            raise

    def load_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Load project metadata from YAML file.

        Args:
            file_path: Path to metadata file

        Returns:
            Metadata dictionary
        """
        try:
            file_path = Path(file_path)

            if not file_path.exists():
                logger.warning(f"Metadata file not found: {file_path}")
                return {}

            with open(file_path, "r") as f:
                metadata = yaml.safe_load(f)

            self.metadata = metadata
            logger.info("Loaded project metadata")

            return metadata

        except Exception as e:
            logger.error(f"Failed to load metadata: {str(e)}")
            return {}

    def validate_data_integrity(self) -> Dict[str, Any]:
        """
        Validate data integrity and consistency.

        Returns:
            Validation results dictionary
        """
        validation_results = {
            "status": "valid",
            "issues": [],
            "warnings": [],
            "summary": {},
        }

        try:
            if self.expression_data is None:
                validation_results["status"] = "error"
                validation_results["issues"].append("Expression data not loaded")
                return validation_results

            if self.labels is None:
                validation_results["status"] = "error"
                validation_results["issues"].append("Labels data not loaded")
                return validation_results

            # Check sample intersection
            expr_samples = set(self.expression_data.columns)
            label_samples = set(self.labels.index)

            common_samples = expr_samples & label_samples
            expr_only = expr_samples - label_samples
            label_only = label_samples - expr_samples

            validation_results["summary"]["sample_intersection"] = {
                "expression_samples": len(expr_samples),
                "label_samples": len(label_samples),
                "common_samples": len(common_samples),
                "expression_only": len(expr_only),
                "label_only": len(label_only),
            }

            if len(common_samples) == 0:
                validation_results["status"] = "error"
                validation_results["issues"].append(
                    "No common samples between expression and labels"
                )
                return validation_results

            if len(common_samples) < 5:
                validation_results["status"] = "error"
                validation_results["issues"].append("Too few common samples (< 5)")
                return validation_results

            if len(expr_only) > 0:
                validation_results["warnings"].append(
                    f"{len(expr_only)} samples in expression data only"
                )

            if len(label_only) > 0:
                validation_results["warnings"].append(
                    f"{len(label_only)} samples in labels only"
                )

            # Check for missing values
            expr_missing = self.expression_data.isna().sum().sum()
            expr_total = self.expression_data.size
            expr_missing_pct = (expr_missing / expr_total) * 100

            validation_results["summary"]["missing_values"] = {
                "expression_missing": expr_missing,
                "expression_missing_pct": expr_missing_pct,
                "label_missing": self.labels.isna().sum().to_dict(),
            }

            if expr_missing_pct > 50:
                validation_results["status"] = "error"
                validation_results["issues"].append(
                    "Too many missing values in expression data (> 50%)"
                )

            elif expr_missing_pct > 20:
                validation_results["warnings"].append(
                    "High percentage of missing values in expression data"
                )

            # Check for zero-inflation
            expr_zeros = (self.expression_data == 0).sum().sum()
            expr_zero_pct = (expr_zeros / expr_total) * 100

            validation_results["summary"]["zero_inflation"] = {
                "expression_zeros": expr_zeros,
                "expression_zero_pct": expr_zero_pct,
            }

            if expr_zero_pct > 80:
                validation_results["warnings"].append(
                    "High zero-inflation in expression data"
                )

            # Check class balance
            label_col = self.config.get("label_column", "class_label")
            if label_col in self.labels.columns:
                class_counts = self.labels[label_col].value_counts()
                min_class_size = class_counts.min()
                max_class_size = class_counts.max()
                class_ratio = min_class_size / max_class_size

                validation_results["summary"]["class_balance"] = {
                    "class_counts": class_counts.to_dict(),
                    "class_ratio": class_ratio,
                }

                if class_ratio < 0.1:
                    validation_results["warnings"].append(
                        "Severe class imbalance detected"
                    )
                elif class_ratio < 0.3:
                    validation_results["warnings"].append(
                        "Moderate class imbalance detected"
                    )

            # Check for batch effects
            batch_col = self.config.get("batch_column")
            if batch_col and batch_col in self.labels.columns:
                batch_counts = self.labels[batch_col].value_counts()
                validation_results["summary"]["batch_info"] = {
                    "batch_counts": batch_counts.to_dict(),
                    "n_batches": len(batch_counts),
                }

                if len(batch_counts) > 1:
                    validation_results["warnings"].append(
                        "Multiple batches detected - consider batch correction"
                    )

            self.validation_results = validation_results
            logger.info(f"Data validation completed: {validation_results['status']}")

            return validation_results

        except Exception as e:
            logger.error(f"Data validation failed: {str(e)}")
            validation_results["status"] = "error"
            validation_results["issues"].append(f"Validation error: {str(e)}")
            return validation_results

    def align_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Align expression data and labels by common samples.

        Returns:
            Tuple of (aligned_expression, aligned_labels)
        """
        if self.expression_data is None or self.labels is None:
            raise ValueError("Both expression data and labels must be loaded")

        # Get common samples
        expr_samples = set(self.expression_data.columns)
        label_samples = set(self.labels.index)
        common_samples = expr_samples & label_samples

        if len(common_samples) == 0:
            raise ValueError("No common samples between expression and labels")

        # Align data
        aligned_expr = self.expression_data[list(common_samples)]
        aligned_labels = self.labels.loc[list(common_samples)]

        logger.info(
            f"Aligned data: {aligned_expr.shape[0]} genes, {aligned_expr.shape[1]} samples"
        )

        return aligned_expr, aligned_labels

    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive data summary.

        Returns:
            Data summary dictionary
        """
        summary = {
            "expression_data": None,
            "labels": None,
            "metadata": self.metadata or {},
            "validation": self.validation_results,
        }

        if self.expression_data is not None:
            summary["expression_data"] = {
                "shape": self.expression_data.shape,
                "dtypes": self.expression_data.dtypes.value_counts().to_dict(),
                "missing_values": self.expression_data.isna().sum().sum(),
                "missing_percentage": (
                    self.expression_data.isna().sum().sum() / self.expression_data.size
                )
                * 100,
                "zero_values": (self.expression_data == 0).sum().sum(),
                "zero_percentage": (
                    (self.expression_data == 0).sum().sum() / self.expression_data.size
                )
                * 100,
                "value_range": {
                    "min": float(self.expression_data.min().min()),
                    "max": float(self.expression_data.max().max()),
                    "mean": float(self.expression_data.mean().mean()),
                    "std": float(self.expression_data.std().mean()),
                },
            }

        if self.labels is not None:
            summary["labels"] = {
                "shape": self.labels.shape,
                "columns": list(self.labels.columns),
                "missing_values": self.labels.isna().sum().to_dict(),
                "categorical_columns": list(
                    self.labels.select_dtypes(include=["object"]).columns
                ),
                "numeric_columns": list(
                    self.labels.select_dtypes(include=[np.number]).columns
                ),
            }

            # Add class distribution if available
            label_col = self.config.get("label_column", "class_label")
            if label_col in self.labels.columns:
                summary["labels"]["class_distribution"] = (
                    self.labels[label_col].value_counts().to_dict()
                )

        return summary

    def save_processed_data(
        self, output_dir: str, prefix: str = "processed"
    ) -> Dict[str, str]:
        """
        Save processed data to files.

        Args:
            output_dir: Output directory
            prefix: File prefix

        Returns:
            Dictionary of saved file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files = {}

        try:
            if self.expression_data is not None:
                expr_file = output_dir / f"{prefix}_expression.tsv"
                self.expression_data.to_csv(expr_file, sep="\t")
                saved_files["expression"] = str(expr_file)

            if self.labels is not None:
                labels_file = output_dir / f"{prefix}_labels.tsv"
                self.labels.to_csv(labels_file, sep="\t")
                saved_files["labels"] = str(labels_file)

            if self.metadata:
                metadata_file = output_dir / f"{prefix}_metadata.yaml"
                with open(metadata_file, "w") as f:
                    yaml.dump(self.metadata, f, default_flow_style=False)
                saved_files["metadata"] = str(metadata_file)

            # Save validation results
            if self.validation_results:
                validation_file = output_dir / f"{prefix}_validation.yaml"
                with open(validation_file, "w") as f:
                    yaml.dump(self.validation_results, f, default_flow_style=False)
                saved_files["validation"] = str(validation_file)

            logger.info(f"Saved processed data to {output_dir}")
            return saved_files

        except Exception as e:
            logger.error(f"Failed to save processed data: {str(e)}")
            raise
