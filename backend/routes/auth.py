from fastapi import APIRouter, Depends
from models.auth import UserLogin, UserRegister, TokenResponse
from controllers.auth import login_user, register_user
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

@router.post("/register")
def register(data: UserRegister):
    return register_user(data)

@router.post("/login", response_model=TokenResponse)
def login(data: UserLogin):
    return login_user(data)

@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return user