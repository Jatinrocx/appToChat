"""
Messages Router — File upload (relay) and message history.
"""

import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.group import GroupMember
from app.models.message import Message, MessageType
from app.schemas.message import MessageResponse, MessageHistoryResponse
from app.auth.jwt_handler import get_current_user
from app.config import settings

router = APIRouter(prefix="/messages", tags=["Messages"])


def ensure_upload_dir():
    """Create upload directories if they don't exist."""
    for subdir in ["image", "audio", "document"]:
        os.makedirs(os.path.join(settings.UPLOAD_DIR, subdir), exist_ok=True)


@router.post("/upload", response_model=MessageResponse)
async def upload_file(
    group_id: int = Form(...),
    file: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a file (image, audio, document) to a group.
    The file is stored temporarily for relay to recipients.
    DB stores only metadata.
    """
    # Check membership and write permission
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id,
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")
    if member.role == "read":
        raise HTTPException(status_code=403, detail="Read-only members cannot send files")

    # Determine file type from extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    file_type = None
    for type_name, extensions in settings.ALLOWED_FILE_TYPES.items():
        if ext in extensions:
            file_type = type_name
            break

    if not file_type:
        raise HTTPException(status_code=400, detail=f"File type '{ext}' not supported")

    # Read file content
    content_bytes = await file.read()
    file_size = len(content_bytes)

    if file_size > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large. Max {settings.MAX_FILE_SIZE_MB}MB")

    # Save file temporarily
    ensure_upload_dir()
    unique_name = f"{uuid.uuid4().hex}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, file_type, unique_name)

    with open(file_path, "wb") as f:
        f.write(content_bytes)

    # Save message metadata to DB
    message = Message(
        group_id=group_id,
        sender_id=current_user.id,
        message_type=file_type,
        content=caption,
        file_name=unique_name,
        file_size=file_size,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return MessageResponse(
        id=message.id,
        group_id=message.group_id,
        sender_id=message.sender_id,
        sender_username=current_user.username,
        message_type=message.message_type,
        content=message.content,
        file_name=message.file_name,
        file_size=message.file_size,
        created_at=message.created_at,
    )


@router.get("/{group_id}/history", response_model=MessageHistoryResponse)
def get_message_history(
    group_id: int,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get paginated message history for a group. Must be a member."""
    # Check membership
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == current_user.id,
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    # Count total messages
    total = db.query(Message).filter(Message.group_id == group_id).count()

    # Get paginated messages (newest first)
    offset = (page - 1) * page_size
    messages_db = (
        db.query(Message)
        .filter(Message.group_id == group_id)
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    messages = []
    for m in messages_db:
        sender = db.query(User).filter(User.id == m.sender_id).first()
        messages.append(MessageResponse(
            id=m.id, group_id=m.group_id, sender_id=m.sender_id,
            sender_username=sender.username if sender else "unknown",
            message_type=m.message_type, content=m.content,
            file_name=m.file_name, file_size=m.file_size,
            created_at=m.created_at,
        ))

    return MessageHistoryResponse(
        messages=list(reversed(messages)),  # Oldest first for display
        total=total, page=page, page_size=page_size,
        has_more=(offset + page_size) < total,
    )
