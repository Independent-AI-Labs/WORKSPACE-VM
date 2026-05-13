# Requirements: Workspace Metadata Separation

**Date:** 2026-05-13
**Status:** DRAFT
**Type:** Requirements
**Scope:** All AMI projects (`AMI-SRP`, `AMI-PORTAL`, `AMI-TRADING`, `AMI-DATAOPS`, `AMI-STREAMS`, `AMI-BROWSER`, `ZK-PORTAL`, `RUST-TRADING`, `PATTERNS`, `AMI-CI`)

> **Implementation status:** REQ only. No code. Supersedes all co-located metadata references in existing REQ/SPEC docs.

## Purpose

Define the absolute separation between source code repositories and operational data storage for every AMI project. Each source project declares a data remote — a separate git repository where its `.onto.md` and `.task.md` files live. The engine clones it to `$AMI_DATA_ROOT/<project>`, pulls before every read, writes with commit, and pushes immediately after every mutation. No operational data ever touches a source repo.

## Design principles

1. **Absolute separation.** Source repos contain only code, configuration templates, and specifications. Operational data lives in per-project git repositories under `$AMI_DATA_ROOT`. A source repo cloned from origin contains zero operational state.

2. **One data repo per project.** Every source project has its own independent data repository. There is no shared monorepo. Project identity is canonical and derived from the source repo's remote origin URL.

3. **Clone-on-declare.** The operator runs `ami data clone <remote-url>` once per project. The engine clones it to `$AMI_DATA_ROOT/<project>`. From that point forward, the CLONE is the ground truth — the operator never manually creates directories or runs `git init`.

4. **Pull-before, push-after.** Before every read operation, the engine pulls the latest from the data remote. After every write operation, the engine commits and pushes. The data store is always operating against the freshest remote state. There is no offline mode.

5. **Reuse shell credentials.** The engine uses the same git credentials as the current shell session (SSH agent, credential helper, or git config). No separate authentication configuration. If the operator can `git push` from the shell, the engine can too.

6. **No fallback, no default, no colocation.** `AMI_DATA_ROOT` must be set. The data remote must be declared. If either is missing, every store operation returns a hard error with a clear remediation message.

## Scope

In scope:
- Per-project data repository declaration via `ami data clone <remote-url>`.
- `AMI_DATA_ROOT` environment variable specification.
- Data root directory layout (one git repo per project).
- Canonical project identity derivation from source repo remote URL.
- Pull-before-read, commit-and-push-after-write synchronization.
- How file stores resolve paths against the data root.
- How git auto-commits operate (every write is a commit + push).
- What gets removed from source repos.

Out of scope:
- PORTAL's `.meta/` CMS sidecar model (different concern — content annotation).
- `.claude/` and per-session agent state (unchanged).
- AMI-CI compliance infrastructure (unchanged, tracked in source).
- Secrets management (unchanged).
- Build artifacts (unchanged).
- Shared data repos — every project gets its own.

## Cross-references

- [SPEC-METADATA.md](../../docs/specifications/SPEC-METADATA.md) — Implementation specification.
- `REQ-TASK-ENGINE.md` (AMI-SRP) — Task persistence, to be updated.
- `REQ-OBJECT-ENGINE.md` (AMI-SRP) — Object persistence, to be updated.
- `REQ-TASK-MANAGEMENT.md` (AMI-PORTAL) — UI layer, to be updated.

---

## Functional Requirements

### FR-1: `AMI_DATA_ROOT` environment variable

The variable MUST be an absolute filesystem path. It is the parent directory under which per-project data repos are cloned. It MUST be set before any data operation. An unset, empty, or relative `AMI_DATA_ROOT` is a hard error.

Unlike the previous revision, `AMI_DATA_ROOT` does NOT need to exist before use — the engine creates it on first `ami data clone`. But if it IS set to a path that exists and is a file (not a directory), that is an error.

### FR-2: Per-project data repositories

Every source project that needs operational data MAY declare a data remote. This is a git URL pointing to a repository dedicated to that project's `.onto.md` and `.task.md` files. The declaration is optional — data repos are first-class and can exist without any source repo referencing them.

When declared, the mapping is stored in the source repo's `.git/config`:
```
[ami]
    data = git@github.com:org/ami-srp-data.git
```

The operator runs `ami data clone git@github.com:org/ami-srp-data.git` from within the source repo. The CLI stores the declaration in `.git/config`. From that point forward, the declaration enables auto-discovery of the data repo on new machines.

**Standalone data repos:** Any git repository under `$AMI_DATA_ROOT` that contains `.tasks/` or `.ontology/` is a valid data repo. It can be cloned manually (`git clone <url> $AMI_DATA_ROOT/<name>`) and used immediately with `--project <name>`. No source repository is required.

### FR-3: Canonical project identity

The project's canonical name is derived from the DATA REMOTE URL, not the local source directory, not the source repo's origin. The name is the last path component of the remote URL, minus the `.git` suffix.

```
git@github.com:org/ami-srp-data.git      →  ami-srp-data
https://github.com/org/my-project.git    →  my-project
ssh://git@gitlab.com/team/tasks.git       →  tasks
```

This name is immutable. Renaming the data remote requires a new data repo. Multiple source clones of the same project (e.g., `~/work/ami-srp/` and `~/forks/ami-srp/`) auto-discover the same canonical name because they share the same `[ami] data` declaration in their `.git/config`.

### FR-4: Data root directory layout

```
$AMI_DATA_ROOT/
├── ami-srp-data/           ← cloned from git@github.com:org/ami-srp-data.git
│   ├── .git/
│   ├── .tasks/              ← task files
│   │   ├── board.yaml
│   │   ├── project.yaml
│   │   ├── templates/
│   │   ├── archive/.deleted/
│   │   └── *.task.md
│   ├── .ontology/           ← ontology object files
│   │   ├── board.yaml
│   │   ├── project.yaml
│   │   ├── archive/.deleted/
│   │   └── *.onto.md
│   └── README.md
├── ami-portal-data/        ← cloned from another remote
│   └── .tasks/
└── my-trading-data/        ← cloned from a third remote
    └── .tasks/
```

Every directory under `$AMI_DATA_ROOT` IS a git repository. The directory name is the canonical project name (derived from the data remote URL). There is no nesting, no grouping, no monorepo.

### FR-5: Clone on declare

`ami data clone <remote-url>` performs:

1. Derives the canonical project name from the remote URL.
2. Creates `$AMI_DATA_ROOT/<project>/` via `git clone <remote-url> $AMI_DATA_ROOT/<project>`.
3. If the clone succeeds: writes `[ami] data = <remote-url>` to the source repo's `.git/config`.
4. If `AMI_DATA_ROOT` does not exist: creates it (`mkdir -p`) before cloning.
5. If the project directory already exists and is a git repo: pulls instead of cloning (recovery from partial state).
6. If the project directory exists but is NOT a git repo: hard error — `"$AMI_DATA_ROOT/<project> exists but is not a git repository. Remove it and retry."`

### FR-6: Store path resolution

File stores resolve their operational directory against the data root:
```
$AMI_DATA_ROOT/<project>/.tasks/
$AMI_DATA_ROOT/<project>/.ontology/
```

The `<project>` name is the canonical name from `[ami] data` in the source repo's `.git/config`. If the declaration is missing: hard error — `"No data remote configured. Run: ami data clone <remote-url>"`.

### FR-7: Pull-before-read

Before every `get`, `list`, `count`, `resolve_links`, or `backlinks` operation, the file store performs a `git pull` in the data repo. If the pull fails (network unreachable, auth expired, merge conflict), the read still proceeds against the local state — the pull is best-effort for reads. A warning is emitted to the event log.

### FR-8: Commit-and-push-after-write

After every `create`, `update`, `delete`, or `transition` operation, the file store:

1. Commits the changes to the data repo with a structured commit message.
2. Pushes to the remote declared in `[ami] data`.
3. If the push fails: the write succeeded locally but remote sync failed. The operation returns success with a warning. The next successful push catches up all pending commits.
4. No push is faster than the write itself — the engine does not wait for network round-trips before returning success to the caller.

### FR-9: Git credential reuse

The engine uses `git2::Remote::push` and `git2::Remote::fetch` with the default credential callback — meaning it picks up the same SSH agent, credential helper, or git config that the shell uses. No additional configuration. If the operator can `git push` manually, the engine can push automatically.

### FR-10: Discovery

`ami data discover` (or equivalent) walks `$AMI_DATA_ROOT` for immediate child directories. Every child that is a git repository with a `.tasks/` or `.ontology/` subdirectory is a discovered project.

PORTAL's project listing API uses the same discovery mechanism.

### FR-11: What gets removed from source repos

Every AMI project source repository MUST NOT contain `.tasks/`, `.ontology/`, any `*.task.md` or `*.onto.md` files, or any project config files (`board.yaml`, `project.yaml`).

`SRP_TASKS_WORKSPACE` is deprecated and removed from PORTAL's configuration surface.

---

## Non-Functional Requirements

### NFR-1: No magic files

Source repos MUST NOT contain `.ami-metadata/` or any file whose sole purpose is metadata configuration. The `[ami] data` section in `.git/config` is the only declaration mechanism.

### NFR-2: Single mechanism

One way to declare the data remote: `[ami] data` in `.git/config`. No env vars, no CLI flags, no config files.

### NFR-3: Consistent across languages

Every project resolves operational data paths identically regardless of implementation language.

### NFR-4: Backward incompatibility is explicit

This specification deliberately breaks backward compatibility with co-located data. Migration is operator-driven: `mv .tasks/ $AMI_DATA_ROOT/<project>/.tasks/`, push data repo, run `ami data clone` on other machines.

---

## Open Questions

1. **Pull-before-read: best-effort or hard requirement?** Current: best-effort (warn, proceed with stale data). Alternative: hard error if pull fails (no stale reads). Leaning best-effort for usability — a developer offline should still be able to read their local data.

2. **Push-after-write: synchronous or background?** Current: synchronous (block until push completes). Alternative: background task that pushes periodically. Leaning synchronous — simpler reasoning, no queued state, immediate feedback if push fails.

3. **Data repo initial state:** Should `ami data clone` scaffold `.tasks/`, `.ontology/`, `board.yaml`, and `project.yaml` automatically, or should the empty repo be valid (files created on first write)? Leaning: empty repo is valid, files are created on first write.

4. **Multiple source projects sharing one data repo?** Current: prohibited (one data repo per project). Is there a use case for sharing? If two source projects want the same tasks, they should link to the same data remote. The `[ami] data` declaration allows this — just set it to the same URL.
