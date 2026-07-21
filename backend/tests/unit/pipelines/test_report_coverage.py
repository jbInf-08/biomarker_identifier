"""Self-contained unit tests for ``app.pipelines.report``.

Run with ``--noconftest``; no fixtures from ``tests/conftest.py`` are used.
"""

import importlib
import json
import os
import sys
import types
import zipfile

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Optional dependency stubs -- installed ONLY when the real package is absent so
# CI keeps exercising the genuine dependency.
# ---------------------------------------------------------------------------


def _ensure_statsmodels():
    try:  # pragma: no cover - depends on local env
        importlib.import_module("statsmodels.stats.multitest")
        return
    except ImportError:
        pass

    import numpy as _np

    statsmodels = types.ModuleType("statsmodels")
    stats_mod = types.ModuleType("statsmodels.stats")
    multitest = types.ModuleType("statsmodels.stats.multitest")

    def multipletests(pvals, alpha=0.05, method="fdr_bh", **kwargs):
        pvals = _np.asarray(pvals, dtype=float)
        adjusted = _np.clip(pvals * max(len(pvals), 1), 0.0, 1.0)
        reject = adjusted < alpha
        return reject, adjusted, alpha, alpha

    multitest.multipletests = multipletests
    stats_mod.multitest = multitest
    statsmodels.stats = stats_mod
    sys.modules.setdefault("statsmodels", statsmodels)
    sys.modules.setdefault("statsmodels.stats", stats_mod)
    sys.modules.setdefault("statsmodels.stats.multitest", multitest)


_ensure_statsmodels()

from app.pipelines.report import ReportGenerator  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _biomarkers(n=60):
    return [
        {
            "gene": f"GENE_{i}",
            "final_rank": i + 1,
            "final_score": 1.0 - i / 100.0,
            "consensus_score": 0.5 + i / 1000.0,
            "statistical_evidence": ["ttest"],
            "ml_evidence": ["rf", "lasso"],
        }
        for i in range(n)
    ]


def _full_results(n_biomarkers=60):
    expression = pd.DataFrame(
        [[float(i + j) for j in range(8)] for i in range(12)],
        index=[f"GENE_{i}" for i in range(12)],
        columns=[f"S{j}" for j in range(8)],
    )
    labels = pd.Series(["A", "B"] * 4, index=expression.columns)
    return {
        "run_id": "run-123",
        "run_name": "demo run",
        "timestamp": "2024-01-01T00:00:00",
        "pipeline_summary": {"steps_completed": 5},
        "pipeline_steps": ["load", "qc", "stats"],
        "config": {"alpha": 0.05, "seed": 42},
        "data_loading": {
            "expression_data": expression,
            "labels": labels,
            "validation_results": {"status": "passed"},
        },
        "quality_control": {
            "summary": {
                "status": "passed",
                "warnings": ["w1", "w2"],
                "recommendations": ["r1"],
            },
            "plots": {"pca": "pca.png"},
        },
        "normalization": {
            "normalization_method": "quantile",
            "batch_correction_applied": True,
        },
        "statistical_analysis": {
            "alpha": 0.01,
            "summary": {
                "methods_applied": ["ttest", "mannwhitney"],
                "total_significant_features": 7,
            },
            "method_results": {
                "ttest": {
                    "significant_features_adjusted": [f"G{i}" for i in range(25)]
                },
                "broken": {"error": "boom"},
                "no_key": {"pvalues": [0.1]},
            },
            "plots": {"volcano": "volcano.png"},
        },
        "ml_selection": {
            "summary": {
                "methods_applied": ["rf", "lasso"],
                "consensus_features_count": 4,
            },
            "stability_bootstraps": 50,
            "plots": {"importance": "imp.png"},
        },
        "pathway_analysis": {"plots": {"dotplot": "dot.png"}},
        "biomarker_list": {
            "biomarkers": _biomarkers(n_biomarkers),
            "summary": {"total_biomarkers": n_biomarkers, "high_confidence": 3},
        },
    }


# ---------------------------------------------------------------------------
# Construction / summary
# ---------------------------------------------------------------------------


def test_init_defaults():
    gen = ReportGenerator()
    assert gen.config == {}
    assert gen.report_data == {}


def test_init_with_config():
    cfg = {"theme": "dark"}
    gen = ReportGenerator(config=cfg)
    assert gen.config is cfg


def test_get_report_summary_empty():
    assert ReportGenerator().get_report_summary() == {"status": "No report generated"}


def test_get_report_summary_populated():
    gen = ReportGenerator()
    gen.report_data = {
        "metadata": {"report_title": "T"},
        "data_summary": {"n_genes": 3},
        "results_summary": {"total_biomarkers": 2},
        "extra": "ignored",
    }
    summary = gen.get_report_summary()
    assert set(summary) == {"metadata", "data_summary", "results_summary"}
    assert summary["data_summary"]["n_genes"] == 3


def test_get_report_summary_partial_keys():
    gen = ReportGenerator()
    gen.report_data = {"metadata": {"a": 1}}
    summary = gen.get_report_summary()
    assert summary["data_summary"] == {}
    assert summary["results_summary"] == {}


# ---------------------------------------------------------------------------
# _extract_methods_info
# ---------------------------------------------------------------------------


def test_extract_methods_info_empty_defaults():
    methods = ReportGenerator()._extract_methods_info({})
    qc = methods["data_processing"]["quality_control"]
    assert qc == {"status": "not_run", "n_warnings": 0, "n_recommendations": 0}
    assert methods["data_processing"]["normalization"] == {
        "method": "unknown",
        "batch_correction": False,
    }
    assert methods["statistical_analysis"] == {}
    assert methods["machine_learning"] == {}
    assert methods["pathway_analysis"] == {}
    assert methods["annotation"] == {}


def test_extract_methods_info_full():
    methods = ReportGenerator()._extract_methods_info(_full_results())
    assert methods["data_processing"]["quality_control"] == {
        "status": "passed",
        "n_warnings": 2,
        "n_recommendations": 1,
    }
    assert methods["data_processing"]["normalization"] == {
        "method": "quantile",
        "batch_correction": True,
    }
    assert methods["statistical_analysis"]["alpha"] == pytest.approx(0.01)
    assert methods["statistical_analysis"]["n_significant"] == 7
    assert methods["machine_learning"]["consensus_features"] == 4
    assert methods["machine_learning"]["stability_bootstraps"] == 50


def test_extract_methods_info_missing_nested_keys_uses_fallbacks():
    results = {
        "quality_control": {},
        "normalization": {},
        "statistical_analysis": {},
        "ml_selection": {},
    }
    methods = ReportGenerator()._extract_methods_info(results)
    assert methods["data_processing"]["quality_control"]["status"] == "unknown"
    assert methods["data_processing"]["normalization"]["method"] == "unknown"
    assert methods["statistical_analysis"]["alpha"] == pytest.approx(0.05)
    assert methods["statistical_analysis"]["methods_applied"] == []
    assert methods["machine_learning"]["stability_bootstraps"] == 100


# ---------------------------------------------------------------------------
# _extract_figures / _extract_tables / _extract_appendices
# ---------------------------------------------------------------------------


def test_extract_figures_empty():
    assert ReportGenerator()._extract_figures({}) == {}


def test_extract_figures_sections_without_plots_key():
    results = {
        "quality_control": {},
        "statistical_analysis": {},
        "ml_selection": {},
        "pathway_analysis": {},
    }
    assert ReportGenerator()._extract_figures(results) == {}


def test_extract_figures_all_sections():
    figures = ReportGenerator()._extract_figures(_full_results())
    assert set(figures) == {
        "quality_control",
        "statistical_analysis",
        "machine_learning",
        "pathway_analysis",
    }
    assert figures["machine_learning"] == {"importance": "imp.png"}


def test_extract_tables_empty():
    assert ReportGenerator()._extract_tables({}) == {}


def test_extract_tables_biomarker_list_truncated_to_50():
    tables = ReportGenerator()._extract_tables(_full_results(n_biomarkers=60))
    assert len(tables["biomarker_list"]) == 50
    assert tables["biomarker_list"][0]["gene"] == "GENE_0"


def test_extract_tables_biomarker_list_missing_biomarkers_key():
    tables = ReportGenerator()._extract_tables({"biomarker_list": {"summary": {}}})
    assert "biomarker_list" not in tables


def test_extract_tables_significant_features_skips_error_and_missing():
    tables = ReportGenerator()._extract_tables(_full_results())
    feats = tables["significant_features"]
    # Only the "ttest" method contributes, capped at 20.
    assert len(feats) == 20
    assert {f["method"] for f in feats} == {"ttest"}
    assert all(f["significant"] is True for f in feats)


def test_extract_tables_stats_without_method_results():
    tables = ReportGenerator()._extract_tables({"statistical_analysis": {}})
    assert "significant_features" not in tables


def test_extract_appendices_empty():
    app_data = ReportGenerator()._extract_appendices({})
    assert app_data["configuration"] == {}
    assert app_data["pipeline_steps"] == []
    assert app_data["run_metadata"] == {
        "run_id": None,
        "run_name": None,
        "timestamp": None,
    }


def test_extract_appendices_populated():
    app_data = ReportGenerator()._extract_appendices(_full_results())
    assert app_data["configuration"]["seed"] == 42
    assert app_data["pipeline_steps"] == ["load", "qc", "stats"]
    assert app_data["run_metadata"]["run_id"] == "run-123"


# ---------------------------------------------------------------------------
# _prepare_report_data
# ---------------------------------------------------------------------------


def test_prepare_report_data_minimal():
    data = ReportGenerator()._prepare_report_data({})
    assert data["metadata"]["pipeline_version"] == "1.0.0"
    assert data["metadata"]["report_title"] == "Biomarker Identification Report"
    assert data["metadata"]["investigator"] == "Unknown"
    assert data["data_summary"] == {}
    assert data["results_summary"] == {}
    assert data["figures"] == {}
    assert data["tables"] == {}
    assert "data_processing" in data["methods"]


def test_prepare_report_data_full_with_kwargs():
    data = ReportGenerator()._prepare_report_data(
        _full_results(),
        report_title="Custom Title",
        project_name="Proj",
        investigator="Dr X",
        institution="Inst",
    )
    assert data["metadata"]["report_title"] == "Custom Title"
    assert data["metadata"]["institution"] == "Inst"
    assert data["data_summary"] == {
        "n_genes": 12,
        "n_samples": 8,
        "n_classes": 2,
        "validation_status": "passed",
    }
    assert data["results_summary"]["total_biomarkers"] == 60
    assert data["pipeline_summary"] == {"steps_completed": 5}


def test_prepare_report_data_single_row_one_class():
    expression = pd.DataFrame([[1.0, 2.0]], index=["G0"], columns=["S0", "S1"])
    results = {
        "data_loading": {
            "expression_data": expression,
            "labels": pd.Series(["A", "A"]),
            "validation_results": {"status": "warning"},
        }
    }
    data = ReportGenerator()._prepare_report_data(results)
    assert data["data_summary"]["n_genes"] == 1
    assert data["data_summary"]["n_classes"] == 1
    assert data["data_summary"]["validation_status"] == "warning"


def test_prepare_report_data_malformed_data_loading_raises():
    with pytest.raises(KeyError):
        ReportGenerator()._prepare_report_data({"data_loading": {}})


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------


def test_default_html_template_contains_markers():
    tpl = ReportGenerator()._get_default_html_template()
    assert "<!DOCTYPE html>" in tpl
    assert "Executive Summary" in tpl
    assert "{{ metadata.report_title }}" in tpl


def test_generate_html_report_default_template(tmp_path):
    gen = ReportGenerator()
    report_data = gen._prepare_report_data(_full_results(), investigator="Ada")
    out = str(tmp_path / "report.html")
    result = gen._generate_html_report(report_data, out)
    assert result == out
    html = (tmp_path / "report.html").read_text(encoding="utf-8")
    assert "Biomarker Identification Report" in html
    assert "Ada" in html
    assert "GENE_0" in html
    # Only the top 20 biomarkers are rendered in the table.
    assert "GENE_19" in html
    assert "GENE_25" not in html


def test_generate_html_report_autoescapes_user_fields(tmp_path):
    gen = ReportGenerator()
    report_data = gen._prepare_report_data(
        _full_results(), investigator="<script>alert(1)</script>"
    )
    out = str(tmp_path / "esc.html")
    gen._generate_html_report(report_data, out)
    html = (tmp_path / "esc.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_generate_html_report_custom_template(tmp_path):
    tpl = tmp_path / "custom.html"
    tpl.write_text("<p>{{ metadata.project_name }}</p>", encoding="utf-8")
    gen = ReportGenerator()
    report_data = gen._prepare_report_data({}, project_name="MyProject")
    out = str(tmp_path / "custom_out.html")
    gen._generate_html_report(report_data, out, template_path=str(tpl))
    assert (tmp_path / "custom_out.html").read_text(encoding="utf-8") == (
        "<p>MyProject</p>"
    )


def test_generate_html_report_write_failure_raises(tmp_path):
    gen = ReportGenerator()
    report_data = gen._prepare_report_data(_full_results())
    bad = str(tmp_path / "missing_dir" / "report.html")
    with pytest.raises(OSError):
        gen._generate_html_report(report_data, bad)


def test_generate_html_report_missing_jinja2_raises(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "jinja2", None)
    gen = ReportGenerator()
    with pytest.raises(ImportError):
        gen._generate_html_report({"metadata": {}}, str(tmp_path / "x.html"))


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------


def test_generate_pdf_report_no_backend_returns_html(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    monkeypatch.setitem(sys.modules, "pdfkit", None)
    gen = ReportGenerator()
    report_data = gen._prepare_report_data(_full_results())
    out = str(tmp_path / "report.pdf")
    result = gen._generate_pdf_report(report_data, out)
    assert result == str(tmp_path / "report.html")
    assert os.path.exists(result)


def test_generate_pdf_report_with_weasyprint(tmp_path, monkeypatch):
    calls = {}

    class _HTML:
        def __init__(self, filename=None):
            calls["filename"] = filename

        def write_pdf(self, target):
            calls["target"] = target
            with open(target, "wb") as fh:
                fh.write(b"%PDF-1.4 fake")

    fake = types.ModuleType("weasyprint")
    fake.HTML = _HTML
    monkeypatch.setitem(sys.modules, "weasyprint", fake)

    gen = ReportGenerator()
    report_data = gen._prepare_report_data(_full_results())
    out = str(tmp_path / "report.pdf")
    result = gen._generate_pdf_report(report_data, out)

    assert result == out
    assert os.path.exists(out)
    # Intermediate HTML is cleaned up.
    assert not os.path.exists(str(tmp_path / "report.html"))
    assert calls["target"] == out


def test_generate_pdf_report_with_pdfkit_fallback(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    seen = {}

    def _from_file(src, dst):
        seen["src"] = src
        seen["dst"] = dst
        with open(dst, "wb") as fh:
            fh.write(b"%PDF-1.4 fake")

    fake = types.ModuleType("pdfkit")
    fake.from_file = _from_file
    monkeypatch.setitem(sys.modules, "pdfkit", fake)

    gen = ReportGenerator()
    report_data = gen._prepare_report_data(_full_results())
    out = str(tmp_path / "r.pdf")
    result = gen._generate_pdf_report(report_data, out)

    assert result == out
    assert seen["src"].endswith("r.html")
    assert not os.path.exists(str(tmp_path / "r.html"))


def test_generate_pdf_report_html_failure_propagates(tmp_path):
    gen = ReportGenerator()
    report_data = gen._prepare_report_data(_full_results())
    with pytest.raises(OSError):
        gen._generate_pdf_report(report_data, str(tmp_path / "nope" / "r.pdf"))


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------


def test_generate_report_html(tmp_path):
    gen = ReportGenerator()
    out = str(tmp_path / "gen.html")
    result = gen.generate_report(_full_results(), out, report_format="HTML")
    assert result == out
    assert os.path.exists(out)


def test_generate_report_pdf_without_backend(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "weasyprint", None)
    monkeypatch.setitem(sys.modules, "pdfkit", None)
    gen = ReportGenerator()
    out = str(tmp_path / "gen.pdf")
    result = gen.generate_report(_full_results(), out, report_format="pdf")
    assert result.endswith(".html")


def test_generate_report_unsupported_format(tmp_path):
    with pytest.raises(ValueError, match="Unsupported report format"):
        ReportGenerator().generate_report(
            _full_results(), str(tmp_path / "x.txt"), report_format="docx"
        )


def test_generate_report_propagates_preparation_error(tmp_path):
    with pytest.raises(KeyError):
        ReportGenerator().generate_report(
            {"data_loading": {}}, str(tmp_path / "a.html")
        )


# ---------------------------------------------------------------------------
# _save_environment_info
# ---------------------------------------------------------------------------


def test_save_environment_info_success(tmp_path, monkeypatch):
    import subprocess

    class _Result:
        stdout = "pandas==2.1.4\n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Result())
    out = tmp_path / "env.txt"
    ReportGenerator()._save_environment_info(str(out))
    text = out.read_text(encoding="utf-8")
    assert "Python version:" in text
    assert "pandas==2.1.4" in text


def test_save_environment_info_pip_failure_writes_fallback(tmp_path, monkeypatch):
    import subprocess

    def _boom(*a, **k):
        raise RuntimeError("pip exploded")

    monkeypatch.setattr(subprocess, "run", _boom)
    out = tmp_path / "env2.txt"
    ReportGenerator()._save_environment_info(str(out))
    assert "Could not retrieve package information" in out.read_text(encoding="utf-8")


def test_save_environment_info_bad_path_is_swallowed(tmp_path):
    bad = str(tmp_path / "no_such_dir" / "env.txt")
    # Failure is logged, not raised.
    assert ReportGenerator()._save_environment_info(bad) is None
    assert not os.path.exists(bad)


# ---------------------------------------------------------------------------
# _create_bundle_readme
# ---------------------------------------------------------------------------


def test_create_bundle_readme_success(tmp_path):
    out = tmp_path / "README.md"
    ReportGenerator()._create_bundle_readme(str(out), _full_results())
    text = out.read_text(encoding="utf-8")
    assert "# Biomarker Identification Run Bundle" in text
    assert "run-123" in text
    assert "## Citation" in text


def test_create_bundle_readme_missing_metadata(tmp_path):
    out = tmp_path / "README2.md"
    ReportGenerator()._create_bundle_readme(str(out), {})
    text = out.read_text(encoding="utf-8")
    assert "**Run ID:** Unknown" in text


def test_create_bundle_readme_bad_path_is_swallowed(tmp_path):
    bad = str(tmp_path / "nope" / "README.md")
    assert ReportGenerator()._create_bundle_readme(bad, {}) is None
    assert not os.path.exists(bad)


# ---------------------------------------------------------------------------
# create_run_bundle
# ---------------------------------------------------------------------------


def _bundle_safe_results():
    """Pipeline results without DataFrames so json/yaml dumps stay small."""
    results = _full_results(n_biomarkers=5)
    results.pop("data_loading")
    return results


@pytest.fixture
def fast_pip_freeze(monkeypatch):
    """Stub out ``pip freeze`` -- the real call adds ~13s per bundle test."""
    import subprocess

    class _Result:
        stdout = "pandas==2.1.4\n"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _Result())


def test_create_run_bundle_creates_zip(tmp_path, fast_pip_freeze):
    gen = ReportGenerator()
    zip_path = gen.create_run_bundle(_bundle_safe_results(), str(tmp_path))

    assert zip_path == os.path.join(str(tmp_path), "run-123_bundle.zip")
    assert os.path.exists(zip_path)
    # The staging directory is removed after zipping.
    assert not os.path.exists(os.path.join(str(tmp_path), "run-123_bundle"))

    with zipfile.ZipFile(zip_path) as zf:
        names = {n.replace("\\", "/") for n in zf.namelist()}
        assert "pipeline_results.json" in names
        assert "README.md" in names
        assert "reports/biomarker_report.html" in names
        assert "configs/pipeline_config.yaml" in names
        assert "configs/environment.txt" in names
        payload = json.loads(zf.read("pipeline_results.json"))
        assert payload["run_id"] == "run-123"


def test_create_run_bundle_uses_unknown_run_id_default(tmp_path, fast_pip_freeze):
    results = _bundle_safe_results()
    results.pop("run_id")
    zip_path = ReportGenerator().create_run_bundle(results, str(tmp_path))
    assert os.path.basename(zip_path) == "unknown_run_bundle.zip"


def test_create_run_bundle_failure_propagates(tmp_path, monkeypatch):
    def _boom(*a, **k):
        raise OSError("cannot create directory")

    monkeypatch.setattr(os, "makedirs", _boom)
    with pytest.raises(OSError):
        ReportGenerator().create_run_bundle(_bundle_safe_results(), str(tmp_path))
