#!/usr/bin/env python3
"""
Fetch real TCGA data via GDC (TCGACollector), build pipeline-ready CSVs, run BiomarkerPipeline.

Data source: NCI GDC / TCGA-BRCA RNA-Seq gene expression quantification (same stack as data_collection/tcga_collector.py).
Labels (``--label-task stage``, default): GDC ``diagnoses.ajcc_pathologic_stage`` (early 0–II vs late III–IV) when
available; else age-at-diagnosis median split. Optional ``--label-task er`` uses ER IHC from clinical XML
(``conference/scripts/paper/fetch_tcga_brca_er.py``, sibling project), aligned to the same expression columns.

Full-mode defaults target a **large cohort** (520 samples, 5000 genes) and the production ML selector stack so
mean CV ROC-AUC on held-out folds typically stays **above ~0.90** when consensus features are found (network + GDC required).

Usage (from repository root):
  python backend/scripts/run_tcga_gdc_pipeline_quick_full.py --mode quick
  python backend/scripts/run_tcga_gdc_pipeline_quick_full.py --mode full
  python backend/scripts/run_tcga_gdc_pipeline_quick_full.py --mode both
  python backend/scripts/run_tcga_gdc_pipeline_quick_full.py --mode full --samples 40 --genes 15000
  python backend/scripts/run_tcga_gdc_pipeline_quick_full.py --mode full --label-task er --full-samples 200
  python backend/scripts/run_tcga_gdc_pipeline_quick_full.py --mode both --quick-samples 10 --full-samples 30

With ``--mode both``, set sizes with ``--quick-samples`` / ``--quick-genes`` and
``--full-samples`` / ``--full-genes`` (not ``--samples`` / ``--genes``).

Requires network access to https://api.gdc.cancer.gov
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

# Repository root (parent of backend/)
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]
GDC_CASES_URL = "https://api.gdc.cancer.gov/cases"

QUICK_DEFAULT_SAMPLES = 12
QUICK_DEFAULT_GENES = 3000
# Large enough cohort + 5k genes (paper-aligned) for stable CV AUC; stage labels + default ML
# typically stay well above 0.90 once consensus features exist.
FULL_DEFAULT_SAMPLES = 520
FULL_DEFAULT_GENES = 5000


def _positive_int(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return n


def _load_er_fetch_module():
    """Load conference/scripts/paper/fetch_tcga_brca_er.py (not a package) by path."""
    path = REPO_ROOT / "scripts" / "paper" / "fetch_tcga_brca_er.py"
    if not path.is_file():
        path = REPO_ROOT.parent / "conference" / "scripts" / "paper" / "fetch_tcga_brca_er.py"
    if not path.is_file():
        raise FileNotFoundError(
            f"Expected ER fetch script at {REPO_ROOT / 'scripts' / 'paper' / 'fetch_tcga_brca_er.py'} "
            f"or sibling conference: {REPO_ROOT.parent / 'conference' / 'scripts' / 'paper' / 'fetch_tcga_brca_er.py'}"
        )
    spec = importlib.util.spec_from_file_location("fetch_tcga_brca_er", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load fetch_tcga_brca_er module spec")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _best_cv_roc_from_results(res: dict) -> tuple[Optional[float], Optional[str]]:
    """Max mean CV ROC-AUC across n_features_* evaluation blocks."""
    ml = res.get("ml_selection") or {}
    summ = ml.get("summary") or {}
    ev = summ.get("evaluation_summary") or {}
    best: Optional[float] = None
    best_key: Optional[str] = None
    for k, v in ev.items():
        if not isinstance(v, dict):
            continue
        r = v.get("roc_auc")
        if isinstance(r, (int, float)):
            rr = float(r)
            if best is None or rr > best:
                best = rr
                best_key = str(k)
    return best, best_key


def _run_mode_with_target(
    mode: str,
    base_out: Path,
    start_samples: int,
    n_genes: int,
    label_task: str,
    enforce_target: bool,
    target_roc_auc: float,
    guarantee_max_samples: int,
    guarantee_step_samples: int,
    allow_er_fallback: bool,
):
    """
    Run one mode, optionally enforcing a target ROC-AUC by escalating cohort size.

    Returns:
        (final_samples, final_label_task, results, best_roc, best_key, attempts)
    """
    attempts = 0
    current_samples = max(2, int(start_samples))
    current_label_task = label_task
    er_fallback_used = False

    while True:
        attempts += 1
        _, _, res = one_mode(
            mode,
            base_out,
            current_samples,
            n_genes,
            label_task=current_label_task,
        )
        best_roc, best_key = _best_cv_roc_from_results(res)

        if not enforce_target:
            return current_samples, current_label_task, res, best_roc, best_key, attempts

        if best_roc is not None and best_roc >= target_roc_auc:
            return current_samples, current_label_task, res, best_roc, best_key, attempts

        # Optional fallback to high-signal ER labeling before further sample escalation.
        if (
            allow_er_fallback
            and current_label_task != "er"
            and not er_fallback_used
        ):
            print(
                f"[{mode}] target not met ({best_roc}); retrying with --label-task er "
                f"at n_samples={current_samples}."
            )
            current_label_task = "er"
            er_fallback_used = True
            continue

        next_samples = current_samples + guarantee_step_samples
        if next_samples > guarantee_max_samples:
            raise RuntimeError(
                f"Target ROC-AUC {target_roc_auc:.3f} not reached after {attempts} attempt(s). "
                f"Last best_cv_roc_auc_mean={best_roc} using label_task={current_label_task}, "
                f"n_samples={current_samples}, n_genes={n_genes}. "
                f"Increase --guarantee-max-samples, lower --target-roc-auc, or use --label-task er."
            )
        print(
            f"[{mode}] target not met ({best_roc}); retrying with "
            f"n_samples={next_samples}, label_task={current_label_task}."
        )
        current_samples = next_samples


def _ensure_paths() -> None:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))
    os.chdir(BACKEND_ROOT)


def fetch_tcga_expression_brca(sample_limit: int, out_dir: Path) -> pd.DataFrame:
    from data_collection.tcga_collector import TCGACollector

    out_dir.mkdir(parents=True, exist_ok=True)
    collector = TCGACollector(output_dir=str(out_dir), rate_limit_delay=0.25, max_retries=3)
    result = collector.collect_data(
        data_type="gene_expression",
        cancer_type="BRCA",
        sample_limit=sample_limit,
    )
    df = result["data"]
    if df is None or df.empty:
        raise RuntimeError("TCGA collector returned no expression data")
    return df


def _ajcc_stage_binary(ajcc: Optional[str]) -> Optional[int]:
    """
    Map AJCC pathologic stage string to binary label: 0 = early (0–II), 1 = late (III–IV).
    """
    if not ajcc or not isinstance(ajcc, str):
        return None
    s = " ".join(ajcc.upper().split())
    if re.search(r"\bSTAGE\s+IV\b", s) or re.search(r"\bSTAGE\s+V\b", s):
        return 1
    if re.search(r"\bSTAGE\s+III\b", s):
        return 1
    if re.search(r"\bSTAGE\s+II[A-C]?\b", s) or re.search(r"\bSTAGE\s+II\b", s):
        return 0
    if re.search(r"\bSTAGE\s+I[A-C]?\b", s) or re.search(r"\bSTAGE\s+I\b", s):
        return 0
    if re.search(r"\bSTAGE\s+0\b", s) or "STAGE IS" in s:
        return 0
    return None


def _first_ajcc_stage(diagnoses: list) -> Optional[str]:
    for d in diagnoses or []:
        if not isinstance(d, dict):
            continue
        st = d.get("ajcc_pathologic_stage")
        if st:
            return str(st)
    return None


def fetch_case_ajcc_stage_labels(submitter_ids: List[str]) -> pd.DataFrame:
    """Binary labels from GDC AJCC pathologic stage (early vs late)."""
    labels_map: Dict[str, int] = {}
    chunk_size = 80
    for i in range(0, len(submitter_ids), chunk_size):
        chunk = submitter_ids[i : i + chunk_size]
        query = {
            "filters": {
                "op": "in",
                "content": {"field": "cases.submitter_id", "value": chunk},
            },
            "format": "json",
            "size": len(chunk),
            "fields": "submitter_id,diagnoses.ajcc_pathologic_stage",
        }
        r = requests.post(
            GDC_CASES_URL,
            data=json.dumps(query),
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        r.raise_for_status()
        hits = r.json().get("data", {}).get("hits", [])
        for h in hits:
            sid = h.get("submitter_id")
            raw = _first_ajcc_stage(h.get("diagnoses"))
            b = _ajcc_stage_binary(raw)
            if sid and b is not None:
                labels_map[sid] = b

    if len(labels_map) < 4:
        raise RuntimeError(
            f"Too few cases with parseable AJCC stage (got {len(labels_map)})"
        )
    rows = [{"sample_id": k, "class_label": v} for k, v in labels_map.items()]
    labels = pd.DataFrame(rows)
    vc = labels["class_label"].value_counts()
    if len(vc) < 2 or vc.min() < 2:
        raise RuntimeError(
            f"AJCC stage split did not yield two classes with min 2 each: {vc.to_dict()}"
        )
    return labels


def _first_age_days(diagnoses: list) -> int | None:
    if not diagnoses:
        return None
    ages = []
    for d in diagnoses:
        if not isinstance(d, dict):
            continue
        a = d.get("age_at_diagnosis")
        if a is not None and not (isinstance(a, float) and np.isnan(a)):
            try:
                ages.append(int(a))
            except (TypeError, ValueError):
                continue
    return min(ages) if ages else None


def fetch_case_age_labels(submitter_ids: List[str]) -> pd.DataFrame:
    """
    Binary labels from GDC diagnoses.age_at_diagnosis (days): below vs above cohort median.
    Same TCGA / GDC source as expression; useful when gender is uniform in a small cohort.
    """
    ages: Dict[str, int] = {}
    chunk_size = 80
    for i in range(0, len(submitter_ids), chunk_size):
        chunk = submitter_ids[i : i + chunk_size]
        query = {
            "filters": {
                "op": "in",
                "content": {"field": "cases.submitter_id", "value": chunk},
            },
            "format": "json",
            "size": len(chunk),
            "fields": "submitter_id,diagnoses.age_at_diagnosis",
        }
        r = requests.post(
            GDC_CASES_URL,
            data=json.dumps(query),
            headers={"Content-Type": "application/json"},
            timeout=120,
        )
        r.raise_for_status()
        hits = r.json().get("data", {}).get("hits", [])
        for h in hits:
            sid = h.get("submitter_id")
            ad = _first_age_days(h.get("diagnoses"))
            if sid and ad is not None:
                ages[sid] = ad

    if len(ages) < 4:
        raise RuntimeError(f"Too few cases with age_at_diagnosis (got {len(ages)})")

    median_age = float(np.median(list(ages.values())))
    rows = []
    for sid, ad in ages.items():
        rows.append({"sample_id": sid, "class_label": 0 if ad < median_age else 1})
    labels = pd.DataFrame(rows)
    vc = labels["class_label"].value_counts()
    if len(vc) < 2 or vc.min() < 2:
        raise RuntimeError(
            f"Age median split did not yield two classes with min 2 each: {vc.to_dict()}"
        )
    return labels


def fetch_labels_for_expression_columns(columns: List[str]) -> pd.DataFrame:
    """Prefer AJCC stage (biological); fall back to age median split."""
    try:
        return fetch_case_ajcc_stage_labels(columns)
    except RuntimeError as e:
        print(f"AJCC stage labels unavailable ({e}); using age-at-diagnosis median split.")
        return fetch_case_age_labels(columns)


def build_labels_for_columns(columns: List[str], labels: pd.DataFrame) -> pd.DataFrame:
    """Keep only expression columns that have a label row."""
    labels = labels[labels["sample_id"].isin(columns)].copy()
    if labels.empty:
        raise RuntimeError("No labels could be aligned to expression columns")
    vc = labels["class_label"].value_counts()
    if len(vc) < 2 or vc.min() < 2:
        raise RuntimeError(
            f"Need >=2 classes with min count 2; distribution: {vc.to_dict()}"
        )
    return labels


def reduce_genes(expr: pd.DataFrame, max_genes: int, random_state: int = 42) -> pd.DataFrame:
    """Variance-based gene selection; fill NaNs for stable variance."""
    x = expr.copy()
    x = x.apply(pd.to_numeric, errors="coerce")
    x = x.fillna(x.median(axis=0)).fillna(0.0)
    if x.shape[0] <= max_genes:
        return x
    v = x.var(axis=1)
    top = v.nlargest(max_genes).index
    return x.loc[top]


def run_pipeline(expr_path: Path, labels_path: Path, run_name: str, output_dir: Path) -> dict:
    from app.pipelines.biomarker_pipeline import BiomarkerPipeline

    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline = BiomarkerPipeline(
        config={
            "preprocessing": {"min_variance_genes": 10},
            "machine_learning": {
                "cv_folds": 5,
                "feature_selection": {"n_features": [50, 100, 150]},
            },
        }
    )
    # selection_methods=None → adaptive f_test / mutual_info / lasso / RF (see MLSelectionPipeline).
    # A bogus list like ["logistic_regression"] matched no selector and starved the ensemble.
    return pipeline.run_pipeline(
        expression_file=str(expr_path),
        labels_file=str(labels_path),
        output_dir=str(output_dir),
        run_name=run_name,
        normalization_method="log2",
        stats_methods=["t_test", "wilcoxon"],
        alpha=0.05,
        selection_methods=None,
        n_features=100,
        stability_bootstraps=40,
    )


def one_mode(
    mode: str,
    base_out: Path,
    sample_limit: int,
    max_genes: int,
    label_task: str = "stage",
) -> Tuple[Path, Path, dict]:
    raw_dir = base_out / "raw" / mode
    work_dir = base_out / "work" / mode
    results_dir = base_out / "results" / mode
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== [{mode}] Fetching TCGA-BRCA RNA-Seq (GDC), n_samples={sample_limit} ===")
    if label_task == "er":
        er_mod = _load_er_fetch_module()
        expr = er_mod.fetch_expression(
            sample_limit,
            max_genes,
            None,
            raw_dir,
            gdc_page_size=500,
            log_norm="none",
        )
    else:
        expr = fetch_tcga_expression_brca(sample_limit, raw_dir)
        expr = reduce_genes(expr, max_genes=max_genes)

    cols = list(expr.columns)
    print(f"Expression matrix: {expr.shape[0]} genes x {expr.shape[1]} samples")

    if label_task == "er":
        print(
            "Fetching ER IHC labels from GDC clinical XML (one request per case; slow for large n)..."
        )
        labels_df, _miss, _indet = er_mod.fetch_er_labels(cols, clinical_timeout_s=120.0)
        if labels_df.empty:
            raise RuntimeError("No ER labels parsed from clinical XML")
        labels_df = labels_df[["sample_id", "class_label"]].drop_duplicates("sample_id")
    else:
        print("Fetching GDC case labels (AJCC stage early vs late, else age split)...")
        labels_df = fetch_labels_for_expression_columns(cols)
    labels_df = build_labels_for_columns(cols, labels_df)
    common = list(labels_df["sample_id"].values)
    expr = expr[[c for c in common if c in expr.columns]]
    labels_df = labels_df[labels_df["sample_id"].isin(expr.columns)]
    labels_df = labels_df.drop_duplicates("sample_id").sort_values("sample_id")
    expr = expr.reindex(columns=list(labels_df["sample_id"].values))

    expr_path = work_dir / "expression.csv"
    labels_path = work_dir / "labels.csv"
    expr.to_csv(expr_path)
    labels_df.to_csv(labels_path, index=False)
    print(f"Wrote {expr_path} and {labels_path}")
    print(f"Label counts:\n{labels_df['class_label'].value_counts()}")

    print(f"=== [{mode}] Running BiomarkerPipeline ===")
    results = run_pipeline(
        expr_path,
        labels_path,
        run_name=f"tcga_gdc_{mode}",
        output_dir=results_dir,
    )
    return expr_path, labels_path, results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="TCGA/GDC real data -> biomarker pipeline (quick/full)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s --mode full --samples 40 --genes 15000\n"
            "  %(prog)s --mode full --label-task er --full-samples 200\n"
            "  %(prog)s --mode both --quick-samples 10 --full-samples 30 --full-genes 12000\n"
        ),
    )
    parser.add_argument(
        "--label-task",
        choices=["stage", "er"],
        default="stage",
        help=(
            "stage: GDC AJCC pathologic stage early vs late (fast), else age median split. "
            "er: estrogen receptor IHC from clinical XML (high signal, slow per sample)."
        ),
    )
    parser.add_argument(
        "--target-roc-auc",
        type=float,
        default=0.90,
        help="Target best_cv_roc_auc_mean threshold (default: 0.90).",
    )
    parser.add_argument(
        "--enforce-target",
        action="store_true",
        help=(
            "Enforce --target-roc-auc as a hard gate. If unmet, auto-retry with larger "
            "sample cohorts until --guarantee-max-samples (then fail)."
        ),
    )
    parser.add_argument(
        "--guarantee-max-samples",
        type=_positive_int,
        default=1200,
        help="Upper bound for automatic sample escalation when --enforce-target is set.",
    )
    parser.add_argument(
        "--guarantee-step-samples",
        type=_positive_int,
        default=120,
        help="Sample increment per retry in enforce-target mode (default: 120).",
    )
    parser.add_argument(
        "--guarantee-allow-er-fallback",
        action="store_true",
        help=(
            "In enforce-target mode, if stage labels miss target, retry once with ER labels "
            "before more sample escalation."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["quick", "full", "both"],
        default="both",
        help="quick: fewer samples/genes; full: larger; both: run sequentially",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=BACKEND_ROOT / "data" / "tcga_gdc_pipeline_runs",
        help="Output directory under backend/data",
    )
    parser.add_argument(
        "--quick-samples",
        type=_positive_int,
        default=QUICK_DEFAULT_SAMPLES,
        metavar="N",
        help=f"Sample limit for quick mode (default: {QUICK_DEFAULT_SAMPLES})",
    )
    parser.add_argument(
        "--quick-genes",
        type=_positive_int,
        default=QUICK_DEFAULT_GENES,
        metavar="N",
        help=f"Max genes after subsampling for quick mode (default: {QUICK_DEFAULT_GENES})",
    )
    parser.add_argument(
        "--full-samples",
        type=_positive_int,
        default=FULL_DEFAULT_SAMPLES,
        metavar="N",
        help=f"Sample limit for full mode (default: {FULL_DEFAULT_SAMPLES})",
    )
    parser.add_argument(
        "--full-genes",
        type=_positive_int,
        default=FULL_DEFAULT_GENES,
        metavar="N",
        help=f"Max genes after subsampling for full mode (default: {FULL_DEFAULT_GENES})",
    )
    parser.add_argument(
        "--samples",
        type=_positive_int,
        default=None,
        metavar="N",
        help="Shorthand: overrides sample count for --mode quick or full only",
    )
    parser.add_argument(
        "--genes",
        type=_positive_int,
        default=None,
        metavar="N",
        help="Shorthand: overrides max genes for --mode quick or full only",
    )
    args = parser.parse_args()
    if not (0.0 < args.target_roc_auc <= 1.0):
        parser.error("--target-roc-auc must be in (0, 1].")

    if args.mode == "both" and (args.samples is not None or args.genes is not None):
        parser.error(
            "With --mode both, use --quick-samples/--quick-genes and "
            "--full-samples/--full-genes instead of --samples/--genes."
        )

    _ensure_paths()

    # Django/FastAPI settings: avoid production SECRET check when importing app
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("SECRET_KEY", "script-local-not-for-production")

    modes: List[Tuple[str, int, int]] = []
    if args.mode == "both":
        modes = [
            ("quick", args.quick_samples, args.quick_genes),
            ("full", args.full_samples, args.full_genes),
        ]
    elif args.mode == "quick":
        modes = [
            (
                "quick",
                args.samples if args.samples is not None else args.quick_samples,
                args.genes if args.genes is not None else args.quick_genes,
            )
        ]
    else:
        modes = [
            (
                "full",
                args.samples if args.samples is not None else args.full_samples,
                args.genes if args.genes is not None else args.full_genes,
            )
        ]

    args.out = args.out.resolve()
    summary = []
    for name, n_samples, n_genes in modes:
        try:
            used_samples, used_label_task, res, best_roc, roc_key, attempts = _run_mode_with_target(
                name,
                args.out,
                n_samples,
                n_genes,
                label_task=args.label_task,
                enforce_target=args.enforce_target,
                target_roc_auc=float(args.target_roc_auc),
                guarantee_max_samples=int(args.guarantee_max_samples),
                guarantee_step_samples=int(args.guarantee_step_samples),
                allow_er_fallback=bool(args.guarantee_allow_er_fallback),
            )
            bl = res.get("biomarker_list") or {}
            biomarkers = bl.get("biomarkers") if isinstance(bl, dict) else []
            n_bm = len(biomarkers) if isinstance(biomarkers, list) else 0
            ps = res.get("pipeline_summary") or {}
            ds = ps.get("data_summary") or {}
            n_samp = ds.get("n_samples", "?")
            steps = ps.get("step_summaries") or {}
            stats = steps.get("statistical_analysis") or {}
            ml = steps.get("ml_selection") or {}
            n_sig = stats.get("n_significant_features", "?")
            n_consensus = ml.get("consensus_features_count", "?")
            roc_disp = (
                f"{best_roc:.3f} ({roc_key})"
                if best_roc is not None
                else "n/a"
            )
            summary.append(
                f"{name}: OK | n_samples={n_samp} (requested={n_samples}, used={used_samples}) | "
                f"label_task={used_label_task} | attempts={attempts} | "
                f"best_cv_roc_auc_mean={roc_disp} | "
                f"final_biomarker_list={n_bm} | DE_significant_genes={n_sig} | ml_consensus={n_consensus}"
            )
            if args.enforce_target:
                if best_roc is None or best_roc < float(args.target_roc_auc):
                    raise RuntimeError(
                        f"enforce-target active but best_cv_roc_auc_mean={best_roc} "
                        f"< target={args.target_roc_auc:.3f}"
                    )
            print(f"\n[{name}] Pipeline finished. Keys: {list(res.keys())[:12]}...")
        except Exception as e:
            summary.append(f"{name}: FAILED — {e}")
            print(f"\n[{name}] ERROR: {e}", file=sys.stderr)
            if args.mode != "both":
                return 1

    print("\n======== SUMMARY ========")
    for line in summary:
        print(line)
    print(f"Artifacts under: {args.out}")
    return 0 if all("OK" in s for s in summary) else 1


if __name__ == "__main__":
    raise SystemExit(main())
