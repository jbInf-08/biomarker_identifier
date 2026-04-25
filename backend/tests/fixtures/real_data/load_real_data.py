"""
Load actual real data from downloaded files.

This module loads genuine data downloaded from TCGA, GEO, and other sources.
"""
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd

# Base path for real data
REAL_DATA_DIR = Path(__file__).parent


def load_tcga_expression_data() -> Optional[pd.DataFrame]:
    """
    Load actual TCGA expression data if available.

    Returns:
        TCGA expression DataFrame or None if not available
    """
    # Try CSV first
    csv_file = REAL_DATA_DIR / "tcga_brca_expression_real.csv"
    tsv_file = REAL_DATA_DIR / "tcga_brca_expression_real.tsv"

    if csv_file.exists():
        try:
            df = pd.read_csv(csv_file, index_col=0)
            print(f"Loaded real TCGA data from: {csv_file.name}")
            return df
        except Exception as e:
            print(f"Error loading TCGA CSV: {e}")

    if tsv_file.exists():
        try:
            df = pd.read_csv(tsv_file, sep="\t", index_col=0)
            print(f"Loaded real TCGA data from: {tsv_file.name}")
            return df
        except Exception as e:
            print(f"Error loading TCGA TSV: {e}")

    return None


def load_tcga_clinical_data() -> Optional[pd.DataFrame]:
    """Load actual TCGA clinical data if available."""
    clinical_file = REAL_DATA_DIR / "tcga_brca_clinical_real.csv"

    if clinical_file.exists():
        try:
            df = pd.read_csv(clinical_file, index_col=0)
            print(f"Loaded real TCGA clinical data from: {clinical_file.name}")
            return df
        except Exception as e:
            print(f"Error loading TCGA clinical data: {e}")

    return None


def load_geo_expression_data() -> Optional[pd.DataFrame]:
    """Load actual GEO expression data if available."""
    geo_file = REAL_DATA_DIR / "geo_expression_real.csv"

    if geo_file.exists():
        try:
            df = pd.read_csv(geo_file, index_col=0)
            print(f"Loaded real GEO data from: {geo_file.name}")
            return df
        except Exception as e:
            print(f"Error loading GEO data: {e}")

    return None


def get_real_data_status() -> Dict[str, bool]:
    """Check which real data files are available."""
    return {
        "tcga_expression": (REAL_DATA_DIR / "tcga_brca_expression_real.csv").exists()
        or (REAL_DATA_DIR / "tcga_brca_expression_real.tsv").exists(),
        "tcga_clinical": (REAL_DATA_DIR / "tcga_brca_clinical_real.csv").exists(),
        "geo_expression": (REAL_DATA_DIR / "geo_expression_real.csv").exists(),
    }


def load_real_expression_data(dataset_name: str = "default") -> pd.DataFrame:
    """
    Load REAL expression data ONLY - no fallback to generated data.

    Args:
        dataset_name: Name of dataset to load

    Returns:
        Expression DataFrame with REAL data

    Raises:
        FileNotFoundError: If no real data files are available
    """
    # Try to load real TCGA data first
    real_data = load_tcga_expression_data()
    if real_data is not None:
        return real_data

    # Try GEO data
    real_data = load_geo_expression_data()
    if real_data is not None:
        return real_data

    # NO FALLBACK - raise error if no real data
    raise FileNotFoundError(
        "No real expression data files found. "
        "Please download real data using: python backend/scripts/setup_real_data.py"
    )


def load_real_clinical_data(dataset_name: str = "default") -> pd.DataFrame:
    """
    Load REAL clinical data ONLY - no fallback to generated data.

    Args:
        dataset_name: Name of dataset to load

    Returns:
        Clinical DataFrame with REAL data

    Raises:
        FileNotFoundError: If no real data files are available
    """
    # Try to load real TCGA clinical data
    real_data = load_tcga_clinical_data()
    if real_data is not None:
        return real_data

    # NO FALLBACK - raise error if no real data
    raise FileNotFoundError(
        "No real clinical data files found. "
        "Please download real data using: python backend/scripts/setup_real_data.py"
    )
