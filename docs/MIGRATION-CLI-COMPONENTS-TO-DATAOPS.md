# AMI-AGENTS V3 — CLI Components Migration to AMI-DATAOPS

**Document ID:** AMI-MIGRATION-CLI-TO-DATAOPS-v1.0
**Status:** Executed — 2026-06-01
**Date:** 2026-06-01
**Author:** AMI-Agents Engineering

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Dependency Analysis](#2-dependency-analysis)
3. [Migration Strategy](#3-migration-strategy)
4. [Files to Move — CLI Components](#4-files-to-move-cli-components)
5. [Files to Move — Types](#5-files-to-move-types)
6. [AMI-DATAOPS Config Changes](#6-ami-dataops-config-changes)
7. [Import Path Analysis](#7-import-path-analysis)
8. [Import Changes Required](#8-import-changes-required)
9. [Install Order & Dependency Chain](#9-install-order-dependency-chain)
10. [Files to Delete from AMI-AGENTS](#10-files-to-delete-from-ami-agents)
11. [Known Issues Outside Scope](#11-known-issues-outside-scope)
12. [Verification](#12-verification)
13. [Risk Register](#13-risk-register)
14. [Shell & Wrapper Migration to opencode](#14-shell-wrapper-migration-to-opencode)

---

## 1. Problem Statement

The V3 migration plan (`docs/MIGRATION-PLAN.md`, §3.1) schedules the entire `ami/cli_components/` and `ami/types/` directories for deletion from the `ami-agents` package. However, **AMI-DATAOPS** depends on these packages at runtime.

AMI-DATAOPS's `pyproject.toml` declares `ami-agents` as a dev dependency:

```toml
[project.optional-dependencies]
dev = [
    "ami-ci[dev]",
    "ami-agents",
    ...
]

[tool.uv.sources]
ami-agents = { path = "../..", editable = true }
```

Four source files in AMI-DATAOPS import from `ami.cli_components`:

| File | Imports |
|------|---------|
| `ami/dataops/report/operator.py` | `dialogs`, `selection_dialog` |
| `ami/dataops/backup/restore/wizard.py` | `dialogs`, `format_utils`, `menu_selector`, `selector`, `text_input_utils`, `tui` |
| `ami/dataops/backup/restore/revision_display.py` | `format_utils`, `text_input_utils` |
| `ami/dataops/backup/restore/cli.py` | `selector` |

**The V3 plan as-written would break AMI-DATAOPS.** The solution is NOT to keep dead agent code in `ami-agents`, but to MOVE the required CLI/TUI components INTO AMI-DATAOPS itself, making it self-contained.

### 1.1 Secondary Impact

Staying scripts in `ami/scripts/` also import from the modules being deleted:

| Staying Script | Imports From | Will Resolve From |
|----------------|-------------|-------------------|
| `ami/scripts/bootstrap_installer.py` | `ami.cli_components.dialogs`, `ami.cli_components.menu_selector`, `ami.cli_components.selection_dialog`, `ami.types.results.NamedComponentStatus` | AMI-DATAOPS (namespace) |
| `ami/scripts/bootstrap_installer_ui.py` | `ami.cli_components.text_input_utils` | AMI-DATAOPS (namespace) |
| `ami/scripts/bootstrap_install.py` | `ami.types.common.InstallationResult` | **import path must change** |
| `ami/scripts/utils/sys_info.py` | `ami.types.results.ColorPair` | AMI-DATAOPS (namespace) |

---

## 2. Dependency Analysis

### 2.1 Direct Import Chain

```
AMI-DATAOPS
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
  ├── ami.cli_components.keys              → ENTER, ESC, LEFT, RIGHT
  ├── ami.cli_components.selection_dialog
  ├── ami.cli_components.terminal.ansi      → AnsiTerminal
  ├── ami.cli_components.text_input_utils
  └── ami.cli_components.tui

selection_dialog.py
  ├── ami.cli_components.keys              → BACKSPACE, DOWN, ENTER, ESC, UP
  ├── ami.cli_components.selection_dialog_render
  ├── ami.cli_components.text_input_utils
  ├── ami.cli_components.tui
  └── ami.types.results                    → GroupRange, KeyHandleResult

selection_dialog_render.py
  ├── ami.cli_components.text_input_utils
  └── ami.types.results                    → FormattedPrefix

format_utils.py
  └── (standalone — no imports)

text_input_utils.py
  ├── ami.cli_components.terminal.ansi     → AnsiTerminal
  └── ami.types.results                    → CharWithOrdinal

selector.py
  ├── ami.cli_components.format_utils
  ├── ami.cli_components.menu_selector
  └── ami.cli_components.text_input_utils

menu_selector.py
  ├── ami.cli_components.dialogs
  └── ami.cli_components.selection_dialog

tui.py
  └── ami.cli_components.text_input_utils

keys.py
  └── (standalone — no imports)

terminal/ansi.py
  └── (standalone — imports only sys)
```

### 2.3 Types Required for Survival

The V3 plan deletes ALL of `ami/types/`. Two categories of types must survive:

**Category A — TUI types (used by moving cli_components):**

| Type | Used By | Fields |
|------|---------|--------|
| `GroupRange` | `selection_dialog.py` | `header_idx: int, start: int, end: int` |
| `KeyHandleResult` | `selection_dialog.py` | `should_continue: bool, result: object` |
| `CharWithOrdinal` | `text_input_utils.py` | `char: str, ordinal: int` |
| `FormattedPrefix` | `selection_dialog_render.py` | `formatted: str, visible: str` |

**Category B — Bootstrap types (used by staying scripts in `ami/scripts/`):**

| Type | Currently In | Used By | Fields |
|------|-------------|---------|--------|
| `NamedComponentStatus` | `ami.types.results` | `bootstrap_installer.py` | `name, installed, version, path` |
| `ColorPair` | `ami.types.results` | `sys_info.py` | `fg: int, bg: int` |
| `InstallationResult` | `ami.types.common` | `bootstrap_install.py` | `component_name, success, error` |

All 7 types are simple NamedTuples or TypedDicts with **zero transitive dependencies** on agent-specific modules. They can coexist in a single `results.py` file within AMI-DATAOPS.

### 2.4 Namespace Constraint

Python namespace packages cannot merge two modules at the same import path. If both `ami-agents` AND `AMI-DATAOPS` provide `ami.types.results`, only one will be importable (whichever is found first on `sys.path`).

**Therefore ALL surviving types must move to AMI-DATAOPS, and `ami/types/` must be fully deleted from the main package.** There can be no split.

---

## 3. Migration Strategy

### 3.1 Principle

**Move, don't fork.** Copy the minimum transitive closure of files from `ami-agents` into `AMI-DATAOPS`, consolidating all surviving types into a single file. Maintain the same `ami.cli_components.*` and `ami.types.*` namespace paths so most import statements require **zero changes**.

### 3.2 Why Namespace Packages Work

Both `ami-agents` (root `ami/`) and `AMI-DATAOPS` (`projects/AMI-DATAOPS/ami/`) use `setuptools` namespace packages. Python resolves `ami.cli_components.*` and `ami.types.*` by scanning all `sys.path` entries. After the move:

| Namespace | Provided By | After Migration |
|-----------|-------------|-----------------|
| `ami.cli_components` | ~~ami-agents~~ → **AMI-DATAOPS** | AMI-DATAOPS |
| `ami.types` | ~~ami-agents~~ → **AMI-DATAOPS** | AMI-DATAOPS |
| `ami.dataops` | **AMI-DATAOPS** | AMI-DATAOPS |
| `ami.config` | **ami-agents** | ami-agents |
| `ami.scripts` | **ami-agents** | ami-agents |
| `ami.utils` | **ami-agents** | ami-agents |
| `ami.ci` | **ami-agents** | ami-agents |

No overlap → no namespace conflict.

---

## 4. Files to Move — CLI Components

Copy these files from `ami/cli_components/` → `projects/AMI-DATAOPS/ami/cli_components/`:

### 4.1 File Inventory (11 files)

```
ami/cli_components/
├── __init__.py                  (empty — create new)
├── keys.py                      (12 lines — key constants)
├── dialogs.py                   (252 lines — BaseDialog, AlertDialog, ConfirmationDialog, facade functions)
├── selection_dialog.py          (488 lines — SelectionDialog, SelectionDialogConfig, types)
├── selection_dialog_render.py   (177 lines — pure rendering helpers)
├── format_utils.py              (38 lines — format_file_size, KB/MB/GB constants)
├── text_input_utils.py          (365 lines — Colors, read_key_sequence, getchar, cbreak mode)
├── selector.py                  (138 lines — BackupFileInfo, select_backup_interactive, display helpers)
├── menu_selector.py             (95 lines — MenuItem, MenuSelector, simple_menu_select, multi_menu_select)
├── tui.py                       (222 lines — TUI.draw_box, BoxStyle, strip_ansi, visible_len, wrap_text)
└── terminal/
    └── ansi.py                  (104 lines — AnsiTerminal with all ANSI escape codes)
```

**Total: 11 files, ~1,891 lines**

### 4.2 Files NOT Moved

The following `ami/cli_components/` files are NOT moved to AMI-DATAOPS. They stay in the main package because they are actively used by the `ops` extension (`ami/scripts/bin/ops` dispatches to `status.py` and `storage.py` directly).

**Kept — active extension entry points and their dependencies:**

| File | Status |
|------|--------|
| `status.py` | KEPT — entry point for `ops status` (imported by ops via `ami/scripts/bin/ops:75`) |
| `storage.py` | KEPT — entry point for `ops storage` (imported by ops via `ami/scripts/bin/ops:78`) |
| `legend.py` | KEPT — imported by status.py for legend display |
| `status_containers.py` | KEPT — imported by status.py for container ops |
| `status_systemd.py` | KEPT — imported by status.py for systemd service display |
| `status_utils.py` | KEPT — imported by status*.py for shared utilities |
| `text_input_utils.py` | DELETED — duplicated in AMI-DATAOPS; imported from DATAOPS via namespace packages |

**Files that were agent-only and are deleted:**

| File | Why Not Needed |
|------|----------------|
| `confirmation_dialog.py` | `ConfirmationDialog` lives in `dialogs.py` itself; external consumers (`ami/tools/`) were deleted |
| `cursor_manager.py` | Agent TUI only |
| `editor_display.py` | Agent text editor |
| `editor_saving.py` | Agent text editor |
| `session_browser.py` | Agent session browser |
| `session_detail.py` | Agent session detail |
| `stream_renderer.py` | Agent stream renderer |
| `text_editor.py` | Agent text editor |
| `text_input_cli.py` | Agent CLI text input |

---

## 5. Files to Move — Types

### 5.1 Strategy

The full `ami.types.results` (181 lines, 23 types) drags in `ami.types.api` → `ami.types.common` transitively. Most of these types are agent-specific.

**Solution:** Create a consolidated `results.py` in AMI-DATAOPS containing ONLY the 7 types that must survive (4 TUI + 3 bootstrap). Drop all agent-specific types and their imports entirely.

### 5.2 Files to Create

```
projects/AMI-DATAOPS/ami/types/
├── __init__.py                  (empty — create new)
└── results.py                   (consolidated — see below)
```

### 5.3 Consolidated `results.py` Contents

```python
"""Result types shared between AMI-DATAOPS and AMI-AGENTS scripts.

Consolidated from ami-agents/ami/types/results.py and
ami-agents/ami/types/common.py.  Contains only the types that survive
the V3 agent-code deletion.

TUI types  — used by ami.cli_components (moved to AMI-DATAOPS)
Bootstrap types — used by ami.scripts.* (staying in AMI-AGENTS)

See AMI-AGENTS docs/MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md
"""

from typing import NamedTuple, TypedDict


# ── TUI types (used by ami.cli_components) ──────────────────────

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


# ── Bootstrap types (used by ami/scripts/*.py) ──────────────────

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

### 5.4 Types — Disposition

The `ami/types/` directory stays in the main package. The surviving cli_components files (status, storage, legend, status_containers, status_systemd, status_utils — see §4.2) depend on types that the slim consolidated DATAOPS `results.py` does not provide:

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

**Therefore `ami/types/` stays in its entirety.** The DATAOPS consolidated `results.py` is a minimal subset useful for DATAOPS's namespace package independence; it is shadowed at runtime by the main package's full types/ (which appears first on PYTHONPATH via `$AMI_ROOT:${PROJECT_PATHS}`) but serves as a fallback reference.

---

## 6. AMI-DATAOPS Config Changes

### 6.1 `pyproject.toml` — Package Discovery

**Before:**
```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["ami.dataops*"]
namespaces = true
```

**After:**
```toml
[tool.setuptools.packages.find]
where = ["."]
include = ["ami.dataops*", "ami.cli_components*", "ami.types*"]
namespaces = true
```

### 6.2 `pyproject.toml` — Dependencies

**Before:**
```toml
[project.optional-dependencies]
dev = [
    "ami-ci[dev]",
    "ami-agents",
    "respx==0.23.1",
]

[tool.uv.sources]
ami-ci = { path = "../AMI-CI", editable = true }
ami-agents = { path = "../..", editable = true }
```

**After:**
```toml
[project.optional-dependencies]
dev = [
    "ami-ci[dev]",
    "respx==0.23.1",
]

[tool.uv.sources]
ami-ci = { path = "../AMI-CI", editable = true }
```

Remove `ami-agents` from AMI-DATAOPS's dependency tree. It is no longer required at build, test, or runtime. Both packages still coexist in the `ami` namespace but have **no import dependency** on each other.

### 6.3 Root `pyproject.toml` — Add AMI-DATAOPS as Dev Dependency

The root `ami-agents` package must install AMI-DATAOPS so that staying scripts (`bootstrap_installer.py`, etc.) can resolve `ami.cli_components.*` and `ami.types.*` through namespace packages.

**Before:**
```toml
[project.optional-dependencies]
dev = [
    "ami-ci[dev]",
]

[tool.uv.sources]
ami-ci = { path = "projects/AMI-CI", editable = true }
```

**After:**
```toml
[project.optional-dependencies]
dev = [
    "ami-ci[dev]",
    "ami-dataops",
]

[tool.uv.sources]
ami-ci = { path = "projects/AMI-CI", editable = true }
ami-dataops = { path = "projects/AMI-DATAOPS", editable = true }
```

---

## 7. Import Path Analysis

### 7.1 Zero-Changes Verification

Every import in AMI-DATAOPS source files uses `ami.cli_components.*` or `ami.types.*` paths. Since the moved files live at the same namespace paths within `projects/AMI-DATAOPS/ami/`, **no import statements need to change in AMI-DATAOPS**.

Verified imports:

| Source File | Import | Status |
|-------------|--------|--------|
| `operator.py:25` | `from ami.cli_components import dialogs` | ✅ |
| `operator.py:26` | `from ami.cli_components.selection_dialog import ...` | ✅ |
| `revision_display.py:9` | `from ami.cli_components.format_utils import format_file_size` | ✅ |
| `revision_display.py:10` | `from ami.cli_components.text_input_utils import Colors` | ✅ |
| `cli.py:14` | `from ami.cli_components.selector import ...` | ✅ |
| `wizard.py:13` | `from ami.cli_components.dialogs import confirm` | ✅ |
| `wizard.py:14` | `from ami.cli_components.format_utils import format_file_size` | ✅ |
| `wizard.py:15` | `from ami.cli_components.menu_selector import ...` | ✅ |
| `wizard.py:16` | `from ami.cli_components.selector import ...` | ✅ |
| `wizard.py:20` | `from ami.cli_components.text_input_utils import Colors` | ✅ |
| `wizard.py:21` | `from ami.cli_components.tui import TUI, BoxStyle` | ✅ |

### 7.2 Internal Cross-References Within Transitive Closure

The moved `.py` files reference each other using the same `ami.cli_components.*` paths. These also resolve via namespace package lookup:

| File | Imports | Resolves To |
|------|---------|-------------|
| `dialogs.py` | `ami.cli_components.keys` | `projects/AMI-DATAOPS/ami/cli_components/keys.py` |
| `dialogs.py` | `ami.cli_components.terminal.ansi` | `projects/AMI-DATAOPS/ami/cli_components/terminal/ansi.py` |
| `selection_dialog.py` | `ami.cli_components.tui` | `projects/AMI-DATAOPS/ami/cli_components/tui.py` |
| `selection_dialog.py` | `ami.types.results` | `projects/AMI-DATAOPS/ami/types/results.py` |
| `text_input_utils.py` | `ami.types.results` | `projects/AMI-DATAOPS/ami/types/results.py` |
| etc. | | All resolve within AMI-DATAOPS |

---

## 8. Import Changes Required

### 8.1 One Import Must Change

The staying script `ami/scripts/bootstrap_install.py` imports `InstallationResult` from a file that is being deleted:

**Before (breaks):**
```python
from ami.types.common import InstallationResult
```

**After (fixed):**
```python
from ami.types.results import InstallationResult
```

This is the **only import change required** anywhere in the codebase.

### 8.2 All Other Staying Script Imports (unchanged)

| Script | Import | Resolves From |
|--------|--------|---------------|
| `bootstrap_installer.py:39` | `from ami.cli_components import dialogs as _dialogs` | AMI-DATAOPS ✅ |
| `bootstrap_installer.py:40` | `from ami.cli_components import menu_selector as _menu` | AMI-DATAOPS ✅ |
| `bootstrap_installer.py:41` | `from ami.cli_components.selection_dialog import DialogItem` | AMI-DATAOPS ✅ |
| `bootstrap_installer.py:55` | `from ami.types.results import NamedComponentStatus` | AMI-DATAOPS ✅ |
| `bootstrap_installer_ui.py:12` | `from ami.cli_components.text_input_utils import Colors` | AMI-DATAOPS ✅ |
| `sys_info.py:8` | `from ami.types.results import ColorPair` | AMI-DATAOPS ✅ |

---

## 9. Install Order & Dependency Chain

### 9.1 Current Dependency Graph

```
AMI-AGENTS (root pyproject.toml)
  ├── include: ["ami.*"]         # ami/cli, ami/core, ami/cli_components, ami/types, ...
  └── dev-dep: AMI-CI            # via [tool.uv.sources]

AMI-DATAOPS (projects/AMI-DATAOPS/pyproject.toml)
  ├── include: ["ami.dataops*"]  # ami/dataops only
  ├── dev-dep: AMI-AGENTS        # for ami.cli_components at runtime
  └── dev-dep: AMI-CI
```

### 9.2 Post-Migration Dependency Graph

```
AMI-AGENTS (root pyproject.toml)
  ├── include: ["ami.*"]         # ami/config, ami/scripts, ami/utils, ami/ci
  └── dev-dep: AMI-CI            # unchanged

AMI-DATAOPS (projects/AMI-DATAOPS/pyproject.toml)
  ├── include: ["ami.dataops*", "ami.cli_components*", "ami.types*"]
  │                              # self-contained — no runtime dep on ami-agents
  └── dev-dep: AMI-CI            # unchanged
```

### 9.3 Makefile Install Flow

Current `sync-package` target:

```makefile
sync-package: bootstrap-core ensure-ci ensure-dataops
    .boot-linux/bin/uv sync --extra dev
```

- `ensure-ci` clones AMI-CI from moon config
- `ensure-dataops` clones AMI-DATAOPS from moon config
- `uv sync` processes all `pyproject.toml` files and resolves deps via `[tool.uv.sources]`

**No changes needed** to the Makefile. The install order is:

1. `bootstrap-core` — uv, python, git-xet
2. `ensure-ci` — clone AMI-CI
3. `ensure-dataops` — clone AMI-DATAOPS
4. `uv sync` — installs all editable packages in dependency order

After migration, `uv sync` will install `ami-dataops` as an editable package (providing `ami.cli_components` and `ami.types`) and `ami-agents` as an editable package (providing remaining `ami.*` namespaces). Both appear as siblings in `uv tree`.

> **Important:** After migration, verify with `uv tree` that both `ami-agents` and `ami-dataops` appear. If AMI-DATAOPS is not installed, scripts like `bootstrap_installer.py` will fail to resolve `ami.cli_components.*`.

### 9.4 First-Time Migration Sequence

```bash
# ── Phase 1: Copy files into AMI-DATAOPS ──

# 1a. CLI components (11 files)
mkdir -p projects/AMI-DATAOPS/ami/cli_components/terminal/
touch projects/AMI-DATAOPS/ami/cli_components/__init__.py

cp ami/cli_components/keys.py                         projects/AMI-DATAOPS/ami/cli_components/
cp ami/cli_components/dialogs.py                      projects/AMI-DATAOPS/ami/cli_components/
cp ami/cli_components/selection_dialog.py             projects/AMI-DATAOPS/ami/cli_components/
cp ami/cli_components/selection_dialog_render.py      projects/AMI-DATAOPS/ami/cli_components/
cp ami/cli_components/format_utils.py                 projects/AMI-DATAOPS/ami/cli_components/
cp ami/cli_components/text_input_utils.py             projects/AMI-DATAOPS/ami/cli_components/
cp ami/cli_components/selector.py                     projects/AMI-DATAOPS/ami/cli_components/
cp ami/cli_components/menu_selector.py                projects/AMI-DATAOPS/ami/cli_components/
cp ami/cli_components/tui.py                          projects/AMI-DATAOPS/ami/cli_components/
cp ami/cli_components/terminal/ansi.py                projects/AMI-DATAOPS/ami/cli_components/terminal/

# 1b. Types (consolidated results.py)
mkdir -p projects/AMI-DATAOPS/ami/types/
touch projects/AMI-DATAOPS/ami/types/__init__.py
# Write consolidated results.py (see §5.3)

# 1c. Tests for moved modules (14 test files)
mkdir -p projects/AMI-DATAOPS/tests/unit/cli_components/terminal/
touch projects/AMI-DATAOPS/tests/unit/cli_components/__init__.py
touch projects/AMI-DATAOPS/tests/unit/cli_components/terminal/__init__.py

cp tests/unit/test_format_utils.py                    projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/test_tui.py                             projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/test_selector.py                        projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/test_menu_selector.py                   projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/test_text_input_utils.py                projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_dialogs_structure.py      projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_dialogs_behavior.py       projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_selection_dialog.py       projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_selection_dialog_skippable.py  projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_selection_dialog_cascade.py   projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_selection_dialog_rendering.py projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_text_input_utils_keys.py      projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/test_text_input_utils_comprehensive.py projects/AMI-DATAOPS/tests/unit/cli_components/
cp tests/unit/cli_components/terminal/test_ansi.py      projects/AMI-DATAOPS/tests/unit/cli_components/terminal/

# ── Phase 2: Update imports ──

# 2a. Fix bootstrap_install.py import path
#   Change: from ami.types.common import InstallationResult
#   To:     from ami.types.results import InstallationResult

# ── Phase 3: Update pyproject.toml files ──

# 3a. Update projects/AMI-DATAOPS/pyproject.toml:
#   - Change include to ["ami.dataops*", "ami.cli_components*", "ami.types*"]
#   - Add exclude = ["res*", "config*", "deploy*", "docs*", "tests*", "*.egg-info*"]
#   - Remove ami-agents from [tool.uv.sources]
#   - Remove ami-agents from [project.optional-dependencies]

# 3b. Update root pyproject.toml:
#   - Add ami-dataops to [project.optional-dependencies] dev
#   - Add ami-dataops to [tool.uv.sources]
#   (Ensures ami-dataops is installed alongside ami-agents via namespace packages)

# ── Phase 4: Fix PROJECT_ROOT move ──

# 4a. Rewrite ami/config_utils.py (inline get_project_root + PROJECT_ROOT from
#     ami/core/env.py, remove the import from ami.core.env)
#     See §11.1 Step 1 for the full file content.

# 4b. Fix ami/scripts/bootstrap_components.py import:
#   Change: from ami.core.env import PROJECT_ROOT
#   To:     from ami.config_utils import PROJECT_ROOT

# 4c. Fix ami/scripts/bootstrap_component_defs.py import:
#   Change: from ami.core.env import PROJECT_ROOT
#   To:     from ami.config_utils import PROJECT_ROOT

# ── Phase 5: Verify ──

# 5a. AMI-DATAOPS
cd projects/AMI-DATAOPS
python -c "from ami.cli_components.dialogs import confirm; print('OK')"
python -c "from ami.cli_components.tui import TUI; print('OK')"
python -c "from ami.types.results import GroupRange; print('OK')"
python -c "from ami.types.results import InstallationResult; print('OK')"
python -m pytest tests/

# 5b. PROJECT_ROOT fix
cd /
python -c "from ami.config_utils import get_project_root, PROJECT_ROOT; print(PROJECT_ROOT)"
python -c "from ami.scripts.bootstrap_components import PROJECT_ROOT; print('OK')"
python -c "from ami.scripts.bootstrap_component_defs import ALL_COMPONENTS; print(len(ALL_COMPONENTS))"
python -c "from ami.config_utils import get_config_path; print(get_config_path('ruff.toml'))"

# ── Phase 6: Delete from main package ──

rm -f ami/cli_components/text_input_utils.py   # duplicated — resolve from DATAOPS
rm -rf ami/cli/
rm -rf ami/core/
rm -rf ami/tools/
rm -rf ami/hooks/
rm -f ami/utils/process.py          # orphaned — imports deleted types
rm -f ami/scripts/bootstrap/bootstrap_agents.sh
rm -f scripts/package.json
rm -f scripts/package.json.backup
rm -f scripts/setup/node.sh         # (already deleted)

# DO NOT delete ami/cli_components/ — status.py, storage.py, legend.py, etc.
# are active extension entry points (ops status, ops storage).
# DO NOT delete ami/types/ — surviving extension chain needs full types
# (LegendRender, ContainerStatusDisplay, etc.). See §4.2 and §5.4.

# ── Phase 7: Rebuild and verify ──

uv sync --extra dev

# Verify imports resolve from AMI-DATAOPS
python -c "import ami.cli_components.keys; print(ami.cli_components.keys.__file__)"
# Should show: ...projects/AMI-DATAOPS/ami/cli_components/keys.py

python -c "from ami.types.results import GroupRange, KeyHandleResult, NamedComponentStatus, InstallationResult; print('ok')"

# Run AMI-DATAOPS full test suite
python -m pytest projects/AMI-DATAOPS/tests/ -q

# Run root test suite (expect errors for deleted agent test files)
python -m pytest tests/ -q
```

---

## 10. Files to Delete from AMI-AGENTS

### 10.1 CLI Components (moved to AMI-DATAOPS)

These 12 files are deleted from `ami/cli_components/` after copying to AMI-DATAOPS:

```
ami/cli_components/__init__.py        ✓ DELETED
ami/cli_components/keys.py            ✓ DELETED
ami/cli_components/dialogs.py         ✓ DELETED
ami/cli_components/selection_dialog.py         ✓ DELETED
ami/cli_components/selection_dialog_render.py  ✓ DELETED
ami/cli_components/format_utils.py             ✓ DELETED
ami/cli_components/text_input_utils.py         ✓ DELETED
ami/cli_components/selector.py                 ✓ DELETED
ami/cli_components/menu_selector.py            ✓ DELETED
ami/cli_components/tui.py                      ✓ DELETED
ami/cli_components/terminal/ansi.py            ✓ DELETED
ami/cli_components/terminal/__init__.py        ✓ DELETED
```

**NOT deleted:** status.py, storage.py, legend.py, status_containers.py, status_systemd.py, status_utils.py — these are active extension entry points (see §4.2).

### 10.2 Types (NOT deleted — kept in main package)

`ami/types/` stays in the main package. See §5.4 for the dependency chain. The surviving status/storage/legend extension chain requires types not present in the DATAOPS consolidated `results.py`.

### 10.3 Remaining Agent Code (per MIGRATION-PLAN.md)

```
ami/cli/               (entire directory — 25 files — DELETED ✓)
ami/core/              (entire directory — 14 files + policies/ — DELETED ✓)
ami/tools/             (entire directory — 3 files — DELETED ✓)
ami/hooks/             (agent-specific hooks — DELETED ✓)
ami/utils/process.py   (orphaned — imports deleted ami.types)
scripts/package.json
scripts/package.json.backup
scripts/setup/node.sh
ami/scripts/bootstrap/bootstrap_agents.sh
```

**NOT deleted from `ami/cli_components/`:** status.py, storage.py, legend.py, status_containers.py, status_systemd.py, status_utils.py — kept for `ops status` and `ops storage` extensions (see §4.2).

**NOT deleted from `ami/types/`:** entire directory kept — surviving extension chain requires types not in DATAOPS consolidated results.py (see §5.4).

---

## 11. Known Issues Outside Scope

The following issues are NOT addressed by this migration document because they involve deletions outside `ami/cli_components/` and `ami/types/`. They are flagged here for the main V3 plan.

### 11.1 `ami.core.env` Dependency — Fix Included

**Problem:** `ami/core/env.py` is scheduled for deletion, but three staying files import from it:

| File | Import | Breaks When |
|------|--------|-------------|
| `ami/config_utils.py:9` | `from ami.core.env import get_project_root` | `ami/core/` deleted |
| `ami/scripts/bootstrap_component_defs.py:24` | `from ami.core.env import PROJECT_ROOT` | `ami/core/` deleted |
| `ami/scripts/bootstrap_components.py:10` | `from ami.core.env import PROJECT_ROOT` | `ami/core/` deleted |

The module provides `get_project_root()` (finds project root by walking up for `pyproject.toml`) and the module-level `PROJECT_ROOT` constant.

**Fix — move into `ami/config_utils.py`:**

#### Step 1: Move `get_project_root()` and `PROJECT_ROOT` into `ami/config_utils.py`

**Before** (`ami/config_utils.py`, 35 lines):
```python
"""Configuration utilities for ami-agents package.

This module provides utilities for accessing shared configuration files.
"""

from pathlib import Path

from ami.core.env import get_project_root


def get_config_path(config_name: str) -> Path:
    return get_project_root() / "res" / "config" / config_name


def get_vendor_config_path(config_name: str) -> Path:
    return get_project_root() / "res" / "config" / vendor / config_name
```

**After** (`ami/config_utils.py`, ~85 lines):
```python
"""Configuration utilities for ami-agents package.

This module provides utilities for accessing shared configuration files
and project root discovery — moved here from ami/core/env.py during the
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
    Falls back to AMI_PROJECT_ROOT environment variable if set.
    """
    cached = _ProjectRootCache.get()
    if cached is not None:
        return cached

    env_root = os.environ.get("AMI_PROJECT_ROOT")
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

#### Step 2: Update `ami/config_utils.py` import line

Remove the `from ami.core.env import get_project_root` import (replaced by inline definition above).

#### Step 3: Update `ami/scripts/bootstrap_components.py`

**Before:**
```python
from ami.core.env import PROJECT_ROOT
```

**After:**
```python
from ami.config_utils import PROJECT_ROOT
```

#### Step 4: Update `ami/scripts/bootstrap_component_defs.py`

**Before:**
```python
from ami.core.env import PROJECT_ROOT
```

**After:**
```python
from ami.config_utils import PROJECT_ROOT
```

#### Step 5: Delete `ami/core/env.py`

With all consumers migrated to `ami/config_utils.py`, `ami/core/env.py` is deleted as part of the `ami/core/` directory removal.

#### Step 6: Verify

```bash
python -c "from ami.config_utils import get_project_root, PROJECT_ROOT; print(PROJECT_ROOT)"
python -c "from ami.scripts.bootstrap_components import PROJECT_ROOT; print(PROJECT_ROOT)"
python -c "from ami.scripts.bootstrap_component_defs import ALL_COMPONENTS; print(len(ALL_COMPONENTS))"
python -c "from ami.config_utils import get_config_path; print(get_config_path('ruff.toml'))"
```

#### Dependency chain after fix:

```
ami/config_utils.py           ← owns PROJECT_ROOT + get_project_root()
  └── (no imports from ami.core.*)

ami/scripts/bootstrap_components.py
  └── ami.config_utils.PROJECT_ROOT

ami/scripts/bootstrap_component_defs.py
  └── ami.config_utils.PROJECT_ROOT
  └── ami.scripts.bootstrap_components

ami/core/env.py                ← DELETED
```

No cyclic imports: `config_utils` depends only on stdlib (`os`, `pathlib`). Bootstrap scripts depend on `config_utils`, never on `ami.core.*`.

### 11.2 `confirmation_dialog.py` Consumer

`ami/cli_components/confirmation_dialog.py` is imported by two files in `ami/tools/` which are being deleted per V3 plan (`update_cli_versions.py`, `clean_temp_files.py`). No action needed — the file is deleted with the rest of the agent code.

---

## 12. Verification

### 12.1 Acceptance Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-CLI-1 | AMI-DATAOPS imports resolve standalone | `pip install -e projects/AMI-DATAOPS && python -c "from ami.cli_components.dialogs import confirm; print('OK')"` |
| AC-CLI-2 | Consolidated types all resolve | `python -c "from ami.types.results import GroupRange, KeyHandleResult, CharWithOrdinal, FormattedPrefix, NamedComponentStatus, ColorPair, InstallationResult; print('OK')"` |
| AC-CLI-3 | All AMI-DATAOPS tests pass | `cd projects/AMI-DATAOPS && python -m pytest tests/` → 1080+ pass |
| AC-CLI-4 | bootstrap_installer.py resolves cli_components | `python -c "from ami.cli_components import dialogs, menu_selector; from ami.cli_components.selection_dialog import DialogItem; print('OK')"` |
| AC-CLI-5 | bootstrap_install.py resolves new import | `python -c "from ami.types.results import InstallationResult; print('OK')"` |
| AC-CLI-6 | sys_info.py resolves types | `python -c "from ami.types.results import ColorPair; print('OK')"` |
| AC-CLI-7 | PROJECT_ROOT moved to config_utils | `python -c "from ami.config_utils import PROJECT_ROOT; print(PROJECT_ROOT)"` |
| AC-CLI-8 | bootstrap_components imports from config_utils | `python -c "from ami.scripts.bootstrap_components import PROJECT_ROOT; print(PROJECT_ROOT)"` |
| AC-CLI-9 | Extension cli_components stay in main package | `ls ami/cli_components/status.py ami/cli_components/storage.py` → found; `ls ami/cli_components/text_input_utils.py` → error (resolved from DATAOPS) |
| AC-CLI-10 | text_input_utils resolves from DATAOPS | `python -c "import ami.cli_components.text_input_utils; print(ami.cli_components.text_input_utils.__file__)"` → shows DATAOPS path |
| AC-CLI-11 | ops status works | `python ami/cli_components/status.py` → exit 0, displays system status |
| AC-CLI-12 | `uv tree` shows both packages | `uv tree` → `ami-agents` and `ami-dataops` as siblings |

### 12.2 Test Matrix

```
┌──────────────────────────────────────────┬───────────┬───────────┐
│                Test                       │  Before   │  After    │
├──────────────────────────────────────────┼───────────┼───────────┤
│ AMI-DATAOPS imports cli_components       │   ✓       │   ✓       │
│ AMI-DATAOPS tests pass (incl. 336 new)   │  771/771  │  1080/1084│
│ bootstrap_installer.py works             │   ✓       │   ✓       │
│ bootstrap_install.py works               │   ✓       │   ✓       │
│ config_utils tests pass                  │  6/6      │  6/6      │
│ sys_info.py works                        │   ✓       │   ✓       │
│ No cross-package import dependency        │   ✗       │   ✓       │
│ AMI-DATAOPS installable standalone        │   ✗       │   ✓       │
└──────────────────────────────────────────┴───────────┴───────────┘
```

---

## 13. Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Namespace package resolution fails at runtime | Low | High | No overlapping subpackage names — verify with AC-CLI-1 |
| Stripped `results.py` misses a type | Low | Medium | Build failure on first import — caught by AC-CLI-2 |
| `uv sync` fails to install both namespace packages | ~~Low~~ **Verified** | Low | Both set `namespaces = true`; `ami-dataops` added to root dev deps — verify with AC-CLI-11/AC-CLI-12 |
| `bootstrap_install.py` import change missed | Low | Medium | Script crashes at runtime — caught by AC-CLI-5 |
| `make install` fails because `ami.core.env` not handled | ~~Medium~~ **Fixed** | ~~High~~ **None** | `get_project_root()`/`PROJECT_ROOT` moved to `ami/config_utils.py` — see §11.1 |
| Drift between AMI-DATAOPS copy and future cli_components evolution | Low | Low | cli_components is extracted from agent code, not actively developed |
| AMI-DATAOPS not installed when bootstrap scripts run | Low | High | Makefile flow ensures `uv sync` installs all editable packages |
| Tests in main package import moved modules | ~~Medium~~ **Handled** | ~~Medium~~ **Low** | 336 cli_components tests migrated to AMI-DATAOPS; 14 test files copied, all pass |
| Root test suite has 61 import errors from deleted agent modules | **Expected** | Low | Errors are from test files for deleted agent code (`ami/cli/`, `ami/core/`, `ami/hooks/`); to be cleaned up in V3 test file purge |

---

## 14. Shell & Wrapper Migration to opencode

### 14.1 Design

The old `ami-agent` wrapper and `ami-transcripts` are **deleted entirely**. They called deleted Python agent code (`ami.cli.main`, `ami.cli.transcript_store`, `ami.core.conversation`).

A single replacement: `ami-oc` — a thin bash script that prints the AMI welcome banner (system info, paths, extension status) and delegates to `npx opencode`.

The welcome banner is printed **fresh on every invocation** so the agent always has environment context.

### 14.2 `ami-oc` Script

**File:** `ami/scripts/bin/ami-oc` (NEW)

```bash
#!/usr/bin/env bash
# ami-oc — AMI opencode wrapper with environment context
# Prints the AMI welcome banner fresh on each invocation so the agent
# always sees system paths, tool versions, and workspace status.
set -e

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
AMI_ROOT="$SCRIPT_DIR"
while [[ "$AMI_ROOT" != "/" && ! -f "$AMI_ROOT/pyproject.toml" ]]; do
    AMI_ROOT="$(dirname "$AMI_ROOT")"
done
export AMI_ROOT
cd "$AMI_ROOT"

WELCOME=$("$AMI_ROOT/ami/scripts/bin/ami-welcome" 2>/dev/null || echo "AMI-AGENTS workspace")

if [[ $# -gt 0 ]]; then
    # Headless mode — pass welcome + task as context
    exec npx opencode run "$WELCOME

Task: $*" --dir "$AMI_ROOT"
else
    # Interactive mode — print welcome, start TUI
    printf '%b\n' "$WELCOME"
    echo ""
    exec npx opencode
fi
```

### 14.3 Command Mapping (Old → Nuked)

| Old Command | Fate |
|-------------|------|
| `ami-agent` (interactive) | **DELETE** — replaced by `ami-oc` |
| `ami-agent --query "..."` | **DELETE** — replaced by `ami-oc "..."` |
| `ami-agent --print FILE` | **DELETE** — replaced by `ami-oc "$(cat FILE)"` |
| `ami-agent --sessions` | **DELETE** — use `opencode session list` directly |
| `ami-agent --continue` | **DELETE** — use `opencode -c` directly |
| `ami-agent --prune` | **DELETE** — use `opencode session delete` directly |
| `ami-transcripts *` | **DELETE** — use `opencode session list\|export\|delete` |
| `ami-claude` / `ami-gemini` / `ami-qwen` | **DELETE** — use `opencode --model <provider/model>` |
| `@` and `msg` aliases | **DELETE** — replaced by `ami-oc` |

### 14.4 Shell Aliases Update

**File:** `ami/scripts/shell/shell-setup` (lines 196-197)

**Before:**
```bash
alias @="ami-agent"
alias msg="ami-agent"
```

**After:**
```bash
alias @="ami-oc"
alias msg="ami-oc"
```

### 14.5 Extension Manifest Update

**File:** `ami/scripts/bin/extension.manifest.yaml`

Remove the `ami-agent` and `ami-transcripts` entries entirely. Add `ami-oc`:

```yaml
extensions:
  - name: ami-oc
    binary: ami/scripts/bin/ami-oc
    description: opencode-ai agent with AMI environment context
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
| `ami/scripts/bin/ami-agent` | Calls deleted `ami.cli.main` |
| `ami/scripts/bin/ami_transcripts.py` | Imports deleted `ami.cli.transcript_store`, `ami.core.conversation` |
| `tests/unit/test_edge_cases_basic.py` | Tests deleted agent code |
| `tests/unit/test_ami_agent_edge_cases_part2.py` | Tests deleted agent code |
| `tests/integration/test_ami_agent_interactive_integration.py` | Imports `ami.cli.main` |
| `tests/e2e/test_performance.py` | References `./ami-agent` |
| `tests/unit/cli/test_main.py` | Imports `ami.cli.main` |
| `tests/unit/cli/test_transcript_store.py` | Imports deleted `ami.cli.transcript_store` |
| `tests/unit/cli/test_transcript_search.py` | Imports deleted `ami.cli.transcript_search` |
| `tests/unit/core/test_conversation.py` | Imports deleted `ami.core.conversation` |
| `tests/unit/test_session_browser.py` | Imports deleted `ami.cli.transcript_store` |
| `tests/unit/test_transcript_search.py` | Imports deleted `ami.cli.transcript_search` |
| `tests/integration/test_bootloader_agent_integration.py` | Imports deleted `ami.cli.transcript_store`, `ami.core.conversation` |

### 14.7 Test File to Update

| File | Action |
|------|--------|
| `tests/integration/test_setup_shell_aliases.py` | Remove `ami-agent`, `ami-claude`, `ami-gemini`, `ami-qwen` from expected functions; add `ami-oc` |

### 14.8 Migration Sequence

```bash
# 1. Create ami-oc wrapper
#    Write ami/scripts/bin/ami-oc (see §14.2)

# 2. Make executable
chmod +x ami/scripts/bin/ami-oc

# 3. Nuke agent files
rm -f ami/scripts/bin/ami-agent
rm -f ami/scripts/bin/ami_transcripts.py
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
#    Change @ and msg to ami-oc

# 5. Update extension manifest
#    Replace ami-agent + ami-transcripts with ami-oc

# 6. Update test_setup_shell_aliases.py
#    Remove old agent aliases, add ami-oc

# 7. Verify
./ami/scripts/bin/ami-oc
ami-oc "hello"
```
