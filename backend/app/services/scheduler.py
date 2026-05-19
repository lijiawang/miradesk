import asyncio
import logging
import subprocess

from app.repositories.task_repository import TaskRepository
from app.schemas.claude import ClaudeCLIRequest
from app.services.claude_cli import ClaudeCLIService, CommandNotAllowedError

logger = logging.getLogger("uvicorn.error")


class SchedulerService:
    def __init__(
        self,
        repository: TaskRepository,
        claude_cli: ClaudeCLIService,
        poll_seconds: float,
        max_concurrent_tasks: int,
    ) -> None:
        self.repository = repository
        self.claude_cli = claude_cli
        self.poll_seconds = poll_seconds
        self.max_concurrent_tasks = max_concurrent_tasks
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self._running_task_ids: set[int] = set()

    @property
    def running(self) -> bool:
        return self._loop_task is not None and not self._loop_task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._stop_event.clear()
        self._loop_task = asyncio.create_task(self._loop(), name="scheduler-loop")
        logger.warning("scheduler started")

    async def stop(self) -> None:
        self._stop_event.set()
        if self._loop_task:
            await self._loop_task
        logger.warning("scheduler stopped")

    async def _loop(self) -> None:
        while not self._stop_event.is_set():
            capacity = self.max_concurrent_tasks - len(self._running_task_ids)
            if capacity > 0:
                due_tasks = self.repository.list_due_tasks(limit=capacity)
                for task in due_tasks:
                    task_id = int(task["id"])
                    if task_id in self._running_task_ids:
                        continue
                    self.repository.claim_task(task)
                    self._running_task_ids.add(task_id)
                    asyncio.create_task(self._run_task(task), name=f"task-{task_id}")
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.poll_seconds)
            except TimeoutError:
                continue

    async def _run_task(self, task: dict) -> None:
        task_id = int(task["id"])
        run_id = self.repository.create_run(task_id)
        try:
            response = await self.claude_cli.execute(
                ClaudeCLIRequest(
                    command=task["command"],
                    args=task["args"],
                    cli_path=task["cli_path"],
                    timeout=task["timeout"],
                )
            )
            self.repository.complete_run(
                run_id=run_id,
                status="success" if response.success else "failed",
                output=response.output,
                error=response.error,
                return_code=response.return_code,
            )
        except subprocess.TimeoutExpired as exc:
            self.repository.complete_run(
                run_id=run_id,
                status="failed",
                output=None,
                error=f"Task timed out after {exc.timeout} seconds",
                return_code=None,
            )
        except (FileNotFoundError, CommandNotAllowedError, Exception) as exc:
            logger.exception("scheduled task %s failed", task_id)
            self.repository.complete_run(
                run_id=run_id,
                status="failed",
                output=None,
                error=str(exc),
                return_code=None,
            )
        finally:
            self._running_task_ids.discard(task_id)

