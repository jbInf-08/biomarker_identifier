#!/usr/bin/env python3
"""
Multi-client federated learning demo against the REST API.

Prerequisites: backend running (e.g. uvicorn app.main:app --reload) on the given base URL.

This script simulates three sites submitting compatible logistic-style weight dicts,
then triggers aggregation and fetches the global model payload.

Usage:
  python scripts/federated_multi_client_demo.py
  python scripts/federated_multi_client_demo.py --base-url http://127.0.0.1:8000/api/federated
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Any, Dict, List

try:
    import numpy as np
    import requests
except ImportError as e:
    print("Requires requests and numpy:", e, file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/api/federated",
        help="Federated API base (e.g. http://localhost:8000/api/federated)",
    )
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    ts = int(time.time())
    participants: List[str] = [f"site_a_{ts}", f"site_b_{ts}", f"site_c_{ts}"]

    init_body: Dict[str, Any] = {
        "model_type": "logistic_regression",
        "participants": participants,
        "min_participants": 2,
        "aggregation_method": "fedavg",
        "num_rounds": 1,
        "differential_privacy": False,
    }

    r = requests.post(f"{base}/initialize", json=init_body, timeout=60)
    if not r.ok:
        print("initialize failed:", r.status_code, r.text, file=sys.stderr)
        sys.exit(1)
    init = r.json()
    round_id = init.get("round_id")
    print("Initialized:", init)
    if not round_id:
        print("No round_id in response", file=sys.stderr)
        sys.exit(1)

    for i, pid in enumerate(participants):
        rng = np.random.default_rng(42 + i)
        weights = {
            "coef_": rng.standard_normal((1, 8)).astype(float).tolist(),
            "intercept_": rng.standard_normal(1).astype(float).tolist(),
        }
        u = requests.post(
            f"{base}/rounds/{round_id}/updates",
            json={
                "participant_id": pid,
                "model_weights": weights,
                "num_samples": 100 + i * 10,
                "loss": 0.5 - i * 0.01,
                "accuracy": 0.75 + i * 0.02,
            },
            timeout=120,
        )
        if not u.ok:
            print("update failed:", u.status_code, u.text, file=sys.stderr)
            sys.exit(1)
        print("Update ok:", pid, u.json())

    agg = requests.post(f"{base}/rounds/{round_id}/aggregate", timeout=120)
    if not agg.ok:
        print("aggregate failed:", agg.status_code, agg.text, file=sys.stderr)
        sys.exit(1)
    print("Aggregate:", agg.json())

    gm = requests.get(
        f"{base}/rounds/{round_id}/global-model",
        params={"participant_id": participants[0]},
        timeout=60,
    )
    if not gm.ok:
        print("global-model failed:", gm.status_code, gm.text, file=sys.stderr)
        sys.exit(1)
    print("Global model response keys:", list(gm.json().keys()))


if __name__ == "__main__":
    main()
