# Makefile for AMI Agents
# Platform detection. On macOS, prefer Homebrew bash 5.x over /bin/bash
# (3.2) for nameref support. The Homebrew gnubin directories are
# prepended to PATH so GNU coreutils, gnu-sed, and findutils shadow
# the BSD equivalents.
_OS := $(shell uname -s)
_HB_PREFIX := $(if $(wildcard /opt/homebrew),/opt/homebrew,$(if $(wildcard /usr/local),/usr/local))
SHELL := $(if $(wildcard $(_HB_PREFIX)/bin/bash),$(_HB_PREFIX)/bin/bash,/bin/bash)
export PATH := $(_HB_PREFIX)/opt/coreutils/libexec/gnubin:$(_HB_PREFIX)/opt/gnu-sed/libexec/gnubin:$(_HB_PREFIX)/opt/findutils/libexec/gnubin:$(_HB_PREFIX)/bin:$(PATH)

# CI provides shared configs (ruff.toml, mypy.toml) and bootstrapped
# tools (uv, ansible, gitleaks). VM-root delegates to CI for these.
CI_DIR := $(abspath projects/CI)
CI_BOOT_NAME := $(if $(filter Darwin,$(_OS)),.boot-macos,.boot-linux)
CI_BOOT_BIN := $(CI_DIR)/$(CI_BOOT_NAME)/bin
CI_RUFF := $(CI_DIR)/ruff.toml
CI_MYPY := $(CI_DIR)/mypy.toml
UV := $(CI_BOOT_BIN)/uv

# cmake 4.x dropped support for cmake_minimum_required < 3.5. python-olm
# uses cmake_minimum_required(VERSION 2.x). Set policy version floor so the
# build succeeds without patching upstream.
export CMAKE_POLICY_VERSION_MINIMUM := 3.5

# Contract compliance
-include projects/CI/lib/makefile_contract.mk

# Default target
.PHONY: help
help: ## Show this help message
	@echo "AMI Agents - Available targets:"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-28s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- Init - system dependencies ---

.PHONY: init-check
init-check: ## Check system dependencies (via CI resolver)
	@bash projects/CI/scripts/install-system-deps --check

.PHONY: init
init: ## Install system dependencies (platform-aware: brew on macOS, two-phase sudo on Linux)
ifeq ($(_OS),Darwin)
	@echo "==> Installing Homebrew + GNU tools (macOS)..."
	@bash $(CI_DIR)/scripts/bootstrap-homebrew
	@echo "==> Installing system packages (from config/system-deps.yaml)..."
	@bash $(CI_DIR)/scripts/install-system-deps --install
	@echo "==> macOS system dependencies installed."
else
	@echo "==> Installing system packages (Linux, two-phase sudo)..."
	@_missing=$$(mktemp); \
	bash $(CI_DIR)/scripts/install-system-deps --export-missing "$$_missing"; \
	bash $(CI_DIR)/scripts/install-system-deps --install-only "$$_missing"; \
	rm -f "$$_missing"
endif

# --- Core prereqs ---

.PHONY: core
core: ## Bootstrap CI tools (uv + ansible + node) + VM-specific tools (python + git-xet + playwright)
	@echo "🔧 Bootstrapping CI tools..."
	@$(MAKE) -C projects/CI install-boot-tools
	@$(MAKE) -C projects/CI install-ansible
	@$(MAKE) -C projects/CI install-node
	@echo "🔧 Bootstrapping VM-specific tools..."
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_python.sh
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_git_xet.sh
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_playwright.sh
	@echo "✅ Core bootstrap complete"

# --- Install - component selection ---

.PHONY: ci-install-deps
ci-install-deps: ensure-repos ## Install CI project deps (boot tools, Python venv, gitleaks) - delegates to CI
	@$(MAKE) -C projects/CI install-deps

.PHONY: build-guard
build-guard: ensure-repos sync-package ## Build git-guard binary (no root needed) - delegates to CI
	@$(MAKE) -C projects/CI build-guard

.PHONY: install-guard
install-guard: ## Install git-guard to /usr/bin/git (requires sudo, binary must be pre-built) - delegates to CI
	@$(MAKE) -C projects/CI install-guard

.PHONY: install
install: init-check sync-package ## Interactive TUI to select and install components
	@.venv/bin/python workspace/scripts/bootstrap_installer.py && \
	$(MAKE) register-extensions && \
	$(MAKE) install-shell && \
	$(MAKE) ci-install-deps && \
	$(MAKE) install-deps-recursive && \
	$(MAKE) install-hooks-recursive && \
	if ! $(MAKE) build-guard; then echo "⚠️  Git guard build failed - continuing without guard"; fi && \
	if ! $(MAKE) install-guard; then echo "⚠️  Git guard installation skipped (needs sudo)"; fi && \
	bash workspace/scripts/shell/shell-setup --welcome && \
	echo "" && \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" && \
	echo "⚠️  POST-INSTALL ACTION REQUIRED (needs sudo):" && \
	echo "" && \
	echo "    make enforce-syslog-limits" && \
	echo "" && \
	echo "    Enforces system-wide log ceilings (logrotate + journald rate" && \
	echo "    limiting) to prevent runaway processes from filling the root" && \
	echo "    disk via /var/log/syslog. See INCIDENT-2026-07-05." && \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

.PHONY: install-ci
install-ci: init-check sync-package ## Non-interactive component install (uses install-defaults.yaml)
	@.venv/bin/python workspace/scripts/bootstrap_installer.py --defaults workspace/config/install-defaults.yaml && \
	$(MAKE) register-extensions && \
	$(MAKE) install-shell && \
	$(MAKE) ci-install-deps && \
	$(MAKE) install-deps-recursive && \
	$(MAKE) install-hooks-recursive && \
	if ! $(MAKE) build-guard; then echo "⚠️  Git guard build failed - continuing without guard"; fi && \
	echo "✨ Installation complete (CI mode)!" && \
	echo "⚠️  Git guard binary built but not installed - run: sudo make install-guard" && \
	echo "" && \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" && \
	echo "⚠️  POST-INSTALL ACTION REQUIRED (needs sudo):" && \
	echo "" && \
	echo "    make enforce-syslog-limits" && \
	echo "" && \
	echo "    Enforces system-wide log ceilings (logrotate + journald rate" && \
	echo "    limiting) to prevent runaway processes from filling the root" && \
	echo "    disk via /var/log/syslog. See INCIDENT-2026-07-05." && \
	echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# --- System hardening (requires sudo -- run after install) ---

.PHONY: enforce-syslog-limits
enforce-syslog-limits: ## Enforce system-level log ceilings (needs sudo) - delegates to CI
	@$(MAKE) -C projects/CI enforce-syslog-limits

# --- Repos ---

.PHONY: ensure-repos
ensure-repos: ## Clone every workspace repo per moon.yml metadata
	@bash workspace/scripts/bin/bootstrap-repos --pull

# --- Package sync ---

.PHONY: sync-package
sync-package: core ensure-repos ## Sync package dependencies via uv
	@echo "🔧 Syncing workspace..."
	$(UV) sync --extra dev
	@echo "✅ Package 'workspace' installed with dev dependencies"

.PHONY: install-package
install-package: ## Lightweight uv sync (dev extras only, no boot/repos)
	$(UV) sync --extra dev

# --- Config ---

.PHONY: setup-config
setup-config: setup-automation ## Setup configuration files

.PHONY: setup-automation
setup-automation: ## Setup automation configuration
	@echo "⚙️  Setting up automation configuration..."
	@if [ ! -f "workspace/config/automation.yaml" ]; then \
		if [ -f "workspace/config/automation.template.yaml" ]; then \
			cp "workspace/config/automation.template.yaml" "workspace/config/automation.yaml"; \
			echo "✅ Created workspace/config/automation.yaml from template"; \
		else \
			echo "⚠️  Template workspace/config/automation.template.yaml not found"; \
		fi \
	else \
		echo "ℹ️  Automation configuration already exists at workspace/config/automation.yaml"; \
	fi

# --- Extensions ---

.PHONY: register-extensions
register-extensions: ## Register extensions in .boot-linux/bin
	@echo "🔌 Registering extensions in ~/.bashrc..."
	@.venv/bin/python workspace/scripts/register_extensions.py

# --- Shell ---

.PHONY: install-shell
install-shell: ## Install AMI shell environment to ~/.bashrc
	@echo "🐚 Installing shell environment..."
	@bash workspace/scripts/shell/shell-setup --install
	@echo "✅ Shell environment installed"

.PHONY: uninstall-shell
uninstall-shell: ## Remove AMI shell environment from ~/.bashrc
	@bash workspace/scripts/shell/shell-setup --uninstall

# --- VM Management ---

.PHONY: vm vm-start vm-stop vm-resume vm-delete vm-kill vm-shell vm-exec \
	vm-logs vm-list vm-status vm-rebuild vm-sync vm-config vm-cert

vm: ## Build and start a VM from config file
	@bash workspace/scripts/bin/vm create "$(filter-out $@,$(MAKECMDGOALS))"
%::
	@true

vm-start: ## podman start <id> + write PID
	@bash workspace/scripts/bin/vm start $(filter-out $@,$(MAKECMDGOALS))
vm-stop: ## podman stop <id> + remove PID
	@bash workspace/scripts/bin/vm stop $(filter-out $@,$(MAKECMDGOALS))
vm-resume: ## podman start <id> (alias)
	@bash workspace/scripts/bin/vm start $(filter-out $@,$(MAKECMDGOALS))
vm-delete: ## podman rm <id> + optional volume purge
	@bash workspace/scripts/bin/vm delete $(filter-out $@,$(MAKECMDGOALS))
vm-kill: ## read .vms/<id>/pid and send SIGKILL directly
	@bash workspace/scripts/bin/vm kill $(filter-out $@,$(MAKECMDGOALS))
vm-shell: ## podman exec -it <id> bash
	@bash workspace/scripts/bin/vm shell $(filter-out $@,$(MAKECMDGOALS))
vm-exec: ## podman exec <id> -- <cmd>
	@bash workspace/scripts/bin/vm exec $(filter-out $@,$(MAKECMDGOALS))
vm-logs: ## podman logs <id>
	@bash workspace/scripts/bin/vm logs $(filter-out $@,$(MAKECMDGOALS))
vm-list: ## podman ps -a --filter label=ami.type=vm
	@bash workspace/scripts/bin/vm list
vm-status: ## podman inspect + stats for <id>
	@bash workspace/scripts/bin/vm status $(filter-out $@,$(MAKECMDGOALS))
vm-rebuild: ## re-build + restart <id> from stored vm.yaml
	@bash workspace/scripts/bin/vm rebuild $(filter-out $@,$(MAKECMDGOALS))
vm-sync: ## file sync per config.sync rules
	@bash workspace/scripts/bin/vm sync $(filter-out $@,$(MAKECMDGOALS))
vm-config: ## print the vm.yaml used to create <id>
	@bash workspace/scripts/bin/vm config $(filter-out $@,$(MAKECMDGOALS))
vm-cert: ## generate or print client cert for <id>
	@bash workspace/scripts/bin/vm cert $(filter-out $@,$(MAKECMDGOALS))

# --- Hooks ---

.PHONY: install-hooks
install-hooks: ensure-repos ## Install native git hooks
	@if [ -x projects/CI/scripts/cleanup-precommit ]; then bash projects/CI/scripts/cleanup-precommit; fi
	bash projects/CI/scripts/generate-hooks

.PHONY: install-deps-recursive
install-deps-recursive: ensure-repos ## Install deps in every nested repo (skip CI, handled by ci-install-deps)
	@_failed=0; \
	for repo in $$(bash projects/CI/scripts/walk-projects); do \
		if [ "$$repo" = "projects/CI" ]; then continue; fi; \
		echo ""; \
		echo "📦 Installing deps in $$repo..."; \
		$(MAKE) -C "$$repo" install-ci || { echo "❌ Dep install failed in $$repo"; _failed=$$((_failed + 1)); }; \
	done; \
	[ $$_failed -eq 0 ] || { echo "❌ Dep install failed in $$_failed repo(s)"; exit 1; }

.PHONY: install-hooks-recursive
install-hooks-recursive: ensure-repos ## Install hooks in workspace + every nested .git under projects/
	@echo "🔗 Installing hooks in workspace root..."
	@if [ -x projects/CI/scripts/cleanup-precommit ]; then bash projects/CI/scripts/cleanup-precommit; fi
	@bash projects/CI/scripts/generate-hooks
	@_failed=0; \
	for repo in $$(bash projects/CI/scripts/walk-projects); do \
		echo ""; \
		echo "🔗 Installing hooks in $$repo..."; \
		( cd "$$repo" && \
		  if [ -x $(CURDIR)/projects/CI/scripts/cleanup-precommit ]; then bash $(CURDIR)/projects/CI/scripts/cleanup-precommit; fi && \
		  bash $(CURDIR)/projects/CI/scripts/generate-hooks ) || { echo "❌ Hook install failed in $$repo"; _failed=$$((_failed + 1)); }; \
	done; \
	[ $$_failed -eq 0 ] || { echo "❌ Hook install failed in $$_failed repo(s)"; exit 1; }

.PHONY: check-hooks
check-hooks: ensure-repos ## Preview generated hooks (dry-run)
	bash projects/CI/scripts/generate-hooks --dry-run

# --- Quality & Test ---

.PHONY: test
test: ## Run tests (delegates to moon for caching)
	@moon run workspace:test

.PHONY: test-e2e
test-e2e: ## Run end-to-end VM integration tests
	@.venv/bin/python -m pytest tests/e2e/ -v -m e2e --timeout 600

.PHONY: lint
lint: ## Run linters (delegates to moon for caching)
	@moon run workspace:lint

.PHONY: type-check
type-check: ## Run type checker (delegates to moon for caching)
	@moon run workspace:type-check

.PHONY: check
check: ## Run all checks (lint + type-check + test, with caching)
	@moon run workspace:check

.PHONY: check-push
check-push: ## Pre-push gate: lint + type-check + test (single pass)
	@moon run workspace:lint && moon run workspace:type-check && moon run workspace:test

.PHONY: dead-code
dead-code: ## Run AST-based dead code analysis (delegates to moon for caching)
	@moon run workspace:dead-code

# Private implementation targets: invoked by moon's command: field.
# Not part of the contract; do not call directly.

.PHONY: _lint-impl
_lint-impl: install-package
ifdef CI
	$(UV) run ruff check --config $(CI_RUFF) --check .
	$(UV) run ruff format --config $(CI_RUFF) --check .
else
	$(UV) run ruff check --config $(CI_RUFF) --fix .
	$(UV) run ruff format --config $(CI_RUFF) .
endif

.PHONY: _type-check-impl
_type-check-impl: install-package
	MYPYPATH=".:projects/DATAOPS" $(UV) run mypy --config-file $(CI_MYPY) workspace

.PHONY: _test-impl
_test-impl: install-package
	$(UV) run pytest tests/unit tests/integration -v --timeout=30

.PHONY: _dead-code-impl
_dead-code-impl: install-package
	$(UV) run ruff check --select F401,F811 --config $(CI_RUFF) .

# --- Update ---

.PHONY: update
update: ## Update workspace via moon - walks every project topologically (^:update)
	@TMP_WS=$$(mktemp) && \
	awk -f workspace/scripts/filter_moon_workspace.awk .moon/workspace.yml > "$$TMP_WS" && \
	MOON_WORKSPACE="$$TMP_WS" moon run :update; \
	RET=$$?; rm -f "$$TMP_WS"; exit $$RET

.PHONY: update-oc
update-oc: ## Update opencode to latest version via npm
	@echo "🔄 Updating opencode..."
	@.boot-linux/bin/npm install --prefix .venv opencode-ai@latest
	@OPN_BIN=".venv/node_modules/.bin/opencode"; \
		if [ -x "$$OPN_BIN" ]; then \
			ln -sf "../../.venv/node_modules/.bin/opencode" .boot-linux/bin/opencode; \
			echo "✅ opencode $$("$$OPN_BIN" --version)"; \
		else \
			echo "❌ opencode binary not found after install" >&2; \
			exit 1; \
		fi

# --- Rules ---

.PHONY: rules
rules: ## List context rules and redeploy plugin
	@bash workspace/scripts/bin/rules list

.PHONY: rules-add
rules-add: ## Add rule - make rules-add REGEX="pattern" RULE="instruction"
	@test -n "$$REGEX" || { echo "ERROR: REGEX required" >&2; exit 1; }
	@test -n "$$RULE" || { echo "ERROR: RULE required" >&2; exit 1; }
	@bash workspace/scripts/bin/rules add -r "$$REGEX" -t "$$RULE"

.PHONY: rules-delete
rules-delete: ## Delete rule - make rules-delete NUM=3
	@test -n "$$NUM" || { echo "ERROR: NUM required" >&2; exit 1; }
	@bash workspace/scripts/bin/rules delete "$$NUM"

.PHONY: rules-update
rules-update: ## Update rule - make rules-update NUM=3 REGEX="pattern" RULE="instruction"
	@test -n "$$NUM" || { echo "ERROR: NUM required" >&2; exit 1; }
	@test -n "$$REGEX" || { echo "ERROR: REGEX required" >&2; exit 1; }
	@test -n "$$RULE" || { echo "ERROR: RULE required" >&2; exit 1; }
	@bash workspace/scripts/bin/rules update "$$NUM" -r "$$REGEX" -t "$$RULE"

.PHONY: hooks
hooks: ## List assistant response hooks and redeploy plugin
	@bash workspace/scripts/bin/rules hooks

.PHONY: hooks-add
hooks-add: ## Add hook - make hooks-add REGEX="pattern" RULE="instruction"
	@test -n "$$REGEX" || { echo "ERROR: REGEX required" >&2; exit 1; }
	@test -n "$$RULE" || { echo "ERROR: RULE required" >&2; exit 1; }
	@bash workspace/scripts/bin/rules hooks add -r "$$REGEX" -t "$$RULE"

.PHONY: hooks-delete
hooks-delete: ## Delete hook - make hooks-delete NUM=3
	@test -n "$$NUM" || { echo "ERROR: NUM required" >&2; exit 1; }
	@bash workspace/scripts/bin/rules hooks delete "$$NUM"

.PHONY: hooks-update
hooks-update: ## Update hook - make hooks-update NUM=3 REGEX="pattern" RULE="instruction"
	@test -n "$$NUM" || { echo "ERROR: NUM required" >&2; exit 1; }
	@test -n "$$REGEX" || { echo "ERROR: REGEX required" >&2; exit 1; }
	@test -n "$$RULE" || { echo "ERROR: RULE required" >&2; exit 1; }
	@bash workspace/scripts/bin/rules hooks update "$$NUM" -r "$$REGEX" -t "$$RULE"

.PHONY: update-deps
update-deps: ## Update Python dependencies only
	@echo "🔄 Updating Python dependencies..."
	$(UV) update

.PHONY: uninstall
uninstall: ## Uninstall workspace
	@echo "🗑️  Uninstalling workspace..."
	$(UV) pip uninstall workspace -y

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
	@bash projects/CI/scripts/walk-projects | while IFS= read -r repo; do \
		_tier=$$(bash -c "source projects/CI/lib/checks_quality.sh && \
			ci_resolve_tier '$$repo' \
			'$(CURDIR)/workspace/config/project_enforcement.yaml'"); \
		if [ -z "$$_tier" ]; then _tier=strict; fi; \
		if [ "$$_tier" != "strict" ]; then continue; fi; \
		if [ ! -f "$$repo/quality_exceptions.yaml" ]; then \
			pname=$$(basename "$$repo"); \
			sed "s/__PROJECT_NAME__/$$pname/" \
				projects/CI/templates/quality_exceptions.template.yaml \
				> "$$repo/quality_exceptions.yaml"; \
			echo "📝 Scaffolded $$repo/quality_exceptions.yaml (tier=strict)"; \
		fi; \
	done

.PHONY: check-compliance-recursive
check-compliance-recursive: ensure-repos ## Audit every nested repo for CI contract compliance
	@_failed=0; \
	bash projects/CI/scripts/walk-projects | while IFS= read -r repo; do \
		echo ""; \
		echo "═══ Compliance: $$repo ═══"; \
		bash -c "source projects/CI/lib/checks.sh && ci_compliance_score '$$repo'" \
			|| _failed=$$((_failed + 1)); \
	done; \
	[ $$_failed -eq 0 ]

# ==============================================================================
# LlamaServer - multi-flavor build + deployment (cpu, sycl, vulkan)
# ==============================================================================
-include Makefile.llamaserver
