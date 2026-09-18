from fastapi import HTTPException, status
from config.database import get_db_connection
from middleware.auth import verify_password, hash_password, create_access_token
from models.auth import UserLogin, UserRegister

def login_user(data: UserLogin):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT user_id, username, password_hash, role_id FROM users WHERE username = %s"
            role = "SELECT role_name FROM roles WHERE role_id = %s"
            cursor.execute(sql, (data.username,))
            user = cursor.fetchone()

            if not user or not verify_password(data.password, user["password_hash"]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Sai tài khoản hoặc mật khẩu"
                )

            cursor.execute(role, (user["role_id"],))
            role_name = cursor.fetchone()

            token = create_access_token({"sub": str(user["user_id"]), "role": role_name["role_name"], "username": user["username"]})
            return {
                "access_token": token,
                "token_type": "bearer",
                "role": role_name["role_name"],
                "username": user["username"]
            }
    finally:
        conn.close()

def register_user(data: UserRegister):
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id FROM users WHERE username = %s OR email = %s", (data.username, data.email))
            if cursor.fetchone():
                raise HTTPException(status_code=400, detail="Username hoặc email đã tồn tại")

            hashed = hash_password(data.password)
            sql = "INSERT INTO users (username, email, password_hash, role_id) VALUES (%s, %s, %s, 'VIEWER')"
            cursor.execute(sql, (data.username, data.email, hashed))
            conn.commit()
            return {"message": "Đăng ký thành công"}
    finally:
        conn.close()