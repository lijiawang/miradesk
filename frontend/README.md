## MiraDesk Frontend

Standalone browser UI for the MiraDesk backend.

### Run

```bash
npm install
npm run dev
```

Default frontend URL:

```text
http://localhost:5173
```

During local development, Vite proxies `/health`, `/claude/*`, and `/tasks/*`
to `http://127.0.0.1:8000`.

For a deployed backend, set:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```
