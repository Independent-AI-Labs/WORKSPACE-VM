# A2A Remote Agent Integration — Codebase Gap Analysis

**Document ID:** AMI-GAP-A2A-v1.0
**Status:** Final
**Date:** 2026-06-01
**Target Branch:** `dev` (commit `fd2278eef`)
**PR Source Branch:** `origin/pr/feat-remote-agents` (PR #10452, closed not merged)
**Analysis By:** Codebase investigation of both branches + manual file reads

---

## 1. Executive Summary

The A2A (Agent-to-Agent) protocol integration exists as **unmerged code in a closed PR** (`origin/pr/feat-remote-agents`) that is ~5 months stale. The PR targets an older version of `opencode` that used sync/async patterns, zod schemas, and namespace exports. The current `dev` has been fully migrated to **Effect** (`Schema.Struct`, `Effect.fn`, `InstanceState`, `Context.Service`, `Layer.effect`) and has diverged significantly.

### Status Overview

| Area | PR Branch Has? | Current `dev` Has? | Action Required |
|------|---------------|-------------------|-----------------|
| `src/a2a/` module (11 files) | **Yes** — complete module | **No** | Cherry-pick + adapt to Effect patterns where needed |
| `test/a2a/` (10 files) | **Yes** — full test suite | **No** | Cherry-pick, adapt test harness to `bun:test` |
| `src/agent/agent.ts` integration | **Yes** — conflicted | **No** | Re-write against Effect-based agent.ts |
| `src/config/config.ts` schema | **Yes** — conflicted | **No** | Port to Effect Schema Info |
| `src/cli/cmd/run.ts` CLI flag | **Yes** — conflicted | **No** | Re-write in Effect handler |
| `src/tool/task.ts` remote execution | **Yes** — conflicted | **No** | Re-write against Effect-based task.ts |
| `src/permission/next.ts` (PermissionNext) | **Yes** — PR uses this | **No** — deleted; PermissionV2 in core | Re-write against PermissionV2 |
| Autocomplete `isRemoteDomain` | **Yes** — clean | **No** — not present | Cherry-pick clean (no conflicts) |
| Permission TUI `remote_agent` | **Yes** — conflicted | **No** — not present | Port to current permission.tsx |
| OAuth PKCE (plugin layer) | **No** — A2A has own impl | **Yes** — xAI + Codex plugins | Leverage existing patterns, A2A module has own impl using Bun |
| `@a2a-js/sdk` dependency | **Yes** — `0.3.9` | **No** | Add to package.json |
| EventV2 A2A event types | **No** — not in PR either | **No** | Must be written from scratch |
| EU AI Act audit logging | **No** — not in PR either | **No** | Must be written from scratch |
| Human oversight / stop button | **No** — not in PR either | **Partial** — Cancel Task exists | Minimal gap |

---

## 2. Codebase Status by Area

### 2.1 A2A Protocol Module (`src/a2a/`)

**On `dev`:** Does not exist. Zero files.

**On PR branch:** 11 source files + 1 spec doc, fully implemented against `@a2a-js/sdk@0.3.9`:

| File | Implements | Status for Porting |
|------|-----------|-------------------|
| `agent-card.ts` | Agent card fetch, parse, cache, ref parsing, OAuth detection | **Clean cherry-pick** — uses `zod` + `fetch`; no Effect dependency |
| `client.ts` | A2A SDK client wrapper, sendMessage, streamMessage, getTask, cancelTask | **Cherry-pick + minor adapt** — uses `@a2a-js/sdk/client` |
| `context.ts` | In-memory context store (sessionId:domain → contextId) | **Clean cherry-pick** — 21 lines, no deps |
| `discovery.ts` | `getDiscoverableAgentRefs`, `discoverAgents` | **Adapt** — imports `Config.get` (now Effect); no `PermissionNext` dependency; uses async/await pattern |
| `trust.ts` | `checkTrust`, `trustForSession`, `isTrusted` | **Re-write needed** — imports `PermissionNext` + `Config.get` (Effect now); uses async/await |
| `oauth/pkce.ts` | PKCE code verifier/challenge/state generation | **Clean cherry-pick** — 14 lines, uses `node:crypto` |
| `oauth/storage.ts` | Token persistence, layered user/project precedence | **Adapt** — uses `Global.Path.data` (still exists), `Instance.directory` (now `InstanceState`); `Bun.file` (fine) |
| `oauth/callback.ts` | `Bun.serve`-based callback server | **Clean cherry-pick** — uses `Bun.serve`, `Bun.connect` |
| `oauth/flow.ts` | Full OAuth flow: prepare, execute, refresh, clear | **Cherry-pick + minor adapt** — imports `open` package, `A2AAuth` (storage); uses `fetch` which is fine |
| `oauth/index.ts` | Barrel file | **Clean cherry-pick** |
| `index.ts` | Barrel file | **Clean cherry-pick** |
| `SPEC.md` | Documentation | **Clean cherry-pick** |

### 2.2 Test Files (`test/a2a/`)

**On `dev`:** Does not exist.

**On PR branch:** 10 test files. All use `bun:test` (viable on current dev):

| File | Coverage | Status for Porting |
|------|---------|-------------------|
| `agent-card.test.ts` | `parseAgentRef`, `resolveAgentCardUrl`, `fetchAgentCard`, `buildEndpointUrl` | **Clean cherry-pick** — no Effect deps |
| `client.test.ts` | `sendMessage`, `streamMessage`, `getTask`, `cancelTask`, `transformStreamEvent` | **Adapt** — mocks `@a2a-js/sdk` |
| `context.test.ts` | `getContextId`, `setContextId`, `clearContextId`, `clearAllContexts` | **Clean cherry-pick** |
| `discovery.test.ts` | `getDiscoverableAgentRefs`, `discoverAgents` | **Re-write** — mocks `Config.get` which is now Effect |
| `oauth-callback.test.ts` | `A2AOAuthCallback.ensureRunning`, `waitForCallback`, `cancelPending` | **Clean cherry-pick** |
| `oauth-flow.test.ts` | `getAccessToken`, `refreshTokens`, `prepareOAuthFlow`, `startOAuthFlow` | **Clean cherry-pick** — uses `fetch`, `open` |
| `oauth-pkce.test.ts` | `generateCodeVerifier`, `generateCodeChallenge`, `generateState` | **Clean cherry-pick** |
| `oauth-storage.test.ts` | `A2AAuth.get/set/remove/updateTokens`, layered loading | **Adapt** — uses `Bun.file`, `Global` |
| `remote-agent-oauth.test.ts` | End-to-end OAuth flow | **Adapt** — integration test |
| `trust.test.ts` | `checkTrust`, `isTrusted`, `trustForSession` | **Re-write** — mocks `Config.get` which is now Effect |

### 2.3 Integration Points (Conflicted Files)

These files exist on the PR branch with merge conflicts because the current `dev` has been refactored to Effect patterns.

| File | PR Branch Approach | Current `dev` Approach | Gap |
|------|-------------------|----------------------|-----|
| `agent/agent.ts` | async function state() returning Record<string, Info>; adds remote agents via `A2A.discoverAgents()` in `state()` | `InstanceState.make` with `Effect.fnUntraced` methods; no async/await; uses `Permission`, `Schema.Struct` | **Full re-write needed** — port A2A discovery into the `Effect.fn(...)` block inside `InstanceState.make`, referencing `cfg` from Effect `Config.Service` |
| `config/config.ts` | zod `Info` schema with `remoteAgents.domains` + `remote_agent` in permission; zod `Agent` schema | Effect `Schema.Struct` `Info` with `ConfigPermission.Info`; no zod layer | **Schema port needed** — add `remoteAgents` field to Effect `Schema.Struct` `Info`; add `remote_agent` to `ConfigPermission.Info` |
| `cli/cmd/run.ts` | `--trust-domains` option + `A2A.trustForSession()` calls in async handler | Effect-based handler (`Effect.fn("Cli.run")`) with `yield* Agent.Service`, `RuntimeFlags`, `InstanceRef` | **Re-write** — add `--trust-domains` to builder, add A2A trust calls in the effect handler |
| `tool/task.ts` | async `execute()` checks `A2A.parseAgentRef()`, has remote agent execution path | Effect-based tool with `Tool.define`, `Schema.Struct` parameters, `ctx.ask` permission | **Re-write** — port remote agent detection path into Effect-based task tool |
| `tool/task.txt` | Updated template with remote agent info | Different template | **Cherry-pick template change** |
| `permission/next.ts` | Used extensively for `PermissionNext.evaluate`, `merge`, `fromConfig` | **DELETED** — replaced by `PermissionV2` in `packages/core/src/permission.ts` | **Re-write all references** to use `PermissionV2.evaluate` and `Permission` from `@/permission` |
| `cli/cmd/tui/component/prompt/autocomplete.tsx` | Added `isRemoteDomain` + remote option | No remote support | **Cherry-pick clean** — no conflict with Effect migration |
| `cli/cmd/tui/routes/session/permission.tsx` | Added `remote_agent` display case | Permission display exists but no `remote_agent` | **Add `remote_agent` case** to permission display |

### 2.4 Dependency Status

| Dependency | PR Branch | Current `dev` | Action |
|-----------|-----------|---------------|--------|
| `@a2a-js/sdk` | `0.3.9` | Not present | Add to `packages/opencode/package.json` |
| `zod` | Used in agent-card and config | Present (used in many places) | No action (remains in use for non-Effect code) |
| `open` | Used in OAuth flow | Present (used elsewhere) | No action |
| `@agentclientprotocol/sdk` | Not present | `0.21.0` | No action (separate protocol) |

---

## 3. Per-Requirement Gap Analysis

### FR-1: Agent Discovery

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| FR-1.1 Agent Card Acquisition | Yes — `fetchAgentCard` in `agent-card.ts` | No | Full feature | Cherry-pick `agent-card.ts` |
| FR-1.2 Agent Card Validation | Yes — `AgentCardSchema` (zod) | No | Zod validation — should be ported to Effect Schema | Either keep zod for validation or re-write as Effect Schema |
| FR-1.3 Agent Card Caching | Yes — 5-min TTL cache in `agent-card.ts` | No | Caching exists but is a simple Map, not HTTP semantics | Cherry-pick as-is; HTTP caching is a nice-to-have |
| FR-1.4 Discovery Strategies | Yes — Well-Known URI + Direct Config | No | Only 2 of 3 strategies (no curated registry) | Cherry-pick + add note about missing catalog discovery |
| FR-1.5 Domain Reference Parsing | Yes — `parseAgentRef` in `agent-card.ts` | No | Full implementation with port/domain/path | Cherry-pick clean |

### FR-2: Agent Communication

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| FR-2.1 Send Message | Yes — `sendMessage` in `client.ts` | No | Wraps `@a2a-js/sdk` client | Cherry-pick + verify SDK v0.3.9 API |
| FR-2.2 Streaming | Yes — `streamMessage` async generator + `transformStreamEvent` | No | Full SSE streaming support | Cherry-pick + verify |
| FR-2.3 Multi-Turn Context | Yes — `context.ts` | No | In-memory map, keyed by sessionId:domain | Cherry-pick clean |
| FR-2.4 Task Lifecycle | Yes — `getTask`, `cancelTask` | No | Delegates to SDK | Cherry-pick |
| FR-2.5 Streaming Event Handling | Yes — `StreamEvent` type + `transformStreamEvent` | No | Converts SDK events to internal format | Cherry-pick |

### FR-3: Authentication & Authorization

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| FR-3.1 Auth Scheme Discovery | Yes — `requiresOAuth`, `getOAuthConfig` | No | Reads from Agent Card securitySchemes | Cherry-pick |
| FR-3.2 OAuth 2.0 with PKCE | Yes — full flow in `oauth/` | No (only in plugins) | Complete S256 PKCE via Bun.serve callback | Cherry-pick; note: uses Bun.serve, not Node http |
| FR-3.3 Token Refresh | Yes — `refreshTokens` in `oauth/flow.ts` | No | refresh_token grant type | Cherry-pick |
| FR-3.4 Bearer Token Injection | Yes — `createAuthHandler` in `client.ts` | No | Creates authenticating fetch wrapper | Cherry-pick + adapt to Effect HttpClient |
| FR-3.5 In-Task Auth Halt | No — not implemented on PR | No | `TASK_STATE_AUTH_REQUIRED` not handled | Must be written |

### FR-4: Trust & Permission Model

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| FR-4.1 Domain Trust Evaluation | Yes — `checkTrust` in `trust.ts` | No | Evaluates permission + session + legacy config | Re-write against PermissionV2 |
| FR-4.2 Trust Actions | Yes — allow/deny/ask | No | Three states supported | Re-write against PermissionV2 |
| FR-4.3 Session-Scoped Trust | Yes — `Set<string>` in `trust.ts` | No | In-memory Set, not persisted | Cherry-pick logic; port to Effect Ref |
| FR-4.4 Permission Configuration | Yes — `remote_agent` rules | No | Zod schema in PR, needs Effect Schema | Port to `ConfigPermission.Info` |

### FR-5: Agent Capability Representation

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| FR-5.1 Agent Card Skills | Yes — formatted in task.ts | No | Skills exposed to LLM in task tool prompt | Re-write in Effect task tool |
| FR-5.2 Text Part Exchange | Yes — client.ts handles text parts | No | Via `@a2a-js/sdk` | Cherry-pick |
| FR-5.3 Modality Negotiation | No — not explicitly checked | No | Should validate modes before sending | Must be written |
| FR-5.4 Artifact Output | Yes — artifacts in `StreamMessageResult` | No | Artifacts returned from send/stream | Cherry-pick |

### FR-6: Observability & Audit

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| FR-6.1 Task Event Recording | **No** — not implemented | No — EventV2 system exists but no A2A events | A2A events not defined | Must be written — define A2A events via EventV2 |
| FR-6.2 Distributed Trace Propagation | **No** — not implemented | Partial — OTEL for AI SDK calls only | No A2A-specific tracing | Must be written — add trace context to A2A HTTP calls |
| FR-6.3 Agent Invocation Metadata | **No** — not implemented | No | No metadata capture | Must be written — capture domain, task ID, timestamps |

### NFR-1: Performance

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| NFR-1.1 Agent Card Fetch Timeout | Yes — 10s timeout | No | Uses `AbortSignal.timeout(10000)` | Cherry-pick |
| NFR-1.2 Streaming Responsiveness | Yes — incremental SSE | No | AsyncGenerator yields events as they arrive | Cherry-pick |
| NFR-1.3 Startup Latency | Partial — discovery is async | No | On PR: called in agent registration | Re-write in Effect (fork in InstanceState) |

### NFR-2: Security

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| NFR-2.1 Transport Security | Yes — HTTPS for non-localhost | No | In `agent-card.ts` resolves to HTTPS | Cherry-pick |
| NFR-2.2 Token Storage Security | Yes — `chmod(0o600)` in storage.ts | No | File permissions set after write | Cherry-pick |
| NFR-2.3 OAuth State Validation | Yes — callback.ts validates state | No | CSRF protection via state param | Cherry-pick |
| NFR-2.4 SSRF Prevention | Partial — only `@localhost:PORT` allowed for HTTP | No | No redirect following in fetch | Enhance — validate resolved URLs |
| NFR-2.5 Deny-by-Default | Yes — `checkTrust` returns "ask" by default | No | Default action is "ask" | Re-write against PermissionV2 |

### NFR-3: Reliability

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| NFR-3.1 Graceful Degradation | Yes — discovery catches errors, logs warnings | No | In `discovery.ts` and `client.ts` | Cherry-pick error handling pattern |
| NFR-3.2 Streaming Reconnection | **No** — not implemented | No | No resubscription logic | Must be written |

### NFR-4: Scalability

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| NFR-4.1 Concurrent Invocations | Yes — agents are independent | No | No shared mutable state per invocation | Cherry-pick; Effect ensures isolation |

### NFR-5: Privacy

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| NFR-5.1 Data Minimization | **No** — not enforced | No | Sends full message, not minimized | Must be written — context filter |
| NFR-5.2 Opaque Execution Default | Yes — only declared capabilities shared | No | Per A2A spec design | Already inherent in protocol architecture |

### REG-1: EU AI Act

| Sub-req | Exists on PR? | Exists on `dev`? | Gap | Action |
|---------|---------------|------------------|-----|--------|
| REG-1.1 Automatic Logging (Art. 12) | **No** | No — EventV2 system can be extended | No A2A event types or log retention | Must be written — define A2A event types, add configurable retention (default 6-month minimum per Art. 26(6), not a cap) |
| REG-1.2 Human Oversight (Art. 14) | **No** | Partial — Cancel Task exists | No A2A-specific stop button | Must be written — wire cancel to remote agent |
| REG-1.3 Deployer Duties (Art. 26) | **No** | No | No deployer-facing suspension mechanism | Must be written |
| REG-1.4 High-Risk Awareness | **No** | No | No classification documentation | Must be written |
| REG-1.5 Transparency (Art. 13) | Partial — "(remote)" in autocomplete | No | Agent name/domain shown | Extend — ensure domain displayed during interaction |

### REG-2 through REG-6

| Req | Exists on PR? | Exists on `dev`? | Action |
|-----|---------------|------------------|--------|
| REG-2 GDPR Art. 22 | **No** | No | Ensure human review pathway documented |
| REG-3 ISO 42001 Alignment | **No** | No | Config persistence already in place; A2A needs documented info |
| REG-4 OWASP LLM01/LLM06 | **No** | No — but Evaluate already checks "deny" | Validate remote output, bound scope |
| REG-5 DORA/NIS2 | **No** | No | Flag invocation failures as incidents |
| REG-6 Data Residency | **No** | No | Domain origin awareness for GDPR Art. 44-49 |

---

## 4. Detailed Rewrite Guidance

### 4.1 `agent/agent.ts` — Remote Agent Registration

**Current `dev` pattern** (lines 93-467):
```typescript
export const layer = Layer.effect(
  Service,
  Effect.gen(function* () {
    const config = yield* Config.Service
    // ...
    const state = yield* InstanceState.make<State>(
      Effect.fn("Agent.state")(function* (ctx) {
        const cfg = yield* config.get()
        // Build agents Record<string, Info> ...
        // Expose get, list, defaultInfo, defaultAgent
      }),
    )
    return Service.of({
      get: Effect.fn("Agent.get")(function* (agent: string) { ... }),
      // ...
    })
  }),
)
```

**What needs to change:** Inside the `Effect.fn("Agent.state")` closure after building the local agents map and before returning `{ get, list, defaultInfo, defaultAgent }`:

```typescript
// After user-configured agent merge + before the get/list/... return:

// Discover remote agents from config
const discovered = yield* Effect.promise(() => A2A.discoverAgents())
for (const { ref, card, requiresAuth } of discovered) {
  const name = `@${ref}`
  agents[name] = {
    name,
    description: card.description + (requiresAuth ? " (requires auth)" : ""),
    mode: "subagent",
    native: false,
    hidden: false,
    permission: Permission.merge(defaults,
      Permission.fromConfig({ remote_agent: "allow" }),
      user,
    ),
    options: {
      remote: true,
      ref,
      agentCard: card,
      requiresAuth,
    },
  }
}
```

**Key differences from PR version:**
- Uses `yield* Config.Service` instead of `await Config.get()`
- Uses `Permission.fromConfig` (not `PermissionNext.fromConfig`)
- Uses `Permission.merge` (not `PermissionNext.merge`)
- Discovery runs inside `Effect.fn(...)` not in an async function
- Should be non-blocking: forked via `Effect.forkScoped` in the layer if startup latency is a concern

### 4.2 `config/config.ts` — Schema Changes

**Add to Effect Schema `Info`** (within lines 135-310, before the closing `}).annotate({ identifier: "Config" })`):

```typescript
remoteAgents: Schema.optional(
  Schema.Struct({
    domains: Schema.optional(Schema.mutable(Schema.Array(Schema.String))).annotate({
      description: "List of trusted domains for remote agents",
    }),
  }),
).annotate({ description: "Configuration for remote subagents accessible via @domain.com syntax" }),
```

**Add `remote_agent` to `ConfigPermission.Info`:**

The permission config schema is in `packages/opencode/src/config/permission.ts`. Need to verify if there's an explicit key list or if it uses catchall. From the investigation, `ConfigPermission.Info` uses `Record<string, Rule>` with catchall — meaning `remote_agent` would be accepted as a catchall key without explicit schema changes. Confirm with the file.

### 4.3 `cli/cmd/run.ts` — CLI Flag

**Builder:** Add to the `yargs.options` chain in the `builder`:

```typescript
.option("trust-domains", {
  type: "string",
  array: true,
  describe: "domains to auto-trust for remote agents (e.g., localhost:3000)",
})
```

**Handler:** Inside the `Effect.fn("Cli.run")` handler, before the main execution:

```typescript
// Trust domains for A2A remote agents
if (args.trustDomains) {
  for (const domain of args.trustDomains) {
    yield* Effect.promise(() => A2A.trustForSession(domain))
  }
}
```

### 4.4 `tool/task.ts` — Remote Agent Execution

The current `dev` task tool uses `Tool.define("task", ...)` with Effect-based patterns. The remote agent execution path needs to:

1. Check if `subagent_type` matches a remote agent ref (has `options.remote === true`)
2. If remote: fetch auth tokens, create A2A client, send message, stream response back
3. Handle OAuth `AuthenticationRequiredError` by prompting user

The PR's `task.ts` has most of this logic but in async/await style. The Effect port needs to:
- `yield* Effect.promise(...)` around A2A SDK calls
- Handle `AuthenticationRequiredError` as a typed error
- Stream A2A responses through the session's event system

### 4.5 `permission/next.ts` → `PermissionV2` Migration

The PR branch used `PermissionNext` from `src/permission/next.ts`. This module has been deleted and replaced by `PermissionV2` from `packages/core/src/permission.ts`.

| PR branch (`PermissionNext`) | Current `dev` (`PermissionV2` / `@/permission`) |
|------------------------------|------------------------------------------------|
| `PermissionNext.evaluate(perm, pattern, rules)` | `PermissionV2.evaluate(perm, pattern, ...rulesets)` or `Permission.evaluate(perm, pattern, ...rulesets)` |
| `PermissionNext.merge(rulesets)` | `Permission.merge(...rulesets)` or `PermissionV2.merge(...rulesets)` |
| `PermissionNext.fromConfig(cfg)` | `Permission.fromConfig(cfg)`¹ |

¹ `fromConfig` is defined locally in `packages/opencode/src/permission/index.ts:292`, not exported from core's `PermissionV2`. Use `import { fromConfig } from "../permission"`.


### 4.6 `discovery.ts` — Effectification

The PR's `discovery.ts` uses:
```typescript
export async function getDiscoverableAgentRefs(): Promise<string[]> {
  const config = await Config.get()
  // ...
}
```

Needs to become:
```typescript
// Option A: Accept config as parameter (preferred for testability)
export function getDiscoverableAgentRefs(cfg: Config.Info): string[] { ... }

// Option B: Accept Effect Config service
export function getDiscoverableAgentRefs(): Effect.Effect<string[]> {
  return Effect.gen(function* () {
    const cfg = yield* Config.Service
    // ... return refs
  })
}
```

### 4.7 `trust.ts` — Effectification

Same pattern as discovery. The `sessionTrusted` Set becomes an `Effect.Ref` or stays module-level (simple enough to stay module-level since it's process-scoped). `checkTrust` takes an Effect config dependency.

---

## 5. New Code That Must Be Written (Not in PR)

The following requirements have **zero implementation** in either the PR branch or `dev`:

### 5.1 A2A Event Types for Observability (FR-6.1)

Following the pattern in `packages/core/src/session/event.ts`:

```typescript
// File: packages/core/src/a2a/event.ts (new)
export const RemoteTaskStarted = EventV2.define({
  type: "a2a.task.started",
  sync: true, // Durable for audit
  schema: {
    domain: Schema.String,
    remoteTaskId: Schema.String,
    localSessionID: SessionID,
    agentName: Schema.String,
    inputSummary: Schema.String, // Truncated input
  },
})

export const RemoteTaskCompleted = EventV2.define({ ... })
export const RemoteTaskFailed = EventV2.define({ ... })
export const RemoteTaskCanceled = EventV2.define({ ... })
export const RemoteTaskAuthRequired = EventV2.define({ ... })

export const RemoteAgentDiscovered = EventV2.define({ ... })
export const RemoteAgentAuthSucceeded = EventV2.define({ ... })
export const RemoteAgentAuthFailed = EventV2.define({ ... })
```

These need to be published from the A2A client/discovery code using `yield* EventV2Bridge.Service`.

### 5.2 EU AI Act Log Retention (REG-1.1)

The EventV2 `sync: true` events are already persisted in SQLite via `EventTable`. Current retention is unbounded — this satisfies Art. 26(6) (requires **at least** 6 months, minimum floor not cap). The gap is deployer-configurable retention for GDPR Art. 5(1)(e) storage limitation: if logs contain personal data, deployers need a retention boundary.

**What this needs — one config field + one DELETE query:**

```typescript
// In Effect Schema Info (config.ts):
eventRetentionDays: Schema.optional(PositiveInt).annotate({
  description: "Auto-delete events older than this (days). Default: undefined (keep forever). GDPR Art. 5(1)(e) compliance."
})

// In a startup/prune effect:
const days = cfg.eventRetentionDays
if (days) {
  const cutoff = new Date(Date.now() - days * 86400000)
  yield* db.delete(EventTable)
    .where(lt(EventTable.created_at, cutoff.getTime()))
}
```

No storage engines, no log rotation daemon, no SIEM export, no archive format. The gap is one config value and one periodic SQL DELETE. Per WS-7: configurable 3–24 months, default 6, but this is deployer policy — the code only needs to support it.

### 5.3 Human Oversight Stop Button (REG-1.2)

Current `cancelTask` in the PR uses the A2A protocol cancel. This needs to be wired to the session's interrupt mechanism so that cancel/stop interrupts remote agent execution too.

### 5.4 Data Minimization / Context Filter (NFR-5.1)

The PR sends the full message to remote agents. Need a filter that strips sensitive information and limits context to the minimum required.

### 5.5 Modality Negotiation (FR-5.3)

Before sending a message, check the Agent Card's `defaultInputModes` and `defaultOutputModes` and validate that the message parts match.

### 5.6 Streaming Reconnection (NFR-3.2)

If the SSE stream disconnects mid-task, call `SubscribeToTask` to re-establish. Not implemented in the PR.

---

## 6. Cherry-Pick Strategy

### 6.1 Files to Cherry-Pick Clean (No Changes Needed)

```bash
# A2A module - no Effect dependencies, standalone
git checkout origin/pr/feat-remote-agents -- \
  packages/opencode/src/a2a/context.ts \
  packages/opencode/src/a2a/oauth/pkce.ts \
  packages/opencode/src/a2a/oauth/callback.ts \
  packages/opencode/src/a2a/index.ts \
  packages/opencode/src/a2a/oauth/index.ts \
  packages/opencode/src/a2a/SPEC.md

# Tests - standalone, no Effect dependencies
git checkout origin/pr/feat-remote-agents -- \
  packages/opencode/test/a2a/context.test.ts \
  packages/opencode/test/a2a/oauth-pkce.test.ts \
  packages/opencode/test/a2a/oauth-callback.test.ts

# Autocomplete - standalone UI change, no merge conflicts
git checkout origin/pr/feat-remote-agents -- \
  packages/opencode/src/cli/cmd/tui/component/prompt/autocomplete.tsx
```

### 6.2 Files to Cherry-Pick + Minor Adapt

```bash
# agent-card.ts - uses zod (fine), needs no Effect adaptation
git checkout origin/pr/feat-remote-agents -- \
  packages/opencode/src/a2a/agent-card.ts

# client.ts - uses @a2a-js/sdk, needs no Effect adaptation
git checkout origin/pr/feat-remote-agents -- \
  packages/opencode/src/a2a/client.ts

# oauth/storage.ts - uses Bun.file (fine), Instance.directory -> InstanceState
git checkout origin/pr/feat-remote-agents -- \
  packages/opencode/src/a2a/oauth/storage.ts

# oauth/flow.ts - uses fetch (fine), open package
git checkout origin/pr/feat-remote-agents -- \
  packages/opencode/src/a2a/oauth/flow.ts

# Tests - need mock adaptation from Config.get() to Effect.Config
git checkout origin/pr/feat-remote-agents -- \
  packages/opencode/test/a2a/agent-card.test.ts \
  packages/opencode/test/a2a/client.test.ts \
  packages/opencode/test/a2a/oauth-storage.test.ts \
  packages/opencode/test/a2a/oauth-flow.test.ts \
  packages/opencode/test/a2a/remote-agent-oauth.test.ts
```

### 6.3 Files to Re-Write Entirely

```bash
# Must be re-written against PermissionV2 + Effect
# discovery.ts - reference the PR version for logic, re-write Effect API
# trust.ts - reference the PR version for logic, re-write Effect API
# trust.test.ts - reference for test cases, re-write mocks
# discovery.test.ts - reference for test cases, re-write mocks

# Must be manually ported (conflicted files)
# agent/agent.ts - port remote agent registration block
# config/config.ts - port remoteAgents + remote_agent schema
# cli/cmd/run.ts - port --trust-domains + A2A init
# tool/task.ts - port remote execution path
# tool/task.txt - port template change
# permission/next.ts references - replace with PermissionV2
```

### 6.4 Files That Must Be Written From Scratch

```bash
# Event definitions
packages/core/src/a2a/event.ts

# Task event recorder
packages/opencode/src/a2a/event-recorder.ts

# Context filter for data minimization
packages/opencode/src/a2a/context-filter.ts

# Streaming reconnection handler
packages/opencode/src/a2a/reconnect.ts

# Tests for new code
packages/opencode/test/a2a/event-recorder.test.ts
packages/opencode/test/a2a/context-filter.test.ts
```

---

## 7. Dependency Changes

Add to `packages/opencode/package.json`:

```json
{
  "dependencies": {
    "@a2a-js/sdk": "^0.3.9"
  }
}
```

---

## 8. Verification Checklist

After integration, the following must be verified:

- [ ] `bun test` passes from `packages/opencode/` (all existing + new A2A tests)
- [ ] `bun typecheck` passes from `packages/opencode/`
- [ ] A2A tests can run independently: `bun test test/a2a/`
- [ ] Agent card fetching works for `@domain.com` (existing agent cards in test fixtures)
- [ ] OAuth flow completes with PKCE (mock token endpoint)
- [ ] Session trust persists for the duration of a session
- [ ] Trust evaluation: session > permission config > legacy config > ask
- [ ] Remote agents appear in `@` autocomplete with description
- [ ] Task tool can delegate to remote agents
- [ ] `--trust-domains` CLI flag works
- [ ] A2A events are published through EventV2 bridge
- [ ] Token storage has `chmod 0600` permissions
- [ ] EU AI Act audit events: task started/completed/failed are logged with metadata
- [ ] Cancel task successfully interrupts remote agent execution
- [ ] Expired tokens trigger refresh flow
- [ ] Streaming events are delivered incrementally

---

## 9. Quick Reference: Key File Paths

| File | Current `dev` Path |
|------|-------------------|
| Agent service | `packages/opencode/src/agent/agent.ts` |
| Config schema | `packages/opencode/src/config/config.ts` |
| Config permission | `packages/opencode/src/config/permission.ts` |
| Permission service | `packages/opencode/src/permission/index.ts` |
| PermissionV2 (core) | `packages/core/src/permission.ts` |
| CLI run handler | `packages/opencode/src/cli/cmd/run.ts` |
| Task tool | `packages/opencode/src/tool/task.ts` |
| Autocomplete TUI | `packages/opencode/src/cli/cmd/tui/component/prompt/autocomplete.tsx` |
| Permission TUI | `packages/opencode/src/cli/cmd/tui/routes/session/permission.tsx` |
| EventV2 definitions | `packages/core/src/session/event.ts` (pattern) |
| EventV2Bridge | `packages/opencode/src/event-v2-bridge.ts` |
| A2A target dir | `packages/opencode/src/a2a/` (does not exist on `dev` — exists only on PR branch) |
| OAuth plugin (xAI) | `packages/opencode/src/plugin/xai.ts` (PKCE reference) |
| OAuth plugin (Codex) | `packages/opencode/src/plugin/openai/codex.ts` (PKCE reference) |
| Auth storage | `packages/opencode/src/auth/index.ts` |
| HTTP retry utility | `packages/opencode/src/util/effect-http-client.ts` |
| OpenTelemetry | `packages/core/src/effect/observability.ts` |
| InstanceState | `packages/opencode/src/effect/instance-state.ts` |
