# INSTRUCTIONS FOR NEXT AGENT -- VM Root: Delete Obsolete Files + Rewire to CI

## CROSS-REPO OVERVIEW

This refactor spans 3 repos. Each has its own spec doc:

| # | Repo | Spec doc | What happens there | Depends on |
|---|------|-----------------|-------------------|------------|
| 1 | `projects/CI` | `CI/docs/SPEC-CI-SHARED-CONFIGS.md` | Create bootstrap-ansible, add install-ansible target, create mypy.toml, unify ruff.toml | nothing (prerequisite) |
| 2 | VM root (`.`) | this file | Delete 6 obsolete files, rewire 7 files to CI configs, delete dead functions+tests, fix broken _-impl targets | CI |
| 3 | `projects/DATAOPS` | `DATAOPS/docs/SPEC-DATAOPS-CI-ONLY.md` | Rewrite Makefile (CI-only), fix .pre-commit-config.yaml paths, fix moon.yml, install hooks | CI |

**Execution order**: CI must be done FIRST. After CI is committed, DATAOPS
and VM-root can proceed in parallel (they are independent of each
other).

## SITUATION

VM-root has accumulated duplicated logic that now lives in CI:
- `res/config/mypy.toml` and `res/config/ruff.toml` are superseded by
  `projects/CI/mypy.toml` and `projects/CI/ruff.toml`.
- Three bootstrap scripts in `workspace/scripts/bootstrap/` are
  duplicated by CI's versions (with underscore -> dash naming):
  `bootstrap_uv.sh`, `bootstrap_rust.sh`, `bootstrap_podman.sh`.
- `bootstrap_ansible.sh` is broken (hardcodes `.boot-linux`, no macOS
  support); CI's new `bootstrap-ansible` replaces it.

Additionally:
- `workspace/config_utils.py` has `get_config_path()` and
  `get_vendor_config_path()` functions with ZERO production callers --
  they point at `res/config/` which is being deleted. Only tests call
  them. Dead code with dead tests.
- `moon.yml` references `make _lint-impl`, `_type-check-impl`,
  `_test-impl`, `_dead-code-impl` -- these targets DO NOT EXIST in the
  VM Makefile. Pre-existing bug.
- `moon.yml` `update` task uses `2>/dev/null || true` -- a banned
  silent-swallow pattern.
- `.pre-commit-config.yaml` hooks reference `res/config/ruff.toml` and
  `res/config/mypy.toml` -- must repoint to `projects/CI/`.
- `.gitignore` has symlink-ignore entries for `ruff.toml` and
  `mypy.toml` that are no longer needed.
- `pyproject.toml` has `res/config/*.toml` in package-data and a
  `[tool.mypy]` comment block referencing `res/config/mypy.toml`.

## PREREQUISITE: CI must be committed first

Before starting, verify that `CI/docs/SPEC-CI-SHARED-CONFIGS.md` has been
executed and committed:
- `projects/CI/mypy.toml` exists (strict shared config).
- `projects/CI/ruff.toml` has `"projects"` in its exclude list.
- `projects/CI/scripts/bootstrap-ansible` exists and is executable.
- `projects/CI/Makefile` has `install-ansible` target.

If CI is not done, do CI first.

## WHAT TO DO

### 1. DELETE obsolete files (6 files)

```bash
git rm res/config/mypy.toml
git rm res/config/ruff.toml
git rm workspace/scripts/bootstrap/bootstrap_uv.sh
git rm workspace/scripts/bootstrap/bootstrap_rust.sh
git rm workspace/scripts/bootstrap/bootstrap_podman.sh
git rm workspace/scripts/bootstrap/bootstrap_ansible.sh
```

After these deletions, `res/config/` is empty (the only other `res/`
content is `res/systemd/ami-network-setup`, a sibling subdir,
unaffected). Remove the empty directory:

```bash
rmdir res/config
```

If `res/config/` has any remaining files (unexpected), do NOT rmdir --
inspect and report.

### 2. Rewire `Makefile` -- `core` target (lines 29-39)

The `core` target currently calls 6 bootstrap scripts:

```makefile
core: ## Bootstrap uv + python + git-xet + node + ansible + playwright (prereq for sync-package)
	@echo "🔧 Bootstrapping core tools..."
	@mkdir -p .boot-linux/bin
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_uv.sh
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_python.sh
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_git_xet.sh
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_node.sh
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_ansible.sh
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_playwright.sh
	@echo "✅ Core bootstrap complete"
```

Replace `bootstrap_uv.sh` and `bootstrap_ansible.sh` calls with
delegation to CI. Keep the 4 VM-specific bootstraps
(`bootstrap_python.sh`, `bootstrap_git_xet.sh`, `bootstrap_node.sh`,
`bootstrap_playwright.sh`). Remove the `@mkdir -p .boot-linux/bin` line
(CI's bootstrap-uv creates its own boot dir).

New `core` target:

```makefile
core: ## Bootstrap CI tools (uv + ansible) + VM-specific tools (python + git-xet + node + playwright)
	@echo "🔧 Bootstrapping CI tools..."
	@$(MAKE) -C projects/CI install-boot-tools
	@$(MAKE) -C projects/CI install-ansible
	@echo "🔧 Bootstrapping VM-specific tools..."
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_python.sh
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_git_xet.sh
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_node.sh
	@AMI_ROOT="$$(pwd)" bash workspace/scripts/bootstrap/bootstrap_playwright.sh
	@echo "✅ Core bootstrap complete"
```

### 3. Add platform-aware header + CI variables to `Makefile`

Add after line 1 (`# Makefile for AMI Agents`), before line 2 (`SHELL`):

```makefile
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
```

Remove the old `SHELL := /bin/bash` line (line 2) -- replaced by the
platform-aware version above.

### 4. Fix `sync-package` target (line 113-117)

Replace `.boot-linux/bin/uv` with `$(UV)`:

```makefile
sync-package: core ensure-repos ## Sync package dependencies via uv
	@echo "🔧 Syncing workspace..."
	$(UV) sync --extra dev
	@echo "✅ Package 'workspace' installed with dev dependencies"
```

### 5. Fix `update-deps` target (line 351-354)

Replace `.boot-linux/bin/uv` with `$(UV)`:

```makefile
update-deps: ## Update Python dependencies only
	@echo "🔄 Updating Python dependencies..."
	$(UV) update
```

### 6. Fix `uninstall` target (line 356-359)

Replace `.boot-linux/bin/uv` with `$(UV)`:

```makefile
uninstall: ## Uninstall workspace
	@echo "🗑️  Uninstalling workspace..."
	$(UV) pip uninstall workspace -y
```

### 7. Delete `setup-linter-config` target (lines 124-142)

Delete the entire `setup-linter-config` target. The symlinks it creates
(`ruff.toml` -> `res/config/ruff.toml`, `mypy.toml` ->
`res/config/mypy.toml`) are no longer needed -- hooks and make targets
reference `projects/CI/ruff.toml` and `projects/CI/mypy.toml` directly.

Update `setup-config` (line 121-122) to drop the `setup-linter-config`
dependency:

```makefile
setup-config: setup-automation ## Setup configuration files
```

### 8. Add `_lint-impl`, `_type-check-impl`, `_test-impl`, `_dead-code-impl` targets

These targets are referenced by `moon.yml` (lines 33, 42, 49, 58) but
do NOT EXIST in the VM Makefile. Add them. Place after the existing
quality targets (after line 281, `dead-code` target).

The convention (from CI and DATAOPS Makefiles): public targets delegate
to `moon run workspace:X`; moon calls `make _X-impl`; `_X-impl` runs
the actual tool. Use CI's configs.

```makefile
# Private implementation targets: invoked by moon's command: field.
# Not part of the contract; do not call directly.

.PHONY: _lint-impl
_lint-impl:
ifdef CI
	$(UV) run ruff check --config $(CI_RUFF) --check .
	$(UV) run ruff format --config $(CI_RUFF) --check .
else
	$(UV) run ruff check --config $(CI_RUFF) --fix .
	$(UV) run ruff format --config $(CI_RUFF) .
endif

.PHONY: _type-check-impl
_type-check-impl:
	$(UV) run mypy --config-file $(CI_MYPY) workspace

.PHONY: _test-impl
_test-impl:
	$(UV) run pytest tests/unit tests/integration -v --timeout=30

.PHONY: _dead-code-impl
_dead-code-impl:
	$(UV) run ruff check --select F401,F811 --config $(CI_RUFF) .
```

NOTE on `_dead-code-impl`: The original `dead-code` target comment says
"AST-based dead code analysis" which implies vulture. However, vulture
is NOT installed (not in any pyproject.toml dev deps, not in any .venv).
CI and DATAOPS do NOT have dead-code targets at all. Ruff's `F401`
(unused import) and `F811` (redefined-while-unused) provide a subset of
dead-code detection already available via the installed ruff. If full
vulture analysis is desired later, add `vulture` to VM pyproject dev
deps and update this target.

NOTE on `_type-check-impl`: VM scans the `workspace` package (the VM's
own Python code). It does NOT scan `projects/` (CI, DATAOPS, GUARD each
have their own type-check tasks). The `CI/mypy.toml` config has no
`exclude` entry for `^projects/` -- VM-root adds this via the
`pyproject.toml` `[tool.mypy]` section (see step 10 below), which mypy
auto-discovers and merges with the explicitly-passed `--config-file`.

### 9. Rewire `.pre-commit-config.yaml` -- config paths (lines 12, 18, 104)

Three hooks reference VM-root configs. Repoint to CI:

| Line | Old | New |
|------|-----|-----|
| 12 | `--config res/config/ruff.toml` | `--config projects/CI/ruff.toml` |
| 18 | `--config res/config/ruff.toml` | `--config projects/CI/ruff.toml` |
| 104 | `--config-file res/config/mypy.toml, workspace` | `--config-file projects/CI/mypy.toml, workspace` |

Use the `edit` tool for each line. Do NOT change any hook logic, entry
commands (except the config path), or structure.

### 10. Rewire `moon.yml` -- config input paths (lines 39, 46) + update task (line 86)

`moon.yml` declares `res/config/ruff.toml` and `res/config/mypy.toml`
as task inputs for cache invalidation. These files are being deleted;
the inputs must point at the CI configs.

| Line | Old | New |
|------|-----|-----|
| 39 | `'res/config/ruff.toml'` | `'projects/CI/ruff.toml'` |
| 46 | `'res/config/mypy.toml'` | `'projects/CI/mypy.toml''` |

Line 86 -- `update` task has banned `2>/dev/null || true`:

```yaml
  update:
    command: 'bash -c "git pull --ff-only 2>/dev/null || true && make sync"'
```

Replace with CI's pattern (logs error to stderr, continues):

```yaml
  update:
    command: 'bash -c "rc=0; git pull --ff-only || rc=$$rc; if [ $$rc -ne 0 ]; then echo \"git pull failed (rc=$$rc): continuing with make sync\" >&2; fi && make sync"'
    deps:
      - '^:update'
    options:
      cache: false
      runDepsInParallel: false
```

### 11. Rewire `pyproject.toml` -- remove res/config references (lines 77-80, 95-101)

**`[tool.setuptools.package-data]` (lines 76-80):** Remove the
`"res/config/*.toml"` and `"res/config/*.yaml"` entries. Those files
are deleted. Keep the `ami = [...]` key but with an empty list, or
remove the entire `[tool.setuptools.package-data]` section if it
becomes empty.

Current:
```toml
[tool.setuptools.package-data]
ami = [
    "res/config/*.toml",
    "res/config/*.yaml",
]
```

New (if no other package-data needed):
```toml
[tool.setuptools.package-data]
ami = []
```

**`[tool.mypy]` (lines 95-101):** The comment references
`res/config/mypy.toml` which is deleted. The `exclude` entry for
`"projects/"` is VM-specific and correct (VM should not type-check
nested repos). The `explicit_package_bases` is redundant with
`CI/mypy.toml`'s setting but harmless if mypy merges both. Replace the
comment and keep the VM-specific settings:

Current:
```toml
[tool.mypy]
# Config is in res/config/mypy.toml - mypy will auto-discover it
# NO CHEATING. All files must pass type checking.
exclude = [
    "projects/",
]
explicit_package_bases = true
```

New:
```toml
[tool.mypy]
# Shared config at projects/CI/mypy.toml (passed via --config-file in
# Makefile and .pre-commit-config.yaml). This section adds VM-specific
# merge keys: exclude projects/ (nested repos have their own type-check)
# and mypy_path for namespace package resolution.
exclude = [
    "projects/",
    "tests/",
]
mypy_path = ".:projects/CI:projects/DATAOPS"
explicit_package_bases = true
```

NOTE: mypy merges `[tool.mypy]` from `pyproject.toml` with the
explicitly-passed `--config-file projects/CI/mypy.toml`. The VM-root
`pyproject.toml` section adds VM-only keys (`exclude projects/`,
`mypy_path`) that CI's shared config does NOT have. This is the correct
separation: shared strict rules in `CI/mypy.toml`, repo-specific merge
keys in each repo's `pyproject.toml`.

### 12. Fix `.gitignore` -- remove symlink-ignore entries (lines 158-160)

Delete these 3 lines:

```
# Linter config symlinks (point to res/config/)
ruff.toml
mypy.toml
```

These symlinks are no longer created (the `setup-linter-config` target
is deleted). The ignore entries are obsolete.

### 13. Delete dead functions from `workspace/config_utils.py`

Delete two functions that have ZERO production callers and point at
deleted `res/config/` paths:

- `get_config_path(config_name: str) -> Path`
- `get_vendor_config_path(config_name: str) -> Path`

Keep `get_project_root()`, `_ProjectRootCache`, and `PROJECT_ROOT` --
these ARE used by production code (`bootstrap_components.py`,
`bootstrap_component_defs.py`).

After deletion, the file should contain: imports, `_ProjectRootCache`
class, `get_project_root()` function, `PROJECT_ROOT` constant, and the
module docstring. Nothing else.

### 14. Delete dead tests from 3 test files

**`tests/unit/test_config_utils.py`:** Delete the `TestGetConfigPath`
class (lines 14-43) and the `TestGetVendorConfigPath` class (lines
46-76). Keep `TestGetProjectRoot` (lines 79-97) and
`TestProjectRootCache` (lines 108-119). Remove the now-unused import of
`get_config_path` and `get_vendor_config_path` from the import block
(lines 6-11) -- keep `get_project_root`, `_ProjectRootCache`,
`PROJECT_ROOT`.

Current imports (lines 6-11):
```python
from workspace.config_utils import (
    _ProjectRootCache,
    get_config_path,
    get_project_root,
    get_vendor_config_path,
)
```

New imports:
```python
from workspace.config_utils import (
    PROJECT_ROOT,
    _ProjectRootCache,
    get_project_root,
)
```

NOTE: `PROJECT_ROOT` was not in the original import -- add it (the
`TestGetProjectRoot.test_uses_env_var` test doesn't use it, but
`test_project_root_constant` in `test_core_utils.py` does; importing
it here is fine for completeness -- it's a real exported symbol).
Actually: check if `PROJECT_ROOT` is used anywhere in
`test_config_utils.py`. If not, do NOT add it. Only import what the
remaining tests use:
```python
from workspace.config_utils import (
    _ProjectRootCache,
    get_project_root,
)
```

**`tests/integration/test_core_utils.py`:** In the `TestConfigUtils`
class (lines 39-65), delete `test_get_config_path_ruff` (lines 47-49)
and `test_get_vendor_config_path` (lines 51-53). Keep
`test_get_project_root_finds_pyproject`, `test_project_root_constant`,
`test_cache_reuse`, `test_env_var_fallback`. Remove `get_config_path`
and `get_vendor_config_path` from the import block (lines 12-18):

Current imports (lines 12-18):
```python
from workspace.config_utils import (
    PROJECT_ROOT,
    _ProjectRootCache,
    get_config_path,
    get_project_root,
    get_vendor_config_path,
)
```

New imports:
```python
from workspace.config_utils import (
    PROJECT_ROOT,
    _ProjectRootCache,
    get_project_root,
)
```

**`tests/integration/cli_smoke/test_workspace_smoke.py`:** Delete
`test_get_config_path_returns_valid_path` function (lines 83-85). Remove
`get_config_path` from the import on line 46:

Current import (line 46):
```python
from workspace.config_utils import get_config_path, get_project_root
```

New import:
```python
from workspace.config_utils import get_project_root
```

## EXACT STEPS TO EXECUTE

### Step 1: Verify CI is committed

```bash
test -f projects/CI/mypy.toml && echo "OK" || echo "MISSING: CI/mypy.toml"
test -f projects/CI/ruff.toml && grep -q '"projects"' projects/CI/ruff.toml && echo "OK" || echo "MISSING: projects in CI/ruff.toml"
test -x projects/CI/scripts/bootstrap-ansible && echo "OK" || echo "MISSING: bootstrap-ansible"
grep -q "install-ansible" projects/CI/Makefile && echo "OK" || echo "MISSING: install-ansible target"
```

All must say OK before proceeding.

### Step 2: Delete the 6 obsolete files

```bash
git rm res/config/mypy.toml
git rm res/config/ruff.toml
git rm workspace/scripts/bootstrap/bootstrap_uv.sh
git rm workspace/scripts/bootstrap/bootstrap_rust.sh
git rm workspace/scripts/bootstrap/bootstrap_podman.sh
git rm workspace/scripts/bootstrap/bootstrap_ansible.sh
```

### Step 3: Remove empty res/config/ directory

```bash
rmdir res/config
```

If rmdir fails (directory not empty), inspect remaining files and
report. Do NOT `rm -rf`.

### Step 4: Add platform-aware header + CI variables to Makefile

Edit `Makefile`: add the header block (section 3) after line 1, remove
old `SHELL := /bin/bash` on line 2.

### Step 5: Fix Makefile core target

Edit `Makefile` `core` target (section 2): replace bootstrap_uv.sh and
bootstrap_ansible.sh calls with `$(MAKE) -C projects/CI` delegation.

### Step 6: Fix Makefile uv references

Edit `Makefile`: replace `.boot-linux/bin/uv` with `$(UV)` in
`sync-package` (section 4), `update-deps` (section 5), `uninstall`
(section 6).

### Step 7: Delete setup-linter-config target

Edit `Makefile`: delete `setup-linter-config` target (lines 124-142),
update `setup-config` (line 122) to remove the dependency (section 7).

### Step 8: Add _-impl targets

Edit `Makefile`: add _lint-impl, _type-check-impl, _test-impl,
_dead-code-impl after the existing quality targets (section 8).

### Step 9: Rewire .pre-commit-config.yaml

Edit 3 lines (section 9): ruff format (line 12), ruff check (line 18),
mypy (line 104). Replace `res/config/` with `projects/CI/`.

### Step 10: Rewire moon.yml

Edit `moon.yml`: repoint lint input (line 39), type-check input (line
46), fix update task (line 86) with CI pattern (section 10).

### Step 11: Rewire pyproject.toml

Edit `pyproject.toml`: clear package-data (section 11, lines 77-80),
rewrite [tool.mypy] section (section 11, lines 95-101).

### Step 12: Fix .gitignore

Edit `.gitignore`: delete lines 158-160 (section 12).

### Step 13: Delete dead functions from config_utils.py

Edit `workspace/config_utils.py`: delete `get_config_path()` and
`get_vendor_config_path()` functions (section 13).

### Step 14: Delete dead tests from 3 test files

Edit `tests/unit/test_config_utils.py`: delete TestGetConfigPath and
TestGetVendorConfigPath classes, update imports (section 14).

Edit `tests/integration/test_core_utils.py`: delete 2 test methods,
update imports (section 14).

Edit `tests/integration/cli_smoke/test_workspace_smoke.py`: delete 1
test function, update import (section 14).

### Step 15: Verify

```bash
# Verify no references to res/config remain
grep -rn "res/config" --include="*.toml" --include="*.yaml" --include="*.yml" --include="*.mk" --include="Makefile*" --include="*.sh" --include="*.py" . 2>/dev/null | grep -v "/.git/" | grep -v "/.venv/" | grep -v "/.boot" | grep -v "^./projects/"
# Should return: tests that still reference res/config paths in
# string literals -- these tests are about the config_utils functions
# which are being deleted. If any remain, they are stale test
# assertions that must also be deleted.

# Verify no references to deleted bootstrap scripts
grep -rn "bootstrap_uv\.sh\|bootstrap_rust\.sh\|bootstrap_podman\.sh\|bootstrap_ansible\.sh" --include="Makefile*" --include="*.sh" --include="*.yaml" --include="*.py" . 2>/dev/null | grep -v "/.git/" | grep -v "/.venv/" | grep -v "/.boot" | grep -v "^./projects/"
# Should return nothing.

# Verify _-impl targets exist
grep -n "_lint-impl\|_type-check-impl\|_test-impl\|_dead-code-impl" Makefile
# Should return 8+ lines (.PHONY + target definitions).

# Verify get_config_path / get_vendor_config_path are gone
grep -rn "get_config_path\|get_vendor_config_path" --include="*.py" . 2>/dev/null | grep -v "/.git/" | grep -v "/.venv/" | grep -v "/.boot"
# Should return nothing.

# Run lint (if CI is installed and bootstrapped)
$(MAKE) -C projects/CI install-boot-tools
$(UV) run ruff check --config $(CI_RUFF) workspace tests
$(UV) run ruff format --config $(CI_RUFF) --check workspace tests

# Run type-check
$(UV) run mypy --config-file $(CI_MYPY) workspace

# Run tests
$(UV) run pytest tests/unit tests/integration -v --timeout=30
```

### Step 16: Commit

```bash
git add -A
git commit -m "refactor: delete obsolete VM bootstrap/config logic, rewire to CI, fix broken _-impl targets"
```

## CRITICAL RULES

1. **CI must be committed first.** VM-root repoints to
   `projects/CI/mypy.toml` and `projects/CI/ruff.toml`. If those files
   don't exist, lint/type-check/pre-commit hooks are broken.
2. **Do NOT delete** `bootstrap_python.sh`, `bootstrap_git_xet.sh`,
   `bootstrap_node.sh`, `bootstrap_playwright.sh`, or any other
   `workspace/scripts/bootstrap/*.sh` not in the deletion list. These
   are VM-specific with no CI equivalent.
3. **Do NOT delete** `res/systemd/` -- only `res/config/` is being
   removed.
4. **No `2>/dev/null`, `|| true`** anywhere. The moon.yml update task
   uses CI's pattern (explicit rc capture + stderr log).
5. **Comments explain WHY, not WHAT.**
6. **Use ASCII two-hyphen (`--`) for dashes, never unicode em-dash.**
7. **`_-impl` targets use `$(UV)` from CI's boot dir**, not
   `.boot-linux/bin/uv` or system uv.
8. **`get_project_root()` and `_ProjectRootCache` stay in
   `config_utils.py`** -- they are used by production code. Only
   `get_config_path` and `get_vendor_config_path` are deleted.
9. **mypy config merge**: `CI/mypy.toml` has the shared strict rules
   (passed via `--config-file`). `pyproject.toml` `[tool.mypy]` has
   VM-specific keys (`exclude projects/`, `mypy_path`). mypy merges
   them. Do NOT duplicate strict rules in `pyproject.toml`.
10. **`update-oc` target (line 293-303) uses `.boot-linux/bin/npm`** --
    this is a VM-specific tool bootstrapped by `bootstrap_node.sh` (not
    being deleted). On macOS it would be `.boot-macos/bin/npm`, but
    `bootstrap_node.sh` hardcodes `.boot-linux`. Leave as-is for now;
    it's a separate platform-awareness issue for the node bootstrap
    script, not part of this CI migration.

## REFERENCE FILES

- `CI/docs/SPEC-CI-SHARED-CONFIGS.md` -- CI prerequisite: creates mypy.toml,
  unifies ruff.toml, creates bootstrap-ansible.
- `DATAOPS/docs/SPEC-DATAOPS-CI-ONLY.md` -- DATAOPS parallel work: Makefile
  rewrite, config repointing, hook installation.
- `projects/CI/Makefile` -- gold standard for platform-aware header,
  `_-impl` target pattern, `install-deps` target.
- `projects/CI/ruff.toml` -- unified ruff config (with "projects" in
  exclude).
- `projects/CI/mypy.toml` -- shared strict mypy config (no project-code
  exemptions).
- `projects/DATAOPS/Makefile` -- sibling `_lint-impl` etc. pattern
  (lines 202-240) with `$(CI_RUFF)` / `$(CI_MYPY)` references.
- `projects/WORKSPACE-GUARD/Makefile` -- another sibling with
  platform-aware header and CI_DIR variables.
- `workspace/config_utils.py` -- file being modified (delete dead
  functions, keep live ones).
- `tests/unit/test_config_utils.py` -- delete dead test classes.
- `tests/integration/test_core_utils.py` -- delete dead test methods.
- `tests/integration/cli_smoke/test_workspace_smoke.py` -- delete dead
  test function.

## EXPECTED END STATE

- 6 obsolete files deleted: `res/config/mypy.toml`,
  `res/config/ruff.toml`, 3 duplicated bootstrap scripts, 1 broken
  ansible bootstrap script.
- `res/config/` directory removed (empty after file deletion).
- VM Makefile has platform-aware header + CI_DIR/CI_BOOT_BIN/CI_RUFF/
  CI_MYPY/UV variables.
- `core` target delegates uv+ansible bootstrapping to CI; keeps 4
  VM-specific bootstraps.
- `.boot-linux/bin/uv` replaced by `$(UV)` everywhere in Makefile
  (except `update-oc` which uses `.boot-linux/bin/npm` -- VM-specific).
- `setup-linter-config` target deleted; `setup-config` no longer
  depends on it.
- `_lint-impl`, `_type-check-impl`, `_test-impl`, `_dead-code-impl`
  targets exist and use `$(CI_RUFF)` / `$(CI_MYPY)` / `$(UV)`.
- `.pre-commit-config.yaml` hooks reference `projects/CI/ruff.toml` and
  `projects/CI/mypy.toml`. Zero `res/config/` references.
- `moon.yml` inputs reference `projects/CI/ruff.toml` and
  `projects/CI/mypy.toml`. `update` task uses CI's error-logging pattern.
- `pyproject.toml` has no `res/config` references. `[tool.mypy]` has
  VM-specific merge keys (`exclude projects/`, `mypy_path`).
- `.gitignore` has no symlink-ignore entries for ruff.toml/mypy.toml.
- `get_config_path()` and `get_vendor_config_path()` deleted from
  `config_utils.py`. All tests for them deleted from 3 test files.
- `get_project_root()`, `_ProjectRootCache`, `PROJECT_ROOT` remain in
  `config_utils.py` (production code uses them).
- Zero references to `res/config` in any non-test file.
- Zero references to deleted bootstrap scripts in any file.
- `make _lint-impl`, `_type-check-impl`, `_test-impl`,
  `_dead-code-impl` all exist and pass.
- Committed with message: `refactor: delete obsolete VM
  bootstrap/config logic, rewire to CI, fix broken _-impl targets`.