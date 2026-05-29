from fastapi import FastAPI
from src.api.routers.health import router as health_router
from src.api.routers.sessions import router as sessions_router
from src.api.routers.chat import router as chat_router


def create_app() -> FastAPI:
    app = FastAPI(title="Garmin AI Trainer API")

    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(chat_router)

    return app

app = create_app()


