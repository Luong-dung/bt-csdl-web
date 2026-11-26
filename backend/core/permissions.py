"""W48-04: global permissions stored in ``permissions`` and granted to roles via ``role_permissions``.

Only role-wide rights live here. Resource-scoped rules (tournament manager, referee of a tournament,
team manager of a team/organization) depend on relations and stay in their checkers; ADMIN keeps its
shortcut there. The default grants reproduce the role checks used before W48-04 exactly.
"""

CATALOG_MANAGE = "CATALOG_MANAGE"
ORGANIZATION_CREATE = "ORGANIZATION_CREATE"
TOURNAMENT_CREATE = "TOURNAMENT_CREATE"
AUDIT_LOG_VIEW_ALL = "AUDIT_LOG_VIEW_ALL"
ROLE_ASSIGNMENT_MANAGE = "ROLE_ASSIGNMENT_MANAGE"

PERMISSIONS = (
    (CATALOG_MANAGE, "Tạo/sửa/xóa publisher, game, khu vực và quốc gia"),
    (ORGANIZATION_CREATE, "Tạo tổ chức mới"),
    (TOURNAMENT_CREATE, "Tạo giải đấu mới"),
    (AUDIT_LOG_VIEW_ALL, "Xem nhật ký audit toàn hệ thống"),
    (ROLE_ASSIGNMENT_MANAGE, "Cấp/thu hồi vai trò theo phạm vi cho mọi người dùng"),
)

ROLE_PERMISSIONS = {
    "ADMIN": (CATALOG_MANAGE, ORGANIZATION_CREATE, TOURNAMENT_CREATE, AUDIT_LOG_VIEW_ALL, ROLE_ASSIGNMENT_MANAGE),
    "ORGANIZER": (TOURNAMENT_CREATE,),
}
