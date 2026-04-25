"""
GEO (Gene Expression Omnibus) Data Collector.

Collects gene expression and other genomic data from NCBI GEO.

Design notes
------------
NCBI's E-utilities ``gds`` database returns **numeric UIDs**, not GSE accessions,
and a single query may contain mixed entry types (GSE series, GDS datasets,
GPL platforms, GSM samples).  Hitting ``<series>_series_matrix.txt.gz`` with a
platform accession obviously 404s, and so does a GSE that never had a matrix
published.  This collector is therefore built around three rules:

1. **Resolve every UID to a real GSE accession** via the ``esummary`` JSON,
   and filter out non-GSE entry types.
2. **Try multiple URL variants** for each series (``…_series_matrix.txt.gz``,
   then any per-platform matrix listed in the directory, then the SOFT
   family file, then MINiML).  A series that publishes only supplemental
   files is still discoverable; we just fall back to the richest parseable
   format available.
3. **Honour NCBI_API_KEY** (and ``NCBI_EMAIL`` / ``NCBI_TOOL``) on every
   E-utilities call so high-throughput runs don't get throttled to 3 rps.

An explicit ``series_list`` may be supplied in config to bypass search
entirely and collect from a curated list of GSEs — useful for CI / demos.
"""

from __future__ import annotations

import gzip
import io
import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

import pandas as pd
import requests

from .base_collector import DataCollectorBase


GSE_ACCESSION_RE = re.compile(r"\bGSE(\d+)\b")


class GEOCollector(DataCollectorBase):
    """Data collector for Gene Expression Omnibus (GEO)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # E-utilities + GEO web endpoints
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.geo_url = "https://www.ncbi.nlm.nih.gov/geo"
        self.ftp_http = "https://ftp.ncbi.nlm.nih.gov/geo/series"

        self.data_types = {
            "expression": "Gene Expression",
            "methylation": "DNA Methylation",
            "chip_seq": "ChIP-seq",
            "atac_seq": "ATAC-seq",
            "rna_seq": "RNA-seq",
            "mirna": "miRNA Expression",
            "lncrna": "lncRNA Expression",
        }

        self.cancer_terms = [
            "cancer", "tumor", "carcinoma", "sarcoma", "leukemia", "lymphoma",
            "breast cancer", "lung cancer", "prostate cancer", "colorectal cancer",
            "ovarian cancer", "pancreatic cancer", "liver cancer", "brain cancer",
        ]

        # Optional curated allowlist — if set, we skip esearch entirely.
        # Accepts either a list of "GSE12345" strings or bare numbers.
        self.series_list: List[str] = [
            self._normalize_gse(acc)
            for acc in (self.config.get("series_list") or [])
            if self._normalize_gse(acc)
        ]

    # ------------------------------------------------------------------ auth --

    def _setup_authentication(self):
        """HTTP headers + NCBI_API_KEY pickup for E-utilities."""
        self.session.headers.update({
            "User-Agent": "Cancer-Biomarker-Identifier/1.0",
            "Accept": "application/json",
        })
        self._ncbi_api_key = os.environ.get("NCBI_API_KEY", "").strip()
        self._ncbi_email = os.environ.get("NCBI_EMAIL", "").strip()
        self._ncbi_tool = os.environ.get("NCBI_TOOL", "cancer-biomarker-identifier").strip()
        if self._ncbi_api_key:
            # With an API key, NCBI allows 10 rps; leave a small buffer.
            self.rate_limit_delay = max(0.15, min(self.rate_limit_delay, 0.35))
            self.logger.info("GEO: using NCBI_API_KEY for E-utilities throughput")
        else:
            # Without a key NCBI throttles at ~3 rps; be conservative.
            self.rate_limit_delay = max(self.rate_limit_delay, 0.5)

    def _eutils_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Attach NCBI auth fields to an E-utilities call."""
        out = dict(params)
        if self._ncbi_api_key:
            out.setdefault("api_key", self._ncbi_api_key)
        if self._ncbi_email:
            out.setdefault("email", self._ncbi_email)
        if self._ncbi_tool:
            out.setdefault("tool", self._ncbi_tool)
        return out

    # ------------------------------------------------------------- discovery --

    def get_available_datasets(self) -> List[Dict[str, Any]]:
        """Lightweight description of what we can pull, without heavy network use."""
        datasets: List[Dict[str, Any]] = []

        try:
            if self.series_list:
                for acc in self.series_list[:5]:
                    datasets.append({
                        "id": acc,
                        "name": acc,
                        "description": f"Curated GEO series {acc}",
                        "data_type": "expression",
                        "source": "GEO",
                        "accession": acc,
                    })
            else:
                hits = self._search_geo_datasets("breast cancer", max_results=5)
                datasets.extend(hits)
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error(f"Failed to get available datasets: {exc}")

        for dt_key, label in self.data_types.items():
            datasets.append({
                "id": f"GEO-{dt_key}",
                "name": f"GEO {label}",
                "description": label,
                "data_type": dt_key,
                "source": "GEO",
            })

        return datasets

    # --------------------------------------------------------------- collect --

    def collect_data(self,
                     search_term: str = "breast cancer",
                     data_type: str = "expression",
                     max_datasets: int = 5,
                     metadata_only: bool = False,
                     series_list: Optional[List[str]] = None,
                     **kwargs) -> Dict[str, Any]:
        """
        Collect real data from GEO.

        When ``series_list`` is provided (argument or config), we skip esearch
        and pull each series directly.  This is the recommended path for
        deterministic runs (CI, demos, grading).
        """
        results = {
            "search_term": search_term,
            "data_type": data_type,
            "datasets_collected": 0,
            "data": None,
            "metadata": {},
        }

        allow = [self._normalize_gse(s) for s in (series_list or self.series_list) if self._normalize_gse(s)]

        # --- metadata-only fast path ---
        if metadata_only:
            datasets = (
                [self._lookup_series(acc) for acc in allow]
                if allow
                else self._search_geo_datasets(search_term, max_results=max_datasets)
            )
            datasets = [d for d in datasets if d]
            if not datasets:
                raise ValueError(f"No GEO datasets resolved for '{search_term}'")
            meta_df = pd.DataFrame(datasets)
            fname = f"geo_metadata_{search_term.replace(' ', '_')}_{len(meta_df)}.csv"
            self._save_data(meta_df, fname)
            results["data"] = meta_df
            results["datasets_collected"] = len(meta_df)
            return results

        # --- resolve the list of series we're going to try ---
        if allow:
            datasets = [self._lookup_series(acc) for acc in allow[:max_datasets]]
            datasets = [d for d in datasets if d]
        else:
            datasets = self._search_geo_datasets(search_term, max_results=max_datasets)
            # Filter out anything that isn't a GSE series — no point trying to
            # download a platform/sample record as a series matrix.
            datasets = [d for d in datasets if d.get("accession", "").startswith("GSE")]

        if not datasets:
            raise ValueError(f"No GSE series resolved for '{search_term}'")

        all_frames: List[Tuple[str, pd.DataFrame]] = []
        for ds in datasets:
            acc = ds.get("accession", "")
            try:
                df = self._download_series(acc, data_type)
                if df is not None and not df.empty:
                    all_frames.append((acc, df))
                    self.logger.info(f"GEO {acc}: downloaded {df.shape}")
            except Exception as exc:
                self.logger.warning(f"GEO {acc}: {exc}")

        if not all_frames:
            raise ValueError(
                "Failed to download any GEO series "
                "(tried: " + ", ".join(d.get("accession", "?") for d in datasets) + "). "
                "Supply 'geo.series_list' in config for a deterministic run."
            )

        # Combine with source-accession column so we can tell runs apart.
        combined = pd.concat(
            [df.assign(_geo_accession=acc) for acc, df in all_frames],
            ignore_index=True,
            sort=False,
        )

        filename = (
            f"geo_{data_type}_{search_term.replace(' ', '_')}_{len(all_frames)}_datasets.csv"
        )
        self._save_data(combined, filename)
        results["data"] = combined
        results["datasets_collected"] = len(all_frames)
        results["records_collected"] = len(combined)
        return results

    # ---------------------------------------------------------------- search --

    def _search_geo_datasets(self, search_term: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Search GEO for series matching ``search_term``."""
        try:
            # Pre-filter to GSE series only — removes the GDS/GPL/GSM noise that
            # used to cause 404s on *_series_matrix.txt.gz.
            term = f"({search_term}) AND gse[ETYP]"
            params = self._eutils_params({
                "db": "gds",
                "term": term,
                "retmax": max_results,
                "retmode": "json",
            })
            self.logger.info(f"GEO esearch: {term}")
            resp = self._make_request(f"{self.base_url}/esearch.fcgi", params=params)
            payload = resp.json()

            result = payload.get("esearchresult") or {}
            if not result or "ERROR" in result:
                self.logger.warning(f"GEO esearch returned no usable result: {payload}")
                return []

            uids: List[str] = result.get("idlist") or []
            self.logger.info(f"GEO esearch: {len(uids)} UID(s)")
            if not uids:
                return []

            return self._summaries(uids)
        except Exception as exc:
            self.logger.error(f"GEO esearch failed: {exc}")
            return []

    def _summaries(self, uids: List[str]) -> List[Dict[str, Any]]:
        """Fetch ``esummary`` JSON for a batch of UIDs at once."""
        if not uids:
            return []
        try:
            params = self._eutils_params({
                "db": "gds",
                "id": ",".join(uids),
                "retmode": "json",
            })
            resp = self._make_request(f"{self.base_url}/esummary.fcgi", params=params)
            data = resp.json().get("result", {})
        except Exception as exc:
            self.logger.warning(f"GEO esummary batch failed: {exc}")
            return []

        out: List[Dict[str, Any]] = []
        for uid in uids:
            entry = data.get(uid) or {}
            if not entry:
                continue
            # Skip non-series entries (GDS/GPL/GSM) — they have no series_matrix.
            entry_type = (entry.get("entrytype") or "").lower()
            raw_accession = entry.get("accession") or ""

            accession = ""
            if raw_accession.startswith("GSE"):
                accession = raw_accession
            elif entry_type == "gse":
                # Sometimes the accession is the *series_id* nested under "gse"
                series_id = entry.get("gse") or entry.get("series_id") or ""
                if series_id.isdigit():
                    accession = f"GSE{series_id}"
                elif GSE_ACCESSION_RE.search(series_id or ""):
                    accession = GSE_ACCESSION_RE.search(series_id).group(0)
            # Last ditch — scan the title for a GSE mention
            if not accession:
                m = GSE_ACCESSION_RE.search(entry.get("title", "") or "")
                if m:
                    accession = m.group(0)
            if not accession:
                self.logger.debug(f"GEO UID {uid}: no GSE accession resolved (entrytype={entry_type}), skipping")
                continue

            out.append({
                "id": uid,
                "title": entry.get("title", ""),
                "summary": entry.get("summary", ""),
                "organism": entry.get("taxon", ""),
                "platform": entry.get("gpl", ""),
                "samples": entry.get("n_samples", 0),
                "data_type": self._infer_data_type(entry.get("title", "")),
                "accession": accession,
            })
        return out

    def _lookup_series(self, accession: str) -> Optional[Dict[str, Any]]:
        """Resolve a single GSE via esearch→esummary."""
        acc = self._normalize_gse(accession)
        if not acc:
            return None
        try:
            params = self._eutils_params({
                "db": "gds",
                "term": f"{acc}[ACCN] AND gse[ETYP]",
                "retmode": "json",
            })
            resp = self._make_request(f"{self.base_url}/esearch.fcgi", params=params)
            uids = (resp.json().get("esearchresult") or {}).get("idlist") or []
            if not uids:
                return {"id": acc, "accession": acc, "title": acc, "source": "GEO"}
            return (self._summaries(uids[:1]) or [None])[0]
        except Exception as exc:
            self.logger.warning(f"GEO lookup for {acc} failed: {exc}")
            return {"id": acc, "accession": acc, "title": acc, "source": "GEO"}

    # ------------------------------------------------------------ data paths --

    def _series_base_url(self, accession: str) -> str:
        """
        GEO bucket layout:

            https://ftp.ncbi.nlm.nih.gov/geo/series/GSE<first-digits>nnn/<accession>/

        The "nnn" grouping replaces the last 3 digits of the accession.  For
        GSE12345 this is GSE12nnn; for GSE999 it's GSE0nnn (zero-padded).
        """
        num = accession[3:]
        bucket = f"GSE{num[:-3] if len(num) > 3 else '0'}nnn"
        return f"{self.ftp_http}/{bucket}/{accession}"

    def _candidate_matrix_urls(self, accession: str) -> List[str]:
        """List matrix URLs to try, in order of preference."""
        base = f"{self._series_base_url(accession)}/matrix"
        return [
            f"{base}/{accession}_series_matrix.txt.gz",
        ]

    def _list_directory(self, url: str) -> List[str]:
        """Scrape the Apache autoindex for a GEO directory listing."""
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code != 200:
                return []
            # Apache auto-index links look like href="GSE12345_series_matrix.txt.gz"
            return re.findall(r'href="([^"?][^"]*)"', resp.text)
        except Exception:
            return []

    def _download_series(self, accession: str, data_type: str) -> Optional[pd.DataFrame]:
        """Try several formats until we have a DataFrame."""
        # 1) Preferred: the canonical combined series matrix.
        for url in self._candidate_matrix_urls(accession):
            df = self._try_parse_matrix(url)
            if df is not None:
                return df

        # 2) Some multi-platform series have per-platform matrix files —
        #    scrape the /matrix/ directory and try each one.
        listing = self._list_directory(f"{self._series_base_url(accession)}/matrix/")
        for name in listing:
            if name.endswith("_series_matrix.txt.gz"):
                df = self._try_parse_matrix(f"{self._series_base_url(accession)}/matrix/{name}")
                if df is not None:
                    return df

        # 3) SOFT family fallback (richer but heavier).
        soft_url = f"{self._series_base_url(accession)}/soft/{accession}_family.soft.gz"
        df = self._try_parse_soft(soft_url)
        if df is not None:
            return df

        # 4) MINiML fallback — metadata-only, but at least non-empty.
        miniml_url = f"{self._series_base_url(accession)}/miniml/{accession}_family.xml.tgz"
        df = self._try_parse_miniml(miniml_url)
        if df is not None:
            return df

        self.logger.warning(f"GEO {accession}: no parseable data found at any fallback path")
        return None

    # -------------------------------------------------------------- parsers --

    def _try_parse_matrix(self, url: str) -> Optional[pd.DataFrame]:
        """Download + parse a ``*_series_matrix.txt.gz`` file."""
        try:
            resp = self.session.get(url, timeout=120)
            if resp.status_code != 200:
                self.logger.debug(f"GEO matrix {resp.status_code}: {url}")
                return None
            raw = resp.content
            text = gzip.decompress(raw).decode("utf-8", errors="replace") if raw[:2] == b"\x1f\x8b" else raw.decode("utf-8", errors="replace")

            lines = text.splitlines()
            start = next(
                (i + 1 for i, ln in enumerate(lines) if ln.startswith("!series_matrix_table_begin")),
                None,
            )
            if start is None:
                return None
            end = next(
                (i for i, ln in enumerate(lines[start:], start=start) if ln.startswith("!series_matrix_table_end")),
                len(lines),
            )
            table = [ln.split("\t") for ln in lines[start:end] if ln.strip()]
            if len(table) < 2:
                return None
            header = [c.strip('"') for c in table[0]]
            rows = [r for r in table[1:] if len(r) == len(header)]
            if not rows:
                return None
            df = pd.DataFrame(rows, columns=header)
            self.logger.info(f"GEO matrix OK: {url} -> {df.shape}")
            return df
        except Exception as exc:
            self.logger.debug(f"GEO matrix parse failed for {url}: {exc}")
            return None

    def _try_parse_soft(self, url: str) -> Optional[pd.DataFrame]:
        """Best-effort SOFT parser — returns the series-level attribute table."""
        try:
            resp = self.session.get(url, timeout=180)
            if resp.status_code != 200:
                self.logger.debug(f"GEO SOFT {resp.status_code}: {url}")
                return None
            raw = resp.content
            text = gzip.decompress(raw).decode("utf-8", errors="replace") if raw[:2] == b"\x1f\x8b" else raw.decode("utf-8", errors="replace")

            # Pull the first table block (``!..._table_begin`` / ``_end``),
            # which is typically the per-sample expression values.
            start = next(
                (i + 1 for i, ln in enumerate(text.splitlines())
                 if ln.startswith("!") and ln.endswith("_table_begin")),
                None,
            )
            lines = text.splitlines()
            if start is not None:
                end = next(
                    (i for i, ln in enumerate(lines[start:], start=start)
                     if ln.startswith("!") and ln.endswith("_table_end")),
                    len(lines),
                )
                rows = [ln.split("\t") for ln in lines[start:end] if ln.strip()]
                if len(rows) >= 2:
                    header = rows[0]
                    body = [r for r in rows[1:] if len(r) == len(header)]
                    if body:
                        df = pd.DataFrame(body, columns=header)
                        self.logger.info(f"GEO SOFT OK: {url} -> {df.shape}")
                        return df

            # Otherwise expose the parsed ``!Series_<key> = <value>`` metadata
            # as a two-column DataFrame.  Better than returning nothing.
            attrs = [
                ln[1:].split(" = ", 1)
                for ln in lines
                if ln.startswith("!Series_") and " = " in ln
            ]
            if attrs:
                df = pd.DataFrame(attrs, columns=["attribute", "value"])
                self.logger.info(f"GEO SOFT (metadata) OK: {url} -> {df.shape}")
                return df
        except Exception as exc:
            self.logger.debug(f"GEO SOFT parse failed for {url}: {exc}")
        return None

    def _try_parse_miniml(self, url: str) -> Optional[pd.DataFrame]:
        """MINiML archives are tarball'd — only used as a last resort."""
        try:
            resp = self.session.get(url, timeout=180, stream=True)
            if resp.status_code != 200:
                self.logger.debug(f"GEO MINiML {resp.status_code}: {url}")
                return None
            import tarfile
            with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tf:
                xml_members = [m for m in tf.getmembers() if m.name.endswith(".xml")]
                if not xml_members:
                    return None
                with tf.extractfile(xml_members[0]) as f:
                    tree = ET.parse(f)
            root = tree.getroot()
            ns = {"m": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
            rows = []
            q = ".//m:Sample" if ns else ".//Sample"
            for sample in root.findall(q, ns or None):
                sid = sample.get("iid") or ""
                title_el = sample.find("m:Title" if ns else "Title", ns or None)
                rows.append({
                    "sample_id": sid,
                    "title": (title_el.text if title_el is not None else "") or "",
                })
            if rows:
                df = pd.DataFrame(rows)
                self.logger.info(f"GEO MINiML OK: {url} -> {df.shape}")
                return df
        except Exception as exc:
            self.logger.debug(f"GEO MINiML parse failed for {url}: {exc}")
        return None

    # ---------------------------------------------------------------- utils --

    @staticmethod
    def _normalize_gse(value: Any) -> str:
        if value is None:
            return ""
        s = str(value).strip().upper()
        if not s:
            return ""
        if s.startswith("GSE") and s[3:].isdigit():
            return s
        if s.isdigit():
            return f"GSE{s}"
        m = GSE_ACCESSION_RE.search(s)
        return m.group(0) if m else ""

    def _infer_data_type(self, title: str) -> str:
        t = (title or "").lower()
        if "methylation" in t:
            return "methylation"
        if "chip-seq" in t or "chipseq" in t:
            return "chip_seq"
        if "atac-seq" in t or "atacseq" in t:
            return "atac_seq"
        if "rna-seq" in t or "rnaseq" in t:
            return "rna_seq"
        if "mirna" in t or "microrna" in t:
            return "mirna"
        if "lncrna" in t:
            return "lncrna"
        return "expression"
