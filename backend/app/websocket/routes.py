"""
WebSocket routes for real-time communication.
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from ..utils.logging_config import get_logger
from .manager import manager

logger = get_logger(__name__)
router = APIRouter()


@router.websocket("/ws/progress/{run_id}")
async def websocket_progress_endpoint(
    websocket: WebSocket, run_id: str, user_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time progress tracking.

    Args:
        websocket: WebSocket connection
        run_id: Analysis run ID to track
        user_id: Optional user ID for user-specific updates
    """
    await manager.connect(websocket, run_id=run_id, user_id=user_id)

    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            json.dumps(
                {
                    "type": "connection_established",
                    "run_id": run_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "Connected to progress tracking",
                }
            ),
            websocket,
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (heartbeat, etc.)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)

                if message.get("type") == "ping":
                    # Respond to ping with pong
                    await manager.send_personal_message(
                        json.dumps(
                            {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                        ),
                        websocket,
                    )
                elif message.get("type") == "subscribe":
                    # Handle subscription to additional run IDs
                    additional_run_id = message.get("run_id")
                    if additional_run_id:
                        await manager.connect(websocket, run_id=additional_run_id)

            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await manager.send_personal_message(
                    json.dumps(
                        {
                            "type": "heartbeat",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ),
                    websocket,
                )
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for run: {run_id}")
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        manager.disconnect(websocket, run_id=run_id, user_id=user_id)


@router.websocket("/ws/user/{user_id}")
async def websocket_user_endpoint(websocket: WebSocket, user_id: str):
    """
    WebSocket endpoint for user-specific updates.

    Args:
        websocket: WebSocket connection
        user_id: User ID for user-specific updates
    """
    await manager.connect(websocket, user_id=user_id)

    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            json.dumps(
                {
                    "type": "connection_established",
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "Connected to user updates",
                }
            ),
            websocket,
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)

                if message.get("type") == "ping":
                    # Respond to ping with pong
                    await manager.send_personal_message(
                        json.dumps(
                            {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                        ),
                        websocket,
                    )
                elif message.get("type") == "subscribe_run":
                    # Subscribe to specific run updates
                    run_id = message.get("run_id")
                    if run_id:
                        await manager.connect(websocket, run_id=run_id)

            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await manager.send_personal_message(
                    json.dumps(
                        {
                            "type": "heartbeat",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ),
                    websocket,
                )
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for user: {user_id}")
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        manager.disconnect(websocket, user_id=user_id)


@router.websocket("/ws/collab/{session_id}")
async def websocket_collab_session(websocket: WebSocket, session_id: str):
    """
    Multi-user collaboration room (chat, shared run pointers).
    Clients send JSON: {"type":"message|ping", "payload":{...}}.
    """
    await manager.connect_collab(websocket, session_id)
    try:
        await manager.send_personal_message(
            json.dumps(
                {
                    "type": "collab_joined",
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ),
            websocket,
        )
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await manager.send_personal_message(
                        json.dumps(
                            {
                                "type": "pong",
                                "timestamp": datetime.utcnow().isoformat(),
                            }
                        ),
                        websocket,
                    )
                else:
                    await manager.broadcast_collab(
                        session_id,
                        {
                            "type": msg.get("type", "message"),
                            "payload": msg.get("payload"),
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    )
            except asyncio.TimeoutError:
                await manager.send_personal_message(
                    json.dumps(
                        {
                            "type": "heartbeat",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ),
                    websocket,
                )
    except WebSocketDisconnect:
        logger.info("Collab WebSocket disconnected: %s", session_id)
    finally:
        manager.disconnect_collab(websocket, session_id)


@router.websocket("/ws/broadcast")
async def websocket_broadcast_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for broadcast updates (admin/system messages).
    """
    await manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await manager.send_personal_message(
            json.dumps(
                {
                    "type": "connection_established",
                    "timestamp": datetime.utcnow().isoformat(),
                    "message": "Connected to broadcast updates",
                }
            ),
            websocket,
        )

        # Keep connection alive
        while True:
            try:
                # Wait for messages from client
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                message = json.loads(data)

                if message.get("type") == "ping":
                    # Respond to ping with pong
                    await manager.send_personal_message(
                        json.dumps(
                            {"type": "pong", "timestamp": datetime.utcnow().isoformat()}
                        ),
                        websocket,
                    )

            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                await manager.send_personal_message(
                    json.dumps(
                        {
                            "type": "heartbeat",
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    ),
                    websocket,
                )
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                break

    except WebSocketDisconnect:
        logger.info("Broadcast WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket connection error: {str(e)}")
    finally:
        manager.disconnect(websocket)
