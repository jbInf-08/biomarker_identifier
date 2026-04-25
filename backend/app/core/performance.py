"""
Performance optimization and monitoring module.
"""

import asyncio
import logging
import multiprocessing as mp
import threading
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import pandas as pd
import psutil

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class PerformanceMonitor:
    """
    Monitor and track application performance metrics.
    """

    def __init__(self):
        self.metrics = {}
        self.start_time = time.time()
        self.lock = threading.Lock()

    def record_metric(self, name: str, value: float, unit: str = "seconds"):
        """Record a performance metric."""
        with self.lock:
            if name not in self.metrics:
                self.metrics[name] = []
            self.metrics[name].append(
                {"value": value, "unit": unit, "timestamp": datetime.now()}
            )

    def get_metrics(self) -> Dict[str, Any]:
        """Get all recorded metrics."""
        with self.lock:
            return self.metrics.copy()

    def get_system_stats(self) -> Dict[str, Any]:
        """Get current system statistics."""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage("/").percent,
            "process_count": len(psutil.pids()),
            "uptime": time.time() - self.start_time,
        }


# Global performance monitor instance
perf_monitor = PerformanceMonitor()


def performance_timer(func_name: Optional[str] = None):
    """
    Decorator to measure function execution time.

    Args:
        func_name: Custom name for the metric (defaults to function name)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = func_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                perf_monitor.record_metric(name, execution_time)
                logger.debug(f"{name} executed in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                perf_monitor.record_metric(f"{name}_error", execution_time)
                logger.error(f"{name} failed after {execution_time:.3f}s: {str(e)}")
                raise

        return wrapper

    return decorator


def async_performance_timer(func_name: Optional[str] = None):
    """
    Decorator to measure async function execution time.

    Args:
        func_name: Custom name for the metric (defaults to function name)
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            name = func_name or f"{func.__module__}.{func.__name__}"
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                perf_monitor.record_metric(name, execution_time)
                logger.debug(f"{name} executed in {execution_time:.3f}s")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                perf_monitor.record_metric(f"{name}_error", execution_time)
                logger.error(f"{name} failed after {execution_time:.3f}s: {str(e)}")
                raise

        return wrapper

    return decorator


@contextmanager
def performance_context(name: str):
    """
    Context manager for measuring code block execution time.

    Args:
        name: Name for the performance metric
    """
    start_time = time.time()
    try:
        yield
    finally:
        execution_time = time.time() - start_time
        perf_monitor.record_metric(name, execution_time)
        logger.debug(f"{name} executed in {execution_time:.3f}s")


class CacheManager:
    """
    Simple in-memory cache with TTL support.
    """

    def __init__(self, default_ttl: int = 3600):
        self.cache = {}
        self.default_ttl = default_ttl
        self.lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        with self.lock:
            if key in self.cache:
                value, expiry = self.cache[key]
                if time.time() < expiry:
                    return value
                else:
                    del self.cache[key]
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache."""
        with self.lock:
            ttl = ttl or self.default_ttl
            expiry = time.time() + ttl
            self.cache[key] = (value, expiry)

    def delete(self, key: str) -> None:
        """Delete value from cache."""
        with self.lock:
            self.cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        with self.lock:
            self.cache.clear()

    def cleanup_expired(self) -> None:
        """Remove expired entries."""
        with self.lock:
            current_time = time.time()
            expired_keys = [
                key for key, (_, expiry) in self.cache.items() if current_time >= expiry
            ]
            for key in expired_keys:
                del self.cache[key]


# Global cache instance
cache_manager = CacheManager()


def cached(ttl: int = 3600, key_func: Optional[Callable] = None):
    """
    Decorator to cache function results.

    Args:
        ttl: Time to live in seconds
        key_func: Custom key generation function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = (
                    f"{func.__module__}.{func.__name__}:{hash(str(args) + str(kwargs))}"
                )

            # Check cache
            cached_result = cache_manager.get(cache_key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_result

            # Execute function and cache result
            result = func(*args, **kwargs)
            cache_manager.set(cache_key, result, ttl)
            logger.debug(f"Cached result for {cache_key}")
            return result

        return wrapper

    return decorator


class ConnectionPool:
    """
    Simple connection pool for database connections.
    """

    def __init__(self, max_connections: int = 10):
        self.max_connections = max_connections
        self.connections = []
        self.lock = threading.Lock()

    def get_connection(self):
        """Get a connection from the pool."""
        with self.lock:
            if self.connections:
                return self.connections.pop()
            return None

    def return_connection(self, connection):
        """Return a connection to the pool."""
        with self.lock:
            if len(self.connections) < self.max_connections:
                self.connections.append(connection)


class RateLimiter:
    """
    Simple rate limiter using token bucket algorithm.
    """

    def __init__(self, rate: int, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity  # maximum tokens
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens."""
        with self.lock:
            now = time.time()
            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False


class BatchProcessor:
    """
    Process items in batches for better performance.
    """

    def __init__(self, batch_size: int = 100, max_workers: int = None):
        self.batch_size = batch_size
        self.max_workers = max_workers or mp.cpu_count()

    def process_batches(self, items: List[Any], process_func: Callable) -> List[Any]:
        """Process items in batches."""
        results = []

        for i in range(0, len(items), self.batch_size):
            batch = items[i : i + self.batch_size]
            batch_results = process_func(batch)
            results.extend(batch_results)

        return results

    def process_parallel(self, items: List[Any], process_func: Callable) -> List[Any]:
        """Process items in parallel batches."""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []

            for i in range(0, len(items), self.batch_size):
                batch = items[i : i + self.batch_size]
                future = executor.submit(process_func, batch)
                futures.append(future)

            results = []
            for future in futures:
                batch_results = future.result()
                results.extend(batch_results)

            return results


class MemoryOptimizer:
    """
    Memory optimization utilities.
    """

    @staticmethod
    def optimize_dataframe(df, inplace: bool = False):
        """Optimize DataFrame memory usage."""
        if not inplace:
            df = df.copy()

        # Convert object columns to category if beneficial
        for col in df.select_dtypes(include=["object"]).columns:
            if df[col].nunique() / len(df) < 0.5:  # Less than 50% unique values
                df[col] = df[col].astype("category")

        # Downcast numeric columns
        for col in df.select_dtypes(include=["int64"]).columns:
            df[col] = pd.to_numeric(df[col], downcast="integer")

        for col in df.select_dtypes(include=["float64"]).columns:
            df[col] = pd.to_numeric(df[col], downcast="float")

        return df

    @staticmethod
    def get_memory_usage(obj) -> Dict[str, Any]:
        """Get memory usage information for an object."""
        import sys

        size = sys.getsizeof(obj)

        if hasattr(obj, "memory_usage"):
            # For pandas objects
            memory_usage = obj.memory_usage(deep=True)
            return {
                "total_size": size,
                "memory_usage": memory_usage.to_dict()
                if hasattr(memory_usage, "to_dict")
                else memory_usage,
                "total_memory": memory_usage.sum()
                if hasattr(memory_usage, "sum")
                else size,
            }

        return {"total_size": size, "type": type(obj).__name__}


class DatabaseOptimizer:
    """
    Database query optimization utilities.
    """

    @staticmethod
    def optimize_query(query: str) -> str:
        """Basic query optimization."""
        # Remove unnecessary whitespace
        query = " ".join(query.split())

        # Add basic optimizations
        if "SELECT *" in query.upper():
            logger.warning("Query uses SELECT * - consider specifying columns")

        return query

    @staticmethod
    def create_indexes(table_name: str, columns: List[str]) -> List[str]:
        """Generate CREATE INDEX statements."""
        indexes = []
        for column in columns:
            index_name = f"idx_{table_name}_{column}"
            indexes.append(
                f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column});"
            )
        return indexes


class APIOptimizer:
    """
    API performance optimization utilities.
    """

    @staticmethod
    def compress_response(data: Any) -> bytes:
        """Compress response data."""
        import gzip
        import json

        json_data = json.dumps(data, default=str)
        compressed = gzip.compress(json_data.encode("utf-8"))
        return compressed

    @staticmethod
    def paginate_results(
        results: List[Any], page: int, page_size: int
    ) -> Dict[str, Any]:
        """Paginate results for better performance."""
        total = len(results)
        start = (page - 1) * page_size
        end = start + page_size

        paginated_results = results[start:end]

        return {
            "data": paginated_results,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": end < total,
                "has_prev": page > 1,
            },
        }


# Performance monitoring endpoints
def get_performance_metrics() -> Dict[str, Any]:
    """Get current performance metrics."""
    return {
        "system_stats": perf_monitor.get_system_stats(),
        "metrics": perf_monitor.get_metrics(),
        "cache_stats": {
            "cache_size": len(cache_manager.cache),
            "cache_keys": list(cache_manager.cache.keys()),
        },
    }


def cleanup_resources():
    """Clean up resources and optimize performance."""
    # Clean up expired cache entries
    cache_manager.cleanup_expired()

    # Force garbage collection
    import gc

    gc.collect()

    logger.info("Resource cleanup completed")


# Background cleanup task
def start_cleanup_scheduler(interval: int = 300):
    """Start background cleanup scheduler."""

    def cleanup_worker():
        while True:
            time.sleep(interval)
            cleanup_resources()

    cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
    cleanup_thread.start()
    logger.info(f"Cleanup scheduler started with {interval}s interval")
