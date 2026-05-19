## MiraDesk Backend

FastAPI API service for operating the local Claude CLI.

### Run

From the repository root:

```bash
uv run --package miradesk-backend python backend/main.py
```

Or from this directory:

```bash
uv run python main.py
```

### Dependencies

The lockfile lives at the repository root. Manage backend dependencies from the
root workspace:

```bash
uv add --package miradesk-backend <package>
uv lock
uv sync --all-packages
```

Default API URL:

```text
http://localhost:8000
```

### Environment

```text
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
CLAUDE_CLI_PATH=claude
DATABASE_PATH=./data/miradesk.sqlite3
```

### Main APIs

- `GET /health`
- `POST /claude/run`
- `POST /claude/stream`
- `POST /tasks`
- `GET /tasks`
- `PATCH /tasks/{task_id}`
- `POST /tasks/{task_id}/run-now`
- `GET /tasks/{task_id}/runs`
