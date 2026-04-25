"""
Celery tasks for cleanup and maintenance.
"""
import logging
from typing import Any, Dict

from celery import current_task

from app.services.celery_service import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.services.tasks.cleanup_tasks.cleanup_temp_files")
def cleanup_temp_files(self, max_age_hours: int = 24) -> Dict[str, Any]:
    """
    Background task for cleaning up temporary files.

    Args:
        max_age_hours: Maximum age of temporary files in hours

    Returns:
        Dict containing cleanup results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting temporary file cleanup..."},
        )

        import os
        import time

        from app.core.config import settings

        temp_dir = settings.TEMP_DIR
        cutoff_time = time.time() - (max_age_hours * 60 * 60)

        deleted_files = []
        total_size_freed = 0

        if os.path.exists(temp_dir):
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        if os.path.getmtime(file_path) < cutoff_time:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            deleted_files.append(file_path)
                            total_size_freed += file_size
                    except OSError as e:
                        logger.warning(
                            f"Failed to delete temporary file {file_path}: {str(e)}"
                        )
                        continue

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Temporary file cleanup completed"},
        )

        logger.info(
            f"Temporary file cleanup completed: {len(deleted_files)} files deleted, {total_size_freed} bytes freed"
        )
        return {
            "status": "completed",
            "deleted_files": len(deleted_files),
            "total_size_freed": total_size_freed,
            "max_age_hours": max_age_hours,
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"Temporary file cleanup failed: {str(e)}")

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Temporary file cleanup failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(bind=True, name="app.services.tasks.cleanup_tasks.cleanup_failed_runs")
def cleanup_failed_runs(self, days_old: int = 7) -> Dict[str, Any]:
    """
    Background task for cleaning up failed analysis runs.

    Args:
        days_old: Number of days after which failed runs should be deleted

    Returns:
        Dict containing cleanup results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting failed run cleanup..."},
        )

        from datetime import datetime, timedelta

        from app.core.database import db_session
        from app.models.run_model import AnalysisRun, RunStatus

        with db_session() as db:
            # Find failed runs older than specified days
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            failed_runs = (
                db.query(AnalysisRun)
                .filter(
                    AnalysisRun.status == RunStatus.FAILED.value,
                    AnalysisRun.created_at < cutoff_date,
                )
                .all()
            )

            deleted_count = 0
            for run in failed_runs:
                try:
                    # Delete associated files
                    import os
                    import shutil

                    from app.core.config import settings

                    run_dir = f"{settings.DATA_DIR}/{run.id}"
                    if os.path.exists(run_dir):
                        shutil.rmtree(run_dir)

                    # Delete database record
                    db.delete(run)
                    deleted_count += 1

                except Exception as e:
                    logger.warning(f"Failed to delete failed run {run.id}: {str(e)}")
                    continue

            db.commit()

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Failed run cleanup completed"},
        )

        logger.info(f"Failed run cleanup completed: {deleted_count} runs deleted")
        return {
            "status": "completed",
            "deleted_runs": deleted_count,
            "days_old": days_old,
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"Failed run cleanup failed: {str(e)}")

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Failed run cleanup failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(bind=True, name="app.services.tasks.cleanup_tasks.optimize_database")
def optimize_database(self) -> Dict[str, Any]:
    """
    Background task for database optimization.

    Returns:
        Dict containing optimization results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting database optimization..."},
        )

        from sqlalchemy import text

        from app.core.database import db_session

        with db_session() as db:
            # Analyze tables
            current_task.update_state(
                state="PROGRESS", meta={"progress": 25, "status": "Analyzing tables..."}
            )

            db.execute(text("ANALYZE"))

            # Vacuum tables
            current_task.update_state(
                state="PROGRESS", meta={"progress": 50, "status": "Vacuuming tables..."}
            )

            db.execute(text("VACUUM"))

            # Reindex tables
            current_task.update_state(
                state="PROGRESS",
                meta={"progress": 75, "status": "Reindexing tables..."},
            )

            db.execute(text("REINDEX"))

            db.commit()

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Database optimization completed"},
        )

        logger.info("Database optimization completed")
        return {"status": "completed", "task_id": self.request.id}

    except Exception as e:
        logger.error(f"Database optimization failed: {str(e)}")

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Database optimization failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(bind=True, name="app.services.tasks.cleanup_tasks.clear_cache")
def clear_cache(self, cache_pattern: str = "*") -> Dict[str, Any]:
    """
    Background task for clearing cache.

    Args:
        cache_pattern: Pattern to match cache keys for deletion

    Returns:
        Dict containing cache clearing results
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting cache clearing..."},
        )

        from app.services.cache_service import cache_service

        deleted_keys = cache_service.delete_pattern(cache_pattern)

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "Cache clearing completed"},
        )

        logger.info(f"Cache clearing completed: {deleted_keys} keys deleted")
        return {
            "status": "completed",
            "deleted_keys": deleted_keys,
            "cache_pattern": cache_pattern,
            "task_id": self.request.id,
        }

    except Exception as e:
        logger.error(f"Cache clearing failed: {str(e)}")

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"Cache clearing failed: {str(e)}",
                "error": str(e),
            },
        )

        raise


@celery_app.task(bind=True, name="app.services.tasks.cleanup_tasks.system_health_check")
def system_health_check(self) -> Dict[str, Any]:
    """
    Background task for system health check.

    Returns:
        Dict containing system health information
    """
    try:
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 0, "status": "Starting system health check..."},
        )

        import os

        import psutil

        from app.services.cache_service import cache_service
        from app.services.celery_service import celery_service

        # Check disk space
        current_task.update_state(
            state="PROGRESS", meta={"progress": 25, "status": "Checking disk space..."}
        )

        disk_usage = psutil.disk_usage("/")
        disk_free_gb = disk_usage.free / (1024**3)
        disk_total_gb = disk_usage.total / (1024**3)
        disk_usage_percent = (disk_usage.used / disk_usage.total) * 100

        # Check memory usage
        current_task.update_state(
            state="PROGRESS",
            meta={"progress": 50, "status": "Checking memory usage..."},
        )

        memory = psutil.virtual_memory()
        memory_usage_percent = memory.percent
        memory_available_gb = memory.available / (1024**3)

        # Check CPU usage
        current_task.update_state(
            state="PROGRESS", meta={"progress": 75, "status": "Checking CPU usage..."}
        )

        cpu_usage_percent = psutil.cpu_percent(interval=1)

        # Check Redis status
        redis_stats = cache_service.get_stats()

        # Check Celery status
        celery_stats = celery_service.get_worker_stats()

        current_task.update_state(
            state="SUCCESS",
            meta={"progress": 100, "status": "System health check completed"},
        )

        health_info = {
            "status": "completed",
            "disk": {
                "free_gb": round(disk_free_gb, 2),
                "total_gb": round(disk_total_gb, 2),
                "usage_percent": round(disk_usage_percent, 2),
            },
            "memory": {
                "usage_percent": memory_usage_percent,
                "available_gb": round(memory_available_gb, 2),
            },
            "cpu": {"usage_percent": cpu_usage_percent},
            "redis": redis_stats,
            "celery": celery_stats,
            "task_id": self.request.id,
        }

        logger.info("System health check completed")
        return health_info

    except Exception as e:
        logger.error(f"System health check failed: {str(e)}")

        current_task.update_state(
            state="FAILURE",
            meta={
                "progress": 0,
                "status": f"System health check failed: {str(e)}",
                "error": str(e),
            },
        )

        raise
