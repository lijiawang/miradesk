SHELL := /bin/bash

HOST ?= localhost
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173

.PHONY: help setup run run-lan run-backend run-frontend check build stop clean

help:
	@echo "MiraDesk commands"
	@echo
	@echo "  make setup        Install/sync backend and frontend dependencies"
	@echo "  make run          Run backend and frontend on localhost"
	@echo "  make run-lan      Run backend and frontend on 0.0.0.0 for LAN access"
	@echo "  make run-backend  Run only the FastAPI backend"
	@echo "  make run-frontend Run only the Vite frontend"
	@echo "  make check        Run backend/frontend checks"
	@echo "  make build        Build frontend assets"
	@echo "  make stop         Stop processes listening on dev ports"
	@echo "  make clean        Remove generated frontend build artifacts"

setup:
	uv sync --all-packages
	cd frontend && npm install

run: setup
	@echo "MiraDesk backend:  http://localhost:$(BACKEND_PORT)"
	@echo "MiraDesk frontend: http://localhost:$(FRONTEND_PORT)"
	@echo
	$(MAKE) -j2 run-backend run-frontend

run-lan: HOST = 0.0.0.0
run-lan: setup
	@echo "MiraDesk backend:  http://localhost:$(BACKEND_PORT)"
	@echo "MiraDesk frontend: http://localhost:$(FRONTEND_PORT)"
	@echo "LAN access is enabled; use the Network URL printed by Vite only from other devices."
	@echo
	$(MAKE) -j2 HOST=$(HOST) run-backend run-frontend

run-backend:
	HOST=$(HOST) PORT=$(BACKEND_PORT) uv run --package miradesk-backend python backend/main.py

run-frontend:
	cd frontend && npm run dev -- --host $(HOST) --port $(FRONTEND_PORT)

check:
	uv lock --check
	uv run --package miradesk-backend python -m compileall backend/app backend/main.py
	cd frontend && node --check app.js && node --check vite.config.js

build:
	cd frontend && npm run build

stop:
	@pids="$$(lsof -ti tcp:$(BACKEND_PORT) -sTCP:LISTEN 2>/dev/null || true)"; \
	if [ -n "$$pids" ]; then echo "Stopping backend port $(BACKEND_PORT): $$pids"; kill $$pids; fi
	@pids="$$(lsof -ti tcp:$(FRONTEND_PORT) -sTCP:LISTEN 2>/dev/null || true)"; \
	if [ -n "$$pids" ]; then echo "Stopping frontend port $(FRONTEND_PORT): $$pids"; kill $$pids; fi

clean:
	rm -rf frontend/dist
