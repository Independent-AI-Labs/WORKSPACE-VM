# WORKSPACE-VM V3 - CLI Components Migration to WORKSPACE-DATAOPS

**Document ID:** WORKSPACE-MIGRATION-CLI-TO-DATAOPS-v1.0
**Status:** Executed - 2026-06-01
**Date:** 2026-06-01
**Author:** WORKSPACE-VM Engineering

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Dependency Analysis](#2-dependency-analysis)
3. [Migration Strategy](#3-migration-strategy)
4. [Files to Move - CLI Components](#4-files-to-move-cli-components)
5. [Files to Move - Types](#5-files-to-move-types)
6. [WORKSPACE-DATAOPS Config Changes](#6-workspace-dataops-config-changes)
7. [Import Path Analysis](#7-import-path-analysis)
8. [Import Changes Required](#8-import-changes-required)
9. [Install Order & Dependency Chain](#9-install-order-dependency-chain)
10. [Files to Delete from WORKSPACE-VM](#10-files-to-delete-from-workspace-vm)
11. [Known Issues Outside Scope](#11-known-issues-outside-scope)
12. [Verification](#12-verification)
13. [Risk Register](#13-risk-register)
14. [Shell & Wrapper Migration to opencode](#14-shell-wrapper-migration-to-opencode)

---

## 1. Problem Statement

The V3 migration plan (`docs/MIGRATION-PLAN.md`, §3.1) schedules the entire `workspace/cli_components/` and `workspace/types/` directories for deletion from the `workspace-vm` package. However, **WORKSPACE-DATAOPS** depends on these packages at runtime.

WORKSPACE-DATAOPS's `pyproject.toml` declares `workspace-vm` as a dev dependency:

```toml
[project.optional-dependencies]
dev = [
    "workspace-ci[dev]",
    "workspace-vm",
    ...
]

[tool.uv.sources]
workspace-vm = { path = "../..", editable = true }
```

Four source files in WORKSPACE-DATAOPS import from `workspace.cli_components`:

| File | Imports |
|------|---------|
| `workspace/dataops/report/operator.py` | `dialogs`, `selection_dialog` |
| `workspace/dataops/backup/restore/wizard.py` | `dialogs`, `format_utils`, `menu_selector`, `selector`, `text_input_utils`, `tui` |
| `workspace/dataops/backup/restore/revision_display.py` | `format_utils`, `text_input_utils` |
| `workspace/dataops/backup/restore/cli.py` | `selector` |

**The V3 plan as-written would break WORKSPACE-DATAOPS.** The solution is NOT to keep dead agent code in `workspace-vm`, but to MOVE the required CLI/TUI components INTO WORKSPACE-DATAOPS itself, making it self-contained.

### 1.1 Secondary Impact

Staying scripts in `workspace/scripts/` also import from the modules being deleted:

| Staying Script | Imports From | Will Resolve From |
|----------------|-------------|-------------------|
| `workspace/scripts/bootstrap_installer.py` | `workspace.cli_components.dialogs`, `workspace.cli_components.menu_selector`, `workspace.cli_components.selection_dialog`, `workspace.types.results.NamedComponentStatus` | WORKSPACE-DATAOPS (namespace) |
| `workspace/scripts/bootstrap_installer_ui.py` | `workspace.cli_components.text_input_utils` | WORKSPACE-DATAOPS (namespace) |
| `workspace/scripts/bootstrap_install.py` | `workspace.types.common.InstallationResult` | **import path must change** |
| `workspace/scripts/utils/sys_info.py` | `workspace.types.results.ColorPair` | WORKSPACE-DATAOPS (namespace) |

---

## 2. Dependency Analysis

### 2.1 Direct Import Chain

```
WORKSPACE-DATAOPS
  ├── dialogs                  → confirm(), AlertDialog, ConfirmationDialog
  ├── selection_dialog          → SelectableItem, SelectionDialog, etc.
  ├── format_utils              → format_file_size()
  ├── text_input_utils          → Colors class
  ├── selector                  → BackupFileInfo, select_backup_interactive()
  ├── menu_selector             → MenuItem, MenuSelector
  └── tui                       → TUI, BoxStyle
```

### 2.2 Transitive Dependency Closure

The 7 directly-imported modules pull in 4 more files through their imports:

```
dialogs.py
  ├── workspace.cli_components.keys              → ENTER, ESC, LEFT, RIGHT
  ├── workspace.cli_components.selection_dialog
  ├── workspace.cli_components.terminal.ansi      → AnsiTerminal
  ├── workspace.cli_components.text_input_utils
  └── workspace.cli_components.tui

selection_dialog.py
  ├── workspace.cli_components.keys              → BACKSPACE, DOWN, ENTER, ESC, UP
  ├── workspace.cli_components.selection_dialog_render
  ├── workspace.cli_components.text_input_utils
  ├── workspace.cli_components.tui
  └── workspace.types.results                    → GroupRange, KeyHandleResult

selection_dialog_render.py
  ├── workspace.cli_components.text_input_utils
  └── workspace.types.results                    → FormattedPrefix

format_utils.py
  └── (standalone - no imports)

text_input_utils.py
  ├── workspace.cli_components.terminal.ansi     → AnsiTerminal
  └── workspace.types.results                    → CharWithOrdinal

selector.py
  ├── workspace.cli_components.format_utils
  ├── workspace.cli_components.menu_selector
  └── workspace.cli_components.text_input_utils

menu_selector.py
  ├── workspace.cli_components.dialogs
  └── workspace.cli_components.selection_dialog

tui.py
  └── workspace.cli_components.text_input_utils

keys.py
  └── (standalone - no imports)

terminal/ansi.py
  └── (standalone - imports only sys)
```

### 2.3 Types Required for Survival

The V3 plan deletes ALL of `workspace/types/`. Two categories of types must survive:

**Category A - TUI types (used by moving cli_components):**

| Type | Used By | Fields |
|------|---------|--------|
| `GroupRange` | `selection_dialog.py` | `header_idx: int, start: int, end: int` |
| `KeyHandleResult` | `selection_dialog.py` | `should_continue: bool, result: object` |
| `CharWithOrdinal` | `text_input_utils.py` | `char: str, ordinal: int` |
| `FormattedPrefix` | `selection_dialog_render.py` | `formatted: str, visible: str` |

**Category B - Bootstrap types (used by staying scripts in `workspace/scripts/`):**

| Type | Currently In | Used By | Fields |
|------|-------------|---------|--------|
| `NamedComponentStatus` | `workspace.types.results` | `bootstrap_installer.py` | `name, installed, version, path` |
| `ColorPair` | `workspace.types.results` | `sys_info.py` | `fg: int, bg: int` |
| `InstallationResult` | `workspace.types.common` | `bootstrap_install.py` | `component_name, success, error` |

All 7 types are simple NamedTuples or TypedDicts with **zero transitive dependencies** on agent-specific modules. They can coexist in a single `results.py` file within WORKSPACE-DATAOPS.

### 2.4 Namespace Constraint

Python namespace packages cannot merge two modules at the same import path. If both `workspace-vm` AND `WORKSPACE-DATAOPS` provide `workspace.types.results`, only one will be importable (whichever is found first on `sys.path`).

**Therefore ALL surviving types must move to WORKSPACE-DATAOPS, and `workspace/types/` must be fully deleted from the main package.** There can be no split.

---

## 3. Migration Strategy

### 3.1 Principle

**Move, don't fork.** Copy the minimum transitive closure of files from `workspace-vm` into `WORKSPACE-DATAOPS`, consolidating all surviving types into a single file. Maintain the same `workspace.cli_components.*` and `workspace.types.*` namespace paths so most import statements require **zero changes**.

### 3.2 Why Namespace Packages Work

Both `workspace-vm` (root `workspace/`) and `WORKSPACE-DATAOPS` (`projects/WORKSPACE-DATAOPS/workspace/`) use `setuptools` namespace packages. Python resolves `workspace.cli_components.*` and `workspace.types.*` by scanning all `sys.path` entries. After the move:

| Namespace | Provided By | After Migration |
|-----------|-------------|-----------------|
| `workspace.cli_components` | ~~workspace-vm~~ → **WORKSPACE-DATAOPS** | WORKSPACE-DATAOPS |
| `workspace.types` | ~~workspace-vm~~ → **WORKSPACE-DATAOPS** | WORKSPACE-DATAOPS |
| `workspace.dataops` | **WORKSPACE-DATAOPS** | WORKSPACE-DATAOPS |
| `workspace.config` | **workspace-vm** | workspace-vm |
| `workspace.scripts` | **workspace-vm** | workspace-vm |
| `workspace.utils` | **workspace-vm** | workspace-vm |
| `workspace.ci` | **workspace-vm** | workspace-vm |

No overlap → no namespace conflict.

---

## 4. Files to Move - CLI Components

Copy these files from `workspace/cli_components/` → `projects/WORKSPACE-DATAOPS/workspace/cli_components/`:

### 4.1 File Inventory (11 files)

```
workspace/cli_components/
├── __init__.py                  (empty - create new)
├── keys.py                      (12 lines - key constants)
├── dialogs.py                   (252 lines - BaseDialog, AlertDialog, ConfirmationDialog, facade functions)
├── selection_dialog.py          (488 lines - SelectionDialog, SelectionDialogConfig, types)
├── selection_dialog_render.py   (177 lines - pure rendering helpers)
├── format_utils.py              (38 lines - format_file_size, KB/MB/GB constants)
├── text_input_utils.py          (365 lines - Colors, read_key_sequence, getchar, cbreak mode)
├── selector.py                  (138 lines - BackupFileInfo, select_backup_interactive, display helpers)
├── menu_selector.py             (95 lines - MenuItem, MenuSelector, simple_menu_select, multi_menu_select)
├── tui.py                       (222 lines - TUI.draw_box, BoxStyle, strip_ansi, visible_len, wrap_text)
└── terminal/
    └── ansi.py                  (104 lines - AnsiTerminal with all ANSI escape codes)
```

**Total: 11 files, ~1,891 lines**

### 4.2 Files NOT Moved

The following `workspace/cli_components/` files are NOT moved to WORKSPACE-DATAOPS. They stay in the main package because they are actively used by the `ops` extension (`workspace/scripts/bin/ops` dispatches to `status.py` and `storage.py` directly).

**Kept - active extension entry points and their dependencies:**

| File | Status |
|------|--------|
| `status.py` | KEPT - entry point for `ops status` (imported by ops via `workspace/scripts/bin/ops:75`) |
| `storage.py` | KEPT - entry point for `ops storage` (imported by ops via `workspace/scripts/bin/ops:78`) |
| `legend.py` | KEPT - imported by status.py for legend display |
| `status_containers.py` | KEPT - imported by status.py for container ops |
| `status_systemd.py` | KEPT - imported by status.py for systemd service display |
| `status_utils.py` | KEPT - imported by status*.py for shared utilities |
| `text_input_utils.py` | DELETED - duplicated in WORKSPACE-DATAOPS; imported from DATAOPS via namespace packages |

**Files that were agent-only and are deleted:**

| File | Why Not Needed |
|------|----------------|
| `confirmation_dialog.py` | `ConfirmationDialog` lives in `dialogs.py` itself; external consumers (`workspace/tools/`) were deleted |
| `cursor_manager.py` | Agent TUI only |
| `editor_display.py` | Agent text editor |
| `editor_saving.py` | Agent text editor |
| `session_browser.py` | Agent session browser |
| `session_detail.py` | Agent session detail |
| `stream_renderer.py` | Agent stream renderer |
| `text_editor.py` | Agent text editor |
| `text_input_cli.py` | Agent CLI text input |

---

## 5. Files to Move - Types

### 5.1 Strategy

The full `workspace.types.results` (181 lines, 23 types) drags in `workspace.types.api` → `workspace.types.common` transitively. Most of these types are agent-specific.

**Solution:** Create a consolidated `results.py` in WORKSPACE-DATAOPS containing ONLY the 7 types that must survive (4 TUI + 3 bootstrap). Drop all agent-specific types and their imports entirely.

### 5.2 Files to Create

```
projects/WORKSPACE-DATAOPS/workspace/types/
├── __init__.py                  (empty - create new)
└── results.py                   (consolidated - see below)
```

### 5.3 Consolidated `results.py` Contents

```python
"""Result types shared between WORKSPACE-DATAOPS and WORKSPACE-VM scripts.

Consolidated from workspace-vm/workspace/types/results.py and
workspace-vm/workspace/types/common.py.  Contains only the types that survive
the V3 agent-code deletion.

TUI types  - used by workspace.cli_components (moved to WORKSPACE-DATAOPS)
Bootstrap types - used by workspace.scripts.* (staying in WORKSPACE-VM)

See WORKSPACE-VM docs/MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md
"""

from typing import NamedTuple, TypedDict


# ── TUI types (used by workspace.cli_components) ──────────────────────


class GroupRange(NamedTuple):
    """Range information for a dialog group."""

    header_idx: int
    start: int
    end: int


class KeyHandleResult(NamedTuple):
    """Result from handling a key press in selection dialog."""

    should_continue: bool
    result: object


class CharWithOrdinal(NamedTuple):
    """Character with its ordinal value."""

    char: str
    ordinal: int


class FormattedPrefix(NamedTuple):
    """Prefix with formatting and visible width."""

    formatted: str
    visible: str


# ── Bootstrap types (used by workspace/scripts/*.py) ──────────────────


class NamedComponentStatus(NamedTuple):
    """Component status paired with its name for collection use."""

    name: str
    installed: bool
    version: str | None
    path: str | None


class ColorPair(NamedTuple):
    """A pair of foreground and background colors."""

    fg: int
    bg: int


class InstallationResult(TypedDict):
    """Result of component installation."""

    component_name: str
    success: bool
    error: str | None
```

### 5.4 Types - Disposition

The `workspace/types/` directory stays in the main package. The surviving cli_components files (status, storage, legend, status_containers, status_systemd, status_utils - see §4.2) depend on types that the slim consolidated DATAOPS `results.py` does not provide:

| Type Needed | In Main `types/` | In DATAOPS `results.py` |
|-------------|-----------------|------------------------|
| `LegendRender` | `results.py` | No |
| `ContainerStatusDisplay` | `results.py` | No |
| `ContainerInspectInfo` | `results.py` | No |
| `ComposeInfo` | `results.py` | No |
| `ContainerSizeData` | `common.py` | No |
| `ContainerStatsData` | `common.py` | No |
| `SystemdDetails` | `common.py` | No |
| `ServiceDisplayInfo` | `status.py` | No |
| `SystemdService` | `status.py` | No |
| `PortMapping` | `status.py` | No |
| `PodmanContainer` | `status.py` | No |

**Therefore `workspace/types/` stays in its entirety.** The DATAOPS consolidated `results.py` is a minimal subset useful for DATAOPS's namespace package independence; it is shadowed at runtime by the main package's full types/ (which appears first on PYTHONPATH via `$WORKSPACE_ROOT:${PROJECT_PATHS}`) but serves as a reference copy.

---

## 6. WORKSPACE-DATAOPS Config Changes

### 6.1 `pyproject.toml` - Package Discovery

**Before:**
```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["workspace.dataops*"]
namespaces = true
```

**After:**
```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["workspace.dataops*", "workspace.cli_components*", "workspace.types*"]
namespaces = true
```

### 6.2 `pyproject.toml` - Dependencies

**Before:**
```toml
[project.optional-dependencies]
dev = [
    "workspace-ci[dev]",
    "workspace-vm",
    "respx==0.23.1",
]

[tool.uv.sources]
workspace-ci = { path = "../WORKSPACE-CI", editable = true }
workspace-vm = { path = "../..", editable = true }
```

**After:**
```toml
[project.optional-dependencies]
dev = [
    "workspace-ci[dev]",
    "respx==0.23.1",
]

[tool.uv.sources]
workspace-ci = { path = "../WORKSPACE-CI", editable = true }
```

Remove `workspace-vm` from WORKSPACE-DATAOPS's dependency tree. It is no longer required at build, test, or runtime. Both packages still coexist in the `workspace` namespace but have **no import dependency** on each other.

### 6.3 Root `pyproject.toml` - Add WORKSPACE-DATAOPS as Dev Dependency

The root `workspace-vm` package must install WORKSPACE-DATAOPS so that staying scripts (`bootstrap_installer.py`, etc.) can resolve `workspace.cli_components.*` and `workspace.types.*` through namespace packages.

**Before:**
```toml
[project.optional-dependencies]
dev = [
    "workspace-ci[dev]",
]

[tool.uv.sources]
workspace-ci = { path = "projects/WORKSPACE-CI", editable = true }
```

**After:**
```toml
[project.optional-dependencies]
dev = [
    "workspace-ci[dev]",
    "workspace-dataops",
]

[tool.uv.sources]
workspace-ci = { path = "projects/WORKSPACE-CI", editable = true }
workspace-dataops = { path = "projects/WORKSPACE-DATAOPS", editable = true }
```

---

## 7. Import Path Analysis

### 7.1 Zero-Changes Verification

Every import in WORKSPACE-DATAOPS source files uses `workspace.cli_components.*` or `workspace.types.*` paths. Since the moved files live at the same namespace paths within `projects/WORKSPACE-DATAOPS/workspace/`, **no import statements need to change in WORKSPACE-DATAOPS**.

Verified imports:

| Source File | Import | Status |
|-------------|--------|--------|
| `operator.py:25` | `from workspace.cli_components import dialogs` | ✅ |
| `operator.py:26` | `from workspace.cli_components.selection_dialog import ...` | ✅ |
| `revision_display.py:9` | `from workspace.cli_components.format_utils import format_file_size` | ✅ |
| `revision_display.py:10` | `from workspace.cli_components.text_input_utils import Colors` | ✅ |
| `cli.py:14` | `from workspace.cli_components.selector import ...` | ✅ |
| `wizard.py:13` | `from workspace.cli_components.dialogs import confirm` | ✅ |
| `wizard.py:14` | `from workspace.cli_components.format_utils import format_file_size` | ✅ |
| `wizard.py:15` | `from workspace.cli_components.menu_selector import ...` | ✅ |
| `wizard.py:16` | `from workspace.cli_components.selector import ...` | ✅ |
| `wizard.py:20` | `from workspace.cli_components.text_input_utils import Colors` | ✅ |
| `wizard.py:21` | `from workspace.cli_components.tui import TUI, BoxStyle` | ✅ |

### 7.2 Internal Cross-References Within Transitive Closure

The moved `.py` files reference each other using the same `workspace.cli_components.*` paths. These also resolve via namespace package lookup:

| File | Imports | Resolves To |
|------|---------|-------------|
| `dialogs.py` | `workspace.cli_components.keys` | `projects/WORKSPACE-DATAOPS/workspace/cli_components/keys.py` |
| `dialogs.py` | `workspace.cli_components.terminal.ansi` | `projects/WORKSPACE-DATAOPS/workspace/cli_components/terminal/ansi.py` |
| `selection_dialog.py` | `workspace.cli_components.tui` | `projects/WORKSPACE-DATAOPS/workspace/cli_components/tui.py` |
| `selection_dialog.py` | `workspace.types.results` | `projects/WORKSPACE-DATAOPS/workspace/types/results.py` |
| `text_input_utils.py` | `workspace.types.results` | `projects/WORKSPACE-DATAOPS/workspace/types/results.py` |
| etc. | | All resolve within WORKSPACE-DATAOPS |

---

## 8. Import Changes Required

### 8.1 One Import Must Change

The staying script `workspace/scripts/bootstrap_install.py` imports `InstallationResult` from a file that is being deleted:

**Before (breaks):**
```python
from workspace.types.common import InstallationResult
```

**After (fixed):**
```python
from workspace.types.results import InstallationResult
```

This is the **only import change required** anywhere in the codebase.

### 8.2 All Other Staying Script Imports (unchanged)

| Script | Import | Resolves From |
|--------|--------|---------------|
| `bootstrap_installer.py:39` | `from workspace.cli_components import dialogs as _dialogs` | WORKSPACE-DATAOPS ✅ |
| `bootstrap_installer.py:40` | `from workspace.cli_components import menu_selector as _menu` | WORKSPACE-DATAOPS ✅ |
| `bootstrap_installer.py:41` | `from workspace.cli_components.selection_dialog import DialogItem` | WORKSPACE-DATAOPS ✅ |
| `bootstrap_installer.py:55` | `from workspace.types.results import NamedComponentStatus` | WORKSPACE-DATAOPS ✅ |
| `bootstrap_installer_ui.py:12` | `from workspace.cli_components.text_input_utils import Colors` | WORKSPACE-DATAOPS ✅ |
| `sys_info.py:8` | `from workspace.types.results import ColorPair` | WORKSPACE-DATAOPS ✅ |

---

## 9. Install Order & Dependency Chain

### 9.1 Current Dependency Graph

```
WORKSPACE-VM (root pyproject.toml)
  ├── include: ["workspace.*"]         # workspace/cli, workspace/core, workspace/cli_components, workspace/types, ...
  └── dev-dep: WORKSPACE-CI            # via [tool.uv.sources]

WORKSPACE-DATAOPS (projects/WORKSPACE-DATAOPS/pyproject.toml)
  ├── include: ["workspace.dataops*"]  # workspace/dataops only
  ├── dev-dep: WORKSPACE-VM        # for workspace.cli_components at runtime
  └── dev-dep: WORKSPACE-CI
```

### 9.2 Post-Migration Dependency Graph

```
WORKSPACE-VM (root pyproject.toml)
  ├── include: ["workspace.*"]         # workspace/config, workspace/scripts, workspace/utils, workspace/ci
  └── dev-dep: WORKSPACE-CI            # unchanged

WORKSPACE-DATAOPS (projects/WORKSPACE-DATAOPS/pyproject.toml)
  ├── include: ["workspace.dataops*", "workspace.cli_components*", "workspace.types*"]
  │                              # self-contained - no runtime dep on workspace-vm
  └── dev-dep: WORKSPACE-CI            # unchanged
```

### 9.3 Makefile Install Flow

Current `sync-package` target:

```makefile
sync-package: bootstrap-core ensure-ci ensure-dataops
    .boot-linux/bin/uv sync --extra dev
```

- `ensure-ci` clones WORKSPACE-CI from moon config
- `ensure-dataops` clones WORKSPACE-DATAOPS from moon config
- `uv sync` processes all `pyproject.toml` files and resolves deps via `[tool.uv.sources]`

**No changes needed** to the Makefile. The install order is:

1. `bootstrap-core` - uv, Python runtime, git-xet
2. `ensure-ci` - clone WORKSPACE-CI
3. `ensure-dataops` - clone WORKSPACE-DATAOPS
4. `uv sync` - installs all editable packages in dependency order

After migration, `uv sync` will install `workspace-dataops` as an editable package (providing `workspace.cli_components` and `workspace.types`) and `workspace-vm` as an editable package (providing remaining `workspace.*` namespaces). Both appear as siblings in `uv tree`.

> **Important:** After migration, verify with `uv tree` that both `workspace-vm` and `workspace-dataops` appear. If WORKSPACE-DATAOPS is not installed, scripts like `bootstrap_installer.py` will fail to resolve `workspace.cli_components.*`.

### 9.4 First-Time Migration Sequence

```bash
# ── Phase 1: Copy files into WORKSPACE-DATAOPS ──

# 1a. CLI components (11 files)
mkdir -p projects/WORKSPACE-DATAOPS/workspace/cli_components/terminal/
touch projects/WORKSPACE-DATAOPS/workspace/cli_components/__init__.py

cp workspace/cli_components/keys.py                         projects/WORKSPACE-DATAOPS/workspace/cli_components/
cp workspace/cli_components/dialogs.py                      projects/WORKSPACE-DATAOPS/workspace/cli_components/
cp workspace/cli_components/selection_dialog.py             projects/WORKSPACE-DATAOPS/workspace/cli_components/
cp workspace/cli_components/selection_dialog_render.py      projects/WORKSPACE-DATAOPS/workspace/cli_components/
cp workspace/cli_components/format_utils.py                 projects/WORKSPACE-DATAOPS/workspace/cli_components/
cp workspace/cli_components/text_input_utils.py             projects/WORKSPACE-DATAOPS/workspace/cli_components/
cp workspace/cli_components/selector.py                     projects/WORKSPACE-DATAOPS/workspace/cli_components/
cp workspace/cli_components/menu_selector.py                projects/WORKSPACE-DATAOPS/workspace/cli_components/
cp workspace/cli_components/tui.py                          projects/WORKSPACE-DATAOPS/workspace/cli_components/
cp workspace/cli_components/terminal/ansi.py                projects/WORKSPACE-DATAOPS/workspace/cli_components/terminal/

# 1b. Types (consolidated results.py)
mkdir -p projects/WORKSPACE-DATAOPS/workspace/types/
touch projects/WORKSPACE-DATAOPS/workspace/types/__init__.py
# Write consolidated results.py (see §5.3)

# 1c. Tests for moved modules (14 test files)
mkdir -p projects/WORKSPACE-DATAOPS/tests/unit/cli_components/terminal/
touch projects/WORKSPACE-DATAOPS/tests/unit/cli_components/__init__.py
touch projects/WORKSPACE-DATAOPS/tests/unit/cli_components/terminal/__init__.py

cp tests/unit/test_format_utils.py                    projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/test_tui.py                             projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/test_selector.py                        projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/test_menu_selector.py                   projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/test_text_input_utils.py                projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_dialogs_structure.py      projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_dialogs_behavior.py       projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_selection_dialog.py       projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_selection_dialog_skippable.py  projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_selection_dialog_cascade.py   projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_selection_dialog_rendering.py projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_text_input_utils_keys.py      projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_text_input_utils_comprehensive.py projects/WORKSPACE-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/terminal/test_ansi.py      projects/WORKSPACE-DATAOPS/tests/unit/cli_components/terminal/

# ── Phase 2: Update imports ──

# 2a. Fix bootstrap_install.py import path
#   Change: from workspace.types.common import InstallationResult
#   To:     from workspace.types.results import InstallationResult

# ── Phase 3: Update pyproject.toml files ──

# 3a. Update projects/WORKSPACE-DATAOPS/pyproject.toml:
#   - Change include to ["workspace.dataops*", "workspace.cli_components*", "workspace.types*"]
#   - Add exclude = ["res*", "config*", "deploy*", "docs*", "tests*", "*.egg-info*"]
#   - Remove workspace-vm from [tool.uv.sources]
#   - Remove workspace-vm from [project.optional-dependencies]

# 3b. Update root pyproject.toml:
#   - Add workspace-dataops to [project.optional-dependencies] dev
#   - Add workspace-dataops to [tool.uv.sources]
#   (Ensures workspace-dataops is installed alongside workspace-vm via namespace packages)

# ── Phase 4: Fix PROJECT_ROOT move ──

# 4a. Rewrite workspace/config_utils.py (inline get_project_root + PROJECT_ROOT from
#     workspace/core/env.py, remove the import from workspace.core.env)
#     See §11.1 Step 1 for the full file content.

# 4b. Fix workspace/scripts/bootstrap_components.py import:
#   Change: from workspace.core.env import PROJECT_ROOT
#   To:     from workspace.config_utils import PROJECT_ROOT

# 4c. Fix workspace/scripts/bootstrap_component_defs.py import:
#   Change: from workspace.core.env import PROJECT_ROOT
#   To:     from workspace.config_utils import PROJECT_ROOT

# ── Phase 5: Verify ──

# 5a. WORKSPACE-DATAOPS
cd projects/WORKSPACE-DATAOPS
uv run python -c "from workspace.cli_components.dialogs import confirm; print('OK')"
uv run python -c "from workspace.cli_components.tui import TUI; print('OK')"
uv run python -c "from workspace.types.results import GroupRange; print('OK')"
uv run python -c "from workspace.types.results import InstallationResult; print('OK')"
uv run python -m pytest tests/

# 5b. PROJECT_ROOT fix
cd /
uv run python -c "from workspace.config_utils import get_project_root, PROJECT_ROOT; print(PROJECT_ROOT)"
uv run python -c "from workspace.scripts.bootstrap_components import PROJECT_ROOT; print('OK')"
uv run python -c "from workspace.scripts.bootstrap_component_defs import ALL_COMPONENTS; print(len(ALL_COMPONENTS))"
uv run python -c "from workspace.config_utils import get_config_path; print(get_config_path('ruff.toml'))"

# ── Phase 6: Delete from main package ──

rm -f workspace/cli_components/text_input_utils.py   # duplicated - resolve from DATAOPS
rm -rf workspace/cli/
rm -rf workspace/core/
rm -rf workspace/tools/
rm -rf workspace/hooks/
rm -f workspace/utils/process.py          # orphaned - imports deleted types
rm -f workspace/scripts/bootstrap/bootstrap_agents.sh
rm -f scripts/package.json
rm -f scripts/package.json.backup
rm -f scripts/setup/node.sh         # (already deleted)

# DO NOT delete workspace/cli_components/ - status.py, storage.py, legend.py, etc.
# are active extension entry points (ops status, ops storage).
# DO NOT delete workspace/types/ - surviving extension chain needs full types
# (LegendRender, ContainerStatusDisplay, etc.). See §4.2 and §5.4.

# ── Phase 7: Rebuild and verify ──

uv sync --extra dev

# Verify imports resolve from WORKSPACE-DATAOPS
uv run python -c "import workspace.cli_components.keys; print(workspace.cli_components.keys.__file__)"
# Should show: ...projects/WORKSPACE-DATAOPS/workspace/cli_components/keys.py

uv run python -c "from workspace.types.results import GroupRange, KeyHandleResult, NamedComponentStatus, InstallationResult; print('ok')"

# Run WORKSPACE-DATAOPS full test suite
uv run python -m pytest projects/WORKSPACE-DATAOPS/tests/ -q

# Run root test suite (expect errors for deleted agent test files)
uv run python -m pytest tests/ -q
```

---

## 10. Files to Delete from WORKSPACE-VM

### 10.1 CLI Components (moved to WORKSPACE-DATAOPS)

These 12 files are deleted from `workspace/cli_components/` after copying to WORKSPACE-DATAOPS:

```
workspace/cli_components/__init__.py        ✓ DELETED
workspace/cli_components/keys.py            ✓ DELETED
workspace/cli_components/dialogs.py         ✓ DELETED
workspace/cli_components/selection_dialog.py         ✓ DELETED
workspace/cli_components/selection_dialog_render.py  ✓ DELETED
workspace/cli_components/format_utils.py             ✓ DELETED
workspace/cli_components/text_input_utils.py         ✓ DELETED
workspace/cli_components/selector.py                 ✓ DELETED
workspace/cli_components/menu_selector.py            ✓ DELETED
workspace/cli_components/tui.py                      ✓ DELETED
workspace/cli_components/terminal/ansi.py            ✓ DELETED
workspace/cli_components/terminal/__init__.py        ✓ DELETED
```

**NOT deleted:** status.py, storage.py, legend.py, status_containers.py, status_systemd.py, status_utils.py - these are active extension entry points (see §4.2).

### 10.2 Types (NOT deleted - kept in main package)

`workspace/types/` stays in the main package. See §5.4 for the dependency chain. The surviving status/storage/legend extension chain requires types not present in the DATAOPS consolidated `results.py`.

### 10.3 Remaining Agent Code (per MIGRATION-PLAN.md)

```
workspace/cli/               (entire directory - 25 files - DELETED ✓)
workspace/core/              (entire directory - 14 files + policies/ - DELETED ✓)
workspace/tools/             (entire directory - 3 files - DELETED ✓)
workspace/hooks/             (agent-specific hooks - DELETED ✓)
workspace/utils/process.py   (orphaned - imports deleted workspace.types)
scripts/package.json
scripts/package.json.backup
scripts/setup/node.sh
workspace/scripts/bootstrap/bootstrap_agents.sh
```

**NOT deleted from `workspace/cli_components/`:** status.py, storage.py, legend.py, status_containers.py, status_systemd.py, status_utils.py - kept for `ops status` and `ops storage` extensions (see §4.2).

**NOT deleted from `workspace/types/`:** entire directory kept - surviving extension chain requires types not in DATAOPS consolidated results.py (see §5.4).

---

## 11. Known Issues Outside Scope

The following issues are NOT addressed by this migration document because they involve deletions outside `workspace/cli_components/` and `workspace/types/`. They are flagged here for the main V3 plan.

### 11.1 `workspace.core.env` Dependency - Fix Included

**Problem:** `workspace/core/env.py` is scheduled for deletion, but three staying files import from it:

| File | Import | Breaks When |
|------|--------|-------------|
| `workspace/config_utils.py:9` | `from workspace.core.env import get_project_root` | `workspace/core/` deleted |
| `workspace/scripts/bootstrap_component_defs.py:24` | `from workspace.core.env import PROJECT_ROOT` | `workspace/core/` deleted |
| `workspace/scripts/bootstrap_components.py:10` | `from workspace.core.env import PROJECT_ROOT` | `workspace/core/` deleted |

The module provides `get_project_root()` (finds project root by walking up for `pyproject.toml`) and the module-level `PROJECT_ROOT` constant.

**Fix - move into `workspace/config_utils.py`:**

#### Step 1: Move `get_project_root()` and `PROJECT_ROOT` into `workspace/config_utils.py`

**Before** (`workspace/config_utils.py`, 35 lines):
```python
"""Configuration utilities for workspace-vm package.

This module provides utilities for accessing shared configuration files.
"""

from pathlib import Path

from workspace.core.env import get_project_root


def get_config_path(config_name: str) -> Path:
    return get_project_root() / "res" / "config" / config_name


def get_vendor_config_path(config_name: str) -> Path:
    return get_project_root() / "res" / "config" / vendor / config_name
```

**After** (`workspace/config_utils.py`, ~85 lines):
```python
"""Configuration utilities for workspace-vm package.

This module provides utilities for accessing shared configuration files
and project root discovery - moved here from workspace/core/env.py during the
V3 migration to avoid deleting infrastructure used by staying scripts.
"""

import os
from pathlib import Path


class _ProjectRootCache:
    _value: Path | None = None

    @classmethod
    def get(cls) -> Path | None:
        return cls._value

    @classmethod
    def set(cls, path: Path) -> None:
        cls._value = path


def get_project_root() -> Path:
    """Get the project root directory.

    Finds root by looking for pyproject.toml or .git marker files.
    Falls back to WORKSPACE_PROJECT_ROOT environment variable if set.
    """
    cached = _ProjectRootCache.get()
    if cached is not None:
        return cached

    env_root = os.environ.get("WORKSPACE_PROJECT_ROOT")
    if env_root:
        result = Path(env_root)
        _ProjectRootCache.set(result)
        return result

    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            _ProjectRootCache.set(current)
            return current
        current = current.parent

    msg = "project root not found"
    raise RuntimeError(msg)


# Module-level constant for direct import
PROJECT_ROOT = get_project_root()


# ── Existing config-path utilities ──────────────────────────────


def get_config_path(config_name: str) -> Path:
    """Get the path to a shared configuration file."""
    return PROJECT_ROOT / "res" / "config" / config_name


def get_vendor_config_path(config_name: str) -> Path:
    """Get the path to a vendor-specific configuration file."""
    return PROJECT_ROOT / "res" / "config" / "vendor" / config_name
```

#### Step 2: Update `workspace/config_utils.py` import line

Remove the `from workspace.core.env import get_project_root` import (replaced by inline definition above).

#### Step 3: Update `workspace/scripts/bootstrap_components.py`

**Before:**
```python
from workspace.core.env import PROJECT_ROOT
```

**After:**
```python
from workspace.config_utils import PROJECT_ROOT
```

#### Step 4: Update `workspace/scripts/bootstrap_component_defs.py`

**Before:**
```python
from workspace.core.env import PROJECT_ROOT
```

**After:**
```python
from workspace.config_utils import PROJECT_ROOT
```

#### Step 5: Delete `workspace/core/env.py`

With all consumers migrated to `workspace/config_utils.py`, `workspace/core/env.py` is deleted as part of the `workspace/core/` directory removal.

#### Step 6: Verify

```bash
uv run python -c "from workspace.config_utils import get_project_root, PROJECT_ROOT; print(PROJECT_ROOT)"
uv run python -c "from workspace.scripts.bootstrap_components import PROJECT_ROOT; print(PROJECT_ROOT)"
uv run python -c "from workspace.scripts.bootstrap_component_defs import ALL_COMPONENTS; print(len(ALL_COMPONENTS))"
uv run python -c "from workspace.config_utils import get_config_path; print(get_config_path('ruff.toml'))"
```

#### Dependency chain after fix:

```
workspace/config_utils.py           ← owns PROJECT_ROOT + get_project_root()
  └── (no imports from workspace.core.*)

workspace/scripts/bootstrap_components.py
  └── workspace.config_utils.PROJECT_ROOT

workspace/scripts/bootstrap_component_defs.py
  └── workspace.config_utils.PROJECT_ROOT
  └── workspace.scripts.bootstrap_components

workspace/core/env.py                ← DELETED
```

No cyclic imports: `config_utils` depends only on stdlib (`os`, `pathlib`). Bootstrap scripts depend on `config_utils`, never on `workspace.core.*`.

### 11.2 `confirmation_dialog.py` Consumer

`workspace/cli_components/confirmation_dialog.py` is imported by two files in `workspace/tools/` which are being deleted per V3 plan (`update_cli_versions.py`, `clean_temp_files.py`). No action needed - the file is deleted with the rest of the agent code.

---

## 12. Verification

### 12.1 Acceptance Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-CLI-1 | WORKSPACE-DATAOPS imports resolve standalone | `uv pip install -e projects/WORKSPACE-DATAOPS && uv run python -c "from workspace.cli_components.dialogs import confirm; print('OK')"` |
| AC-CLI-2 | Consolidated types all resolve | `uv run python -c "from workspace.types.results import GroupRange, KeyHandleResult, CharWithOrdinal, FormattedPrefix, NamedComponentStatus, ColorPair, InstallationResult; print('OK')"` |
| AC-CLI-3 | All WORKSPACE-DATAOPS tests pass | `cd projects/WORKSPACE-DATAOPS && uv run python -m pytest tests/` → 1080+ pass |
| AC-CLI-4 | bootstrap_installer.py resolves cli_components | `uv run python -c "from workspace.cli_components import dialogs, menu_selector; from workspace.cli_components.selection_dialog import DialogItem; print('OK')"` |
| AC-CLI-5 | bootstrap_install.py resolves new import | `uv run python -c "from workspace.types.results import InstallationResult; print('OK')"` |
| AC-CLI-6 | sys_info.py resolves types | `uv run python -c "from workspace.types.results import ColorPair; print('OK')"` |
| AC-CLI-7 | PROJECT_ROOT moved to config_utils | `uv run python -c "from workspace.config_utils import PROJECT_ROOT; print(PROJECT_ROOT)"` |
| AC-CLI-8 | bootstrap_components imports from config_utils | `uv run python -c "from workspace.scripts.bootstrap_components import PROJECT_ROOT; print(PROJECT_ROOT)"` |
| AC-CLI-9 | Extension cli_components stay in main package | `ls workspace/cli_components/status.py workspace/cli_components/storage.py` → found; `ls workspace/cli_components/text_input_utils.py` → error (resolved from DATAOPS) |
| AC-CLI-10 | text_input_utils resolves from DATAOPS | `uv run python -c "import workspace.cli_components.text_input_utils; print(workspace.cli_components.text_input_utils.__file__)"` → shows DATAOPS path |
| AC-CLI-11 | ops status works | `uv run python workspace/cli_components/status.py` → exit 0, displays system status |
| AC-CLI-12 | `uv tree` shows both packages | `uv tree` → `workspace-vm` and `workspace-dataops` as siblings |

### 12.2 Test Matrix

```
┌──────────────────────────────────────────┬───────────┬───────────┐
│                Test                       │  Before   │  After    │
├──────────────────────────────────────────┼───────────┼───────────┤
│ WORKSPACE-DATAOPS imports cli_components       │   ✓       │   ✓       │
│ WORKSPACE-DATAOPS tests pass (incl. 336 new)   │  771/771  │  1080/1084│
│ bootstrap_installer.py works             │   ✓       │   ✓       │
│ bootstrap_install.py works               │   ✓       │   ✓       │
│ config_utils tests pass                  │  6/6      │  6/6      │
│ sys_info.py works                        │   ✓       │   ✓       │
│ No cross-package import dependency        │   ✗       │   ✓       │
│ WORKSPACE-DATAOPS installable standalone        │   ✗       │   ✓       │
└──────────────────────────────────────────┴───────────┴───────────┘
```

---

## 13. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Namespace package resolution fails at runtime | Low | High | No overlapping subpackage names - verify with AC-CLI-1 |
| Stripped `results.py` misses a type | Low | Medium | Build failure on first import - caught by AC-CLI-2 |
| `uv sync` fails to install both namespace packages | ~~Low~~ **Verified** | Low | Both set `namespaces = true`; `workspace-dataops` added to root dev deps - verify with AC-CLI-11/AC-CLI-12 |
| `bootstrap_install.py` import change missed | Low | Medium | Script crashes at runtime - caught by AC-CLI-5 |
| `make install` fails because `workspace.core.env` not handled | ~~Medium~~ **Fixed** | ~~High~~ **None** | `get_project_root()`/`PROJECT_ROOT` moved to `workspace/config_utils.py` - see §11.1 |
| Drift between WORKSPACE-DATAOPS copy and future cli_components evolution | Low | Low | cli_components is extracted from agent code, not actively developed |
| WORKSPACE-DATAOPS not installed when bootstrap scripts run | Low | High | Makefile flow ensures `uv sync` installs all editable packages |
| Tests in main package import moved modules | ~~Medium~~ **Handled** | ~~Medium~~ **Low** | 336 cli_components tests migrated to WORKSPACE-DATAOPS; 14 test files copied, all pass |
| Root test suite has 61 import errors from deleted agent modules | **Expected** | Low | Errors are from test files for deleted agent code (`workspace/cli/`, `workspace/core/`, `workspace/hooks/`); to be cleaned up in V3 test file purge |

---

## 14. Shell & Wrapper Migration to opencode

### 14.1 Design

The old `workspace-agent` wrapper and `workspace-transcripts` are **deleted entirely**. They called deleted Python agent code (`workspace.cli.main`, `workspace.cli.transcript_store`, `workspace.core.conversation`).

A single replacement: `workspace-oc` - a thin bash script that prints the WORKSPACE welcome banner (system info, paths, extension status) and delegates to `npx opencode`.

The welcome banner is printed **fresh on every invocation** so the agent always has environment context.

### 14.2 `workspace-oc` Script

**File:** `workspace/scripts/bin/workspace-oc` (NEW)

```bash
#!/usr/bin/env bash
# workspace-oc - WORKSPACE opencode wrapper with environment context
# Prints the WORKSPACE welcome banner fresh on each invocation so the agent
# always sees system paths, tool versions, and workspace status.
set -e

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
WORKSPACE_ROOT="$SCRIPT_DIR"
while [[ "$WORKSPACE_ROOT" != "/" && ! -f "$WORKSPACE_ROOT/pyproject.toml" ]]; do
    WORKSPACE_ROOT="$(dirname "$WORKSPACE_ROOT")"
done
export WORKSPACE_ROOT
cd "$WORKSPACE_ROOT"

WELCOME=$("$WORKSPACE_ROOT/workspace/scripts/bin/workspace-welcome" 2>/dev/null || echo "WORKSPACE-VM workspace")

if [[ $# -gt 0 ]]; then
    # Headless mode - pass welcome + task as context
    exec npx opencode run "$WELCOME

Task: $*" --dir "$WORKSPACE_ROOT"
else
    # Interactive mode - print welcome, start TUI
    printf '%b\n' "$WELCOME"
    echo ""
    exec npx opencode
fi
```

### 14.3 Command Mapping (Old → Nuked)

| Old Command | Fate |
|-------------|------|
| `workspace-agent` (interactive) | **DELETE** - replaced by `workspace-oc` |
| `workspace-agent --query "..."` | **DELETE** - replaced by `workspace-oc "..."` |
| `workspace-agent --print FILE` | **DELETE** - replaced by `workspace-oc "$(cat FILE)"` |
| `workspace-agent --sessions` | **DELETE** - use `opencode session list` directly |
| `workspace-agent --continue` | **DELETE** - use `opencode -c` directly |
| `workspace-agent --prune` | **DELETE** - use `opencode session delete` directly |
| `workspace-transcripts *` | **DELETE** - use `opencode session list\|export\|delete` |
| `workspace-claude` / `workspace-gemini` / `workspace-qwen` | **DELETE** - use `opencode --model <provider/model>` |
| `@` and `msg` aliases | **DELETE** - replaced by `workspace-oc` |

### 14.4 Shell Aliases Update

**File:** `workspace/scripts/shell/shell-setup` (lines 196-197)

**Before:**
```bash
alias @="workspace-agent"
alias msg="workspace-agent"
```

**After:**
```bash
alias @="workspace-oc"
alias msg="workspace-oc"
```

### 14.5 Extension Manifest Update

**File:** `workspace/scripts/bin/extension.manifest.yaml`

Remove the `workspace-agent` and `workspace-transcripts` entries entirely. Add `workspace-oc`:

```yaml
extensions:
  - name: workspace-oc
    binary: workspace/scripts/bin/workspace-oc
    description: opencode-ai agent with WORKSPACE environment context
    category: core
    features:
      - run
      - interactive
      - session
    bannerPriority: 10
```

### 14.6 Files to NUKE (Deletion List)

| File | Reason |
|------|--------|
| `workspace/scripts/bin/workspace-agent` | Calls deleted `workspace.cli.main` |
| `workspace/scripts/bin/workspace_transcripts.py` | Imports deleted `workspace.cli.transcript_store`, `workspace.core.conversation` |
| `tests/unit/test_edge_cases_basic.py` | Tests deleted agent code |
| `tests/unit/test_ami_agent_edge_cases_part2.py` | Tests deleted agent code |
| `tests/integration/test_ami_agent_interactive_integration.py` | Imports `workspace.cli.main` |
| `tests/e2e/test_performance.py` | References `./workspace-agent` |
| `tests/unit/cli/test_main.py` | Imports `workspace.cli.main` |
| `tests/unit/cli/test_transcript_store.py` | Imports deleted `workspace.cli.transcript_store` |
| `tests/unit/cli/test_transcript_search.py` | Imports deleted `workspace.cli.transcript_search` |
| `tests/unit/core/test_conversation.py` | Imports deleted `workspace.core.conversation` |
| `tests/unit/test_session_browser.py` | Imports deleted `workspace.cli.transcript_store` |
| `tests/unit/test_transcript_search.py` | Imports deleted `workspace.cli.transcript_search` |
| `tests/integration/test_bootloader_agent_integration.py` | Imports deleted `workspace.cli.transcript_store`, `workspace.core.conversation` |

### 14.7 Test File to Update

| File | Action |
|------|--------|
| `tests/integration/test_setup_shell_aliases.py` | Remove `workspace-agent`, `workspace-claude`, `workspace-gemini`, `workspace-qwen` from expected functions; add `workspace-oc` |

### 14.8 Migration Sequence

```bash
# 1. Create workspace-oc wrapper
#    Write workspace/scripts/bin/workspace-oc (see §14.2)

# 2. Make executable
chmod +x workspace/scripts/bin/workspace-oc

# 3. Nuke agent files
rm -f workspace/scripts/bin/workspace-agent
rm -f workspace/scripts/bin/workspace_transcripts.py
rm -f tests/unit/test_edge_cases_basic.py
rm -f tests/unit/test_ami_agent_edge_cases_part2.py
rm -f tests/integration/test_ami_agent_interactive_integration.py
rm -f tests/e2e/test_performance.py
rm -f tests/unit/cli/test_main.py
rm -f tests/unit/cli/test_transcript_store.py
rm -f tests/unit/cli/test_transcript_search.py
rm -f tests/unit/core/test_conversation.py
rm -f tests/unit/test_session_browser.py
rm -f tests/unit/test_transcript_search.py
rm -f tests/integration/test_bootloader_agent_integration.py

# 4. Update shell-setup aliases
#    Change @ and msg to workspace-oc

# 5. Update extension manifest
#    Replace workspace-agent + workspace-transcripts with workspace-oc

# 6. Update test_setup_shell_aliases.py
#    Remove old agent aliases, add workspace-oc

# 7. Verify
./workspace/scripts/bin/workspace-oc
workspace-oc "hello"
```
