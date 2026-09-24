PYTHON ?= python

.PHONY: install run test lint format format-check typecheck migrate verify

install:
	$(PYTHON) -m pip install -e ".[dev]"

run:
	$(PYTHON) -m uvicorn app.main:app --reload --host 127.0.0.1 --port 4174

test:
	$(PYTHON) -m pytest -q

lint:
	ruff check app tests alembic scripts

format:
	ruff format app tests alembic scripts

format-check:
	ruff format --check app tests alembic scripts

typecheck:
	mypy app

migrate:
	alembic upgrade head

verify: format-check lint typecheck test
