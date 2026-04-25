"""
Test script for all data collectors.

Uses per-source kwargs from ``collector_smoke_kwargs`` when available; marks
``NotImplementedError`` as skipped (stubs); optional APIs (OncoKB, COSMIC) may
skip on 401 / access errors.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Dict

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

try:
    from data_collection.collector_smoke_kwargs import COLLECTOR_SMOKE_KWARGS
except ImportError:
    from collector_smoke_kwargs import COLLECTOR_SMOKE_KWARGS


def test_collector(stem: str, output_root: Path) -> Dict[str, Any]:
    results: Dict[str, Any] = {
        "file": f"{stem}.py",
        "status": "unknown",
        "error": None,
        "datasets_count": 0,
        "test_data_shape": None,
        "kwargs_used": None,
    }

    out_dir = output_root / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        module = importlib.import_module(f"data_collection.{stem}")

        collector_class = None
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type)
                and hasattr(obj, "__bases__")
                and "DataCollectorBase" in str(obj.__bases__)
            ):
                collector_class = obj
                break

        if collector_class is None:
            results["status"] = "failed"
            results["error"] = "No collector class found"
            return results

        init_kwargs: Dict[str, Any] = {}
        if stem == "geo_collector":
            init_kwargs["rate_limit_delay"] = 0.35
        collector = collector_class(output_dir=str(out_dir), **init_kwargs)

        datasets = collector.get_available_datasets()
        results["datasets_count"] = len(datasets)

        kwargs = COLLECTOR_SMOKE_KWARGS.get(
            stem,
            {"data_type": "clinical", "sample_limit": 5},
        )
        results["kwargs_used"] = kwargs

        collection_results = collector.collect_data(**kwargs)

        if collection_results.get("data") is not None:
            data = collection_results["data"]
            if isinstance(data, pd.DataFrame):
                results["test_data_shape"] = data.shape
            else:
                results["test_data_shape"] = f"Non-DataFrame: {type(data)}"

        results["status"] = "success"

    except NotImplementedError as e:
        results["status"] = "skipped_unimplemented"
        results["error"] = str(e)
    except PermissionError as e:
        results["status"] = "skipped_auth"
        results["error"] = str(e)
    except Exception as e:
        err = str(e)
        low = err.lower()
        if "429" in err or "too many requests" in low:
            results["status"] = "skipped_rate_limit"
            results["error"] = err
        elif "401" in err or "unauthorized" in low or "403" in err or "forbidden" in low:
            results["status"] = "skipped_auth"
            results["error"] = err
        else:
            results["status"] = "failed"
            results["error"] = err
            results["traceback"] = traceback.format_exc()

    return results


def test_all_collectors(
    priority_only: bool = False,
) -> Dict[str, Any]:
    data_collection_dir = Path(__file__).resolve().parent
    output_root = data_collection_dir / ".collector_smoke_output"
    output_root.mkdir(parents=True, exist_ok=True)

    collector_files = sorted(data_collection_dir.glob("*_collector.py"))
    collector_files = [f for f in collector_files if f.name != "base_collector.py"]

    if priority_only:
        want = set(COLLECTOR_SMOKE_KWARGS.keys())
        collector_files = [f for f in collector_files if f.stem in want]

    print(f"Found {len(collector_files)} collector files to test")

    test_results: Dict[str, Dict[str, Any]] = {}
    counts = {
        "success": 0,
        "failed": 0,
        "skipped_unimplemented": 0,
        "skipped_auth": 0,
        "skipped_rate_limit": 0,
    }

    for collector_file in collector_files:
        stem = collector_file.stem
        print(f"Testing {collector_file.name}...")
        result = test_collector(stem, output_root)
        test_results[collector_file.name] = result
        st = result["status"]
        if st in counts:
            counts[st] += 1
        if st == "success":
            print(
                f"  [OK] {result['datasets_count']} datasets, "
                f"shape: {result['test_data_shape']}"
            )
        elif st.startswith("skipped"):
            print(f"  [{st.upper()}] {result['error']}")
        else:
            print(f"  [FAIL] {result['error']}")

    hard_failures = counts["failed"]
    summary = {
        "total_collectors": len(collector_files),
        "counts": counts,
        "hard_failures": hard_failures,
        "success_rate": counts["success"] / len(collector_files) if collector_files else 0,
        "test_results": test_results,
    }
    return summary


def print_test_summary(summary: Dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("DATA COLLECTOR TEST SUMMARY")
    print("=" * 60)
    c = summary["counts"]
    print(f"Total collectors run: {summary['total_collectors']}")
    print(
        f"  success: {c['success']}, failed: {c['failed']}, "
        f"skipped (stub): {c['skipped_unimplemented']}, "
        f"skipped (auth): {c['skipped_auth']}, "
        f"skipped (429): {c['skipped_rate_limit']}"
    )

    if c["failed"] > 0:
        print("\nFAILED:")
        print("-" * 40)
        for filename, result in summary["test_results"].items():
            if result["status"] == "failed":
                print(f"  {filename}: {result['error']}")

    if c["success"] > 0:
        print("\nSUCCESSFUL:")
        print("-" * 40)
        for filename, result in summary["test_results"].items():
            if result["status"] == "success":
                print(
                    f"  {filename}: {result['datasets_count']} datasets, "
                    f"shape: {result['test_data_shape']}"
                )


def main() -> bool:
    parser = argparse.ArgumentParser(description="Smoke-test data collectors")
    parser.add_argument(
        "--priority-only",
        action="store_true",
        help="Only run collectors listed in collector_smoke_kwargs.py",
    )
    args = parser.parse_args()

    print("Testing data collectors...")
    summary = test_all_collectors(priority_only=args.priority_only)
    print_test_summary(summary)

    results_path = Path(__file__).resolve().parent / "test_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\nTest results saved to {results_path}")

    return summary["hard_failures"] == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
