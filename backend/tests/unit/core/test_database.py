"""
Unit tests for database module.
"""

import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.database import (
    check_db_connection,
    close_db,
    get_db,
    get_db_context,
    get_db_info,
    health_check,
    init_db,
)


class TestDatabase:
    """Test database functions."""

    def test_get_db(self):
        """Test getting database session (generator yields session, closes on gen.close())."""
        gen = get_db()
        db = next(gen)
        try:
            assert db is not None
        finally:
            gen.close()

    def test_get_db_context(self):
        """Test database context manager."""
        with get_db_context() as db:
            assert db is not None

    def test_check_db_connection(self):
        """Test checking database connection."""
        result = check_db_connection()
        assert isinstance(result, bool)

    def test_get_db_info(self):
        """Test getting database info."""
        info = get_db_info()
        assert "database_url" in info
        assert "tables" in info
        assert "connection_status" in info

    def test_health_check(self):
        """Test database health check."""
        health = health_check()
        assert "status" in health
        assert "timestamp" in health
