from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import get_settings
from routes.auth import router as auth_router
from routes.team import router as team_router
from routes.catalog import router as catalog_router
from routes.tournaments import router as tournament_router
from routes.registrations import router as registration_router

def create_app() -> FastAPI:
    settings = get_settings()
    
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(team_router)
    app.include_router(catalog_router)
    app.include_router(tournament_router)
    app.include_router(registration_router)

    @app.get("/")
    def check_server():
        return {"status": "ok", "message": "Server backend dang chay ngon lanh!"}

    @app.get("/health")
    def health_check():
        return {"status": "up"}
        
    @app.get("/ready")
    def ready_check():
        return {"status": "ready"}
            
    return app

app = create_app()
