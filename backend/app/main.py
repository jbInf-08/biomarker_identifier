"""
Main FastAPI application for Cancer Biomarker Identifier.
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import (
    admin_routes,
    analysis_routes,
    auth_routes,
    biomarkers,
    clinical_routes,
    data_routes,
    federated_routes,
    integrations_routes,
    public_data_routes,
    research_routes,
    system_routes,
    tenant_routes,
)
from .core.config import DEFAULT_SECRET_KEY, settings
from .core.database import init_db
from .middleware.correlation_id import CorrelationIdMiddleware
from .middleware.rate_limit import limiter
from .middleware.tenant_context import TenantContextMiddleware
from .utils.logging_config import setup_logging
from .websocket import router as websocket_router

# Setup logging (skip during testing)
if "pytest" not in os.environ.get("_", "") and "PYTEST_CURRENT_TEST" not in os.environ:
    try:
        setup_logging()
    except Exception:
        # Silently fail during test imports or if logging setup fails
        pass
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    """
    # Startup
    logger.info("Starting Cancer Biomarker Identifier application...")

    if "PYTEST_CURRENT_TEST" not in os.environ:
        if settings.DATABASE_URL.startswith("sqlite") or settings.DEBUG:
            try:
                await init_db()
            except Exception as e:
                logger.warning("Database init skipped or failed: %s", e)
        else:
            logger.info(
                "PostgreSQL: skipping create_all on startup; run Alembic migrations explicitly."
            )

    # Create necessary directories
    os.makedirs("results", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    os.makedirs("data", exist_ok=True)
    os.makedirs("models", exist_ok=True)
    os.makedirs("reports", exist_ok=True)

    logger.info("Application startup complete")

    _origins = getattr(settings, "ALLOWED_ORIGINS", None) or []
    if any(str(o).strip() == "*" for o in _origins):
        logger.warning(
            "ALLOWED_ORIGINS contains '*'; wildcard origins are incompatible with "
            "credentialed requests in browsers — use explicit origins in production."
        )

    if os.getenv("BIOMARKER_ENV") == "production" and getattr(
        settings, "STRICT_CONFIG_CHECK", False
    ):
        missing = []
        if not settings.SECRET_KEY or settings.SECRET_KEY == DEFAULT_SECRET_KEY:
            missing.append("SECRET_KEY")
        if missing:
            raise RuntimeError(f"Missing required configuration: {missing}")

    yield

    # Shutdown
    logger.info("Shutting down Cancer Biomarker Identifier application...")


# Create FastAPI application
app = FastAPI(
    title="Cancer Biomarker Identifier",
    description="A comprehensive tool for identifying, validating, and visualizing cancer biomarkers using multi-omics data integration and machine learning.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

try:
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except Exception as e:
    logger.warning("SlowAPI rate limiting not registered: %s", e)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tenant context middleware (multi-tenant foundation)
app.add_middleware(TenantContextMiddleware)
# Correlation IDs (runs first on incoming requests — added last)
app.add_middleware(CorrelationIdMiddleware)

# Mount static files (create directories if they don't exist)
os.makedirs("static", exist_ok=True)
os.makedirs("reports", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/reports", StaticFiles(directory="reports"), name="reports")

# Include API routes (unversioned + versioned aliases)
app.include_router(biomarkers.router, prefix="/api/biomarkers", tags=["biomarkers"])
app.include_router(analysis_routes.router, prefix="/api/analysis", tags=["analysis"])
app.include_router(
    federated_routes.router, prefix="/api/federated", tags=["federated-learning"]
)
app.include_router(data_routes.router, prefix="/api/data", tags=["data"])
app.include_router(clinical_routes.router, prefix="/api/clinical", tags=["clinical"])
app.include_router(auth_routes.router, prefix="/api/auth", tags=["authentication"])
app.include_router(system_routes.router, prefix="/api/v1/system", tags=["system"])
app.include_router(admin_routes.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(
    integrations_routes.router,
    prefix="/api/v1/integrations",
    tags=["integrations"],
)
app.include_router(
    research_routes.router,
    prefix="/api/v1/research",
    tags=["research"],
)
app.include_router(
    public_data_routes.router,
    prefix="/api/v1/public-data",
    tags=["public-data"],
)

# v1 versioned paths (preferred for new integrations; same handlers as unversioned)
app.include_router(biomarkers.router, prefix="/api/v1/biomarkers", tags=["biomarkers-v1"])
app.include_router(analysis_routes.router, prefix="/api/v1/analysis", tags=["analysis-v1"])
app.include_router(
    federated_routes.router, prefix="/api/v1/federated", tags=["federated-learning-v1"]
)
app.include_router(data_routes.router, prefix="/api/v1/data", tags=["data-v1"])
app.include_router(clinical_routes.router, prefix="/api/v1/clinical", tags=["clinical-v1"])
app.include_router(auth_routes.router, prefix="/api/v1/auth", tags=["authentication-v1"])
app.include_router(tenant_routes.router, prefix="/api/v1/tenants", tags=["tenants-v1"])

# v2 aliases for core APIs (same handlers, different versioned paths)
app.include_router(
    biomarkers.router, prefix="/api/v2/biomarkers", tags=["biomarkers-v2"]
)
app.include_router(
    analysis_routes.router, prefix="/api/v2/analysis", tags=["analysis-v2"]
)
app.include_router(
    federated_routes.router,
    prefix="/api/v2/federated",
    tags=["federated-learning-v2"],
)
app.include_router(data_routes.router, prefix="/api/v2/data", tags=["data-v2"])
app.include_router(
    clinical_routes.router, prefix="/api/v2/clinical", tags=["clinical-v2"]
)
app.include_router(
    auth_routes.router, prefix="/api/v2/auth", tags=["authentication-v2"]
)
app.include_router(system_routes.router, prefix="/api/v2/system", tags=["system-v2"])
app.include_router(admin_routes.router, prefix="/api/v2/admin", tags=["admin-v2"])
app.include_router(
    integrations_routes.router,
    prefix="/api/v2/integrations",
    tags=["integrations-v2"],
)
app.include_router(
    research_routes.router,
    prefix="/api/v2/research",
    tags=["research-v2"],
)
app.include_router(
    public_data_routes.router,
    prefix="/api/v2/public-data",
    tags=["public-data-v2"],
)
app.include_router(tenant_routes.router, prefix="/api/tenants", tags=["tenants"])

# Include WebSocket routes
app.include_router(websocket_router, prefix="/api", tags=["websocket"])


@app.get("/metrics")
async def prometheus_metrics():
    from app.observability.metrics import metrics_response

    return metrics_response()


@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Root endpoint with application information.
    """
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cancer Biomarker Identifier</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                line-height: 1.6;
            }
            .header {
                text-align: center;
                border-bottom: 3px solid #2c3e50;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }
            .header h1 {
                color: #2c3e50;
                margin: 0;
            }
            .section {
                margin-bottom: 30px;
                padding: 20px;
                border-left: 4px solid #3498db;
                background-color: #f8f9fa;
            }
            .section h2 {
                color: #2c3e50;
                margin-top: 0;
            }
            .links {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin-top: 20px;
            }
            .link-card {
                background: white;
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                text-align: center;
                text-decoration: none;
                color: #2c3e50;
                transition: transform 0.2s;
            }
            .link-card:hover {
                transform: translateY(-2px);
            }
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            .feature {
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .feature h3 {
                color: #3498db;
                margin-top: 0;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>Cancer Biomarker Identifier</h1>
            <p>A comprehensive tool for identifying, validating, and visualizing cancer biomarkers</p>
        </div>
        
        <div class="section">
            <h2>API Documentation</h2>
            <p>Access the interactive API documentation to explore all available endpoints:</p>
            <div class="links">
                <a href="/docs" class="link-card">
                    <strong>Swagger UI</strong><br>
                    Interactive API documentation
                </a>
                <a href="/redoc" class="link-card">
                    <strong>ReDoc</strong><br>
                    Alternative API documentation
                </a>
            </div>
        </div>
        
        <div class="section">
            <h2>Key Features</h2>
            <div class="features">
                <div class="feature">
                    <h3>Multi-Omics Integration</h3>
                    <p>Support for gene expression, proteomics, and clinical data integration with comprehensive quality control and normalization.</p>
                </div>
                <div class="feature">
                    <h3>Statistical Analysis</h3>
                    <p>Advanced differential expression analysis with multiple testing correction, effect size calculations, and volcano plots.</p>
                </div>
                <div class="feature">
                    <h3>Machine Learning</h3>
                    <p>Feature selection using filter, wrapper, and embedded methods with stability selection and consensus scoring.</p>
                </div>
                <div class="feature">
                    <h3>Model Explainability</h3>
                    <p>SHAP-based model interpretability with global and local explanations for transparent biomarker discovery.</p>
                </div>
                <div class="feature">
                    <h3>Pathway Analysis</h3>
                    <p>Gene set enrichment analysis (GSEA) and over-representation analysis (ORA) for biological context.</p>
                </div>
                <div class="feature">
                    <h3>Clinical Annotation</h3>
                    <p>Integration with cancer databases (COSMIC, OncoKB, ClinVar) for clinical and biological context.</p>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Quick Start</h2>
            <p>To get started with biomarker identification:</p>
            <ol>
                <li>Prepare your expression data (TSV/CSV format) and sample labels</li>
                <li>Use the <code>/api/biomarkers/run</code> endpoint to start the pipeline</li>
                <li>Monitor progress with <code>/api/biomarkers/runs/{run_id}/status</code></li>
                <li>Retrieve results and generate reports</li>
            </ol>
        </div>
        
        <div class="section">
            <h2>API Endpoints</h2>
            <p>Main API endpoints for biomarker identification:</p>
            <ul>
                <li><strong>POST /api/biomarkers/run</strong> - Start biomarker identification pipeline</li>
                <li><strong>GET /api/biomarkers/runs/{run_id}/status</strong> - Check pipeline status</li>
                <li><strong>GET /api/biomarkers/runs/{run_id}/biomarkers</strong> - Get biomarker list</li>
                <li><strong>POST /api/biomarkers/runs/{run_id}/train-model</strong> - Train prediction model</li>
                <li><strong>POST /api/biomarkers/runs/{run_id}/shap-analysis</strong> - Run SHAP analysis</li>
                <li><strong>POST /api/biomarkers/runs/{run_id}/pathway-analysis</strong> - Run pathway analysis</li>
                <li><strong>POST /api/biomarkers/runs/{run_id}/annotate</strong> - Annotate biomarkers</li>
                <li><strong>POST /api/biomarkers/runs/{run_id}/report</strong> - Generate comprehensive report</li>
            </ul>
        </div>
    </body>
    </html>
    """


def _readiness_response():
    from .core.health import get_readiness_payload_for_request

    body = get_readiness_payload_for_request()
    body.setdefault("service", "Cancer Biomarker Identifier")
    body.setdefault("version", "1.0.0")
    if not body.get("ready"):
        return JSONResponse(status_code=503, content=body)
    return body


@app.get("/health/live")
async def health_live():
    """Liveness: process is running (use for Docker/k8s liveness when deps may be warming)."""
    body = {
        "status": "ok",
        "service": "Cancer Biomarker Identifier",
        "version": "1.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    region = getattr(settings, "DEPLOYMENT_REGION", None)
    if region:
        body["region"] = region
    return body


@app.get("/health/ready")
async def health_ready():
    """Readiness: database (and Redis when not SQLite) must be healthy."""
    return _readiness_response()


@app.get("/health")
async def health_check():
    """
    Readiness-compatible health check (same as /health/ready).
    Returns 503 if dependencies are not ready.
    """
    return _readiness_response()


@app.get("/api/status")
async def api_status():
    """
    API status endpoint.
    """
    out = {
        "api_status": "operational",
        "endpoints": {
            "biomarkers": "/api/biomarkers",
            "biomarkers_v1": "/api/v1/biomarkers",
            "biomarkers_v2": "/api/v2/biomarkers",
            "federated_capabilities": "/api/v1/federated/capabilities",
            "integrations_v1": "/api/v1/integrations",
            "research_v1": "/api/v1/research/projects",
            "public_data_v1": "/api/v1/public-data",
            "documentation": "/docs",
            "health": "/health",
            "health_ready": "/health/ready",
            "health_live": "/health/live",
        },
        "version": "1.0.0",
    }
    if getattr(settings, "DEPLOYMENT_REGION", None):
        out["region"] = settings.DEPLOYMENT_REGION
    return out


# CGAS Integration — proxy when CGAS_FORWARD_ENABLED, else 501 with fallbacks documented
@app.get("/api/cgas/mutations/{gene_symbol}")
async def get_cgas_mutations(gene_symbol: str):
    """
    Mutation information from a CGAS-compatible service, or 501 with COSMIC/ClinVar fallbacks.
    """
    from fastapi.responses import JSONResponse

    if getattr(settings, "CGAS_FORWARD_ENABLED", False):
        import httpx

        base = settings.CGAS_BASE_URL.rstrip("/")
        path = f"{settings.CGAS_MUTATION_API.rstrip('/')}/{gene_symbol}"
        url = f"{base}{path}"
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, timeout=30.0)
            ct = (r.headers.get("content-type") or "").lower()
            if "application/json" in ct:
                return JSONResponse(status_code=r.status_code, content=r.json())
            return JSONResponse(
                status_code=r.status_code,
                content={"raw": r.text[:8000], "upstream": url},
            )
        except Exception as e:
            logger.exception("CGAS forward failed: %s", e)
            raise HTTPException(status_code=502, detail=f"CGAS upstream error: {e}")

    return JSONResponse(
        status_code=501,
        content={
            "gene_symbol": gene_symbol,
            "error": "CGAS integration not configured",
            "message": "Set CGAS_FORWARD_ENABLED=true and CGAS_BASE_URL, or use /api/clinical/cosmic/mutations or /api/clinical/clinvar/variants",
        },
    )


@app.get("/api/cgas/pathways/{gene_symbol}")
async def get_cgas_pathways(gene_symbol: str):
    """
    Pathway information from CGAS-compatible service, or 501 with pathway-enrichment fallback.
    """
    from fastapi.responses import JSONResponse

    if getattr(settings, "CGAS_FORWARD_ENABLED", False):
        import httpx

        base = settings.CGAS_BASE_URL.rstrip("/")
        path = f"{settings.CGAS_PATHWAY_API.rstrip('/')}/{gene_symbol}"
        url = f"{base}{path}"
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(url, timeout=30.0)
            ct = (r.headers.get("content-type") or "").lower()
            if "application/json" in ct:
                return JSONResponse(status_code=r.status_code, content=r.json())
            return JSONResponse(
                status_code=r.status_code,
                content={"raw": r.text[:8000], "upstream": url},
            )
        except Exception as e:
            logger.exception("CGAS forward failed: %s", e)
            raise HTTPException(status_code=502, detail=f"CGAS upstream error: {e}")

    return JSONResponse(
        status_code=501,
        content={
            "gene_symbol": gene_symbol,
            "error": "CGAS integration not configured",
            "message": "Set CGAS_FORWARD_ENABLED=true and CGAS_BASE_URL, or use POST /api/analysis/pathway/enrichment",
        },
    )


@app.post("/api/reports/generate/{run_id}")
async def generate_cgas_report(run_id: str):
    """
    Report hook for CGAS-compatible upstream, or 501 with biomarker report fallback.
    """
    from fastapi.responses import JSONResponse

    if getattr(settings, "CGAS_FORWARD_ENABLED", False):
        import httpx

        base = settings.CGAS_BASE_URL.rstrip("/")
        url = f"{base}/api/reports/generate/{run_id}"
        try:
            async with httpx.AsyncClient() as client:
                r = await client.post(url, timeout=60.0)
            ct = (r.headers.get("content-type") or "").lower()
            if "application/json" in ct:
                return JSONResponse(status_code=r.status_code, content=r.json())
            return JSONResponse(
                status_code=r.status_code,
                content={"raw": r.text[:8000], "upstream": url},
            )
        except Exception as e:
            logger.exception("CGAS report forward failed: %s", e)
            raise HTTPException(status_code=502, detail=f"CGAS upstream error: {e}")

    return JSONResponse(
        status_code=501,
        content={
            "run_id": run_id,
            "error": "CGAS integration not configured",
            "message": "Use POST /api/biomarkers/runs/{run_id}/report for report generation",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app", host="0.0.0.0", port=8000, reload=True, log_level="info"
    )
