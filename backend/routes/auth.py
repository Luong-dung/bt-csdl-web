from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from config.database import get_db
from core.security import create_access_token, hash_password, verify_password
from middleware.auth import get_current_user
from modules.identity.models import Role, User

router = APIRouter(prefix="/api/v1/auth", tags=["Identity"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    real_name: str = Field(default="", max_length=100)


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where((User.username == data.username) | (User.email == data.email)))
    if exists:
        raise HTTPException(status_code=409, detail="Username hoặc email đã tồn tại")
    role = db.scalar(select(Role).where(Role.role_name == "VIEWER"))
    if role is None:
        role = Role(role_name="VIEWER")
        db.add(role)
        db.flush()
    user = User(
        username=data.username,
        email=data.email,
        real_name=data.real_name,
        password_hash=hash_password(data.password),
        role_id=role.role_id,
    )
    db.add(user)
    db.commit()
    return {"message": "Đăng ký thành công", "user_id": user.user_id}


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if user is None or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Sai tài khoản hoặc mật khẩu")
    return {
        "access_token": create_access_token({"sub": str(user.user_id)}),
        "token_type": "bearer",
        "user": {"id": user.user_id, "username": user.username, "role": user.role.role_name},
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.user_id, "username": user.username, "email": user.email, "role": user.role.role_name}
