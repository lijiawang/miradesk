from fastapi import APIRouter

from app.api.routes import claude, health, tasks

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(claude.router)
api_router.include_router(tasks.router)

