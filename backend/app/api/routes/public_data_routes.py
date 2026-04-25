"""
Public dataset entry points (GEO, dbGaP, FDA openFDA) with lightweight live lookups.
"""

from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@router.get("/geo/series/{accession}")
async def geo_series(accession: str) -> Dict[str, Any]:
    acc = accession.strip().upper()
    if not acc:
        raise HTTPException(status_code=400, detail="accession is required")
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search_url = f"{base}/esearch.fcgi"
    summary_url = f"{base}/esummary.fcgi"
    async with httpx.AsyncClient(timeout=20.0) as client:
        s = await client.get(
            search_url,
            params={
                "db": "gds",
                "term": f"{acc}[ACCN]",
                "retmode": "json",
                "retmax": 5,
            },
        )
        s.raise_for_status()
        sdata = s.json()
        ids = (sdata.get("esearchresult") or {}).get("idlist") or []
        summaries: list[dict] = []
        if ids:
            su = await client.get(
                summary_url,
                params={
                    "db": "gds",
                    "id": ",".join(ids[:5]),
                    "retmode": "json",
                },
            )
            su.raise_for_status()
            sudata = su.json()
            for i in ids[:5]:
                row = (sudata.get("result") or {}).get(i) or {}
                if row:
                    summaries.append(
                        {
                            "uid": i,
                            "accession": row.get("accession"),
                            "title": row.get("title"),
                            "summary": row.get("summary"),
                            "taxon": row.get("taxon"),
                            "gpl": row.get("gpl"),
                            "n_samples": row.get("n_samples"),
                        }
                    )
    return {
        "accession": acc,
        "ncbi_geo_query": f"https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc={acc}",
        "matches": summaries,
        "count": len(summaries),
        "note": "For raw SOFT/matrix retrieval and harmonization pipelines, use dedicated ingestion workers.",
    }


@router.get("/dbgap/study/{study_id}")
async def dbgap_study(study_id: str) -> Dict[str, Any]:
    sid = study_id.strip()
    if not sid:
        raise HTTPException(status_code=400, detail="study_id is required")
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    search_url = f"{base}/esearch.fcgi"
    summary_url = f"{base}/esummary.fcgi"
    async with httpx.AsyncClient(timeout=20.0) as client:
        s = await client.get(
            search_url,
            params={
                "db": "gap",
                "term": sid,
                "retmode": "json",
                "retmax": 5,
            },
        )
        s.raise_for_status()
        sdata = s.json()
        ids = (sdata.get("esearchresult") or {}).get("idlist") or []
        summaries: list[dict] = []
        if ids:
            su = await client.get(
                summary_url,
                params={
                    "db": "gap",
                    "id": ",".join(ids[:5]),
                    "retmode": "json",
                },
            )
            su.raise_for_status()
            sudata = su.json()
            for i in ids[:5]:
                row = (sudata.get("result") or {}).get(i) or {}
                if row:
                    summaries.append(
                        {
                            "uid": i,
                            "caption": row.get("caption"),
                            "title": row.get("title"),
                            "desc": row.get("desc"),
                            "extra": row.get("extra"),
                        }
                    )
    return {
        "study_id": sid,
        "dbgap_portal": f"https://www.ncbi.nlm.nih.gov/projects/gap/cgi-bin/study.cgi?study_id={sid}",
        "matches": summaries,
        "count": len(summaries),
        "note": "Controlled-access retrieval still requires NIH auth, DUC, and IRB alignment.",
    }


@router.get("/fda/openfda/search")
async def openfda_search(
    endpoint: str = Query("drug", description="openFDA group, e.g. drug, device, food"),
    search: Optional[str] = Query(None, description="openFDA search fragment"),
    limit: int = Query(10, ge=1, le=100),
) -> Dict[str, Any]:
    base = "https://api.fda.gov"
    q = (search or "").strip()
    url = f"{base}/{endpoint}/event.json"
    params: Dict[str, Any] = {"limit": limit}
    if q:
        params["search"] = q
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url, params=params)
    if r.status_code >= 400:
        raise HTTPException(
            status_code=r.status_code,
            detail=f"openFDA query failed: {r.text[:200]}",
        )
    data = r.json()
    return {
        "openfda_request": str(r.request.url),
        "meta": data.get("meta"),
        "results": data.get("results", []),
        "documentation": "https://open.fda.gov/apis/",
        "note": "Use an API key and client-side caching for higher sustained throughput.",
    }
