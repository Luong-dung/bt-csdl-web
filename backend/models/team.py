from pydantic import BaseModel

class MemberAdd(BaseModel):
    user_id: int
    role_in_team: str  # ("PLAYER", "MANAGER", "SUB", "AD_CARRY", "SUPPORT", "MID", "DS_LANE", "JUNGLE")
class MemberUpdate(BaseModel):
    user_id: int
    role_in_team: str  # ("PLAYER", "MANAGER", "SUB", "AD_CARRY", "SUPPORT", "MID", "DS_LANE", "JUNGLE")
class MemberTerminate(BaseModel):
    user_id: int

    

