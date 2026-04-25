"""
Lightweight retrieval for LLM grounding from bundled biomedical snippets.
No external vector DB — keyword overlap on gene symbols and titles.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_GROUNDING_CACHE: Optional[List[Dict[str, Any]]] = None


def _snippets_path() -> Path:
    # backend/data/llm_grounding/snippets.json
    return (
        Path(__file__).resolve().parent.parent.parent / "data" / "llm_grounding" / "snippets.json"
    )


def load_snippets() -> List[Dict[str, Any]]:
    global _GROUNDING_CACHE
    if _GROUNDING_CACHE is not None:
        return _GROUNDING_CACHE
    path = _snippets_path()
    if not path.is_file():
        logger.warning("Grounding snippets not found at %s", path)
        _GROUNDING_CACHE = []
        return _GROUNDING_CACHE
    try:
        with open(path, "r", encoding="utf-8") as f:
            _GROUNDING_CACHE = json.load(f)
    except Exception as e:
        logger.warning("Failed to load grounding snippets: %s", e)
        _GROUNDING_CACHE = []
    return _GROUNDING_CACHE


def retrieve_for_genes(
    genes: List[str], limit: int = 5
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Return snippet dicts (id, title, text, genes) plus matched gene symbols used for ranking.
    """
    gset = {g.upper().strip() for g in genes if g and str(g).strip()}
    if not gset:
        return [], []

    scored: List[Tuple[int, Dict[str, Any], List[str]]] = []
    for sn in load_snippets():
        sg = {str(x).upper() for x in (sn.get("genes") or [])}
        overlap = sorted(gset & sg)
        if not overlap:
            continue
        score = len(overlap) * 10
        title = sn.get("title") or ""
        for token in gset:
            if len(token) > 2 and token in title.upper():
                score += 1
        scored.append((score, sn, overlap))

    scored.sort(key=lambda x: -x[0])
    out = []
    matched: List[str] = []
    for score, sn, overlap in scored[:limit]:
        out.append(
            {
                "id": sn.get("id"),
                "title": sn.get("title"),
                "text": sn.get("text"),
                "genes": sn.get("genes"),
                "match_score": score,
            }
        )
        matched.extend(overlap)
    # unique preserve order
    seen = set()
    uniq_matched = []
    for m in matched:
        if m not in seen:
            seen.add(m)
            uniq_matched.append(m)
    return out, uniq_matched


def retrieve_all_sources(
    genes: List[str], local_limit: int = 6
) -> Tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    """
    Bundled snippets + optional PubMed (when ENABLE_PUBMED_GROUNDING).
    Returns (merged_sources_for_prompt, matched_genes, sources_for_api).
    """
    from app.core.config import settings

    local_raw, matched = retrieve_for_genes(genes, limit=local_limit)
    merged: List[Dict[str, Any]] = []
    api_sources: List[Dict[str, Any]] = []
    for s in local_raw:
        entry = {
            "id": s.get("id"),
            "title": s.get("title"),
            "text": s.get("text"),
            "source_type": "corpus",
        }
        merged.append(entry)
        api_sources.append(
            {
                "id": s.get("id"),
                "title": s.get("title"),
                "snippet": (s.get("text") or "")[:500],
                "pmid": None,
            }
        )

    if getattr(settings, "ENABLE_PUBMED_GROUNDING", False):
        try:
            from app.services.pubmed_client import retrieve_pubmed_for_genes

            for p in retrieve_pubmed_for_genes(genes):
                merged.append(
                    {
                        "id": f"PMID:{p.get('pmid')}",
                        "title": p.get("title"),
                        "text": p.get("text"),
                        "source_type": "pubmed",
                    }
                )
                api_sources.append(
                    {
                        "id": f"PMID:{p.get('pmid')}",
                        "title": p.get("title"),
                        "snippet": (p.get("text") or "")[:500],
                        "pmid": p.get("pmid"),
                    }
                )
        except Exception as e:
            logger.warning("PubMed grounding skipped: %s", e)

    return merged, matched, api_sources
