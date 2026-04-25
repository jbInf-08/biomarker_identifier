"""
Comprehensive unit tests for pathway analysis pipeline.
"""
import numpy as np
import pandas as pd
import pytest

from app.pipelines.pathways import PathwayAnalysis


class TestPathwayAnalysis:
    """Test cases for PathwayAnalysis."""

    def test_pathway_analysis_initialization(self):
        """Test PathwayAnalysis initialization."""
        pathway_analyzer = PathwayAnalysis()
        assert pathway_analyzer is not None
        assert pathway_analyzer.config == {}
        assert pathway_analyzer.pathway_results == {}

    def test_pathway_analysis_initialization_with_config(self):
        """Test PathwayAnalysis initialization with config."""
        config = {"test": "value"}
        pathway_analyzer = PathwayAnalysis(config=config)
        assert pathway_analyzer.config == config

    def test_run_pathway_analysis_ora(self):
        """Test running ORA pathway analysis."""
        pathway_analyzer = PathwayAnalysis()

        gene_list = ["TP53", "BRCA1", "BRCA2", "KRAS", "EGFR"]
        results = pathway_analyzer.run_pathway_analysis(
            gene_list=gene_list, analysis_type="ora", gene_sets=["KEGG"]
        )

        assert results is not None
        assert "gene_list" in results
        assert "analysis_type" in results
        assert "ora_results" in results
        assert "summary" in results

    def test_run_pathway_analysis_gsea(self):
        """Test running GSEA pathway analysis."""
        pathway_analyzer = PathwayAnalysis()

        # Create sample expression data
        np.random.seed(42)
        n_samples = 50
        n_genes = 100
        gene_names = [f"GENE{i:03d}" for i in range(n_genes)]
        sample_names = [f"SAMPLE{i:03d}" for i in range(n_samples)]
        expression_data = pd.DataFrame(
            np.random.randn(n_genes, n_samples), index=gene_names, columns=sample_names
        )

        labels = pd.Series(np.random.choice([0, 1], n_samples), index=sample_names)

        results = pathway_analyzer.run_pathway_analysis(
            gene_list=gene_names[:20],
            expression_data=expression_data,
            labels=labels,
            analysis_type="gsea",
            gene_sets=["KEGG"],
        )

        assert results is not None
        assert "gsea_results" in results

    def test_run_pathway_analysis_both(self):
        """Test running both ORA and GSEA."""
        pathway_analyzer = PathwayAnalysis()

        gene_list = ["TP53", "BRCA1", "BRCA2"]
        results = pathway_analyzer.run_pathway_analysis(
            gene_list=gene_list, analysis_type="both"
        )

        assert results is not None
        assert "ora_results" in results

    def test_run_ora(self):
        """Test ORA analysis."""
        pathway_analyzer = PathwayAnalysis()

        gene_list = ["TP53", "BRCA1", "BRCA2"]
        results = pathway_analyzer._run_ora(gene_list, ["KEGG"])
        assert isinstance(results, dict)

    def test_run_gsea(self):
        """Test GSEA analysis."""
        pathway_analyzer = PathwayAnalysis()

        np.random.seed(42)
        expression_data = pd.DataFrame(
            np.random.randn(50, 20),
            index=[f"GENE{i:03d}" for i in range(50)],
            columns=[f"SAMPLE{i:03d}" for i in range(20)],
        )
        labels = pd.Series(np.random.choice([0, 1], 20))

        results = pathway_analyzer._run_gsea(expression_data, labels, ["KEGG"])
        assert isinstance(results, dict)

    def test_generate_pathway_summary(self):
        """Test generating pathway summary."""
        pathway_analyzer = PathwayAnalysis()

        results = {
            "gene_list": ["TP53", "BRCA1", "BRCA2"],
            "ora_results": {"pathways": []},
            "gsea_results": {},
        }
        summary = pathway_analyzer._generate_pathway_summary(results)
        assert isinstance(summary, dict)

    def test_generate_pathway_plots(self):
        """Test generating pathway plots."""
        pathway_analyzer = PathwayAnalysis()

        results = {"ora_results": {}, "gsea_results": {}}
        plots = pathway_analyzer._generate_pathway_plots(results)
        assert isinstance(plots, dict)

    def test_run_pathway_analysis_empty_gene_list(self):
        """Test pathway analysis with empty gene list."""
        pathway_analyzer = PathwayAnalysis()

        results = pathway_analyzer.run_pathway_analysis(gene_list=[])
        assert results is not None
        assert len(results["gene_list"]) == 0
