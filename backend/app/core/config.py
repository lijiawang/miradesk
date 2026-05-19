import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]


def _split_env_list(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "MiraDesk")
    app_version: str = os.getenv("APP_VERSION", "0.1.0")
    database_path: Path = Path(
        os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "miradesk.sqlite3"))
    )
    default_cli_path: str = os.getenv("CLAUDE_CLI_PATH", "claude")
    scheduler_poll_seconds: float = float(os.getenv("SCHEDULER_POLL_SECONDS", "3"))
    scheduler_max_concurrent_tasks: int = int(
        os.getenv("SCHEDULER_MAX_CONCURRENT_TASKS", "2")
    )
    cors_origins: tuple[str, ...] = _split_env_list(
        os.getenv("CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173")
    )
    command_allowlist: tuple[str, ...] = _split_env_list(
        os.getenv("CLAUDE_COMMAND_ALLOWLIST", "chat,complete")
    )


settings = Settings()
