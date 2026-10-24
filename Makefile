VENV ?= .venv
PY := $(abspath $(VENV))/bin

.PHONY: run test lint format

run:
	cd api && LANGSMITH_TRACING=false $(PY)/uvicorn app.main:app --reload

test:
	$(PY)/pytest -q

lint:
	$(PY)/ruff check . && $(PY)/black --check .

format:
	$(PY)/black . && $(PY)/ruff check --fix .
