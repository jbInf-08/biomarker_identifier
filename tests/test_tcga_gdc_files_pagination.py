"""Unit tests for GDC /files pagination in TCGACollector (no network)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

import numpy as np
import pandas as pd
import pytest

from data_collection.tcga_collector import TCGACollector

REPO = Path(__file__).resolve().parents[1]


def _load_fetch_script():
    path = REPO / "scripts" / "paper" / "fetch_tcga_brca_er.py"
    spec = importlib.util.spec_from_file_location("fetch_tcga_brca_er", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fetch_tcga_brca_er"] = mod
    spec.loader.exec_module(mod)
    return mod


def _json_response(payload: Dict[str, Any]) -> mock.MagicMock:
    r = mock.MagicMock()
    r.json.return_value = payload
    return r


def test_collect_gene_expression_paginates_files_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    GDC caps /files page size; collector must issue multiple POSTs until
    sample_limit is reached or pagination.total is exhausted.
    """
    files_posts: List[Dict[str, Any]] = []

    def make_request(
        self: TCGACollector,
        url: str,
        method: str = "GET",
        params: Any = None,
        data: Any = None,
        headers: Any = None,
        timeout: int = 30,
    ) -> mock.MagicMock:
        u = url.rstrip("/")
        if u.endswith("/files") and method == "POST":
            body = json.loads(data)
            files_posts.append(body)
            frm = int(body["from"])
            page_size = int(body["size"])
            assert page_size <= 10

            if frm == 0:
                hits = [
                    {
                        "file_id": f"f{i:03d}",
                        "file_name": f"{i}.tsv",
                        "cases": [{"submitter_id": f"TCGA-XX-{i:04d}"}],
                    }
                    for i in range(10)
                ]
                return _json_response(
                    {
                        "data": {
                            "hits": hits,
                            "pagination": {"total": 15, "from": 0, "size": 10, "pages": 2},
                        }
                    }
                )
            if frm == 10:
                hits = [
                    {
                        "file_id": f"f{i:03d}",
                        "file_name": f"{i}.tsv",
                        "cases": [{"submitter_id": f"TCGA-XX-{i:04d}"}],
                    }
                    for i in range(10, 15)
                ]
                return _json_response(
                    {
                        "data": {
                            "hits": hits,
                            "pagination": {"total": 15, "from": 10, "size": 5, "pages": 2},
                        }
                    }
                )
            pytest.fail(f"unexpected pagination from={frm}")

        pytest.fail(f"unexpected request {method} {url}")

    def fake_download(
        self: TCGACollector,
        file_list: List[Dict[str, Any]],
        data_type: str,
    ) -> pd.DataFrame:
        assert data_type == "gene_expression"
        assert len(file_list) == 15
        cols = [f"TCGA-XX-{i:04d}" for i in range(15)]
        return pd.DataFrame(np.ones((2, 15)), index=["G1", "G2"], columns=cols)

    monkeypatch.setattr(TCGACollector, "_make_request", make_request)
    monkeypatch.setattr(
        TCGACollector, "_download_and_process_gdc_files", fake_download
    )

    collector = TCGACollector(
        output_dir=str(tmp_path), rate_limit_delay=0, max_retries=1
    )
    out = collector.collect_data(
        data_type="gene_expression",
        cancer_type="BRCA",
        sample_limit=15,
        workflow_type="STAR - Counts",
        gdc_page_size=10,
    )

    assert len(files_posts) == 2
    assert files_posts[0]["from"] == 0 and files_posts[0]["size"] == 10
    assert files_posts[1]["from"] == 10 and files_posts[1]["size"] == 5

    df = out["data"]
    assert df is not None
    assert not df.empty
    assert df.shape == (2, 15)


def test_fetch_gdc_status_reads_top_level_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """GDC /status returns data_release at JSON root (not under data)."""
    mod = _load_fetch_script()

    def fake_get(url: str, timeout: float = 60):
        assert "status" in url
        r = mock.MagicMock()
        r.raise_for_status = lambda: None
        r.json.return_value = {
            "data_release": "Data Release 45.0",
            "data_release_version": {"major": 45, "minor": 0, "release_date": "2025-12-04"},
            "commit": "abc",
            "tag": "8.3.1",
            "status": "OK",
        }
        return r

    monkeypatch.setattr(mod.requests, "get", fake_get)
    st = mod.fetch_gdc_status(timeout_s=5)
    assert st.get("data_release") == "Data Release 45.0"
    assert st.get("commit") == "abc"
    txt = mod._format_data_release_version(st.get("data_release_version"))
    assert "45" in txt and "2025-12-04" in txt
