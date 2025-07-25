from typing import Optional
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status
from database import get_db
from models import User
from schemas.auth_schema import AddPassword, AuthBase, AuthLogin, AuthResponse, LoginResponse, PasswordChange, PasswordResetRequest
import bcrypt
import string
import secrets


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies if a given password matches the stored hash."""
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def hash_password(password: str) -> str:
    """Hashes a password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode(), salt)
    return hashed_password.decode()


def create_reset_pin(length: int = 8) -> str:
    """Generates a random reset PIN."""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User with this email not found"
        )
    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=403,
            detail="Incorrect password"
        )
    return user


auth_router = APIRouter(prefix="/auth", tags=["Auth"])


@auth_router.post("/create_password", response_model=AuthResponse)
def add_password(auth: AddPassword, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == auth.email).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(auth.password)
    user.status = "active"
    db.commit()
    db.refresh(user)

    return AuthResponse(
        user_id=user.id,
        status=user.status,
        role=user.role
    )


@auth_router.post("/forgot-password")
async def forgot_password(request: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if user:
        reset_token = create_reset_pin()
        user.password_hash = hash_password(reset_token)
        db.commit()
        print(f"Reset token for {user.email}: {reset_token}")
        # TODO: Send token via email or SMS
    return {"message": "If the user exists, a reset token has been sent."}

@auth_router.post("/access", response_model=LoginResponse)
async def login(form_data: AuthLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, form_data.email, form_data.password)

    return LoginResponse(
        user_id=user.id,
        status=user.status,
        role=user.role,
        name=user.name,
        profile_image=user.personal_image_path,
        email=user.email,
        business_name=user.business_name,
        business_description=user.business_description,
        business_profile_image=user.business_image_path
    )


@auth_router.post("/change-password")
async def change_password(data: PasswordChange, db: Session = Depends(get_db)):
    user = authenticate_user(db, data.old_password, data.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect current password"
        )

    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}
