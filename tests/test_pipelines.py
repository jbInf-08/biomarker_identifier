"""
Unit tests for pipeline modules.
"""

import unittest
import pandas as pd
import numpy as np
import tempfile
import os
import json
from unittest.mock import patch, MagicMock

# Import pipeline modules
import sys
sys.path.append('../backend')

from app.pipelines.biomarker_pipeline import BiomarkerPipeline
from app.pipelines.train_eval import ModelTrainingPipeline
from app.pipelines.shap_tools import SHAPExplainer
from app.pipelines.pathways import PathwayAnalysis
from app.pipelines.annotate import GeneAnnotation
from app.pipelines.report import ReportGenerator

class TestBiomarkerPipeline(unittest.TestCase):
    """Test cases for BiomarkerPipeline."""
    
    def setUp(self):
        """Set up test data."""
        # Create mock expression data
        np.random.seed(42)
        self.expression_data = pd.DataFrame(
            np.random.randn(100, 50),  # 100 genes, 50 samples
            index=[f"GENE_{i:03d}" for i in range(100)],
            columns=[f"SAMPLE_{i:03d}" for i in range(50)]
        )
        
        # Create mock labels
        self.labels = pd.Series(
            ["TUMOR"] * 25 + ["NORMAL"] * 25,
            index=self.expression_data.columns
        )
        
        # Create temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        config = {"test_param": "test_value"}
        pipeline = BiomarkerPipeline(config)
        
        self.assertEqual(pipeline.config, config)
        self.assertIsNone(pipeline.run_id)
        self.assertEqual(pipeline.pipeline_results, {})
    
    def test_run_id_generation(self):
        """Test run ID generation."""
        pipeline = BiomarkerPipeline()
        
        # Test with run name
        run_id = pipeline._generate_run_id("test_run")
        self.assertIn("test_run", run_id)
        self.assertIn("_", run_id)
        
        # Test without run name
        run_id = pipeline._generate_run_id(None)
        self.assertIn("biomarker_run", run_id)
    
    def test_biomarker_list_generation(self):
        """Test biomarker list generation."""
        pipeline = BiomarkerPipeline()
        
        # Mock statistical results
        stats_results = {
            "method_results": {
                "t_test": {
                    "significant_features_adjusted": ["GENE_001", "GENE_002", "GENE_003"]
                }
            }
        }
        
        # Mock ML results
        ml_results = {
            "consensus_features": {
                "consensus_features": [
                    {"feature": "GENE_001", "consensus_score": 0.8, "selection_count": 4, "methods": ["method1"]},
                    {"feature": "GENE_002", "consensus_score": 0.6, "selection_count": 3, "methods": ["method2"]}
                ]
            }
        }
        
        biomarker_list = pipeline._generate_biomarker_list(stats_results, ml_results)
        
        self.assertIn("biomarkers", biomarker_list)
        self.assertIn("summary", biomarker_list)
        self.assertGreater(len(biomarker_list["biomarkers"]), 0)
    
    def test_pipeline_summary_generation(self):
        """Test pipeline summary generation."""
        pipeline = BiomarkerPipeline()
        
        # Mock results
        results = {
            "run_id": "test_run",
            "run_name": "Test Run",
            "timestamp": "2024-01-01T00:00:00",
            "pipeline_steps": ["step1", "step2"],
            "data_loading": {
                "expression_data": self.expression_data,
                "labels": self.labels
            },
            "biomarker_list": {
                "summary": {
                    "total_biomarkers": 10,
                    "high_confidence": 5
                }
            }
        }
        
        summary = pipeline._generate_pipeline_summary(results)
        
        self.assertIn("run_id", summary)
        self.assertIn("data_summary", summary)
        self.assertIn("results_summary", summary)
        self.assertEqual(summary["run_id"], "test_run")

class TestModelTrainingPipeline(unittest.TestCase):
    """Test cases for ModelTrainingPipeline."""
    
    def setUp(self):
        """Set up test data."""
        np.random.seed(42)
        self.X = pd.DataFrame(
            np.random.randn(100, 20),  # 100 samples, 20 features
            columns=[f"FEATURE_{i:02d}" for i in range(20)]
        )
        self.y = pd.Series(np.random.choice([0, 1], 100))
    
    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        config = {"test_param": "test_value"}
        pipeline = ModelTrainingPipeline(config)
        
        self.assertEqual(pipeline.config, config)
        self.assertEqual(pipeline.training_results, {})
    
    def test_model_training(self):
        """Test model training."""
        pipeline = ModelTrainingPipeline()
        
        # Test logistic regression training
        model = pipeline._train_model(self.X, self.y, "logistic_regression")
        self.assertIsNotNone(model)
        
        # Test random forest training
        model = pipeline._train_model(self.X, self.y, "random_forest")
        self.assertIsNotNone(model)
    
    def test_model_evaluation(self):
        """Test model evaluation."""
        pipeline = ModelTrainingPipeline()
        
        # Train a model first
        model = pipeline._train_model(self.X, self.y, "logistic_regression")
        
        # Split data for evaluation
        from sklearn.model_selection import train_test_split
        X_train, X_test, y_train, y_test = train_test_split(self.X, self.y, test_size=0.3, random_state=42)
        
        # Evaluate model
        evaluation = pipeline._evaluate_model(model, X_test, y_test)
        
        self.assertIn("accuracy", evaluation)
        self.assertIn("precision", evaluation)
        self.assertIn("recall", evaluation)
        self.assertIn("f1_score", evaluation)
        self.assertIn("confusion_matrix", evaluation)
    
    def test_cross_validation(self):
        """Test cross-validation."""
        pipeline = ModelTrainingPipeline()
        
        # Train a model first
        model = pipeline._train_model(self.X, self.y, "logistic_regression")
        
        # Perform cross-validation
        cv_results = pipeline._cross_validate_model(model, self.X, self.y, cv_folds=3, random_state=42)
        
        self.assertIn("accuracy", cv_results)
        self.assertIn("precision", cv_results)
        self.assertIn("recall", cv_results)
        self.assertIn("f1_score", cv_results)

class TestSHAPExplainer(unittest.TestCase):
    """Test cases for SHAPExplainer."""
    
    def setUp(self):
        """Set up test data."""
        np.random.seed(42)
        self.X = pd.DataFrame(
            np.random.randn(50, 10),  # 50 samples, 10 features
            columns=[f"FEATURE_{i:02d}" for i in range(10)]
        )
        self.y = pd.Series(np.random.choice([0, 1], 50))
    
    def test_explainer_initialization(self):
        """Test explainer initialization."""
        config = {"test_param": "test_value"}
        explainer = SHAPExplainer(config)
        
        self.assertEqual(explainer.config, config)
        self.assertEqual(explainer.shap_results, {})
    
    def test_explainer_type_detection(self):
        """Test explainer type detection."""
        explainer = SHAPExplainer()
        
        # Mock different model types
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression
        
        rf_model = RandomForestClassifier()
        lr_model = LogisticRegression()
        
        # Test tree explainer detection
        explainer_type = explainer._determine_explainer_type(rf_model)
        self.assertEqual(explainer_type, "tree")
        
        # Test linear explainer detection
        explainer_type = explainer._determine_explainer_type(lr_model)
        self.assertEqual(explainer_type, "linear")
    
    @patch('app.pipelines.shap_tools.shap')
    def test_shap_computation(self, mock_shap):
        """Test SHAP computation with mocked SHAP library."""
        explainer = SHAPExplainer()
        
        # Mock SHAP explainer and values
        mock_explainer = MagicMock()
        mock_explainer.expected_value = 0.5
        mock_shap.TreeExplainer.return_value = mock_explainer
        
        mock_shap_values = np.random.randn(50, 10)
        mock_explainer.return_value = mock_shap_values
        
        # Test SHAP computation
        with patch.object(explainer, '_determine_explainer_type', return_value='tree'):
            with patch.object(explainer, '_create_explainer', return_value=mock_explainer):
                results = explainer.compute_shap_values(
                    MagicMock(),  # Mock model
                    self.X,
                    explainer_type="tree"
                )
        
        self.assertIn("shap_values", results)
        self.assertIn("expected_value", results)
        self.assertIn("global_analysis", results)
        self.assertIn("local_analysis", results)

class TestPathwayAnalysis(unittest.TestCase):
    """Test cases for PathwayAnalysis."""
    
    def setUp(self):
        """Set up test data."""
        self.gene_list = ["GENE_001", "GENE_002", "GENE_003", "GENE_004", "GENE_005"]
        self.expression_data = pd.DataFrame(
            np.random.randn(5, 20),  # 5 genes, 20 samples
            index=self.gene_list,
            columns=[f"SAMPLE_{i:02d}" for i in range(20)]
        )
        self.labels = pd.Series(["TUMOR"] * 10 + ["NORMAL"] * 10, index=self.expression_data.columns)
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        config = {"test_param": "test_value"}
        analyzer = PathwayAnalysis(config)
        
        self.assertEqual(analyzer.config, config)
        self.assertEqual(analyzer.pathway_results, {})
    
    def test_gene_set_mapping(self):
        """Test gene set name mapping."""
        analyzer = PathwayAnalysis()
        
        # Test KEGG mapping
        mapped_name = analyzer._map_gene_set_name("KEGG")
        self.assertEqual(mapped_name, "KEGG_2021_Human")
        
        # Test Reactome mapping
        mapped_name = analyzer._map_gene_set_name("REACTOME")
        self.assertEqual(mapped_name, "Reactome_2022")
        
        # Test unknown mapping
        mapped_name = analyzer._map_gene_set_name("UNKNOWN")
        self.assertEqual(mapped_name, "UNKNOWN")
    
    def test_differential_expression_calculation(self):
        """Test differential expression calculation."""
        analyzer = PathwayAnalysis()
        
        de_results = analyzer._calculate_differential_expression(self.expression_data, self.labels)
        
        self.assertIsInstance(de_results, pd.DataFrame)
        self.assertEqual(len(de_results), len(self.gene_list))
        self.assertIn("log2fc", de_results.columns)
    
    def test_pathway_summary_generation(self):
        """Test pathway summary generation."""
        analyzer = PathwayAnalysis()
        
        # Mock results
        results = {
            "gene_list": self.gene_list,
            "analysis_type": "both",
            "gene_sets": ["KEGG", "REACTOME"],
            "gsea_results": {
                "KEGG": {
                    "results": [
                        {"pathway": "pathway1", "fdr": 0.01},
                        {"pathway": "pathway2", "fdr": 0.05}
                    ],
                    "status": "success"
                }
            },
            "ora_results": {
                "KEGG": {
                    "results": [
                        {"pathway": "pathway1", "adj_pval": 0.01},
                        {"pathway": "pathway2", "adj_pval": 0.05}
                    ],
                    "status": "success"
                }
            }
        }
        
        summary = analyzer._generate_pathway_summary(results)
        
        self.assertIn("n_genes", summary)
        self.assertIn("analysis_type", summary)
        self.assertIn("gsea_summary", summary)
        self.assertIn("ora_summary", summary)

class TestGeneAnnotation(unittest.TestCase):
    """Test cases for GeneAnnotation."""
    
    def setUp(self):
        """Set up test data."""
        self.gene_list = ["TP53", "BRCA1", "BRCA2", "EGFR", "KRAS"]
    
    def test_annotator_initialization(self):
        """Test annotator initialization."""
        config = {"test_param": "test_value"}
        annotator = GeneAnnotation(config)
        
        self.assertEqual(annotator.config, config)
        self.assertEqual(annotator.annotation_results, {})
        self.assertEqual(annotator.cache, {})
    
    def test_basic_gene_info(self):
        """Test basic gene information retrieval."""
        annotator = GeneAnnotation()
        
        gene_info = annotator._get_basic_gene_info("TP53")
        
        self.assertIn("symbol", gene_info)
        self.assertIn("name", gene_info)
        self.assertIn("chromosome", gene_info)
        self.assertIn("description", gene_info)
        self.assertEqual(gene_info["symbol"], "TP53")
    
    def test_cancer_info_retrieval(self):
        """Test cancer information retrieval."""
        annotator = GeneAnnotation()
        
        cancer_info = annotator._get_cancer_info("TP53", ["COSMIC", "OncoKB"])
        
        self.assertIn("COSMIC", cancer_info)
        self.assertIn("OncoKB", cancer_info)
        self.assertIn("status", cancer_info["COSMIC"])
    
    def test_clinical_info_retrieval(self):
        """Test clinical information retrieval."""
        annotator = GeneAnnotation()
        
        clinical_info = annotator._get_clinical_info("TP53", ["ClinVar", "OncoKB"])
        
        self.assertIn("ClinVar", clinical_info)
        self.assertIn("OncoKB", clinical_info)
        self.assertIn("status", clinical_info["ClinVar"])
    
    def test_annotation_summary_generation(self):
        """Test annotation summary generation."""
        annotator = GeneAnnotation()
        
        # Mock results
        results = {
            "gene_list": self.gene_list,
            "databases": ["COSMIC", "ClinVar"],
            "annotations": {
                "TP53": {
                    "cancer_info": {"COSMIC": {"status": "placeholder"}},
                    "clinical_info": {"ClinVar": {"status": "placeholder"}}
                },
                "BRCA1": {
                    "cancer_info": {"COSMIC": {"status": "placeholder"}},
                    "clinical_info": {"ClinVar": {"status": "placeholder"}}
                }
            }
        }
        
        summary = annotator._generate_annotation_summary(results)
        
        self.assertIn("n_genes", summary)
        self.assertIn("databases_queried", summary)
        self.assertIn("cancer_genes", summary)
        self.assertIn("clinical_genes", summary)
        self.assertEqual(summary["n_genes"], 5)

class TestReportGenerator(unittest.TestCase):
    """Test cases for ReportGenerator."""
    
    def setUp(self):
        """Set up test data."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock pipeline results
        self.pipeline_results = {
            "run_id": "test_run",
            "run_name": "Test Run",
            "timestamp": "2024-01-01T00:00:00",
            "pipeline_steps": ["step1", "step2"],
            "config": {"test_param": "test_value"},
            "data_loading": {
                "expression_data": pd.DataFrame(np.random.randn(100, 50)),
                "labels": pd.Series(["TUMOR"] * 25 + ["NORMAL"] * 25)
            },
            "biomarker_list": {
                "summary": {
                    "total_biomarkers": 10,
                    "high_confidence": 5
                }
            }
        }
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_generator_initialization(self):
        """Test generator initialization."""
        config = {"test_param": "test_value"}
        generator = ReportGenerator(config)
        
        self.assertEqual(generator.config, config)
        self.assertEqual(generator.report_data, {})
    
    def test_report_data_preparation(self):
        """Test report data preparation."""
        generator = ReportGenerator()
        
        report_data = generator._prepare_report_data(self.pipeline_results)
        
        self.assertIn("metadata", report_data)
        self.assertIn("pipeline_summary", report_data)
        self.assertIn("data_summary", report_data)
        self.assertIn("results_summary", report_data)
        self.assertIn("figures", report_data)
        self.assertIn("tables", report_data)
        self.assertIn("methods", report_data)
        self.assertIn("appendices", report_data)
    
    def test_methods_info_extraction(self):
        """Test methods information extraction."""
        generator = ReportGenerator()
        
        # Add more detailed results to pipeline_results
        self.pipeline_results.update({
            "quality_control": {
                "summary": {
                    "status": "passed",
                    "warnings": ["warning1"],
                    "recommendations": ["rec1"]
                }
            },
            "normalization": {
                "normalization_method": "log2",
                "batch_correction_applied": False
            },
            "statistical_analysis": {
                "summary": {
                    "methods_applied": ["t_test"],
                    "total_significant_features": 15
                },
                "alpha": 0.05
            },
            "ml_selection": {
                "summary": {
                    "methods_applied": ["logistic_regression"],
                    "consensus_features_count": 8
                },
                "stability_bootstraps": 100
            }
        })
        
        methods = generator._extract_methods_info(self.pipeline_results)
        
        self.assertIn("data_processing", methods)
        self.assertIn("statistical_analysis", methods)
        self.assertIn("machine_learning", methods)
    
    def test_figures_extraction(self):
        """Test figures extraction."""
        generator = ReportGenerator()
        
        # Add mock figures to pipeline_results
        self.pipeline_results.update({
            "quality_control": {
                "plots": {"qc_plot": "mock_plot"}
            },
            "statistical_analysis": {
                "plots": {"volcano_plot": "mock_plot"}
            },
            "ml_selection": {
                "plots": {"feature_importance": "mock_plot"}
            }
        })
        
        figures = generator._extract_figures(self.pipeline_results)
        
        self.assertIn("quality_control", figures)
        self.assertIn("statistical_analysis", figures)
        self.assertIn("machine_learning", figures)
    
    def test_tables_extraction(self):
        """Test tables extraction."""
        generator = ReportGenerator()
        
        # Add mock biomarker list to pipeline_results
        self.pipeline_results["biomarker_list"]["biomarkers"] = [
            {"gene": "GENE_001", "final_score": 0.9, "consensus_score": 0.8},
            {"gene": "GENE_002", "final_score": 0.7, "consensus_score": 0.6}
        ]
        
        tables = generator._extract_tables(self.pipeline_results)
        
        self.assertIn("biomarker_list", tables)
        self.assertEqual(len(tables["biomarker_list"]), 2)
    
    def test_appendices_extraction(self):
        """Test appendices extraction."""
        generator = ReportGenerator()
        
        appendices = generator._extract_appendices(self.pipeline_results)
        
        self.assertIn("configuration", appendices)
        self.assertIn("pipeline_steps", appendices)
        self.assertIn("run_metadata", appendices)
        self.assertEqual(appendices["run_metadata"]["run_id"], "test_run")

if __name__ == '__main__':
    unittest.main()
