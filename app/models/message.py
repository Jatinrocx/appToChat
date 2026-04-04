"""
💬 Message Model

Stores every message sent in a group chat.

💡 LEARNING NOTES — Message Types:
This answers the assignment question:
"How would you support other message types like audio, documents, etc?"

→ Using a `message_type` column! The message table stores METADATA only.
→ For files (audio, images, docs), the actual file is relayed to recipients.
→ The DB just records: "User X sent an audio file called voice.mp3 at 2pm"

message_type can be:
- "text"     → content has the message text
- "image"    → file_name has the filename, content has optional caption
- "audio"    → file_name has the filename
- "document" → file_name has the filename, content has optional caption
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class MessageType(str, enum.Enum):
    """Supported message types."""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"


class Message(Base):
    """
    A message sent in a group.

    For text messages:
        message_type = "text", content = "Hello!"

    For file messages (relay model):
        message_type = "image", file_name = "photo.jpg",
        file_size = 2048000, content = "Check this out" (optional caption)

    The actual file is NOT stored permanently — it's relayed to recipients
    and they download it to their own systems.
    """
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message_type = Column(String, default=MessageType.TEXT, nullable=False)

    # ── Content ──
    content = Column(Text, nullable=True)       # Text content or caption for files

    # ── File metadata (only for non-text messages) ──
    file_name = Column(String, nullable=True)    # Original filename
    file_size = Column(Integer, nullable=True)   # Size in bytes

    # ── Timestamps ──
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ──
    group = relationship("Group", back_populates="messages")
    sender = relationship("User", back_populates="messages")

    def __repr__(self):
        return f"<Message(id={self.id}, type='{self.message_type}', sender_id={self.sender_id})>"
