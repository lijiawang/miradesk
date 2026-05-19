## MiraDesk

MiraDesk is a local AI workbench for Claude CLI: independent chat windows,
streaming responses, and scheduled local tasks from a clean web interface.

The project is split into two independently runnable apps:

```text
backend/    FastAPI API service, scheduler, SQLite repository, Claude CLI runner
frontend/   Vite-powered browser UI
docs/       Architecture diagram assets
```

The backend does not serve the frontend files. Run both services during local
development.

### Quick Start

```bash
make run
```

This syncs Python dependencies with `uv`, installs frontend packages, and starts
both services on localhost:

```text
Backend:  http://localhost:8000
Frontend: http://localhost:5173
```

Use `localhost` for day-to-day development. The browser treats `localhost`,
`127.0.0.1`, and LAN IP addresses as different sites, so their local chat
history and cache will not match.

To expose the app to other devices on the same network:

```bash
make run-lan
```

### Python Management

Python dependencies are managed by `uv` from the project root:

```bash
uv sync --all-packages
uv lock
```

Add backend dependencies with:

```bash
uv add --package miradesk-backend <package>
```

### Start Backend

```bash
uv run --package miradesk-backend python backend/main.py
```

Default backend URL:

```text
http://localhost:8000
```

### Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Default frontend URL:

```text
http://localhost:5173
```

Vite proxies frontend API requests to the backend, so the browser can keep
calling `/health`, `/claude/stream`, and `/tasks`.

### Directory

```text
backend/
  app/
    api/
      routes/
        claude.py
        health.py
        tasks.py
      router.py
    core/
    repositories/
    schemas/
    services/
  main.py
  pyproject.toml
frontend/
  index.html
  app.js
  styles.css
  package.json
  vite.config.js
docs/
  miradesk-architecture.svg
  miradesk-architecture.png
pyproject.toml
uv.lock
Makefile
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
