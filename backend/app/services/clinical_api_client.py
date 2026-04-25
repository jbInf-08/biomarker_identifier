"""
Real API client for COSMIC, ClinVar, and OncoKB.
Returns only authentic data from public APIs. Never returns mock/fake data.
When APIs are unavailable, returns empty results with clear status.
"""
import urllib.parse
from typing import Any, Dict, List, Optional

import requests

from app.core.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

# Public API endpoints (no authentication required for basic usage)
COSMIC_API_BASE = "https://clinicaltables.nlm.nih.gov/api/cosmic/v4/search"
ONCOKB_API_BASE = "https://public.api.oncokb.org/api/v1"
NCBI_EFETCH_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


def fetch_cosmic_mutations(
    gene_symbol: Optional[str] = None,
    cancer_type: Optional[str] = None,
    mutation_type: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Fetch COSMIC mutation data from NIH Clinical Tables API.
    Returns real data only. Empty when API unavailable.
    """
    try:
        terms = gene_symbol or ""
        params = {
            "terms": terms,
            "maxList": min(limit, 500),
            "df": "MutationID,GeneName,MutationCDS,MutationAA,PrimaryHistology,PrimarySite,MutationDescription",
        }
        resp = requests.get(COSMIC_API_BASE, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, list) or len(data) < 4:
            return {
                "database": "COSMIC",
                "data_source": "api",
                "query_parameters": {
                    "gene_symbol": gene_symbol,
                    "cancer_type": cancer_type,
                    "mutation_type": mutation_type,
                },
                "total_count": 0,
                "mutations": [],
            }

        total, codes, extra, display_arr = data[0], data[1], data[2], data[3]
        mutations = []
        for i, code in enumerate(codes):
            row = display_arr[i] if i < len(display_arr) else []
            mutations.append({
                "gene_symbol": row[1] if len(row) > 1 else "",
                "mutation_id": str(code),
                "mutation_type": row[6] if len(row) > 6 else (mutation_type or "Unknown"),
                "cancer_type": row[4] if len(row) > 4 else (cancer_type or ""),
                "cosmic_id": str(code),
                "mutation_cds": row[2] if len(row) > 2 else "",
                "mutation_aa": row[3] if len(row) > 3 else "",
                "primary_site": row[5] if len(row) > 5 else "",
            })
            if len(mutations) >= limit:
                break

        return {
            "database": "COSMIC",
            "data_source": "api",
            "query_parameters": {
                "gene_symbol": gene_symbol,
                "cancer_type": cancer_type,
                "mutation_type": mutation_type,
            },
            "total_count": min(total, limit) if isinstance(total, int) else len(mutations),
            "mutations": mutations,
        }
    except Exception as e:
        logger.warning(f"COSMIC API unavailable: {e}")
        return {
            "database": "COSMIC",
            "data_source": "unavailable",
            "query_parameters": {
                "gene_symbol": gene_symbol,
                "cancer_type": cancer_type,
                "mutation_type": mutation_type,
            },
            "total_count": 0,
            "mutations": [],
            "error": str(e),
        }


def fetch_oncokb_cancer_genes(
    cancer_type: Optional[str] = None,
    tier: Optional[int] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Fetch OncoKB cancer gene list from public API.
    Returns real data only.
    """
    try:
        url = f"{ONCOKB_API_BASE}/utils/cancerGeneList"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        genes = resp.json()

        if not isinstance(genes, list):
            genes = []

        result = []
        for g in genes[:limit]:
            if not isinstance(g, dict):
                continue
            gene_tier = g.get("tier") or g.get("geneTier")
            if tier and gene_tier != tier:
                continue
            ct = g.get("cancerTypes") or g.get("cancerTypesList") or []
            if cancer_type and cancer_type not in str(ct):
                continue
            result.append({
                "gene_symbol": g.get("hugoSymbol") or g.get("gene") or "",
                "tier": gene_tier,
                "cancer_types": ct if isinstance(ct, list) else [ct],
                "oncogenic": g.get("oncogenic", ""),
            })

        return {
            "database": "OncoKB",
            "data_source": "api",
            "query_parameters": {"cancer_type": cancer_type, "tier": tier},
            "total_count": len(result),
            "cancer_genes": result,
        }
    except Exception as e:
        logger.warning(f"OncoKB API unavailable: {e}")
        return {
            "database": "OncoKB",
            "data_source": "unavailable",
            "query_parameters": {"cancer_type": cancer_type, "tier": tier},
            "total_count": 0,
            "cancer_genes": [],
            "error": str(e),
        }


def fetch_clinvar_variants(
    gene_symbol: Optional[str] = None,
    clinical_significance: Optional[str] = None,
    variant_type: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Fetch ClinVar variants via NCBI E-utilities.
    Returns real data only. Empty when API unavailable.
    """
    try:
        query_parts = []
        if gene_symbol:
            query_parts.append(f"{gene_symbol}[gene]")
        if clinical_significance:
            query_parts.append(f"{clinical_significance}[clinical_significance]")
        query = " AND ".join(query_parts) if query_parts else "TP53[gene]"

        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "clinvar",
            "term": query,
            "retmax": min(limit, 100),
            "retmode": "json",
        }
        sr = requests.get(search_url, params=search_params, timeout=15)
        sr.raise_for_status()
        search_data = sr.json()
        id_list = search_data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return {
                "database": "ClinVar",
                "data_source": "api",
                "query_parameters": {
                    "gene_symbol": gene_symbol,
                    "clinical_significance": clinical_significance,
                    "variant_type": variant_type,
                },
                "total_count": 0,
                "variants": [],
            }

        summary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
        summary_params = {
            "db": "clinvar",
            "id": ",".join(id_list),
            "retmode": "json",
        }
        fr = requests.get(summary_url, params=summary_params, timeout=15)
        fr.raise_for_status()
        fetch_data = fr.json()

        result = fetch_data.get("result", {})
        variants = []
        for vid in id_list:
            vdata = result.get(vid, {})
            if isinstance(vdata, dict) and vdata.get("title"):
                variants.append({
                    "variant_id": vid,
                    "gene_symbol": gene_symbol or vdata.get("gene_symbol", "") or "",
                    "clinical_significance": vdata.get("clinical_significance_description", "") or vdata.get("title", ""),
                    "variant_type": variant_type or "Unknown",
                    "title": vdata.get("title", ""),
                })
            if len(variants) >= limit:
                break

        return {
            "database": "ClinVar",
            "data_source": "api",
            "query_parameters": {
                "gene_symbol": gene_symbol,
                "clinical_significance": clinical_significance,
                "variant_type": variant_type,
            },
            "total_count": len(variants),
            "variants": variants,
        }
    except Exception as e:
        logger.warning(f"ClinVar API unavailable: {e}")
        return {
            "database": "ClinVar",
            "data_source": "unavailable",
            "query_parameters": {
                "gene_symbol": gene_symbol,
                "clinical_significance": clinical_significance,
                "variant_type": variant_type,
            },
            "total_count": 0,
            "variants": [],
            "error": str(e),
        }


def fetch_oncokb_genes(
    cancer_type: Optional[str] = None,
    oncogenic: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """Fetch OncoKB curated genes. Uses cancer gene list filtered by params."""
    result = fetch_oncokb_cancer_genes(
        cancer_type=cancer_type, tier=None, limit=limit
    )
    result["genes"] = result.get("cancer_genes", [])
    return result


def fetch_oncokb_drugs(
    gene_symbol: Optional[str] = None,
    cancer_type: Optional[str] = None,
    evidence_level: Optional[str] = None,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Fetch OncoKB therapeutic agents. Uses public API.
    Returns real data only. Empty when API unavailable.
    """
    try:
        url = f"{ONCOKB_API_BASE}/therapeutics"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, list):
            data = []

        result = []
        for d in data[:limit]:
            if not isinstance(d, dict):
                continue
            genes = d.get("genes") or d.get("geneSymbols") or []
            if gene_symbol and gene_symbol not in str(genes):
                continue
            result.append({
                "drug_name": d.get("name") or d.get("drugName", ""),
                "drug_type": d.get("drugType", ""),
                "target_genes": genes if isinstance(genes, list) else [genes],
                "cancer_types": d.get("cancerTypes", []),
                "evidence_level": d.get("level", ""),
                "fda_approved": d.get("fdaApproved", False),
            })
            if len(result) >= limit:
                break

        return {
            "database": "OncoKB",
            "data_source": "api",
            "query_parameters": {
                "gene_symbol": gene_symbol,
                "cancer_type": cancer_type,
                "evidence_level": evidence_level,
            },
            "total_count": len(result),
            "drugs": result,
        }
    except Exception as e:
        logger.warning(f"OncoKB drugs API unavailable: {e}")
        return {
            "database": "OncoKB",
            "data_source": "unavailable",
            "query_parameters": {
                "gene_symbol": gene_symbol,
                "cancer_type": cancer_type,
                "evidence_level": evidence_level,
            },
            "total_count": 0,
            "drugs": [],
            "error": str(e),
        }
