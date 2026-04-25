#!/usr/bin/env python3
"""
Smoke-run the priority public data sources (TCGA, GEO, GDC, COSMIC, ICGC,
ClinVar, OncoKB, NCBI, PubMed, cBioPortal, CCLE, GDSC).

Usage (from repository root):

  python data_collection/run_priority_collectors.py

OncoKB and COSMIC may fail without API tokens; other sources use public APIs.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test priority data collectors")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data" / "external_sources_priority_smoke",
        help="Where to write collector outputs",
    )
    args = parser.parse_args()
    sys.path.insert(0, str(REPO_ROOT))

    from data_collection.run_data_collection import ComprehensiveDataCollector

    sources = [
        "TCGA",
        "GEO",
        "GDC",
        "COSMIC",
        "ICGC",
        "ClinVar",
        "OncoKB",
        "NCBI",
        "PubMed",
        "cBioPortal",
        "CCLE",
        "GDSC",
    ]

    collector = ComprehensiveDataCollector(
        output_dir=str(args.output_dir.resolve()),
        max_workers=1,
    )
    out = collector.run_comprehensive_collection(sources=sources)
    summary = out["summary"]
    print("\n=== Priority collector smoke run ===")
    print(f"Successful: {summary['successful_sources']} / {summary['total_sources']}")
    print(f"Failed: {summary['failed_sources']}")
    if summary.get("failed_source_names"):
        print("Failed sources:", ", ".join(summary["failed_source_names"]))
    print(f"Total records (reported): {summary.get('total_records_collected', 0)}")
    print(f"Output: {args.output_dir.resolve()}")
    return 0 if summary["failed_sources"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
