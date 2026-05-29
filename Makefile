.DEFAULT_GOAL := help
PYTHON ?= python
ENV    ?= dev

# ─── Development ───────────────────────────────────────────────
.PHONY: install install-dev lint test

install:  ## Install the agent-management package (editable)
	pip install -e .

install-dev:  ## Install with dev extras
	pip install -e ".[dev,crypto]"

lint:  ## Run ruff linter
	$(PYTHON) -m ruff check agent_management/ tests/

test:  ## Run test suite (uv-managed environment)
	uv run python -m pytest tests/ -q

# ─── Validation ────────────────────────────────────────────────
.PHONY: validate render-eval

validate:  ## Validate all agent specs and SV YAMLs
	agent-mgmt-validate --env $(ENV)

render-eval:  ## Render eval templates for ENV
	agent-mgmt-render-eval --env $(ENV)

# ─── Deployment ────────────────────────────────────────────────
.PHONY: deploy-agents deploy-svs snapshot

deploy-agents:  ## Deploy agents to ENV
	agent-mgmt-deploy-agents --env $(ENV)

deploy-svs:  ## Deploy semantic views to ENV
	agent-mgmt-deploy-svs --env $(ENV)

snapshot:  ## Capture pre-deploy snapshots for ENV
	agent-mgmt-snapshot --env $(ENV)

# ─── Evaluation ────────────────────────────────────────────────
.PHONY: eval sv-eval sv-eval-check deploy-vqrs check-vqrs metrics drift sync-vqrs

eval:  ## Run CI evaluations for ENV
	agent-mgmt-eval-agent --env $(ENV)

sv-eval:  ## Run SV evaluations for ENV
	agent-mgmt-eval-sv --env $(ENV)

sv-eval-check:  ## Check SV eval results for ENV (read-only)
	agent-mgmt-check-sv-eval --env $(ENV) --run-name "$(RUN_NAME)"

deploy-vqrs:  ## Deploy VQRs to semantic views for ENV
	agent-mgmt-deploy-svs-yaml --env $(ENV)

check-vqrs:  ## Check VQR + eval status across environments
	agent-mgmt-check-sv-evals --env $(ENV)

sync-vqrs:  ## Sync verified queries into dbt models
	agent-mgmt-sync-vqrs

metrics:  ## Compute metrics from eval results for ENV
	agent-mgmt-metrics --env $(ENV)

drift:  ## Detect SV schema drift for ENV
	agent-mgmt-detect-drift --env $(ENV)

# ─── Dry Runs ──────────────────────────────────────────────────
.PHONY: dry-deploy-agents dry-deploy-svs dry-eval dry-sv-eval dry-sync-vqrs dry-deploy-vqrs

dry-deploy-agents:  ## Dry-run agent deployment
	agent-mgmt-deploy-agents --env $(ENV) --dry-run

dry-deploy-svs:  ## Dry-run SV deployment
	agent-mgmt-deploy-svs --env $(ENV) --dry-run

dry-eval:  ## Dry-run evaluation
	agent-mgmt-eval-agent --env $(ENV) --dry-run

dry-sv-eval:  ## Dry-run SV evaluation
	agent-mgmt-eval-sv --env $(ENV) --dry-run

dry-sync-vqrs:  ## Preview VQR sync without writing
	agent-mgmt-sync-vqrs --dry-run

dry-deploy-vqrs:  ## Dry-run VQR deployment
	agent-mgmt-deploy-svs-yaml --env $(ENV) --dry-run

# ─── Help ──────────────────────────────────────────────────────
.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
