from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Index, func as sa_func, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from config.database import Base

class Role(Base):
    __tablename__ = "roles"
    
    role_id = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(50), nullable=False, unique=True)
    
    users = relationship("User", back_populates="role")

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, index=True)
    role_id = Column(Integer, ForeignKey("roles.role_id", ondelete="RESTRICT"), nullable=False)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    real_name = Column(String(100), default="")
    email = Column(String(100), nullable=False, unique=True)
    avatar_url = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    role = relationship("Role", back_populates="users")
    # Only active (not revoked) assignments grant anything; every checker reads this collection.
    assignments = relationship("RoleAssignment", viewonly=True,
                               primaryjoin="and_(User.user_id == RoleAssignment.user_id, RoleAssignment.revoked_at.is_(None))")
    audit_logs = relationship("AuditLog", back_populates="user")

class Permission(Base):
    __tablename__ = "permissions"
    
    permission_id = Column(Integer, primary_key=True, index=True)
    permission_name = Column(String(100), nullable=False, unique=True)
    description = Column(String(255), nullable=True)

class RoleAssignment(Base):
    __tablename__ = "role_assignments"
    
    assignment_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.role_id", ondelete="CASCADE"), nullable=False)
    scope_type = Column(String(30), nullable=False, default="GLOBAL")
    scope_id = Column(Integer, nullable=True)
    # W47-01: grant/revoke history. Legacy rows keep NULL granted_* (unknown), never backfilled.
    granted_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL", name="fk_role_assignments_granted_by"), nullable=True)
    granted_at = Column(DateTime(timezone=True), nullable=True)
    revoked_by = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL", name="fk_role_assignments_revoked_by"), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    role = relationship("Role")

    __table_args__ = (
        # At most one ACTIVE assignment per user/role/scope; revoked rows stay as history.
        Index("uq_role_assignments_active", "user_id", "role_id", "scope_type",
              sa_func.coalesce(scope_id, 0), unique=True,
              postgresql_where=text("revoked_at IS NULL"), sqlite_where=text("revoked_at IS NULL")),
    )

class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    log_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    resource = Column(String(100), nullable=False)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # W47-02: derived from details by core.audit.record_audit; no FK so history survives deletes.
    tournament_id = Column(Integer, nullable=True)
    resource_id = Column(Integer, nullable=True)

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_tournament_log", "tournament_id", "log_id"),
        Index("ix_audit_logs_resource_log", "resource", "resource_id", "log_id"),
        Index("ix_audit_logs_user_log", "user_id", "log_id"),
    )
