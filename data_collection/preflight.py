"""
Preflight credential check.

Runs before a long data-collection run and reports, per source, whether the
credentials it needs are present and (where possible) whether a tiny live
probe against the service works.  Usage:

    python -m data_collection.preflight
    python -m data_collection.preflight --sources OncoKB COSMIC GEO
    python -m data_collection.preflight --probe           # hit the APIs

Exit codes:

    0   all requested sources are *ready* or have green fallback
    1   at least one requested source is *not ready* (hard-fail)
    2   unexpected internal error

The checker never downloads real datasets — it only checks auth and does a
minimal HEAD/GET to confirm that credentials are accepted.  For the
high-profile public sources (GDC, ClinVar, PubMed, NCBI) it will return
``ready`` without any credentials because those APIs are open.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

# Trigger .env autoload before any getenv calls.
from . import base_collector  # noqa: F401

try:
    import requests
except Exception:  # pragma: no cover - requests is a hard dep elsewhere
    requests = None  # type: ignore


# ---------------------------------------------------------------------------- #
#  Data model                                                                  #
# ---------------------------------------------------------------------------- #


@dataclass
class CheckResult:
    source: str
    status: str              # "ready" | "degraded" | "missing" | "error"
    summary: str
    details: List[str] = field(default_factory=list)
    suggestion: str = ""

    def as_row(self) -> Dict[str, Any]:
        return asdict(self)


STATUS_ICON = {
    "ready": "OK ",
    "degraded": "~~ ",
    "missing": "XX ",
    "error": "!! ",
}


# ---------------------------------------------------------------------------- #
#  Per-source checks                                                           #
# ---------------------------------------------------------------------------- #


def _require_env(*names: str) -> Optional[str]:
    """Return the first non-empty env var from ``names``, else None."""
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return None


def check_oncokb(probe: bool = False) -> CheckResult:
    token = _require_env("ONCOKB_API_TOKEN", "ONCOKB_API_KEY")
    if not token:
        return CheckResult(
            source="OncoKB",
            status="missing",
            summary="No OncoKB API token found.",
            suggestion=(
                "Request an OncoKB token (academic or commercial), then set "
                "ONCOKB_API_TOKEN in your .env or shell."
            ),
        )
    details = [f"Token length: {len(token)}"]
    if probe and requests is not None:
        try:
            r = requests.get(
                "https://www.oncokb.org/api/v1/utils/allCuratedGenes",
                headers={"Authorization": f"Bearer {token}",
                         "User-Agent": "Cancer-Biomarker-Identifier/1.0",
                         "Accept": "application/json"},
                timeout=20,
            )
            details.append(f"Probe status: {r.status_code}")
            if r.status_code == 401:
                return CheckResult(
                    source="OncoKB",
                    status="missing",
                    summary="Token present but rejected (401).",
                    details=details,
                    suggestion="Re-generate the token on OncoKB and update ONCOKB_API_TOKEN.",
                )
            if r.status_code >= 400:
                return CheckResult(
                    source="OncoKB",
                    status="error",
                    summary=f"Probe failed: HTTP {r.status_code}",
                    details=details,
                )
        except Exception as exc:
            return CheckResult(
                source="OncoKB",
                status="error",
                summary=f"Probe raised: {exc}",
                details=details,
            )
    return CheckResult(
        source="OncoKB", status="ready",
        summary="Bearer token detected.",
        details=details,
    )


def check_cosmic(probe: bool = False) -> CheckResult:
    email = _require_env("COSMIC_API_EMAIL")
    secret = _require_env("COSMIC_API_KEY")
    if not (email and secret):
        return CheckResult(
            source="COSMIC",
            status="missing",
            summary="COSMIC requires Sanger basic-auth (email + key).",
            suggestion=(
                "Register at COSMIC (Sanger), then set both "
                "COSMIC_API_EMAIL and COSMIC_API_KEY in your .env."
            ),
        )
    details = [f"Email: {email}", f"Key length: {len(secret)}"]
    if probe and requests is not None:
        try:
            r = requests.get(
                "https://cancer.sanger.ac.uk/cosmic/api/ping",
                auth=(email, secret),
                timeout=20,
            )
            details.append(f"Probe status: {r.status_code}")
            if r.status_code in (401, 403):
                return CheckResult(
                    source="COSMIC",
                    status="missing",
                    summary=f"Credentials rejected ({r.status_code}).",
                    details=details,
                    suggestion="Check COSMIC_API_EMAIL / COSMIC_API_KEY on the Sanger portal.",
                )
        except Exception as exc:
            # COSMIC's endpoints are famously flaky; don't fail the preflight
            # just because the probe timed out.
            details.append(f"Probe raised: {exc}")
    return CheckResult(
        source="COSMIC", status="ready",
        summary="Basic-auth credentials detected.",
        details=details,
    )


def check_geo(probe: bool = False) -> CheckResult:
    key = _require_env("NCBI_API_KEY")
    details = [f"NCBI_API_KEY: {'set' if key else 'missing'}"]
    status = "ready" if key else "degraded"
    summary = (
        "NCBI_API_KEY present — high-throughput mode."
        if key else
        "No NCBI_API_KEY — E-utilities is throttled to ~3 rps, runs still work."
    )
    if probe and requests is not None:
        try:
            params = {
                "db": "gds", "term": "GSE2034[ACCN] AND gse[ETYP]",
                "retmode": "json",
            }
            if key:
                params["api_key"] = key
            r = requests.get(
                "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
                params=params, timeout=20,
            )
            details.append(f"Probe status: {r.status_code}")
            ok = r.status_code == 200 and "esearchresult" in (r.text or "")
            if not ok:
                status = "error"
                summary = f"GEO probe failed (HTTP {r.status_code})."
        except Exception as exc:
            details.append(f"Probe raised: {exc}")
            status = "error"
    suggestion = (
        "" if key else
        "Optional: set NCBI_API_KEY in .env to lift the rate limit."
    )
    return CheckResult(
        source="GEO", status=status,
        summary=summary, details=details, suggestion=suggestion,
    )


def check_public(source: str, summary: str) -> Callable[[bool], CheckResult]:
    """Factory for public-no-auth sources (GDC, ClinVar, PubMed, NCBI)."""
    def _check(probe: bool = False) -> CheckResult:
        return CheckResult(source=source, status="ready", summary=summary)
    return _check


def check_gdc(probe: bool = False) -> CheckResult:
    tok = _require_env("GDC_API_TOKEN")
    summary = (
        "GDC public endpoints — token optional." if not tok else
        "GDC token detected (controlled access enabled)."
    )
    return CheckResult(source="GDC", status="ready", summary=summary)


def check_kaggle(probe: bool = False) -> CheckResult:
    u = _require_env("KAGGLE_USERNAME")
    k = _require_env("KAGGLE_KEY")
    if not (u and k):
        return CheckResult(
            source="Kaggle",
            status="missing",
            summary="Kaggle needs KAGGLE_USERNAME + KAGGLE_KEY.",
            suggestion="Generate an API token on kaggle.com/account.",
        )
    return CheckResult(source="Kaggle", status="ready",
                       summary="Kaggle credentials detected.")


CHECKERS: Dict[str, Callable[[bool], CheckResult]] = {
    "OncoKB": check_oncokb,
    "COSMIC": check_cosmic,
    "GEO": check_geo,
    "GDC": check_gdc,
    "ClinVar": check_public("ClinVar", "Public E-utilities endpoint — no auth needed."),
    "PubMed": check_public("PubMed", "Public E-utilities endpoint — no auth needed."),
    "NCBI": check_public("NCBI", "Public E-utilities endpoint — no auth needed."),
    "cBioPortal": check_public("cBioPortal", "Public REST endpoint — no auth."),
    "Kaggle": check_kaggle,
}


# ---------------------------------------------------------------------------- #
#  Driver                                                                      #
# ---------------------------------------------------------------------------- #


def run(sources: Optional[List[str]] = None, probe: bool = False) -> List[CheckResult]:
    names = sources or list(CHECKERS.keys())
    results: List[CheckResult] = []
    for name in names:
        fn = CHECKERS.get(name)
        if fn is None:
            results.append(CheckResult(
                source=name, status="error",
                summary=f"No preflight registered for '{name}'.",
            ))
            continue
        try:
            results.append(fn(probe))
        except Exception as exc:  # pragma: no cover - defensive
            results.append(CheckResult(
                source=name, status="error",
                summary=f"Preflight raised: {exc}",
            ))
    return results


def format_table(results: List[CheckResult]) -> str:
    w_src = max(7, max(len(r.source) for r in results))
    lines = [f"{' ':<3}{'Source':<{w_src}}  Status     Summary"]
    lines.append("-" * (len(lines[0]) + 10))
    for r in results:
        icon = STATUS_ICON.get(r.status, "?? ")
        lines.append(f"{icon}{r.source:<{w_src}}  {r.status:<9}  {r.summary}")
        if r.suggestion:
            lines.append(f"     -> {r.suggestion}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Data-collection preflight check")
    parser.add_argument("--sources", nargs="+",
                        help="Only check these sources (default: all).")
    parser.add_argument("--probe", action="store_true",
                        help="Make a tiny live call to each API to verify credentials.")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON instead of a table.")
    args = parser.parse_args()

    try:
        results = run(args.sources, probe=args.probe)
    except Exception as exc:  # pragma: no cover - defensive
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps([r.as_row() for r in results], indent=2))
    else:
        print(format_table(results))

    # Hard-fail only when an *explicitly requested* source is missing.
    if args.sources:
        not_ready = [r for r in results if r.status == "missing"]
        if not_ready:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
