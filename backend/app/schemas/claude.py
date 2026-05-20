from typing import Any

from pydantic import BaseModel, Field


class ClaudeCLIRequest(BaseModel):
    command: str = Field(..., min_length=1, examples=["chat"])
    args: dict[str, Any] = Field(default_factory=dict)
    cli_path: str | None = Field(default=None, examples=["claude"])
    timeout: int = Field(default=30, ge=1, le=86400)


class ClaudeCLIResponse(BaseModel):
    success: bool
    output: str | None = None
    error: str | None = None
    return_code: int | None = None


class ClaudeSlashCommand(BaseModel):
    name: str
    title: str
    detail: str
    source: str = "claude"


class ClaudeSlashCommandResponse(BaseModel):
    commands: list[ClaudeSlashCommand]
    source: str
    error: str | None = None
