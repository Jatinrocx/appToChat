"""
WebSocket Handler — The real-time endpoint.

Handles:
- Text messages
- Typing indicators (ephemeral, not saved to DB)
- Online/offline notifications
- File message notifications

This answers: "How do we check if someone is typing?"
-> Client sends {"type": "typing_start"} or {"type": "typing_stop"} via WebSocket.
   Server broadcasts to other group members. These are ephemeral (not saved to DB).
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models.user import User
from app.models.group import GroupMember
from app.models.message import Message, MessageType
from app.auth.jwt_handler import decode_token
from app.websocket.manager import manager

router = APIRouter()


def get_user_from_token(token: str, db: Session) -> User | None:
    """Verify JWT token and return the user. Returns None if invalid."""
    try:
        payload = decode_token(token)
        user_id = int(payload.get("sub"))
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None


@router.websocket("/ws/{group_id}")
async def websocket_endpoint(websocket: WebSocket, group_id: int):
    """
    Main WebSocket endpoint.

    Connection: ws://host/ws/{group_id}?token=JWT_TOKEN

    Message types the client can send:
        {"type": "text_message", "content": "Hello!"}
        {"type": "typing_start"}
        {"type": "typing_stop"}

    Message types the server broadcasts:
        {"type": "text_message", "sender_id": 1, "sender_username": "rahul", "content": "Hello!", ...}
        {"type": "typing", "user_id": 1, "username": "rahul", "is_typing": true}
        {"type": "user_joined", "user_id": 1, "username": "rahul"}
        {"type": "user_left", "user_id": 1, "username": "rahul"}
        {"type": "file_message", "sender_id": 1, ...}
        {"type": "online_users", "users": [{"id": 1, "username": "rahul"}, ...]}
    """
    # Get token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    # Verify token and get user
    db = SessionLocal()
    try:
        user = get_user_from_token(token, db)
        if not user:
            await websocket.close(code=4001, reason="Invalid token")
            return

        # Check group membership
        member = db.query(GroupMember).filter(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user.id,
        ).first()
        if not member:
            await websocket.close(code=4003, reason="Not a member of this group")
            return

        user_id = user.id
        username = user.username
        user_role = member.role
    finally:
        db.close()

    # Connect
    await manager.connect(websocket, user_id, group_id)

    # Notify group that user joined
    await manager.broadcast_to_group(group_id, {
        "type": "user_joined",
        "user_id": user_id,
        "username": username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, exclude_user_id=user_id)

    # Send online users list to the new connection
    online_ids = manager.get_online_users(group_id)
    db = SessionLocal()
    try:
        online_users = []
        for uid in online_ids:
            u = db.query(User).filter(User.id == uid).first()
            if u:
                online_users.append({"id": u.id, "username": u.username})
    finally:
        db.close()

    await manager.send_to_user(user_id, group_id, {
        "type": "online_users",
        "users": online_users,
    })

    # Listen for messages
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "")

            if msg_type == "text_message":
                await handle_text_message(data, user_id, username, user_role, group_id)

            elif msg_type == "typing_start":
                manager.set_typing(user_id, group_id, True)
                await manager.broadcast_to_group(group_id, {
                    "type": "typing",
                    "user_id": user_id,
                    "username": username,
                    "is_typing": True,
                }, exclude_user_id=user_id)

            elif msg_type == "typing_stop":
                manager.set_typing(user_id, group_id, False)
                await manager.broadcast_to_group(group_id, {
                    "type": "typing",
                    "user_id": user_id,
                    "username": username,
                    "is_typing": False,
                }, exclude_user_id=user_id)

            elif msg_type == "file_message":
                # The REST API already saved the file and DB record.
                # Just broadcast the notification to others in the group.
                await manager.broadcast_to_group(group_id, {
                    "type": "file_message",
                    "sender_id": user_id,
                    "sender_username": username,
                    "content": data.get("content"),
                    "message_type": data.get("message_type"),
                    "file_name": data.get("file_name"),
                    "file_size": data.get("file_size"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

    except WebSocketDisconnect:
        manager.disconnect(user_id, group_id)
        await manager.broadcast_to_group(group_id, {
            "type": "user_left",
            "user_id": user_id,
            "username": username,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        manager.disconnect(user_id, group_id)


async def handle_text_message(data: dict, user_id: int, username: str, role: str, group_id: int):
    """Process and broadcast a text message."""
    # Read-only users can't send messages
    if role == "read":
        await manager.send_to_user(user_id, group_id, {
            "type": "error",
            "message": "You have read-only access in this group",
        })
        return

    content = data.get("content", "").strip()
    if not content:
        return

    # Save to database
    db = SessionLocal()
    try:
        message = Message(
            group_id=group_id,
            sender_id=user_id,
            message_type=MessageType.TEXT,
            content=content,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        msg_id = message.id
        created_at = message.created_at
    finally:
        db.close()

    # Stop typing indicator
    manager.set_typing(user_id, group_id, False)

    # Broadcast to group (including sender for confirmation)
    await manager.broadcast_to_group(group_id, {
        "type": "text_message",
        "id": msg_id,
        "sender_id": user_id,
        "sender_username": username,
        "content": content,
        "timestamp": created_at.isoformat() if created_at else datetime.now(timezone.utc).isoformat(),
    })
