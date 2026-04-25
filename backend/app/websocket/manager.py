"""
WebSocket connection manager for real-time progress tracking.
"""

import asyncio
import json
from typing import Dict, List, Set

from fastapi import WebSocket, WebSocketDisconnect

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        # Store active connections by run_id
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Store connections by user_id for general updates
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        # Collaboration sessions (multi-user shared rooms)
        self.collab_rooms: Dict[str, Set[WebSocket]] = {}

    async def connect(
        self, websocket: WebSocket, run_id: str = None, user_id: str = None
    ):
        """Accept a WebSocket connection and register it."""
        await websocket.accept()

        if run_id:
            if run_id not in self.active_connections:
                self.active_connections[run_id] = set()
            self.active_connections[run_id].add(websocket)
            logger.info(f"WebSocket connected for run: {run_id}")

        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(websocket)
            logger.info(f"WebSocket connected for user: {user_id}")

    def disconnect(self, websocket: WebSocket, run_id: str = None, user_id: str = None):
        """Remove a WebSocket connection."""
        if run_id and run_id in self.active_connections:
            self.active_connections[run_id].discard(websocket)
            if not self.active_connections[run_id]:
                del self.active_connections[run_id]
            logger.info(f"WebSocket disconnected for run: {run_id}")

        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(websocket)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
            logger.info(f"WebSocket disconnected for user: {user_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {str(e)}")

    async def send_to_run(self, run_id: str, message: dict):
        """Send a message to all connections for a specific run."""
        if run_id in self.active_connections:
            message_str = json.dumps(message)
            disconnected = set()

            for websocket in self.active_connections[run_id]:
                try:
                    await websocket.send_text(message_str)
                except Exception as e:
                    logger.error(f"Failed to send message to run {run_id}: {str(e)}")
                    disconnected.add(websocket)

            # Remove disconnected connections
            for websocket in disconnected:
                self.active_connections[run_id].discard(websocket)

    async def send_to_user(self, user_id: str, message: dict):
        """Send a message to all connections for a specific user."""
        if user_id in self.user_connections:
            message_str = json.dumps(message)
            disconnected = set()

            for websocket in self.user_connections[user_id]:
                try:
                    await websocket.send_text(message_str)
                except Exception as e:
                    logger.error(f"Failed to send message to user {user_id}: {str(e)}")
                    disconnected.add(websocket)

            # Remove disconnected connections
            for websocket in disconnected:
                self.user_connections[user_id].discard(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a message to all active connections."""
        message_str = json.dumps(message)
        all_connections = set()

        # Collect all connections
        for connections in self.active_connections.values():
            all_connections.update(connections)
        for connections in self.user_connections.values():
            all_connections.update(connections)

        # Send to all connections
        disconnected = set()
        for websocket in all_connections:
            try:
                await websocket.send_text(message_str)
            except Exception as e:
                logger.error(f"Failed to broadcast message: {str(e)}")
                disconnected.add(websocket)

        # Clean up disconnected connections
        for websocket in disconnected:
            for connections in self.active_connections.values():
                connections.discard(websocket)
            for connections in self.user_connections.values():
                connections.discard(websocket)

    def get_connection_count(self) -> int:
        """Get the total number of active connections."""
        total = 0
        for connections in self.active_connections.values():
            total += len(connections)
        for connections in self.user_connections.values():
            total += len(connections)
        return total

    def get_run_connection_count(self, run_id: str) -> int:
        """Get the number of connections for a specific run."""
        return len(self.active_connections.get(run_id, set()))

    async def connect_collab(self, websocket: WebSocket, session_id: str):
        """Shared analysis / co-editing room."""
        await websocket.accept()
        if session_id not in self.collab_rooms:
            self.collab_rooms[session_id] = set()
        self.collab_rooms[session_id].add(websocket)
        logger.info("WebSocket collaboration session: %s", session_id)

    def disconnect_collab(self, websocket: WebSocket, session_id: str):
        if session_id in self.collab_rooms:
            self.collab_rooms[session_id].discard(websocket)
            if not self.collab_rooms[session_id]:
                del self.collab_rooms[session_id]
            logger.info("WebSocket collab left: %s", session_id)

    async def broadcast_collab(self, session_id: str, message: dict):
        if session_id not in self.collab_rooms:
            return
        message_str = json.dumps(message)
        dead: Set[WebSocket] = set()
        for ws in self.collab_rooms[session_id]:
            try:
                await ws.send_text(message_str)
            except Exception as e:
                logger.error("collab send failed: %s", e)
                dead.add(ws)
        for ws in dead:
            self.collab_rooms[session_id].discard(ws)


# Global connection manager instance
manager = ConnectionManager()
