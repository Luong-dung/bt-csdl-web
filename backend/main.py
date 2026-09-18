from fastapi import FastAPI
from config.database import get_db_connection
from routes.auth import router as auth_router
app = FastAPI(title="Esports Tournament API")

app.include_router(auth_router)

@app.get("/")
def check_server():
    return {"status": "ok", "message": "Server backend dang chay ngon lanh!"}

@app.get("/test-db") 
def check_db(): 
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            # Query thử 1 bảng bất kỳ xem MySQL XAMPP có nhận không
            cursor.execute("SELECT COUNT(*) AS total_users FROM users;")
            result = cursor.fetchone()
        conn.close()
        return {"database": "connected", "data": result}
    except Exception as e:
        return {"database": "error", "detail": str(e)}