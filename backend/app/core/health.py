"""
Readiness and dependency checks for orchestration (Kubernetes, Docker, load balancers).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import settings
from .database import check_db_connection

logger = logging.getLogger(__name__)


def _is_sqlite() -> bool:
    return settings.DATABASE_URL.startswith("sqlite")


def check_redis() -> bool:
    """Return True if Redis responds to PING."""
    try:
        import redis

        r = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2.0, socket_timeout=2.0)
        return bool(r.ping())
    except Exception as e:
        logger.warning("Redis health check failed: %s", e)
        return False


def check_celery_workers() -> Optional[bool]:
    """
    Return True if at least one Celery worker responds to inspect.
    None if Celery check is disabled (default).
    """
    if not settings.HEALTH_CHECK_CELERY:
        return None
    try:
        from app.services.celery_service import celery_app

        inspect = celery_app.control.inspect(timeout=1.0)
        stats = inspect.stats()
        return bool(stats)
    except Exception as e:
        logger.warning("Celery health check failed: %s", e)
        return False


def get_readiness_payload() -> Dict[str, Any]:
    """
    Build readiness body. Returns overall status and per-component checks.
    """
    db_ok = check_db_connection()
    checks: Dict[str, Any] = {"database": {"ok": db_ok}}

    if _is_sqlite():
        checks["redis"] = {"ok": None, "skipped": True, "reason": "sqlite_dev_mode"}
    else:
        checks["redis"] = {"ok": check_redis()}

    celery_res = check_celery_workers()
    if celery_res is None:
        checks["celery"] = {"ok": None, "skipped": True, "reason": "HEALTH_CHECK_CELERY=false"}
    else:
        checks["celery"] = {"ok": celery_res}

    def _redis_ok() -> bool:
        r = checks["redis"]
        if r.get("skipped"):
            return True
        return r.get("ok") is True

    def _celery_ok() -> bool:
        c = checks["celery"]
        if c.get("skipped"):
            return True
        return c.get("ok") is True

    ready = db_ok and _redis_ok() and _celery_ok()
    status = "healthy" if ready else "unhealthy"
    return {
        "status": status,
        "ready": ready,
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def should_skip_external_checks() -> bool:
    """Pytest or explicit opt-out for health checks that need external services."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    if os.environ.get("SKIP_HEALTH_EXTERNAL", "").lower() in ("1", "true", "yes"):
        return True
    return False


def get_readiness_payload_for_request() -> Dict[str, Any]:
    """
    Readiness payload used by HTTP handlers. Under pytest, only checks DB when
    external checks would fail without Redis/Celery.
    """
    if should_skip_external_checks():
        db_ok = check_db_connection()
        return {
            "status": "healthy" if db_ok else "unhealthy",
            "ready": db_ok,
            "checks": {
                "database": {"ok": db_ok},
                "redis": {"ok": None, "skipped": True, "reason": "test_or_skip_external"},
                "celery": {"ok": None, "skipped": True, "reason": "test_or_skip_external"},
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    return get_readiness_payload()
