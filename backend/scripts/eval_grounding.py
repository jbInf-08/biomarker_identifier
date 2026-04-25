#!/usr/bin/env python3
"""
Offline faithfulness check: compare model output to expected gene mentions.
Uses fixture JSON at data/eval/grounding_eval.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "data" / "eval" / "grounding_eval.json"


def main() -> None:
    if not FIXTURE.is_file():
        print("No fixture at", FIXTURE, file=sys.stderr)
        sys.exit(1)
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ok = 0
    for c in cases:
        text = (c.get("mock_output") or "").upper()
        must = [g.upper() for g in c.get("must_mention_genes", [])]
        hit = all(g in text for g in must)
        if hit:
            ok += 1
        else:
            print("FAIL", c.get("id"), "missing", must)
    print(f"eval_grounding: {ok}/{len(cases)} cases passed (string overlap on mock_output)")


if __name__ == "__main__":
    main()
