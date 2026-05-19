from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(request: Request) -> dict:
    scheduler = request.app.state.scheduler
    return {
        "status": "healthy",
        "service": "miradesk",
        "scheduler_running": scheduler.running,
    }
