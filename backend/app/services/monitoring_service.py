"""
Advanced Monitoring and Logging Service
Comprehensive system monitoring and alerting capabilities
"""

import asyncio
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import aiohttp
import psutil
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import db_session
from app.models.monitoring import Alert, PerformanceLog, SystemMetrics

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds", "HTTP request duration", ["method", "endpoint"]
)
ACTIVE_CONNECTIONS = Gauge("active_connections", "Number of active connections")
SYSTEM_CPU_USAGE = Gauge("system_cpu_usage_percent", "System CPU usage percentage")
SYSTEM_MEMORY_USAGE = Gauge(
    "system_memory_usage_percent", "System memory usage percentage"
)
SYSTEM_DISK_USAGE = Gauge("system_disk_usage_percent", "System disk usage percentage")
DATABASE_CONNECTIONS = Gauge("database_connections", "Number of database connections")
REDIS_CONNECTIONS = Gauge("redis_connections", "Number of Redis connections")
ANALYSIS_QUEUE_LENGTH = Gauge(
    "analysis_queue_length", "Number of pending analysis tasks"
)
ANALYSIS_DURATION = Histogram(
    "analysis_duration_seconds", "Analysis duration", ["analysis_type"]
)


@dataclass
class SystemHealth:
    """System health status"""

    status: str  # healthy, warning, critical
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    database_status: str
    redis_status: str
    active_connections: int
    error_rate: float
    response_time_p95: float


class MonitoringService:
    """Advanced monitoring and logging service"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics_interval = 30  # seconds
        self.alert_thresholds = {
            "cpu_usage": 80.0,
            "memory_usage": 85.0,
            "disk_usage": 90.0,
            "error_rate": 5.0,
            "response_time_p95": 5.0,
        }
        self.monitoring_active = False
        self.monitoring_thread = None

    def start_monitoring(self):
        """Start system monitoring"""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()

        # Start Prometheus metrics server
        start_http_server(8001)

        self.logger.info("Monitoring service started")

    def stop_monitoring(self):
        """Stop system monitoring"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)

        self.logger.info("Monitoring service stopped")

    def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.monitoring_active:
            try:
                # Collect system metrics
                metrics = self._collect_system_metrics()

                # Update Prometheus metrics
                self._update_prometheus_metrics(metrics)

                # Store metrics in database
                self._store_metrics(metrics)

                # Check for alerts
                self._check_alerts(metrics)

                # Sleep for interval
                time.sleep(self.metrics_interval)

            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {str(e)}")
                time.sleep(5)

    def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect comprehensive system metrics"""

        # System metrics
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        # Network metrics
        network = psutil.net_io_counters()

        # Process metrics
        process = psutil.Process()
        process_memory = process.memory_info()
        process_cpu = process.cpu_percent()

        # Database metrics
        db_status = self._check_database_status()

        # Redis metrics
        redis_status = self._check_redis_status()

        # Application metrics
        app_metrics = self._get_application_metrics()

        return {
            "timestamp": datetime.now(),
            "system": {
                "cpu_usage": cpu_usage,
                "memory_usage": memory.percent,
                "memory_available": memory.available,
                "memory_total": memory.total,
                "disk_usage": disk.percent,
                "disk_free": disk.free,
                "disk_total": disk.total,
                "load_average": psutil.getloadavg()
                if hasattr(psutil, "getloadavg")
                else [0, 0, 0],
            },
            "network": {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv,
            },
            "process": {
                "cpu_usage": process_cpu,
                "memory_usage": process_memory.rss,
                "memory_percent": process.memory_percent(),
                "num_threads": process.num_threads(),
                "num_fds": process.num_fds() if hasattr(process, "num_fds") else 0,
            },
            "database": db_status,
            "redis": redis_status,
            "application": app_metrics,
        }

    def _check_database_status(self) -> Dict[str, Any]:
        """Check database connection and performance"""
        try:
            from sqlalchemy import text

            with db_session() as db:
                # Test connection
                start_time = time.time()
                db.execute(text("SELECT 1"))
                response_time = time.time() - start_time

                # Get connection info (PostgreSQL only; SQLite uses 0)
                if settings.DATABASE_URL.startswith("sqlite"):
                    connection_info = 0
                else:
                    connection_info = db.execute(
                        text("SELECT count(*) FROM pg_stat_activity")
                    ).scalar()

            return {
                "status": "healthy",
                "response_time": response_time,
                "active_connections": connection_info,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now()}

    def _check_redis_status(self) -> Dict[str, Any]:
        """Check Redis connection and performance"""
        try:
            import redis

            r = redis.Redis.from_url(settings.REDIS_URL)

            # Test connection
            start_time = time.time()
            r.ping()
            response_time = time.time() - start_time

            # Get Redis info
            info = r.info()

            return {
                "status": "healthy",
                "response_time": response_time,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory", 0),
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "timestamp": datetime.now(),
            }

        except Exception as e:
            return {"status": "unhealthy", "error": str(e), "timestamp": datetime.now()}

    def _get_application_metrics(self) -> Dict[str, Any]:
        """Get application-specific metrics"""
        try:
            with db_session() as db:
                # Analysis metrics
                from app.models.run_model import AnalysisRun

                total_analyses = db.query(AnalysisRun).count()
                running_analyses = (
                    db.query(AnalysisRun)
                    .filter(AnalysisRun.status == "running")
                    .count()
                )
                completed_analyses = (
                    db.query(AnalysisRun)
                    .filter(AnalysisRun.status == "completed")
                    .count()
                )
                failed_analyses = (
                    db.query(AnalysisRun)
                    .filter(AnalysisRun.status == "failed")
                    .count()
                )

                # User metrics
                from app.models.user_model import User

                total_users = db.query(User).count()
                active_users = (
                    db.query(User)
                    .filter(User.last_login > datetime.now() - timedelta(hours=24))
                    .count()
                )

                return {
                    "total_analyses": total_analyses,
                    "running_analyses": running_analyses,
                    "completed_analyses": completed_analyses,
                    "failed_analyses": failed_analyses,
                    "total_users": total_users,
                    "active_users": active_users,
                    "timestamp": datetime.now(),
                }

        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now()}

    def _update_prometheus_metrics(self, metrics: Dict[str, Any]):
        """Update Prometheus metrics"""
        try:
            # System metrics
            SYSTEM_CPU_USAGE.set(metrics["system"]["cpu_usage"])
            SYSTEM_MEMORY_USAGE.set(metrics["system"]["memory_usage"])
            SYSTEM_DISK_USAGE.set(metrics["system"]["disk_usage"])

            # Database metrics
            if metrics["database"]["status"] == "healthy":
                DATABASE_CONNECTIONS.set(metrics["database"]["active_connections"])

            # Redis metrics
            if metrics["redis"]["status"] == "healthy":
                REDIS_CONNECTIONS.set(metrics["redis"]["connected_clients"])

            # Application metrics
            if "application" in metrics and "error" not in metrics["application"]:
                ANALYSIS_QUEUE_LENGTH.set(metrics["application"]["running_analyses"])

        except Exception as e:
            self.logger.error(f"Error updating Prometheus metrics: {str(e)}")

    def _store_metrics(self, metrics: Dict[str, Any]):
        """Store metrics in database"""
        try:
            with db_session() as db:
                # Create system metrics record
                system_metrics = SystemMetrics(
                    timestamp=metrics["timestamp"],
                    cpu_usage=metrics["system"]["cpu_usage"],
                    memory_usage=metrics["system"]["memory_usage"],
                    disk_usage=metrics["system"]["disk_usage"],
                    database_status=metrics["database"]["status"],
                    redis_status=metrics["redis"]["status"],
                    active_connections=metrics["database"].get(
                        "active_connections", 0
                    ),
                    error_rate=0.0,  # Calculate from logs
                    response_time_p95=metrics["database"].get("response_time", 0.0),
                )

                db.add(system_metrics)
                db.commit()

        except Exception as e:
            self.logger.error(f"Error storing metrics: {str(e)}")

    def _check_alerts(self, metrics: Dict[str, Any]):
        """Check for alert conditions"""
        try:
            alerts = []

            # CPU usage alert
            if metrics["system"]["cpu_usage"] > self.alert_thresholds["cpu_usage"]:
                alerts.append(
                    {
                        "type": "cpu_usage",
                        "severity": "warning",
                        "message": f"High CPU usage: {metrics['system']['cpu_usage']:.1f}%",
                        "value": metrics["system"]["cpu_usage"],
                        "threshold": self.alert_thresholds["cpu_usage"],
                    }
                )

            # Memory usage alert
            if (
                metrics["system"]["memory_usage"]
                > self.alert_thresholds["memory_usage"]
            ):
                alerts.append(
                    {
                        "type": "memory_usage",
                        "severity": "warning",
                        "message": f"High memory usage: {metrics['system']['memory_usage']:.1f}%",
                        "value": metrics["system"]["memory_usage"],
                        "threshold": self.alert_thresholds["memory_usage"],
                    }
                )

            # Disk usage alert
            if metrics["system"]["disk_usage"] > self.alert_thresholds["disk_usage"]:
                alerts.append(
                    {
                        "type": "disk_usage",
                        "severity": "critical",
                        "message": f"High disk usage: {metrics['system']['disk_usage']:.1f}%",
                        "value": metrics["system"]["disk_usage"],
                        "threshold": self.alert_thresholds["disk_usage"],
                    }
                )

            # Database status alert
            if metrics["database"]["status"] != "healthy":
                alerts.append(
                    {
                        "type": "database_status",
                        "severity": "critical",
                        "message": f"Database unhealthy: {metrics['database'].get('error', 'Unknown error')}",
                        "value": 0,
                        "threshold": 1,
                    }
                )

            # Redis status alert
            if metrics["redis"]["status"] != "healthy":
                alerts.append(
                    {
                        "type": "redis_status",
                        "severity": "warning",
                        "message": f"Redis unhealthy: {metrics['redis'].get('error', 'Unknown error')}",
                        "value": 0,
                        "threshold": 1,
                    }
                )

            # Store alerts
            for alert_data in alerts:
                self._create_alert(alert_data)

        except Exception as e:
            self.logger.error(f"Error checking alerts: {str(e)}")

    def _create_alert(self, alert_data: Dict[str, Any]):
        """Create and store alert"""
        try:
            with db_session() as db:
                alert = Alert(
                    alert_type=alert_data["type"],
                    severity=alert_data["severity"],
                    message=alert_data["message"],
                    value=alert_data["value"],
                    threshold=alert_data["threshold"],
                    timestamp=datetime.now(),
                    resolved=False,
                )

                db.add(alert)
                db.commit()

                # Send notification
                self._send_alert_notification(alert)

        except Exception as e:
            self.logger.error(f"Error creating alert: {str(e)}")

    def _send_alert_notification(self, alert: Alert):
        """Send alert notification"""
        try:
            # Log alert
            self.logger.warning(f"ALERT: {alert.message}")

            # Send to external monitoring systems
            if settings.ALERT_WEBHOOK_URL:
                asyncio.create_task(self._send_webhook_alert(alert))

            # Send email alert for critical issues
            if alert.severity == "critical":
                asyncio.create_task(self._send_email_alert(alert))

        except Exception as e:
            self.logger.error(f"Error sending alert notification: {str(e)}")

    async def _send_webhook_alert(self, alert: Alert):
        """Send webhook alert"""
        try:
            webhook_data = {
                "alert_type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
                "value": alert.value,
                "threshold": alert.threshold,
                "timestamp": alert.timestamp.isoformat(),
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    settings.ALERT_WEBHOOK_URL,
                    json=webhook_data,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status != 200:
                        self.logger.error(f"Webhook alert failed: {response.status}")

        except Exception as e:
            self.logger.error(f"Error sending webhook alert: {str(e)}")

    async def _send_email_alert(self, alert: Alert):
        """Send email alert"""
        try:
            # Implement email sending logic
            # This would integrate with your email service
            pass

        except Exception as e:
            self.logger.error(f"Error sending email alert: {str(e)}")

    def get_system_health(self) -> SystemHealth:
        """Get current system health status"""
        try:
            # Get latest metrics
            with db_session() as db:
                latest_metrics = (
                    db.query(SystemMetrics)
                    .order_by(SystemMetrics.timestamp.desc())
                    .first()
                )

            if not latest_metrics:
                return SystemHealth(
                    status="unknown",
                    timestamp=datetime.now(),
                    cpu_usage=0.0,
                    memory_usage=0.0,
                    disk_usage=0.0,
                    database_status="unknown",
                    redis_status="unknown",
                    active_connections=0,
                    error_rate=0.0,
                    response_time_p95=0.0,
                )

            # Determine overall status
            status = "healthy"
            if (
                latest_metrics.cpu_usage > self.alert_thresholds["cpu_usage"]
                or latest_metrics.memory_usage > self.alert_thresholds["memory_usage"]
                or latest_metrics.disk_usage > self.alert_thresholds["disk_usage"]
            ):
                status = "warning"

            if (
                latest_metrics.database_status != "healthy"
                or latest_metrics.redis_status != "healthy"
            ):
                status = "critical"

            return SystemHealth(
                status=status,
                timestamp=latest_metrics.timestamp,
                cpu_usage=latest_metrics.cpu_usage,
                memory_usage=latest_metrics.memory_usage,
                disk_usage=latest_metrics.disk_usage,
                database_status=latest_metrics.database_status,
                redis_status=latest_metrics.redis_status,
                active_connections=latest_metrics.active_connections,
                error_rate=latest_metrics.error_rate,
                response_time_p95=latest_metrics.response_time_p95,
            )

        except Exception as e:
            self.logger.error(f"Error getting system health: {str(e)}")
            return SystemHealth(
                status="error",
                timestamp=datetime.now(),
                cpu_usage=0.0,
                memory_usage=0.0,
                disk_usage=0.0,
                database_status="error",
                redis_status="error",
                active_connections=0,
                error_rate=0.0,
                response_time_p95=0.0,
            )

    def get_metrics_history(
        self, hours: int = 24, metric_type: str = "all"
    ) -> List[Dict[str, Any]]:
        """Get metrics history"""
        try:
            with db_session() as db:
                start_time = datetime.now() - timedelta(hours=hours)

                metrics = (
                    db.query(SystemMetrics)
                    .filter(SystemMetrics.timestamp >= start_time)
                    .order_by(SystemMetrics.timestamp.asc())
                    .all()
                )

                return [asdict(metric) for metric in metrics]

        except Exception as e:
            self.logger.error(f"Error getting metrics history: {str(e)}")
            return []

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts"""
        try:
            with db_session() as db:
                alerts = (
                    db.query(Alert)
                    .filter(Alert.resolved == False)
                    .order_by(Alert.timestamp.desc())
                    .all()
                )

                return [asdict(alert) for alert in alerts]

        except Exception as e:
            self.logger.error(f"Error getting active alerts: {str(e)}")
            return []


# Global monitoring service instance
monitoring_service = MonitoringService()
