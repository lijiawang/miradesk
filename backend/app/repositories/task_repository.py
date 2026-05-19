import json
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.core.time import to_iso, utc_now
from app.schemas.tasks import ScheduledTaskCreate, ScheduledTaskUpdate


class TaskRepository:
    def __init__(self, database_path: Path, default_cli_path: str) -> None:
        self.database_path = database_path
        self.default_cli_path = default_cli_path

    def init_db(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS scheduled_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    command TEXT NOT NULL,
                    args_json TEXT NOT NULL DEFAULT '{}',
                    cli_path TEXT NOT NULL,
                    timeout INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    interval_seconds INTEGER,
                    next_run_at TEXT,
                    last_run_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS task_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    output TEXT,
                    error TEXT,
                    return_code INTEGER,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    FOREIGN KEY(task_id) REFERENCES scheduled_tasks(id)
                );

                CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_due
                    ON scheduled_tasks(enabled, next_run_at);
                CREATE INDEX IF NOT EXISTS idx_task_runs_task_id
                    ON task_runs(task_id, started_at);
                """
            )

    def create_task(self, payload: ScheduledTaskCreate) -> dict[str, Any]:
        now = utc_now()
        next_run_at = payload.next_run_at or now
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scheduled_tasks (
                    name, command, args_json, cli_path, timeout, enabled,
                    interval_seconds, next_run_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.name,
                    payload.command,
                    json.dumps(payload.args, ensure_ascii=False),
                    payload.cli_path or self.default_cli_path,
                    payload.timeout,
                    int(payload.enabled),
                    payload.interval_seconds,
                    to_iso(next_run_at) if payload.enabled else None,
                    to_iso(now),
                    to_iso(now),
                ),
            )
            task_id = int(cursor.lastrowid)
        task = self.get_task(task_id)
        if task is None:
            raise RuntimeError("Failed to create scheduled task")
        return task

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scheduled_tasks ORDER BY created_at DESC"
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def get_task(self, task_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM scheduled_tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
        return self._task_from_row(row) if row else None

    def update_task(
        self,
        task_id: int,
        payload: ScheduledTaskUpdate,
    ) -> dict[str, Any] | None:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self.get_task(task_id)

        values: list[Any] = []
        assignments: list[str] = []
        if "args" in updates:
            assignments.append("args_json = ?")
            values.append(json.dumps(updates.pop("args") or {}, ensure_ascii=False))
        if "enabled" in updates:
            assignments.append("enabled = ?")
            values.append(int(bool(updates.pop("enabled"))))
        if "cli_path" in updates and updates["cli_path"] is None:
            updates["cli_path"] = self.default_cli_path
        if "next_run_at" in updates and updates["next_run_at"] is not None:
            updates["next_run_at"] = to_iso(updates["next_run_at"])

        for key, value in updates.items():
            assignments.append(f"{key} = ?")
            values.append(value)

        assignments.append("updated_at = ?")
        values.append(to_iso(utc_now()))
        values.append(task_id)

        with self._connect() as conn:
            conn.execute(
                f"UPDATE scheduled_tasks SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )
        return self.get_task(task_id)

    def delete_task(self, task_id: int) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
            return cursor.rowcount > 0

    def list_due_tasks(self, limit: int) -> list[dict[str, Any]]:
        now = to_iso(utc_now())
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM scheduled_tasks
                WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?
                ORDER BY next_run_at ASC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
        return [self._task_from_row(row) for row in rows]

    def claim_task(self, task: dict[str, Any]) -> None:
        now = utc_now()
        interval_seconds = task.get("interval_seconds")
        next_run_at = (
            to_iso(now + timedelta(seconds=interval_seconds))
            if interval_seconds
            else None
        )
        enabled = 1 if interval_seconds else 0
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE scheduled_tasks
                SET next_run_at = ?, last_run_at = ?, enabled = ?, updated_at = ?
                WHERE id = ?
                """,
                (next_run_at, to_iso(now), enabled, to_iso(now), task["id"]),
            )

    def trigger_now(self, task_id: int) -> dict[str, Any] | None:
        now = to_iso(utc_now())
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE scheduled_tasks
                SET enabled = 1, next_run_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, task_id),
            )
        return self.get_task(task_id)

    def create_run(self, task_id: int) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO task_runs (task_id, status, started_at)
                VALUES (?, 'running', ?)
                """,
                (task_id, to_iso(utc_now())),
            )
            return int(cursor.lastrowid)

    def complete_run(
        self,
        run_id: int,
        status: str,
        output: str | None,
        error: str | None,
        return_code: int | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE task_runs
                SET status = ?, output = ?, error = ?, return_code = ?, finished_at = ?
                WHERE id = ?
                """,
                (status, output, error, return_code, to_iso(utc_now()), run_id),
            )

    def list_runs(self, task_id: int, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM task_runs
                WHERE task_id = ?
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (task_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _task_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["args"] = json.loads(data.pop("args_json") or "{}")
        data["enabled"] = bool(data["enabled"])
        return data

