"""Pydantic schemas for messages."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class MessageResponse(BaseModel):
    """Message data returned in API responses"""
    id: int
    group_id: int
    sender_id: int
    sender_username: Optional[str] = None
    message_type: str
    content: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MessageHistoryResponse(BaseModel):
    """Paginated message history"""
    messages: list[MessageResponse]
    total: int
    page: int
    page_size: int
    has_more: bool
