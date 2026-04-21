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

test:  ## Run test suite
	$(PYTHON) -m pytest tests/ -v

# ─── Validation ────────────────────────────────────────────────
.PHONY: validate render-eval

validate:  ## Validate all agent specs and SV YAMLs
	$(PYTHON) -m agent_management.validate_specs --env $(ENV)

render-eval:  ## Render eval templates for ENV
	$(PYTHON) -m agent_management.render_eval_templates --env $(ENV)

# ─── Deployment ────────────────────────────────────────────────
.PHONY: deploy-agents deploy-svs snapshot

deploy-agents:  ## Deploy agents to ENV
	$(PYTHON) -m agent_management.deploy_agents --env $(ENV)

deploy-svs:  ## Deploy semantic views to ENV
	$(PYTHON) -m agent_management.deploy_semantic_views --env $(ENV)

snapshot:  ## Capture pre-deploy snapshots for ENV
	$(PYTHON) -m agent_management.snapshot_state --env $(ENV)

# ─── Evaluation ────────────────────────────────────────────────
.PHONY: eval sv-eval sv-eval-check deploy-vqrs check-vqrs metrics drift sync-vqrs

eval:  ## Run CI evaluations for ENV
	$(PYTHON) -m agent_management.run_ci_eval --env $(ENV)

sv-eval:  ## Run SV evaluations for ENV
	$(PYTHON) -m agent_management.run_sv_eval --env $(ENV)

sv-eval-check:  ## Check SV eval results for ENV (read-only)
	$(PYTHON) -m agent_management.check_sv_eval --env $(ENV) --run-name "$(RUN_NAME)"

deploy-vqrs:  ## Deploy VQRs to semantic views for ENV
	$(PYTHON) -m agent_management.deploy_svs_yaml --env $(ENV)

check-vqrs:  ## Check VQR + eval status across environments
	$(PYTHON) -m agent_management.check_sv_evals --env $(ENV)

sync-vqrs:  ## Sync verified queries into dbt models
	$(PYTHON) -m agent_management.sync_vqrs_to_dbt

metrics:  ## Compute metrics from eval results for ENV
	$(PYTHON) -m agent_management.compute_metrics --env $(ENV)

drift:  ## Detect SV schema drift for ENV
	$(PYTHON) -m agent_management.detect_drift --env $(ENV)

# ─── Dry Runs ──────────────────────────────────────────────────
.PHONY: dry-deploy-agents dry-deploy-svs dry-eval dry-sv-eval dry-sync-vqrs dry-deploy-vqrs

dry-deploy-agents:  ## Dry-run agent deployment
	$(PYTHON) -m agent_management.deploy_agents --env $(ENV) --dry-run

dry-deploy-svs:  ## Dry-run SV deployment
	$(PYTHON) -m agent_management.deploy_semantic_views --env $(ENV) --dry-run

dry-eval:  ## Dry-run evaluation
	$(PYTHON) -m agent_management.run_ci_eval --env $(ENV) --dry-run

dry-sv-eval:  ## Dry-run SV evaluation
	$(PYTHON) -m agent_management.run_sv_eval --env $(ENV) --dry-run

dry-sync-vqrs:  ## Preview VQR sync without writing
	$(PYTHON) -m agent_management.sync_vqrs_to_dbt --dry-run

dry-deploy-vqrs:  ## Dry-run VQR deployment
	$(PYTHON) -m agent_management.deploy_svs_yaml --env $(ENV) --dry-run

# ─── Help ──────────────────────────────────────────────────────
.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
