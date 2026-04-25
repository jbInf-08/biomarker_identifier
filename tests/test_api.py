"""
Integration tests for FastAPI endpoints.
"""

import unittest
import tempfile
import os
import json
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the FastAPI app
import sys
sys.path.append('../backend')

from app.main import app

class TestAPIIntegration(unittest.TestCase):
    """Integration tests for API endpoints."""
    
    def setUp(self):
        """Set up test client and data."""
        self.client = TestClient(app)
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        
        # Create mock expression data
        np.random.seed(42)
        self.expression_data = pd.DataFrame(
            np.random.randn(100, 50),  # 100 genes, 50 samples
            index=[f"GENE_{i:03d}" for i in range(100)],
            columns=[f"SAMPLE_{i:03d}" for i in range(50)]
        )
        
        # Create mock labels
        self.labels = pd.DataFrame({
            'sample_id': self.expression_data.columns,
            'class_label': ["TUMOR"] * 25 + ["NORMAL"] * 25
        })
        
        # Save test files
        self.expression_file = os.path.join(self.temp_dir, "expression.tsv")
        self.labels_file = os.path.join(self.temp_dir, "labels.tsv")
        
        self.expression_data.to_csv(self.expression_file, sep='\t')
        self.labels.to_csv(self.labels_file, sep='\t', index=False)
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Cancer Biomarker Identifier", response.text)
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
    
    def test_api_status_endpoint(self):
        """Test API status endpoint."""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("version", data)
        self.assertIn("status", data)
    
    @patch('app.api.routes.biomarkers.BiomarkerPipeline')
    def test_run_pipeline_endpoint(self, mock_pipeline_class):
        """Test pipeline run endpoint."""
        # Mock pipeline instance
        mock_pipeline = MagicMock()
        mock_pipeline.run_pipeline.return_value = {
            "run_id": "test_run_123",
            "status": "completed",
            "biomarker_list": {
                "biomarkers": [
                    {"gene": "GENE_001", "final_score": 0.9},
                    {"gene": "GENE_002", "final_score": 0.8}
                ]
            }
        }
        mock_pipeline_class.return_value = mock_pipeline
        
        # Prepare files for upload
        with open(self.expression_file, 'rb') as f:
            expression_content = f.read()
        with open(self.labels_file, 'rb') as f:
            labels_content = f.read()
        
        # Test pipeline run
        response = self.client.post(
            "/api/biomarkers/run",
            files={
                "expression_file": ("expression.tsv", expression_content, "text/tab-separated-values"),
                "labels_file": ("labels.tsv", labels_content, "text/tab-separated-values")
            },
            data={
                "run_name": "Test Run",
                "normalization_method": "log2",
                "stats_methods": "t_test",
                "selection_methods": "logistic_regression",
                "n_features": "50"
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("run_id", data)
        self.assertEqual(data["status"], "started")
    
    def test_get_runs_endpoint(self):
        """Test get runs endpoint."""
        response = self.client.get("/api/biomarkers/runs")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, list)
    
    @patch('app.api.routes.biomarkers.pipeline_runs')
    def test_get_run_status_endpoint(self, mock_pipeline_runs):
        """Test get run status endpoint."""
        # Mock pipeline runs
        mock_pipeline_runs.get.return_value = {
            "run_id": "test_run_123",
            "status": "completed",
            "progress": 100
        }
        
        response = self.client.get("/api/biomarkers/runs/test_run_123/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("run_id", data)
        self.assertIn("status", data)
        self.assertIn("progress", data)
    
    @patch('app.api.routes.biomarkers.pipeline_results')
    def test_get_run_results_endpoint(self, mock_pipeline_results):
        """Test get run results endpoint."""
        # Mock pipeline results
        mock_pipeline_results.get.return_value = {
            "run_id": "test_run_123",
            "biomarker_list": {
                "biomarkers": [
                    {"gene": "GENE_001", "final_score": 0.9},
                    {"gene": "GENE_002", "final_score": 0.8}
                ]
            },
            "statistical_analysis": {
                "method_results": {
                    "t_test": {"significant_features": ["GENE_001", "GENE_002"]}
                }
            }
        }
        
        response = self.client.get("/api/biomarkers/runs/test_run_123/results")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("run_id", data)
        self.assertIn("biomarker_list", data)
        self.assertIn("statistical_analysis", data)
    
    @patch('app.api.routes.biomarkers.pipeline_results')
    def test_get_biomarkers_endpoint(self, mock_pipeline_results):
        """Test get biomarkers endpoint."""
        # Mock pipeline results
        mock_pipeline_results.get.return_value = {
            "biomarker_list": {
                "biomarkers": [
                    {"gene": "GENE_001", "final_score": 0.9, "final_rank": 1},
                    {"gene": "GENE_002", "final_score": 0.8, "final_rank": 2}
                ]
            }
        }
        
        response = self.client.get("/api/biomarkers/runs/test_run_123/biomarkers")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("biomarkers", data)
        self.assertEqual(len(data["biomarkers"]), 2)
    
    @patch('app.api.routes.biomarkers.ModelTrainingPipeline')
    def test_train_model_endpoint(self, mock_training_class):
        """Test model training endpoint."""
        # Mock training pipeline
        mock_training = MagicMock()
        mock_training.train_and_evaluate.return_value = {
            "model_performance": {
                "accuracy": 0.85,
                "precision": 0.83,
                "recall": 0.87,
                "f1_score": 0.85
            },
            "cross_validation": {
                "accuracy": [0.82, 0.85, 0.88]
            }
        }
        mock_training_class.return_value = mock_training
        
        response = self.client.post(
            "/api/biomarkers/runs/test_run_123/train-model",
            json={
                "model_type": "logistic_regression",
                "features": ["GENE_001", "GENE_002", "GENE_003"],
                "cv_folds": 5
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("model_performance", data)
        self.assertIn("cross_validation", data)
    
    @patch('app.api.routes.biomarkers.SHAPExplainer')
    def test_shap_analysis_endpoint(self, mock_shap_class):
        """Test SHAP analysis endpoint."""
        # Mock SHAP explainer
        mock_explainer = MagicMock()
        mock_explainer.compute_shap_values.return_value = {
            "global_analysis": {
                "feature_importance": {"GENE_001": 0.3, "GENE_002": 0.2}
            },
            "local_analysis": {
                "sample_contributions": {}
            }
        }
        mock_shap_class.return_value = mock_explainer
        
        response = self.client.post(
            "/api/biomarkers/runs/test_run_123/shap-analysis",
            json={
                "model_type": "logistic_regression",
                "features": ["GENE_001", "GENE_002"]
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("global_analysis", data)
        self.assertIn("local_analysis", data)
    
    @patch('app.api.routes.biomarkers.PathwayAnalysis')
    def test_pathway_analysis_endpoint(self, mock_pathway_class):
        """Test pathway analysis endpoint."""
        # Mock pathway analyzer
        mock_analyzer = MagicMock()
        mock_analyzer.run_pathway_analysis.return_value = {
            "gsea_results": {
                "KEGG": {
                    "results": [
                        {"pathway": "pathway1", "fdr": 0.01},
                        {"pathway": "pathway2", "fdr": 0.05}
                    ]
                }
            },
            "ora_results": {
                "KEGG": {
                    "results": [
                        {"pathway": "pathway1", "adj_pval": 0.01}
                    ]
                }
            }
        }
        mock_pathway_class.return_value = mock_analyzer
        
        response = self.client.post(
            "/api/biomarkers/runs/test_run_123/pathway-analysis",
            json={
                "gene_list": ["GENE_001", "GENE_002", "GENE_003"],
                "analysis_type": "both",
                "gene_sets": ["KEGG", "REACTOME"]
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("gsea_results", data)
        self.assertIn("ora_results", data)
    
    @patch('app.api.routes.biomarkers.GeneAnnotation')
    def test_annotate_endpoint(self, mock_annotation_class):
        """Test gene annotation endpoint."""
        # Mock gene annotator
        mock_annotator = MagicMock()
        mock_annotator.annotate_genes.return_value = {
            "annotations": {
                "GENE_001": {
                    "basic_info": {"symbol": "GENE_001", "name": "Test Gene"},
                    "cancer_info": {"COSMIC": {"status": "placeholder"}},
                    "clinical_info": {"ClinVar": {"status": "placeholder"}}
                }
            }
        }
        mock_annotation_class.return_value = mock_annotator
        
        response = self.client.post(
            "/api/biomarkers/runs/test_run_123/annotate",
            json={
                "gene_list": ["GENE_001", "GENE_002"],
                "databases": ["COSMIC", "ClinVar", "OncoKB"]
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("annotations", data)
        self.assertIn("GENE_001", data["annotations"])
    
    @patch('app.api.routes.biomarkers.ReportGenerator')
    def test_generate_report_endpoint(self, mock_report_class):
        """Test report generation endpoint."""
        # Mock report generator
        mock_generator = MagicMock()
        mock_generator.generate_report.return_value = {
            "report_path": "/reports/test_run_123_report.html",
            "report_url": "/api/reports/test_run_123_report.html"
        }
        mock_report_class.return_value = mock_generator
        
        response = self.client.post(
            "/api/biomarkers/runs/test_run_123/report",
            json={
                "report_format": "html",
                "report_title": "Test Report",
                "include_appendices": True
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("report_path", data)
        self.assertIn("report_url", data)
    
    def test_delete_run_endpoint(self):
        """Test delete run endpoint."""
        response = self.client.delete("/api/biomarkers/runs/test_run_123")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["message"], "Run deleted successfully")
    
    def test_cgas_integration_endpoints(self):
        """Test CGAS integration endpoints."""
        # Test mutation endpoint
        response = self.client.get("/api/cgas/mutations/TP53")
        self.assertEqual(response.status_code, 200)
        
        # Test pathway endpoint
        response = self.client.get("/api/cgas/pathways/TP53")
        self.assertEqual(response.status_code, 200)
    
    def test_invalid_file_upload(self):
        """Test invalid file upload."""
        # Test with missing files
        response = self.client.post(
            "/api/biomarkers/run",
            data={"run_name": "Test Run"}
        )
        self.assertEqual(response.status_code, 422)  # Validation error
        
        # Test with invalid file format
        response = self.client.post(
            "/api/biomarkers/run",
            files={
                "expression_file": ("expression.txt", b"invalid content", "text/plain"),
                "labels_file": ("labels.txt", b"invalid content", "text/plain")
            },
            data={"run_name": "Test Run"}
        )
        self.assertEqual(response.status_code, 422)
    
    def test_invalid_run_id(self):
        """Test invalid run ID handling."""
        response = self.client.get("/api/biomarkers/runs/invalid_run_id/status")
        self.assertEqual(response.status_code, 404)
        
        response = self.client.get("/api/biomarkers/runs/invalid_run_id/results")
        self.assertEqual(response.status_code, 404)
    
    def test_cors_headers(self):
        """Test CORS headers are present."""
        response = self.client.options("/api/biomarkers/runs")
        self.assertIn("access-control-allow-origin", response.headers)
        self.assertIn("access-control-allow-methods", response.headers)

class TestDataValidation(unittest.TestCase):
    """Test data validation endpoints."""
    
    def setUp(self):
        """Set up test client."""
        self.client = TestClient(app)
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up after tests."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_expression_data_validation(self):
        """Test expression data validation."""
        # Create valid expression data
        expression_data = pd.DataFrame(
            np.random.randn(10, 5),
            index=[f"GENE_{i}" for i in range(10)],
            columns=[f"SAMPLE_{i}" for i in range(5)]
        )
        
        expression_file = os.path.join(self.temp_dir, "expression.tsv")
        expression_data.to_csv(expression_file, sep='\t')
        
        with open(expression_file, 'rb') as f:
            content = f.read()
        
        response = self.client.post(
            "/api/data/validate-expression",
            files={"file": ("expression.tsv", content, "text/tab-separated-values")}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_valid"])
    
    def test_labels_validation(self):
        """Test labels validation."""
        # Create valid labels
        labels = pd.DataFrame({
            'sample_id': [f"SAMPLE_{i}" for i in range(5)],
            'class_label': ["TUMOR", "TUMOR", "NORMAL", "NORMAL", "NORMAL"]
        })
        
        labels_file = os.path.join(self.temp_dir, "labels.tsv")
        labels.to_csv(labels_file, sep='\t', index=False)
        
        with open(labels_file, 'rb') as f:
            content = f.read()
        
        response = self.client.post(
            "/api/data/validate-labels",
            files={"file": ("labels.tsv", content, "text/tab-separated-values")}
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_valid"])
    
    def test_data_compatibility(self):
        """Test data compatibility validation."""
        # Create compatible expression and labels
        expression_data = pd.DataFrame(
            np.random.randn(10, 5),
            index=[f"GENE_{i}" for i in range(10)],
            columns=[f"SAMPLE_{i}" for i in range(5)]
        )
        
        labels = pd.DataFrame({
            'sample_id': [f"SAMPLE_{i}" for i in range(5)],
            'class_label': ["TUMOR", "TUMOR", "NORMAL", "NORMAL", "NORMAL"]
        })
        
        expression_file = os.path.join(self.temp_dir, "expression.tsv")
        labels_file = os.path.join(self.temp_dir, "labels.tsv")
        
        expression_data.to_csv(expression_file, sep='\t')
        labels.to_csv(labels_file, sep='\t', index=False)
        
        with open(expression_file, 'rb') as f:
            expr_content = f.read()
        with open(labels_file, 'rb') as f:
            labels_content = f.read()
        
        response = self.client.post(
            "/api/data/validate-compatibility",
            files={
                "expression_file": ("expression.tsv", expr_content, "text/tab-separated-values"),
                "labels_file": ("labels.tsv", labels_content, "text/tab-separated-values")
            }
        )
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["is_compatible"])

if __name__ == '__main__':
    unittest.main()
