"""
👤 User Model

Represents a user in the system. Each user has:
- A unique email (used for login)
- A unique username (displayed in chat)
- A hashed password (NEVER store plain text passwords!)

💡 LEARNING NOTES:
- Each class below maps to a database TABLE
- Each attribute maps to a COLUMN
- SQLAlchemy handles the SQL for you (CREATE TABLE, INSERT, SELECT, etc.)
- `relationship()` creates virtual links between tables (not actual DB columns)
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    # ── Columns ──
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, nullable=False, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ── Relationships (virtual, not DB columns) ──
    # "Which groups am I a member of?"
    group_memberships = relationship("GroupMember", back_populates="user")
    # "Which messages did I send?"
    messages = relationship("Message", back_populates="sender")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"
