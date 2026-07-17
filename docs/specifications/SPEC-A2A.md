# SPEC-A2A: A2A Remote Agent Integration Implementation

**Date:** 2026-07-17
**Status:** Draft
**Type:** Specification
**Requirements:** [REQ-A2A](../requirements/REQ-A2A.md)

> Intended design for the A2A client integration mandated by REQ-A2A. Not
> implemented: the only prior art is the closed, unmerged PR #10452
> (`origin/pr/feat-remote-agents`), which targets a pre-Effect opencode
> codebase and cannot be cherry-picked wholesale. Key invariant: remote agent
> output is untrusted input; no local state, memory, or tools are shared.

---

**Cross-references:**
- [REQ-A2A](../requirements/REQ-A2A.md): requirements contract
- [GAP-ANALYSIS-A2A](../audits/GAP-ANALYSIS-A2A.md): per-area action plan against PR #10452

---

## 1. Overview

An `a2a` module added to the opencode fork provides:

1. **Discovery**: Agent Card fetch from `https://{domain}/.well-known/agent-card.json`
   with ETag/If-Modified-Since caching (REQ FR-1).
2. **Client**: JSON-RPC 2.0 Send Message / Send Streaming Message / Get Task /
   Cancel Task / Subscribe to Task, with SSE event handling (REQ FR-2).
3. **Auth**: OAuth 2.0 Authorization Code + PKCE against schemes declared in
   the Agent Card, token storage at mode 0600, automatic refresh (REQ FR-3).
4. **Trust**: `remote_agent` permission rules evaluated session-first, then
   config, with default `"ask"` (REQ FR-4).
5. **Audit**: JSONL record of every invocation satisfying EU AI Act Art. 12
   logging fields (REQ REG-1.1).

## 2. Architectural Principles

### 2.1 Opaque execution

The local agent MUST NOT expose internal state, memory, tools, or system
prompt to remote agents (A2A §1.2). All remote output passes validation
before any local processing (OWASP LLM01).

### 2.2 Deny-by-default trust

Unknown domains resolve to `"ask"`. No auto-discovery or auto-invocation
without explicit consent or config (REQ NFR-2.5).

### 2.3 Effect-native implementation

New code MUST follow the current `dev` patterns (`Schema.Struct`,
`Effect.fn`, `InstanceState`, `Context.Service`, `Layer.effect`). The closed
PR's sync/async and zod patterns MUST be rewritten, not ported verbatim.

## 3. System Diagram

```
user -> opencode agent -> a2a module
                            |-- discovery (agent-card fetch + cache)
                            |-- trust evaluator (session -> config -> ask)
                            |-- oauth pkce (browser + 127.0.0.1 callback)
                            |-- json-rpc client (http + sse)
                            +-- audit log (jsonl, art. 12 fields)
```

## 4. Gap-to-Action Map

Per [GAP-ANALYSIS-A2A](../audits/GAP-ANALYSIS-A2A.md): cherry-pick the PR's
`src/a2a/` module and autocomplete `isRemoteDomain` where clean; rewrite
`agent.ts`, `config.ts`, `run.ts`, `task.ts`, and permission integration
against Effect and PermissionV2; add `@a2a-js/sdk` `0.3.9` dependency.

## 5. Edge Cases & Decisions

| Case | Decision |
|------|----------|
| SSE stream breaks mid-task | Resubscribe via `SubscribeToTask` (A2A §3.5.2) |
| `TASK_STATE_AUTH_REQUIRED` | Halt task, surface to user, resume after out-of-band credential |
| Agent Card redirect to `file://`/localhost | Reject (SSRF prevention, REQ NFR-2.4) |
| Empty `A2A-Version` header | Assume protocol 0.3 client (A2A §3.6.2); implementation targets v1.0 |

## 6. File Map

| File | Purpose | Key Changes |
|------|---------|-------------|
| `src/a2a/` (planned) | A2A client module | New; adapt from closed PR |
| `src/permission/` (planned) | `remote_agent` rules | Rewrite against PermissionV2 |
| `src/config/` (planned) | Trusted domain config | Port to Effect Schema |

## 7. Implementation Status

| Component | Status | Evidence |
|-----------|--------|----------|
| Discovery module | Not implemented | No `src/a2a/` on `dev` |
| JSON-RPC/SSE client | Not implemented | Closed PR only |
| OAuth PKCE flow | Not implemented | PR has own impl; xAI/Codex plugin patterns preferred |
| Trust/permission integration | Not implemented | PermissionV2 rewrite required |
| Audit log | Not implemented | - |
| Test suite (`test/a2a/`) | Not implemented | PR suite needs `bun:test` harness adaptation |
