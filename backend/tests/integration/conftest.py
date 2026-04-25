"""
Integration-test defaults: mock external clinical APIs so CI/local runs do not
depend on COSMIC / ClinVar / OncoKB / NCBI availability or rate limits.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pytest


def _empty_cosmic(
    gene_symbol: Optional[str] = None,
    cancer_type: Optional[str] = None,
    mutation_type: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    return {
        "database": "COSMIC",
        "data_source": "mock",
        "query_parameters": {
            "gene_symbol": gene_symbol,
            "cancer_type": cancer_type,
            "mutation_type": mutation_type,
        },
        "total_count": 0,
        "mutations": [],
    }


def _empty_clinvar(
    gene_symbol: Optional[str] = None,
    clinical_significance: Optional[str] = None,
    variant_type: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    return {
        "database": "ClinVar",
        "data_source": "mock",
        "query_parameters": {
            "gene_symbol": gene_symbol,
            "clinical_significance": clinical_significance,
            "variant_type": variant_type,
        },
        "total_count": 0,
        "variants": [],
    }


def _empty_oncokb_cancer_genes(
    cancer_type: Optional[str] = None,
    tier: Optional[int] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    return {
        "database": "OncoKB",
        "data_source": "mock",
        "query_parameters": {"cancer_type": cancer_type, "tier": tier},
        "total_count": 0,
        "cancer_genes": [],
    }


def _empty_oncokb_drugs(
    gene_symbol: Optional[str] = None,
    cancer_type: Optional[str] = None,
    evidence_level: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    return {
        "database": "OncoKB",
        "data_source": "mock",
        "query_parameters": {
            "gene_symbol": gene_symbol,
            "cancer_type": cancer_type,
            "evidence_level": evidence_level,
        },
        "total_count": 0,
        "drugs": [],
    }


def _patched_oncokb_genes(
    cancer_type: Optional[str] = None,
    oncogenic: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    base = _empty_oncokb_cancer_genes(cancer_type=cancer_type, limit=limit)
    base["genes"] = base.get("cancer_genes", [])
    return base


@pytest.fixture(autouse=True)
def mock_external_clinical_apis(monkeypatch: pytest.MonkeyPatch):
    """Patch clinical_api_client fetchers for stable integration tests."""
    import app.services.clinical_api_client as cap

    monkeypatch.setattr(cap, "fetch_cosmic_mutations", _empty_cosmic)
    monkeypatch.setattr(cap, "fetch_clinvar_variants", _empty_clinvar)
    monkeypatch.setattr(cap, "fetch_oncokb_cancer_genes", _empty_oncokb_cancer_genes)
    monkeypatch.setattr(cap, "fetch_oncokb_drugs", _empty_oncokb_drugs)
    monkeypatch.setattr(cap, "fetch_oncokb_genes", _patched_oncokb_genes)
