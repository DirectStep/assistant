from fastapi import APIRouter

from app.api.routes.digests import router as digests_router
from app.api.routes.health import router as health_router
from app.api.routes.settings import router as settings_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.telegram import router as telegram_router

api_router = APIRouter(prefix="/api")
api_router.include_router(health_router)
api_router.include_router(digests_router)
api_router.include_router(tasks_router)
api_router.include_router(settings_router)
api_router.include_router(telegram_router)
