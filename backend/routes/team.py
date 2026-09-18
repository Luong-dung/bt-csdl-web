from fastapi import APIRouter, Depends
from models.team import MemberAdd, MemberUpdate
from controllers.team import (
    Add_Member,
    Update_Member,
    Terminate_Member,
    Out_Manager
)
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/v1/team", tags=["Teams"])

# Các route tĩnh đưa lên đầu
@router.get("/me")
def get_me(user: dict = Depends(get_current_user)):
    return user

@router.post("/{team_id}/members")
def add_member(team_id: int, data: MemberAdd, user: dict = Depends(get_current_user)):
    user_id = int(user.get("user_id") or user.get("sub"))
    return Add_Member(team_id, data, user_id)

@router.put("/{team_id}/members/{user_id}")
def update_member(team_id: int, user_id: int, data: MemberUpdate, user: dict = Depends(get_current_user)):
    current_user_id = int(user.get("user_id") or user.get("sub"))
    return Update_Member(team_id, user_id, data, current_user_id)

@router.delete("/{team_id}/members/{user_id}")
def terminate_member(team_id: int, user_id: int, user: dict = Depends(get_current_user)):
    current_user_id = int(user.get("user_id") or user.get("sub"))
    return Terminate_Member(team_id, user_id, current_user_id)

@router.post("/{team_id}/manager/out")
def out_manager(team_id: int, user: dict = Depends(get_current_user)):
    current_user_id = int(user.get("user_id") or user.get("sub"))
    return Out_Manager(team_id, current_user_id)