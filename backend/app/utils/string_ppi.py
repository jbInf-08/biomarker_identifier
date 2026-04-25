"""
Protein–protein interaction edges from STRING (public REST API).

Uses the ``/api/json/network`` endpoint for batch queries.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)

STRING_NETWORK = "https://string-db.org/api/json/network"

# STRING ``required_score`` 700 => combined score >= 0.7 (high-confidence paper default)
STRING_HIGH_CONFIDENCE_THRESHOLD: float = 0.7


def fetch_string_network_edges(
    gene_symbols: List[str],
    *,
    species: int = 9606,
    confidence_threshold: float = STRING_HIGH_CONFIDENCE_THRESHOLD,
    limit_genes: int = 400,
) -> List[Dict[str, Any]]:
    """
    Return PPI edges among the given genes (STRING combined scores, 0–1).

    ``confidence_threshold`` maps to STRING ``required_score`` (0–1000).
    """
    genes = [g.strip() for g in gene_symbols if g and str(g).strip()][:limit_genes]
    if len(genes) < 1:
        return []
    req_score = max(0, min(1000, int(confidence_threshold * 1000)))
    try:
        r = requests.get(
            STRING_NETWORK,
            params={
                "identifiers": "%0d".join(genes),
                "species": species,
                "required_score": req_score,
            },
            timeout=45,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        logger.warning("STRING network API failed: %s", e)
        return []

    edges: List[Dict[str, Any]] = []
    for row in data if isinstance(data, list) else []:
        if not isinstance(row, dict):
            continue
        a = row.get("preferredName_A") or row.get("stringId_A")
        b = row.get("preferredName_B") or row.get("stringId_B")
        score = float(row.get("score", 0))
        if a and b:
            edges.append(
                {
                    "source": str(a),
                    "target": str(b),
                    "score": score,
                    "string_id_a": row.get("stringId_A"),
                    "string_id_b": row.get("stringId_B"),
                }
            )
    return edges


def to_cytoscape_elements(
    seed_genes: List[str], edges: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Cytoscape.js-style elements for simple graph rendering."""
    nodes_set = {g.strip() for g in seed_genes if g and str(g).strip()}
    for e in edges:
        nodes_set.add(str(e.get("source", "")))
        nodes_set.add(str(e.get("target", "")))
    nodes_set.discard("")
    nodes = [{"data": {"id": g, "label": g}} for g in sorted(nodes_set)]
    seen = set()
    el_edges = []
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if not s or not t:
            continue
        key = (s, t) if s < t else (t, s)
        if key in seen:
            continue
        seen.add(key)
        el_edges.append(
            {
                "data": {
                    "id": f"{s}__{t}",
                    "source": s,
                    "target": t,
                    "weight": float(e.get("score", 0)),
                }
            }
        )
    return {"elements": {"nodes": nodes, "edges": el_edges}}
