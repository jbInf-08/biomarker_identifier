"""
Celery service for background task processing.
"""
import logging
from typing import Any, Dict, Optional

from celery import Celery
from celery.exceptions import CeleryError

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize Celery (use REDIS_URL so passwords / DB index match the app)
celery_app = Celery(
    "biomarker_identifier",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.services.tasks.biomarker_tasks",
        "app.services.tasks.clinical_tasks",
        "app.services.tasks.report_tasks",
        "app.services.tasks.cleanup_tasks",
        "app.services.tasks.federated_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3300,  # 55 minutes
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_disable_rate_limits=True,
    worker_max_tasks_per_child=500,
    result_expires=3600,  # 1 hour
    task_default_max_retries=3,
    task_default_retry_delay=60,
    task_routes={
        "app.services.tasks.biomarker_tasks.*": {"queue": "biomarker"},
        "app.services.tasks.clinical_tasks.*": {"queue": "clinical"},
        "app.services.tasks.report_tasks.*": {"queue": "reports"},
        "app.services.tasks.cleanup_tasks.*": {"queue": "cleanup"},
    },
    task_default_queue="default",
    task_default_exchange="default",
    task_default_exchange_type="direct",
    task_default_routing_key="default",
    broker_transport_options={
        "visibility_timeout": 3600,
        "retry_on_timeout": True,
        "socket_keepalive": True,
    },
    result_backend_transport_options={
        "visibility_timeout": 3600,
    },
    worker_send_task_events=True,
    task_send_sent_event=True,
)


class CeleryService:
    """Service for managing Celery background tasks."""

    def __init__(self):
        """Initialize Celery service."""
        self.app = celery_app
        logger.info("Celery service initialized successfully")

    def is_available(self) -> bool:
        """Check if Celery is available."""
        try:
            # Try to get active tasks
            inspect = self.app.control.inspect(timeout=2.0)
            stats = inspect.stats()
            return stats is not None
        except CeleryError:
            return False

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get status of a specific task."""
        try:
            result = self.app.AsyncResult(task_id)
            return {
                "task_id": task_id,
                "status": result.status,
                "result": result.result if result.ready() else None,
                "info": result.info,
                "traceback": result.traceback,
            }
        except CeleryError as e:
            logger.error(f"Failed to get task status for {task_id}: {str(e)}")
            return {"task_id": task_id, "status": "FAILURE", "error": str(e)}

    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker statistics."""
        try:
            inspect = self.app.control.inspect(timeout=2.0)
            stats = inspect.stats()
            active = inspect.active()
            scheduled = inspect.scheduled()
            reserved = inspect.reserved()

            return {
                "workers": stats or {},
                "active_tasks": active or {},
                "scheduled_tasks": scheduled or {},
                "reserved_tasks": reserved or {},
            }
        except CeleryError as e:
            logger.error(f"Failed to get worker stats: {str(e)}")
            return {"error": str(e)}

    def revoke_task(self, task_id: str, terminate: bool = False) -> bool:
        """Revoke a task."""
        try:
            self.app.control.revoke(task_id, terminate=terminate)
            logger.info(f"Revoked task {task_id}")
            return True
        except CeleryError as e:
            logger.error(f"Failed to revoke task {task_id}: {str(e)}")
            return False

    def purge_queue(self, queue_name: str) -> int:
        """Purge all tasks from a queue."""
        try:
            purged = self.app.control.purge()
            logger.info(f"Purged queue {queue_name}: {purged} tasks")
            return purged
        except CeleryError as e:
            logger.error(f"Failed to purge queue {queue_name}: {str(e)}")
            return 0

    def get_queue_length(self, queue_name: str) -> int:
        """Get the length of a specific queue."""
        try:
            inspect = self.app.control.inspect(timeout=2.0)
            reserved = inspect.reserved()
            if reserved:
                return sum(len(tasks) for tasks in reserved.values())
            return 0
        except CeleryError as e:
            logger.error(f"Failed to get queue length for {queue_name}: {str(e)}")
            return 0


# Global Celery service instance
celery_service = CeleryService()


# Task decorators
def task_with_retry(max_retries: int = 3, countdown: int = 60):
    """Decorator for tasks with retry logic."""

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Task {func.__name__} failed: {str(e)}")
                raise

        wrapper.max_retries = max_retries
        wrapper.countdown = countdown
        wrapper.bind = True
        return wrapper

    return decorator


def task_with_progress(callback_func=None):
    """Decorator for tasks that report progress."""

    def decorator(func):
        def wrapper(self, *args, **kwargs):
            try:
                # Update progress at start
                if callback_func:
                    callback_func(0, "Starting task...")

                result = func(self, *args, **kwargs)

                # Update progress at completion
                if callback_func:
                    callback_func(100, "Task completed successfully")

                return result
            except Exception as e:
                # Update progress on error
                if callback_func:
                    callback_func(0, f"Task failed: {str(e)}")
                raise

        return wrapper

    return decorator
