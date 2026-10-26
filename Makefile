VENV ?= .venv
PY := $(abspath $(VENV))/bin

.PHONY: run test lint format web-install web web-test

run:
	cd api && LANGSMITH_TRACING=false $(PY)/uvicorn app.main:app --reload

test:
	$(PY)/pytest -q

lint:
	$(PY)/ruff check . && $(PY)/black --check .

format:
	$(PY)/black . && $(PY)/ruff check --fix .

# Web demo UI (web/). The Vite proxy reads API_KEY from .env; run `make run` alongside.
web-install:
	cd web && npm install

web:
	cd web && npm run dev

web-test:
	cd web && npm run typecheck && npm test
