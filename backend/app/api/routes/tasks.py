from fastapi import APIRouter, HTTPException, Query, Request, status

from app.schemas.tasks import (
    ScheduledTask,
    ScheduledTaskCreate,
    ScheduledTaskUpdate,
    TaskRun,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=ScheduledTask, status_code=status.HTTP_201_CREATED)
async def create_task(payload: ScheduledTaskCreate, request: Request) -> ScheduledTask:
    repository = request.app.state.task_repository
    return ScheduledTask.model_validate(repository.create_task(payload))


@router.get("", response_model=list[ScheduledTask])
async def list_tasks(request: Request) -> list[ScheduledTask]:
    repository = request.app.state.task_repository
    return [ScheduledTask.model_validate(task) for task in repository.list_tasks()]


@router.get("/{task_id}", response_model=ScheduledTask)
async def get_task(task_id: int, request: Request) -> ScheduledTask:
    repository = request.app.state.task_repository
    task = repository.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return ScheduledTask.model_validate(task)


@router.patch("/{task_id}", response_model=ScheduledTask)
async def update_task(
    task_id: int,
    payload: ScheduledTaskUpdate,
    request: Request,
) -> ScheduledTask:
    repository = request.app.state.task_repository
    task = repository.update_task(task_id, payload)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return ScheduledTask.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: int, request: Request) -> None:
    repository = request.app.state.task_repository
    if not repository.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")


@router.post("/{task_id}/run-now", response_model=ScheduledTask)
async def run_task_now(task_id: int, request: Request) -> ScheduledTask:
    repository = request.app.state.task_repository
    task = repository.trigger_now(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return ScheduledTask.model_validate(task)


@router.get("/{task_id}/runs", response_model=list[TaskRun])
async def list_task_runs(
    task_id: int,
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[TaskRun]:
    repository = request.app.state.task_repository
    if repository.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return [TaskRun.model_validate(run) for run in repository.list_runs(task_id, limit)]

