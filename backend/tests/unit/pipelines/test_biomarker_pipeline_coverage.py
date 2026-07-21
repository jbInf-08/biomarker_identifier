"""
Self-contained coverage tests for app.pipelines.biomarker_pipeline.

These tests deliberately avoid tests/conftest.py fixtures so they can be run
with --noconftest. All heavy pipeline components (DataIO, QualityControl,
Normalization, StatisticalPipeline, MLSelectionPipeline) are replaced with
mocks, so the tests exercise only the orchestration logic of
BiomarkerPipeline.
"""

import importlib.util
import json
import os
import sys
import types
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


def _install_statsmodels_stub() -> None:
    """Install a minimal statsmodels stub ONLY if the real package is absent.

    ``app.pipelines.stats`` transitively imports
    ``statsmodels.stats.multitest.multipletests``. statsmodels is not part of
    this environment's pinned deps, but it may be present in CI - in that case
    we leave the real package alone so CI exercises it.
    """
    if importlib.util.find_spec("statsmodels") is not None:
        return

    def multipletests(pvals, alpha=0.05, method="fdr_bh", **kwargs):
        pvals = np.asarray(pvals, dtype=float)
        adjusted = np.clip(pvals * max(len(pvals), 1), 0.0, 1.0)
        return adjusted <= alpha, adjusted, alpha, alpha

    statsmodels = types.ModuleType("statsmodels")
    stats_mod = types.ModuleType("statsmodels.stats")
    multitest = types.ModuleType("statsmodels.stats.multitest")
    multitest.multipletests = multipletests
    stats_mod.multitest = multitest
    statsmodels.stats = stats_mod
    sys.modules.setdefault("statsmodels", statsmodels)
    sys.modules.setdefault("statsmodels.stats", stats_mod)
    sys.modules.setdefault("statsmodels.stats.multitest", multitest)


_install_statsmodels_stub()

from app.pipelines.biomarker_pipeline import BiomarkerPipeline  # noqa: E402

MODULE = "app.pipelines.biomarker_pipeline"

N_GENES = 12
N_SAMPLES = 24


# ---------------------------------------------------------------------------
# Helpers to build small deterministic data / fake component payloads
# ---------------------------------------------------------------------------


class FrameLike:
    """Thin stand-in for the expression/normalized DataFrame.

    ``BiomarkerPipeline`` only ever uses ``.shape`` and ``.to_csv`` on these
    frames (every other consumer is a mocked component), so a wrapper is
    sufficient. It also gives a cheap ``__repr__``: ``_save_pipeline_results``
    serialises the whole results dict with ``json.dump(..., default=str)``,
    which calls ``str()`` on the frame, and pandas' own DataFrame repr blows up
    in this environment when coverage tracing is active (numpy ends up
    imported twice, breaking its ``_NoValue`` sentinel).
    """

    def __init__(self, df: pd.DataFrame):
        self._df = df

    @property
    def shape(self):
        return self._df.shape

    def to_csv(self, *args, **kwargs):
        return self._df.to_csv(*args, **kwargs)

    def __repr__(self):
        return f"<FrameLike shape={self._df.shape}>"


def make_expression(n_genes: int = N_GENES, n_samples: int = N_SAMPLES) -> FrameLike:
    rng = np.random.default_rng(0)
    return FrameLike(
        pd.DataFrame(
            rng.normal(size=(n_genes, n_samples)),
            index=[f"GENE{i}" for i in range(n_genes)],
            columns=[f"S{j}" for j in range(n_samples)],
        )
    )


def make_labels(n_samples: int = N_SAMPLES) -> pd.Series:
    return pd.Series(
        ["A" if j % 2 == 0 else "B" for j in range(n_samples)],
        index=[f"S{j}" for j in range(n_samples)],
        name="label",
    )


def make_stats_results():
    return {
        "method_results": {
            "ttest": {
                "significant_features_adjusted": ["GENE0", "GENE1"],
                "significant_features": ["GENE0", "GENE1", "GENE2"],
            },
            "mannwhitney": {"significant_features": ["GENE1", "GENE3"]},
            "nothing": {},
            "broken": {"error": "boom"},
        },
        "summary": {
            "total_significant_features": 4,
            "methods_applied": ["ttest", "mannwhitney"],
        },
    }


def make_ml_results():
    return {
        "consensus_features": {
            "consensus_features": [
                {
                    "feature": "GENE1",
                    "consensus_score": 0.9,
                    "selection_count": 3,
                    "methods": ["lasso", "rf"],
                },
                {
                    "feature": "GENE5",
                    "consensus_score": 0.5,
                    "selection_count": 1,
                    "methods": ["rf"],
                },
            ],
            "consensus_scores": {"GENE1": 0.9, "GENE5": 0.5, "GENE7": 0.3},
        },
        "summary": {
            "consensus_features_count": 2,
            "methods_applied": ["lasso", "rf"],
            "evaluation_summary": {
                "logreg": {"roc_auc": 0.81},
                "rf": {"roc_auc": 0.93},
                "bad": {"roc_auc": "not-a-number"},
                "not_a_dict": 7,
            },
        },
    }


def build_pipeline(config=None):
    """Create a BiomarkerPipeline whose 5 components are MagicMocks."""
    with patch(f"{MODULE}.DataIO"), patch(f"{MODULE}.QualityControl"), patch(
        f"{MODULE}.Normalization"
    ), patch(f"{MODULE}.StatisticalPipeline"), patch(f"{MODULE}.MLSelectionPipeline"):
        pipeline = BiomarkerPipeline(config)
    return pipeline


def wire_components(pipeline, validation_status="passed", metadata=None):
    """Give the mocked components realistic return values."""
    expression = make_expression()
    labels = make_labels()

    pipeline.data_io.load_data.return_value = {
        "expression_data": expression,
        "labels": labels,
        "metadata": {} if metadata is None else metadata,
        "validation_results": {"status": validation_status},
    }
    pipeline.qc.perform_qc_analysis.return_value = {
        "summary": {
            "status": "passed",
            "warnings": ["w1"],
            "recommendations": ["r1", "r2"],
        }
    }
    pipeline.qc.filter_data.return_value = (expression, {"n_removed": 0})
    pipeline.normalizer.normalize_data.return_value = {"final_data": expression}
    pipeline.stats_pipeline.run_statistical_analysis.return_value = make_stats_results()
    pipeline.ml_pipeline.run_ml_selection.return_value = make_ml_results()
    return pipeline


@pytest.fixture
def pipeline():
    return wire_components(build_pipeline({"some": "config"}))


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


def test_init_defaults_to_empty_config():
    p = build_pipeline()
    assert p.config == {}
    assert p.pipeline_results == {}
    assert p.run_id is None


def test_init_keeps_supplied_config_and_builds_components():
    cfg = {"a": 1}
    with patch(f"{MODULE}.DataIO") as data_io, patch(
        f"{MODULE}.QualityControl"
    ) as qc, patch(f"{MODULE}.Normalization") as norm, patch(
        f"{MODULE}.StatisticalPipeline"
    ) as stats, patch(
        f"{MODULE}.MLSelectionPipeline"
    ) as ml:
        p = BiomarkerPipeline(cfg)

    assert p.config is cfg
    for component in (data_io, qc, norm, stats, ml):
        component.assert_called_once_with(cfg)


# ---------------------------------------------------------------------------
# _generate_run_id
# ---------------------------------------------------------------------------


def test_generate_run_id_without_name():
    p = build_pipeline()
    run_id = p._generate_run_id()
    assert run_id.startswith("biomarker_run_")
    assert len(run_id.split("biomarker_run_")[1]) == 15


def test_generate_run_id_sanitises_name():
    p = build_pipeline()
    run_id = p._generate_run_id("My Run!! #1 ")
    # '!' and '#' dropped, spaces -> underscores, trailing space stripped
    assert run_id.startswith("My_Run_1")
    assert "!" not in run_id and "#" not in run_id


def test_generate_run_id_all_illegal_characters_yields_timestamp_only():
    p = build_pipeline()
    run_id = p._generate_run_id("@@@")
    assert run_id.startswith("_")


# ---------------------------------------------------------------------------
# _generate_biomarker_list
# ---------------------------------------------------------------------------


def test_generate_biomarker_list_combines_stats_and_ml():
    p = build_pipeline()
    result = p._generate_biomarker_list(make_stats_results(), make_ml_results())

    genes = {b["gene"] for b in result["biomarkers"]}
    # union of DE hits plus consensus feature list entries
    assert genes == {"GENE0", "GENE1", "GENE3", "GENE5"}

    summary = result["summary"]
    assert summary["total_biomarkers"] == 4
    assert set(summary) == {
        "total_biomarkers",
        "statistically_significant",
        "ml_selected",
        "high_confidence",
    }

    # ranks are 1..n in descending final_score order
    ranks = [b["final_rank"] for b in result["biomarkers"]]
    assert ranks == list(range(1, len(ranks) + 1))
    scores = [b["final_score"] for b in result["biomarkers"]]
    assert scores == sorted(scores, reverse=True)

    by_gene = {b["gene"]: b for b in result["biomarkers"]}
    # GENE1 significant in both methods and ML selected -> top score
    assert by_gene["GENE1"]["final_rank"] == 1
    assert by_gene["GENE1"]["consensus_score"] == pytest.approx(0.9)
    assert by_gene["GENE1"]["ml_evidence"]["selection_count"] == 3
    # 'broken' method had an error and is excluded from statistical evidence
    assert "broken" not in by_gene["GENE1"]["statistical_evidence"]
    # method with neither key contributes an empty significant list
    assert by_gene["GENE1"]["statistical_evidence"]["nothing"] is False
    # 0.6 * (2/3) + 0.4 * 0.9
    assert by_gene["GENE1"]["final_score"] == pytest.approx(0.6 * (2 / 3) + 0.4 * 0.9)

    # GENE0 has no ML evidence at all
    assert by_gene["GENE0"]["ml_evidence"] == {}
    assert by_gene["GENE0"]["consensus_score"] == 0.0


def test_generate_biomarker_list_ranked_fallback_when_nothing_significant():
    stats_results = {"method_results": {}}
    ml_results = {
        "consensus_features": {
            "consensus_features": [],
            "consensus_scores": {"G1": 0.9, "G2": 0.8, "G3": 0.1},
        }
    }
    p = build_pipeline()
    result = p._generate_biomarker_list(
        stats_results, ml_results, biomarker_fallback_top_k=2
    )

    genes = [b["gene"] for b in result["biomarkers"]]
    assert set(genes) == {"G1", "G2"}
    for b in result["biomarkers"]:
        assert b["ml_evidence"]["methods"] == ["ranked_fallback"]
        assert b["ml_evidence"]["selection_count"] == 0
        assert b["statistical_evidence"] == {}
    # no statistical evidence -> final_score is purely 0.4 * consensus
    assert result["biomarkers"][0]["final_score"] == pytest.approx(0.4 * 0.9)
    assert result["summary"]["statistically_significant"] == 0
    assert result["summary"]["ml_selected"] == 2
    assert result["summary"]["high_confidence"] == 0


def test_generate_biomarker_list_truncates_when_de_union_empty_but_consensus_large():
    # method present, no error, but zero significant features -> de_union empty
    stats_results = {"method_results": {"ttest": {"significant_features": []}}}
    consensus_features = [
        {
            "feature": f"G{i}",
            "consensus_score": 1.0 - i / 100.0,
            "selection_count": 1,
            "methods": ["rf"],
        }
        for i in range(5)
    ]
    ml_results = {
        "consensus_features": {
            "consensus_features": consensus_features,
            "consensus_scores": {f"G{i}": 1.0 - i / 100.0 for i in range(5)},
        }
    }
    p = build_pipeline()
    result = p._generate_biomarker_list(
        stats_results, ml_results, biomarker_fallback_top_k=2
    )
    assert {b["gene"] for b in result["biomarkers"]} == {"G0", "G1"}
    # the truncated set still resolves ML evidence from consensus_features
    assert result["biomarkers"][0]["ml_evidence"]["methods"] == ["rf"]


def test_generate_biomarker_list_empty_inputs():
    p = build_pipeline()
    result = p._generate_biomarker_list({}, {})
    assert result["biomarkers"] == []
    assert result["summary"]["total_biomarkers"] == 0
    assert result["summary"]["high_confidence"] == 0


def test_generate_biomarker_list_handles_none_consensus_block():
    stats_results = {"method_results": {"ttest": {"significant_features": ["GENE0"]}}}
    ml_results = {"consensus_features": None}
    p = build_pipeline()
    result = p._generate_biomarker_list(stats_results, ml_results)
    assert [b["gene"] for b in result["biomarkers"]] == ["GENE0"]
    assert result["biomarkers"][0]["consensus_score"] == 0.0
    assert result["summary"]["ml_selected"] == 0
    # final_score is 0.6 * 1.0 = 0.6, which is NOT above the 0.7 threshold
    assert result["biomarkers"][0]["final_score"] == pytest.approx(0.6)
    assert result["summary"]["high_confidence"] == 0


# ---------------------------------------------------------------------------
# _generate_pipeline_summary
# ---------------------------------------------------------------------------


def test_generate_pipeline_summary_full():
    p = build_pipeline()
    results = {
        "run_id": "rid",
        "run_name": "rname",
        "timestamp": "2024-01-01T00:00:00",
        "pipeline_steps": ["data_loading"],
        "data_loading": {
            "expression_data": make_expression(),
            "labels": make_labels(),
            "validation_results": {"status": "passed"},
        },
        "biomarker_list": {"summary": {"total_biomarkers": 3}},
        "quality_control": {
            "summary": {
                "status": "passed",
                "warnings": ["a", "b"],
                "recommendations": ["c"],
            }
        },
        "statistical_analysis": {
            "summary": {
                "total_significant_features": 5,
                "methods_applied": ["ttest"],
            }
        },
        "ml_selection": {
            "summary": {
                "consensus_features_count": 2,
                "methods_applied": ["rf"],
                "evaluation_summary": {
                    "a": {"roc_auc": 0.7},
                    "b": {"roc_auc": 0.85},
                    "c": {"roc_auc": None},
                    "d": "scalar",
                },
            }
        },
    }
    summary = p._generate_pipeline_summary(results)

    assert summary["data_summary"] == {
        "n_genes": N_GENES,
        "n_samples": N_SAMPLES,
        "n_classes": 2,
        "validation_status": "passed",
    }
    assert summary["results_summary"] == {"total_biomarkers": 3}
    steps = summary["step_summaries"]
    assert steps["quality_control"] == {
        "status": "passed",
        "n_warnings": 2,
        "n_recommendations": 1,
    }
    assert steps["statistical_analysis"] == {
        "n_significant_features": 5,
        "methods_applied": ["ttest"],
    }
    assert steps["ml_selection"]["best_cv_roc_auc_mean"] == pytest.approx(0.85)
    assert steps["ml_selection"]["consensus_features_count"] == 2


def test_generate_pipeline_summary_minimal_and_missing_sections():
    p = build_pipeline()
    results = {
        "run_id": "rid",
        "timestamp": "ts",
        "pipeline_steps": [],
    }
    summary = p._generate_pipeline_summary(results)
    assert summary["run_name"] is None
    assert summary["data_summary"] == {}
    assert summary["results_summary"] == {}
    assert summary["step_summaries"] == {}


def test_generate_pipeline_summary_ml_without_evaluation_summary():
    p = build_pipeline()
    results = {
        "run_id": "rid",
        "timestamp": "ts",
        "pipeline_steps": [],
        "quality_control": {},
        "statistical_analysis": {},
        "ml_selection": {},
    }
    summary = p._generate_pipeline_summary(results)
    steps = summary["step_summaries"]
    assert steps["quality_control"]["status"] == "unknown"
    assert steps["quality_control"]["n_warnings"] == 0
    assert steps["statistical_analysis"]["n_significant_features"] == 0
    assert steps["ml_selection"]["best_cv_roc_auc_mean"] is None
    assert steps["ml_selection"]["methods_applied"] == []


# ---------------------------------------------------------------------------
# _save_pipeline_results
# ---------------------------------------------------------------------------


def test_save_pipeline_results_writes_all_artifacts(tmp_path):
    p = build_pipeline()
    expression = make_expression()
    results = {
        "run_id": "rid",
        "pipeline_summary": {"run_id": "rid"},
        "biomarker_list": {
            "biomarkers": [{"gene": "GENE0", "final_score": 0.5}],
            "summary": {},
        },
        "normalization": {"final_data": expression},
        "quality_control": {"summary": {}},
        "statistical_analysis": {"summary": {}},
        "ml_selection": {"summary": {}},
        "when": pd.Timestamp("2024-01-01"),
    }
    out = str(tmp_path)
    p._save_pipeline_results(results, out)

    for name in (
        "pipeline_results.json",
        "biomarker_list.csv",
        "normalized_data.tsv",
        "pipeline_summary.json",
    ):
        assert os.path.exists(os.path.join(out, name))

    with open(os.path.join(out, "pipeline_results.json")) as f:
        payload = json.load(f)
    assert payload["run_id"] == "rid"

    p.qc.save_qc_report.assert_called_once()
    p.normalizer.save_normalization_report.assert_called_once()
    p.stats_pipeline.save_analysis_results.assert_called_once()
    p.ml_pipeline.save_selection_results.assert_called_once()


def test_save_pipeline_results_skips_optional_sections_and_empty_biomarkers(tmp_path):
    p = build_pipeline()
    results = {
        "run_id": "rid",
        "pipeline_summary": {},
        "biomarker_list": {"biomarkers": [], "summary": {}},
    }
    out = str(tmp_path)
    p._save_pipeline_results(results, out)

    assert not os.path.exists(os.path.join(out, "biomarker_list.csv"))
    assert not os.path.exists(os.path.join(out, "normalized_data.tsv"))
    p.qc.save_qc_report.assert_not_called()
    p.ml_pipeline.save_selection_results.assert_not_called()


def test_save_pipeline_results_reraises_on_failure(tmp_path):
    p = build_pipeline()
    results = {"run_id": "rid", "pipeline_summary": {}}
    missing_dir = str(tmp_path / "does_not_exist")
    with pytest.raises(OSError):
        p._save_pipeline_results(results, missing_dir)


# ---------------------------------------------------------------------------
# get_biomarker_list / get_pipeline_summary
# ---------------------------------------------------------------------------


def test_get_biomarker_list_empty_when_no_run():
    p = build_pipeline()
    assert p.get_biomarker_list() == []


def test_get_biomarker_list_empty_when_key_missing():
    p = build_pipeline()
    p.pipeline_results = {"run_id": "rid"}
    assert p.get_biomarker_list() == []


def test_get_biomarker_list_respects_top_n():
    p = build_pipeline()
    biomarkers = [{"gene": f"G{i}"} for i in range(10)]
    p.pipeline_results = {"biomarker_list": {"biomarkers": biomarkers}}
    assert p.get_biomarker_list(top_n=3) == biomarkers[:3]
    assert len(p.get_biomarker_list()) == 10


def test_get_pipeline_summary_no_run():
    p = build_pipeline()
    assert p.get_pipeline_summary() == {"status": "No pipeline run performed"}


def test_get_pipeline_summary_returns_stored_summary():
    p = build_pipeline()
    p.pipeline_results = {"pipeline_summary": {"run_id": "rid"}}
    assert p.get_pipeline_summary() == {"run_id": "rid"}


def test_get_pipeline_summary_fallback_shape():
    p = build_pipeline()
    p.pipeline_results = {"run_id": "rid", "run_name": "n", "pipeline_steps": ["a"]}
    summary = p.get_pipeline_summary()
    assert summary == {
        "run_id": "rid",
        "run_name": "n",
        "pipeline_steps": ["a"],
        "status": "completed",
    }


# ---------------------------------------------------------------------------
# config load/save
# ---------------------------------------------------------------------------


def test_save_and_load_config_roundtrip(tmp_path):
    p = build_pipeline({"alpha": 0.05, "methods": ["ttest"]})
    cfg_file = str(tmp_path / "config.yaml")
    p.save_config_to_file(cfg_file)
    assert os.path.exists(cfg_file)

    other = build_pipeline()
    other.load_config_from_file(cfg_file)
    assert other.config == {"alpha": 0.05, "methods": ["ttest"]}


def test_load_config_missing_file_raises(tmp_path):
    p = build_pipeline()
    with pytest.raises(OSError):
        p.load_config_from_file(str(tmp_path / "nope.yaml"))


def test_save_config_to_unwritable_path_raises(tmp_path):
    p = build_pipeline()
    with pytest.raises(OSError):
        p.save_config_to_file(str(tmp_path / "missing_dir" / "config.yaml"))


def test_load_config_with_invalid_yaml_raises(tmp_path):
    p = build_pipeline()
    bad = tmp_path / "bad.yaml"
    bad.write_text("a: [1, 2\n  b: }")
    with pytest.raises(Exception):
        p.load_config_from_file(str(bad))


# ---------------------------------------------------------------------------
# run_pipeline
# ---------------------------------------------------------------------------


def test_run_pipeline_happy_path(pipeline, tmp_path):
    results = pipeline.run_pipeline(
        expression_file="expr.tsv",
        labels_file="labels.tsv",
        metadata_file=None,
        output_dir=str(tmp_path),
        run_name="unit test run",
    )

    assert results["run_id"].startswith("unit_test_run_")
    assert results["run_name"] == "unit test run"
    assert results["pipeline_steps"] == [
        "data_loading",
        "quality_control",
        "data_filtering",
        "normalization",
        "statistical_analysis",
        "ml_selection",
        "biomarker_list",
    ]
    assert results["data_filtering"]["filtered_data_shape"] == (N_GENES, N_SAMPLES)
    assert "pipeline_summary" in results
    assert pipeline.pipeline_results is results
    assert pipeline.run_id == results["run_id"]

    run_dir = tmp_path / results["run_id"]
    assert (run_dir / "pipeline_results.json").exists()
    assert (run_dir / "pipeline_summary.json").exists()

    # top biomarkers available through the accessor after a run
    assert len(pipeline.get_biomarker_list(top_n=2)) == 2
    assert pipeline.get_pipeline_summary()["run_id"] == results["run_id"]


def test_run_pipeline_raises_on_failed_validation(tmp_path):
    p = wire_components(build_pipeline(), validation_status="failed")
    p.data_io.load_data.return_value["validation_results"] = {
        "status": "failed",
        "errors": ["bad shape"],
        "warnings": ["odd values"],
    }
    with pytest.raises(ValueError) as exc:
        p.run_pipeline("e.tsv", "l.tsv", output_dir=str(tmp_path))
    message = str(exc.value)
    assert "Data validation failed" in message
    assert "bad shape" in message
    assert "odd values" in message
    p.qc.perform_qc_analysis.assert_not_called()


def test_run_pipeline_failed_validation_without_details(tmp_path):
    p = wire_components(build_pipeline())
    p.data_io.load_data.return_value["validation_results"] = {"status": "failed"}
    with pytest.raises(ValueError) as exc:
        p.run_pipeline("e.tsv", "l.tsv", output_dir=str(tmp_path))
    assert "Errors:" not in str(exc.value)


def test_run_pipeline_propagates_component_exception(tmp_path):
    p = wire_components(build_pipeline())
    p.stats_pipeline.run_statistical_analysis.side_effect = RuntimeError(
        "stats blew up"
    )
    with pytest.raises(RuntimeError, match="stats blew up"):
        p.run_pipeline("e.tsv", "l.tsv", output_dir=str(tmp_path))


def test_run_pipeline_uses_batch_info_from_metadata(tmp_path):
    batch_info = pd.Series(["b1"] * N_SAMPLES, index=make_labels().index)
    p = wire_components(build_pipeline(), metadata={"batch_info": batch_info})
    p.run_pipeline(
        "e.tsv",
        "l.tsv",
        output_dir=str(tmp_path),
        normalization_method="quantile",
        batch_correction="combat",
    )
    call = p.normalizer.normalize_data.call_args
    assert call.args[2] is batch_info
    assert call.args[3] == "quantile"
    assert call.args[4] == "combat"


def test_run_pipeline_forwards_kwargs_to_components(tmp_path):
    p = wire_components(build_pipeline())
    p.run_pipeline(
        "e.tsv",
        "l.tsv",
        output_dir=str(tmp_path),
        min_detection_rate=0.42,
        min_variance=0.11,
        max_missing_ratio=0.33,
        stats_methods=["ttest"],
        alpha=0.01,
        selection_methods=["rf"],
        n_features=7,
        stability_bootstraps=3,
    )

    filter_kwargs = p.qc.filter_data.call_args.kwargs
    assert filter_kwargs["min_detection_rate"] == pytest.approx(0.42)
    assert filter_kwargs["min_variance"] == pytest.approx(0.11)
    assert filter_kwargs["max_missing_ratio"] == pytest.approx(0.33)

    stats_args = p.stats_pipeline.run_statistical_analysis.call_args.args
    assert stats_args[2] == ["ttest"]
    assert stats_args[3] == pytest.approx(0.01)

    ml_args = p.ml_pipeline.run_ml_selection.call_args.args
    assert ml_args[2] == ["rf"]
    assert ml_args[3] == 7
    assert ml_args[4] == 3


def test_run_pipeline_defaults_when_no_kwargs(tmp_path):
    p = wire_components(build_pipeline())
    p.run_pipeline("e.tsv", "l.tsv", output_dir=str(tmp_path))

    # normalization defaults: log2 method, batch correction disabled
    call = p.normalizer.normalize_data.call_args
    assert call.args[2] is None
    assert call.args[3] == "log2"
    assert call.args[4] is None

    stats_args = p.stats_pipeline.run_statistical_analysis.call_args.args
    assert stats_args[2] is None
    assert stats_args[3] == pytest.approx(0.05)

    ml_args = p.ml_pipeline.run_ml_selection.call_args.args
    assert ml_args[3] == 100
    assert ml_args[4] == 100


def test_run_pipeline_single_sample_edge_case(tmp_path):
    p = build_pipeline()
    expression = make_expression(n_genes=3, n_samples=1)
    labels = pd.Series(["A"], index=["S0"], name="label")
    p.data_io.load_data.return_value = {
        "expression_data": expression,
        "labels": labels,
        "validation_results": {"status": "passed"},
    }
    p.qc.perform_qc_analysis.return_value = {}
    p.qc.filter_data.return_value = (expression, {})
    p.normalizer.normalize_data.return_value = {"final_data": expression}
    p.stats_pipeline.run_statistical_analysis.return_value = {"method_results": {}}
    p.ml_pipeline.run_ml_selection.return_value = {}

    results = p.run_pipeline("e.tsv", "l.tsv", output_dir=str(tmp_path))
    assert results["biomarker_list"]["biomarkers"] == []
    assert results["pipeline_summary"]["data_summary"]["n_classes"] == 1
    assert results["pipeline_summary"]["data_summary"]["n_samples"] == 1


def test_run_pipeline_missing_metadata_key(tmp_path):
    """metadata absent from load_data payload -> .get default kicks in."""
    p = wire_components(build_pipeline())
    del p.data_io.load_data.return_value["metadata"]
    results = p.run_pipeline("e.tsv", "l.tsv", output_dir=str(tmp_path))
    assert p.normalizer.normalize_data.call_args.args[2] is None
    assert results["run_id"].startswith("biomarker_run_")
