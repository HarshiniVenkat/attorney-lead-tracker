.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

.PHONY: env
env: ## Create .env from .env.example if it does not exist
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

.PHONY: up
up: env ## Build and start the full stack
	$(COMPOSE) up --build -d
	@echo ""
	@echo "  Public form     http://localhost:3000/apply"
	@echo "  Internal UI     http://localhost:3000/admin/leads"
	@echo "  API docs        http://localhost:8000/docs"
	@echo "  MailHog inbox   http://localhost:8025"
	@echo "  MinIO console   http://localhost:9001"
	@echo ""
	@echo "  Run 'make seed' to create the attorney login."

.PHONY: down
down: ## Stop the stack, keeping volumes
	$(COMPOSE) down

.PHONY: clean
clean: ## Stop the stack and delete all data volumes
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Tail logs from every service
	$(COMPOSE) logs -f

.PHONY: seed
seed: ## Create the attorney account from SEED_ADMIN_* in .env
	$(COMPOSE) exec backend python -m app.cli seed-admin

.PHONY: migrate
migrate: ## Apply database migrations
	$(COMPOSE) exec backend alembic upgrade head

.PHONY: revision
revision: ## Autogenerate a migration: make revision m="add x"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

.PHONY: test
test: ## Run the backend test suite against a throwaway database
	$(COMPOSE) exec backend pytest -v

.PHONY: lint
lint: ## Lint backend and frontend
	$(COMPOSE) exec backend ruff check app alembic tests
	$(COMPOSE) exec frontend npm run lint

.PHONY: fmt
fmt: ## Auto-fix backend lint issues
	$(COMPOSE) exec backend ruff check app alembic tests --fix

.PHONY: shell
shell: ## Open a shell in the backend container
	$(COMPOSE) exec backend bash

.PHONY: psql
psql: ## Open a psql prompt
	$(COMPOSE) exec postgres psql -U alma -d alma
