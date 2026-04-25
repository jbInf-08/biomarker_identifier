"""
Comprehensive unit tests for data loader.
"""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from app.data_processing.data_loader import DataLoader


class TestDataLoader:
    """Test cases for DataLoader."""

    def test_data_loader_initialization(self):
        """Test DataLoader initialization."""
        loader = DataLoader()
        assert loader is not None
        assert loader.config == {}

    def test_load_expression_data_csv(self):
        """Test loading expression data from CSV."""
        loader = DataLoader()

        # DataLoader requires: index_col=0 (genes as index), >=10 genes, >=5 samples
        np.random.seed(42)
        n_genes, n_samples = 20, 8
        gene_names = [f"GENE{i:04d}" for i in range(n_genes)]
        sample_names = [f"Sample{i}" for i in range(n_samples)]
        data = np.random.lognormal(5, 1, (n_genes, n_samples))
        df = pd.DataFrame(data, index=gene_names, columns=sample_names)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df.to_csv(f.name)
            temp_path = f.name

        try:
            result = loader.load_expression_data(temp_path)
            assert isinstance(result, pd.DataFrame)
            assert result.shape[0] >= 10
            assert result.shape[1] >= 5
        finally:
            os.unlink(temp_path)

    def test_load_expression_data_tsv(self):
        """Test loading expression data from TSV."""
        loader = DataLoader()

        np.random.seed(42)
        n_genes, n_samples = 20, 8
        gene_names = [f"GENE{i:04d}" for i in range(n_genes)]
        sample_names = [f"Sample{i}" for i in range(n_samples)]
        data = np.random.lognormal(5, 1, (n_genes, n_samples))
        df = pd.DataFrame(data, index=gene_names, columns=sample_names)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False) as f:
            df.to_csv(f.name, sep="\t")
            temp_path = f.name

        try:
            result = loader.load_expression_data(temp_path)
            assert isinstance(result, pd.DataFrame)
        finally:
            os.unlink(temp_path)

    def test_load_labels(self):
        """Test loading labels."""
        loader = DataLoader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            df = pd.DataFrame(
                {"sample_id": ["S1", "S2", "S3"], "class_label": ["A", "B", "A"]}
            )
            df.to_csv(f.name, index=False)
            temp_path = f.name

        try:
            result = loader.load_labels(temp_path)
            assert isinstance(result, pd.DataFrame)
            assert "class_label" in result.columns
        finally:
            os.unlink(temp_path)

    def test_load_metadata(self):
        """Test loading metadata."""
        loader = DataLoader()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("project: test\ninvestigator: test\n")
            temp_path = f.name

        try:
            result = loader.load_metadata(temp_path)
            assert isinstance(result, dict)
        finally:
            os.unlink(temp_path)

    def test_validate_data_integrity(self, test_data_files):
        """Test validating data integrity."""
        loader = DataLoader()
        loader.load_expression_data(test_data_files["expression_file"])
        loader.load_labels(test_data_files["clinical_file"])

        validation = loader.validate_data_integrity()
        assert isinstance(validation, dict)
        assert "status" in validation
        assert "issues" in validation

    def test_align_data(self, test_data_files):
        """Test aligning data."""
        loader = DataLoader()
        loader.load_expression_data(test_data_files["expression_file"])
        loader.load_labels(test_data_files["clinical_file"])

        aligned_expr, aligned_labels = loader.align_data()
        assert isinstance(aligned_expr, pd.DataFrame)
        assert isinstance(aligned_labels, pd.DataFrame)
        assert len(aligned_expr.columns) == len(aligned_labels)
