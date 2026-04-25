"""
Database models for monitoring and logging
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SystemMetrics(Base):
    """System metrics model"""

    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    cpu_usage = Column(Float, nullable=False)
    memory_usage = Column(Float, nullable=False)
    disk_usage = Column(Float, nullable=False)
    database_status = Column(String(20), nullable=False)
    redis_status = Column(String(20), nullable=False)
    active_connections = Column(Integer, default=0)
    error_rate = Column(Float, default=0.0)
    response_time_p95 = Column(Float, default=0.0)
    network_bytes_sent = Column(Integer, default=0)
    network_bytes_recv = Column(Integer, default=0)
    load_average_1m = Column(Float, default=0.0)
    load_average_5m = Column(Float, default=0.0)
    load_average_15m = Column(Float, default=0.0)


class Alert(Base):
    """Alert model"""

    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    alert_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)  # info, warning, critical
    message = Column(Text, nullable=False)
    value = Column(Float, nullable=False)
    threshold = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    meta_data = Column(JSON, nullable=True)


class PerformanceLog(Base):
    """Performance log model"""

    __tablename__ = "performance_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    endpoint = Column(String(200), nullable=False, index=True)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=False, index=True)
    response_time = Column(Float, nullable=False)
    request_size = Column(Integer, default=0)
    response_size = Column(Integer, default=0)
    user_id = Column(Integer, nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)


class ApplicationMetrics(Base):
    """Application-specific metrics model"""

    __tablename__ = "application_metrics"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    metric_type = Column(String(50), nullable=False, index=True)
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)
    tags = Column(JSON, nullable=True)
    meta_data = Column(JSON, nullable=True)


class HealthCheck(Base):
    """Health check model"""

    __tablename__ = "health_checks"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    service_name = Column(String(100), nullable=False, index=True)
    status = Column(
        String(20), nullable=False, index=True
    )  # healthy, unhealthy, degraded
    response_time = Column(Float, nullable=False)
    error_message = Column(Text, nullable=True)
    meta_data = Column(JSON, nullable=True)


class AuditLog(Base):
    """Audit log model"""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)
    resource_id = Column(String(100), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, index=True)  # success, failure, error
    error_message = Column(Text, nullable=True)
