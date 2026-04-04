"""
WebSocket Connection Manager

Tracks all active WebSocket connections, organized by group.
Handles broadcasting messages to all members of a group.

This answers: "What are you using for implementing WebSockets?"
-> FastAPI's native WebSocket support (built on Starlette + websockets library)
"""

from fastapi import WebSocket
from typing import Dict, List, Set
import json


class ConnectionManager:
    """
    Manages active WebSocket connections.

    Structure:
        active_connections = {
            group_id: {
                user_id: WebSocket,
                user_id: WebSocket,
            }
        }

        typing_users = {
            group_id: {user_id, user_id, ...}
        }
    """

    def __init__(self):
        # {group_id: {user_id: websocket}}
        self.active_connections: Dict[int, Dict[int, WebSocket]] = {}
        # {group_id: set of user_ids currently typing}
        self.typing_users: Dict[int, Set[int]] = {}

    async def connect(self, websocket: WebSocket, user_id: int, group_id: int):
        """Accept a WebSocket connection and register it."""
        await websocket.accept()

        if group_id not in self.active_connections:
            self.active_connections[group_id] = {}

        self.active_connections[group_id][user_id] = websocket

    def disconnect(self, user_id: int, group_id: int):
        """Remove a WebSocket connection."""
        if group_id in self.active_connections:
            self.active_connections[group_id].pop(user_id, None)
            if not self.active_connections[group_id]:
                del self.active_connections[group_id]

        # Also remove from typing
        if group_id in self.typing_users:
            self.typing_users[group_id].discard(user_id)

    async def broadcast_to_group(self, group_id: int, message: dict, exclude_user_id: int = None):
        """Send a message to all connected members of a group."""
        if group_id not in self.active_connections:
            return

        disconnected = []
        for user_id, ws in self.active_connections[group_id].items():
            if user_id == exclude_user_id:
                continue
            try:
                await ws.send_json(message)
            except Exception:
                disconnected.append(user_id)

        # Cleanup dead connections
        for uid in disconnected:
            self.disconnect(uid, group_id)

    async def send_to_user(self, user_id: int, group_id: int, message: dict):
        """Send a message to a specific user in a group."""
        if group_id in self.active_connections:
            ws = self.active_connections[group_id].get(user_id)
            if ws:
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect(user_id, group_id)

    def get_online_users(self, group_id: int) -> List[int]:
        """Get list of user IDs currently connected to a group."""
        if group_id in self.active_connections:
            return list(self.active_connections[group_id].keys())
        return []

    def set_typing(self, user_id: int, group_id: int, is_typing: bool):
        """Track typing status for a user in a group."""
        if group_id not in self.typing_users:
            self.typing_users[group_id] = set()

        if is_typing:
            self.typing_users[group_id].add(user_id)
        else:
            self.typing_users[group_id].discard(user_id)

    def get_typing_users(self, group_id: int) -> Set[int]:
        """Get set of user IDs currently typing in a group."""
        return self.typing_users.get(group_id, set())


# Single global instance shared across the app
manager = ConnectionManager()
