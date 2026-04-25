"""
Celery configuration for background task processing.

This module configures Celery for handling background tasks such as
biomarker analysis, report generation, and data processing.
"""

import logging
import os

from celery import Celery
from celery.schedules import crontab

from .config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "biomarker_app",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "backend.app.tasks.biomarker_tasks",
        "backend.app.tasks.report_tasks",
        "backend.app.tasks.data_tasks",
        "backend.app.tasks.maintenance_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task routing
    task_routes={
        "backend.app.tasks.biomarker_tasks.*": {"queue": "biomarker"},
        "backend.app.tasks.report_tasks.*": {"queue": "reports"},
        "backend.app.tasks.data_tasks.*": {"queue": "data"},
        "backend.app.tasks.maintenance_tasks.*": {"queue": "maintenance"},
    },
    # Task serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Task execution
    task_always_eager=False,
    task_eager_propagates=True,
    task_ignore_result=False,
    task_store_errors_even_if_ignored=True,
    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    # Result backend
    result_expires=3600,  # 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },
    # Task timeouts
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,  # 10 minutes
    # Retry configuration
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_remote_tracebacks=True,
    # Beat schedule for periodic tasks
    beat_schedule={
        "cleanup-old-runs": {
            "task": "backend.app.tasks.maintenance_tasks.cleanup_old_runs",
            "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
        },
        "backup-database": {
            "task": "backend.app.tasks.maintenance_tasks.backup_database",
            "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
        },
        "update-external-databases": {
            "task": "backend.app.tasks.maintenance_tasks.update_external_databases",
            "schedule": crontab(
                hour=4, minute=0, day_of_week=1
            ),  # Weekly on Monday at 4 AM
        },
        "generate-system-reports": {
            "task": "backend.app.tasks.maintenance_tasks.generate_system_reports",
            "schedule": crontab(
                hour=5, minute=0, day_of_week=1
            ),  # Weekly on Monday at 5 AM
        },
    },
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    # Logging
    worker_log_format="[%(asctime)s: %(levelname)s/%(processName)s] %(message)s",
    worker_task_log_format="[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s",
)


# Task routing configuration
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    logger.info(f"Request: {self.request!r}")
    return "Debug task completed"


# Error handling
@celery_app.task(bind=True)
def error_handler(self, exc, task_id, args, kwargs, einfo):
    """Global error handler for Celery tasks."""
    logger.error(
        f"Task {task_id} failed: {exc}",
        exc_info=einfo,
        extra={
            "task_id": task_id,
            "args": args,
            "kwargs": kwargs,
        },
    )


# Task monitoring
@celery_app.task(bind=True)
def task_monitor(self):
    """Monitor task execution and performance."""
    from celery.task.control import inspect

    i = inspect()

    # Get active tasks
    active = i.active()
    if active:
        logger.info(f"Active tasks: {active}")

    # Get registered tasks
    registered = i.registered()
    if registered:
        logger.info(f"Registered tasks: {registered}")

    # Get worker stats
    stats = i.stats()
    if stats:
        logger.info(f"Worker stats: {stats}")

    return "Task monitoring completed"


# Health check task
@celery_app.task(bind=True)
def health_check(self):
    """Health check task for monitoring system status."""
    import os

    import psutil

    # System metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    health_status = {
        "task_id": self.request.id,
        "timestamp": self.request.utcnow().isoformat(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available": memory.available,
            "disk_percent": disk.percent,
            "disk_free": disk.free,
        },
        "celery": {
            "worker_name": os.environ.get("CELERY_WORKER_NAME", "unknown"),
            "queue": self.request.delivery_info.get("routing_key", "unknown"),
        },
    }

    logger.info(f"Health check completed: {health_status}")
    return health_status


# Task result monitoring
@celery_app.task(bind=True)
def monitor_task_results(self):
    """Monitor task results and performance metrics."""
    from datetime import datetime, timedelta

    from celery.result import GroupResult

    # Get recent task results
    recent_results = []

    # This would typically query the result backend
    # For now, we'll just log the monitoring attempt
    logger.info("Task result monitoring completed")

    return {
        "monitored_tasks": len(recent_results),
        "timestamp": datetime.utcnow().isoformat(),
    }


# Task cleanup
@celery_app.task(bind=True)
def cleanup_task_results(self, days_old=7):
    """Clean up old task results."""
    from datetime import datetime, timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days_old)

    # This would typically clean up old results from the backend
    # For now, we'll just log the cleanup attempt
    logger.info(f"Cleaning up task results older than {cutoff_date}")

    return {
        "cleaned_results": 0,  # Would be actual count
        "cutoff_date": cutoff_date.isoformat(),
    }


# Task performance monitoring
@celery_app.task(bind=True)
def monitor_task_performance(self):
    """Monitor task performance and identify bottlenecks."""
    from celery.task.control import inspect

    i = inspect()

    # Get worker stats
    stats = i.stats()
    if not stats:
        return {"error": "No worker stats available"}

    performance_metrics = {}

    for worker_name, worker_stats in stats.items():
        performance_metrics[worker_name] = {
            "pool": worker_stats.get("pool", {}),
            "load": worker_stats.get("load", []),
            "processed": worker_stats.get("total", {}).get("processed", 0),
        }

    logger.info(f"Task performance monitoring completed: {performance_metrics}")
    return performance_metrics


# Task queue monitoring
@celery_app.task(bind=True)
def monitor_queues(self):
    """Monitor queue lengths and performance."""
    from celery.task.control import inspect

    i = inspect()

    # Get active tasks by queue
    active = i.active()
    if not active:
        return {"error": "No active tasks"}

    queue_stats = {}

    for worker_name, tasks in active.items():
        for task in tasks:
            queue = task.get("delivery_info", {}).get("routing_key", "default")
            if queue not in queue_stats:
                queue_stats[queue] = 0
            queue_stats[queue] += 1

    logger.info(f"Queue monitoring completed: {queue_stats}")
    return queue_stats


# Task retry monitoring
@celery_app.task(bind=True)
def monitor_task_retries(self):
    """Monitor task retries and failures."""
    from celery.task.control import inspect

    i = inspect()

    # Get reserved tasks (tasks that have been retried)
    reserved = i.reserved()
    if not reserved:
        return {"message": "No reserved tasks"}

    retry_stats = {}

    for worker_name, tasks in reserved.items():
        retry_stats[worker_name] = {
            "reserved_tasks": len(tasks),
            "retry_count": sum(task.get("retries", 0) for task in tasks),
        }

    logger.info(f"Task retry monitoring completed: {retry_stats}")
    return retry_stats


# System resource monitoring
@celery_app.task(bind=True)
def monitor_system_resources(self):
    """Monitor system resources and performance."""
    import psutil

    # CPU information
    cpu_count = psutil.cpu_count()
    cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
    cpu_freq = psutil.cpu_freq()

    # Memory information
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Disk information
    disk = psutil.disk_usage("/")
    disk_io = psutil.disk_io_counters()

    # Network information
    network = psutil.net_io_counters()

    resource_metrics = {
        "cpu": {
            "count": cpu_count,
            "percent_per_core": cpu_percent,
            "frequency": {
                "current": cpu_freq.current if cpu_freq else None,
                "min": cpu_freq.min if cpu_freq else None,
                "max": cpu_freq.max if cpu_freq else None,
            }
            if cpu_freq
            else None,
        },
        "memory": {
            "total": memory.total,
            "available": memory.available,
            "percent": memory.percent,
            "used": memory.used,
            "free": memory.free,
        },
        "swap": {
            "total": swap.total,
            "used": swap.used,
            "free": swap.free,
            "percent": swap.percent,
        },
        "disk": {
            "total": disk.total,
            "used": disk.used,
            "free": disk.free,
            "percent": disk.percent,
            "io_read_bytes": disk_io.read_bytes if disk_io else None,
            "io_write_bytes": disk_io.write_bytes if disk_io else None,
        },
        "network": {
            "bytes_sent": network.bytes_sent,
            "bytes_recv": network.bytes_recv,
            "packets_sent": network.packets_sent,
            "packets_recv": network.packets_recv,
        },
    }

    logger.info(f"System resource monitoring completed")
    return resource_metrics


# Task execution time monitoring
@celery_app.task(bind=True)
def monitor_task_execution_times(self):
    """Monitor task execution times and identify slow tasks."""
    # This would typically query the result backend for execution times
    # For now, we'll just log the monitoring attempt

    execution_times = {
        "average_execution_time": 0,  # Would be calculated from actual data
        "slowest_tasks": [],  # Would contain actual slow task data
        "fastest_tasks": [],  # Would contain actual fast task data
    }

    logger.info("Task execution time monitoring completed")
    return execution_times


# Task failure analysis
@celery_app.task(bind=True)
def analyze_task_failures(self, days_back=7):
    """Analyze task failures and identify patterns."""
    from datetime import datetime, timedelta

    cutoff_date = datetime.utcnow() - timedelta(days=days_back)

    # This would typically query the result backend for failed tasks
    # For now, we'll just log the analysis attempt

    failure_analysis = {
        "total_failures": 0,  # Would be actual count
        "failure_rate": 0.0,  # Would be calculated percentage
        "common_errors": [],  # Would contain actual error patterns
        "failed_task_types": [],  # Would contain task type breakdown
        "analysis_period": {
            "start": cutoff_date.isoformat(),
            "end": datetime.utcnow().isoformat(),
        },
    }

    logger.info(
        f"Task failure analysis completed for period: {cutoff_date} to {datetime.utcnow()}"
    )
    return failure_analysis


# Export Celery app for use in other modules
__all__ = ["celery_app"]
