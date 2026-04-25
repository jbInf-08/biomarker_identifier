"""
WebSocket module for real-time communication.
"""

from .manager import ConnectionManager, manager
from .routes import router

__all__ = ["manager", "ConnectionManager", "router"]
