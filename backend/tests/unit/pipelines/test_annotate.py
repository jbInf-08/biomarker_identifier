"""
Comprehensive unit tests for annotation pipeline.
"""
import numpy as np
import pandas as pd
import pytest

from app.pipelines.annotate import GeneAnnotation


class TestGeneAnnotation:
    """Test cases for GeneAnnotation."""

    def test_gene_annotation_initialization(self):
        """Test GeneAnnotation initialization."""
        annotator = GeneAnnotation()
        assert annotator is not None
        assert annotator.config == {}
        assert annotator.annotation_results == {}
        assert annotator.cache == {}

    def test_gene_annotation_initialization_with_config(self):
        """Test GeneAnnotation initialization with config."""
        config = {"test": "value"}
        annotator = GeneAnnotation(config=config)
        assert annotator.config == config

    def test_annotate_genes_basic(self):
        """Test basic gene annotation."""
        annotator = GeneAnnotation()

        gene_list = ["TP53", "BRCA1", "BRCA2"]
        results = annotator.annotate_genes(
            gene_list=gene_list,
            databases=["COSMIC", "ClinVar"],
            include_expression=False,
            include_mutations=False,
            include_pathways=False,
        )

        assert results is not None
        assert "gene_list" in results
        assert "databases" in results
        assert "annotations" in results
        assert "summary" in results
        assert len(results["annotations"]) == len(gene_list)

    def test_annotate_genes_with_expression(self):
        """Test gene annotation with expression data."""
        annotator = GeneAnnotation()

        gene_list = ["TP53", "BRCA1"]
        results = annotator.annotate_genes(
            gene_list=gene_list,
            include_expression=True,
            include_mutations=False,
            include_pathways=False,
        )

        assert results is not None
        assert len(results["annotations"]) == len(gene_list)

    def test_annotate_genes_with_mutations(self):
        """Test gene annotation with mutation data."""
        annotator = GeneAnnotation()

        gene_list = ["TP53", "KRAS"]
        results = annotator.annotate_genes(
            gene_list=gene_list,
            include_expression=False,
            include_mutations=True,
            include_pathways=False,
        )

        assert results is not None
        assert len(results["annotations"]) == len(gene_list)

    def test_annotate_genes_with_pathways(self):
        """Test gene annotation with pathway data."""
        annotator = GeneAnnotation()

        gene_list = ["TP53", "BRCA1"]
        results = annotator.annotate_genes(
            gene_list=gene_list,
            include_expression=False,
            include_mutations=False,
            include_pathways=True,
        )

        assert results is not None
        assert len(results["annotations"]) == len(gene_list)

    def test_annotate_genes_all_features(self):
        """Test gene annotation with all features."""
        annotator = GeneAnnotation()

        gene_list = ["TP53"]
        results = annotator.annotate_genes(
            gene_list=gene_list,
            include_expression=True,
            include_mutations=True,
            include_pathways=True,
        )

        assert results is not None
        assert len(results["annotations"]) == 1

    def test_get_basic_gene_info(self):
        """Test getting basic gene information."""
        annotator = GeneAnnotation()

        info = annotator._get_basic_gene_info("TP53")
        assert isinstance(info, dict)

    def test_get_cancer_info(self):
        """Test getting cancer information."""
        annotator = GeneAnnotation()

        info = annotator._get_cancer_info("TP53", ["COSMIC"])
        assert isinstance(info, dict)

    def test_get_clinical_info(self):
        """Test getting clinical information."""
        annotator = GeneAnnotation()

        info = annotator._get_clinical_info("TP53", ["ClinVar"])
        assert isinstance(info, dict)

    def test_get_expression_info(self):
        """Test getting expression information."""
        annotator = GeneAnnotation()

        info = annotator._get_expression_info("TP53")
        assert isinstance(info, dict)

    def test_get_mutation_info(self):
        """Test getting mutation information."""
        annotator = GeneAnnotation()

        info = annotator._get_mutation_info("TP53", ["COSMIC"])
        assert isinstance(info, dict)

    def test_get_pathway_info(self):
        """Test getting pathway information."""
        annotator = GeneAnnotation()

        info = annotator._get_pathway_info("TP53")
        assert isinstance(info, dict)

    def test_annotate_genes_empty_list(self):
        """Test annotation with empty gene list."""
        annotator = GeneAnnotation()

        results = annotator.annotate_genes(gene_list=[])
        assert results is not None
        assert len(results["annotations"]) == 0

    def test_annotate_genes_single_gene(self):
        """Test annotation with single gene."""
        annotator = GeneAnnotation()

        results = annotator.annotate_genes(gene_list=["TP53"])
        assert results is not None
        assert len(results["annotations"]) == 1
