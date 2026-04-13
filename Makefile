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
.PHONY: eval metrics drift

eval:  ## Run CI evaluations for ENV
	$(PYTHON) -m agent_management.run_ci_eval --env $(ENV)

metrics:  ## Compute metrics from eval results for ENV
	$(PYTHON) -m agent_management.compute_metrics --env $(ENV)

drift:  ## Detect SV schema drift for ENV
	$(PYTHON) -m agent_management.detect_drift --env $(ENV)

# ─── Dry Runs ──────────────────────────────────────────────────
.PHONY: dry-deploy-agents dry-deploy-svs dry-eval

dry-deploy-agents:  ## Dry-run agent deployment
	$(PYTHON) -m agent_management.deploy_agents --env $(ENV) --dry-run

dry-deploy-svs:  ## Dry-run SV deployment
	$(PYTHON) -m agent_management.deploy_semantic_views --env $(ENV) --dry-run

dry-eval:  ## Dry-run evaluation
	$(PYTHON) -m agent_management.run_ci_eval --env $(ENV) --dry-run

# ─── Help ──────────────────────────────────────────────────────
.PHONY: help
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
