"""
Groups Router — Create groups, manage members, RBAC.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.group import Group, GroupMember, MemberRole
from app.schemas.group import (
    GroupCreate, GroupResponse, GroupDetailResponse,
    AddMember, UpdateRole, MemberResponse,
)
from app.auth.jwt_handler import get_current_user

router = APIRouter(prefix="/groups", tags=["Groups"])


def get_member_role(db: Session, group_id: int, user_id: int) -> str | None:
    """Get a user's role in a group, or None if not a member."""
    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id,
        GroupMember.user_id == user_id,
    ).first()
    return member.role if member else None


def require_admin(db: Session, group_id: int, user_id: int):
    """Raise 403 if user is not an admin of the group."""
    role = get_member_role(db, group_id, user_id)
    if role != MemberRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only group admins can perform this action")


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
def create_group(
    data: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new group. Creator becomes the admin."""
    group = Group(name=data.name, created_by=current_user.id)
    db.add(group)
    db.commit()
    db.refresh(group)

    # Add creator as admin
    member = GroupMember(
        user_id=current_user.id,
        group_id=group.id,
        role=MemberRole.ADMIN,
    )
    db.add(member)
    db.commit()

    return GroupResponse(
        id=group.id,
        name=group.name,
        created_by=group.created_by,
        created_at=group.created_at,
        member_count=1,
    )


@router.post("/dm", response_model=GroupDetailResponse)
def create_dm(
    data: AddMember,  # uses AddMember schema simply because it has `username`
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a DM seamlessly. Fails safely if the username doesn't exist."""
    # 1. Lookup user BEFORE doing anything
    target_user = db.query(User).filter(User.username == data.username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"User '{data.username}' doesn't exist.")

    # 2. Check if trying to DM themselves
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot DM yourself.")

    # 3. Check if DM already exists!
    name1 = f"DM: {current_user.username} & {target_user.username}"
    name2 = f"DM: {target_user.username} & {current_user.username}"
    
    existing_group = db.query(Group).filter((Group.name == name1) | (Group.name == name2)).first()
    if existing_group:
        # If the DM already exists, just return it without creating a new duplicate
        return get_group(existing_group.id, db, current_user)

    # 4. Create group
    group = Group(
        name=name1, 
        created_by=current_user.id
    )
    db.add(group)
    db.commit()
    db.refresh(group)

    # 5. Add both users
    m1 = GroupMember(user_id=current_user.id, group_id=group.id, role=MemberRole.ADMIN)
    m2 = GroupMember(user_id=target_user.id, group_id=group.id, role=MemberRole.WRITE)
    db.add_all([m1, m2])
    db.commit()

    # 6. Return group details
    return get_group(group.id, db, current_user)


@router.get("/me", response_model=List[GroupResponse])
def get_my_groups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all groups the current user is a member of."""
    memberships = db.query(GroupMember).filter(GroupMember.user_id == current_user.id).all()
    groups = []
    for m in memberships:
        group = db.query(Group).filter(Group.id == m.group_id).first()
        if group:
            count = db.query(GroupMember).filter(GroupMember.group_id == group.id).count()
            groups.append(GroupResponse(
                id=group.id, name=group.name, created_by=group.created_by,
                created_at=group.created_at, member_count=count,
            ))
    return groups


@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get group details with member list. Must be a member."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    role = get_member_role(db, group_id, current_user.id)
    if role is None:
        raise HTTPException(status_code=403, detail="You are not a member of this group")

    members_db = db.query(GroupMember).filter(GroupMember.group_id == group_id).all()
    members = []
    for m in members_db:
        user = db.query(User).filter(User.id == m.user_id).first()
        members.append(MemberResponse(
            user_id=m.user_id, username=user.username if user else "unknown",
            role=m.role, joined_at=m.joined_at,
        ))

    return GroupDetailResponse(
        id=group.id, name=group.name, created_by=group.created_by,
        created_at=group.created_at, members=members,
    )


@router.post("/{group_id}/members", response_model=MemberResponse)
def add_member(
    group_id: int,
    data: AddMember,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a member to the group. Only admins can do this."""
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    require_admin(db, group_id, current_user.id)

    # Check if user exists by username
    user = db.query(User).filter(User.username == data.username).first()
    if not user:
        raise HTTPException(status_code=404, detail=f"User '{data.username}' not found")

    # Check if already a member
    existing = db.query(GroupMember).filter(
        GroupMember.group_id == group_id, GroupMember.user_id == user.id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member")

    member = GroupMember(user_id=user.id, group_id=group_id, role=data.role)
    db.add(member)
    db.commit()
    db.refresh(member)

    return MemberResponse(
        user_id=member.user_id, username=user.username,
        role=member.role, joined_at=member.joined_at,
    )


@router.put("/{group_id}/members/{user_id}/role", response_model=MemberResponse)
def update_member_role(
    group_id: int,
    user_id: int,
    data: UpdateRole,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change a member's role. Only admins can do this."""
    require_admin(db, group_id, current_user.id)

    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id, GroupMember.user_id == user_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found in this group")

    member.role = data.role
    db.commit()
    db.refresh(member)

    user = db.query(User).filter(User.id == user_id).first()
    return MemberResponse(
        user_id=member.user_id, username=user.username if user else "unknown",
        role=member.role, joined_at=member.joined_at,
    )


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    group_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove a member from the group. Admin only. Can't remove yourself if you're the only admin."""
    require_admin(db, group_id, current_user.id)

    if user_id == current_user.id:
        admin_count = db.query(GroupMember).filter(
            GroupMember.group_id == group_id, GroupMember.role == MemberRole.ADMIN
        ).count()
        if admin_count <= 1:
            raise HTTPException(status_code=400, detail="Cannot remove the only admin")

    member = db.query(GroupMember).filter(
        GroupMember.group_id == group_id, GroupMember.user_id == user_id
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    db.delete(member)
    db.commit()
