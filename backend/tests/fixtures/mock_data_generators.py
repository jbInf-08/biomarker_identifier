"""
Comprehensive mock data generators for testing.
Provides reusable fixtures for generating test data across all test scenarios.
"""
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

try:
    from faker import Faker

    fake = Faker()
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False
    # Fallback for when faker is not available
    import random

    fake = None


class MockDataGenerator:
    """Base class for mock data generation."""

    @staticmethod
    def generate_gene_expression_data(
        n_samples: int = 50, n_genes: int = 1000, seed: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Generate mock gene expression data.

        Args:
            n_samples: Number of samples
            n_genes: Number of genes
            seed: Random seed for reproducibility

        Returns:
            DataFrame with samples as rows and genes as columns
        """
        if seed is not None:
            np.random.seed(seed)

        # Generate gene names
        gene_names = [f"GENE_{i:05d}" for i in range(1, n_genes + 1)]

        # Generate sample names
        sample_names = [f"SAMPLE_{i:03d}" for i in range(1, n_samples + 1)]

        # Generate expression values (log-transformed counts)
        expression_data = np.random.lognormal(
            mean=5, sigma=2, size=(n_samples, n_genes)
        )

        df = pd.DataFrame(expression_data, index=sample_names, columns=gene_names)

        return df

    @staticmethod
    def generate_clinical_data(
        n_samples: int = 50, include_survival: bool = True, seed: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Generate mock clinical data.

        Args:
            n_samples: Number of samples
            include_survival: Whether to include survival data
            seed: Random seed for reproducibility

        Returns:
            DataFrame with clinical annotations
        """
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)

        sample_names = [f"SAMPLE_{i:03d}" for i in range(1, n_samples + 1)]

        data = {
            "sample_id": sample_names,
            "age": np.random.randint(30, 80, n_samples),
            "gender": np.random.choice(["M", "F"], n_samples),
            "stage": np.random.choice(
                ["I", "II", "III", "IV"], n_samples, p=[0.2, 0.3, 0.3, 0.2]
            ),
            "grade": np.random.choice(["G1", "G2", "G3"], n_samples, p=[0.3, 0.4, 0.3]),
            "tumor_type": np.random.choice(
                ["TypeA", "TypeB", "TypeC"], n_samples, p=[0.4, 0.3, 0.3]
            ),
            "treatment": np.random.choice(
                ["Treatment1", "Treatment2", "Control"], n_samples, p=[0.4, 0.3, 0.3]
            ),
        }

        if include_survival:
            data["survival_time"] = np.random.exponential(
                scale=365, size=n_samples
            ).astype(int)
            data["survival_status"] = np.random.choice([0, 1], n_samples, p=[0.4, 0.6])

        return pd.DataFrame(data)

    @staticmethod
    def generate_mutation_data(
        n_samples: int = 50, n_mutations: int = 100, seed: Optional[int] = None
    ) -> pd.DataFrame:
        """
        Generate mock mutation data.

        Args:
            n_samples: Number of samples
            n_mutations: Number of mutations to generate
            seed: Random seed for reproducibility

        Returns:
            DataFrame with mutation annotations
        """
        if seed is not None:
            random.seed(seed)

        sample_names = [f"SAMPLE_{i:03d}" for i in range(1, n_samples + 1)]
        gene_names = [f"GENE_{i:05d}" for i in range(1, 501)]

        mutations = []
        mutation_types = ["SNV", "Insertion", "Deletion", "CNV"]
        impacts = ["High", "Moderate", "Low", "Modifier"]

        for _ in range(n_mutations):
            mutations.append(
                {
                    "sample_id": random.choice(sample_names),
                    "gene": random.choice(gene_names),
                    "mutation_type": random.choice(mutation_types),
                    "impact": random.choice(impacts),
                    "chromosome": random.randint(1, 22),
                    "position": random.randint(1, 100000000),
                    "ref_allele": random.choice(["A", "T", "G", "C"]),
                    "alt_allele": random.choice(["A", "T", "G", "C"]),
                    "vaf": np.random.uniform(0.05, 1.0),
                }
            )

        return pd.DataFrame(mutations)

    @staticmethod
    def generate_biomarker_result(
        gene_name: str,
        fold_change: float = 2.0,
        p_value: float = 0.001,
        fdr: float = 0.05,
    ) -> Dict:
        """Generate a mock biomarker result."""
        return {
            "gene": gene_name,
            "fold_change": fold_change,
            "p_value": p_value,
            "fdr": fdr,
            "log2fc": np.log2(fold_change),
            "t_statistic": np.random.normal(0, 1),
            "base_mean": np.random.uniform(100, 10000),
        }

    @staticmethod
    def generate_analysis_run_config(n_samples: int = 50, n_genes: int = 1000) -> Dict:
        """Generate a mock analysis run configuration."""
        return {
            "n_samples": n_samples,
            "n_genes": n_genes,
            "normalization_method": "log_cpm",
            "feature_selection_method": "variance",
            "model_type": "random_forest",
            "cv_folds": 5,
            "random_seed": 42,
        }

    @staticmethod
    def generate_user_data(
        n_users: int = 5, include_admin: bool = True, seed: Optional[int] = None
    ) -> List[Dict]:
        """Generate mock user data for testing."""
        if seed is not None:
            random.seed(seed)
            if FAKER_AVAILABLE:
                Faker.seed(seed)

        users = []
        roles = ["researcher"] * (n_users - (1 if include_admin else 0))
        if include_admin:
            roles.append("admin")

        random.shuffle(roles)

        for i, role in enumerate(roles):
            name = fake.name() if FAKER_AVAILABLE else f"User {i+1}"
            institution = fake.company() if FAKER_AVAILABLE else f"Institution {i+1}"
            users.append(
                {
                    "email": f"user{i+1}@example.com",
                    "name": name,
                    "password": "testpassword123",
                    "role": role,
                    "institution": institution,
                    "is_active": True,
                    "is_verified": True,
                }
            )

        return users

    @staticmethod
    def generate_metadata_dict() -> Dict:
        """Generate a mock metadata dictionary."""
        return {
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "version": "1.0.0",
            "source": "test",
            "description": "Mock metadata for testing",
        }


class TestDataFactory:
    """Factory class for creating test data scenarios."""

    @staticmethod
    def create_small_dataset(seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Create a small test dataset (10 samples, 100 genes)."""
        expr_data = MockDataGenerator.generate_gene_expression_data(
            n_samples=10, n_genes=100, seed=seed
        )
        clinical_data = MockDataGenerator.generate_clinical_data(
            n_samples=10, include_survival=True, seed=seed
        )
        return expr_data, clinical_data

    @staticmethod
    def create_medium_dataset(seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Create a medium test dataset (50 samples, 1000 genes)."""
        expr_data = MockDataGenerator.generate_gene_expression_data(
            n_samples=50, n_genes=1000, seed=seed
        )
        clinical_data = MockDataGenerator.generate_clinical_data(
            n_samples=50, include_survival=True, seed=seed
        )
        return expr_data, clinical_data

    @staticmethod
    def create_large_dataset(seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Create a large test dataset (200 samples, 5000 genes)."""
        expr_data = MockDataGenerator.generate_gene_expression_data(
            n_samples=200, n_genes=5000, seed=seed
        )
        clinical_data = MockDataGenerator.generate_clinical_data(
            n_samples=200, include_survival=True, seed=seed
        )
        return expr_data, clinical_data

    @staticmethod
    def create_imbalanced_dataset(seed: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Create an imbalanced dataset for testing."""
        expr_data = MockDataGenerator.generate_gene_expression_data(
            n_samples=50, n_genes=1000, seed=seed
        )
        clinical_data = MockDataGenerator.generate_clinical_data(
            n_samples=50, include_survival=True, seed=seed
        )
        # Make class distribution imbalanced (80% class 0, 20% class 1)
        clinical_data["treatment"] = np.random.choice(
            ["Treatment1", "Control"], size=50, p=[0.2, 0.8]
        )
        return expr_data, clinical_data

    @staticmethod
    def create_dataset_with_missing_values(
        missing_fraction: float = 0.1, seed: int = 42
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Create a dataset with missing values."""
        expr_data, clinical_data = TestDataFactory.create_medium_dataset(seed=seed)

        # Introduce missing values in expression data
        n_missing = int(expr_data.size * missing_fraction)
        missing_indices = np.random.choice(
            expr_data.size, size=n_missing, replace=False
        )
        expr_data.values.flat[missing_indices] = np.nan

        # Introduce missing values in clinical data
        clinical_data.loc[
            np.random.choice(
                clinical_data.index,
                size=int(len(clinical_data) * missing_fraction),
                replace=False,
            ),
            "age",
        ] = np.nan

        return expr_data, clinical_data
