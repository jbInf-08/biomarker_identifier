"""
Unit tests for WebSocket manager module.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.websocket.manager import ConnectionManager, manager


class TestConnectionManager:
    """Test ConnectionManager class."""

    def test_init(self):
        """Test ConnectionManager initialization."""
        cm = ConnectionManager()
        assert cm.active_connections == {}
        assert cm.user_connections == {}

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connecting a WebSocket."""
        cm = ConnectionManager()
        websocket = AsyncMock()
        websocket.accept = AsyncMock()

        await cm.connect(websocket, run_id="test_run", user_id="test_user")

        assert "test_run" in cm.active_connections
        assert "test_user" in cm.user_connections
        websocket.accept.assert_called_once()

    def test_disconnect(self):
        """Test disconnecting a WebSocket."""
        cm = ConnectionManager()
        websocket = MagicMock()

        cm.active_connections["test_run"] = {websocket}
        cm.user_connections["test_user"] = {websocket}

        cm.disconnect(websocket, run_id="test_run", user_id="test_user")

        assert "test_run" not in cm.active_connections
        assert "test_user" not in cm.user_connections

    @pytest.mark.asyncio
    async def test_send_personal_message(self):
        """Test sending personal message."""
        cm = ConnectionManager()
        websocket = AsyncMock()
        websocket.send_text = AsyncMock()

        await cm.send_personal_message("test message", websocket)

        websocket.send_text.assert_called_once_with("test message")

    @pytest.mark.asyncio
    async def test_send_to_run(self):
        """Test sending message to run."""
        cm = ConnectionManager()
        websocket = AsyncMock()
        websocket.send_text = AsyncMock()

        cm.active_connections["test_run"] = {websocket}

        await cm.send_to_run("test_run", {"type": "test"})

        websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_to_user(self):
        """Test sending message to user."""
        cm = ConnectionManager()
        websocket = AsyncMock()
        websocket.send_text = AsyncMock()

        cm.user_connections["test_user"] = {websocket}

        await cm.send_to_user("test_user", {"type": "test"})

        websocket.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast(self):
        """Test broadcasting message."""
        cm = ConnectionManager()
        websocket1 = AsyncMock()
        websocket2 = AsyncMock()
        websocket1.send_text = AsyncMock()
        websocket2.send_text = AsyncMock()

        cm.active_connections["test_run"] = {websocket1}
        cm.user_connections["test_user"] = {websocket2}

        await cm.broadcast({"type": "test"})

        websocket1.send_text.assert_called_once()
        websocket2.send_text.assert_called_once()

    def test_get_connection_count(self):
        """Test getting connection count."""
        cm = ConnectionManager()
        websocket1 = MagicMock()
        websocket2 = MagicMock()

        cm.active_connections["test_run"] = {websocket1}
        cm.user_connections["test_user"] = {websocket2}

        count = cm.get_connection_count()
        assert count == 2

    def test_get_run_connection_count(self):
        """Test getting run connection count."""
        cm = ConnectionManager()
        websocket = MagicMock()

        cm.active_connections["test_run"] = {websocket}

        count = cm.get_run_connection_count("test_run")
        assert count == 1

        count = cm.get_run_connection_count("nonexistent")
        assert count == 0


class TestGlobalManager:
    """Test global manager instance."""

    def test_manager_exists(self):
        """Test that global manager exists."""
        assert manager is not None
        assert isinstance(manager, ConnectionManager)
