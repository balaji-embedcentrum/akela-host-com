# akela-host.com — single entrypoint for every action (see CLAUDE.md).
# Local-first: every target below runs with ZERO external accounts.

.DEFAULT_GOAL := help
UV ?= uv
COMPOSE ?= docker compose -f infra/docker-compose.dev.yml

.PHONY: help
help: ## List all targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
	  awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Create venv (Python 3.12) and install all deps
	$(UV) python install 3.12
	$(UV) sync --extra dev
	cd frontend && npm install

.PHONY: fmt
fmt: ## Auto-format (ruff)
	$(UV) run ruff format src
	$(UV) run ruff check --fix src

.PHONY: lint
lint: ## Lint (ruff, no fixes)
	$(UV) run ruff check src
	$(UV) run ruff format --check src

.PHONY: typecheck
typecheck: ## Static types (mypy)
	$(UV) run mypy src/backend

.PHONY: test
test: ## Run the test suite (mock mode, no external accounts)
	$(UV) run pytest

.PHONY: verify
verify: lint typecheck test ## Lint + typecheck + test — the CI gate

.PHONY: db-up
db-up: ## Start only Postgres (for local runs/tests against PG)
	$(COMPOSE) up -d db

.PHONY: migrate
migrate: ## Apply DB migrations (web-app + fleet schema)
	$(UV) run alembic upgrade head

.PHONY: seed
seed: ## Seed: 1 fake VPS + N available slots + an admin user
	$(UV) run python -m backend.scripts.seed

.PHONY: api
api: ## Run the FastAPI backend (mock mode)
	$(UV) run uvicorn backend.main:app --reload --port 8000 --app-dir src

.PHONY: web
web: ## Run the React SPA dev server
	cd frontend && npm run dev

.PHONY: dev
dev: ## Bring up the full local stack (Postgres + Traefik); then run `make api` & `make web`
	$(COMPOSE) up -d
	@echo "Stack up. Now: make migrate && make seed && (make api & make web)"

.PHONY: down
down: ## Tear down the local stack
	$(COMPOSE) down -v

.PHONY: build-hermes
build-hermes: ## Build the hermes-adapter image from the local repo (for Epic 6)
	docker build -t $${HERMES_ADAPTER_IMAGE:-hermes-adapter:latest} \
	  /Users/balajiboominathan/Documents/hermes-adapter

.PHONY: e2e
e2e: ## End-to-end happy-path test (anon→login→rent→deploy→cancel→recycle)
	$(UV) run pytest src/backend/tests/test_e2e.py -v
