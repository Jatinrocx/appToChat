"""Pydantic schemas for group operations."""

from pydantic import BaseModel, field_validator
from datetime import datetime
from typing import Optional, List

class GroupCreate(BaseModel):
    """Request body for POST /groups"""
    name: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError("Group name must be at least 2 characters")
        return v.strip()

class AddMember(BaseModel):
    """Request body for POST /groups/{id}/members"""
    username: str
    role: str = "write"  # admin, write, or read

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ("admin", "write", "read"):
            raise ValueError("Role must be 'admin', 'write', or 'read'")
        return v


class UpdateRole(BaseModel):
    """Request body for PUT /groups/{id}/members/{user_id}/role"""
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ("admin", "write", "read"):
            raise ValueError("Role must be 'admin', 'write', or 'read'")
        return v

class MemberResponse(BaseModel):
    """A member in a group"""
    user_id: int
    username: str
    role: str
    joined_at: Optional[datetime] = None


class GroupResponse(BaseModel):
    """Group data returned in API responses"""
    id: int
    name: str
    created_by: int
    created_at: Optional[datetime] = None
    member_count: Optional[int] = 0

    class Config:
        from_attributes = True


class GroupDetailResponse(BaseModel):
    """Group with members list"""
    id: int
    name: str
    created_by: int
    created_at: Optional[datetime] = None
    members: List[MemberResponse] = []
