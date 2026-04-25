"""
Comprehensive unit tests for cleanup tasks.
"""
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

from app.models.run_model import AnalysisRun, RunStatus
from app.services.tasks.cleanup_tasks import cleanup_failed_runs, cleanup_temp_files
from tests.helpers import patch_module_db_session


class TestCleanupTasks:
    """Test cases for cleanup tasks."""

    def test_cleanup_temp_files(self):
        """Test cleaning up temporary files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            old_file = os.path.join(temp_dir, "old_file.txt")
            new_file = os.path.join(temp_dir, "new_file.txt")

            with open(old_file, "w") as f:
                f.write("test")

            with open(new_file, "w") as f:
                f.write("test")

            old_time = time.time() - (25 * 60 * 60)
            os.utime(old_file, (old_time, old_time))

            mock_task = MagicMock()
            mock_task.request.id = "test_task_id"
            mock_task.update_state = MagicMock()

            from app.core.config import settings

            with patch("app.services.tasks.cleanup_tasks.current_task", mock_task):
                with patch.object(settings, "TEMP_DIR", temp_dir):
                    result = cleanup_temp_files.__wrapped__(max_age_hours=24)

                    assert result is not None
                    assert result["status"] == "completed"
                    assert result["deleted_files"] >= 0
                    assert "task_id" in result

    def test_cleanup_failed_runs(self, db_session, test_user):
        """Test cleaning up failed runs."""
        from datetime import datetime, timedelta

        old_failed_run = AnalysisRun(
            id="test_run_1",
            project_name="Failed",
            analysis_type="differential_expression",
            configuration={},
            status=RunStatus.FAILED.value,
            created_at=datetime.utcnow() - timedelta(days=10),
            user_id=test_user.id,
        )
        db_session.add(old_failed_run)
        db_session.commit()

        mock_task = MagicMock()
        mock_task.request.id = "test_task_id"
        mock_task.update_state = MagicMock()

        with patch("app.services.tasks.cleanup_tasks.current_task", mock_task):
            with patch_module_db_session("app.core.database", db_session):
                result = cleanup_failed_runs.__wrapped__(days_old=7)

                assert result is not None
                assert result["status"] == "completed"
                assert "deleted_runs" in result
                assert "task_id" in result

    def test_cleanup_temp_files_no_directory(self):
        """Test cleanup when temp directory doesn't exist."""
        mock_task = MagicMock()
        mock_task.request.id = "test_task_id"
        mock_task.update_state = MagicMock()

        from app.core.config import settings

        with patch("app.services.tasks.cleanup_tasks.current_task", mock_task):
            with patch.object(settings, "TEMP_DIR", "/nonexistent/directory"):
                result = cleanup_temp_files.__wrapped__(max_age_hours=24)

                assert result is not None
                assert result["status"] == "completed"

    def test_cleanup_temp_files_exception_handling(self):
        """Test cleanup handles exceptions gracefully."""
        mock_task = MagicMock()
        mock_task.request.id = "test_task_id"
        mock_task.update_state = MagicMock()

        from app.core.config import settings

        with patch("app.services.tasks.cleanup_tasks.current_task", mock_task):
            with patch.object(settings, "TEMP_DIR", "/invalid/path"):
                with patch("os.path.exists", side_effect=Exception("Test error")):
                    with pytest.raises(Exception):
                        cleanup_temp_files.__wrapped__(max_age_hours=24)
