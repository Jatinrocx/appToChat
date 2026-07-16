"""
👥 Group & GroupMember Models

Group: A chat room/group (like a WhatsApp group)
GroupMember: The join table that connects Users to Groups WITH a role.

💡 LEARNING NOTES — RBAC (Role-Based Access Control):
- Each member has a ROLE in the group: "admin", "write", or "read"
- Admin:  Can send messages, add/remove members, change roles
- Write:  Can send messages and view chat
- Read:   Can only view chat (read-only, can't send messages)

This answers the assignment question:
"How can we separate the Admin, Read, or Write members in the group?"
→ Using a `role` column in the GroupMember table!
"""

from datetime import datetime, timezone
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class MemberRole(str, enum.Enum):
    """The three roles a group member can have."""
    ADMIN = "admin"
    WRITE = "write"
    READ = "read"


class Group(Base):
    """A chat group/room."""
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ──
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="group", cascade="all, delete-orphan")
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<Group(id={self.id}, name='{self.name}')>"


class GroupMember(Base):
    """
    Join table: which users are in which groups, and with what role.

    This is the KEY table for RBAC!

    Example rows:
    | user_id | group_id | role   |
    |---------|----------|--------|
    | 1       | 1        | admin  |  ← Creator of the group
    | 2       | 1        | write  |  ← Can send messages
    | 3       | 1        | read   |  ← Can only view
    """
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    role = Column(String, default=MemberRole.WRITE, nullable=False)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relationships ──
    user = relationship("User", back_populates="group_memberships")
    group = relationship("Group", back_populates="members")

    def __repr__(self):
        return f"<GroupMember(user_id={self.user_id}, group_id={self.group_id}, role='{self.role}')>"
