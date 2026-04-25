"""
Unit tests for performance module.
"""

import time

import numpy as np
import pandas as pd
import pytest

from app.core.performance import (
    APIOptimizer,
    BatchProcessor,
    CacheManager,
    DatabaseOptimizer,
    MemoryOptimizer,
    PerformanceMonitor,
    RateLimiter,
    async_performance_timer,
    cached,
    cleanup_resources,
    get_performance_metrics,
    performance_context,
    performance_timer,
)


class TestPerformanceMonitor:
    """Test PerformanceMonitor class."""

    def test_init(self):
        """Test PerformanceMonitor initialization."""
        monitor = PerformanceMonitor()
        assert monitor.metrics == {}
        assert monitor.start_time > 0

    def test_record_metric(self):
        """Test recording a metric."""
        monitor = PerformanceMonitor()
        monitor.record_metric("test_metric", 1.5, "seconds")

        assert "test_metric" in monitor.metrics
        assert len(monitor.metrics["test_metric"]) == 1

    def test_get_metrics(self):
        """Test getting metrics."""
        monitor = PerformanceMonitor()
        monitor.record_metric("test_metric", 1.5)

        metrics = monitor.get_metrics()
        assert "test_metric" in metrics

    def test_get_system_stats(self):
        """Test getting system stats."""
        monitor = PerformanceMonitor()
        stats = monitor.get_system_stats()

        assert "cpu_percent" in stats
        assert "memory_percent" in stats
        assert "disk_percent" in stats


class TestPerformanceDecorators:
    """Test performance decorators."""

    def test_performance_timer(self):
        """Test performance timer decorator."""

        @performance_timer("test_function")
        def test_func():
            time.sleep(0.1)
            return "result"

        result = test_func()
        assert result == "result"

    def test_async_performance_timer(self):
        """Test async performance timer decorator."""

        @async_performance_timer("test_async_function")
        async def test_async_func():
            await asyncio.sleep(0.1)
            return "result"

        import asyncio

        result = asyncio.run(test_async_func())
        assert result == "result"

    def test_performance_context(self):
        """Test performance context manager."""
        with performance_context("test_context"):
            time.sleep(0.1)


class TestCacheManager:
    """Test CacheManager class."""

    def test_init(self):
        """Test CacheManager initialization."""
        cache = CacheManager(default_ttl=3600)
        assert cache.default_ttl == 3600
        assert cache.cache == {}

    def test_get_set(self):
        """Test getting and setting cache values."""
        cache = CacheManager()
        cache.set("key1", "value1", ttl=60)

        value = cache.get("key1")
        assert value == "value1"

    def test_delete(self):
        """Test deleting cache values."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.delete("key1")

        value = cache.get("key1")
        assert value is None

    def test_clear(self):
        """Test clearing cache."""
        cache = CacheManager()
        cache.set("key1", "value1")
        cache.clear()

        assert len(cache.cache) == 0

    def test_cached_decorator(self):
        """Test cached decorator."""
        call_count = [0]

        @cached(ttl=60)
        def test_func(x):
            call_count[0] += 1
            return x * 2

        result1 = test_func(5)
        result2 = test_func(5)  # Should use cache

        assert result1 == 10
        assert result2 == 10
        assert call_count[0] == 1  # Function called only once


class TestRateLimiter:
    """Test RateLimiter class."""

    def test_init(self):
        """Test RateLimiter initialization."""
        limiter = RateLimiter(rate=10, capacity=20)
        assert limiter.rate == 10
        assert limiter.capacity == 20
        assert limiter.tokens == 20

    def test_acquire(self):
        """Test acquiring tokens."""
        limiter = RateLimiter(rate=10, capacity=20)

        result = limiter.acquire(tokens=1)
        assert result is True
        assert limiter.tokens == 19


class TestBatchProcessor:
    """Test BatchProcessor class."""

    def test_process_batches(self):
        """Test processing items in batches."""
        processor = BatchProcessor(batch_size=10)
        items = list(range(25))

        def process_func(batch):
            return [x * 2 for x in batch]

        results = processor.process_batches(items, process_func)
        assert len(results) == 25
        assert results[0] == 0
        assert results[10] == 20


class TestMemoryOptimizer:
    """Test MemoryOptimizer class."""

    def test_optimize_dataframe(self):
        """Test optimizing DataFrame memory."""
        df = pd.DataFrame(
            {
                "int_col": np.random.randint(0, 100, 1000),
                "float_col": np.random.randn(1000),
                "str_col": ["A", "B", "C"] * 333 + ["A"],
            }
        )

        optimized = MemoryOptimizer.optimize_dataframe(df, inplace=False)
        assert isinstance(optimized, pd.DataFrame)

    def test_get_memory_usage(self):
        """Test getting memory usage."""
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": [4, 5, 6]})
        usage = MemoryOptimizer.get_memory_usage(df)

        assert "total_size" in usage


class TestDatabaseOptimizer:
    """Test DatabaseOptimizer class."""

    def test_optimize_query(self):
        """Test optimizing query."""
        query = "SELECT   *   FROM   users"
        optimized = DatabaseOptimizer.optimize_query(query)
        assert isinstance(optimized, str)

    def test_create_indexes(self):
        """Test creating index statements."""
        indexes = DatabaseOptimizer.create_indexes("users", ["id", "email"])
        assert len(indexes) == 2
        assert "CREATE INDEX" in indexes[0]


class TestAPIOptimizer:
    """Test APIOptimizer class."""

    def test_compress_response(self):
        """Test compressing response."""
        data = {"key": "value", "number": 123}
        compressed = APIOptimizer.compress_response(data)
        assert isinstance(compressed, bytes)

    def test_paginate_results(self):
        """Test paginating results."""
        results = list(range(100))
        paginated = APIOptimizer.paginate_results(results, page=1, page_size=10)

        assert "data" in paginated
        assert "pagination" in paginated
        assert len(paginated["data"]) == 10


class TestPerformanceFunctions:
    """Test performance utility functions."""

    def test_get_performance_metrics(self):
        """Test getting performance metrics."""
        metrics = get_performance_metrics()
        assert "system_stats" in metrics
        assert "metrics" in metrics
        assert "cache_stats" in metrics

    def test_cleanup_resources(self):
        """Test cleaning up resources."""
        cleanup_resources()  # Should not raise
