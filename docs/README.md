<p align="center">AMI Workspace Docs</p>
<p align="center">Architecture notes, migration plans, and postmortems for the AMI workspace.</p>

<p align="center">
  <a href="https://github.com/Independent-AI-Labs/AMI-AGENTS/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-green?style=flat-square" /></a>
</p>

---

### Architecture

- [`ARCH-AGENT-ECOSYSTEM.md`](ARCH-AGENT-ECOSYSTEM.md) — target agent ecosystem: containers, gateway, A2A
- [`RUST-TRADING-ARCHITECTURE.md`](RUST-TRADING-ARCHITECTURE.md) — Rust trading stack layout
- [`DEPENDENCY-MAP.md`](DEPENDENCY-MAP.md) — cross-repo dependency graph for the workspace
- [`architecture/PROPOSAL-MERKLE-CONSOLIDATION.md`](architecture/PROPOSAL-MERKLE-CONSOLIDATION.md) — collapse duplicate Merkle implementations
- [`architecture/PROPOSAL-SHARED-PORTAL-LIB.md`](architecture/PROPOSAL-SHARED-PORTAL-LIB.md) — extract shared portal primitives
- [`architecture/PROPOSAL-ZK-ERROR-UNIFICATION.md`](architecture/PROPOSAL-ZK-ERROR-UNIFICATION.md) — unify ZK error taxonomy

For requirements docs (`requirements/REQ-*.md`) and full specifications (`specifications/SPEC-*.md`), browse those folders directly. Each doc carries its own status header.

### Migration plans

- [`../projects/docs/MOON-MIGRATION-PLAN.md`](../projects/docs/MOON-MIGRATION-PLAN.md) — workspace orchestrator migration to moon

### Incident postmortems

- [`AUDIT-CLAUDE-SESSION-2026-04-17.md`](AUDIT-CLAUDE-SESSION-2026-04-17.md) — agent session audit, 2026-04-17
- [`AUDIT-INSTALL-ISSUES.md`](AUDIT-INSTALL-ISSUES.md) — bootstrap and install issues with remediation status
- [`archive/AUDIT-REMEDIATION-2026-Q1.md`](archive/AUDIT-REMEDIATION-2026-Q1.md) — Q1 2026 architectural debt cycle
- [`archive/AUTH-FRAGMENTATION-AUDIT.md`](archive/AUTH-FRAGMENTATION-AUDIT.md) — six fragmented auth systems, prerequisite for the OIDC spec

### Guides

- [`GUIDE-USAGE.md`](GUIDE-USAGE.md) — getting started, install, configuration overview

### Adding docs here

Drop new docs in the right folder: `architecture/` for proposals, `requirements/` for `REQ-*` docs, `specifications/` for `SPEC-*` docs, `archive/` once a doc is superseded. Top-level slots are reserved for cross-cutting indices, postmortems, and guides. Add the new file to this README under the matching section so you do not strand it. Each doc starts with a header declaring **Date**, **Status** (`DRAFT` / `ACTIVE` / `DEPRECATED`), and **Type**.

---

**License** MIT
