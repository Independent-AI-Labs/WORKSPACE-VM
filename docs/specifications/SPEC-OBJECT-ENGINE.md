# Specification: Object Engine (`srp-objects`)

**Date:** 2026-05-12
**Status:** DRAFT
**Type:** Specification
**Requirements:** [REQ-OBJECT-ENGINE.md](../projects/AMI-SRP/docs/requirements/REQ-OBJECT-ENGINE.md)

## Overview

`srp-objects` is the persistence and query layer for ontology object instances. It provides a single `ObjectStore` trait with two backends (file and in-memory), an `Object` data model that wraps any ontology type in a generic container, link traversal via full directory scans (unvalidated-link model), and validation against `srp-ontology` metadata on every write.

## Crate Layout

```
crates/srp-objects/
├── Cargo.toml              # deps: srp-ontology, srp-types, srp-store-common,
│                           #       serde, serde_json, serde_yaml_ng, uuid, chrono,
│                           #       tokio, async-trait, dashmap, thiserror
└── src/
    ├── lib.rs              # re-exports
    ├── object.rs           # Object, CreateObjectInput, ObjectPatch
    ├── filter.rs           # ObjectFilter, ObjectPage
    ├── event.rs            # ObjectEvent, ObjectEventStream
    ├── validate.rs         # Validation against srp-ontology metadata
    ├── id.rs               # ObjectId (UUID v7 newtype, to be promoted to srp-types)
    └── store/
        ├── mod.rs          # ObjectStore trait
        ├── file/
        │   ├── mod.rs      # FileObjectStore (open, create, get, list, etc.)
        │   ├── frontmatter.rs  # .onto.md split/join (YAML frontmatter + Markdown body)
        │   └── slug.rs     # Slug collision check via directory scan
        └── memory/
            └── mod.rs      # InMemoryObjectStore (DashMap-backed)
```

Dependencies on `srp-store-common` (extracted from `srp-tasks`) for:
- `atomic::write_atomic()` — crash-safe file writes
- `lock::LockfileGuard` — opt-in `flock(2)` sidecar
- `discover::find_dirs_containing()` — workspace project discovery
- `git::GitBackend` — opt-in per-mutation auto-commits

## Data Model

### Object

```rust
pub struct Object {
    pub id: ObjectId,                       // UUID v7 newtype
    pub namespace: String,                  // ami.dev, ami.pmf, ami.fundraising
    pub object_type: String,                // Feature, TermSheet, Hypothesis
    pub slug: Option<String>,               // per-namespace unique, immutable
    pub data: serde_json::Value,            // type-specific fields
    pub links: IndexMap<String, Vec<ObjectId>>,  // typed relationships
    pub marking: SecurityMarking,           // object-level MLS
    pub actor: Actor,                       // creator
    pub version: i64,                       // optimistic concurrency
    pub labels: Vec<String>,
    pub body: String,                       // Markdown body
    pub metadata: IndexMap<String, serde_json::Value>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}
```

### Serde field aliases

Same pattern as `Task` in `srp-tasks`:

| Rust field | YAML frontmatter key | Reason |
|---|---|---|
| `object_type` | `type` | Shorter, matches task convention |
| `created_at` | `created` | Shorter |
| `updated_at` | `updated` | Shorter |

### ObjectId

```rust
// crates/srp-objects/src/id.rs (promote to srp-types later)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct ObjectId(pub Uuid);

impl ObjectId {
    pub fn new_v7() -> Self { Self(Uuid::now_v7()) }
}
```

### CreateObjectInput

```rust
pub struct CreateObjectInput {
    pub namespace: String,
    pub object_type: String,
    pub slug: Option<String>,
    pub data: serde_json::Value,
    pub links: IndexMap<String, Vec<ObjectId>>,
    pub marking: Option<SecurityMarking>,  // defaults to Internal
    pub actor: Actor,
    pub labels: Vec<String>,
    pub body: String,
    pub metadata: IndexMap<String, serde_json::Value>,
}
```

### ObjectPatch

```rust
pub struct ObjectPatch {
    pub data: Option<serde_json::Value>,    // None = unchanged
    pub links: Option<IndexMap<String, Vec<ObjectId>>>,
    pub labels: Option<Vec<String>>,
    pub body: Option<String>,
    pub metadata: Option<IndexMap<String, serde_json::Value>>,
}
```

Marking changes are not permitted via `ObjectPatch`. The store provides a dedicated `reclassify` operation for security marking transitions, requiring clearance validation for both the old and new levels.

### ObjectFilter

```rust
pub struct ObjectFilter {
    pub namespace: Option<String>,
    pub object_type: Option<String>,
    pub labels_any: Vec<String>,
    pub labels_all: Vec<String>,
    pub marking_max: Option<SecurityMarking>,
    pub created_after: Option<DateTime<Utc>>,
    pub created_before: Option<DateTime<Utc>>,
    pub search: Option<String>,
    pub page_size: usize,       // default 50, max 200
    pub page_token: Option<String>,
}
```

### ObjectPage

```rust
pub struct ObjectPage {
    pub objects: Vec<Object>,
    pub next_token: Option<String>,  // opaque cursor
    pub total: u64,
}
```

### ObjectEvent and ObjectEventStream

```rust
pub enum ObjectEvent {
    Created { object: Object },
    Updated { object: Object, previous_version: i64 },
    Deleted { id: ObjectId, namespace: String, object_type: String },
}

pub type ObjectEventStream = Pin<Box<dyn Stream<Item = ObjectEvent> + Send>>;
```

### Backlink

```rust
pub struct Backlink {
    pub source_id: ObjectId,
    pub source_type: String,
    pub link_name: String,
}
```

## ObjectStore Trait

```rust
#[async_trait]
pub trait ObjectStore: Send + Sync {
    // ── lifecycle ──
    async fn create(&self, input: CreateObjectInput) -> Result<Object>;
    async fn get(&self, id: ObjectId, clearance: Option<SecurityMarking>)
        -> Result<Option<Object>>;
    async fn list(&self, filter: &ObjectFilter, clearance: Option<SecurityMarking>)
        -> Result<ObjectPage>;
    async fn count(&self, filter: &ObjectFilter, clearance: Option<SecurityMarking>)
        -> Result<u64>;
    async fn update(&self, id: ObjectId, patch: ObjectPatch, expected_version: i64,
                    actor: &Actor, clearance: Option<SecurityMarking>)
        -> Result<Object>;
    async fn delete(&self, id: ObjectId, expected_version: i64,
                    actor: &Actor, clearance: Option<SecurityMarking>)
        -> Result<()>;

    // ── link traversal (unvalidated-link model) ──
    async fn resolve_links(&self, id: ObjectId, link_name: &str,
                           clearance: Option<SecurityMarking>)
        -> Result<Vec<Object>>;
    async fn backlinks(&self, id: ObjectId,
                       clearance: Option<SecurityMarking>)
        -> Result<Vec<Backlink>>;

    // ── events ──
    async fn subscribe(&self, filter: ObjectFilter) -> Result<ObjectEventStream>;
}
```

**Every backend implements the full trait.** No extension surface, no feature-flag gating, no conditional compilation. A backend that cannot support a method returns an error rather than omitting it.

**Clearance filtering:** `Some(c)` filters out objects and properties above the clearance. `None` bypasses filtering entirely — trusted server contexts pass `None`.

**Versioning:** Every write operation checks `expected_version` against the stored object's `version`. On mismatch: `VersionConflict`. On success: `version` increments, `updated_at` advances.

## File Backend

### `.onto.md` format

Identical structural pattern to `.task.md`: YAML frontmatter delimited by `---\n`, followed by Markdown body.

```
---
id: 019ad1e0-...
namespace: ami.dev
type: Feature
slug: dark-mode-toggle
marking: INTERNAL
actor: { type: User, id: ..., email: ... }
version: 3
labels: [ui, accessibility]

data:
  name: "Dark mode toggle"
  status: in_progress
  effort_estimate: "3d"
  acceptance_criteria:
    - "Toggles theme between light and dark"
    - "Persists preference in localStorage"

links:
  parent_epic: [019abc00-...]
  delivered_in: [019def00-...]
  blocked_by: [019bbb00-..., 019ccc00-...]
  srp_task: [019eee00-...]

created: 2026-05-12T14:00:00Z
updated: 2026-05-12T17:30:00Z
metadata: {}
---

Body content here...
```

### Frontmatter parsing (frontmatter.rs)

```rust
/// Splits raw file content into (frontmatter_yaml_str, body_str).
/// Returns error if file doesn't start with "---\n".
pub fn split(raw: &str) -> Result<(&str, &str), SrpError>;

/// Joins frontmatter YAML string and body string into full file content.
pub fn join(frontmatter: &str, body: &str) -> String;
```

Inherits the same strict lint rules as `.task.md` (per D-018):
- No YAML comments in frontmatter
- No ambiguous bare scalars
- Mandatory opening and closing `---` delimiters
- Unknown keys preserved on round-trip for forward compatibility

### Atomic write flow

Every file mutation follows this sequence:

```
1. Validate input (type schema, cardinality, marking clearance)
2. Build new frontmatter YAML from Object struct
3. join(frontmatter, body) → full content bytes
4. write_atomic(target_path, content_bytes):
   a. NamedTempFile::new(parent_dir)
   b. tempfile.write_all(content)
   c. tempfile.as_file().sync_all()     // fsync
   d. tempfile.persist(target_path)      // atomic rename(2)
5. Emit ObjectEvent on broadcast channel
6. (Optional) git add + git commit
```

### Lockfile protocol (opt-in)

When `OpenOptions::lockfile(true)`:

```
1. Open or create {path}.lock sidecar file
2. Acquire exclusive flock(2)
3. Re-read the .onto.md file under the lock (version may have changed)
4. Validate version
5. Write via atomic rename (the .lock sidecar's fd survives the rename)
6. Release flock on guard drop
```

### Slug uniqueness algorithm

```rust
fn check_slug_unique(dir: &Path, namespace: &str, slug: &str) -> Result<(), SlugConflict> {
    for entry in std::fs::read_dir(dir)? {
        let entry = entry?;
        if !entry.file_name().to_string_lossy().ends_with(".onto.md") {
            continue;
        }
        let raw = std::fs::read_to_string(entry.path())?;
        let (fm, _) = frontmatter::split(&raw)?;
        let existing: MinimalFrontmatter = serde_yaml_ng::from_str(fm)?;
        if existing.namespace == namespace && existing.slug.as_deref() == Some(slug) {
            return Err(SlugConflict { slug: slug.to_string(), namespace: namespace.to_string() });
        }
    }
    Ok(())
}

#[derive(Deserialize)]
struct MinimalFrontmatter {
    namespace: String,
    slug: Option<String>,
}
```

The scan reads only the minimum fields needed (namespace + slug), not the full Object. This keeps the collision check fast while staying O(n).

### Filename derivation

```
If slug is provided:  {slug}.onto.md
If slug is absent:    obj_{first-8-chars-of-id}.onto.md
```

Objects with the same slug in different namespaces produce distinct files because the collision check is per-namespace, not global. A user who wants "dark-mode" in both `ami.dev` and `ami.pmf` gets two files that happen to share a slug; the filesystem distinguishes by file content (different UUIDs, different namespaces in frontmatter).

### File-to-object mapping (read path)

```
get(id):
    for entry in read_dir(.ontology/):
        if not *.onto.md: continue
        read file → split → parse frontmatter
        if object.id == id: return object (with clearance filter)
    return None

list(filter):
    for entry in read_dir(.ontology/):
        if not *.onto.md: continue
        read file → split → parse frontmatter
        if matches filter + clearance: collect
    sort by created_at descending
    paginate
    return page
```

No index, no cache. Every read is a full directory scan. For hundreds to low thousands of objects on a modern SSD, this completes in single-digit milliseconds.

### Link traversal (unvalidated-link model)

```
resolve_links(id, link_name, clearance):
    obj = get(id)
    target_ids = obj.links[link_name]
    results = []
    for tid in target_ids:
        target = get(tid, clearance)
        if target is Some: results.push(target)
        // silently skip unresolvable targets
    return results

backlinks(id, clearance):
    results = []
    for entry in read_dir(.ontology/):
        obj = parse(entry)
        for (link_name, target_ids) in obj.links:
            if id is in target_ids:
                if clearance_check(obj.marking, clearance):
                    results.push(Backlink {
                        source_id: obj.id,
                        source_type: obj.object_type,
                        link_name,
                    })
    return results
```

Both are O(n) scans. `resolve_links` is O(n) in the target count (calls `get()` which is O(n), making it O(n × m) where m = number of targets). `backlinks` is O(n) in total objects.

## Validation Pipeline

Every `create` and `update` runs these checks in order:

### 1. Type schema validation (validate.rs)

```rust
fn validate_object(meta: &ObjectTypeMeta, data: &serde_json::Value,
                   links: &IndexMap<String, Vec<ObjectId>>,
                   actor_clearance: Option<SecurityMarking>)
    -> Result<(), Vec<ValidationError>>
{
    let mut errors = Vec::new();

    // a. Check (namespace, object_type) exists in ALL_ONTOLOGIES
    // b. For each required property: present and non-null
    // c. For each enum property: value in enum_values
    // d. For each property with a marking: actor clearance >= marking
    // e. Reject unknown properties (strict mode)
    // f. For each link name: matches a defined LinkMeta
    // g. For each link: cardinality check (array length)

    errors
}
```

### 2. Slug uniqueness (file backend only)

```rust
// On create only — slugs are immutable
check_slug_unique(dir, &input.namespace, &input.slug)?;
```

### 3. Version check (all mutators except create)

```rust
if existing.version != expected_version {
    return Err(VersionConflict {
        expected: expected_version,
        actual: existing.version,
    });
}
```

## Directory Layout

```
<project-root>/
  .ontology/
    ├── dark-mode-toggle.onto.md
    ├── product-led-growth.onto.md
    ├── seed-round-2026.onto.md
    ├── obj_019ad1e0.onto.md        # unslugged object
    ├── archive/
    │   └── .deleted/               # renamed here on delete
    ├── board.yaml                  # board config
    └── project.yaml                # project metadata, namespaces, owners
```

### project.yaml format

```yaml
name: my-startup
namespaces:
  - ami.dev
  - ami.pmf
  - ami.fundraising
owners:
  - alice@example.com
  - bob@example.com
```

### board.yaml format (optional)

```yaml
columns:
  - name: Proposed
    filter: { object_type: Feature, status: proposed }
  - name: In Progress
    filter: { object_type: Feature, status: in_progress }
  - name: Shipped
    filter: { object_type: Feature, status: shipped }
filters:
  - name: Active Features
    query: { object_type: Feature, status: [in_progress] }
  - name: Critical Bugs
    query: { object_type: Bug, severity: critical }
```

## In-Memory Backend

```rust
pub struct InMemoryObjectStore {
    objects: DashMap<ObjectId, Object>,
    events: tokio::sync::broadcast::Sender<ObjectEvent>,
}
```

- `DashMap` provides concurrent read/write with shard-level locking.
- `create` inserts into DashMap, emits `Created`.
- `get` calls `DashMap::get()`, clones, applies clearance filter.
- `list` iterates DashMap, filters in-memory, sorts by created_at, paginates.
- `update` uses `DashMap::get_mut()`, checks version, applies patch, version++, emits `Updated`.
- `delete` calls `DashMap::remove()`, emits `Deleted`.
- `resolve_links` reads from DashMap (no scan — direct ID lookup).
- `backlinks` iterates entire DashMap (same O(n) pattern as file backend but in-memory).
- `subscribe` returns a filtered receiver from the broadcast channel.

## Error Types

| Variant | When |
|---|---|
| `NotFound(ObjectId)` | `get` or `update` on nonexistent ID |
| `VersionConflict { expected, actual }` | Optimistic concurrency mismatch |
| `SlugConflict { slug, namespace }` | Duplicate slug in same namespace |
| `InvalidInput(String)` | Schema validation failure (enum mismatch, missing required, unknown property, cardinality violation) |
| `PermissionDenied` | Actor clearance insufficient for object or property marking |
| `Backend(String)` | IO error, parse error, backend-internal failure |

## File Map

| File | Purpose |
|---|---|
| `crates/srp-objects/src/object.rs` | Object, CreateObjectInput, ObjectPatch structs + serde config |
| `crates/srp-objects/src/filter.rs` | ObjectFilter, ObjectPage |
| `crates/srp-objects/src/event.rs` | ObjectEvent enum, ObjectEventStream type alias |
| `crates/srp-objects/src/validate.rs` | validate_object() — schema + marking + cardinality checks |
| `crates/srp-objects/src/id.rs` | ObjectId newtype (promote to srp-types later) |
| `crates/srp-objects/src/store/mod.rs` | ObjectStore trait definition |
| `crates/srp-objects/src/store/file/mod.rs` | FileObjectStore — open(), create(), get(), list(), update(), delete() |
| `crates/srp-objects/src/store/file/frontmatter.rs` | split() / join() for .onto.md format |
| `crates/srp-objects/src/store/file/slug.rs` | check_slug_unique() |
| `crates/srp-objects/src/store/memory/mod.rs` | InMemoryObjectStore — DashMap-backed |
| `crates/srp-store-common/src/atomic.rs` | write_atomic() (shared with srp-tasks) |
| `crates/srp-store-common/src/lock.rs` | LockfileGuard (shared with srp-tasks) |
| `crates/srp-store-common/src/discover.rs` | find_dirs_containing() (shared with srp-tasks) |
| `crates/srp-store-common/src/git.rs` | GitBackend (shared with srp-tasks) |

## Open Implementation Questions

1. **`ObjectId` location**: Currently planned in `srp-objects/src/id.rs`. Should be promoted to `srp-types` alongside `TaskId` and `ContextId` for consistency. Timing: either as a prerequisite for `srp-objects` (touches `srp-types`) or shipped within `srp-objects` and promoted later.

2. **Property-level marking enforcement**: The `validate_object()` function must check per-property markings against the actor's clearance. This requires traversing `data` as a JSON object and matching each key to the type's `PropertyMeta`. The current `srp-ontology` metadata carries `marking` on each `PropertyMeta` — the enforcement code needs to walk both in parallel.

3. **`srp-store-common` extraction order**: See REQ-OBJECT-ENGINE.md NFR-3 and Open Question 1 in the REQ doc. Either extract before `srp-objects` ships (touching `srp-tasks`) or implement with temporary copies and extract after.

4. **Watcher integration**: The file backend should support a filesystem watcher (same `notify-debouncer-full` pattern as `srp-tasks`). On external change, re-parse the file and emit an event. Deferred to a follow-up spec section.
