# Makefile for AMI Agents
SHELL := /bin/bash

# Contract compliance
-include projects/AMI-CI/lib/makefile_contract.mk

# Default target
.PHONY: help
help: ## Show this help message
	@echo "AMI Agents - Available targets:"
	@echo ""
	@echo "Other Targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %%-28s %%s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Preflight ---

.PHONY: preflight
preflight: pre-req-check ## Verify environment and pre-requisites

# --- Pre-requisites Check ---

.PHONY: pre-req-check
pre-req-check: ## Check system pre-requisites (runs automatically on install)
	@bash ami/scripts/pre-req.sh

# Pass args to pre-req.sh via PRE_REQ_ARGS:
#   sudo make pre-req                           # default: --install
#   sudo make pre-req PRE_REQ_ARGS="--reinstall-rust-guard"
#   sudo make pre-req PRE_REQ_ARGS="--uninstall-rust-guard"
PRE_REQ_ARGS ?= --install

.PHONY: pre-req
pre-req: ## Install system pre-requisites (requires sudo)
	@bash ami/scripts/pre-req.sh $(PRE_REQ_ARGS)

# --- Main Installation Flow ---

INSTALL_LOG := install-$(shell date +%Y%m%d-%H%M%S).log

.PHONY: install
install: ## Install AMI Agents in editable mode with all setup
	@exec > >(awk -W interactive -v LOG="$(INSTALL_LOG)" '{ ts=strftime("[%Y-%m-%dT%H:%M:%S]"); print $$0; print ts, $$0 >> LOG; fflush(); }') 2>&1; \
	echo "🚀 Installing AMI Agents..."; \
	echo "📝 Log: $(INSTALL_LOG)"; \
	$(MAKE) pre-req-check && \
	$(MAKE) sync-package && \
	$(MAKE) bootstrap-gitleaks && \
	$(MAKE) setup-config && \
	$(MAKE) install-bootstrap && \
	$(MAKE) install-opencode && \
	$(MAKE) register-extensions && \
	$(MAKE) install-hooks && \
	$(MAKE) install-shell && \
	echo "✨ Installation complete!" && \
	bash ami/scripts/shell/shell-setup --welcome

.PHONY: install-ci
install-ci: ## Non-interactive install for CI (uses install-defaults.yaml)
	@exec > >(awk -W interactive -v LOG="$(INSTALL_LOG)" '{ ts=strftime("[%Y-%m-%dT%H:%M:%S]"); print $$0; print ts, $$0 >> LOG; fflush(); }') 2>&1; \
	echo "🚀 Installing AMI Agents (CI mode)..."; \
	echo "📝 Log: $(INSTALL_LOG)"; \
	$(MAKE) pre-req-check && \
	$(MAKE) sync-package && \
	$(MAKE) bootstrap-gitleaks && \
	$(MAKE) setup-config && \
	$(MAKE) install-bootstrap-ci && \
	$(MAKE) install-opencode && \
	$(MAKE) register-extensions && \
	$(MAKE) install-hooks && \
	$(MAKE) install-shell && \
	echo "✨ Installation complete (CI mode)!"

.PHONY: ensure-repos
ensure-repos: ## Clone every workspace repo per moon.yml metadata.workspaceClones (mandatory + opt-in via --include)
	@bash ami/scripts/bin/ami-bootstrap-repos --pull

.PHONY: ensure-ci
ensure-ci: ensure-repos  ## Compatibility alias for ensure-repos (data-driven via moon.yml)

.PHONY: ensure-dataops
ensure-dataops: ensure-repos  ## Compatibility alias for ensure-repos (data-driven via moon.yml)

.PHONY: sync-package
sync-package: bootstrap-core ensure-ci ensure-dataops ## Sync package dependencies via uv
	@echo "🔧 Syncing ami-agents..."
	.boot-linux/bin/uv sync --extra dev

	@echo "✅ Package 'ami-agents' installed with dev dependencies"

# --- Component Targets ---

.PHONY: install-bootstrap
install-bootstrap: ## Interactive TUI to select and install optional bootstrap components
	@.venv/bin/python ami/scripts/bootstrap_installer.py

.PHONY: install-bootstrap-ci
install-bootstrap-ci: ## Non-interactive bootstrap using defaults file
	@.venv/bin/python ami/scripts/bootstrap_installer.py --defaults ami/config/install-defaults.yaml

.PHONY: bootstrap-core
bootstrap-core: ## Bootstrap core tools (uv, python, git-lfs/xet) into .boot-linux
	@echo "🔧 Bootstrapping core tools..."
	@bash ami/scripts/bootstrap/bootstrap_uv.sh
	@bash ami/scripts/bootstrap/bootstrap_python.sh
	@bash ami/scripts/bootstrap/bootstrap_git_xet.sh
	@echo "✅ Core bootstrap complete"

.PHONY: bootstrap-gitleaks
bootstrap-gitleaks: ## Bootstrap gitleaks (requires AMI-CI to be cloned first)
	@bash projects/AMI-CI/scripts/bootstrap-gitleaks

.PHONY: install-git-guard
install-git-guard: ## (DEPRECATED) RUST-GUARD is now handled by sudo make pre-req
	@echo "⚠️  install-git-guard is deprecated — rust guard is now installed via sudo make pre-req"
	@echo "    The SUID Rust guard at /usr/bin/git replaces the .boot-linux/bin/git wrapper."

.PHONY: install-shell
install-shell: ## Install AMI shell environment to ~/.bashrc
	@echo "🐚 Installing shell environment..."
	@bash ami/scripts/shell/shell-setup --install
	@echo "✅ Shell environment installed"

.PHONY: uninstall-shell
uninstall-shell: ## Remove AMI shell environment from ~/.bashrc
	@bash ami/scripts/shell/shell-setup --uninstall

.PHONY: install-opencode
install-opencode: ## Install opencode-ai globally via npm
	@echo "📦 Installing opencode-ai..."
	@bash ami/scripts/bootstrap/bootstrap_opencode.sh

.PHONY: update-opencode
update-opencode: ## Update opencode-ai to latest
	@npm update -g opencode-ai
	@echo "✅ opencode-ai updated"

.PHONY: sync
sync: sync-package install-hooks ## Sync deps + reinstall hooks

# --- Config & Utilities ---

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

.PHONY: register-extensions
register-extensions: ## Register extensions in .bashrc
	@echo "🔌 Registering extensions in ~/.bashrc..."
	@.venv/bin/python ami/scripts/register_extensions.py

.PHONY: clean
clean: ## Clean build artifacts
	@echo "🧹 Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

.PHONY: dev
dev: install install-hooks ## Install for development with code quality tools and hooks

.PHONY: install-hooks
install-hooks: ensure-ci ## Install native git hooks (no pre-commit dependency)
	@bash projects/AMI-CI/scripts/cleanup-precommit 2>/dev/null || true
	bash projects/AMI-CI/scripts/generate-hooks

.PHONY: install-hooks-recursive
install-hooks-recursive: ensure-ci ## Install hooks in workspace + every nested .git under projects/
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

.PHONY: scaffold-recursive
scaffold-recursive: ensure-ci ## Scaffold quality_exceptions.yaml in every strict-tier repo missing it
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
check-compliance-recursive: ensure-ci ## Audit every nested repo for AMI-CI contract compliance
	@_failed=0; \
	bash projects/AMI-CI/scripts/walk-projects | while IFS= read -r repo; do \
		echo ""; \
		echo "═══ Compliance: $$repo ═══"; \
		bash -c "source projects/AMI-CI/lib/checks.sh && ci_compliance_score '$$repo'" || \
			_failed=$$((_failed + 1)); \
	done; \
	[ $$_failed -eq 0 ]

# --- Quality & Test ---

.PHONY: test
test: ## Run tests (delegates to moon for caching)
	@moon run ami-agents:test

.PHONY: _test-impl
_test-impl:
	@echo "🧪 Running tests..."
	pytest

.PHONY: lint
lint: ## Run linters (delegates to moon for caching)
	@moon run ami-agents:lint

.PHONY: _lint-impl
_lint-impl:
	@echo "🔍 Running linters..."
	uv run ruff check --config res/config/ruff.toml .
	uv run ruff format --config res/config/ruff.toml --check .

.PHONY: type-check
type-check: ## Run type checker (delegates to moon for caching)
	@moon run ami-agents:type-check

.PHONY: _type-check-impl
_type-check-impl:
	@echo "📝 Running type checker..."
	mypy .

.PHONY: check
check: ## Run all checks (lint + type-check + test, with caching)
	@moon run ami-agents:check

.PHONY: check-hooks
check-hooks: ensure-ci ## Preview generated hooks (dry-run)
	bash projects/AMI-CI/scripts/generate-hooks --dry-run

.PHONY: cleanup-precommit
cleanup-precommit: ## Remove pre-commit package and cache
	bash projects/AMI-CI/scripts/cleanup-precommit

.PHONY: dead-code
dead-code: ## Run AST-based dead code analysis (delegates to moon for caching)
	@moon run ami-agents:dead-code

.PHONY: _dead-code-impl
_dead-code-impl:
	.boot-linux/bin/uv run python -m ami.ci.check_dead_code

.PHONY: update
update: ## Update workspace via moon — walks every project topologically (^:update)
	@moon run :update

.PHONY: update-ci
update-ci: ## Update via moon (non-interactive — same as `make update`, alias kept for CI)
	@moon run :update

.PHONY: update-deps
update-deps: ## Update Python dependencies only
	@echo "🔄 Updating Python dependencies..."
	.boot-linux/bin/uv update

.PHONY: uninstall
uninstall: ## Uninstall ami-agents
	@echo "🗑️  Uninstalling ami-agents..."
	.boot-linux/bin/uv pip uninstall ami-agents -y

# ==============================================================================
# LlamaServer — multi-flavor build + deployment (cpu, sycl, vulkan)
# ==============================================================================
-include Makefile.llamaserver
