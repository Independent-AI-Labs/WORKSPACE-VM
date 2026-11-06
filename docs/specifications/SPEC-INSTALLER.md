# SPEC-INSTALLER: Bootstrap and Host Configuration Implementation

**Date:** 2026-11-02
**Status:** Active
**Type:** Specification
**Requirements:** [REQ-INSTALLER](../requirements/REQ-INSTALLER.md)

> Implementation of [REQ-INSTALLER](../requirements/REQ-INSTALLER.md). One
> auxiliary feature registry, one host stage, two execution scopes, and one
> storage seam writer owned by WORKSPACE-DATAOPS.

---

## 1. Layout

```
workspace/config/install-aux.yaml            # auxiliary feature registry
workspace/config/install-aux-defaults.yaml   # non-interactive aux selections
workspace/config/install-defaults.yaml       # component selections (existing)
workspace/scripts/bootstrap_aux_defs.py      # schemas + loader
workspace/scripts/bootstrap_aux.py           # status scan + action runner
workspace/scripts/host_setup_installer.py    # host TUI + defaults mode
workspace/scripts/host_setup_installer_ui.py # presentation helpers
projects/WORKSPACE-DATAOPS/scripts/storage/write-storage-locations.sh
```

## 2. Auxiliary registry

`workspace/config/install-aux.yaml`:

```yaml
groups:
  - Storage
  - Host Services

features:
  - id: storage-locations
    label: Storage locations
    description: Write fast/backup seam
    group: Storage
    scope: agent
    action: storage-configure
    order: 10
    enabled_by_default: true
    detect_path: workspace/config/storage-locations.yaml
    args:
      fast:
        default: /mnt/ws-fast
        description: Fast storage root
      backup:
        default: /mnt/ws-backup
        description: Backup storage root
```

Fields:

| Field | Meaning |
|---|---|
| `id` | Stable identifier used by defaults |
| `label` | TUI label |
| `description` | One-line description |
| `group` | TUI group |
| `scope` | `agent` or `root` |
| `action` | Fixed handler key |
| `order` | Execution order, ascending |
| `enabled_by_default` | Preselected in non-interactive mode |
| `detect_path` | Path whose existence means configured |
| `args` | Named values with defaults |
| `requires` | Feature IDs that must run first |

## 3. Action handlers

| Action | Scope | Command |
|---|---|---|
| `storage-configure` | agent | `bash projects/WORKSPACE-DATAOPS/scripts/storage/write-storage-locations.sh --fast <fast> --backup <backup>` |
| `storage-mount-backup` | root | `make -C projects/WORKSPACE-DATAOPS storage-mount NAME=ws-backup` |
| `storage-persist-backup` | root | `make -C projects/WORKSPACE-DATAOPS storage-persist NAME=ws-backup` |
| `storage-provision-fast` | root | `make -C projects/WORKSPACE-DATAOPS storage-provision` then apply after confirmation |
| `storage-migrate` | agent | `make -C projects/WORKSPACE-DATAOPS storage-migrate` |
| `install-diagnostics` | agent | `make install-diagnostics` |
| `install-agentci` | agent | `make install-agentci` |
| `install-moderator` | agent | `make install-moderator` |
| `dataops-profiles` | agent | `make -C projects/WORKSPACE-DATAOPS runtime-up PROFILES=<profiles>` |

Handlers are a closed set. YAML cannot inject arbitrary commands.

## 4. Execution model

1. Load registry.
2. Scan `detect_path` for each feature.
3. Interactive: multiselect grouped features, prompt argument values.
4. Defaults: enable features from `install-aux-defaults.yaml`.
5. Validate required arguments and scope.
6. Sort by `order`, then `requires`.
7. Root stage: run `root` features directly.
8. Root stage: run `agent` features through `runuser -u "$SUDO_USER" --`.
9. User stage: run only `agent` features.
10. Report each result. Any failure exits non-zero.

Root stage order:

```
system packages -> deploy-ci -> host aux TUI -> guard -> hooks -> limits
```

## 5. Make integration

| Target | Scope | Behaviour |
|---|---|---|
| `make install` | agent | component TUI + agent auxiliary defaults |
| `make install-ci` | agent | component defaults + agent auxiliary defaults |
| `make install-aux` | agent | host TUI, agent features only |
| `make install-aux-ci` | agent | host defaults, agent features only |
| `sudo make init` | root | system packages + `init-root` |
| `init-root` | root | deploy-ci + host TUI + guard + hooks + limits |

`init-root` chooses the TUI when stdin is a terminal; otherwise it uses
`workspace/config/install-aux-defaults.yaml`. Override the file with
`sudo make init AUX_DEFAULTS=/path/to/defaults.yaml`. The TUI is skipped with
an explicit message when `.venv` is absent; run `make install` first.

## 6. Storage seam writer

`write-storage-locations.sh`:

- Requires absolute `--fast` and `--backup` paths.
- Rejects `/`.
- Resolves the workspace root with `lib-storage.sh::storage_workspace_root`.
- Writes atomically through a temporary file and `mv`.
- Writes the canonical `dirs` map.
- Is idempotent.
- Never prints secrets.

Output:

```yaml
fast: /mnt/ws-fast
backup: /mnt/ws-backup
dirs:
  containers: containers
  models: models
  qemu: qemu
  caches: caches
  diag: diag
  swap: swap
```

## 7. Defaults file

`workspace/config/install-aux-defaults.yaml`:

```yaml
features:
  storage-locations:
    enabled: true
    args:
      fast: /mnt/ws-fast
      backup: /mnt/ws-backup
  diagnostics:
    enabled: true
  agentci:
    enabled: true
```

Root-gated storage and DATAOPS profiles stay disabled until the selection file enables them. Unknown feature
IDs fail validation.

## 8. Failure behaviour

- Missing registry: named error with the expected path.
- Unknown action: named error with the feature ID.
- Root feature in a non-root run: skipped and reported.
- Agent feature without `SUDO_USER` in a root run: named error.
- Missing tool for an action: named error with the remediation command.
- Failed subprocess: propagate exit status; stop unless the feature is optional.

## 9. Tests

| Test | Coverage |
|---|---|
| `tests/unit/scripts/test_bootstrap_aux_defs.py` | schema, loader, unknown ID, required args |
| `tests/unit/scripts/test_bootstrap_aux.py` | ordering, scope gate, command construction, failure |
| `tests/unit/scripts/test_host_setup_installer.py` | defaults parsing, selection, dispatch |
| DATAOPS `tests/unit/host/test_storage_scripts.py` | seam writer validation and idempotency |

No test executes root actions or real mounts.

## 10. File map

| File | Change |
|---|---|
| `docs/requirements/REQ-INSTALLER.md` | new |
| `docs/specifications/SPEC-INSTALLER.md` | new |
| `workspace/config/install-aux.yaml` | new |
| `workspace/config/install-aux-defaults.yaml` | new |
| `workspace/scripts/bootstrap_aux_defs.py` | new |
| `workspace/scripts/bootstrap_aux.py` | new |
| `workspace/scripts/host_setup_installer.py` | new |
| `workspace/scripts/host_setup_installer_ui.py` | new |
| `projects/WORKSPACE-DATAOPS/scripts/storage/write-storage-locations.sh` | new |
| `projects/WORKSPACE-DATAOPS/Makefile` | add `storage-configure` |
| `Makefile` | add `install-aux`, `install-aux-ci`, wire `init-root` |
| `.gitignore` | ignore machine-local storage seam |
| `workspace/config/bootstrap-components.yaml` | remove `hooks` from user stage |
| `docs/README.md` | index both documents |

## 11. Implementation status

| Item | Status |
|---|---|
| Registry + schemas | Implemented |
| Host TUI + defaults | Implemented |
| Storage seam writer | Implemented |
| Make wiring | Implemented |
| Tests | Implemented |
