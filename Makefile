.PHONY: help install run lint format typecheck test test-cov check docker-build docker-up docker-down sonar clean

IMAGE ?= btc-lottery-miner
TAG ?= local
SONAR_HOST ?= http://192.168.3.196:9003
SONAR_TOKEN ?=

help:
	@echo "install      - cria o venv e instala dependências (uv)"
	@echo "run          - sobe a API/local (uvicorn com reload) em http://localhost:8080"
	@echo "lint         - ruff check"
	@echo "format       - ruff format"
	@echo "typecheck    - mypy (strict)"
	@echo "test         - pytest com cobertura"
	@echo "check        - lint + typecheck + test (o que o CI roda)"
	@echo "docker-build - builda a imagem local"
	@echo "docker-up    - docker compose up -d --build"
	@echo "docker-down  - docker compose down"
	@echo "sonar        - roda o SonarQube scan (usa SONAR_TOKEN)"

install:
	uv sync

run:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

lint:
	uv run ruff check .

format:
	uv run ruff format .

typecheck:
	uv run mypy app

test:
	uv run pytest

test-cov:
	uv run pytest --cov-report=html

check: lint typecheck test

docker-build:
	docker build -t $(IMAGE):$(TAG) .

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

sonar:
	docker run --rm \
		-e SONAR_TOKEN=$(SONAR_TOKEN) \
		-e SONAR_HOST_URL=$(SONAR_HOST) \
		-v "$(CURDIR):/usr/src" \
		-w /usr/src \
		sonarsource/sonar-scanner-cli:latest

clean:
	rm -rf .venv .pytest_cache .ruff_cache .mypy_cache .coverage coverage.xml htmlcov .scannerwork
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
