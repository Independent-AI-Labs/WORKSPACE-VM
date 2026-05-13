# Specification: Workspace Metadata Separation

**Date:** 2026-05-13
**Status:** DRAFT
**Type:** Specification
**Requirements:** [REQ-METADATA.md](../requirements/REQ-METADATA.md)

## Overview

Every AMI project stores operational data (tasks, ontology objects, board configs, project metadata) under a single data root defined by the `AMI_DATA_ROOT` environment variable. Source repositories contain only code and configuration templates. This specification defines the directory layout, the discovery protocol, the store resolution mechanism, the git strategy, and the migration procedure.

## Design Decision: One Git Repo at Data Root

The data root IS a single git repository. `$AMI_DATA_ROOT/.git` covers all project subdirectories. This decision resolves Open Question 1 from the REQ doc:

**Rationale:**
- One `git push` backs up all project data simultaneously.
- Cross-project queries (e.g., "show me all open tasks") operate within one git tree.
- Simpler operator setup: `git init $AMI_DATA_ROOT` once.
- Per-project access control is not a v1 requirement; if needed later, per-project repos can be added without changing the layout.

**Commit structure:** Each auto-commit touches files within one project subdirectory. The commit message carries the project name as a prefix: `AMI-SRP: create sprint-12.task.md`.

## Directory Layout Specification

```
$AMI_DATA_ROOT/                   ← one git repo
├── .git/                         ← covers everything below
├── .gitignore                    ← excludes editor temp files, .DS_Store
├── AMI-SRP/                      ← project directory (= source repo basename)
│   ├── .tasks/                   ← FileTaskStore root
│   │   ├── board.yaml            ← column/filter/lane definitions
│   │   ├── project.yaml          ← name, namespaces, owners
│   │   ├── templates/            ← template .task.md files
│   │   │   └── bug.task.md
│   │   ├── archive/
│   │   │   └── .deleted/         ← renamed here on logical delete
│   │   ├── <group>/              ← optional subdirectory grouping
│   │   │   └── *.task.md
│   │   └── *.task.md             ← task files (slug-based filenames)
│   ├── .ontology/                ← FileObjectStore root
│   │   ├── board.yaml
│   │   ├── project.yaml
│   │   ├── archive/.deleted/
│   │   └── *.onto.md             ← ontology object files
│   └── README.md                 ← optional: human context for this project
├── AMI-PORTAL/
│   └── .tasks/
├── AMI-TRADING/
│   ├── .tasks/
│   └── .ontology/
└── ...
```

### Filename conventions (unchanged from current `.task.md` / `.onto.md` specs)

- Tasks: `{slug}.task.md` or `{slug}-{n}.task.md` on collision.
- Ontology objects: `{slug}.onto.md` when slug is present; `obj_{full-uuid}.onto.md` when absent.
- Board config: `board.yaml` (YAML, tracked).
- Project config: `project.yaml` (YAML, tracked).

### Data root `.gitignore`

```
# Editor temporary files
*.swp
*.swo
*~
.DS_Store

# Never commit index caches
.tasks/.index/
.ontology/.index/

# Never commit lock sidecars (ephemeral)
*.task.md.lock
*.onto.md.lock
```

## Store Path Resolution

### FileTaskStore

```rust
use std::env;
use std::path::PathBuf;

fn resolve_tasks_dir(project: &str) -> Result<PathBuf, StoreError> {
    let root = env::var("AMI_DATA_ROOT")
        .map_err(|_| StoreError::Backend(
            "AMI_DATA_ROOT is not set. Set it to the absolute path of your data directory.".into()
        ))?;
    let root = PathBuf::from(&root);
    if !root.is_absolute() {
        return Err(StoreError::Backend(
            format!("AMI_DATA_ROOT must be an absolute path, got: {root}", root = root.display()).into()
        ));
    }
    if !root.is_dir() {
        return Err(StoreError::Backend(
            format!("AMI_DATA_ROOT points to a non-existent directory: {root}", root = root.display()).into()
        ));
    }
    Ok(root.join(project).join(".tasks"))
}
```

### FileObjectStore

Identical resolution, substituting `.ontology` for `.tasks`.

### Validation at store open, not at compile time

The `AMI_DATA_ROOT` check happens when `FileTaskStore::open()` or `FileObjectStore::open()` is called. Compile-time configuration (build.rs, env! macro) is NOT used — the data root is a runtime concern. This allows the same binary to work against different data roots in different deployments.

## Project Identity Derivation

Three mechanisms, in order of precedence:

1. **Explicit (CLI flag or constructor argument):** The caller passes the project name directly.
   ```rust
   FileTaskStore::open("AMI-SRP")?
   ```
   CLI tools use `--project <name>` or `-p <name>`.

2. **Environment variable `AMI_PROJECT`:** Set per-shell or per-directory via direnv.
   ```bash
   export AMI_PROJECT=AMI-SRP
   ```

3. **CWD derivation:** Walk up from the current working directory looking for a known project root marker. Markers checked in order:
   - `Cargo.toml` — extract `[package].name`.
   - `package.json` — extract `"name"`.
   - `pyproject.toml` — extract `[project].name`.
   - `.git` — use the repo's directory basename.

If none of these mechanisms produce a project name, the operation fails with a descriptive error listing the available options.

### No project identity file in source

There is NO `.ami-project` file, no `project.yaml` in the source tree, no `ami.project` key in `Cargo.toml`. The project identity is derived, not declared. If two projects share the same source repo basename, one must be renamed.

## Discovery Protocol

### `srp-store-common::discover` — updated signature

```rust
/// Discover all projects with operational data under AMI_DATA_ROOT.
///
/// Walks immediate children of AMI_DATA_ROOT. Returns a list of
/// (project_name, [data_kinds]) where data_kinds indicates which
/// dot-directories exist (.tasks, .ontology, or both).
pub fn discover_projects() -> Result<Vec<DiscoveredProject>, StoreError> {
    let root = resolve_data_root()?;
    let mut projects = Vec::new();
    for entry in std::fs::read_dir(&root)? {
        let entry = entry?;
        if !entry.file_type()?.is_dir() { continue; }
        let name = entry.file_name().to_string_lossy().into_owned();
        let path = entry.path();
        let mut kinds = Vec::new();
        if path.join(".tasks").is_dir() { kinds.push(DataKind::Tasks); }
        if path.join(".ontology").is_dir() { kinds.push(DataKind::Ontology); }
        if !kinds.is_empty() {
            projects.push(DiscoveredProject { name, path, kinds });
        }
    }
    Ok(projects)
}

pub struct DiscoveredProject {
    pub name: String,
    pub path: PathBuf,
    pub kinds: Vec<DataKind>,
}

pub enum DataKind { Tasks, Ontology }
```

### PORTAL integration

PORTAL's `app/api/tasks/projects/route.ts` replaces its filesystem walk with a call to the discovery function (via napi bindings or direct filesystem access using the same algorithm):

```typescript
// OLD: walk SRP_TASKS_WORKSPACE for subdirs containing .tasks/
// NEW: walk AMI_DATA_ROOT for subdirs containing .tasks/ or .ontology/
const root = process.env.AMI_DATA_ROOT;
if (!root) {
  return Response.json({ error: "AMI_DATA_ROOT not set" }, { status: 500 });
}
const projects = fs.readdirSync(root)
  .filter(name => fs.existsSync(path.join(root, name, '.tasks')))
  .map(name => ({ name, tasksDir: path.join(root, name, '.tasks') }));
```

The `SRP_TASKS_WORKSPACE` env var is deprecated and removed from PORTAL's configuration surface.

## Git Auto-Commit Strategy

### Repository initialization

On first store open with `GitMode::On`:

1. Check if `$AMI_DATA_ROOT/.git` exists.
2. If not: initialize `git init $AMI_DATA_ROOT`.
3. Write `$AMI_DATA_ROOT/.gitignore` with the template from this spec.
4. Create an initial empty commit: `git commit --allow-empty -m "init: AMI data root"`.

### Per-mutation commits

Every create/update/delete/transition produces one commit:

```
AMI-SRP: create dark-mode-toggle.task.md

Actor-Id: 019abc...
Actor-Type: User
```

The subject line prefixes the project name. The body contains structured trailers for the actor. File paths in the commit are relative to the data root (e.g., `AMI-SRP/.tasks/dark-mode-toggle.task.md`).

### No source repo commits

The git auto-commit mechanism MUST NOT attempt to commit to source repositories. The `GitBackend` in `srp-store-common` receives the data root path, not a project source path. There is no code path that writes commits to a source repo.

## Migration Procedure

For each project currently using co-located `.tasks/` or `.ontology/`:

```bash
# 1. Set the data root
export AMI_DATA_ROOT=/home/user/ami-data

# 2. Create project directory
mkdir -p $AMI_DATA_ROOT/AMI-SRP

# 3. Move operational data
cd /path/to/AMI-SRP-source
mv .tasks $AMI_DATA_ROOT/AMI-SRP/.tasks
mv .ontology $AMI_DATA_ROOT/AMI-SRP/.ontology  # if exists

# 4. Remove co-located references from source repo
#    - Delete .tasks/ from .gitignore entries
#    - Remove .ontology/ from .gitignore entries
#    - Remove *.task.md.tmp, *.task.md.lock from .gitignore (now in data root .gitignore)

# 5. Initialize git at data root
cd $AMI_DATA_ROOT
git init
git add -A
git commit -m "init: migrate operational data from co-located source repos"

# 6. Commit source repo cleanup
cd /path/to/AMI-SRP-source
git add -A
git commit -m "chore: remove co-located .tasks/ — data now at AMI_DATA_ROOT"
```

### What the migration does NOT touch

- AMI-CI `config/` directories — stay in source repos.
- `quality_exceptions.yaml` — stays in source repos.
- Test fixtures that create temp `.tasks/` dirs — tests create their own temp data roots, not the production one.
- PORTAL's `.meta/` CMS sidecars — different concern, stay where they are.

## Updated `.gitignore` Entries

### Source repos (every project)

Add:
```
# Operational data lives at $AMI_DATA_ROOT
# No .tasks/ or .ontology/ directories belong in source repos.
```

Remove:
```
.tasks/.index/
*.task.md.tmp
*.task.md.lock
# Any reference to .tasks/ or .ontology/ as tracked or generated directories
```

### Data root

Create `$AMI_DATA_ROOT/.gitignore` with:
```
*.swp
*.swo
*~
.DS_Store
.tasks/.index/
.ontology/.index/
*.task.md.lock
*.onto.md.lock
```

## Root Workspace `.gitignore` Update

In `/home/ami/AMI-AGENTS/.gitignore`:

Remove or comment out:
```
# REMOVED: .ami-metadata/ — superseded by AMI_DATA_ROOT (see REQ-METADATA.md)
# .ami-metadata/
```

The `.ami-metadata/` entry was a placeholder that was never implemented. It is removed.

## File Map

| File | Purpose |
|---|---|
| `docs/requirements/REQ-METADATA.md` | Requirements for metadata separation |
| `docs/specifications/SPEC-METADATA.md` | This document |
| `projects/AMI-SRP/crates/srp-store-common/src/discover.rs` | Updated discovery (walks AMI_DATA_ROOT) |
| `projects/AMI-SRP/crates/srp-store-common/src/git.rs` | Auto-commits to data root |
| `projects/AMI-SRP/crates/srp-tasks/src/store/file/mod.rs` | Updated FileTaskStore::open() |
| `projects/AMI-SRP/crates/srp-objects/src/store/file/mod.rs` | Updated FileObjectStore::open() |
| `projects/AMI-PORTAL/app/api/tasks/projects/route.ts` | Updated project discovery |

## Open Implementation Questions

1. **Transactionality across the data root:** When an operation touches multiple projects (e.g., linking a task to an ontology object in another project), should the data root git commit be atomic across projects? Current leaning: no — each mutation produces its own commit. Multi-project transactions are a consumer concern.

2. **PORTAL data root for CMS data:** PORTAL's own operational data (user accounts, workspace state) currently lives in `data/*.json` (gitignored in the PORTAL source repo). Should this also move to `$AMI_DATA_ROOT/AMI-PORTAL/`? Current leaning: yes — all operational data lives under the data root. PORTAL's `data/` directory becomes a symlink or is configured to point to `$AMI_DATA_ROOT/AMI-PORTAL/server/`.

3. **Test fixtures and `AMI_DATA_ROOT` in CI:** In CI, `AMI_DATA_ROOT` should point to a temporary directory. CI pipelines must set this variable before running integration tests. The existing test infrastructure (which creates temp dirs for `.tasks/` in tests) does not change — test code uses `OpenOptions` with an explicit path override for the data root.
