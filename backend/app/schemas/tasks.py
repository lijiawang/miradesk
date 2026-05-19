from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ScheduledTaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    command: str = Field(default="chat", min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    cli_path: str | None = None
    timeout: int = Field(default=300, ge=1, le=86400)
    enabled: bool = True
    interval_seconds: int | None = Field(default=None, ge=10)
    next_run_at: datetime | None = None


class ScheduledTaskUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    command: str | None = Field(default=None, min_length=1)
    args: dict[str, Any] | None = None
    cli_path: str | None = None
    timeout: int | None = Field(default=None, ge=1, le=86400)
    enabled: bool | None = None
    interval_seconds: int | None = Field(default=None, ge=10)
    next_run_at: datetime | None = None


class ScheduledTask(BaseModel):
    id: int
    name: str
    command: str
    args: dict[str, Any]
    cli_path: str
    timeout: int
    enabled: bool
    interval_seconds: int | None
    next_run_at: datetime | None
    last_run_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TaskRun(BaseModel):
    id: int
    task_id: int
    status: Literal["running", "success", "failed"]
    output: str | None
    error: str | None
    return_code: int | None
    started_at: datetime
    finished_at: datetime | None

