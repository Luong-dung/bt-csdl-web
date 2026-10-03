from datetime import date
from fastapi import HTTPException
from psycopg2 import errors
from config.database import get_db_connection
from models.team import MemberAdd, MemberUpdate, TeamCreate

# Chỉ nâng VIEWER/PLAYER lên TEAM_MANAGER, không hạ quyền ADMIN hay ORGANIZER
SQL_PROMOTE_MANAGER = """
    UPDATE users
    SET role_id = (SELECT role_id FROM roles WHERE role_name = 'TEAM_MANAGER')
    WHERE user_id = %s AND role_id IN (SELECT role_id FROM roles WHERE role_name IN ('VIEWER', 'PLAYER'))
"""

# Chỉ hạ TEAM_MANAGER về PLAYER, không đụng tới ADMIN hay ORGANIZER
SQL_DEMOTE_TO_PLAYER = """
    UPDATE users
    SET role_id = (SELECT role_id FROM roles WHERE role_name = 'PLAYER')
    WHERE user_id = %s AND role_id = (SELECT role_id FROM roles WHERE role_name = 'TEAM_MANAGER')
"""

def Create_Team(data: TeamCreate, user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Kiểm tra trùng lặp tên đội hoặc tag
            cursor.execute("SELECT team_id FROM teams WHERE team_name = %s OR tag = %s", (data.team_name, data.tag))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Tên đội hoặc Tag đã được sử dụng")

            # 2. Kiểm tra xem user có đang tham gia đội nào ACTIVE không
            cursor.execute("SELECT team_id FROM team_memberships WHERE user_id = %s AND status = 'ACTIVE'", (user_id,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Bạn đang là thành viên hoạt động của một đội khác, không thể tạo đội mới")

            # 3. Tạo đội mới
            sql_team = "INSERT INTO teams (team_name, tag) VALUES (%s, %s) RETURNING team_id"
            cursor.execute(sql_team, (data.team_name, data.tag))
            team_row = cursor.fetchone()
            team_id = team_row["team_id"]

            # 4. Gán user làm MANAGER trong bảng team_memberships
            today = date.today().isoformat()
            sql_member = "INSERT INTO team_memberships (team_id, user_id, role_in_team, joined_date, status) VALUES (%s, %s, 'MANAGER', %s, 'ACTIVE')"
            cursor.execute(sql_member, (team_id, user_id, today))

            # 5. Cập nhật role_id trong bảng users lên TEAM_MANAGER
            cursor.execute(SQL_PROMOTE_MANAGER, (user_id,))

        conn.commit()
        return {
            "message": "Tạo đội tuyển thành công",
            "team_id": team_id,
            "team_name": data.team_name,
            "tag": data.tag
        }
    except HTTPException:
        raise
    except errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Bạn đang là thành viên hoạt động của một đội khác, không thể tạo đội mới")
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

def Get_Team(user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT t.team_id, t.team_name, t.tag, tm.role_in_team
                FROM team_memberships tm
                JOIN teams t ON tm.team_id = t.team_id
                WHERE tm.user_id = %s AND tm.role_in_team = 'MANAGER' AND tm.status = 'ACTIVE'
            """
            cursor.execute(sql, (user_id,))
            result = cursor.fetchall()
            return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

def Get_Team_Detail(team_id: int, current_user_id: int):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. Lấy tên team và tag
            cursor.execute("SELECT team_id, team_name, tag FROM teams WHERE team_id = %s", (team_id,))
            team_row = cursor.fetchone()
            if not team_row:
                raise HTTPException(status_code=404, detail="Không tìm thấy đội tuyển")

            team = {
                "team_id": team_row["team_id"] if isinstance(team_row, dict) else team_row[0],
                "team_name": team_row["team_name"] if isinstance(team_row, dict) else team_row[1],
                "tag": team_row["tag"] if isinstance(team_row, dict) else team_row[2],
            }

            # 2. Lấy danh sách thành viên
            sql_members = """
                SELECT
                    u.user_id,
                    u.username,
                    u.real_name,
                    u.email,
                    tm.role_in_team,
                    tm.joined_date
                FROM team_memberships tm
                JOIN users u ON tm.user_id = u.user_id
                WHERE tm.team_id = %s AND tm.status = 'ACTIVE'
                ORDER BY tm.role_in_team = 'MANAGER' DESC
            """
            cursor.execute(sql_members, (team_id,))
            rows = cursor.fetchall()

            members = []
            for r in rows:
                if isinstance(r, dict):
                    members.append(r)
                else:
                    members.append({
                        "user_id": r[0],
                        "username": r[1],
                        "real_name": r[2],
                        "email": r[3],
                        "role_in_team": r[4],
                        "joined_date": str(r[5])
                    })

            # Chỉ quản lý của đội mới được xem email thành viên
            cursor.execute(
                "SELECT 1 FROM team_memberships WHERE team_id = %s AND user_id = %s AND role_in_team = 'MANAGER' AND status = 'ACTIVE'",
                (team_id, current_user_id)
            )
            if not cursor.fetchone():
                for m in members:
                    m.pop("email", None)

            team["members"] = members
            team["total_members"] = len(members)
            return team
    finally:
        conn.close()

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
            cursor.execute("SELECT user_id FROM users WHERE username = %s", (data.username,))
            user_row = cursor.fetchone()
            if not user_row:
                raise HTTPException(status_code=404, detail="Người dùng không tồn tại")
            user_id = user_row["user_id"] if isinstance(user_row, dict) else user_row[0]

            # Kiểm tra user đã ở trong team này chưa
            cursor.execute("SELECT 1 FROM team_memberships WHERE user_id = %s AND team_id = %s AND status = 'ACTIVE'", (user_id, team_id))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Người này đang là thành viên của đội")

            # Kiểm tra user có đang ở team khác không
            cursor.execute("SELECT 1 FROM team_memberships WHERE user_id = %s AND status = 'ACTIVE'", (user_id,))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Người này đang là thành viên ACTIVE của một đội khác")

            # Bổ sung joined_date bắt buộc theo DDL
            today = date.today().isoformat()
            sql = "INSERT INTO team_memberships (user_id, team_id, role_in_team, joined_date, status) VALUES (%s, %s, %s, %s, 'ACTIVE')"
            cursor.execute(sql, (user_id, team_id, data.role_in_team, today))

            # Cập nhật role_id trong bảng users
            if data.role_in_team == 'MANAGER':
                cursor.execute(SQL_PROMOTE_MANAGER, (user_id,))
            else:
                # Nâng VIEWER lên PLAYER, không hạ quyền ADMIN hay ORGANIZER
                sql_role = """
                    UPDATE users
                    SET role_id = (SELECT role_id FROM roles WHERE role_name = 'PLAYER')
                    WHERE user_id = %s AND role_id = (SELECT role_id FROM roles WHERE role_name = 'VIEWER')
                """
                cursor.execute(sql_role, (user_id,))

        conn.commit()
        return {"message": "Thêm thành viên thành công"}
    except HTTPException:
        raise
    except errors.UniqueViolation:
        conn.rollback()
        raise HTTPException(status_code=400, detail="Người này đang là thành viên ACTIVE của một đội khác")
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

            # Lấy thông tin thành viên hiện tại trong team
            cursor.execute(
                "SELECT role_in_team FROM team_memberships WHERE user_id = %s AND team_id = %s AND status = 'ACTIVE'",
                (user_id, team_id)
            )
            target_membership = cursor.fetchone()
            if not target_membership:
                raise HTTPException(status_code=404, detail="Thành viên không tồn tại hoặc không ACTIVE trong đội")

            old_role = target_membership["role_in_team"] if isinstance(target_membership, dict) else target_membership[0]

            # Nếu thành viên đang là MANAGER và muốn chuyển sang vị trí khác (không phải MANAGER)
            if old_role == 'MANAGER' and data.role_in_team != 'MANAGER':
                cursor.execute(
                    "SELECT COUNT(*) as total FROM team_memberships WHERE team_id = %s AND role_in_team = 'MANAGER' AND status = 'ACTIVE'",
                    (team_id,)
                )
                res = cursor.fetchone()
                total_managers = res["total"] if isinstance(res, dict) else res[0]
                if total_managers <= 1:
                    raise HTTPException(
                        status_code=400,
                        detail="Đây là Quản lý duy nhất của đội! Cần bổ nhiệm thêm Quản lý khác trước khi đổi vai trò."
                    )

            sql = "UPDATE team_memberships SET role_in_team = %s WHERE user_id = %s AND team_id = %s"
            cursor.execute(sql, (data.role_in_team, user_id, team_id))

            # Đồng bộ role_id trong bảng users
            if data.role_in_team == 'MANAGER':
                cursor.execute(SQL_PROMOTE_MANAGER, (user_id,))
            elif old_role == 'MANAGER':
                cursor.execute(SQL_DEMOTE_TO_PLAYER, (user_id,))

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

            if user_id == current_user_id:
                raise HTTPException(
                    status_code=400,
                    detail="Không thể tự thanh lý hợp đồng của chính mình! Vui lòng dùng chức năng 'Rút Khỏi Ghế Manager'."
                )

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

            # Chuyển role tài khoản về VIEWER nếu đang là PLAYER hoặc TEAM_MANAGER
            sql_role = """
                UPDATE users
                SET role_id = (SELECT role_id FROM roles WHERE role_name = 'VIEWER')
                WHERE user_id = %s AND role_id IN (SELECT role_id FROM roles WHERE role_name IN ('PLAYER', 'TEAM_MANAGER'))
            """
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

            sql_role = """
                UPDATE users
                SET role_id = (SELECT role_id FROM roles WHERE role_name = 'VIEWER')
                WHERE user_id = %s AND role_id = (SELECT role_id FROM roles WHERE role_name = 'TEAM_MANAGER')
            """
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
