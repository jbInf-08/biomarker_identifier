"""
Minimal NCBI E-utilities client for PubMed summaries (grounding).
Respect NCBI rate limits; set NCBI_EMAIL (and optional API key) in production.
"""

import logging
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

_LAST_CALL = 0.0
_MIN_INTERVAL = 0.34  # ~3 req/s without API key


def _throttle():
    global _LAST_CALL
    now = time.monotonic()
    elapsed = now - _LAST_CALL
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)
    _LAST_CALL = time.monotonic()


def search_pubmed(query: str, retmax: int = 5) -> List[str]:
    """Return PMIDs for a PubMed query."""
    if not getattr(settings, "ENABLE_PUBMED_GROUNDING", False):
        return []
    email = getattr(settings, "NCBI_EMAIL", None) or "user@example.com"
    tool = getattr(settings, "NCBI_TOOL", "biomarker_identifier")
    params = {
        "db": "pubmed",
        "term": query,
        "retmax": retmax,
        "retmode": "json",
        "tool": tool,
        "email": email,
    }
    api_key = getattr(settings, "NCBI_API_KEY", None)
    if api_key:
        params["api_key"] = api_key
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    try:
        _throttle()
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        return data.get("esearchresult", {}).get("idlist", []) or []
    except Exception as e:
        logger.warning("PubMed esearch failed: %s", e)
        return []


def fetch_summaries(pmids: List[str]) -> List[Dict[str, Any]]:
    """Fetch title + abstract snippet per PMID."""
    if not pmids or not getattr(settings, "ENABLE_PUBMED_GROUNDING", False):
        return []
    email = getattr(settings, "NCBI_EMAIL", None) or "user@example.com"
    tool = getattr(settings, "NCBI_TOOL", "biomarker_identifier")
    params = {
        "db": "pubmed",
        "id": ",".join(pmids[:10]),
        "retmode": "xml",
        "tool": tool,
        "email": email,
    }
    api_key = getattr(settings, "NCBI_API_KEY", None)
    if api_key:
        params["api_key"] = api_key
    url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    out: List[Dict[str, Any]] = []
    try:
        _throttle()
        r = requests.get(url, params=params, timeout=45)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        for article in root.findall(".//PubmedArticle"):
            pmid_el = article.find(".//PMID")
            title_el = article.find(".//ArticleTitle")
            abst = article.find(".//Abstract/AbstractText")
            pmid = pmid_el.text if pmid_el is not None else ""
            title = "".join(title_el.itertext()) if title_el is not None else ""
            abstract = "".join(abst.itertext()) if abst is not None else ""
            out.append(
                {
                    "pmid": pmid,
                    "title": title[:500],
                    "text": abstract[:1500],
                    "source": "pubmed",
                }
            )
    except Exception as e:
        logger.warning("PubMed efetch failed: %s", e)
    return out


def retrieve_pubmed_for_genes(genes: List[str], max_per_query: int = 3) -> List[Dict[str, Any]]:
    """Gene-oriented PubMed retrieval for grounding."""
    if not genes:
        return []
    results: List[Dict[str, Any]] = []
    seen = set()
    for g in genes[:8]:
        q = f"{g}[Title/Abstract] AND (cancer[Title/Abstract] OR neoplasm[Title/Abstract])"
        pmids = search_pubmed(q, retmax=max_per_query)
        for row in fetch_summaries(pmids):
            key = row.get("pmid")
            if key and key not in seen:
                seen.add(key)
                row["genes"] = [g]
                results.append(row)
    return results[:12]
