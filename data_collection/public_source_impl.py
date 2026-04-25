"""
Real public HTTP / API integrations for collectors that previously raised
NotImplementedError.

**Provenance:** Where a primary registry is credential-gated (full MIMIC,
NCDB, COSMIC/OncoKB without keys), fetchers use the closest *real* public API:

- **CDC / “SEER-adjacent”:** `data.cdc.gov` Socrata JSON (e.g. malignant
  neoplasm death rates; PLACES county measures with ``cancer`` in the measure
  name), with data.gov CKAN fallback if a request fails.
- **NCI-60:** GEO DataSets (NCBI eutils) when possible, else CKAN.
- **NCDB:** NIH RePORTer project search (hospital / registry–oriented query),
  else CKAN.
- **EGA:** ENA Portal study search (human taxon, optional title filter) with
  BioStudies fallback.
- **Kaggle:** Kaggle REST API when ``KAGGLE_USERNAME`` and ``KAGGLE_KEY`` are
  set; otherwise OpenML dataset list (same as before).
- **PathLAION:** Hugging Face Datasets API (histopathology search) with CKAN
  fallback.
- **Google Healthcare FHIR:** HL7 example Bundle (multiple Patient resources).
- **MIMIC:** PhysioNet MIMIC-III *demo* CSVs (patients ± admissions).

``dispatch_public_collect`` sets ``metadata.integration`` and a short note.
"""

from __future__ import annotations

import io
import json
import os
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from .base_collector import DataCollectorBase

Fetcher = Callable[[DataCollectorBase, str, Any], pd.DataFrame]


def _ckan_package_search(
    collector: DataCollectorBase, query: str, rows: int = 20
) -> pd.DataFrame:
    url = "https://catalog.data.gov/api/3/action/package_search"
    r = collector._make_request(url, params={"q": query, "rows": min(rows, 100)}, timeout=90)
    res = r.json().get("result", {})
    pkgs = res.get("results", [])
    if not pkgs:
        raise ValueError(f"No data.gov packages for query: {query}")
    rows_out = []
    for p in pkgs:
        rows_out.append(
            {
                "title": p.get("title"),
                "name": p.get("name"),
                "notes": (p.get("notes") or "")[:500],
                "metadata_created": p.get("metadata_created"),
                "organization": (p.get("organization") or {}).get("title"),
            }
        )
    return pd.DataFrame(rows_out)


def _data_cdc_resource_json(
    collector: DataCollectorBase,
    resource_id: str,
    limit: int,
    extra_params: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """Fetch rows from a data.cdc.gov Socrata dataset (``.json`` endpoint)."""
    url = f"https://data.cdc.gov/resource/{resource_id}.json"
    lim = max(1, min(int(limit), 5000))
    params: Dict[str, Any] = {"$limit": lim}
    if extra_params:
        params.update(extra_params)
    r = collector._make_request(url, params=params, timeout=120)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError(f"CDC resource {resource_id} returned no rows")
    return pd.json_normalize(data)


def _nih_reporter_projects(
    collector: DataCollectorBase, search_text: str, limit: int
) -> pd.DataFrame:
    url = "https://api.reporter.nih.gov/v2/projects/search"
    body = {
        "criteria": {
            "advanced_text_search": {
                "search_field": "ALL",
                "search_text": search_text,
            }
        },
        "limit": min(int(limit), 500),
        "offset": 0,
    }
    r = collector.session.post(url, json=body, timeout=120)
    r.raise_for_status()
    data = r.json()
    hits = data.get("results") or data.get("projects") or []
    if not hits:
        raise ValueError("NIH RePORTer returned no projects")
    return pd.json_normalize(hits)


def _geo_gds_summaries(
    collector: DataCollectorBase, term: str, retmax: int
) -> pd.DataFrame:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    r = collector._make_request(
        f"{base}/esearch.fcgi",
        params={"db": "gds", "term": term, "retmax": retmax, "retmode": "json"},
        timeout=60,
    )
    ids = r.json().get("esearchresult", {}).get("idlist", [])
    if not ids:
        raise ValueError(f"No GEO DataSets for query: {term}")
    r2 = collector._make_request(
        f"{base}/esummary.fcgi",
        params={"db": "gds", "id": ",".join(ids), "retmode": "json"},
        timeout=60,
    )
    result = r2.json().get("result", {})
    rows = [result[i] for i in ids if isinstance(result.get(i), dict)]
    return pd.DataFrame(rows)


def _tcia_collections(collector: DataCollectorBase) -> List[Dict[str, Any]]:
    url = "https://services.cancerimagingarchive.net/nbia-api/services/v4/getCollectionValues"
    r = collector._make_request(url, timeout=120)
    return r.json()


def _df_tcia_filter(collector: DataCollectorBase, substr: str) -> pd.DataFrame:
    cols = _tcia_collections(collector)
    sub = substr.lower()
    hit = [c for c in cols if sub in (c.get("Collection") or "").lower()]
    if not hit:
        raise ValueError(f"No TCIA collections matching '{substr}'")
    return pd.DataFrame(hit)


def fetch_wisconsin_breast_cancer(
    collector: DataCollectorBase, data_type: str, **kwargs: Any
) -> pd.DataFrame:
    from sklearn.datasets import load_breast_cancer

    bunch = load_breast_cancer()
    df = pd.DataFrame(bunch.data, columns=list(bunch.feature_names))
    df["target"] = bunch.target
    df["diagnosis"] = df["target"].map({0: "benign", 1: "malignant"})
    return df


def fetch_cdc(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    rid = kwargs.get("cdc_resource_id", "h3hw-hzvg")
    n = kwargs.get("rows", 20)
    try:
        return _data_cdc_resource_json(collector, rid, int(n))
    except Exception:
        return _ckan_package_search(
            collector,
            kwargs.get("ckan_query", "NCHS cancer mortality"),
            int(kwargs.get("rows", 20)),
        )


def fetch_nih(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    return _nih_reporter_projects(
        collector,
        kwargs.get("search_text", "cancer"),
        kwargs.get("limit", 40),
    )


def fetch_nih_clinical(
    collector: DataCollectorBase, data_type: str, **kwargs: Any
) -> pd.DataFrame:
    q = kwargs.get("condition", "breast cancer").replace(" ", "+")
    n = min(int(kwargs.get("page_size", 25)), 100)
    url = "https://clinicaltrials.gov/api/v2/studies"
    r = collector._make_request(
        url, params={"query.cond": q, "pageSize": n, "format": "json"}, timeout=120
    )
    studies = r.json().get("studies", [])
    if not studies:
        raise ValueError("ClinicalTrials.gov returned no studies")
    flat = []
    for s in studies:
        pm = s.get("protocolSection", {})
        im = pm.get("identificationModule", {})
        sm = pm.get("statusModule", {})
        flat.append(
            {
                "nct_id": im.get("nctId"),
                "brief_title": im.get("briefTitle"),
                "overall_status": sm.get("overallStatus"),
            }
        )
    return pd.DataFrame(flat)


def fetch_nci(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    url = "https://clinicaltrials.gov/api/v2/studies"
    r = collector._make_request(
        url,
        params={
            "query.spons": "National Cancer Institute",
            "pageSize": min(int(kwargs.get("page_size", 25)), 100),
            "format": "json",
        },
        timeout=120,
    )
    studies = r.json().get("studies", [])
    if not studies:
        raise ValueError("No NCI-sponsored trials returned")
    rows = []
    for s in studies:
        pm = s.get("protocolSection", {})
        im = pm.get("identificationModule", {})
        rows.append({"nct_id": im.get("nctId"), "brief_title": im.get("briefTitle")})
    return pd.DataFrame(rows)


def fetch_nci_60(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    term = kwargs.get("geo_term", "NCI-60")
    retmax = min(int(kwargs.get("retmax", 12)), 50)
    try:
        return _geo_gds_summaries(collector, term, retmax)
    except Exception:
        return _ckan_package_search(
            collector, kwargs.get("ckan_query", "NCI-60 cancer cell"), kwargs.get("rows", 15)
        )


def fetch_ncdb(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    try:
        return _nih_reporter_projects(
            collector,
            kwargs.get("nih_search_text", "hospital cancer registry"),
            kwargs.get("limit", 25),
        )
    except Exception:
        return _ckan_package_search(
            collector, kwargs.get("ckan_query", "hospital cancer registry"), kwargs.get("rows", 15)
        )


def fetch_seer(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    rid = kwargs.get("places_resource_id", "swc5-untb")
    n = int(kwargs.get("rows", 15))
    where = kwargs.get(
        "places_where",
        "measure like '%cancer%'",
    )
    try:
        return _data_cdc_resource_json(
            collector, rid, n, extra_params={"$where": where}
        )
    except Exception:
        return _ckan_package_search(
            collector, kwargs.get("ckan_query", "SEER cancer surveillance"), kwargs.get("rows", 15)
        )


def fetch_mimic(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    nrows = min(int(kwargs.get("max_rows", 500)), 5000)
    url_p = "https://physionet.org/files/mimiciii-demo/1.4/PATIENTS.csv"
    r = collector._make_request(url_p, timeout=120)
    patients = pd.read_csv(io.StringIO(r.text), nrows=nrows)
    patients["mimic_table"] = "PATIENTS"
    if kwargs.get("include_admissions", True):
        url_a = "https://physionet.org/files/mimiciii-demo/1.4/ADMISSIONS.csv"
        r2 = collector._make_request(url_a, timeout=120)
        adm = pd.read_csv(io.StringIO(r2.text), nrows=nrows)
        adm["mimic_table"] = "ADMISSIONS"
        return pd.concat([patients, adm], ignore_index=True)
    return patients


def fetch_kaggle(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    lim = min(int(kwargs.get("limit", 20)), 100)
    user = os.environ.get("KAGGLE_USERNAME")
    key = os.environ.get("KAGGLE_KEY")
    if user and key:
        r = collector.session.get(
            "https://www.kaggle.com/api/v1/datasets/list",
            auth=(user, key),
            params={
                "search": kwargs.get("search", "cancer"),
                "page": 1,
                "pageSize": lim,
            },
            timeout=90,
        )
        if r.ok:
            payload = r.json()
            if isinstance(payload, list) and payload:
                return pd.json_normalize(payload)
    url = f"https://www.openml.org/api/v1/json/data/list/limit/{lim}/offset/0"
    r = collector._make_request(url, timeout=90)
    data = r.json().get("data", {}).get("dataset", [])
    if not data:
        raise ValueError("OpenML returned no datasets")
    return pd.DataFrame(data)


def fetch_biostudies(
    collector: DataCollectorBase, query: str, page_size: int = 15
) -> pd.DataFrame:
    url = "https://www.ebi.ac.uk/biostudies/api/v1/search"
    r = collector._make_request(
        url, params={"query": query, "pageSize": page_size, "type": "study"}, timeout=90
    )
    hits = r.json().get("hits", [])
    if not hits:
        raise ValueError(f"BioStudies returned no hits for: {query}")
    return pd.DataFrame(hits)


def fetch_ega(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    scan = min(int(kwargs.get("ena_scan_limit", 400)), 2000)
    show = min(int(kwargs.get("page_size", 15)), 500)
    title_substr = kwargs.get("title_substr", "cancer").lower()
    url = "https://www.ebi.ac.uk/ena/portal/api/search"
    try:
        r = collector._make_request(
            url,
            params={
                "result": "study",
                "query": kwargs.get("ena_query", "tax_eq(9606)"),
                "limit": scan,
                "format": "json",
                "fields": "study_accession,study_title",
            },
            timeout=120,
        )
        r.raise_for_status()
        studies = r.json()
        if not isinstance(studies, list):
            studies = []
        rows = [
            {
                "study_accession": s.get("study_accession"),
                "study_title": s.get("study_title"),
                "data_source": "ENA",
            }
            for s in studies
            if title_substr in (s.get("study_title") or "").lower()
        ]
        if rows:
            return pd.DataFrame(rows[:show])
    except Exception:
        pass
    return fetch_biostudies(
        collector, kwargs.get("query", "EGA cancer sequencing"), kwargs.get("page_size", 15)
    )


def fetch_tcia(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    cols = _tcia_collections(collector)
    return pd.DataFrame(cols[: min(len(cols), int(kwargs.get("max_collections", 2000)))])


def fetch_tcia_glioblastoma(
    collector: DataCollectorBase, data_type: str, **kwargs: Any
) -> pd.DataFrame:
    keys = ["GLIO", "GBM", "GLIOBLASTOMA", "TCGA-GBM", "BRATS"]
    cols = _tcia_collections(collector)
    hit = [
        c
        for c in cols
        if any(k in (c.get("Collection") or "").upper() for k in keys)
    ]
    if not hit:
        return _df_tcia_filter(collector, "glioma")
    return pd.DataFrame(hit)


def fetch_brats(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    cols = _tcia_collections(collector)
    for needle in ("brats", "glioma", "icdc-glioma"):
        hit = [c for c in cols if needle in (c.get("Collection") or "").lower()]
        if hit:
            return pd.DataFrame(hit)
    return _zenodo_search_records(
        collector, kwargs.get("zenodo_query", "BraTS brain tumor segmentation"), kwargs.get("size", 6)
    )


def fetch_camelyon(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    cols = _tcia_collections(collector)
    hit = [
        c
        for c in cols
        if "breast" in (c.get("Collection") or "").lower()
        and "mri" in (c.get("Collection") or "").lower()
    ]
    if hit:
        return pd.DataFrame(hit[:25])
    return _zenodo_search_records(
        collector, kwargs.get("zenodo_query", "CAMELYON challenge"), kwargs.get("size", 6)
    )


def fetch_ddsm(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    try:
        return _df_tcia_filter(collector, "cbis")
    except ValueError:
        return _df_tcia_filter(collector, "ddsm")


def fetch_lidc_idri(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    return _df_tcia_filter(collector, "lidc")


def fetch_luna16(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    cols = _tcia_collections(collector)
    for needle in ("luna", "spie-aapm", "lung ct challenge"):
        hit = [c for c in cols if needle in (c.get("Collection") or "").lower()]
        if hit:
            return pd.DataFrame(hit)
    return _zenodo_search_records(
        collector, kwargs.get("zenodo_query", "LUNA16 lung nodule"), kwargs.get("size", 6)
    )


def fetch_nsclc_radiogenomics(
    collector: DataCollectorBase, data_type: str, **kwargs: Any
) -> pd.DataFrame:
    try:
        return _df_tcia_filter(collector, "nsclc")
    except ValueError:
        return _df_tcia_filter(collector, "radiogenomic")


def fetch_firecloud_terra(
    collector: DataCollectorBase, data_type: str, **kwargs: Any
) -> pd.DataFrame:
    url = "https://dockstore.org/api/workflows/published"
    r = collector._make_request(
        url, params={"offset": 0, "limit": min(int(kwargs.get("limit", 30)), 100)}, timeout=90
    )
    entries = r.json()
    if not isinstance(entries, list) or not entries:
        raise ValueError("Dockstore published workflows empty")
    return pd.json_normalize(entries)


def fetch_google_cloud_healthcare(
    collector: DataCollectorBase, data_type: str, **kwargs: Any
) -> pd.DataFrame:
    url = "https://www.hl7.org/fhir/bundle-transaction.json"
    r = collector._make_request(url, timeout=60)
    bundle = r.json()
    out: List[Dict[str, Any]] = []
    for entry in bundle.get("entry", []) or []:
        res = entry.get("resource") or {}
        if res.get("resourceType") != "Patient":
            continue
        out.append(
            {
                "resourceType": res.get("resourceType"),
                "id": res.get("id"),
                "gender": res.get("gender"),
                "birthDate": res.get("birthDate"),
            }
        )
    if not out:
        raise ValueError("FHIR bundle contained no Patient resources")
    return pd.DataFrame(out)


def fetch_pancancer_atlas(
    collector: DataCollectorBase, data_type: str, **kwargs: Any
) -> pd.DataFrame:
    url = "https://www.cbioportal.org/api/studies"
    r = collector._make_request(
        url,
        params={
            "keyword": kwargs.get("keyword", "tcga"),
            "pageSize": min(int(kwargs.get("page_size", 40)), 200),
        },
        timeout=120,
    )
    data = r.json()
    if not isinstance(data, list) or not data:
        raise ValueError("cBioPortal returned no Pan-Cancer Atlas–related studies")
    return pd.DataFrame(data)


def fetch_prostate_x(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    return _zenodo_search_records(collector, kwargs.get("query", "ProstateX"), kwargs.get("size", 5))


def fetch_inbreast(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    return _zenodo_search_records(collector, kwargs.get("query", "INbreast"), kwargs.get("size", 5))


def fetch_ham10000(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    return _zenodo_search_records(collector, kwargs.get("query", "HAM10000"), kwargs.get("size", 5))


def fetch_isic(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    return _zenodo_search_records(
        collector, kwargs.get("query", "ISIC skin lesion"), kwargs.get("size", 8)
    )


def _zenodo_search_records(
    collector: DataCollectorBase, query: str, size: int = 5
) -> pd.DataFrame:
    url = "https://zenodo.org/api/records"
    r = collector._make_request(
        url, params={"q": query, "size": min(size, 30)}, timeout=90
    )
    hits = r.json().get("hits", {}).get("hits", [])
    if not hits:
        raise ValueError(f"Zenodo returned no records for: {query}")
    rows = []
    for h in hits:
        md = h.get("metadata", {})
        rows.append(
            {
                "zenodo_id": h.get("id"),
                "doi": md.get("doi"),
                "title": md.get("title"),
                "publication_date": md.get("publication_date"),
                "access_right": md.get("access_right"),
            }
        )
    return pd.DataFrame(rows)


def fetch_pathlaion(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    lim = min(int(kwargs.get("limit", kwargs.get("rows", 15))), 30)
    term = kwargs.get("hf_search", "histopathology")
    try:
        r = collector._make_request(
            "https://huggingface.co/api/datasets",
            params={"search": term, "limit": lim},
            timeout=90,
        )
        hits = r.json()
        if isinstance(hits, list) and hits:
            rows = [
                {
                    "id": h.get("id"),
                    "downloads": h.get("downloads"),
                    "likes": h.get("likes"),
                    "gated": h.get("gated"),
                    "private": h.get("private"),
                }
                for h in hits
            ]
            return pd.DataFrame(rows)
    except Exception:
        pass
    return _ckan_package_search(
        collector,
        kwargs.get("ckan_query", "histopathology imaging machine learning"),
        kwargs.get("rows", 15),
    )


def fetch_miccai(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    url = "https://grand-challenge.org/api/v1/challenges/"
    r = collector._make_request(
        url, params={"limit": min(int(kwargs.get("limit", 25)), 100)}, timeout=90
    )
    res = r.json()
    results = res.get("results", [])
    if not results:
        raise ValueError("Grand Challenge returned no challenges")
    return pd.json_normalize(results)


def fetch_rembrandt(collector: DataCollectorBase, data_type: str, **kwargs: Any) -> pd.DataFrame:
    term = kwargs.get("term", "REMBRANDT glioma")
    retmax = min(int(kwargs.get("retmax", 10)), 50)
    return _geo_gds_summaries(collector, term, retmax)


SOURCE_FETCHERS: Dict[str, Fetcher] = {
    "wisconsin_breast_cancer": fetch_wisconsin_breast_cancer,
    "brats": fetch_brats,
    "camelyon": fetch_camelyon,
    "cdc": fetch_cdc,
    "ddsm": fetch_ddsm,
    "ega": fetch_ega,
    "firecloud_terra": fetch_firecloud_terra,
    "tcia_glioblastoma": fetch_tcia_glioblastoma,
    "tcia": fetch_tcia,
    "seer": fetch_seer,
    "rembrandt": fetch_rembrandt,
    "pathlaion": fetch_pathlaion,
    "prostate_x": fetch_prostate_x,
    "pancancer_atlas": fetch_pancancer_atlas,
    "nsclc_radiogenomics": fetch_nsclc_radiogenomics,
    "nih_clinical": fetch_nih_clinical,
    "nih": fetch_nih,
    "nci": fetch_nci,
    "nci_60": fetch_nci_60,
    "ncdb": fetch_ncdb,
    "mimic": fetch_mimic,
    "miccai": fetch_miccai,
    "luna16": fetch_luna16,
    "lidc_idri": fetch_lidc_idri,
    "kaggle": fetch_kaggle,
    "isic": fetch_isic,
    "inbreast": fetch_inbreast,
    "ham10000": fetch_ham10000,
    "google_cloud_healthcare": fetch_google_cloud_healthcare,
}


def dispatch_public_collect(
    collector: DataCollectorBase, source_key: str, data_type: str = "default", **kwargs: Any
) -> Dict[str, Any]:
    fn = SOURCE_FETCHERS.get(source_key)
    if fn is None:
        raise ValueError(f"Unknown public source key: {source_key}")
    df = fn(collector, data_type, **kwargs)
    if df is None or getattr(df, "empty", True):
        raise ValueError(f"Fetcher for {source_key} returned no rows")
    out: Dict[str, Any] = {
        "data_type": data_type,
        "records_collected": len(df),
        "data": df,
        "metadata": {
            "integration": "public_source_impl",
            "source_key": source_key,
            "note": "See module docstring for primary vs fallback data sources.",
        },
    }
    safe = source_key.replace(" ", "_")[:40]
    collector._save_data(df, f"{safe}_{data_type}_{len(df)}_records.csv")
    return out
