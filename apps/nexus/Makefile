.PHONY: help install migrate api ui test build ingest docker-up docker-down

help:
	@echo "ADAN NEXUS | CONNECT"
	@echo "  make install    Install backend and frontend dependencies"
	@echo "  make migrate    Apply Alembic migrations"
	@echo "  make ingest     Run the ingestion pipeline once"
	@echo "  make api        Start FastAPI on :8000"
	@echo "  make ui         Start Next.js on :3000"
	@echo "  make test       Backend pytest + frontend typecheck"
	@echo "  make build      Production frontend build"
	@echo "  make docker-up  docker compose up -d --build"

install:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
	cd frontend && npm ci

migrate:
	cd backend && .venv/bin/alembic upgrade head

ingest:
	cd backend && .venv/bin/python -m scripts.ingest

api:
	cd backend && .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

ui:
	cd frontend && npm run dev

test:
	cd backend && .venv/bin/python -m pytest tests -q
	cd frontend && npx tsc --noEmit

build:
	cd frontend && npm run build

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
