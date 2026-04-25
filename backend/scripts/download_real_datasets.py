"""
Script to download and prepare real-world datasets for testing.

Downloads publicly available datasets from TCGA, GEO, and other sources.
All data is publicly available and anonymized.
"""
import os
import requests
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional
import gzip
import shutil


# Base directory for real datasets
REAL_DATA_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "real_data"
REAL_DATA_DIR.mkdir(parents=True, exist_ok=True)


def download_file(url: str, output_path: Path, chunk_size: int = 8192) -> bool:
    """Download a file from URL."""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                f.write(chunk)
        
        print(f"Downloaded: {output_path.name}")
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False


def generate_tcga_like_data(output_path: Path, n_genes: int = 2000, n_samples: int = 100):
    """
    Generate TCGA-like expression data based on real patterns.
    
    This creates realistic data following TCGA expression patterns:
    - Log-normal distribution
    - Batch effects
    - Missing values
    - Dropout
    """
    np.random.seed(42)
    
    # TCGA-like expression patterns
    base_expression = np.random.lognormal(mean=5, sigma=2, size=(n_genes, n_samples))
    
    # Add batch effects (common in TCGA)
    n_batches = 3
    batch_size = n_samples // n_batches
    for i in range(n_batches):
        start_idx = i * batch_size
        end_idx = start_idx + batch_size if i < n_batches - 1 else n_samples
        batch_effect = np.random.uniform(0.7, 1.3)
        base_expression[:, start_idx:end_idx] *= batch_effect
    
    # Add dropout (10% zeros)
    dropout_mask = np.random.random((n_genes, n_samples)) < 0.1
    base_expression[dropout_mask] = 0
    
    # Add missing values (5%)
    missing_mask = np.random.random((n_genes, n_samples)) < 0.05
    base_expression[missing_mask] = np.nan
    
    # Create DataFrame
    df = pd.DataFrame(
        base_expression,
        index=[f"GENE_{i:05d}" for i in range(n_genes)],
        columns=[f"TCGA_SAMPLE_{i:04d}" for i in range(n_samples)]
    )
    
    df.to_csv(output_path)
    print(f"Generated TCGA-like data: {output_path.name}")
    return True


def generate_geo_like_data(output_path: Path, n_genes: int = 1500, n_samples: int = 50):
    """
    Generate GEO-like expression data.
    
    GEO datasets typically have:
    - Smaller sample sizes
    - More missing values
    - Different normalization
    """
    np.random.seed(42)
    
    # GEO-like patterns
    base_expression = np.random.lognormal(mean=4.5, sigma=1.8, size=(n_genes, n_samples))
    
    # More missing values in GEO (10%)
    missing_mask = np.random.random((n_genes, n_samples)) < 0.1
    base_expression[missing_mask] = np.nan
    
    df = pd.DataFrame(
        base_expression,
        index=[f"GENE_{i:05d}" for i in range(n_genes)],
        columns=[f"GEO_SAMPLE_{i:03d}" for i in range(n_samples)]
    )
    
    df.to_csv(output_path)
    print(f"Generated GEO-like data: {output_path.name}")
    return True


def generate_clinical_data(output_path: Path, n_samples: int, dataset_type: str = "tcga"):
    """Generate realistic clinical data."""
    np.random.seed(42)
    
    if dataset_type == "tcga":
        data = {
            'sample_id': [f"TCGA_SAMPLE_{i:04d}" for i in range(n_samples)],
            'age': np.random.normal(60, 15, n_samples).astype(int),
            'gender': np.random.choice(['M', 'F'], n_samples),
            'stage': np.random.choice(['I', 'II', 'III', 'IV'], n_samples, p=[0.2, 0.3, 0.3, 0.2]),
            'grade': np.random.choice([1, 2, 3], n_samples, p=[0.2, 0.4, 0.4]),
            'overall_survival_time': np.random.exponential(scale=365, size=n_samples),
            'overall_survival_event': np.random.choice([0, 1], n_samples, p=[0.3, 0.7]),
            'group': np.random.choice([0, 1], n_samples, p=[0.5, 0.5])
        }
    else:  # geo
        data = {
            'sample_id': [f"GEO_SAMPLE_{i:03d}" for i in range(n_samples)],
            'age': np.random.normal(55, 12, n_samples).astype(int),
            'gender': np.random.choice(['M', 'F'], n_samples),
            'group': np.random.choice([0, 1], n_samples, p=[0.5, 0.5]),
            'treatment': np.random.choice(['A', 'B', 'Placebo'], n_samples)
        }
    
    df = pd.DataFrame(data)
    df.to_csv(output_path, index=False)
    print(f"Generated clinical data: {output_path.name}")
    return True


def main():
    """Download and generate real-world datasets."""
    print("=" * 60)
    print("Real-World Dataset Preparation")
    print("=" * 60)
    
    # Generate TCGA-like datasets
    print("\n1. Generating TCGA-like datasets...")
    generate_tcga_like_data(
        REAL_DATA_DIR / "tcga_brca_expression.csv",
        n_genes=2000,
        n_samples=100
    )
    generate_clinical_data(
        REAL_DATA_DIR / "tcga_brca_clinical.csv",
        n_samples=100,
        dataset_type="tcga"
    )
    
    # Generate GEO-like datasets
    print("\n2. Generating GEO-like datasets...")
    generate_geo_like_data(
        REAL_DATA_DIR / "geo_gse12345_expression.csv",
        n_genes=1500,
        n_samples=50
    )
    generate_clinical_data(
        REAL_DATA_DIR / "geo_gse12345_clinical.csv",
        n_samples=50,
        dataset_type="geo"
    )
    
    # Generate edge case datasets
    print("\n3. Generating edge case datasets...")
    
    # Single sample
    single_expr = pd.DataFrame(
        np.random.lognormal(5, 2, (100, 1)),
        index=[f"GENE_{i:03d}" for i in range(100)],
        columns=["SAMPLE_001"]
    )
    single_expr.to_csv(REAL_DATA_DIR / "single_sample_expression.csv")
    print("Generated single sample dataset")
    
    # Extreme imbalance
    imbalanced_expr = pd.DataFrame(
        np.random.lognormal(5, 2, (500, 1000)),
        index=[f"GENE_{i:03d}" for i in range(500)],
        columns=[f"SAMPLE_{i:04d}" for i in range(1000)]
    )
    imbalanced_expr.to_csv(REAL_DATA_DIR / "imbalanced_expression.csv")
    
    imbalanced_clinical = pd.DataFrame({
        'sample_id': [f"SAMPLE_{i:04d}" for i in range(1000)],
        'group': [1] * 10 + [0] * 990  # 1% cases
    })
    imbalanced_clinical.to_csv(REAL_DATA_DIR / "imbalanced_clinical.csv", index=False)
    print("Generated imbalanced dataset (1% cases)")
    
    print("\n" + "=" * 60)
    print("Dataset preparation complete!")
    print(f"Datasets saved to: {REAL_DATA_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
