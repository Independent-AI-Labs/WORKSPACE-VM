# Boot Layout - Enterprise Requirements Specification

**Document ID:** AMI-REQ-BOOTLAYOUT-v1.0
**Status:** Draft
**Date:** 2026-07-10
**Classification:** Internal - Enterprise
**Specification:** [SPEC-BOOT-LAYOUT](../specifications/SPEC-BOOT-LAYOUT.md)
**Authors:** AMI-Agents Engineering
**References:**
- [config/boot_layout.yaml](../../config/boot_layout.yaml) (current boot-path declaration)
- [SPEC-BOOT-LAYOUT](../specifications/SPEC-BOOT-LAYOUT.md) (Technical Specification)
- [REQ-AGENT-POLICY](REQ-AGENT-POLICY.md) (Agent Policy Engine, references boot-path resolver)
- [AGENTS.md](../../AGENTS.md) (Universal Agent Rules: shell-first, no-root, 512-line limit)
- POSIX.1-2017 (Shell Command Language)
- GNU Core Utilities (`realpath`, `readlink`, `dirname`, `basename`)
- BSD/macOS System Calls (`uname(2)`, `readlink(2)`)

---

## 1. Scope

This document specifies the functional, non-functional, and architectural requirements for the **Boot Layout**, the platform abstraction layer that resolves the workspace-local toolchain directory (`boot directory`) based on the host operating system. The boot directory (currently hardcoded as `.boot-linux`) holds bootstrapped binaries, virtual environments, and toolchain installations that are private to the workspace and never committed to git.

The Boot Layout feature provides:

- **Platform-aware boot directory resolution**, `.boot-linux` on Linux, `.boot-macos` on macOS (Darwin), with a stable API for all consumers
- **OS-aware hook generation**, `generate-hooks` emits correct PATH entries for the host platform
- **Portable CI tooling**, replacement of GNU-specific constructs (`realpath --relative-to`, `readlink -f`) with POSIX-portable equivalents
- **Backward-compatible workspace detection**, `walk-projects` and compliance checks accept either platform's boot directory as a workspace root marker
- **Unified bootstrap target directory**, all ~25 bootstrap scripts write to the platform-correct directory by default

**Out of scope:**

- The content of the boot directory (which tools are installed, their versions, or their configuration)
- The bootstrap scripts' download logic (platform detection for binary URLs is already implemented)
- The `.venv/` Python project virtual environment (separate from `python-env/` in the boot directory)
- systemd service templates (Linux-only, not applicable to macOS)
- The git-guard binary compilation and installation (covered by CI project contracts)

---

## 2. Terminology

| Term | Definition |
|------|------------|
| **Boot Directory** | The workspace-local directory containing bootstrapped toolchain binaries, virtual environments, and tool installations. Named `.boot-linux` on Linux, `.boot-macos` on macOS. Never committed to git. |
| **Boot Name** | The directory name portion: `.boot-linux` or `.boot-macos`. Derived from `uname -s` via a platform mapping function. |
| **Boot Path** | The absolute filesystem path to the boot directory (e.g., `/path/to/workspace/.boot-linux`). |
| **Platform** | The host operating system, classified as `linux` or `darwin` (lowercase, derived from `uname -s`). |
| **Workspace Root** | The top-level directory of the monorepo, identified by the presence of `pyproject.toml` or `Makefile` and a boot directory. |
| **Workspace Marker** | A directory (`.boot-linux` or `.boot-macos`) whose presence at a given path identifies that path as a workspace root during directory traversal. |
| **Hook Generation** | The process by which `projects/CI/scripts/generate-hooks` reads `.pre-commit-config.yaml` and emits native bash git hooks to `.git/hooks/`. |
| **Generated Hook** | A bash script written to `.git/hooks/{pre-commit,commit-msg,pre-push}` by the hook generation process. Sources `ci.sh` at runtime. |
| **`ci.sh`** | The CI core library (`projects/CI/lib/ci.sh`) sourced by every generated hook and CI script. Provides path resolution, output helpers, and the boot directory resolver. |
| **`realpath --relative-to`** | A GNU coreutils extension to `realpath(1)` that computes relative paths. Not available on macOS BSD `realpath`. |
| **`readlink -f`** | A GNU coreutils extension to `readlink(1)` that canonicalizes by resolving all symlinks. Not available on macOS BSD `readlink`. |

---

## 3. Functional Requirements

### FR-1: Platform Detection

**FR-1.1 - `ci_platform_name()` Function:**
The system SHALL provide a `ci_platform_name()` shell function in `projects/CI/lib/ci.sh` that echoes the lowercase value returned by `uname -s`. On Linux, it SHALL echo `linux`. On macOS (Darwin), it SHALL echo `darwin`. The boot-name resolver SHALL map unrecognized platform values to the Linux boot directory and SHALL make that selection visible to the caller.

**FR-1.2 - Detection Mechanism:**
`ci_platform_name()` SHALL use `uname -s` as the sole detection mechanism. The function SHALL NOT depend on `/etc/os-release`, `sw_vers`, or any platform-specific file. `uname -s` returns `Linux` on Linux and `Darwin` on macOS, both are stable, POSIX-mandated values.

**FR-1.3 - Function Purity:**
`ci_platform_name()` SHALL be a pure function with no side effects, no file I/O, and no external dependencies beyond `uname`. It SHALL be safe to call from any shell context (subshell, pipeline, trap handler).

### FR-2: Boot Directory Resolution

**FR-2.1 - `ci_boot_dir()` Function:**
The system SHALL provide a `ci_boot_dir()` shell function in `projects/CI/lib/ci.sh` that echoes the absolute path to the platform-appropriate boot directory. The function SHALL accept an optional workspace root argument; if omitted, it SHALL use `CI_WORKSPACE_ROOT` (set by `ci.sh` at source-time) or the current working directory.

**FR-2.2 - Directory Naming Convention:**
The boot directory name SHALL follow the pattern `.boot-<platform>` where `<platform>` is the output of `ci_platform_name()`. On Linux: `.boot-linux`. On macOS: `.boot-macos`.

**FR-2.3 - Migration Path for Existing Installations:**
When the platform-preferred boot directory does not exist but `.boot-linux` does exist, `ci_boot_dir()` SHALL select `.boot-linux` and emit a one-time warning to stderr advising the operator to re-bootstrap. This preserves installations created before platform-specific boot directories were introduced.

**FR-2.4 - `ci_boot_name()` Function:**
The system SHALL provide a `ci_boot_name()` shell function that echoes just the directory name (e.g., `.boot-linux` or `.boot-macos`), without the workspace root prefix. This is used by workspace root detection logic that needs to check for directory existence.

**FR-2.5 - Source-Time Resolution:**
When `ci.sh` is sourced, it SHALL resolve `CI_BOOT_DIR` (absolute path) and `CI_BOOT_NAME` (directory name) as variables available to all consumers. These SHALL be computed once at source-time, not on every invocation.

### FR-3: Portable Relative Path Computation

**FR-3.1 - `ci_relative_path()` Function:**
The system SHALL provide a `ci_relative_path()` shell function that computes the relative path from a source directory to a target directory using pure bash string manipulation. The function SHALL NOT depend on `realpath`, `readlink -f`, `perl`, `python`, or any GNU-specific external tool.

**FR-3.2 - Correctness:**
`ci_relative_path()` SHALL produce correct results for all cases:

- Target is a subdirectory of source: `projects/CI` (from workspace root)
- Source is a subdirectory of target: `../../projects/CI` (from a nested repo)
- Sibling directories: `../CI` (from `projects/foo` to `projects/CI`)
- Identical paths: `.` (empty string after normalization)

**FR-3.3 - Trailing Slash Insensitivity:**
`ci_relative_path()` SHALL produce identical output regardless of trailing slashes on input paths.

### FR-4: Hook Generation OS Awareness

**FR-4.1 - Portable `_ci_rel` Computation:**
`projects/CI/scripts/generate-hooks` SHALL use `ci_relative_path()` instead of `realpath --relative-to` to compute the relative path from the repository root to the CI project root (`_ci_rel`). This eliminates the GNU coreutils dependency that breaks on macOS.

**FR-4.2 - Platform-Aware PATH Emission:**
Generated hook scripts SHALL emit `PATH` entries using `CI_BOOT_DIR` (resolved at hook runtime by `ci.sh`) instead of hardcoded `.boot-linux` paths. The generated preamble SHALL be:

```bash
export PATH="${CI_BOOT_DIR}/python-env/bin:${CI_BOOT_DIR}/bin:$PATH"
```

This ensures that on macOS, the generated hooks correctly prepend `.boot-macos/python-env/bin` and `.boot-macos/bin` to `PATH`.

**FR-4.3 - Comment Accuracy:**
The generated hook header comments SHALL reference the correct CI relative path (`_ci_rel`) and re-generation command, matching the platform where generation occurred. The `# Source:` and `# Re-generate:` comment lines SHALL use the same `_ci_rel` variable.

### FR-5: Workspace Root Detection

**FR-5.1 - Dual-Marker Acceptance:**
Workspace root detection logic in `projects/CI/scripts/walk-projects`, `projects/CI/lib/checks_compliance.sh`, and any other script that walks up from a nested repo to find the workspace root SHALL accept EITHER `.boot-linux` OR `.boot-macos` as a valid workspace marker. The presence of either directory, combined with a `projects/` directory, SHALL identify the path as a workspace root.

**FR-5.2 - Marker Check in `generate-hooks`:**
The tier resolution logic in `generate-hooks` that checks for the workspace root's boot directory (to auto-create `project_enforcement.yaml`) SHALL use `ci_boot_name()` or accept either marker.

### FR-6: Bootstrap Script Boot Directory

**FR-6.1 - Platform-Default Boot Directory:**
All bootstrap scripts in `workspace/scripts/bootstrap/` SHALL default their boot directory to the platform-appropriate path (`.boot-linux` on Linux, `.boot-macos` on macOS) instead of hardcoding `.boot-linux`.

**FR-6.2 - Environment Variable Override:**
Bootstrap scripts SHALL support a `BOOT_DIR` environment variable that overrides the platform-default boot directory. During migration, an explicitly set `BOOT_LINUX_DIR` remains accepted when `BOOT_DIR` is absent.

**FR-6.3 - Bootstrap Script Pattern:**
Each bootstrap script SHALL resolve its boot directory using an inline platform detection pattern (not sourcing `ci.sh`, since bootstrap scripts run before `ci.sh` is guaranteed to be available):

```bash
_boot_platform="$(uname -s | tr 'A-Z' 'a-z')"
case "$_boot_platform" in
    darwin) _boot_name=".boot-macos" ;;
    *)      _boot_name=".boot-linux" ;;
esac
BOOT_DIR="${BOOT_DIR:-${PROJECT_ROOT}/$_boot_name}"
```

### FR-7: CLI Wrapper Boot Directory

**FR-7.1 - CLI Wrappers:**
The CLI wrapper scripts (`workspace/scripts/bin/{repo,run,ops,oc}`) SHALL resolve their boot directory to the platform-appropriate path using the same inline platform detection pattern as bootstrap scripts.

**FR-7.2 - Portable Shebang Resolution:**
CLI wrappers that currently use `readlink -f` in their `SCRIPT_DIR` resolution SHALL replace this with a portable `cd + dirname` pattern that works on both Linux and macOS:

```bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
```

### FR-8: Extension Registration

**FR-8.1 - `register_extensions.py` Platform Awareness:**
The `workspace/scripts/register_extensions.py` script SHALL determine the boot directory name using `platform.system()` instead of hardcoding `.boot-linux`. On Darwin, it SHALL use `.boot-macos`.

**FR-8.2 - `env_setup.sh` Platform Awareness:**
The `workspace/scripts/utils/env_setup.sh` `setup_paths()` function SHALL detect the platform and prepend the correct boot directory's `bin/` to `PATH`.

### FR-9: CI Library Skip Patterns

**FR-9.1 - Skip-Dir Regex:**
CI scripts that skip boot directories in file listings (`compliance-report`, `audit-workspace`, `code-stats`) SHALL use a regex pattern that matches both `.boot-linux` and `.boot-macos`:

```bash
grep -vE '\.boot-(linux|macos)|...'
```

**FR-9.2 - Ignore Lists:**
`projects/CI/lib/checks_core.sh` `_IGNORE_DIRS` array already includes `.boot-macos` (line 13). No change required.

### FR-10: Configuration Files

**FR-10.1 - Linter Excludes:**
`ruff.toml`, `mypy.toml`, and equivalent linter configuration files SHALL include both `.boot-linux` and `.boot-macos` in their exclude patterns.

**FR-10.2 - Gitignore:**
The `.gitignore` file SHALL include both `.boot-linux/` and `.boot-macos/` as ignored directories.

**FR-10.3 - Boot Layout Config:**
`config/boot_layout.yaml` SHALL document that the `boot_dir` field is resolved at runtime by `ci_boot_dir()` and that the static value serves as documentation/default only.

### FR-11: Root Makefile

**FR-11.1 - Makefile Boot Directory Variable:**
The root `Makefile` SHALL define a computed variable `BOOT_NAME` that resolves to `.boot-linux` or `.boot-macos` based on `uname -s`. All hardcoded `.boot-linux` path references in the Makefile SHALL use `$(BOOT_NAME)` instead.

---

## 4. Non-Functional Requirements

### NFR-1: Performance

**NFR-1.1 - Platform Detection Overhead:**
`ci_platform_name()` SHALL execute in under 10ms (single `uname -s` call + case statement). The overhead of platform detection in generated hooks SHALL be negligible compared to the hooks' actual work (git operations, linter invocations).

**NFR-1.2 - Relative Path Computation:**
`ci_relative_path()` SHALL execute in under 5ms for paths up to 10 components deep (pure bash string manipulation, no external processes).

### NFR-2: Compatibility

**NFR-2.1 - POSIX Shell Compliance:**
All new functions added to `ci.sh` SHALL use only POSIX-compatible shell constructs plus bashisms already present in the file (`[[ ]]`, `${var#...}`, `BASH_REMATCH`, `BASH_SOURCE[0]`). No bash 4+ features (associative arrays, `lastpipe`, `${var,,}`) SHALL be introduced.

**NFR-2.2 - macOS Bash Compatibility:**
Generated hooks and CI scripts SHALL function correctly under macOS's default bash (3.2) as well as Homebrew-installed bash (5.x). No bash 4+ features SHALL be used in generated hook code.

**NFR-2.3 - Linux Backward Compatibility:**
All existing functionality on Linux SHALL continue to work identically. The `.boot-linux` directory name, all tool paths, and all workspace detection logic SHALL remain unchanged on Linux platforms.

**NFR-2.4 - Cross-Platform Bootstrap Scripts:**
Bootstrap scripts that already detect Darwin and download macOS binaries (e.g., `bootstrap_uv.sh`, `bootstrap_kubernetes.sh`) SHALL continue to function correctly with the new default boot directory. The only change is the target directory, not the download or installation logic.

### NFR-3: Reliability

**NFR-3.1 - Fallback Completeness:**
When `ci_boot_dir()` selects `.boot-linux` because the platform directory is missing, it SHALL emit the migration warning described in FR-2.3. The returned path SHALL be valid and usable for tool resolution.

**NFR-3.2 - No Partial Migration State:**
The system SHALL tolerate mixed-state workspaces where some tools are installed in `.boot-linux` and others in `.boot-macos`. The boot directory resolver returns one directory; tools not found there fall through to system `PATH`.

**NFR-3.3 - Generated Hook Idempotency:**
Re-running `generate-hooks` on the same platform SHALL produce functionally identical hooks. Switching platforms (by changing `uname -s` result, e.g., via container) SHALL produce correctly re-targeted hooks on the next generation.

### NFR-4: Maintainability

**NFR-4.1 - Single Source of Truth:**
`projects/CI/lib/ci.sh` SHALL be the single source of truth for boot directory resolution. All scripts that need the boot directory SHALL source `ci.sh` (or use the inline pattern for bootstrap scripts that run before `ci.sh` is available).

**NFR-4.2 - All Files Under 512 Lines:**
All modified or new source files SHALL remain under 512 lines per AGENTS.md Rule 12.

**NFR-4.3 - No Comment Suppression:**
No `# shellcheck disable`, `# type: ignore`, or `# noqa` directives SHALL be introduced to suppress linting of the new code. All code SHALL pass existing lint gates without suppression.

### NFR-5: Security

**NFR-5.1 - No Path Injection:**
The boot directory path SHALL NOT be derived from user-controlled environment variables without validation. `BOOT_DIR` (in bootstrap scripts) is the only override mechanism and is validated by being used as a directory prefix.

**NFR-5.2 - No Symlink Following Outside Workspace:**
`ci_relative_path()` SHALL NOT follow symlinks outside the workspace root. Path computation SHALL use string manipulation only, not filesystem traversal.

---

## 5. Constraints

| ID | Constraint | Source |
|----|------------|--------|
| C-1 | `ci.sh` is sourced by every generated hook. All additions to `ci.sh` SHALL NOT change its passive-sourcing contract (no side effects on source, no output to stdout). | `ci.sh` header (line 4): "This file must stay passive." |
| C-2 | Bootstrap scripts cannot depend on `ci.sh` because they run during workspace bootstrap before `ci.sh` is guaranteed available. They SHALL use inline platform detection. | Bootstrap ordering (uv -> python -> everything else) |
| C-3 | The `.boot-linux` directory name SHALL NOT be renamed or removed. `.boot-macos` is an addition, not a replacement. | Backward compatibility with existing Linux deployments |
| C-4 | The `BOOT_LINUX_DIR` environment variable SHALL continue to be honored as an override, in addition to the new `BOOT_DIR` variable. | Existing operator workflows |
| C-5 | `realpath --relative-to` SHALL be replaced with a pure-bash function, not with `grealpath` (GNU coreutils via Homebrew). No new external dependencies. | AGENTS.md Rule 5 (Shell-First, Framework-Never) |
| C-6 | `readlink -f` SHALL be replaced with `cd + dirname` patterns, not with `greadlink` (GNU coreutils via Homebrew). No new external dependencies. | AGENTS.md Rule 5 (Shell-First, Framework-Never) |
| C-7 | All shell scripts SHALL use `set -euo pipefail` and pass shellcheck. | AGENTS.md Rule 1 |
| C-8 | Generated hook code SHALL NOT use bash 4+ features (associative arrays, `printf -v`, `${var,,}`, `coproc`, `lastpipe`). macOS ships bash 3.2. | macOS compatibility (NFR-2.2) |
| C-9 | `config/boot_layout.yaml` references `ci_resolve_boot_path` which does not yet exist. This function SHALL be implemented as `ci_boot_dir()` to fulfill the documented contract. | `config/boot_layout.yaml` line 4 |

---

## 6. Assumptions

| ID | Assumption |
|----|------------|
| A-1 | `uname -s` returns `Linux` on all Linux distributions and `Darwin` on all macOS versions. This is a POSIX.1-2001 mandate and has been stable across all known implementations. |
| A-2 | macOS users have bash available. macOS ships with bash 3.2 at `/bin/bash`. Users with Homebrew bash 5.x are also supported. The `#!/usr/bin/env bash` shebang resolves correctly on both. |
| A-3 | The workspace's bootstrap sequence (uv -> python -> ...) already handles macOS binary downloads correctly. Only the target directory naming needs to change. |
| A-4 | Existing Linux deployments will not be affected by the addition of `.boot-macos`. The migration rule keeps `.boot-linux` usable until re-bootstrap. |
| A-5 | The `BOOT_LINUX_DIR` environment variable is used by a limited number of operators. The migration to `BOOT_DIR` retains that explicit setting when the new variable is absent. |
| A-6 | The `config/boot_layout.yaml` specification comment referencing `ci_resolve_boot_path` was written as a forward-looking contract. Implementing `ci_boot_dir()` fulfills this contract. |
| A-7 | The `.boot-linux` directory is gitignored and not shared across machines. Each developer/CI runner has their own boot directory, so platform-specific naming introduces no cross-environment conflicts. |

---

## 7. Traceability Matrix

| Requirement ID | Source | Domain | Priority |
|:---------------|:-------|:-------|:---------|
| FR-1.1 | Self (platform abstraction needed for macOS hooks) | Platform Detection | **CRITICAL** |
| FR-1.2 | POSIX.1-2001 `uname(2)` | Platform Detection | **CRITICAL** |
| FR-1.3 | Self (function purity for shell contexts) | Platform Detection | HIGH |
| FR-2.1 | `config/boot_layout.yaml` (forward-looking `ci_resolve_boot_path`) | Boot Resolution | **CRITICAL** |
| FR-2.2 | Self (naming convention) | Boot Resolution | **CRITICAL** |
| FR-2.3 | Backward compatibility with pre-feature macOS installs | Boot Resolution | HIGH |
| FR-2.4 | `walk-projects`, `checks_compliance.sh` marker checks | Boot Resolution | HIGH |
| FR-2.5 | `ci.sh` passive-sourcing contract (compute once) | Boot Resolution | HIGH |
| FR-3.1 | `generate-hooks:47` (`realpath --relative-to` replacement) | Portability | **CRITICAL** |
| FR-3.2 | Correctness verification | Portability | HIGH |
| FR-3.3 | Edge case: trailing slashes in path construction | Portability | MEDIUM |
| FR-4.1 | `generate-hooks:47` (GNU coreutils breakage on macOS) | Hook Generation | **CRITICAL** |
| FR-4.2 | `generate-hooks:104-111` (hardcoded `.boot-linux` in PATH) | Hook Generation | **CRITICAL** |
| FR-4.3 | Generated hook readability and debuggability | Hook Generation | MEDIUM |
| FR-5.1 | `walk-projects:26`, `checks_compliance.sh:360` | Workspace Detection | HIGH |
| FR-5.2 | `generate-hooks:56` (workspace root marker check) | Workspace Detection | HIGH |
| FR-6.1 | ~25 bootstrap scripts (`.boot-linux` default) | Bootstrap | HIGH |
| FR-6.2 | `BOOT_LINUX_DIR` migration support | Bootstrap | HIGH |
| FR-6.3 | Bootstrap scripts cannot source `ci.sh` | Bootstrap | HIGH |
| FR-7.1 | `repo`, `run`, `ops`, `oc` CLI wrappers | CLI | HIGH |
| FR-7.2 | `readlink -f` GNU-only breakage on macOS | CLI | HIGH |
| FR-8.1 | `register_extensions.py:110,112` | Extensions | HIGH |
| FR-8.2 | `env_setup.sh:12` (PATH setup) | Shell | HIGH |
| FR-9.1 | `compliance-report:16`, `audit-workspace:16`, `code-stats` | CI Scripts | MEDIUM |
| FR-9.2 | `checks_core.sh:13` (already includes `.boot-macos`) | CI Scripts | LOW |
| FR-10.1 | `ruff.toml:1`, `mypy.toml:12` | Config | MEDIUM |
| FR-10.2 | `.gitignore:142` | Config | MEDIUM |
| FR-10.3 | `config/boot_layout.yaml` documentation | Config | LOW |
| FR-11.1 | `Makefile:32,116,295,298,354,359` | Build | HIGH |

---

## 8. Success Criteria

### Phase 1: Core Platform Abstraction (ci.sh)

- [ ] `ci_platform_name()` implemented and returns `linux` on Linux, `darwin` on macOS
- [ ] `ci_boot_dir()` implements the existing-installation migration rule for `.boot-linux`
- [ ] `ci_boot_name()` implemented, returns `.boot-linux` or `.boot-macos`
- [ ] `ci_relative_path()` implemented, correct for all four cases in FR-3.2
- [ ] `CI_BOOT_DIR` and `CI_BOOT_NAME` set at source-time
- [ ] `ci.sh` passive-sourcing contract preserved (no stdout on source)
- [ ] All new functions pass shellcheck without suppression

### Phase 2: Hook Generation (generate-hooks)

- [ ] `realpath --relative-to` replaced with `ci_relative_path()`
- [ ] Generated hook PATH uses `CI_BOOT_DIR` instead of hardcoded `.boot-linux`
- [ ] Workspace root marker check accepts both `.boot-linux` and `.boot-macos`
- [ ] Generated hooks function correctly on macOS (bash 3.2)
- [ ] Generated hooks function correctly on Linux (no regression)

### Phase 3: CI Scripts and Libraries

- [ ] `walk-projects` accepts both markers
- [ ] `checks_compliance.sh` accepts both markers
- [ ] `compliance-report`, `audit-workspace`, `code-stats` skip both boot dirs
- [ ] `check_required_hooks_present.py` accepts both markers
- [ ] `bootstrap-workspace-guard`, `bootstrap-gitleaks` updated

### Phase 4: Bootstrap Scripts

- [ ] All ~25 bootstrap scripts select the platform-appropriate boot directory when no override is supplied
- [ ] `BOOT_DIR` overrides work, with `BOOT_LINUX_DIR` accepted during migration
- [ ] `bootstrap_uv.sh` installs to `.boot-macos/bin/` on macOS
- [ ] `bootstrap_python.sh` creates `.boot-macos/python-env/` on macOS

### Phase 5: CLI Wrappers and Workspace Scripts

- [ ] `repo`, `run`, `ops`, `oc` use platform-aware boot directory
- [ ] `readlink -f` replaced with portable pattern in all CLI wrappers
- [ ] `register_extensions.py` uses `platform.system()` for boot dir
- [ ] `env_setup.sh` prepends correct boot dir to PATH

### Phase 6: Root Makefile and Configs

- [ ] `Makefile` uses computed `$(BOOT_NAME)` variable
- [ ] `ruff.toml` excludes both `.boot-linux` and `.boot-macos`
- [ ] `mypy.toml` excludes both `.boot-linux` and `.boot-macos`
- [ ] `.gitignore` includes both directories

### Phase 7: Tests

- [ ] Test fixtures updated to use platform-appropriate boot directory
- [ ] `test_register_extensions.py` passes on both platforms
- [ ] `test_extensions_help.py` passes on both platforms
- [ ] Hook generation test produces correct output on macOS
