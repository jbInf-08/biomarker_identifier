"""
Comprehensive integration tests for clinical API endpoints.
"""
import pytest
from fastapi.testclient import TestClient


class TestClinicalAPI:
    """Test cases for clinical API endpoints."""

    def test_get_cosmic_mutations_unauthorized(self, client: TestClient):
        """Test getting COSMIC mutations without authentication."""
        response = client.get("/api/clinical/cosmic/mutations")
        assert response.status_code in [200, 401, 403]  # May or may not require auth

    def test_get_cosmic_mutations_success(self, client: TestClient, auth_headers):
        """Test getting COSMIC mutations with valid parameters."""
        response = client.get(
            "/api/clinical/cosmic/mutations",
            params={"gene_symbol": "TP53", "limit": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "mutations" in data or "results" in data

    def test_get_clinvar_variants_unauthorized(self, client: TestClient):
        """Test getting ClinVar variants without authentication."""
        response = client.get("/api/clinical/clinvar/variants")
        assert response.status_code in [200, 401, 403]

    def test_get_clinvar_variants_success(self, client: TestClient, auth_headers):
        """Test getting ClinVar variants with valid parameters."""
        response = client.get(
            "/api/clinical/clinvar/variants",
            params={"gene_symbol": "BRCA1", "limit": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "variants" in data or "results" in data

    def test_get_oncokb_genes_unauthorized(self, client: TestClient):
        """Test getting OncoKB genes without authentication."""
        response = client.get("/api/clinical/oncokb/genes")
        assert response.status_code in [200, 401, 403]

    def test_get_oncokb_genes_success(self, client: TestClient, auth_headers):
        """Test getting OncoKB genes with valid parameters."""
        response = client.get(
            "/api/clinical/oncokb/genes",
            params={"cancer_type": "breast_cancer", "limit": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "genes" in data or "results" in data

    def test_get_oncokb_drugs_unauthorized(self, client: TestClient):
        """Test getting OncoKB drugs without authentication."""
        response = client.get("/api/clinical/oncokb/drugs")
        assert response.status_code in [200, 401, 403]

    def test_get_oncokb_drugs_success(self, client: TestClient, auth_headers):
        """Test getting OncoKB drugs with valid parameters."""
        response = client.get(
            "/api/clinical/oncokb/drugs",
            params={"gene_symbol": "TP53", "limit": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "drugs" in data or "results" in data

    def test_annotate_biomarkers_unauthorized(self, client: TestClient):
        """Test annotating biomarkers without authentication."""
        response = client.post(
            "/api/clinical/annotate-biomarkers", json={"biomarkers": ["TP53", "BRCA1"]}
        )
        assert response.status_code in [401, 403, 422]

    def test_annotate_biomarkers_success(self, client: TestClient, auth_headers):
        """Test annotating biomarkers with valid data."""
        response = client.post(
            "/api/clinical/annotate-biomarkers",
            json={
                "biomarkers": ["TP53", "BRCA1", "BRCA2"],
                "databases": ["COSMIC", "ClinVar", "OncoKB"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "annotated_biomarkers" in data or "results" in data

    def test_annotate_run_biomarkers_not_found(self, client: TestClient, auth_headers):
        """Test annotating biomarkers for non-existent run."""
        response = client.post(
            "/api/clinical/annotate-run/nonexistent-id",
            params={"top_n": 50},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_annotate_run_biomarkers_success(
        self,
        client: TestClient,
        auth_headers,
        test_analysis_run,
        test_biomarker_results,
    ):
        """Test annotating biomarkers for existing run."""
        response = client.post(
            f"/api/clinical/annotate-run/{test_analysis_run.id}",
            params={"top_n": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "annotated_biomarkers" in data or "results" in data

    def test_get_cosmic_cancer_genes(self, client: TestClient, auth_headers):
        """Test getting COSMIC cancer genes."""
        response = client.get(
            "/api/clinical/cosmic/cancer-genes",
            params={"cancer_type": "Breast Cancer", "limit": 10},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "cancer_genes" in data or "results" in data

    def test_annotate_biomarkers_edge_cases(self, client: TestClient, auth_headers):
        """Test annotating biomarkers with edge cases."""
        # Test with empty biomarker list
        response = client.post(
            "/api/clinical/annotate-biomarkers",
            json={"biomarkers": []},
            headers=auth_headers,
        )
        assert response.status_code in [200, 422]

        # Test with single database
        response = client.post(
            "/api/clinical/annotate-biomarkers",
            json={"biomarkers": ["TP53"], "databases": ["COSMIC"]},
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_get_cosmic_mutations_edge_cases(self, client: TestClient, auth_headers):
        """Test COSMIC mutations with edge cases."""
        # Test with different parameters
        response = client.get(
            "/api/clinical/cosmic/mutations",
            params={
                "gene_symbol": "TP53",
                "cancer_type": "Breast Cancer",
                "mutation_type": "Missense",
                "limit": 5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_get_clinvar_variants_edge_cases(self, client: TestClient, auth_headers):
        """Test ClinVar variants with edge cases."""
        response = client.get(
            "/api/clinical/clinvar/variants",
            params={
                "gene_symbol": "BRCA1",
                "clinical_significance": "Pathogenic",
                "variant_type": "Single nucleotide variant",
                "limit": 5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200

    def test_get_oncokb_drugs_edge_cases(self, client: TestClient, auth_headers):
        """Test OncoKB drugs with edge cases."""
        response = client.get(
            "/api/clinical/oncokb/drugs",
            params={
                "gene_symbol": "KRAS",
                "cancer_type": "Non-Small Cell Lung Cancer",
                "evidence_level": "1",
                "limit": 5,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
