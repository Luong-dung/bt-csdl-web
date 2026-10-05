from fastapi import Depends, HTTPException, status
from typing import List, Optional
from sqlalchemy.orm import Session
from config.database import get_db
from modules.identity.models import User, RoleAssignment
from fastapi.security import OAuth2PasswordBearer
import jwt
from config.settings import get_settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
settings = get_settings()

SECRET_KEY = "supersecretkey"  # TODO: move to settings
ALGORITHM = "HS256"

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

def require_permission(required_role: str, required_scope: Optional[str] = None):
    """
    Dependency to check if the user has a specific role, optionally constrained by a scope.
    Example: require_permission("TEAM_MANAGER", scope="TEAM_123")
    """
    def permission_checker(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
        # 1. System Admin has access to everything
        if current_user.role.role_name == "SYSTEM_ADMIN":
            return current_user
            
        # 2. Check specific role assignments
        assignments = db.query(RoleAssignment).filter(RoleAssignment.user_id == current_user.user_id).all()
        
        has_permission = False
        for assignment in assignments:
            # Note: We'd typically join with Role to get the role_name of the assignment
            # For simplicity, assuming we fetch it or it's eager loaded, but let's query it
            role_assigned = assignment.role # assuming relationship is set up
            if role_assigned and role_assigned.role_name == required_role:
                if required_scope is None or assignment.scope == required_scope or assignment.scope == "GLOBAL":
                    has_permission = True
                    break
        
        # 3. Check base role (legacy or simple fallback)
        if current_user.role.role_name == required_role and not required_scope:
            has_permission = True
            
        if not has_permission:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
        
    return permission_checker
