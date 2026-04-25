"""
WebSocket collaboration scaffolding.

This module provides a minimal FastAPI router and connection manager for
real-time collaboration features described in Weeks 5–6. It does not attempt
to implement full collaborative editing, but establishes the message types and
session management building blocks.
"""

from typing import Dict, List, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class CollaborationConnectionManager:
    """Basic connection manager for collaboration sessions."""

    def __init__(self) -> None:
        # session_id -> set of WebSocket connections
        self.active_sessions: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_sessions.setdefault(session_id, set()).add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        if session_id in self.active_sessions:
            self.active_sessions[session_id].discard(websocket)
            if not self.active_sessions[session_id]:
                del self.active_sessions[session_id]

    async def broadcast(self, session_id: str, message: Dict) -> None:
        """Broadcast a JSON message to all participants in a session."""
        for connection in list(self.active_sessions.get(session_id, [])):
            await connection.send_json(message)


manager = CollaborationConnectionManager()


@router.websocket("/ws/collab/{session_id}")
async def collab_endpoint(websocket: WebSocket, session_id: str) -> None:
    """
    WebSocket endpoint for collaboration sessions.

    Message payloads are expected to be JSON with a `type` field, for example:
    - {"type": "presence", "user": "..."}
    - {"type": "config_update", "payload": {...}}
    - {"type": "comment", "text": "..."}
    """
    await manager.connect(session_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Echo to all collaborators in the same session
            await manager.broadcast(session_id, data)
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
