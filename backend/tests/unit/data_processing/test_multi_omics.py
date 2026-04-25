"""
Comprehensive unit tests for multi-omics data processing.
"""
import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from app.data_processing.multi_omics import MultiOmicsProcessor


class TestMultiOmicsProcessor:
    """Test cases for MultiOmicsProcessor."""

    def test_multi_omics_processor_initialization(self):
        """Test MultiOmicsProcessor initialization."""
        processor = MultiOmicsProcessor()
        assert processor is not None
        assert processor.config == {}
        assert processor.processed_data == {}
        assert processor.integration_results == {}

    def test_load_expression_data(self):
        """Test loading expression data."""
        processor = MultiOmicsProcessor()

        # Create sample expression data
        np.random.seed(42)
        data = pd.DataFrame(
            np.random.randn(10, 5),
            index=[f"GENE{i:03d}" for i in range(10)],
            columns=[f"SAMPLE{i:03d}" for i in range(5)],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name)
            temp_path = f.name

        try:
            result = processor.load_expression_data(temp_path)
            assert isinstance(result, pd.DataFrame)
            assert result.shape[0] > 0
        finally:
            os.unlink(temp_path)

    def test_load_methylation_data(self):
        """Test loading methylation data."""
        processor = MultiOmicsProcessor()

        # Create sample methylation data
        np.random.seed(42)
        data = pd.DataFrame(
            np.random.rand(10, 5),
            index=[f"PROBE{i:03d}" for i in range(10)],
            columns=[f"SAMPLE{i:03d}" for i in range(5)],
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            data.to_csv(f.name)
            temp_path = f.name

        try:
            result = processor.load_methylation_data(temp_path)
            assert isinstance(result, pd.DataFrame)
        finally:
            os.unlink(temp_path)

    def test_integrate_omics_data(self):
        """Test integrating multiple omics data types."""
        processor = MultiOmicsProcessor()

        # Create sample data - use same samples for alignment
        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(20, 8),
            index=[f"GENE{i:03d}" for i in range(20)],
            columns=[f"SAMPLE{i:03d}" for i in range(8)],
        )

        methylation_data = pd.DataFrame(
            np.random.rand(15, 8),
            index=[f"PROBE{i:03d}" for i in range(15)],
            columns=[f"SAMPLE{i:03d}" for i in range(8)],
        )

        # Load into processor and align (integrate_omics_data uses processed_data)
        processor.processed_data["expression"] = expression_data
        processor.processed_data["methylation"] = methylation_data
        processor.align_omics_data()

        result = processor.integrate_omics_data(
            integration_method="concatenation", feature_selection=False
        )
        assert isinstance(result, pd.DataFrame)

    def test_normalize_omics_data(self):
        """Test normalizing omics data."""
        processor = MultiOmicsProcessor()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(10, 5),
            index=[f"GENE{i:03d}" for i in range(10)],
            columns=[f"SAMPLE{i:03d}" for i in range(5)],
        )

        processor.processed_data["expression"] = expression_data

        result = processor.normalize_omics_data("expression", method="zscore")
        assert isinstance(result, pd.DataFrame)
        assert result.shape == expression_data.shape

    def test_align_omics_data(self):
        """Test aligning omics data."""
        processor = MultiOmicsProcessor()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(10, 5),
            index=[f"GENE{i:03d}" for i in range(10)],
            columns=[f"SAMPLE{i:03d}" for i in range(5)],
        )

        methylation_data = pd.DataFrame(
            np.random.rand(10, 5),
            index=[f"PROBE{i:03d}" for i in range(10)],
            columns=[f"SAMPLE{i:03d}" for i in range(5)],
        )

        processor.processed_data["expression"] = expression_data
        processor.processed_data["methylation"] = methylation_data

        result = processor.align_omics_data("expression")
        assert isinstance(result, dict)
        assert "expression" in result
        assert "methylation" in result
