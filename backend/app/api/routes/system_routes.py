"""
System API routes for health monitoring and system administration.
"""

from datetime import datetime
from typing import Any, Dict
import os
import subprocess

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.platform_models import SparkJob
from app.models.user_model import User
from app.services.monitoring_service import MonitoringService
from app.services.spark_submitter import spark_available, submit_spark_job
from app.services.tenant_policy import apply_tenant_scope, effective_tenant_filter
from app.utils.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Initialize monitoring service
monitoring_service = MonitoringService()


class SparkSubmitBody(BaseModel):
    app_path: str = Field(..., description="Path visible to Spark runtime")
    app_args: list[str] = Field(default_factory=list)
    conf: Dict[str, str] = Field(default_factory=dict)


@router.get("/health", response_model=Dict[str, Any])
async def get_system_health(db: Session = Depends(get_db)):
    """
    Get comprehensive system health status.

    Returns:
        System health information including:
        - Overall status (healthy/warning/critical)
        - System metrics (CPU, memory, disk)
        - Service status (database, Redis, etc.)
        - Application metrics
    """
    try:
        # Collect system metrics
        metrics = monitoring_service._collect_system_metrics()

        # Determine overall status
        status = "healthy"
        if (
            metrics["system"]["cpu_usage"] > 90
            or metrics["system"]["memory_usage"] > 90
        ):
            status = "critical"
        elif (
            metrics["system"]["cpu_usage"] > 80
            or metrics["system"]["memory_usage"] > 80
        ):
            status = "warning"

        # Check service status
        db_status = monitoring_service._check_database_status()
        redis_status = monitoring_service._check_redis_status()

        services = {
            "database": db_status.get("status", "unknown"),
            "redis": redis_status.get("status", "unknown"),
        }

        # Get application metrics
        app_metrics = monitoring_service._get_application_metrics()

        return {
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "system": {
                    "cpu_usage": metrics["system"]["cpu_usage"],
                    "memory_usage": metrics["system"]["memory_usage"],
                    "disk_usage": metrics["system"]["disk_usage"],
                    "load_average": metrics["system"].get("load_average", [0, 0, 0]),
                },
                "database": {
                    "status": db_status.get("status", "unknown"),
                    "size": db_status.get("size", "N/A"),
                    "connections": db_status.get("active_connections", 0),
                },
                "redis": {
                    "status": redis_status.get("status", "unknown"),
                    "connected_clients": redis_status.get("connected_clients", 0),
                },
                "application": {
                    "active_connections": app_metrics.get("total_analyses", 0),
                    "request_rate": 0,  # Would be calculated from Prometheus metrics
                    "error_rate": 0,  # Would be calculated from Prometheus metrics
                    "avg_response_time": 0,  # Would be calculated from Prometheus metrics
                    "active_tasks": app_metrics.get("running_analyses", 0),
                },
            },
            "services": services,
        }

    except Exception as e:
        logger.error(f"Error getting system health: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving system health: {str(e)}"
        )


@router.get("/metrics", response_model=Dict[str, Any])
async def get_system_metrics(db: Session = Depends(get_db)):
    """
    Get detailed system metrics.

    Returns:
        Detailed system metrics including CPU, memory, disk, network, and application metrics.
    """
    try:
        metrics = monitoring_service._collect_system_metrics()
        return metrics

    except Exception as e:
        logger.error(f"Error getting system metrics: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving system metrics: {str(e)}"
        )


@router.get("/services/status", response_model=Dict[str, Any])
async def get_services_status(db: Session = Depends(get_db)):
    """
    Get status of all system services.

    Returns:
        Status of database, Redis, and other services.
    """
    try:
        db_status = monitoring_service._check_database_status()
        redis_status = monitoring_service._check_redis_status()

        return {
            "database": db_status,
            "redis": redis_status,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error getting services status: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Error retrieving services status: {str(e)}"
        )


@router.get("/spark/status", response_model=Dict[str, Any])
async def get_spark_status():
    """Spark runtime readiness for production/offline heavy jobs."""
    return {"spark_submit_available": spark_available()}


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        out = subprocess.run(  # noqa: S603
            ["tasklist", "/FI", f"PID eq {pid}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(pid) in (out.stdout or "")
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


@router.post("/spark/submit", response_model=Dict[str, Any])
async def spark_submit(
    request: Request,
    body: SparkSubmitBody,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    """
    Submit a Spark job (non-blocking).
    """
    try:
        del request
        meta = submit_spark_job(
            app_path=body.app_path, app_args=body.app_args, conf=body.conf
        )
        row = SparkJob(
            user_id=user.id,
            tenant_id=effective_tenant_filter(user),
            app_path=body.app_path,
            app_args=body.app_args,
            conf=body.conf,
            pid=int(meta["pid"]),
            command=meta["command"],
            status="submitted",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {
            "status": "accepted",
            "job_id": row.id,
            **meta,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error("spark submit failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"spark submit failed: {e}")


@router.get("/spark/jobs", response_model=Dict[str, Any])
async def list_spark_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(SparkJob).order_by(SparkJob.submitted_at.desc())
    q = apply_tenant_scope(q, SparkJob, user)
    if getattr(user, "role", None) != "admin":
        q = q.filter(SparkJob.user_id == user.id)
    rows = q.limit(100).all()
    return {
        "jobs": [
            {
                "id": r.id,
                "status": r.status,
                "app_path": r.app_path,
                "pid": r.pid,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            }
            for r in rows
        ]
    }


@router.post("/spark/jobs/{job_id}/refresh", response_model=Dict[str, Any])
async def refresh_spark_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(SparkJob).filter(SparkJob.id == job_id)
    q = apply_tenant_scope(q, SparkJob, user)
    if getattr(user, "role", None) != "admin":
        q = q.filter(SparkJob.user_id == user.id)
    row = q.first()
    if not row:
        raise HTTPException(status_code=404, detail="Spark job not found")
    if row.pid and _pid_running(int(row.pid)):
        row.status = "running"
    elif row.status in ("submitted", "running"):
        row.status = "unknown"
    db.commit()
    return {"id": row.id, "status": row.status, "pid": row.pid}


@router.post("/spark/jobs/{job_id}/retry", response_model=Dict[str, Any])
async def retry_spark_job(
    job_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    row = db.query(SparkJob).filter(SparkJob.id == job_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Spark job not found")
    meta = submit_spark_job(
        app_path=row.app_path,
        app_args=list(row.app_args or []),
        conf=dict(row.conf or {}),
    )
    retry = SparkJob(
        user_id=user.id,
        tenant_id=effective_tenant_filter(user),
        app_path=row.app_path,
        app_args=row.app_args,
        conf=row.conf,
        retry_of_job_id=row.id,
        pid=int(meta["pid"]),
        command=meta["command"],
        status="submitted",
    )
    db.add(retry)
    db.commit()
    db.refresh(retry)
    return {"status": "accepted", "job_id": retry.id, "retry_of_job_id": row.id, **meta}
