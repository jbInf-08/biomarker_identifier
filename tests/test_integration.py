"""
Integration tests for the Cancer Biomarker Identifier application.
"""

import pytest
import asyncio
import json
import os
import tempfile
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.core.database import get_db, Base
from backend.app.models.run_model import AnalysisRun, RunStatus
from backend.app.models.biomarker_model import BiomarkerResult

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module")
def setup_database():
    """Set up test database."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)

@pytest.fixture
def sample_expression_data():
    """Create sample expression data file."""
    data = """Gene_Symbol,Sample_001,Sample_002,Sample_003,Sample_004
TP53,8.2,7.9,8.5,7.8
BRCA1,6.1,5.8,6.3,5.9
KRAS,7.4,7.2,7.6,7.1
MYC,9.1,8.9,9.3,8.8
EGFR,5.2,5.0,5.4,4.9"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(data)
        temp_file = f.name
    
    yield temp_file
    os.unlink(temp_file)

@pytest.fixture
def sample_labels_data():
    """Create sample labels data file."""
    data = """Sample_ID,Phenotype,Age,Stage
Sample_001,Tumor,65,III
Sample_002,Normal,62,NA
Sample_003,Tumor,58,II
Sample_004,Normal,70,NA"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(data)
        temp_file = f.name
    
    yield temp_file
    os.unlink(temp_file)

class TestBiomarkerAPI:
    """Test biomarker API endpoints."""
    
    def test_start_pipeline(self, client, setup_database, sample_expression_data, sample_labels_data):
        """Test starting a biomarker analysis pipeline."""
        with open(sample_expression_data, 'rb') as expr_file, \
             open(sample_labels_data, 'rb') as labels_file:
            
            config = {
                "normalization_method": "log2",
                "statistical_test": "welch_t",
                "alpha": 0.05,
                "ml_models": ["logistic_regression"]
            }
            
            response = client.post(
                "/api/biomarkers/run",
                files={
                    "expression_file": ("expression.csv", expr_file, "text/csv"),
                    "labels_file": ("labels.csv", labels_file, "text/csv")
                },
                data={
                    "run_name": "Test Analysis",
                    "config": json.dumps(config)
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "run_id" in data
        assert data["status"] == "started"
        assert data["run_name"] == "Test Analysis"
        
        return data["run_id"]
    
    def test_get_runs(self, client, setup_database):
        """Test getting list of analysis runs."""
        response = client.get("/api/biomarkers/runs")
        assert response.status_code == 200
        data = response.json()
        assert "runs" in data
        assert isinstance(data["runs"], list)
    
    def test_get_run_status(self, client, setup_database, sample_expression_data, sample_labels_data):
        """Test getting run status."""
        # First start a pipeline
        run_id = self.test_start_pipeline(client, setup_database, sample_expression_data, sample_labels_data)
        
        # Then get its status
        response = client.get(f"/api/biomarkers/runs/{run_id}/status")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert "status" in data
        assert "progress" in data
    
    def test_get_run_results(self, client, setup_database, sample_expression_data, sample_labels_data):
        """Test getting run results."""
        # First start a pipeline
        run_id = self.test_start_pipeline(client, setup_database, sample_expression_data, sample_labels_data)
        
        # Then get its results (may be empty if not completed)
        response = client.get(f"/api/biomarkers/runs/{run_id}/results")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert "status" in data
    
    def test_get_biomarkers(self, client, setup_database, sample_expression_data, sample_labels_data):
        """Test getting biomarkers for a run."""
        # First start a pipeline
        run_id = self.test_start_pipeline(client, setup_database, sample_expression_data, sample_labels_data)
        
        # Then get biomarkers
        response = client.get(f"/api/biomarkers/runs/{run_id}/biomarkers")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert "biomarkers" in data
        assert "total_count" in data
    
    def test_delete_run(self, client, setup_database, sample_expression_data, sample_labels_data):
        """Test deleting a run."""
        # First start a pipeline
        run_id = self.test_start_pipeline(client, setup_database, sample_expression_data, sample_labels_data)
        
        # Then delete it
        response = client.delete(f"/api/biomarkers/runs/{run_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == run_id
        assert data["status"] == "deleted"

class TestClinicalAPI:
    """Test clinical database API endpoints."""
    
    def test_get_cosmic_mutations(self, client):
        """Test getting COSMIC mutation data."""
        response = client.get("/api/clinical/cosmic/mutations?gene_symbol=TP53")
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert data["database"] == "COSMIC"
        assert "mutations" in data
        assert "total_count" in data
    
    def test_get_cosmic_cancer_genes(self, client):
        """Test getting COSMIC cancer genes."""
        response = client.get("/api/clinical/cosmic/cancer-genes")
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert data["database"] == "COSMIC"
        assert "cancer_genes" in data
        assert "total_count" in data
    
    def test_get_clinvar_variants(self, client):
        """Test getting ClinVar variant data."""
        response = client.get("/api/clinical/clinvar/variants?gene_symbol=TP53")
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert data["database"] == "ClinVar"
        assert "variants" in data
        assert "total_count" in data
    
    def test_get_oncokb_genes(self, client):
        """Test getting OncoKB gene data."""
        response = client.get("/api/clinical/oncokb/genes")
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert data["database"] == "OncoKB"
        assert "genes" in data
        assert "total_count" in data
    
    def test_get_oncokb_drugs(self, client):
        """Test getting OncoKB drug data."""
        response = client.get("/api/clinical/oncokb/drugs")
        assert response.status_code == 200
        data = response.json()
        assert "database" in data
        assert data["database"] == "OncoKB"
        assert "drugs" in data
        assert "total_count" in data
    
    def test_annotate_biomarkers(self, client):
        """Test biomarker annotation."""
        biomarkers = ["TP53", "BRCA1", "KRAS"]
        databases = ["COSMIC", "ClinVar", "OncoKB"]
        
        response = client.post(
            "/api/clinical/annotate-biomarkers",
            json={
                "biomarkers": biomarkers,
                "databases": databases
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "annotation_summary" in data
        assert "annotated_biomarkers" in data
        assert len(data["annotated_biomarkers"]) == len(biomarkers)

class TestAnalysisAPI:
    """Test analysis API endpoints."""
    
    def test_get_available_statistical_methods(self, client):
        """Test getting available statistical methods."""
        response = client.get("/api/analysis/methods/statistical")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_get_available_ml_methods(self, client):
        """Test getting available ML methods."""
        response = client.get("/api/analysis/methods/ml")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_get_available_pathway_methods(self, client):
        """Test getting available pathway methods."""
        response = client.get("/api/analysis/methods/pathway")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_get_available_databases(self, client):
        """Test getting available databases."""
        response = client.get("/api/analysis/databases")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "pathway_databases" in data
        assert "clinical_databases" in data

class TestReportGeneration:
    """Test report generation functionality."""
    
    def test_generate_report(self, client, setup_database, sample_expression_data, sample_labels_data):
        """Test generating a report."""
        # First start a pipeline
        run_id = self.test_start_pipeline(client, setup_database, sample_expression_data, sample_labels_data)
        
        # Try to generate a report (may fail if run not completed)
        response = client.post(
            f"/api/biomarkers/runs/{run_id}/report",
            json={
                "report_format": "html",
                "report_title": "Test Report"
            }
        )
        
        # Should either succeed or return appropriate error
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            data = response.json()
            assert "run_id" in data
            assert "report_path" in data
            assert "report_format" in data

class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_invalid_run_id(self, client):
        """Test handling of invalid run ID."""
        response = client.get("/api/biomarkers/runs/invalid-id/status")
        assert response.status_code == 404
    
    def test_missing_files(self, client):
        """Test handling of missing files."""
        response = client.post(
            "/api/biomarkers/run",
            files={},
            data={
                "run_name": "Test",
                "config": "{}"
            }
        )
        assert response.status_code == 422  # Validation error
    
    def test_invalid_config(self, client, sample_expression_data, sample_labels_data):
        """Test handling of invalid configuration."""
        with open(sample_expression_data, 'rb') as expr_file, \
             open(sample_labels_data, 'rb') as labels_file:
            
            response = client.post(
                "/api/biomarkers/run",
                files={
                    "expression_file": ("expression.csv", expr_file, "text/csv"),
                    "labels_file": ("labels.csv", labels_file, "text/csv")
                },
                data={
                    "run_name": "Test Analysis",
                    "config": "invalid json"
                }
            )
        
        # Should still succeed but with empty config
        assert response.status_code == 200

class TestPerformance:
    """Test performance and scalability."""
    
    def test_concurrent_requests(self, client, setup_database, sample_expression_data, sample_labels_data):
        """Test handling of concurrent requests."""
        import concurrent.futures
        
        def make_request():
            with open(sample_expression_data, 'rb') as expr_file, \
                 open(sample_labels_data, 'rb') as labels_file:
                
                config = {"normalization_method": "log2"}
                
                response = client.post(
                    "/api/biomarkers/run",
                    files={
                        "expression_file": ("expression.csv", expr_file, "text/csv"),
                        "labels_file": ("labels.csv", labels_file, "text/csv")
                    },
                    data={
                        "run_name": f"Concurrent Test {id(expr_file)}",
                        "config": json.dumps(config)
                    }
                )
                return response.status_code
        
        # Make 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All requests should succeed
        assert all(status == 200 for status in results)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
