# Requirements: opencode Per-Repo Database Sharding

**Document ID:** WS-REQ-OPENCODE-DB-SHARDING-v0.1
**Status:** Approved , operator decision 2026-09-17, implemented same day
**Parent Docs:** workspace/scripts/opencode-wrapper.sh, projects/opencode/packages/core/src/database/database.ts
**Last Updated:** 2026-09-17

## 1. Purpose

The monolithic `~/.local/share/opencode/opencode.db` grew to 12 GB: every
project's sessions, messages, and full tool-output JSON (`part.data`) in one
file, one FK namespace, one lock. This document specifies user-level sharding:
one sqlite DB per git repository, derived in the `oc`/`ocb` wrappers.

## 2. Decision Log (verified this session)

- Benchmarks (`/tmp/opencode/sqlite-bench-v3.sh`, opencode-realistic WAL
  workload): LUKS adds no measurable cost , encrypted nvme1n1 beat plain
  nvme0n1 4.5x on fsync churn because nvme0n1 is a QLC DRAM-less Crucial P3
  Plus (tProg 2.3ms); commit latency, not encryption, is the cost.
- Security posture: opencode DBs hold **non-redacted transcripts**; the
  Gateway database holds the redacted mirror. Therefore shards stay on the
  encrypted home , sharding must NOT relocate data to unencrypted mounts.
- Upstream seam exists: `database.ts` honors `OPENCODE_DB` (absolute path, or
  relative to the data dir). No upstream change required.
- `opencode-wrapper.sh` already plumbs explicit `--db` → `OPENCODE_DB`;
  auto-derivation runs only when the operator did not choose a DB.

## 3. Requirements

- **R1 , Automatic shard derivation.** When `OPENCODE_DB` is unset and no
  `--db` flag is given, the wrapper resolves the git toplevel of the
  invocation directory and sets `OPENCODE_DB=shard-<sha256(path)[0:16]>.db`
  (relative name → stored in the opencode data dir).
- **R2 , Explicit override wins.** A pre-set `OPENCODE_DB` or the `--db`
  flag bypasses derivation entirely.
- **R3 , Shard registry.** The wrapper appends `hash<TAB>git-root` to
  `<data-dir>/shards.tsv` (once per hash) so shards are inspectable.
- **R4 , Encrypted storage only.** Shards live under the opencode data dir in
  the home directory. The wrapper must not emit paths outside it.
- **R5 , Outside git.** When the invocation directory is not in a git
  repository, derivation is skipped and opencode's own channel-based naming
  applies.
- **R6 , Startup visibility.** The wrapper prints the chosen shard to stderr.
- **R7 , Test coverage.** Pytest coverage for: derivation inside a temp git
  repo, override preservation, registry append, non-git passthrough.
- **R8 , Runtime monolith override.** `oc --mono` / `ocb --mono` unset
  `OPENCODE_DB` for that invocation, forcing opencode's default (monolith)
  naming. `--mono` also wins over a pre-set `OPENCODE_DB`; combining `--mono`
  with `--db` is rejected with exit code 2. The decision is per-invocation,
  never persisted.

## 4. Non-Goals (v1)

- Migrating or splitting the existing 12 GB monolith (operator decision).
- Session pruning/GC of shards.
- Upstream schema or batching changes.

## 5. Acceptance Criteria

- **AC-1** Two checkouts produce two distinct `shard-*.db` files; repeated
  invocations in one checkout reuse one shard.
- **AC-2** `oc --db name` and pre-set `OPENCODE_DB` produce no auto shard.
- **AC-3** `shards.tsv` maps every auto shard hash to its git root.
- **AC-4** All shards resolve inside the encrypted home data dir.
- **AC-5** `pytest tests/unit/scripts/test_opencode_wrapper_shard.py` green.
- **AC-6** `oc --mono` launches with `OPENCODE_DB` unset (monolith) even when
  a shard would derive or `OPENCODE_DB` is pre-set; `oc --mono --db x` exits 2.
