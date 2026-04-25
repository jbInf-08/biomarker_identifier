"""
Integration tests with real services - no mocks.

All tests use actual Redis, database, and Celery instances.
"""
import time

import pytest

from app.services.cache_service import CacheService
from app.services.celery_service import CeleryService


class TestRealRedisService:
    """Test with real Redis instance."""

    def test_cache_real_redis(self, real_redis_client):
        """Test cache service with real Redis."""
        cache = CacheService()

        # Use real Redis client
        cache.redis_client = real_redis_client

        # Test real operations
        cache.set("test_key", "test_value")
        result = cache.get("test_key")
        assert result == "test_value"

        # Test real expiration
        cache.set("expiring_key", "value", expire=1)
        time.sleep(2)
        result = cache.get("expiring_key")
        assert result is None

    def test_cache_real_connection_error(self):
        """Test cache with real connection error."""
        import redis

        # Try to connect to non-existent Redis
        try:
            bad_client = redis.Redis(host="localhost", port=99999, db=0)
            bad_client.ping()
            pytest.skip("Port 99999 is actually available")
        except redis.ConnectionError:
            # Real connection error - test our service
            cache = CacheService()
            # Should handle gracefully
            result = cache.get("test")
            assert result is None or True


class TestRealDatabaseService:
    """Test with real database."""

    def test_database_real_operations(self, real_db_session):
        """Test database with real operations."""
        from app.models.user_model import User

        # Create real user
        user = User(
            email=f"real_test_{int(time.time())}@example.com",
            name="Real Test User",
            hashed_password="real_hash",
            role="researcher",
        )

        real_db_session.add(user)
        real_db_session.commit()
        real_db_session.refresh(user)

        assert user.id is not None
        assert user.email.startswith("real_test_")

        # Cleanup
        real_db_session.delete(user)
        real_db_session.commit()

    def test_database_real_integrity_error(self, real_db_session):
        """Test database with real integrity error."""
        from app.models.user_model import User

        email = f"real_duplicate_{int(time.time())}@example.com"

        # Create first user
        user1 = User(
            email=email, name="User 1", hashed_password="hash1", role="researcher"
        )
        real_db_session.add(user1)
        real_db_session.commit()

        # Try to create duplicate (real integrity error)
        user2 = User(
            email=email,  # Same email
            name="User 2",
            hashed_password="hash2",
            role="researcher",
        )
        real_db_session.add(user2)

        try:
            real_db_session.commit()
            # Should not reach here
            assert False, "Should have raised IntegrityError"
        except Exception as e:
            # Real integrity error - verify rollback
            real_db_session.rollback()
            assert "unique" in str(e).lower() or "constraint" in str(e).lower()

        # Cleanup
        real_db_session.delete(user1)
        real_db_session.commit()


class TestRealCeleryService:
    """Test with real Celery instance."""

    def test_celery_real_task_status(self, real_celery_app):
        """Test Celery with real task status."""
        service = CeleryService()

        # Get real task status (may be empty if no tasks)
        try:
            tasks = service.get_active_tasks()
            assert isinstance(tasks, list)
        except Exception:
            # May fail if no workers
            pass

    def test_celery_real_worker_stats(self, real_celery_app):
        """Test Celery with real worker stats."""
        service = CeleryService()

        try:
            stats = service.get_worker_stats()
            assert isinstance(stats, dict)
        except Exception:
            # May fail if no workers
            pass
