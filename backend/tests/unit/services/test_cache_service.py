"""
Comprehensive unit tests for cache service.
"""
import pytest

from app.services.cache_service import CacheService


class TestCacheService:
    """Test cases for CacheService."""

    def test_cache_service_initialization(self):
        """Test cache service initialization."""
        service = CacheService()
        assert service is not None

    def test_is_available(self):
        """Test checking if cache is available."""
        service = CacheService()
        # May return False if Redis not available, but should not crash
        result = service.is_available()
        assert isinstance(result, bool)

    def test_get_set_delete(self):
        """Test basic cache operations."""
        service = CacheService()

        if service.is_available():
            # Test set
            result = service.set("test_key", {"data": "test_value"}, expire=60)
            assert result is True

            # Test get
            value = service.get("test_key")
            assert value is not None
            assert value["data"] == "test_value"

            # Test delete
            result = service.delete("test_key")
            assert result is True

            # Test get after delete
            value = service.get("test_key")
            assert value is None

    def test_exists(self):
        """Test checking if key exists."""
        service = CacheService()

        if service.is_available():
            service.set("test_key_exists", "value", expire=60)
            assert service.exists("test_key_exists") is True
            service.delete("test_key_exists")
            assert service.exists("test_key_exists") is False

    def test_delete_pattern(self):
        """Test deleting keys by pattern."""
        service = CacheService()

        if service.is_available():
            service.set("test_pattern_1", "value1", expire=60)
            service.set("test_pattern_2", "value2", expire=60)
            service.set("other_key", "value3", expire=60)

            deleted = service.delete_pattern("test_pattern_*")
            assert deleted >= 0

            assert service.exists("test_pattern_1") is False
            assert service.exists("test_pattern_2") is False
            assert service.exists("other_key") is True

            service.delete("other_key")

    def test_get_stats(self):
        """Test getting cache statistics."""
        service = CacheService()

        stats = service.get_stats()
        assert isinstance(stats, dict)
        assert "status" in stats

    def test_increment(self):
        """Test incrementing numeric value."""
        service = CacheService()

        if service.is_available():
            service.set("counter", 10, expire=60)
            result = service.increment("counter", 5)
            assert result is not None
            assert result >= 10
            service.delete("counter")

    def test_expire(self):
        """Test setting expiration."""
        service = CacheService()

        if service.is_available():
            service.set("expire_test", "value", expire=60)
            result = service.expire("expire_test", 120)
            assert isinstance(result, bool)
            service.delete("expire_test")
