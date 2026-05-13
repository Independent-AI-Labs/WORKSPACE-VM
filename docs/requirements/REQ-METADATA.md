# Requirements: Workspace Metadata Separation

**Date:** 2026-05-13
**Status:** DRAFT
**Type:** Requirements
**Scope:** All AMI projects (`AMI-SRP`, `AMI-PORTAL`, `AMI-TRADING`, `AMI-DATAOPS`, `AMI-STREAMS`, `AMI-BROWSER`, `ZK-PORTAL`, `RUST-TRADING`, `PATTERNS`, `AMI-CI`)

> **Implementation status:** REQ only. No code. Supersedes all co-located metadata references in existing REQ/SPEC docs.

## Purpose

Define the absolute separation between source code repositories and operational data storage for every AMI project. Source repos contain only code, configuration templates, and specifications. All runtime data — tasks, ontology objects, board definitions, project configs, and generated artifacts — lives under a single data root defined by the `AMI_DATA_ROOT` environment variable. There is no fallback, no default, and no co-location mode.

## Design principles

Non-negotiable constraints on every implementation decision:

1. **Absolute separation.** A source repo MUST NOT contain operational data in any tracked or untracked form. `.tasks/`, `.ontology/`, and any equivalent dot-directories are removed from project repos. A project cloned from source contains zero operational state.

2. **One variable, no fallbacks.** `AMI_DATA_ROOT` is the sole mechanism for locating operational data. If the variable is unset, empty, or points to a non-existent directory, every store operation returns a hard error. There is no default path, no `~/ami-data` fallback, no `.ami-data-root` sidecar file, no `AMI_DATA_ROOT` in `.env` auto-detection. The operator sets it or nothing works.

3. **Flat project namespace.** Under the data root, every project has one directory named by the project's canonical identifier (the source repo directory name — `AMI-SRP`, `AMI-PORTAL`, etc.). There is no nesting, no grouping hierarchy, no namespacing beyond the directory name.

4. **Git at data root.** `$AMI_DATA_ROOT` is a git repository (or contains per-project git repos — see SPEC). The engine auto-commits operational data to this repo. Source repos never receive data commits. The audit trail lives with the data, not the code.

## Scope

In scope:
- The `AMI_DATA_ROOT` environment variable specification.
- The data root directory layout and naming conventions.
- How projects register in the data root (project identity).
- How file stores (FileTaskStore, FileObjectStore) resolve paths against the data root.
- How discovery works (PORTAL, CLI tools finding project data).
- How git auto-commits operate in the separated model.
- Migration from co-located `.tasks/` directories (one-time, operator-driven).
- What gets removed from source repos (`.tasks/`, `.ontology/`, co-located references).
- The `srp-store-common::discover` module's new contract.

Out of scope:
- PORTAL's `.meta/` CMS sidecar model (different concern — content annotation, not operational data).
- `.claude/` and per-session agent state (unchanged — gitignored, local-only).
- AMI-CI compliance infrastructure (`quality_exceptions.yaml`, `config/` — unchanged, tracked in source).
- Secrets management (`.env`, credentials — unchanged).
- Build artifacts (`target/`, `.next/`, `dist/` — unchanged).
- XDG compliance beyond the `AMI_DATA_ROOT` pattern (no `XDG_DATA_HOME` integration needed).

## Cross-references

- [SPEC-METADATA.md](../../docs/specifications/SPEC-METADATA.md) — Implementation specification.
- `REQ-TASK-ENGINE.md` (AMI-SRP) — Task persistence, to be updated for data root.
- `REQ-OBJECT-ENGINE.md` (AMI-SRP) — Object persistence, to be updated for data root.
- `REQ-TASK-MANAGEMENT.md` (AMI-PORTAL) — UI layer, to be updated for data root discovery.

---

## Functional Requirements

### FR-1: `AMI_DATA_ROOT` environment variable

The variable MUST be an absolute filesystem path. It MUST point to an existing directory. Every project that reads or writes operational data MUST resolve its data paths relative to this variable. An unset, empty, relative, or non-existent `AMI_DATA_ROOT` is a hard error on every data operation — no store opens, no task is created, no object is read.

The variable is set once per machine (or per session). It is not per-project, not per-shell, not derived from CWD. The expectation is that it lives in shell profile (`~/.bashrc`, `~/.zshrc`) or systemd environment.

### FR-2: Data root directory layout

```
$AMI_DATA_ROOT/
├── AMI-SRP/
│   ├── .tasks/              ← task files (*.task.md)
│   │   ├── board.yaml
│   │   ├── project.yaml
│   │   ├── templates/
│   │   ├── archive/.deleted/
│   │   └── <group>/
│   ├── .ontology/           ← ontology object files (*.onto.md)
│   │   ├── board.yaml
│   │   ├── project.yaml
│   │   └── archive/.deleted/
│   └── README.md            ← optional: describes this project's data
├── AMI-PORTAL/
│   └── .tasks/
├── AMI-TRADING/
│   ├── .tasks/
│   └── .ontology/
└── ...
```

Every project directory under the data root is named by the project's canonical identifier — the source repo directory name. No two projects may share the same name (flat namespace, no nesting).

Project directories are created on first write via `create_dir_all`. The operator may pre-create them or let the engine handle it. Empty project directories are valid — they simply return empty listings.

### FR-3: Project identity

Every project identifies itself by its canonical name — the basename of its source repository. This is obtained at runtime:

- **Rust crates**: `env!("CARGO_PKG_NAME")` or the workspace member name.
- **CLI tools**: `--project <name>` flag or derived from the current working directory by walking up to find a known project marker (e.g., `Cargo.toml` with a specific `[package] name`).
- **PORTAL**: Already knows its own project identity; passes it to the store.

The project name is never stored in a file within the source repo. There is no `.ami-project` marker file, no `.project-name` sidecar, no `project.yaml` in the source tree. The name is either explicit (CLI flag) or derivable from the source repo root's basename.

### FR-4: Store path resolution

Every file store (`FileTaskStore`, `FileObjectStore`) resolves its operational directory against `AMI_DATA_ROOT`. The concrete path is:

```
$AMI_DATA_ROOT/<project-name>/.tasks/
$AMI_DATA_ROOT/<project-name>/.ontology/
```

The store's `open()` method takes the project name and constructs the full path. There is no provision for opening a store at an arbitrary path — every store is rooted under `AMI_DATA_ROOT/<project>/`.

Example:
```rust
// FileTaskStore::open("AMI-SRP")?
// → resolves to $AMI_DATA_ROOT/AMI-SRP/.tasks/
```

### FR-5: Discovery

Project discovery walks `$AMI_DATA_ROOT` for immediate child directories. Every child directory that contains a `.tasks/` or `.ontology/` subdirectory is a project with operational data.

The discovery function (`srp-store-common::discover`) no longer walks arbitrary workspace roots — it ONLY walks `AMI_DATA_ROOT`. The concept of a "workspace root" for data discovery is replaced by the data root.

PORTAL's project listing API reads `AMI_DATA_ROOT` and returns the set of child directories containing `.tasks/`.

### FR-6: Git auto-commits

When git auto-commits are enabled (`GitMode::On`), the engine commits to the git repository at the data root. This is ONE repository containing all project data, or optionally one repository per project directory (see SPEC for the decision).

- If `$AMI_DATA_ROOT` is a git repository: commits go to that repo, with file paths prefixed by the project directory (e.g., `AMI-SRP/.tasks/some-task.task.md`).
- If `$AMI_DATA_ROOT` is NOT a git repository: the engine initializes one on first write, or errors if `GitMode::On` is requested without a pre-existing repo (see SPEC).
- Source repos are NEVER auto-committed to. The engine MUST NOT touch git repositories outside the data root.

### FR-7: Migration from co-location

Existing projects with `.tasks/` or `.ontology/` directories inside their source repos MUST be migrated. This is an operator-driven, one-time process:

1. Set `AMI_DATA_ROOT` to the desired data directory.
2. Create the project subdirectory: `mkdir -p $AMI_DATA_ROOT/<project>/`
3. Move the dot-directory: `mv .tasks/ $AMI_DATA_ROOT/<project>/.tasks/`
4. Remove any remaining co-located references from `.gitignore` and documentation.
5. Commit the source repo changes (removal of `.tasks/`, updated `.gitignore`).

There is no automated migration tool in v1. The operator owns this process.

### FR-8: What gets removed from source repos

Every AMI project source repository MUST NOT contain:

- `.tasks/` directories or any `*.task.md` files.
- `.ontology/` directories or any `*.onto.md` files.
- Project-level `board.yaml` or `project.yaml` in the repo root.
- `.tasks/.index/` directories or index caches.
- Any reference to co-located data in `.gitignore`, README, or documentation.
- `SRP_TASKS_WORKSPACE` references that imply co-location (PORTAL should use `AMI_DATA_ROOT` instead).

What REMAINS in source repos:

- `quality_exceptions.yaml` (compliance — reviewed on every PR).
- `config/` (AMI-CI overrides — per-project, tracked).
- `.claude/` (agent sessions — gitignored, local-only).
- `src/`, `crates/`, `Cargo.toml`, `Makefile`, `moon.yml`, and all source code.
- `docs/` (requirements, specifications).
- `.env.example` (template only, secrets never committed).

### FR-9: Error handling for missing data root

When `AMI_DATA_ROOT` is unset, empty, relative, or points to a non-existent directory:

- `FileTaskStore::open()` returns `StoreError::Backend("AMI_DATA_ROOT is not set or invalid: ...")`.
- `FileObjectStore::open()` returns the equivalent `StoreError`.
- PORTAL's API returns HTTP 500 with a clear message: "AMI_DATA_ROOT not configured".
- CLI tools print an error to stderr and exit non-zero.
- The error message MUST include the current value of `AMI_DATA_ROOT` (or state that it is unset) and MUST explain how to set it.

### FR-10: Multiple projects on one machine

A single machine may run multiple AMI projects simultaneously. All projects share the same `AMI_DATA_ROOT`. Each project's operational data is isolated in its own subdirectory. There is no project-level isolation mechanism beyond the directory name — two projects with the same canonical name WILL collide in the data root. Rename one source repo to resolve.

---

## Non-Functional Requirements

### NFR-1: No magic files

Source repos MUST NOT contain any file whose sole purpose is to declare the project's data root or project identity. No `.ami-data-root`, no `.ami-project`, no `project.yaml` in the source tree, no `data_root` field in `Cargo.toml` or `package.json`. The project name is derived from the repo directory basename; the data root is `AMI_DATA_ROOT`.

### NFR-2: Single mechanism

There is exactly one way to configure the data root: the `AMI_DATA_ROOT` environment variable. No CLI flag overrides, no config file overrides, no compile-time defaults, no runtime negotiation. One variable, one behavior.

### NFR-3: Consistent across languages

Every project — Rust, TypeScript, Python — resolves operational data paths using the same `AMI_DATA_ROOT` variable and the same directory layout convention. The implementation language differs; the contract does not.

### NFR-4: Backward incompatibility is explicit

This specification deliberately breaks backward compatibility with any co-located `.tasks/` or `.ontology/` usage. The migration path (FR-7) is manual and operator-driven. There is no compatibility shim, no "fallback to repo root," no transitional period where both modes work.

---

## Open Questions

1. **Git structure at data root**: One git repo for the entire data root (`$AMI_DATA_ROOT/.git`) or one git repo per project (`$AMI_DATA_ROOT/<project>/.git`)? Single repo is simpler for backup; per-project repos allow independent versioning and access control. SPEC must decide.

2. **Project identity derivation**: Should the project name always be passed explicitly (via `--project` flag or constructor argument), or should CLI tools auto-derive it from CWD? Explicit is unambiguous but verbose; auto-derivation is convenient but fragile when CWD differs from repo root.

3. **PORTAL's `SRP_TASKS_WORKSPACE`**: Should this env var be removed in favor of `AMI_DATA_ROOT`, or should PORTAL use BOTH (data root for file stores, workspace for project discovery)? Current leaning: PORTAL uses `AMI_DATA_ROOT` for data, drops `SRP_TASKS_WORKSPACE`.

4. **Existing `.task.md` test fixtures**: Many test files in `srp-tasks/tests/` and `srp-tasks-cli-rs/tests/` create `.tasks/` directories in temp dirs. These are test artifacts, not operational data. Do they need to change? Leaning: no — test code creates temp dirs and sets a mock data root; the data root concept applies only to production store operations.
