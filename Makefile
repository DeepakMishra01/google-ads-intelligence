# Developer convenience targets. Requires Python 3.12 for the local targets.
.PHONY: help install lint format test cov run migrate revision up down logs build

help:
	@echo "Targets: install lint format test cov run migrate revision up down logs build"

install:
	pip install -e ".[dev]"

lint:
	ruff check app tests
	mypy app

format:
	ruff format app tests
	ruff check --fix app tests

test:
	pytest

cov:
	pytest --cov=app --cov-report=term-missing

run:
	uvicorn app.main:app --reload

migrate:
	alembic upgrade head

revision:
	alembic revision --autogenerate -m "$(m)"

# Docker
up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api

build:
	docker compose build
