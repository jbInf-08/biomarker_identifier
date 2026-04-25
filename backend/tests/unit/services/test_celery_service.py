"""
Comprehensive unit tests for Celery service.
"""
import pytest

from app.services.celery_service import CeleryService


class TestCeleryService:
    """Test cases for CeleryService."""

    def test_celery_service_initialization(self):
        """Test Celery service initialization."""
        service = CeleryService()
        assert service is not None
        assert service.app is not None

    def test_is_available(self):
        """Test checking if Celery is available."""
        service = CeleryService()
        # May return False if Celery workers not running, but should not crash
        result = service.is_available()
        assert isinstance(result, bool)

    def test_get_task_status(self):
        """Test getting task status."""
        service = CeleryService()

        # Test with non-existent task ID
        result = service.get_task_status("nonexistent-task-id")
        assert isinstance(result, dict)
        assert "task_id" in result
        assert "status" in result

    def test_get_worker_stats(self):
        """Test getting worker statistics."""
        service = CeleryService()

        result = service.get_worker_stats()
        assert isinstance(result, dict)
        assert "workers" in result or "active_tasks" in result

    def test_revoke_task(self):
        """Test revoking a task."""
        service = CeleryService()

        # Test revoking non-existent task (should not crash)
        result = service.revoke_task("nonexistent-task-id", terminate=False)
        assert isinstance(result, bool)

    def test_purge_queue(self):
        """Test purging a queue."""
        service = CeleryService()

        # Test purging (may return 0 if no tasks, but should not crash)
        result = service.purge_queue("default")
        assert isinstance(result, int)
        assert result >= 0

    def test_get_queue_length(self):
        """Test getting queue length."""
        service = CeleryService()

        result = service.get_queue_length("default")
        assert isinstance(result, int)
        assert result >= 0
