# Specification: Workspace Metadata Separation

**Date:** 2026-05-13
**Status:** DRAFT
**Type:** Specification
**Requirements:** [REQ-METADATA.md](../requirements/REQ-METADATA.md)

## Overview

Every AMI project stores operational data in a dedicated git repository under `$AMI_DATA_ROOT/<project>`. The data repo is declared once via `ami data clone <remote-url>`, which stores the remote URL in the source repo's `.git/config`. From that point, the engine pulls before every read, commits on every write, and pushes after every mutation. Git credentials are inherited from the shell session.

## Design Decision: Per-Project Repos

Each source project has its own independent data repository. This decision resolves Open Question 1 from the REQ doc:

**Rationale:**
- Independent versioning — commits to AMI-SRP data don't pollute AMI-PORTAL history.
- Independent access control — different teams, different data repos.
- Independent remotes — one project can use GitHub, another GitLab.
- Simpler mental model — one source repo, one data repo. No nesting, no monorepo.

## Directory Layout

```
$AMI_DATA_ROOT/                          ← created on first clone if absent
├── ami-srp-data/                        ← git clone of git@github.com:org/ami-srp-data.git
│   ├── .git/
│   ├── .gitignore                       ← excludes *.swp, .DS_Store, lock sidecars
│   ├── .tasks/
│   │   ├── board.yaml
│   │   ├── project.yaml
│   │   ├── templates/
│   │   ├── archive/.deleted/
│   │   └── *.task.md
│   ├── .ontology/
│   │   ├── board.yaml
│   │   ├── project.yaml
│   │   ├── archive/.deleted/
│   │   └── *.onto.md
│   └── README.md
├── ami-portal-data/                     ← git clone of another remote
│   └── .tasks/
└── my-trading-data/                     ← git clone of a third remote
    └── .tasks/
```

Every directory is a standalone git repository. The directory name is derived from the data remote URL (last path component, minus `.git`).

## Data Remote Declaration

The declaration lives in the source repo's `.git/config`:

```ini
[ami]
    data = git@github.com:org/ami-srp-data.git
```

This is written by `ami data clone` and read by every store operation. It is never committed — `.git/config` is always local to the clone.

## Canonical Project Name Derivation

```rust
fn canonical_name(remote_url: &str) -> String {
    // Extract the last path component, strip .git suffix
    let path = remote_url.trim_end_matches('/');
    let name = path.rsplit('/').next().unwrap_or(path);
    name.strip_suffix(".git").unwrap_or(name).to_string()
}
```

Examples:
| Remote URL | Canonical name |
|---|---|
| `git@github.com:org/ami-srp-data.git` | `ami-srp-data` |
| `https://github.com/org/my-project` | `my-project` |
| `ssh://git@gitlab.com/team/tasks.git` | `tasks` |

## `ami data clone` Flow

```rust
fn cmd_data_clone(remote_url: &str) -> Result<()> {
    // 1. Derive canonical name
    let project = canonical_name(remote_url);

    // 2. Ensure AMI_DATA_ROOT exists
    let root = env::var("AMI_DATA_ROOT")
        .map_err(|_| "AMI_DATA_ROOT is not set")?;
    std::fs::create_dir_all(&root)?;
    let target = PathBuf::from(&root).join(&project);

    // 3. Clone or pull
    if target.join(".git").is_dir() {
        // Already cloned — pull to refresh
        let repo = Repository::open(&target)?;
        repo.find_remote("origin")?.fetch(&["main"], None, None)?;
        // Fast-forward merge
        let fetch_head = repo.find_reference("FETCH_HEAD")?;
        let commit = fetch_head.peel_to_commit()?;
        repo.branch("main", &commit, true)?;
        repo.set_head("refs/heads/main")?;
        repo.checkout_head(None)?;
    } else if target.exists() {
        bail!("{} exists but is not a git repository. Remove it and retry.", target.display());
    } else {
        // Fresh clone
        Repository::clone(remote_url, &target)?;
    }

    // 4. Write declaration to source repo's .git/config
    let source_repo = Repository::open(".")?;
    source_repo.config()?.set_str("ami.data", remote_url)?;

    println!("Data repo ready at {}", target.display());
    Ok(())
}
```

## Store Path Resolution

### FileTaskStore (updated)

```rust
impl FileTaskStore {
    pub fn open(project: &str, remote_url: &str) -> Result<Self> {
        let root = resolve_data_root()?;
        let repo_dir = root.join(project);

        // Ensure cloned
        if !repo_dir.join(".git").is_dir() {
            return Err("No data repo. Run: ami data clone <remote-url>");
        }

        let repo = Repository::open(&repo_dir)?;

        // Pull before proceeding
        pull_before_read(&repo)?;

        let tasks_dir = repo_dir.join(".tasks");
        std::fs::create_dir_all(&tasks_dir)?;

        Ok(Self {
            inner: Arc::new(Inner {
                root: tasks_dir,
                repo: Some(repo),
                events: broadcast::channel(1024).0,
                // ...
            }),
        })
    }
}
```

### FileObjectStore (same pattern)

Identical, substituting `.ontology` for `.tasks`.

## Pull-Before-Read Implementation

```rust
fn pull_before_read(repo: &Repository) -> Result<(), Warning> {
    let mut remote = match repo.find_remote("origin") {
        Ok(r) => r,
        Err(_) => return Ok(()), // no remote configured — skip
    };

    match remote.fetch(&["main"], None, None) {
        Ok(()) => {
            // Fast-forward to FETCH_HEAD
            let fetch_head = repo.find_reference("FETCH_HEAD")?;
            let commit = fetch_head.peel_to_commit()?;
            let main = repo.find_reference("refs/heads/main")
                .or_else(|_| repo.find_reference("refs/heads/master"))?;
            let main_commit = main.peel_to_commit()?;

            if commit.id() != main_commit.id() {
                // Only fast-forward (no merge conflicts in data repos)
                repo.reference("refs/heads/main", commit.id(), true,
                    "ami: pull-before-read")?;
                repo.set_head("refs/heads/main")?;
                repo.checkout_head(None)?;
            }
            Ok(())
        }
        Err(e) => {
            eprintln!("ami: pull failed ({e}), proceeding with local state");
            Ok(()) // best-effort — reads proceed with stale data
        }
    }
}
```

## Commit-And-Push-After-Write Implementation

```rust
fn commit_and_push(repo: &Repository, message: &str) -> Result<()> {
    // Stage all changes in .tasks/ and .ontology/
    let mut index = repo.index()?;
    index.add_all(["*"], git2::IndexAddOption::DEFAULT, None)?;
    index.write()?;

    let tree_id = index.write_tree()?;
    let tree = repo.find_tree(tree_id)?;

    let sig = Signature::now("ami-srp", "ami-srp@local")?;
    let head = repo.head().ok().and_then(|h| h.peel_to_commit().ok());
    let parents: Vec<&Commit> = head.iter().collect();

    repo.commit(Some("HEAD"), &sig, &sig, message, &tree, &parents)?;

    // Push
    let mut remote = repo.find_remote("origin")?;
    remote.push(&["refs/heads/main:refs/heads/main"], None)?;

    Ok(())
}
```

Called after every `create`, `update`, `delete`, `transition`. The write succeeds locally even if the push fails — uncommitted changes sit in the data repo and are included in the next successful push.

## Credential Handling

The `git2` crate's `Remote::fetch` and `Remote::push` use the default credential callback chain:

1. SSH agent (`SSH_AUTH_SOCK`)
2. Git credential helper (`git credential fill`)
3. `.netrc` file
4. Prompt (not used in automated mode — the engine sets `GIT_TERMINAL_PROMPT=0`)

No custom credential handling. If the operator can `git push` manually, the engine can push.

## Discovery

```rust
pub fn discover_projects() -> Result<Vec<DiscoveredProject>> {
    let root = resolve_data_root()?;
    let mut projects = Vec::new();
    for entry in std::fs::read_dir(&root)? {
        let entry = entry?;
        if !entry.file_type()?.is_dir() { continue; }
        let path = entry.path();
        if !path.join(".git").is_dir() { continue; }

        let name = entry.file_name().to_string_lossy().into_owned();
        let mut kinds = Vec::new();
        if path.join(".tasks").is_dir() { kinds.push(DataKind::Tasks); }
        if path.join(".ontology").is_dir() { kinds.push(DataKind::Ontology); }
        if !kinds.is_empty() {
            projects.push(DiscoveredProject { name, path, kinds });
        }
    }
    Ok(projects)
}
```

## File Map

| File | Purpose |
|---|---|
| `docs/requirements/REQ-METADATA.md` | Requirements for metadata separation |
| `docs/specifications/SPEC-METADATA.md` | This document |
| `projects/AMI-SRP/crates/srp-store-common/src/data_root.rs` | `AMI_DATA_ROOT` resolution, canonical name derivation |
| `projects/AMI-SRP/crates/srp-store-common/src/discover.rs` | `discover_projects()` walking `AMI_DATA_ROOT` |
| `projects/AMI-SRP/crates/srp-store-common/src/git.rs` | `pull_before_read()`, `commit_and_push()` |
| `projects/AMI-SRP/crates/srp-tasks/src/store/file/mod.rs` | Updated `FileTaskStore::open()` |
| `projects/AMI-SRP/crates/srp-objects/src/store/file/mod.rs` | Updated `FileObjectStore::open()` |
| `projects/AMI-SRP/crates/srp-tasks-cli-rs/src/cmd/data.rs` | `ami data clone`, `ami data status` |
| `projects/AMI-PORTAL/app/api/tasks/projects/route.ts` | Updated project discovery |

## Open Implementation Questions

1. **Branch name**: Always `main`? Or follow the source repo's default branch? Leaning: always `main` — data repos have no branching strategy, just a single linear history.

2. **Initial commit on clone**: Should the engine create an initial empty commit if the cloned data repo is empty? Leaning: yes — provides a known HEAD state for pulls.

3. **Merge conflicts in data repos**: Under normal operation, data repos are append-only (no branching, no concurrent edits to the same file). Merge conflicts indicate a bug or external tampering. Leaning: treat merge conflicts as `StoreError::Backend` with a message to resolve manually.

4. **`ami data status`**: A diagnostic command that shows the data remote, last pull time, uncommitted changes, and last push status. Deferred to a follow-up spec section.
