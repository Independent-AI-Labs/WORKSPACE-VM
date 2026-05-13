# Specification: Ontology Types & Codegen (`srp-ontology`)

**Date:** 2026-05-12
**Status:** ACTIVE
**Type:** Specification
**Requirements:** [REQ-ONTOLOGY.md](../projects/AMI-SRP/docs/requirements/REQ-ONTOLOGY.md)

## Overview

The `srp-ontology` crate is the single source of truth for AMI-SRP's ontology layer: what object types exist, what fields they carry, what security markings apply to which properties, how objects connect via typed links, and what writeback actions are permitted. It ships as a library crate with a companion binary crate (`srp-ontology-codegen`) that reads a `const` metadata registry and generates schema artifacts in YAML and TypeScript.

## Crate Layout

```
crates/
├── srp-ontology/
│   ├── Cargo.toml              # deps: serde, serde_json, uuid, chrono, srp-types
│   └── src/
│       ├── lib.rs              # re-exports, pub mod types, pub mod registry, pub mod meta
│       ├── meta.rs             # Meta type definitions (ObjectTypeMeta, PropertyMeta, etc.)
│       ├── development/
│       │   ├── mod.rs          # pub use types::*; pub use objects_a::*; etc.
│       │   ├── types.rs        # Rust structs + enums for 7 dev types
│       │   ├── objects_a.rs    # SPRINT_META → RELEASE_META (4 const ObjectTypeMeta)
│       │   ├── objects_b.rs    # BUG_META → DEPLOYMENT_META (3 const ObjectTypeMeta)
│       │   └── actions.rs      # DEV_ACTIONS + DEV_ONTOLOGY
│       ├── pmf/
│       │   ├── mod.rs
│       │   ├── types.rs        # Rust structs + enums for 7 PMF types
│       │   └── meta.rs         # 7 const ObjectTypeMeta, PMF_ACTIONS, PMF_ONTOLOGY, macros
│       └── fundraising/
│           ├── mod.rs
│           ├── types.rs        # Rust structs + enums for 9 fundraising types
│           └── meta.rs         # 9 const ObjectTypeMeta, FUNDRAISING_ACTIONS, FUNDRAISING_ONTOLOGY, macros
│
├── srp-ontology-codegen/
│   ├── Cargo.toml              # deps: serde, serde_json, serde_yaml_ng, clap, srp-ontology, srp-types
│   └── src/
│       ├── main.rs             # CLI: clap Parser + Subcommand dispatch
│       ├── generate.rs         # gen_yaml(), yaml_object_type(), yaml_action(), gen_rust(), cmd_generate()
│       ├── typescript.rs       # gen_typescript() — produces TS interfaces + LINK_MAP
│       ├── list.rs             # cmd_list() — tabular overview of ontologies
│       ├── show.rs             # cmd_show(), find_type(), find_incoming_links()
│       ├── markings.rs         # cmd_markings() — MLS taxonomy
│       └── helpers.rs          # marking_str_opt(), to_camel(), ts_type_for(), namespace_for()
```

### File length constraint

Every source file under 512 lines (AMI-CI limit). The development ontology is split across 5 files because its 7-type metadata footprint exceeds the limit when combined. The pmf and fundraising ontologies fit in 2 files each (types + meta). The codegen binary is split across 7 modules.

## Metadata Type Definitions

The `meta.rs` module defines the descriptor types that every ontology constant uses. These types live in `crate::meta` and are consumed by both the registry constants and the codegen binary.

```rust
// crates/srp-ontology/src/meta.rs

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Cardinality {
    OneToOne,    // serde: one_to_one
    OneToMany,   // serde: one_to_many
    ManyToOne,   // serde: many_to_one
    ManyToMany,  // serde: many_to_many
}

#[derive(Debug, Clone)]
pub struct PropertyMeta {
    pub name: &'static str,              // YAML-facing name (snake_case)
    pub rust_name: &'static str,         // Rust struct field name
    pub type_label: &'static str,        // DSL type: string, int32, enum, json, etc.
    pub required: bool,
    pub enum_values: Option<&'static [&'static str]>,  // must match serde wire format
    pub marking: Option<SecurityMarking>,
    pub default: Option<&'static str>,
}

#[derive(Debug, Clone)]
pub struct LinkMeta {
    pub name: &'static str,
    pub target: &'static str,
    pub cardinality: Cardinality,
    pub properties: Option<&'static [&'static str]>,
}

#[derive(Debug, Clone)]
pub struct TimeSeriesMeta {
    pub name: &'static str,
    pub unit: &'static str,
    pub retention: &'static str,
    pub marking: Option<SecurityMarking>,
}

#[derive(Debug, Clone)]
pub struct ObjectTypeMeta {
    pub name: &'static str,
    pub description: &'static str,
    pub properties: &'static [PropertyMeta],
    pub links: &'static [LinkMeta],
    pub time_series: &'static [TimeSeriesMeta],
}

#[derive(Debug, Clone)]
pub enum SideEffectMeta {
    Event { name: &'static str },
    Webhook { url: &'static str },
    Notification { channel: &'static str, target: &'static str },
}

#[derive(Debug, Clone)]
pub struct ActionMeta {
    pub name: &'static str,
    pub target: &'static str,
    pub description: &'static str,
    pub parameters: &'static [PropertyMeta],
    pub validation: &'static [&'static str],
    pub approval_required: bool,
    pub approvers: Option<&'static [&'static str]>,
    pub side_effects: &'static [SideEffectMeta],
}

#[derive(Debug, Clone)]
pub struct OntologyMeta {
    pub namespace: &'static str,
    pub display_name: &'static str,
    pub description: &'static str,
    pub object_types: &'static [ObjectTypeMeta],
    pub actions: &'static [ActionMeta],
}
```

## Defining Object Types

Object types are defined using two mechanisms in each domain module:

### 1. Rust structs with serde derives (types.rs)

Every ontology type has a corresponding Rust struct with proper enum fields:

```rust
// crates/srp-ontology/src/development/types.rs
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum FeatureStatus {
    Proposed,
    Accepted,
    InProgress,
    Done,
    Shipped,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Feature {
    pub id: Uuid,
    pub name: String,
    pub description: Option<String>,
    pub spec_url: Option<String>,
    pub status: FeatureStatus,   // typed enum, not free-form string
    pub effort_estimate: Option<String>,
    pub acceptance_criteria: Option<Vec<String>>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
    pub created_by: Actor,
}
```

**Enum wire format rule:** All enums use `#[serde(rename_all = "snake_case")]`. The metadata `enum_values` array MUST match the serde output byte-for-byte. Example: `FeatureStatus::InProgress` serializes to `"in_progress"`, so the metadata enum_values entry is `"in_progress"`. A mismatch (e.g. `"in-progress"` or `"InProgress"`) causes validation failures at the object storage layer.

### 2. Const metadata for codegen (meta.rs / objects_*.rs)

Two approaches are used depending on the ontology's size:

**Small ontologies (pmf, fundraising):** Macros reduce boilerplate. Each macro variant explicitly names all optional fields to avoid Rust 2024 const-evaluation issues with `Option::or()`:

```rust
macro_rules! prop {
    // Base: no enum, no marking, no default
    ($name:literal, $rust:literal, $type:literal, $req:literal) => { ... };
    // With enum values
    ($name:literal, $rust:literal, $type:literal, $req:literal, enum: [$($v:literal),+]) => { ... };
    // With marking
    ($name:literal, $rust:literal, $type:literal, $req:literal, marking: $mk:expr) => { ... };
    // enum + marking
    ($name:literal, $rust:literal, $type:literal, $req:literal, enum: [$($v:literal),+], marking: $mk:expr) => { ... };
    // ... 8 variants total covering all combinations of (enum, marking, default)
}
```

**Large ontologies (development, 7 types):** Full explicit `PropertyMeta` structs to avoid file length issues with macro expansion:

```rust
pub const SPRINT_META: ObjectTypeMeta = ObjectTypeMeta {
    name: "Sprint",
    description: "A time-boxed development iteration...",
    properties: &[
        PropertyMeta {
            name: "name",
            rust_name: "name",
            type_label: "string",
            required: true,
            enum_values: None,
            marking: None,
            default: None,
        },
        // ...
    ],
    links: &[...],
    time_series: &[...],
};
```

Both approaches produce the same `&[ObjectTypeMeta]` constants. The choice is aesthetic: macros for smaller, repetitive ontologies; explicit struct construction for larger ones that would exceed the 512-line limit.

## Registry

`lib.rs` aggregates all ontology meta constants into a single `const` slice:

```rust
// crates/srp-ontology/src/lib.rs
pub mod registry {
    pub const ALL_ONTOLOGIES: &[OntologyMeta] = &[
        DEV_ONTOLOGY,
        PMF_ONTOLOGY,
        FUNDRAISING_ONTOLOGY,
    ];
}
```

This is a `const`, not `static`. Every consumer reads it at compile time with zero runtime initialization cost. Adding a new ontology requires:
1. Create domain module with types + metadata
2. Add `pub const NEW_ONTOLOGY: OntologyMeta = ...` in that module
3. Append it to the `ALL_ONTOLOGIES` slice
4. Re-export types in `crate::types`

## Codegen Binary

The `srp-ontology-codegen` binary links against `srp-ontology` directly — no proc macros, no source parsing, no `syn`. It calls `srp_ontology::registry::ALL_ONTOLOGIES` at runtime and iterates the metadata.

### CLI architecture

```
cargo run --bin srp-ontology-codegen -- <command>

Commands:
  generate       Write YAML + TypeScript + Rust to disk
  list           Tabular overview of all ontologies
  list --actions Flat list of 18 writeback actions
  show <Type>    Properties, links, time-series for one type
  show <Type> --links --actions  Full graph context with inbound references
  markings       MLS 5-level taxonomy table
```

The CLI uses `clap` derive macros. Subcommand dispatch lives in `main.rs` (86 lines). Each subcommand handler is in its own module.

### How `generate` works

```
cmd_generate(root, &ontologies)
    │
    ├── For each OntologyMeta:
    │   └── gen_yaml(ont) → schemas/ontologies/{namespace}.yaml
    │       ├── Object types loop → yaml_object_type()
    │       └── Actions loop → yaml_action()
    │
    ├── gen_typescript(ontologies) → src/generated/ontology.ts
    │   ├── Type preamble (SecurityMarking, Actor, Cardinality types)
    │   ├── Object type interfaces (23) with marking annotations
    │   ├── Actions namespace (18 Params + 18 Result interfaces)
    │   └── LINK_MAP: Record<string, Array<{from, link, to, cardinality}>>
    │
    └── gen_rust(ontologies) → crates/srp-ontology/src/generated.rs
        └── Minimal header pointing to crate::types
```

### Generated YAML schema format

```yaml
# Development Lifecycle
# ...
# Auto-generated from srp-ontology. DO NOT EDIT.
# Schema version: 1.0.0
# SRP compat: MLS markings per SecurityMarking enum

ontology:
  namespace: ami.dev
  display_name: "Development Lifecycle"
  description: > ...
  object_types:
    Sprint:
      description: > ...
      properties:
        name: { type: string, required: true }
        status: { type: enum, required: true, values: ["planned", "active", "completed", "cancelled"] }
        priority: { type: string, marking: INTERNAL }
      time_series:
        velocity: { unit: story_points, retention: 2y }
      links:
        contains_feature: { target: Feature, cardinality: one_to_many }
    ...
  actions:
    ShipRelease:
      target: Release
      description: "Promote a release candidate to production"
      parameters:
        release_id: { type: uuid, required: true }
      validation:
        - release.status == 'candidate'
        - release.built_from.build.status == 'succeeded'
      approval: { required: true, approvers: ["release_owner"] }
      side_effects:
        - event: ReleaseShipped
        - notification: { channel: matrix, room: engineering }
```

### Generated TypeScript format

```typescript
import type { UUID } from '@ami/srp-types';  // published by srp-tasks-napi

export type SecurityMarking = 'PUBLIC' | 'INTERNAL' | 'CONFIDENTIAL'
    | 'RESTRICTED' | 'TOP_SECRET';

export type Actor = { type: 'User'; id: UUID; email: string; name?: string }
  | { type: 'Agent'; id: string; provider: string; model: string }
  | { type: 'System'; component: string }
  | { type: 'External'; service: string; reference: string };

// ami.dev — A time-boxed development iteration...
export interface Sprint {
  id: UUID;
  _type: 'Sprint';
  _namespace: 'ami.dev';
  name: string;
  status: 'planned' | 'active' | 'completed' | 'cancelled';
  priority?: string;  // [INTERNAL]
  created_at: string;
  updated_at: string;
  created_by: Actor;
}
// ... 22 more interfaces

export namespace Actions {
  export interface ShipReleaseParams { ... }
  export interface ShipReleaseResult { success: boolean; action_id: UUID; ... }
  // ... 35 more param/result pairs
}

export const LINK_MAP: Record<string, Array<{
  from: string; link: string; to: string; cardinality: Cardinality;
}>> = { ... };
```

Field names are camelCased from the metadata `rust_name` using the `to_camel()` helper. Security markings appear as trailing `// [LEVEL]` comments on affected properties.

## File Map

| File | Purpose |
|---|---|
| `crates/srp-ontology/src/meta.rs` | Metadata type definitions (108 lines) |
| `crates/srp-ontology/src/lib.rs` | Re-exports, `pub mod registry` with `ALL_ONTOLOGIES` (38 lines) |
| `crates/srp-ontology/src/development/types.rs` | 7 dev type structs + enums with serde (214 lines) |
| `crates/srp-ontology/src/development/objects_a.rs` | SPRINT_META → RELEASE_META (378 lines) |
| `crates/srp-ontology/src/development/objects_b.rs` | BUG_META → DEPLOYMENT_META (274 lines) |
| `crates/srp-ontology/src/development/actions.rs` | DEV_ACTIONS (5) + DEV_ONTOLOGY (250 lines) |
| `crates/srp-ontology/src/pmf/types.rs` | 7 PMF type structs + enums (259 lines) |
| `crates/srp-ontology/src/pmf/meta.rs` | PMF macros, 7 ObjectTypeMeta, PMF_ACTIONS, PMF_ONTOLOGY (368 lines) |
| `crates/srp-ontology/src/fundraising/types.rs` | 9 fundraising type structs + enums (310 lines) |
| `crates/srp-ontology/src/fundraising/meta.rs` | Fundraising macros, 9 ObjectTypeMeta, FUNDRAISING_ACTIONS, FUNDRAISING_ONTOLOGY (462 lines) |
| `crates/srp-ontology-codegen/src/main.rs` | CLI structs + dispatch (86 lines) |
| `crates/srp-ontology-codegen/src/generate.rs` | gen_yaml, yaml_object_type, yaml_action, cmd_generate (226 lines) |
| `crates/srp-ontology-codegen/src/typescript.rs` | gen_typescript — TS interface + namespace + LINK_MAP generation (114 lines) |
| `crates/srp-ontology-codegen/src/list.rs` | cmd_list — tabular overview (62 lines) |
| `crates/srp-ontology-codegen/src/show.rs` | cmd_show, find_type, find_incoming_links (148 lines) |
| `crates/srp-ontology-codegen/src/markings.rs` | cmd_markings — MLS taxonomy table (25 lines) |
| `crates/srp-ontology-codegen/src/helpers.rs` | marking_str_opt, to_camel, ts_type_for, namespace_for (68 lines) |

Generated artifacts (gitignored):
| File | Purpose |
|---|---|
| `schemas/ontologies/ami_dev.yaml` | Dev ontology YAML schema |
| `schemas/ontologies/ami_pmf.yaml` | PMF ontology YAML schema |
| `schemas/ontologies/ami_fundraising.yaml` | Fundraising ontology YAML schema |
| `src/generated/ontology.ts` | 23 interfaces + 36 action types + LINK_MAP |
| `src/generated/index.ts` | Barrel export |
| `crates/srp-ontology/src/generated.rs` | Generated header (points to `crate::types`) |

## Type Mapping Reference

### DSL types → Rust → TypeScript

| DSL type_label | Rust field type | TS output |
|---|---|---|
| `string` | `String` | `string` |
| `string_list` | `Vec<String>` | `string[]` |
| `int32` | `i32` | `number` |
| `int64` | `i64` | `number` |
| `float64` | `f64` | `number` |
| `boolean` | `bool` | `boolean` |
| `date` | `NaiveDate` / `String` | `string` |
| `datetime` | `DateTime<Utc>` / `String` | `string` |
| `uuid` | `Uuid` | `string` (UUID) |
| `uuid_list` | `Vec<Uuid>` | `string[]` |
| `enum` | Typed Rust enum | Union literal (`'a' \| 'b'`) |
| `json` | `serde_json::Value` | `Record<string, unknown>` |
| `geo_point` | — (future) | `{ lat: number; lng: number }` |

### Cardinality → constraint

| Metadata variant | Serde wire | Constraint |
|---|---|---|
| `Cardinality::OneToOne` | `one_to_one` | Array length = 1 |
| `Cardinality::OneToMany` | `one_to_many` | Array length ≥ 1 |
| `Cardinality::ManyToOne` | `many_to_one` | Array length ≤ 1 |
| `Cardinality::ManyToMany` | `many_to_many` | No constraint |

## Adding a New Ontology

1. Create `crates/srp-ontology/src/{domain}/` directory with `mod.rs`, `types.rs`, `meta.rs`.
2. Define Rust structs and enums in `types.rs` with `#[derive(Serialize, Deserialize)]` and `#[serde(rename_all = "snake_case")]` on enums.
3. Define `ObjectTypeMeta` constants in `meta.rs` — enum values MUST match serde wire format.
4. Define `ActionMeta` array and a top-level `{DOMAIN}_ONTOLOGY: OntologyMeta` constant.
5. Add `mod {domain};` to `lib.rs` and append `{DOMAIN}_ONTOLOGY` to the `ALL_ONTOLOGIES` slice.
6. Re-export types in `pub mod types { pub use crate::{domain}::*; }`.
7. Run `make ontology-generate` to produce YAML, TypeScript, and Rust generated artifacts.
