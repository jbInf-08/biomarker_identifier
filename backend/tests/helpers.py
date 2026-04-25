"""Shared test helpers (avoid circular imports via conftest)."""

from unittest.mock import MagicMock, patch


def patch_module_db_session(module: str, mock_db):
    """Patch ``module.db_session`` for ``with db_session() as db:`` (context manager)."""
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_db
    mock_ctx.__exit__.return_value = None
    return patch(f"{module}.db_session", return_value=mock_ctx)


def patch_monitoring_service_db_session(mock_db):
    """
    Patch ``app.services.monitoring_service.db_session`` so ``with db_session() as db:``
    yields ``mock_db``.
    """
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_db
    mock_ctx.__exit__.return_value = None
    return patch(
        "app.services.monitoring_service.db_session", return_value=mock_ctx
    )
