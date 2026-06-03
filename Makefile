# Makefile for AMI Agents
SHELL := /bin/bash

# Contract compliance
-include projects/AMI-CI/lib/makefile_contract.mk

# Default target
.PHONY: help
help: ## Show this help message
	@echo "AMI Agents - Available targets:"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %%-28s %%s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Init — system dependencies ---

.PHONY: init-check
init-check: ## Check system dependencies
	@bash ami/scripts/initial-setup.sh

.PHONY: init
init: ## Install system dependencies (requires sudo)
	@bash ami/scripts/initial-setup.sh --install

# --- Core prereqs ---

.PHONY: core
core: ## Bootstrap uv + python + git-xet (prereq for sync-package)
	@echo "🔧 Bootstrapping core tools..."
	@bash ami/scripts/bootstrap/bootstrap_uv.sh
	@bash ami/scripts/bootstrap/bootstrap_python.sh
	@bash ami/scripts/bootstrap/bootstrap_git_xet.sh
	@echo "✅ Core bootstrap complete"

# --- Install — component selection ---

.PHONY: install
install: sync-package ## Interactive TUI to select and install components
	@.venv/bin/python ami/scripts/bootstrap_installer.py && \
	$(MAKE) register-extensions && \
	bash ami/scripts/shell/shell-setup --welcome

.PHONY: install-ci
install-ci: ## Non-interactive component install (uses install-defaults.yaml)
	@.venv/bin/python ami/scripts/bootstrap_installer.py --defaults ami/config/install-defaults.yaml && \
	$(MAKE) register-extensions && \
	echo "✨ Installation complete (CI mode)!"

# --- Repos ---

.PHONY: ensure-repos
ensure-repos: ## Clone every workspace repo per moon.yml metadata
	@bash ami/scripts/bin/bootstrap-repos --pull

# --- Package sync ---

.PHONY: sync-package
sync-package: core ensure-repos ## Sync package dependencies via uv
	@echo "🔧 Syncing ami-agents..."
	.boot-linux/bin/uv sync --extra dev
	@echo "✅ Package 'ami-agents' installed with dev dependencies"

# --- Config ---

.PHONY: setup-config
setup-config: setup-automation setup-linter-config ## Setup configuration files

.PHONY: setup-linter-config
setup-linter-config: ## Create symlinks for linter configs in project root
	@echo "🔗 Setting up linter configuration symlinks..."
	@if [ -f "res/config/ruff.toml" ] && [ ! -e "ruff.toml" ]; then \
		ln -s res/config/ruff.toml ruff.toml; \
		echo "✅ Created ruff.toml symlink"; \
	elif [ -e "ruff.toml" ]; then \
		echo "ℹ️  ruff.toml already exists"; \
	else \
		echo "⚠️  res/config/ruff.toml not found"; \
	fi
	@if [ -f "res/config/mypy.toml" ] && [ ! -e "mypy.toml" ]; then \
		ln -s res/config/mypy.toml mypy.toml; \
		echo "✅ Created mypy.toml symlink"; \
	elif [ -e "mypy.toml" ]; then \
		echo "ℹ️  mypy.toml already exists"; \
	elif [ -f "res/config/mypy.toml" ]; then \
		echo "ℹ️  mypy config exists in res/config/mypy.toml"; \
	fi

.PHONY: setup-automation
setup-automation: ## Setup automation configuration
	@echo "⚙️  Setting up automation configuration..."
	@if [ ! -f "ami/config/automation.yaml" ]; then \
		if [ -f "ami/config/automation.template.yaml" ]; then \
			cp "ami/config/automation.template.yaml" "ami/config/automation.yaml"; \
			echo "✅ Created ami/config/automation.yaml from template"; \
		else \
			echo "⚠️  Template ami/config/automation.template.yaml not found"; \
		fi \
	else \
		echo "ℹ️  Automation configuration already exists at ami/config/automation.yaml"; \
	fi

# --- Extensions ---

.PHONY: register-extensions
register-extensions: ## Register extensions in .boot-linux/bin
	@echo "🔌 Registering extensions in ~/.bashrc..."
	@.venv/bin/python ami/scripts/register_extensions.py

# --- Shell ---

.PHONY: install-shell
install-shell: ## Install AMI shell environment to ~/.bashrc
	@echo "🐚 Installing shell environment..."
	@bash ami/scripts/shell/shell-setup --install
	@echo "✅ Shell environment installed"

.PHONY: uninstall-shell
uninstall-shell: ## Remove AMI shell environment from ~/.bashrc
	@bash ami/scripts/shell/shell-setup --uninstall

# --- Hooks ---

.PHONY: install-hooks
install-hooks: ensure-repos ## Install native git hooks
	@bash projects/AMI-CI/scripts/cleanup-precommit 2>/dev/null || true
	bash projects/AMI-CI/scripts/generate-hooks

.PHONY: install-hooks-recursive
install-hooks-recursive: ensure-repos ## Install hooks in workspace + every nested .git under projects/
	@echo "🔗 Installing hooks in workspace root..."
	@bash projects/AMI-CI/scripts/cleanup-precommit 2>/dev/null || true
	@bash projects/AMI-CI/scripts/generate-hooks
	@bash projects/AMI-CI/scripts/walk-projects | while IFS= read -r repo; do \
		echo ""; \
		echo "🔗 Installing hooks in $$repo..."; \
		( cd "$$repo" && bash $(CURDIR)/projects/AMI-CI/scripts/cleanup-precommit 2>/dev/null || true; \
		  bash $(CURDIR)/projects/AMI-CI/scripts/generate-hooks ) || \
		  echo "⚠️  Hook install failed in $$repo (skipping)"; \
	done

.PHONY: check-hooks
check-hooks: ensure-repos ## Preview generated hooks (dry-run)
	bash projects/AMI-CI/scripts/generate-hooks --dry-run

# --- Quality & Test ---

.PHONY: test
test: ## Run tests (delegates to moon for caching)
	@moon run ami-agents:test

.PHONY: lint
lint: ## Run linters (delegates to moon for caching)
	@moon run ami-agents:lint

.PHONY: type-check
type-check: ## Run type checker (delegates to moon for caching)
	@moon run ami-agents:type-check

.PHONY: check
check: ## Run all checks (lint + type-check + test, with caching)
	@moon run ami-agents:check

.PHONY: dead-code
dead-code: ## Run AST-based dead code analysis (delegates to moon for caching)
	@moon run ami-agents:dead-code

# --- Update ---

.PHONY: update
update: ## Update workspace via moon — walks every project topologically (^:update)
	@TMP_WS=$$(mktemp) && \
	awk -f ami/scripts/filter_moon_workspace.awk .moon/workspace.yml > "$$TMP_WS" && \
	MOON_WORKSPACE="$$TMP_WS" moon run :update; \
	RET=$$?; rm -f "$$TMP_WS"; exit $$RET

.PHONY: update-deps
update-deps: ## Update Python dependencies only
	@echo "🔄 Updating Python dependencies..."
	.boot-linux/bin/uv update

.PHONY: uninstall
uninstall: ## Uninstall ami-agents
	@echo "🗑️  Uninstalling ami-agents..."
	.boot-linux/bin/uv pip uninstall ami-agents -y

# --- Utility ---

.PHONY: clean
clean: ## Clean build artifacts
	@echo "🧹 Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

.PHONY: scaffold-recursive
scaffold-recursive: ensure-repos ## Scaffold quality_exceptions.yaml in every strict-tier repo
	@bash projects/AMI-CI/scripts/walk-projects | while IFS= read -r repo; do \
		_tier=$$(bash -c "source projects/AMI-CI/lib/checks_quality.sh && \
			ci_resolve_tier '$$repo' \
			'$(CURDIR)/ami/config/project_enforcement.yaml'" 2>/dev/null || echo strict); \
		if [ "$$_tier" != "strict" ]; then continue; fi; \
		if [ ! -f "$$repo/quality_exceptions.yaml" ]; then \
			pname=$$(basename "$$repo"); \
			sed "s/__PROJECT_NAME__/$$pname/" \
				projects/AMI-CI/templates/quality_exceptions.template.yaml \
				> "$$repo/quality_exceptions.yaml"; \
			echo "📝 Scaffolded $$repo/quality_exceptions.yaml (tier=strict)"; \
		fi; \
	done

.PHONY: check-compliance-recursive
check-compliance-recursive: ensure-repos ## Audit every nested repo for AMI-CI contract compliance
	@_failed=0; \
	bash projects/AMI-CI/scripts/walk-projects | while IFS= read -r repo; do \
		echo ""; \
		echo "═══ Compliance: $$repo ═══"; \
		bash -c "source projects/AMI-CI/lib/checks.sh && ci_compliance_score '$$repo'" || \
			_failed=$$((_failed + 1)); \
	done; \
	[ $$_failed -eq 0 ]

# ==============================================================================
# LlamaServer — multi-flavor build + deployment (cpu, sycl, vulkan)
# ==============================================================================
-include Makefile.llamaserver
