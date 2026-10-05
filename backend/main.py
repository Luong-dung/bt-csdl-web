from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import get_settings
from routes.auth import router as auth_router
from routes.team import router as team_router
from config.database import get_db_connection

def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(team_router)

    @app.get("/")
    def check_server():
        return {"status": "ok", "message": "Server backend dang chay ngon lanh!"}

    @app.get("/health")
    def health_check():
        return {"status": "up"}
        
    @app.get("/ready")
    def ready_check():
        # Check DB connection for readiness
        try:
            conn = get_db_connection()
            conn.close()
            return {"status": "ready"}
        except Exception as e:
            return {"status": "not ready", "detail": str(e)}

    @app.get("/test-db") 
    def check_db(): 
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total_users FROM users;")
                result = cursor.fetchone()
            conn.close()
            return {"database": "connected", "data": result}
        except Exception as e:
            return {"database": "error", "detail": str(e)}
            
    return app

app = create_app()