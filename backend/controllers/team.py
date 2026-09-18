from datetime import date
from fastapi import HTTPException
from config.database import get_db_connection
from models.team import MemberAdd, MemberUpdate

def Add_Member(team_id: int, data: MemberAdd, current_user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Kiểm tra quyền Manager
            cursor.execute(
                "SELECT 1 FROM team_memberships WHERE team_id = %s AND user_id = %s AND role_in_team = 'MANAGER' AND status = 'ACTIVE'",
                (team_id, current_user_id)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="Chỉ quản lý hiện tại mới có thể thêm thành viên")

            # Kiểm tra user tồn tại
            cursor.execute("SELECT 1 FROM users WHERE user_id = %s", (data.user_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
            
            # Kiểm tra user đã ở trong team này chưa
            cursor.execute("SELECT 1 FROM team_memberships WHERE user_id = %s AND team_id = %s AND status = 'ACTIVE'", (data.user_id, team_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Người này đang là thành viên của đội")

            # Kiểm tra user có đang ở team khác không
            cursor.execute("SELECT 1 FROM team_memberships WHERE user_id = %s AND status = 'ACTIVE'", (data.user_id,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Người này đang là thành viên ACTIVE của một đội khác")
            
            # Bổ sung joined_date bắt buộc theo DDL
            today = date.today().isoformat()
            sql = "INSERT INTO team_memberships (user_id, team_id, role_in_team, joined_date, status) VALUES (%s, %s, %s, %s, 'ACTIVE')"
            cursor.execute(sql, (data.user_id, team_id, data.role_in_team, today))
            
            # Cập nhật role_id trong bảng users lên PLAYER (nếu thêm vị trí thi đấu)
            sql_role = "UPDATE users SET role_id = (SELECT role_id FROM roles WHERE role_name = 'PLAYER') WHERE user_id = %s"
            cursor.execute(sql_role, (data.user_id,))

        conn.commit()
        return {"message": "Thêm thành viên thành công"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

def Update_Member(team_id: int, user_id: int, data: MemberUpdate, current_user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Kiểm tra quyền Manager
            cursor.execute(
                "SELECT 1 FROM team_memberships WHERE team_id = %s AND user_id = %s AND role_in_team = 'MANAGER' AND status = 'ACTIVE'",
                (team_id, current_user_id)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="Chỉ quản lý hiện tại mới có quyền cập nhật")

            cursor.execute("SELECT 1 FROM team_memberships WHERE user_id = %s AND team_id = %s AND status = 'ACTIVE'", (user_id, team_id))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Thành viên không tồn tại hoặc không ACTIVE trong đội")

            sql = "UPDATE team_memberships SET role_in_team = %s WHERE user_id = %s AND team_id = %s"
            cursor.execute(sql, (data.role_in_team, user_id, team_id))
        conn.commit()
        return {"message": "Cập nhật vị trí thành công"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

def Terminate_Member(team_id: int, user_id: int, current_user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Kiểm tra quyền Manager
            cursor.execute(
                "SELECT 1 FROM team_memberships WHERE team_id = %s AND user_id = %s AND role_in_team = 'MANAGER' AND status = 'ACTIVE'",
                (team_id, current_user_id)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="Chỉ quản lý hiện tại mới có quyền xóa thành viên")

            cursor.execute("SELECT 1 FROM team_memberships WHERE user_id = %s AND team_id = %s AND status = 'ACTIVE'", (user_id, team_id))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="Thành viên không tồn tại trong đội")

            # Không cho phép xóa nếu người này là Manager duy nhất của team
            cursor.execute(
                "SELECT COUNT(*) as total FROM team_memberships WHERE team_id = %s AND role_in_team = 'MANAGER' AND status = 'ACTIVE'",
                (team_id,)
            )
            res = cursor.fetchone()
            total_managers = res["total"] if isinstance(res, dict) else res[0]

            cursor.execute(
                "SELECT 1 FROM team_memberships WHERE user_id = %s AND team_id = %s AND role_in_team = 'MANAGER' AND status = 'ACTIVE'",
                (user_id, team_id)
            )
            is_target_manager = cursor.fetchone()

            if is_target_manager and total_managers <= 1:
                raise HTTPException(status_code=400, detail="Không thể xóa quản lý duy nhất của đội!")

            today = date.today().isoformat()
            sql = "UPDATE team_memberships SET status = 'TERMINATED', left_date = %s WHERE user_id = %s AND team_id = %s"
            cursor.execute(sql, (today, user_id, team_id))

            # Chuyển role tài khoản về VIEWER
            sql_role = "UPDATE users SET role_id = (SELECT role_id FROM roles WHERE role_name = 'VIEWER') WHERE user_id = %s"
            cursor.execute(sql_role, (user_id,))

        conn.commit()
        return {"message": "Thanh lý hợp đồng thành công"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

def Out_Manager(team_id: int, current_user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM team_memberships WHERE team_id = %s AND user_id = %s AND role_in_team = 'MANAGER' AND status = 'ACTIVE'",
                (team_id, current_user_id)
            )
            if not cursor.fetchone():
                raise HTTPException(status_code=403, detail="Bạn không phải quản lý của đội này")

            # Đếm tổng số manager của đội này
            cursor.execute(
                "SELECT COUNT(*) as total FROM team_memberships WHERE team_id = %s AND role_in_team = 'MANAGER' AND status = 'ACTIVE'",
                (team_id,)
            )
            res = cursor.fetchone()
            total_managers = res["total"] if isinstance(res, dict) else res[0]

            if total_managers <= 1:
                raise HTTPException(
                    status_code=400, 
                    detail="Bạn là Quản lý duy nhất. Phải bổ nhiệm thêm một Quản lý khác trước khi rời đội!"
                )

            today = date.today().isoformat()
            sql = "UPDATE team_memberships SET status = 'TERMINATED', left_date = %s WHERE user_id = %s AND team_id = %s"
            cursor.execute(sql, (today, current_user_id, team_id))

            sql_role = "UPDATE users SET role_id = (SELECT role_id FROM roles WHERE role_name = 'VIEWER') WHERE user_id = %s"
            cursor.execute(sql_role, (current_user_id,))

        conn.commit()
        return {"message": "Rời vị trí quản lý thành công"}
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()