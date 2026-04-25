"""
Final Presentation Demo Script
==============================
Comprehensive demo for the Final Presentation (5-7 minutes).
Shows: health check, API docs, real data collectors, biomarker pipeline,
ML training, frontend, multi-tenant, production stack, survival analysis.

Usage:
  python demo_final.py              # Full demo (~5-7 min)
  python demo_final.py --quick    # Faster demo (~3-4 min), skips survival + lighter ML
  python demo_final.py --no-pause # No sleep between sections (CI / scripting)

Prerequisites:
  docker-compose up -d postgres redis
  cd backend && uvicorn app.main:app --reload --port 8000
  cd frontend && npm start   (optional, for browser demo)

See `../conference/docs/presentations/` for deck materials; add `DEMO_RECORDING_GUIDE_Final.md` there for speaker notes and recording steps.
"""

import sys
import os
import argparse
import warnings
from pathlib import Path
import time

# Add project root to path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))
sys.path.insert(0, str(project_root / "data_collection"))

DEMO_OUTPUT_DIR = project_root / "demo_output"
BASE_URL = "http://localhost:8000"


def _configure_runtime():
    """Stable cwd + env so `app.*` imports match backend scripts (SECRET check, relative paths)."""
    try:
        os.chdir(project_root)
    except OSError:
        pass
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("SECRET_KEY", "demo-final-local-not-for-production")
    warnings.filterwarnings(
        "ignore",
        message=".*copying old ast.*",
        category=PendingDeprecationWarning,
    )


def print_section(title, duration=None):
    """Print a formatted section header."""
    print("\n" + "=" * 80, flush=True)
    print(f"  {title}", flush=True)
    if duration:
        print(f"  [~{duration} sec]", flush=True)
    print("=" * 80 + "\n", flush=True)


def print_subsection(title):
    """Print a formatted subsection header."""
    print(f"\n--- {title} ---\n", flush=True)


def ensure_output_dir():
    """Create demo output directory."""
    DEMO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return DEMO_OUTPUT_DIR


# =============================================================================
# Demo 1: Health Check & System Status
# =============================================================================
def demo_1_health_check():
    """Demo 1: Health check and system status."""
    print_section("Demo 1: Health Check & System Status", 30)

    try:
        import urllib.request
        import json
        req = urllib.request.Request(f"{BASE_URL}/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            print("[OK] Backend is running!")
            print(f"  Status: {data.get('status', 'ok')}")
            if isinstance(data.get("checks"), dict):
                for k, v in data["checks"].items():
                    print(f"  {k}: {v}")
            else:
                print(f"  Response: {str(data)[:200]}")
    except Exception as e:
        print("[INFO] Backend not running. Start with:")
        print("  docker-compose up -d postgres redis")
        print("  cd backend && uvicorn app.main:app --reload --port 8000")
        print(f"  Health: GET {BASE_URL}/health")


# =============================================================================
# Demo 2: API Documentation
# =============================================================================
def demo_2_api_docs():
    """Demo 2: Swagger/ReDoc API documentation."""
    print_section("Demo 2: API Documentation", 30)

    print("Interactive Documentation:")
    print("  Swagger UI:  http://localhost:8000/docs")
    print("  ReDoc:       http://localhost:8000/redoc")
    print("\n  Key endpoints:")
    print("    /api/biomarkers  - Pipeline run, results, reports")
    print("    /api/analysis   - Statistical, ML, pathway analysis")
    print("    /api/data       - Upload, validate, process")
    print("    /api/clinical   - COSMIC, ClinVar, OncoKB annotation")
    print("    /api/tenants    - Multi-tenant management")
    print("    /api/v1/system, /api/v2/* - Versioned routes")


# =============================================================================
# Demo 3: Real Data Collectors
# =============================================================================
def demo_3_real_data_collection():
    """Demo 3: Six real data collectors."""
    print_section("Demo 3: Real Data Collectors (6 Sources)", 45)

    collectors = [
        ("TCGA/GDC", "gdc_collector", "GDC Data Portal API, OAuth2"),
        ("GEO", "geo_collector", "NCBI GEO API, SOFT/matrix parsing"),
        ("COSMIC", "cosmic_collector", "REST API, mutation data"),
        ("ICGC", "icgc_collector", "Data Portal API, OAuth"),
        ("ClinVar", "clinvar_collector", "NCBI E-utilities, XML"),
        ("OncoKB", "oncokb_collector", "REST API, therapeutic implications"),
    ]

    for name, module, desc in collectors:
        path = project_root / "data_collection" / f"{module}.py"
        exists = path.exists()
        print(f"  [{'OK' if exists else '--'}] {name}: {desc}")

    print_subsection("Initializing GEO & GDC Collectors")
    try:
        from data_collection.geo_collector import GEOCollector
        c = GEOCollector()
        print("[OK] GEO Collector initialized")
    except Exception as e:
        print(f"[INFO] GEO: {e}")

    try:
        from data_collection.gdc_collector import GDCCollector
        c = GDCCollector()
        print("[OK] GDC Collector initialized (TCGA)")
    except Exception as e:
        print(f"[INFO] GDC: {e}")


# =============================================================================
# Demo 4: Biomarker Pipeline
# =============================================================================
def demo_4_biomarker_pipeline(quick: bool = False):
    """Demo 4: Biomarker pipeline execution."""
    print_section("Demo 4: Biomarker Pipeline (Upload -> Analysis -> Results)", 60)

    print("Pipeline Flow:")
    print("  1. Upload:   POST /api/data/upload (expression, clinical)")
    print("  2. Analyze:  POST /api/biomarkers/run (Celery async)")
    print("  3. Results:  GET  /api/biomarkers/runs/{id}/results")
    print("  4. Report:   POST /api/biomarkers/runs/{id}/report")
    print()

    try:
        warnings.filterwarnings("ignore", category=UserWarning)
        warnings.filterwarnings("ignore", message=".*inconsistent.*")

        from app.pipelines.ml_select import MLSelectionPipeline
        import pandas as pd
        import numpy as np

        print_subsection("Quick ML Selection (sample data)")
        np.random.seed(42)
        n_genes, n_samples = (100, 48) if quick else (100, 60)
        X = pd.DataFrame(
            np.random.randn(n_genes, n_samples),
            index=[f"Gene_{i}" for i in range(n_genes)],
            columns=[f"S{i}" for i in range(n_samples)],
        )
        y = pd.Series(np.random.randint(0, 2, n_samples), index=[f"S{i}" for i in range(n_samples)])

        ml_pipeline = MLSelectionPipeline()
        n_feat = 8 if quick else 10
        boot = 0 if quick else 2
        result = ml_pipeline.run_ml_selection(X, y, n_features=n_feat, stability_bootstraps=boot)
        cf = result.get("consensus_features", {})
        feat_list = cf.get("consensus_features", []) if isinstance(cf, dict) else []
        n_feat = len(feat_list)
        print(f"[OK] ML selection completed - {n_feat} features selected")
        if feat_list:
            top = [f["feature"] if isinstance(f, dict) else str(f) for f in feat_list[:5]]
            print(f"     Top features: {top}")
    except Exception as e:
        print(f"[INFO] Pipeline: {e}")


# =============================================================================
# Demo 5: ML Training
# =============================================================================
def demo_5_ml_training(quick: bool = False):
    """Demo 5: ML model training and deep learning."""
    print_section("Demo 5: ML Training & Feature Selection", 45)

    try:
        from app.ml_models.deep_models import PyTorchTabularClassifier, TORCH_AVAILABLE
        if TORCH_AVAILABLE:
            import torch
            import numpy as np
            import pandas as pd

            try:
                threads = max(1, min(4, os.cpu_count() or 4))
                torch.set_num_threads(threads)
            except Exception:
                pass

            device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"[OK] PyTorch - Device: {device}", flush=True)

            np.random.seed(42)
            rows, cols = (48, 24) if quick else (80, 40)
            X = pd.DataFrame(np.random.randn(rows, cols))
            y = pd.Series(np.random.randint(0, 2, rows))

            epochs = 2 if quick else 3
            clf = PyTorchTabularClassifier(max_epochs=epochs, batch_size=32)
            clf.fit(X, y)
            y_pred = clf.predict(X)
            acc = (y_pred == y.values).mean()
            print(f"[OK] Training complete - Accuracy: {acc:.2%}")
        else:
            from app.data_processing.feature_selection import FeatureSelection
            fs = FeatureSelection()
            print("[OK] FeatureSelection module loaded (PyTorch optional)")
    except Exception as e:
        print(f"[INFO] ML: {e}")


# =============================================================================
# Demo 6: Frontend
# =============================================================================
def demo_6_frontend():
    """Demo 6: Frontend - Dashboard, DataUpload, Results."""
    print_section("Demo 6: Frontend (Dashboard, DataUpload, Results)", 45)

    print("Frontend (start with: cd frontend && npm start):")
    print("  Dashboard:  http://localhost:3000/")
    print("  DataUpload: Upload expression/clinical data")
    print("  Results:    Filtering, export (CSV, JSON)")
    print("  WebSocket:  Real-time progress at /api/ws/collab/{session_id}")
    print("\n  [For recording: open browser, show Dashboard -> DataUpload -> Results]")


# =============================================================================
# Demo 7: Multi-Tenant Isolation
# =============================================================================
def demo_7_multi_tenant(save_commands=True):
    """Demo 7: Multi-tenant isolation."""
    print_section("Demo 7: Multi-Tenant Isolation", 45)

    commands = """
# Multi-Tenant Demo (PowerShell) - tenant routes require an admin-authenticated session in production
Invoke-RestMethod -Uri "http://localhost:8000/api/tenants/" -Method POST -ContentType "application/json" -Body '{"id":"lab-oncology","name":"Lab Oncology"}'
Invoke-RestMethod -Uri "http://localhost:8000/api/tenants/" -Method POST -ContentType "application/json" -Body '{"id":"lab-pathology","name":"Lab Pathology"}'
Invoke-RestMethod -Uri "http://localhost:8000/api/tenants/" -Method GET
Invoke-RestMethod -Uri "http://localhost:8000/api/tenants/lab-oncology" -Method GET -Headers @{"X-Tenant-ID"="lab-oncology"}
"""
    print(commands.strip(), flush=True)

    try:
        import urllib.request
        import urllib.error
        import json
        health_req = urllib.request.Request(f"{BASE_URL}/health")
        with urllib.request.urlopen(health_req, timeout=3) as _:
            pass
        req = urllib.request.Request(
            f"{BASE_URL}/api/tenants/",
            data=json.dumps({"id": "demo-final", "name": "Demo Lab"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            json.loads(resp.read().decode())
            print("\n  [OK] Live: Tenant created (or already exists)", flush=True)
    except urllib.error.HTTPError as e:
        msg = f"HTTP {e.code}"
        if e.code in (401, 403):
            msg += " (admin login required for tenant API)"
        print(f"\n  [INFO] Live tenant POST skipped: {msg}", flush=True)
    except Exception:
        print("\n  [INFO] Backend not running - use commands above for recording", flush=True)

    if save_commands:
        ensure_output_dir()
        out = DEMO_OUTPUT_DIR / "final_tenant_commands.txt"
        with open(out, "w") as f:
            f.write(commands.strip())
        print(f"\n  [SAVED] {out}")


# =============================================================================
# Demo 8: Production Stack & Monitoring
# =============================================================================
def demo_8_production_monitoring():
    """Demo 8: Production Docker stack and Prometheus/Grafana."""
    print_section("Demo 8: Production Stack & Monitoring", 45)

    prod_yml = project_root / "docker-compose.prod.yml"
    if prod_yml.exists():
        print("[OK] docker-compose.prod.yml")
        print("  Services: postgres, redis, backend (2), frontend, celery-worker (3),")
        print("           flower, nginx, prometheus (9090), grafana (3000)")
        print("\n  Command: docker-compose -f docker-compose.prod.yml up -d")
    else:
        print("[INFO] docker-compose.prod.yml - check deployment config")

    prometheus_yml = project_root / "monitoring" / "prometheus.yml"
    if prometheus_yml.exists():
        print(f"\n[OK] Prometheus: {prometheus_yml}")
    print("  Metrics: request count, duration, CPU, memory, disk")


# =============================================================================
# Demo 9: Survival Analysis (optional in quick mode)
# =============================================================================
def demo_9_survival_analysis():
    """Demo 9: Survival analysis and clinical annotation."""
    print_section("Demo 9: Survival Analysis & Clinical Annotation", 40)

    try:
        from app.analysis.survival_analysis import SurvivalAnalyzer
        import pandas as pd
        import numpy as np
        import tempfile

        print("[OK] SurvivalAnalyzer loaded (Cox PH, Kaplan-Meier)")
        np.random.seed(42)
        n = 50
        clinical = pd.DataFrame({
            "sample_id": [f"S{i}" for i in range(n)],
            "overall_survival_time": np.random.exponential(365, n),
            "overall_survival_event": np.random.randint(0, 2, n),
        })
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            clinical.to_csv(f.name, index=False)
            path = f.name
        try:
            analyzer = SurvivalAnalyzer()
            data = analyzer.load_survival_data(path)
            print(f"[OK] Loaded {len(data)} samples")
        finally:
            os.unlink(path)
        print("  Clinical annotation: COSMIC, ClinVar, OncoKB")
    except Exception as e:
        print(f"[INFO] Survival: {e}")


# =============================================================================
# Main
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Final Presentation demo (5-7 min)")
    parser.add_argument("--quick", action="store_true", help="Faster demo (~3-4 min)")
    parser.add_argument(
        "--no-pause",
        action="store_true",
        help="Skip short pauses between sections (smoother for CI / scripting)",
    )
    args = parser.parse_args()

    _configure_runtime()

    print("\n" + "=" * 80, flush=True)
    print("  FINAL PRESENTATION DEMO", flush=True)
    print("  Cancer Biomarker Identifier - Full Working Project", flush=True)
    print("  Duration: 5-7 minutes (--quick: ~3-4 min)", flush=True)
    print("=" * 80, flush=True)

    pause = 0 if args.no_pause else (1 if args.quick else 2)

    demo_1_health_check()
    if pause:
        time.sleep(pause)

    demo_2_api_docs()
    if pause:
        time.sleep(pause)

    demo_3_real_data_collection()
    if pause:
        time.sleep(pause)

    demo_4_biomarker_pipeline(quick=args.quick)
    if pause:
        time.sleep(pause)

    demo_5_ml_training(quick=args.quick)
    if pause:
        time.sleep(pause)

    demo_6_frontend()
    if pause:
        time.sleep(pause)

    demo_7_multi_tenant(save_commands=True)
    if pause:
        time.sleep(pause)

    demo_8_production_monitoring()
    if pause:
        time.sleep(pause)

    if not args.quick:
        demo_9_survival_analysis()

    print("\n" + "=" * 80, flush=True)
    print("  DEMO COMPLETE", flush=True)
    print("=" * 80, flush=True)
    print(f"  Output artifacts: {DEMO_OUTPUT_DIR}", flush=True)
    print("  Next: docker-compose up -d; uvicorn app.main:app --reload --port 8000", flush=True)
    print("=" * 80 + "\n", flush=True)


if __name__ == "__main__":
    main()
