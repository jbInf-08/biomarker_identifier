"""
Logging configuration for the Cancer Biomarker Identifier application.

This module configures structured logging with different handlers for
development and production environments.
"""

import json
import logging
import logging.config
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from ..core.config import settings


class CorrelationIdFilter(logging.Filter):
    """Attach correlation_id from request context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            from ..middleware.correlation_id import request_id_ctx

            rid = request_id_ctx.get("")
            if rid:
                record.correlation_id = rid
        except Exception:
            record.correlation_id = getattr(record, "correlation_id", "")
        return True


def setup_logging(
    log_level: str = None, log_file: str = None, log_format: str = "json"
) -> None:
    """
    Setup application logging configuration.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file
        log_format: Log format (json, text)
    """

    # Use settings if not provided
    log_level = log_level or settings.LOG_LEVEL
    log_file = log_file or settings.LOG_FILE
    if getattr(settings, "LOG_JSON", False):
        log_format = "json"

    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure logging based on environment
    if settings.DEBUG:
        config = _get_development_config(log_level, log_file, log_format)
    else:
        config = _get_production_config(log_level, log_file, log_format)

    # Apply configuration
    logging.config.dictConfig(config)

    # Set root logger level
    logging.getLogger().setLevel(getattr(logging, log_level.upper()))

    # Log startup message
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configuration initialized",
        extra={
            "log_level": log_level,
            "log_file": log_file,
            "log_format": log_format,
            "environment": "development" if settings.DEBUG else "production",
        },
    )


def _get_development_config(
    log_level: str, log_file: str, log_format: str
) -> Dict[str, Any]:
    """Get logging configuration for development environment."""

    if log_format == "json":
        formatter = "json_formatter"
    else:
        formatter = "text_formatter"

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "correlation_id": {
                "()": "app.utils.logging_config.CorrelationIdFilter",
            },
        },
        "formatters": {
            "json_formatter": {
                "()": "app.utils.logging_config.JsonFormatter",
                "format": "%(timestamp)s %(level)s %(name)s %(message)s",
            },
            "text_formatter": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
            "detailed_formatter": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level.upper(),
                "formatter": "detailed_formatter",
                "stream": "ext://sys.stdout",
                "filters": ["correlation_id"],
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level.upper(),
                "formatter": formatter,
                "filename": log_file,
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
                "filters": ["correlation_id"],
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": formatter,
                "filename": log_file.replace(".log", "_error.log"),
                "maxBytes": 10485760,  # 10MB
                "backupCount": 5,
                "encoding": "utf8",
                "filters": ["correlation_id"],
            },
        },
        "loggers": {
            "": {  # Root logger
                "level": log_level.upper(),
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "backend": {
                "level": log_level.upper(),
                "handlers": ["console", "file", "error_file"],
                "propagate": False,
            },
            "uvicorn": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "fastapi": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "celery": {
                "level": "INFO",
                "handlers": ["console", "file"],
                "propagate": False,
            },
            "sqlalchemy": {
                "level": "WARNING",
                "handlers": ["console", "file"],
                "propagate": False,
            },
        },
    }


def _get_production_config(
    log_level: str, log_file: str, log_format: str
) -> Dict[str, Any]:
    """Get logging configuration for production environment."""

    if log_format == "json":
        formatter = "json_formatter"
    else:
        formatter = "text_formatter"

    handlers: Dict[str, Any] = {
        "console_json": {
            "class": "logging.StreamHandler",
            "level": log_level.upper(),
            "formatter": "json_formatter",
            "stream": "ext://sys.stdout",
            "filters": ["correlation_id"],
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": log_level.upper(),
            "formatter": formatter,
            "filename": log_file,
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "encoding": "utf8",
            "filters": ["correlation_id"],
        },
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "ERROR",
            "formatter": formatter,
            "filename": log_file.replace(".log", "_error.log"),
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "encoding": "utf8",
            "filters": ["correlation_id"],
        },
    }
    root_handlers = ["file", "error_file"]
    if getattr(settings, "LOG_JSON", False):
        root_handlers.insert(0, "console_json")
    if sys.platform != "win32":
        handlers["syslog"] = {
            "class": "logging.handlers.SysLogHandler",
            "level": "WARNING",
            "formatter": formatter,
            "address": "/dev/log",
        }
        root_handlers.append("syslog")

    uvicorn_handlers = list(root_handlers)

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {
            "correlation_id": {
                "()": "app.utils.logging_config.CorrelationIdFilter",
            },
        },
        "formatters": {
            "json_formatter": {
                "()": "app.utils.logging_config.JsonFormatter",
                "format": "%(timestamp)s %(level)s %(name)s %(message)s",
            },
            "text_formatter": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": handlers,
        "loggers": {
            "": {
                "level": log_level.upper(),
                "handlers": root_handlers,
                "propagate": False,
            },
            "backend": {
                "level": log_level.upper(),
                "handlers": root_handlers,
                "propagate": False,
            },
            "uvicorn": {
                "level": "WARNING",
                "handlers": uvicorn_handlers,
                "propagate": False,
            },
            "fastapi": {
                "level": "WARNING",
                "handlers": uvicorn_handlers,
                "propagate": False,
            },
            "celery": {
                "level": "INFO",
                "handlers": root_handlers,
                "propagate": False,
            },
            "sqlalchemy": {
                "level": "ERROR",
                "handlers": root_handlers,
                "propagate": False,
            },
        },
    }


class JsonFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""

        # Create base log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception information if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        # Add process and thread information
        log_entry.update(
            {
                "process_id": record.process,
                "thread_id": record.thread,
                "process_name": record.processName,
                "thread_name": record.threadName,
            }
        )
        cid = getattr(record, "correlation_id", None)
        if cid:
            log_entry["correlation_id"] = cid

        return json.dumps(log_entry, ensure_ascii=False)


class StructuredLogger:
    """Structured logger with additional context support."""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.extra_fields = {}

    def bind(self, **kwargs) -> "StructuredLogger":
        """Bind additional context to the logger."""
        new_logger = StructuredLogger(self.logger.name)
        new_logger.extra_fields = {**self.extra_fields, **kwargs}
        return new_logger

    def _log(self, level: int, message: str, **kwargs):
        """Internal logging method with structured data."""
        extra_fields = {**self.extra_fields, **kwargs}
        record = self.logger.makeRecord(
            self.logger.name, level, "", 0, message, (), None
        )
        record.extra_fields = extra_fields
        self.logger.handle(record)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        kwargs["exc_info"] = True
        self._log(logging.ERROR, message, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


def log_request(
    request_id: str,
    method: str,
    url: str,
    status_code: int = None,
    duration: float = None,
):
    """Log HTTP request information."""
    logger = get_logger("http")
    extra_data = {
        "request_id": request_id,
        "method": method,
        "url": url,
        "type": "request",
    }

    if status_code:
        extra_data["status_code"] = status_code
        extra_data["type"] = "response"

    if duration:
        extra_data["duration_ms"] = duration * 1000

    logger.info(f"{method} {url}", **extra_data)


def log_biomarker_analysis(run_id: str, step: str, status: str, **kwargs):
    """Log biomarker analysis events."""
    logger = get_logger("biomarker_analysis")
    logger.info(
        f"Biomarker analysis {step}: {status}",
        run_id=run_id,
        step=step,
        status=status,
        **kwargs,
    )


def log_data_processing(file_path: str, operation: str, status: str, **kwargs):
    """Log data processing events."""
    logger = get_logger("data_processing")
    logger.info(
        f"Data processing {operation}: {status}",
        file_path=file_path,
        operation=operation,
        status=status,
        **kwargs,
    )


def log_model_training(model_type: str, dataset_size: int, status: str, **kwargs):
    """Log model training events."""
    logger = get_logger("model_training")
    logger.info(
        f"Model training {model_type}: {status}",
        model_type=model_type,
        dataset_size=dataset_size,
        status=status,
        **kwargs,
    )


def log_database_operation(operation: str, table: str, status: str, **kwargs):
    """Log database operations."""
    logger = get_logger("database")
    logger.info(
        f"Database {operation} on {table}: {status}",
        operation=operation,
        table=table,
        status=status,
        **kwargs,
    )


def log_external_api_call(api_name: str, endpoint: str, status: str, **kwargs):
    """Log external API calls."""
    logger = get_logger("external_api")
    logger.info(
        f"External API {api_name} {endpoint}: {status}",
        api_name=api_name,
        endpoint=endpoint,
        status=status,
        **kwargs,
    )


def log_security_event(event_type: str, user_id: str = None, **kwargs):
    """Log security-related events."""
    logger = get_logger("security")
    extra_data = {"event_type": event_type, **kwargs}
    if user_id:
        extra_data["user_id"] = user_id

    logger.warning(f"Security event: {event_type}", **extra_data)


def log_performance_metric(metric_name: str, value: float, unit: str = None, **kwargs):
    """Log performance metrics."""
    logger = get_logger("performance")
    extra_data = {"metric_name": metric_name, "value": value, **kwargs}
    if unit:
        extra_data["unit"] = unit

    logger.info(f"Performance metric {metric_name}: {value}", **extra_data)


# Initialize logging when module is imported (skip during testing)
import os

if not logging.getLogger().handlers and "pytest" not in os.environ.get("_", ""):
    try:
        setup_logging()
    except Exception:
        # Silently fail during test imports
        pass
