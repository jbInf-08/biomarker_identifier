#!/usr/bin/env python3
"""
Compare top-K genes from a biomarker CSV (gene column) to data/benchmarks/brca_drivers.json.
Usage:
  python scripts/check_benchmark_overlap.py --csv path/to/genes.csv --top-k 50
  python scripts/check_benchmark_overlap.py --genes BRCA1,TP53,EGFR
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "benchmarks" / "brca_drivers.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", help="CSV with a gene column")
    ap.add_argument("--genes", help="Comma-separated genes")
    ap.add_argument("--top-k", type=int, default=50)
    ap.add_argument(
        "--min-overlap",
        type=int,
        default=None,
        help="If set, exit with code 1 when overlap count is below this threshold",
    )
    args = ap.parse_args()

    gold = set(json.loads(BENCH.read_text(encoding="utf-8"))["genes"])
    genes: list[str] = []
    if args.csv:
        with open(args.csv, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            col = None
            if r.fieldnames:
                for c in r.fieldnames:
                    if c.lower() in ("gene", "gene_symbol", "symbol"):
                        col = c
                        break
            if not col:
                print("No gene column found", file=sys.stderr)
                sys.exit(1)
            for row in r:
                genes.append(row[col].strip())
    elif args.genes:
        genes = [g.strip() for g in args.genes.split(",") if g.strip()]
    else:
        print("Provide --csv or --genes", file=sys.stderr)
        sys.exit(1)

    top = genes[: args.top_k]
    overlap = [g for g in top if g in gold]
    n_overlap = len(overlap)
    print(f"Top-K: {args.top_k}, overlap with gold ({len(gold)} genes): {n_overlap}")
    print("Matched:", ", ".join(overlap) or "(none)")
    if args.min_overlap is not None and n_overlap < args.min_overlap:
        print(
            f"FAIL: overlap {n_overlap} < required {args.min_overlap}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
