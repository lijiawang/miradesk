from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.utils import truncate
from app.repositories.task_repository import TaskRepository
from app.services.claude_cli import ClaudeCLIService
from app.services.scheduler import SchedulerService

configure_logging()
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task_repository = TaskRepository(
        database_path=settings.database_path,
        default_cli_path=settings.default_cli_path,
    )
    task_repository.init_db()

    claude_cli = ClaudeCLIService(settings=settings)
    scheduler = SchedulerService(
        repository=task_repository,
        claude_cli=claude_cli,
        poll_seconds=settings.scheduler_poll_seconds,
        max_concurrent_tasks=settings.scheduler_max_concurrent_tasks,
    )

    app.state.task_repository = task_repository
    app.state.claude_cli = claude_cli
    app.state.scheduler = scheduler

    await scheduler.start()
    logger.warning("miradesk started")
    try:
        yield
    finally:
        await scheduler.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="Local web API for controlling Claude CLI.",
        version=settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_http_requests(request: Request, call_next):
        body = await request.body()

        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        request = Request(request.scope, receive)
        body_preview = truncate(body.decode("utf-8", errors="replace")) if body else ""
        logger.warning("HTTP %s %s", request.method, request.url.path)
        if body_preview:
            logger.warning("HTTP body preview: %s", body_preview)
        return await call_next(request)

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def api_index() -> dict:
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health",
        }

    return app


app = create_app()
