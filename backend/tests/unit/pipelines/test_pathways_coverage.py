"""Self-contained coverage tests for app.pipelines.pathways.

Run with --noconftest: no shared fixtures are used, all data is built inline.
gseapy is an optional dependency of the module; every test that needs it
injects an explicit fake into sys.modules (mocking a networked dependency),
and the ImportError paths are exercised by mapping the name to None.
"""

import importlib.util
import json
import sys
import types

import numpy as np
import pandas as pd
import pytest


def _ensure_statsmodels():
    """app.pipelines.__init__ pulls in a module that needs statsmodels.

    Install a minimal stub ONLY when the real package is absent, so CI (which
    has statsmodels pinned) still exercises the genuine dependency.
    """
    if importlib.util.find_spec("statsmodels") is not None:
        return
    statsmodels = types.ModuleType("statsmodels")
    stats_mod = types.ModuleType("statsmodels.stats")
    multitest = types.ModuleType("statsmodels.stats.multitest")

    def multipletests(pvals, alpha=0.05, method="fdr_bh", **kwargs):
        pvals = np.asarray(pvals, dtype=float)
        adjusted = np.minimum(pvals * max(len(pvals), 1), 1.0)
        return adjusted < alpha, adjusted, alpha, alpha

    multitest.multipletests = multipletests
    stats_mod.multitest = multitest
    statsmodels.stats = stats_mod
    sys.modules.setdefault("statsmodels", statsmodels)
    sys.modules.setdefault("statsmodels.stats", stats_mod)
    sys.modules.setdefault("statsmodels.stats.multitest", multitest)


_ensure_statsmodels()

from app.pipelines.pathways import PathwayAnalysis  # noqa: E402

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def make_expression(n_genes=12, n_samples=24, seed=0):
    rng = np.random.default_rng(seed)
    genes = [f"GENE{i}" for i in range(n_genes)]
    samples = [f"S{i}" for i in range(n_samples)]
    data = rng.normal(loc=5.0, scale=1.0, size=(n_genes, n_samples))
    # give the first few genes a real group difference
    data[:3, : n_samples // 2] += 3.0
    return pd.DataFrame(data, index=genes, columns=samples)


def make_labels(n_samples=24):
    samples = [f"S{i}" for i in range(n_samples)]
    return pd.Series([0] * (n_samples // 2) + [1] * (n_samples // 2), index=samples)


def gsea_row_frame():
    return pd.DataFrame(
        [
            {
                "Name": "Pathway A",
                "ES": 0.7,
                "NES": 1.9,
                "NOM p-val": 0.001,
                "FDR q-val": 0.01,
                "FWER p-val": 0.02,
                "SIZE": 30,
                "LEADING EDGE": "GENE0,GENE1",
            },
            {
                "Name": "Pathway B",
                "ES": -0.4,
                "NES": -1.1,
                "NOM p-val": 0.4,
                "FDR q-val": 0.6,
                "FWER p-val": 0.7,
                "SIZE": 20,
                "LEADING EDGE": "GENE2",
            },
        ]
    )


def ora_row_frame():
    return pd.DataFrame(
        [
            {
                "Term": "Term A",
                "P-value": 0.0001,
                "Adjusted P-value": 0.001,
                "Odds Ratio": 4.5,
                "Combined Score": 33.0,
                "Genes": "GENE0;GENE1",
                "Overlap": 5,
                "Pathway Size": 120,
            },
            {
                "Term": "Term B",
                "P-value": 0.3,
                "Adjusted P-value": 0.5,
                "Odds Ratio": 1.2,
                "Combined Score": 2.0,
                "Genes": "GENE2",
                "Overlap": 2,
                "Pathway Size": 80,
            },
        ]
    )


def install_fake_gseapy(monkeypatch, gsea_obj=None, enrichr_obj=None, raises=None):
    """Insert a deterministic stand-in for the networked gseapy package."""
    mod = types.ModuleType("gseapy")

    def _gsea(**kwargs):
        if raises is not None:
            raise raises
        return gsea_obj

    def _enrichr(**kwargs):
        if raises is not None:
            raise raises
        return enrichr_obj

    mod.gsea = _gsea
    mod.enrichr = _enrichr
    monkeypatch.setitem(sys.modules, "gseapy", mod)
    return mod


class Res2d:
    def __init__(self, res2d):
        self.res2d = res2d


class EnrichrRes:
    def __init__(self, results):
        self.results = results


# ---------------------------------------------------------------------------
# init / trivial accessors
# ---------------------------------------------------------------------------


def test_init_defaults_and_config():
    pa = PathwayAnalysis()
    assert pa.config == {}
    assert pa.pathway_results == {}

    pa2 = PathwayAnalysis({"a": 1})
    assert pa2.config == {"a": 1}


def test_map_gene_set_name_known_and_unknown():
    pa = PathwayAnalysis()
    assert pa._map_gene_set_name("KEGG") == "KEGG_2021_Human"
    assert pa._map_gene_set_name("REACTOME") == "Reactome_2022"
    assert pa._map_gene_set_name("GO_BP") == "GO_Biological_Process_2021"
    assert pa._map_gene_set_name("GO_MF") == "GO_Molecular_Function_2021"
    assert pa._map_gene_set_name("GO_CC") == "GO_Cellular_Component_2021"
    assert pa._map_gene_set_name("HALLMARK") == "MSigDB_Hallmark_2020"
    assert pa._map_gene_set_name("CURATED") == "MSigDB_Curated_2020"
    # unknown names pass through unchanged
    assert pa._map_gene_set_name("Custom_2024") == "Custom_2024"


def test_get_pathway_summary_without_analysis():
    pa = PathwayAnalysis()
    assert pa.get_pathway_summary() == {"status": "No pathway analysis performed"}


def test_get_pathway_summary_after_results():
    pa = PathwayAnalysis()
    pa.pathway_results = {"summary": {"n_genes": 3}}
    assert pa.get_pathway_summary() == {"n_genes": 3}


def test_get_pathway_summary_missing_summary_key():
    pa = PathwayAnalysis()
    pa.pathway_results = {"gene_list": ["A"]}
    assert pa.get_pathway_summary() == {"status": "unknown"}


# ---------------------------------------------------------------------------
# _calculate_differential_expression
# ---------------------------------------------------------------------------


def test_calculate_differential_expression_shape_and_sorting():
    pa = PathwayAnalysis()
    expr = make_expression()
    labels = make_labels()

    de = pa._calculate_differential_expression(expr, labels)

    assert list(de.columns) == ["log2fc"]
    assert de.index.name == "gene"
    assert len(de) == expr.shape[0]
    assert set(de.index) == set(expr.index)
    assert np.isfinite(de["log2fc"].to_numpy()).all()


def test_calculate_differential_expression_single_class_raises_keyerror():
    """With one label group no rows are produced, so the sort by 'pval' fails."""
    pa = PathwayAnalysis()
    expr = make_expression(n_genes=4, n_samples=8)
    labels = pd.Series([1] * 8, index=expr.columns)

    with pytest.raises(KeyError):
        pa._calculate_differential_expression(expr, labels)


def test_calculate_differential_expression_three_classes_raises_keyerror():
    pa = PathwayAnalysis()
    expr = make_expression(n_genes=4, n_samples=9)
    labels = pd.Series([0, 0, 0, 1, 1, 1, 2, 2, 2], index=expr.columns)

    with pytest.raises(KeyError):
        pa._calculate_differential_expression(expr, labels)


def test_calculate_differential_expression_with_nans():
    pa = PathwayAnalysis()
    expr = make_expression(n_genes=5, n_samples=10, seed=3)
    expr.iloc[0, 0] = np.nan
    labels = make_labels(10)

    de = pa._calculate_differential_expression(expr, labels)
    assert len(de) == 5


# ---------------------------------------------------------------------------
# _run_gsea
# ---------------------------------------------------------------------------


def test_run_gsea_success(monkeypatch):
    install_fake_gseapy(monkeypatch, gsea_obj=Res2d(gsea_row_frame()))
    pa = PathwayAnalysis()

    out = pa._run_gsea(make_expression(), make_labels(), ["KEGG"])

    assert out["KEGG"]["status"] == "success"
    rows = out["KEGG"]["results"]
    assert len(rows) == 2
    assert rows[0]["pathway"] == "Pathway A"
    assert rows[0]["es"] == pytest.approx(0.7)
    assert rows[0]["nes"] == pytest.approx(1.9)
    assert rows[0]["pval"] == pytest.approx(0.001)
    assert rows[0]["fdr"] == pytest.approx(0.01)
    assert rows[0]["fw_pval"] == pytest.approx(0.02)
    assert rows[0]["size"] == 30
    assert rows[0]["leading_edge"] == ["GENE0", "GENE1"]


def test_run_gsea_passes_kwargs(monkeypatch):
    captured = {}
    mod = types.ModuleType("gseapy")

    def _gsea(**kwargs):
        captured.update(kwargs)
        return Res2d(gsea_row_frame())

    mod.gsea = _gsea
    monkeypatch.setitem(sys.modules, "gseapy", mod)

    pa = PathwayAnalysis()
    pa._run_gsea(
        make_expression(),
        make_labels(),
        ["HALLMARK"],
        min_size=5,
        max_size=100,
        permutation_num=10,
        weighted_score_type=0,
    )

    assert captured["gene_sets"] == "MSigDB_Hallmark_2020"
    assert captured["min_size"] == 5
    assert captured["max_size"] == 100
    assert captured["permutation_num"] == 10
    assert captured["weighted_score_type"] == 0
    assert captured["outdir"] is None


def test_run_gsea_no_results_when_res2d_none(monkeypatch):
    install_fake_gseapy(monkeypatch, gsea_obj=Res2d(None))
    pa = PathwayAnalysis()

    out = pa._run_gsea(make_expression(), make_labels(), ["KEGG", "GO_BP"])

    assert out["KEGG"] == {"results": [], "status": "no_results"}
    assert out["GO_BP"] == {"results": [], "status": "no_results"}


def test_run_gsea_no_res2d_attribute(monkeypatch):
    install_fake_gseapy(monkeypatch, gsea_obj=object())
    pa = PathwayAnalysis()

    out = pa._run_gsea(make_expression(), make_labels(), ["KEGG"])
    assert out["KEGG"]["status"] == "no_results"


def test_run_gsea_per_gene_set_error(monkeypatch):
    install_fake_gseapy(monkeypatch, raises=RuntimeError("boom"))
    pa = PathwayAnalysis()

    out = pa._run_gsea(make_expression(), make_labels(), ["KEGG"])

    assert out["KEGG"]["status"] == "error"
    assert out["KEGG"]["results"] == []
    assert "boom" in out["KEGG"]["error"]


def test_run_gsea_empty_gene_sets(monkeypatch):
    install_fake_gseapy(monkeypatch, gsea_obj=Res2d(gsea_row_frame()))
    pa = PathwayAnalysis()
    assert pa._run_gsea(make_expression(), make_labels(), []) == {}


def test_run_gsea_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "gseapy", None)
    pa = PathwayAnalysis()

    out = pa._run_gsea(make_expression(), make_labels(), ["KEGG"])
    assert out == {"error": "gseapy not available"}


def test_run_gsea_outer_exception_single_class(monkeypatch):
    """A one-class label vector blows up before the gene-set loop."""
    install_fake_gseapy(monkeypatch, gsea_obj=Res2d(gsea_row_frame()))
    pa = PathwayAnalysis()
    expr = make_expression(n_genes=4, n_samples=8)
    labels = pd.Series([1] * 8, index=expr.columns)

    out = pa._run_gsea(expr, labels, ["KEGG"])
    assert list(out.keys()) == ["error"]
    assert isinstance(out["error"], str)


# ---------------------------------------------------------------------------
# _run_ora
# ---------------------------------------------------------------------------


def test_run_ora_success(monkeypatch):
    install_fake_gseapy(monkeypatch, enrichr_obj=EnrichrRes(ora_row_frame()))
    pa = PathwayAnalysis()

    out = pa._run_ora(["GENE0", "GENE1"], ["KEGG"])

    assert out["KEGG"]["status"] == "success"
    rows = out["KEGG"]["results"]
    assert len(rows) == 2
    assert rows[0]["pathway"] == "Term A"
    assert rows[0]["pval"] == pytest.approx(0.0001)
    assert rows[0]["adj_pval"] == pytest.approx(0.001)
    assert rows[0]["odds_ratio"] == pytest.approx(4.5)
    assert rows[0]["combined_score"] == pytest.approx(33.0)
    assert rows[0]["genes"] == ["GENE0", "GENE1"]
    assert rows[0]["overlap_size"] == 5
    assert rows[0]["pathway_size"] == 120


def test_run_ora_passes_arguments(monkeypatch):
    captured = {}
    mod = types.ModuleType("gseapy")

    def _enrichr(**kwargs):
        captured.update(kwargs)
        return EnrichrRes(ora_row_frame())

    mod.enrichr = _enrichr
    monkeypatch.setitem(sys.modules, "gseapy", mod)

    pa = PathwayAnalysis()
    pa._run_ora(["A", "B"], ["REACTOME"])

    assert captured["gene_list"] == ["A", "B"]
    assert captured["gene_sets"] == "Reactome_2022"
    assert captured["organism"] == "Human"
    assert captured["outdir"] is None


def test_run_ora_no_results(monkeypatch):
    install_fake_gseapy(monkeypatch, enrichr_obj=EnrichrRes(None))
    pa = PathwayAnalysis()

    out = pa._run_ora(["A"], ["KEGG"])
    assert out["KEGG"] == {"results": [], "status": "no_results"}


def test_run_ora_missing_results_attribute(monkeypatch):
    install_fake_gseapy(monkeypatch, enrichr_obj=object())
    pa = PathwayAnalysis()

    out = pa._run_ora(["A"], ["KEGG"])
    assert out["KEGG"]["status"] == "no_results"


def test_run_ora_row_conversion_error_is_caught(monkeypatch):
    """Real Enrichr returns Overlap as '5/120'; int() on that raises and the
    per-gene-set handler records status 'error' (documents current behaviour)."""
    df = ora_row_frame()
    df["Overlap"] = ["5/120", "2/80"]
    install_fake_gseapy(monkeypatch, enrichr_obj=EnrichrRes(df))
    pa = PathwayAnalysis()

    out = pa._run_ora(["A"], ["KEGG"])
    assert out["KEGG"]["status"] == "error"
    assert out["KEGG"]["results"] == []
    assert "error" in out["KEGG"]


def test_run_ora_per_gene_set_error(monkeypatch):
    install_fake_gseapy(monkeypatch, raises=ValueError("enrichr down"))
    pa = PathwayAnalysis()

    out = pa._run_ora(["A"], ["KEGG", "GO_BP"])
    assert out["KEGG"]["status"] == "error"
    assert "enrichr down" in out["GO_BP"]["error"]


def test_run_ora_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "gseapy", None)
    pa = PathwayAnalysis()

    assert pa._run_ora(["A"], ["KEGG"]) == {"error": "gseapy not available"}


def test_run_ora_outer_exception(monkeypatch):
    """gene_sets that is not iterable trips the outer handler."""
    install_fake_gseapy(monkeypatch, enrichr_obj=EnrichrRes(ora_row_frame()))
    pa = PathwayAnalysis()

    out = pa._run_ora(["A"], 5)
    assert list(out.keys()) == ["error"]


# ---------------------------------------------------------------------------
# _generate_pathway_summary
# ---------------------------------------------------------------------------


def test_generate_pathway_summary_counts_significant():
    pa = PathwayAnalysis()
    results = {
        "gene_list": ["A", "B", "C"],
        "analysis_type": "both",
        "gene_sets": ["KEGG"],
        "gsea_results": {
            "KEGG": {
                "status": "success",
                "results": [{"fdr": 0.01}, {"fdr": 0.5}, {"fdr": 0.001}],
            }
        },
        "ora_results": {
            "KEGG": {
                "status": "success",
                "results": [{"adj_pval": 0.02}, {"adj_pval": 0.9}],
            }
        },
    }

    summary = pa._generate_pathway_summary(results)

    assert summary["n_genes"] == 3
    assert summary["analysis_type"] == "both"
    assert summary["gene_sets"] == ["KEGG"]
    assert summary["gsea_summary"]["KEGG"] == {
        "n_pathways": 3,
        "n_significant": 2,
        "status": "success",
    }
    assert summary["ora_summary"]["KEGG"] == {
        "n_pathways": 2,
        "n_significant": 1,
        "status": "success",
    }


def test_generate_pathway_summary_empty_results():
    pa = PathwayAnalysis()
    summary = pa._generate_pathway_summary({})

    assert summary["n_genes"] == 0
    assert summary["analysis_type"] == "unknown"
    assert summary["gene_sets"] == []
    assert summary["gsea_summary"] == {}
    assert summary["ora_summary"] == {}


def test_generate_pathway_summary_skips_non_dict_and_error_entries():
    pa = PathwayAnalysis()
    results = {
        "gene_list": [],
        "gsea_results": {"error": "gseapy not available"},
        "ora_results": {"KEGG": ["not", "a", "dict"]},
    }

    summary = pa._generate_pathway_summary(results)
    assert summary["gsea_summary"] == {}
    assert summary["ora_summary"] == {}


def test_generate_pathway_summary_missing_status_defaults_unknown():
    pa = PathwayAnalysis()
    results = {"gene_list": ["A"], "gsea_results": {"KEGG": {"results": []}}}

    summary = pa._generate_pathway_summary(results)
    assert summary["gsea_summary"]["KEGG"]["status"] == "unknown"
    assert summary["gsea_summary"]["KEGG"]["n_pathways"] == 0


# ---------------------------------------------------------------------------
# _generate_pathway_plots
# ---------------------------------------------------------------------------


def _full_results():
    return {
        "gene_sets": ["KEGG", "GO_BP"],
        "gsea_results": {
            "KEGG": {
                "status": "success",
                "results": [
                    {"pathway": "P1", "nes": 1.9, "fdr": 0.01},
                    {"pathway": "P2", "nes": -1.2, "fdr": 0.5},
                ],
            },
            "GO_BP": {"status": "no_results", "results": []},
        },
        "ora_results": {
            "KEGG": {
                "status": "success",
                "results": [
                    {
                        "pathway": "T1",
                        "adj_pval": 0.001,
                        "odds_ratio": 4.0,
                        "overlap_size": 5,
                    },
                    {
                        "pathway": "T2",
                        "adj_pval": 0.4,
                        "odds_ratio": 1.1,
                        "overlap_size": 2,
                    },
                ],
            },
            "GO_BP": {"status": "error", "results": []},
        },
        "summary": {
            "gsea_summary": {"KEGG": {"n_significant": 1}},
            "ora_summary": {"KEGG": {"n_significant": 1}},
        },
    }


def test_generate_pathway_plots_full():
    pa = PathwayAnalysis()
    plots = pa._generate_pathway_plots(_full_results())

    assert "gsea_KEGG" in plots
    assert "ora_KEGG" in plots
    assert "method_comparison" in plots
    # gene sets with empty result lists produce no figure
    assert "gsea_GO_BP" not in plots
    assert "ora_GO_BP" not in plots


def test_generate_pathway_plots_missing_expected_columns():
    pa = PathwayAnalysis()
    results = {
        "gene_sets": ["KEGG"],
        "gsea_results": {"KEGG": {"results": [{"pathway": "P1", "other": 1}]}},
        "ora_results": {"KEGG": {"results": [{"pathway": "T1", "other": 2}]}},
        "summary": {},
    }

    plots = pa._generate_pathway_plots(results)
    assert plots == {}


def test_generate_pathway_plots_no_comparison_data():
    pa = PathwayAnalysis()
    results = {
        "gene_sets": ["KEGG"],
        "summary": {"gsea_summary": {}, "ora_summary": {}},
    }

    plots = pa._generate_pathway_plots(results)
    assert "method_comparison" not in plots


def test_generate_pathway_plots_empty_results_dict():
    pa = PathwayAnalysis()
    assert pa._generate_pathway_plots({}) == {}


def test_generate_pathway_plots_plotly_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "plotly.express", None)
    pa = PathwayAnalysis()

    assert pa._generate_pathway_plots(_full_results()) == {}


# ---------------------------------------------------------------------------
# get_significant_pathways
# ---------------------------------------------------------------------------


def _analysed():
    pa = PathwayAnalysis()
    pa.pathway_results = {
        "gsea_results": {
            "KEGG": {
                "results": [
                    {"pathway": "G1", "fdr": 0.01},
                    {"pathway": "G2", "fdr": 0.001},
                    {"pathway": "G3", "fdr": 0.9},
                ]
            },
            "GO_BP": {"results": [{"pathway": "G4", "fdr": 0.02}]},
        },
        "ora_results": {
            "KEGG": {
                "results": [
                    {"pathway": "O1", "adj_pval": 0.04},
                    {"pathway": "O2", "adj_pval": 0.6},
                ]
            },
            "GO_BP": {"error": "nope"},
        },
    }
    return pa


def test_get_significant_pathways_empty_when_no_results():
    assert PathwayAnalysis().get_significant_pathways() == []


def test_get_significant_pathways_both_methods_sorted_by_fdr():
    pa = _analysed()
    out = pa.get_significant_pathways()

    names = [p["pathway"] for p in out]
    assert set(names) == {"G1", "G2", "G4", "O1"}
    # first entry carries an 'fdr' key so the list is sorted by fdr ascending
    assert out[0]["pathway"] == "G2"
    assert all("method" in p and "gene_set" in p for p in out)


def test_get_significant_pathways_gsea_only():
    pa = _analysed()
    out = pa.get_significant_pathways(method="gsea")
    assert {p["method"] for p in out} == {"GSEA"}
    assert len(out) == 3


def test_get_significant_pathways_ora_only_sorted_by_adj_pval():
    pa = _analysed()
    out = pa.get_significant_pathways(method="ora")
    assert [p["pathway"] for p in out] == ["O1"]
    assert out[0]["method"] == "ORA"
    assert out[0]["gene_set"] == "KEGG"


def test_get_significant_pathways_filtered_by_gene_set():
    pa = _analysed()
    out = pa.get_significant_pathways(gene_set="GO_BP")
    assert [p["pathway"] for p in out] == ["G4"]


def test_get_significant_pathways_threshold():
    pa = _analysed()
    strict = pa.get_significant_pathways(p_threshold=0.005)
    assert [p["pathway"] for p in strict] == ["G2"]

    loose = pa.get_significant_pathways(p_threshold=1.0)
    assert len(loose) == 6


def test_get_significant_pathways_does_not_mutate_source():
    pa = _analysed()
    pa.get_significant_pathways()
    assert "method" not in pa.pathway_results["gsea_results"]["KEGG"]["results"][0]


def test_get_significant_pathways_ora_sort_branch():
    pa = PathwayAnalysis()
    pa.pathway_results = {
        "ora_results": {
            "KEGG": {
                "results": [
                    {"pathway": "O1", "adj_pval": 0.04},
                    {"pathway": "O2", "adj_pval": 0.001},
                ]
            }
        }
    }
    out = pa.get_significant_pathways()
    assert [p["pathway"] for p in out] == ["O2", "O1"]


# ---------------------------------------------------------------------------
# save_pathway_results
# ---------------------------------------------------------------------------


def test_save_pathway_results_without_results_raises():
    pa = PathwayAnalysis()
    with pytest.raises(ValueError, match="No pathway results to save"):
        pa.save_pathway_results("out.json")


def test_save_pathway_results_json(tmp_path):
    pa = _analysed()
    target = tmp_path / "res.json"

    returned = pa.save_pathway_results(str(target))

    assert returned == str(target)
    loaded = json.loads(target.read_text())
    assert "gsea_results" in loaded and "ora_results" in loaded


def test_save_pathway_results_json_uppercase_format(tmp_path):
    pa = _analysed()
    target = tmp_path / "res2.json"
    pa.save_pathway_results(str(target), format="JSON")
    assert target.exists()


def test_save_pathway_results_csv_with_rows(tmp_path):
    pa = _analysed()
    target = tmp_path / "res.csv"

    pa.save_pathway_results(str(target), format="csv")

    df = pd.read_csv(target)
    assert len(df) == 4
    assert "pathway" in df.columns
    assert "method" in df.columns


def test_save_pathway_results_csv_empty(tmp_path):
    pa = PathwayAnalysis()
    pa.pathway_results = {"gsea_results": {"KEGG": {"results": [{"fdr": 0.9}]}}}
    target = tmp_path / "empty.csv"

    pa.save_pathway_results(str(target), format="csv")

    df = pd.read_csv(target)
    assert df.empty
    assert list(df.columns) == [
        "pathway",
        "method",
        "gene_set",
        "pval",
        "fdr",
        "adj_pval",
    ]


def test_save_pathway_results_unsupported_format(tmp_path):
    pa = _analysed()
    with pytest.raises(ValueError, match="Unsupported format"):
        pa.save_pathway_results(str(tmp_path / "x.tsv"), format="tsv")


def test_save_pathway_results_bad_path_reraises(tmp_path):
    pa = _analysed()
    bad = tmp_path / "missing_dir" / "res.json"
    with pytest.raises(OSError):
        pa.save_pathway_results(str(bad))


# ---------------------------------------------------------------------------
# run_pathway_analysis
# ---------------------------------------------------------------------------


def test_run_pathway_analysis_both(monkeypatch):
    mod = types.ModuleType("gseapy")
    mod.gsea = lambda **kw: Res2d(gsea_row_frame())
    mod.enrichr = lambda **kw: EnrichrRes(ora_row_frame())
    monkeypatch.setitem(sys.modules, "gseapy", mod)

    pa = PathwayAnalysis()
    results = pa.run_pathway_analysis(
        gene_list=["GENE0", "GENE1", "GENE2"],
        expression_data=make_expression(),
        labels=make_labels(),
        analysis_type="both",
        gene_sets=["KEGG"],
    )

    assert results["gene_list"] == ["GENE0", "GENE1", "GENE2"]
    assert results["analysis_type"] == "both"
    assert results["gene_sets"] == ["KEGG"]
    assert results["gsea_results"]["KEGG"]["status"] == "success"
    assert results["ora_results"]["KEGG"]["status"] == "success"
    assert results["summary"]["n_genes"] == 3
    assert "plots" in results
    assert pa.pathway_results is results


def test_run_pathway_analysis_default_gene_sets(monkeypatch):
    monkeypatch.setitem(sys.modules, "gseapy", None)
    pa = PathwayAnalysis()

    results = pa.run_pathway_analysis(gene_list=["A"], analysis_type="ora")

    assert results["gene_sets"] == ["KEGG", "REACTOME", "GO_BP"]
    assert results["ora_results"] == {"error": "gseapy not available"}
    assert results["gsea_results"] == {}


def test_run_pathway_analysis_ora_only_skips_gsea(monkeypatch):
    mod = types.ModuleType("gseapy")
    mod.enrichr = lambda **kw: EnrichrRes(ora_row_frame())
    monkeypatch.setitem(sys.modules, "gseapy", mod)

    pa = PathwayAnalysis()
    results = pa.run_pathway_analysis(
        gene_list=["A"],
        expression_data=make_expression(),
        labels=make_labels(),
        analysis_type="ora",
        gene_sets=["KEGG"],
    )

    assert results["gsea_results"] == {}
    assert results["ora_results"]["KEGG"]["status"] == "success"


def test_run_pathway_analysis_gsea_only(monkeypatch):
    mod = types.ModuleType("gseapy")
    mod.gsea = lambda **kw: Res2d(gsea_row_frame())
    monkeypatch.setitem(sys.modules, "gseapy", mod)

    pa = PathwayAnalysis()
    results = pa.run_pathway_analysis(
        gene_list=["A"],
        expression_data=make_expression(),
        labels=make_labels(),
        analysis_type="gsea",
        gene_sets=["KEGG"],
    )

    assert results["ora_results"] == {}
    assert results["gsea_results"]["KEGG"]["status"] == "success"


def test_run_pathway_analysis_gsea_requested_without_data(monkeypatch):
    monkeypatch.setitem(sys.modules, "gseapy", None)
    pa = PathwayAnalysis()

    results = pa.run_pathway_analysis(gene_list=["A"], analysis_type="gsea")
    assert results["gsea_results"] == {}
    assert results["ora_results"] == {}
    assert results["summary"]["analysis_type"] == "gsea"


def test_run_pathway_analysis_empty_gene_list(monkeypatch):
    monkeypatch.setitem(sys.modules, "gseapy", None)
    pa = PathwayAnalysis()

    results = pa.run_pathway_analysis(gene_list=[], analysis_type="ora")
    assert results["summary"]["n_genes"] == 0


def test_run_pathway_analysis_reraises(monkeypatch):
    monkeypatch.setitem(sys.modules, "gseapy", None)
    pa = PathwayAnalysis()

    def boom(_results):
        raise RuntimeError("summary exploded")

    monkeypatch.setattr(pa, "_generate_pathway_summary", boom)

    with pytest.raises(RuntimeError, match="summary exploded"):
        pa.run_pathway_analysis(gene_list=["A"], analysis_type="ora")


def test_run_pathway_analysis_then_accessors(monkeypatch):
    mod = types.ModuleType("gseapy")
    mod.enrichr = lambda **kw: EnrichrRes(ora_row_frame())
    monkeypatch.setitem(sys.modules, "gseapy", mod)

    pa = PathwayAnalysis()
    pa.run_pathway_analysis(
        gene_list=["GENE0"], analysis_type="ora", gene_sets=["KEGG"]
    )

    summary = pa.get_pathway_summary()
    assert summary["ora_summary"]["KEGG"]["n_significant"] == 1

    sig = pa.get_significant_pathways(method="ora")
    assert [p["pathway"] for p in sig] == ["Term A"]
