from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import User
from schemas import UserOut, UserUpdate, StatsResponse
from auth import get_current_user

# Router for admin-only operations\
admin_router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_user)])

# Dependency to check admin role
def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")
    return current_user

@admin_router.get("/users", response_model=List[UserOut])
def list_users(
    skip: int = 0,
    limit: int = 100,
    role: Optional[str] = Query(None, description="Filter by role"),
    status: Optional[str] = Query(None, description="Filter by user status"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    List users with optional filters.
    """
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if status:
        query = query.filter(User.status == status)
    users = query.offset(skip).limit(limit).all()
    return users

@admin_router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Retrieve a single user's details.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@admin_router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: str,
    data: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Update user fields like status or role.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(user, field, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@admin_router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Delete a user (hard delete).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return

@admin_router.get("/stats/users", response_model=StatsResponse)
def user_stats(
    period_days: int = Query(30, description="Days back to calculate stats from"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin)
) -> StatsResponse:
    """
    Return user statistics: total, active, disabled, new in period.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=period_days)

    total = db.query(func.count(User.id)).scalar()
    active = db.query(func.count(User.id)).filter(User.status == 'active').scalar()
    disabled = db.query(func.count(User.id)).filter(User.status == 'disabled').scalar()
    new_users = db.query(func.count(User.id)).filter(User.created_at >= since).scalar()

    return StatsResponse(
        total_users=total,
        active_users=active,
        disabled_users=disabled,
        new_users=new_users,
        period_days=period_days
    )
