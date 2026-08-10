VENV ?= .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install up down db dev worker seed provision migrate revision test lint fmt

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -e "apps/api[dev]"

up:
	docker compose up --build -d

down:
	docker compose down

db:
	docker compose up -d postgres redis

dev:
	cd apps/api && ../../$(PY) -m uvicorn app.main:app --reload --port 8000

worker:
	cd apps/api && ../../$(PY) -m app.workers.post_call

seed:
	cd apps/api && ../../$(PY) scripts/seed_demo.py ../../config/tenants/example-dental.yaml

# Push a tenant's agent config to the voice vendor and point its number at it.
# Re-run after any prompt/knowledge/tool change. Override: make provision SLUG=...
SLUG ?= bright-smile-dental
provision:
	cd apps/api && ../../$(PY) scripts/provision_voice.py --slug $(SLUG)

migrate:
	cd apps/api && ../../$(PY) -m alembic upgrade head

revision:
	cd apps/api && ../../$(PY) -m alembic revision -m "$(m)"

test:
	cd apps/api && ../../$(PY) -m pytest -q

lint:
	$(VENV)/bin/ruff check apps/api
	$(VENV)/bin/ruff format --check apps/api

fmt:
	$(VENV)/bin/ruff check --fix apps/api
	$(VENV)/bin/ruff format apps/api
