# Specification: AgentCI Response Moderation

**Status:** Active
**Date:** 2026-10-14
**Requirement:** `docs/requirements/REQ-AGENTCI-RESPONSE-MODERATION.md`
**Supersedes:** `docs/specifications/SPEC-OPENCODE-RESPONSE-MODERATOR.md`

## Purpose

Completion-gating for terminal Build responses: before an OpenCode agent stops,
the local MiniCPM5-1B llamafile server, reached only through the Workspace
Gateway `/llamafile` relay, decides whether the task is complete. A failure makes
the agent continue; a pass leaves the session idle. All logic is TypeScript
inside `workspace/agentci/`: no shell-out classifier, no new daemon, route, or
database.

## Module Layout

```text
workspace/agentci/src/moderation/
  types.ts       durable state, events, effects, verdicts
  config.ts      gateway-only option validation, GBNF grammar, token bounds
  machine.ts     pure dependency-free reducer (no I/O)
  context.ts     pure selection and fenced-sudo detection
  classifier.ts  Gateway token-trim + GBNF completion + strict two-line parse
  audit.ts        XDG state directory, atomic JSON document persistence
  adapter.ts      event wiring, FIFO queue per session, effect executor
workspace/agentci/src/server.ts
workspace/config/opencode/agentci/agentci.template.json
workspace/scripts/install-agentci
```

## Configuration

The plugin option configuration is validated at startup by
`resolveModerationOptions`. `gateway_url` MUST equal the Workspace Gateway relay
`http://127.0.0.1:9080/llamafile`; any other endpoint (including a direct
llamafile port) is rejected. `model` MUST be non-empty. The fixed input bound is
16,384 tokens.

Configuration is resolved from the plugin options `moderation` object. When the
plugin is auto-discovered (`plugins/agentci.js`), the installer-rendered
release-local `options.json` is the single provisioning-owned source; a missing
file is an explicit error, and no environment variable can override the endpoint.

## State Model

Durable per-session state contains only facts needed to reconstruct legal
transitions:

```text
phase                    IDLE | OBSERVING | CLASSIFYING | CONTINUING | ERROR
busyGeneration           monotonic busy counter
pendingIdleGenerations   queued idle generations
inflightAssistantID      assistant claim in progress
lastTerminalAssistantID  last moderated terminal assistant
realUserCycleID          latest real user turn id
consecutiveNoProgressCount
blocker                  null | { source, originUserID }
compaction               { active, generation }
```

`AGENT_COMPLETE`, `AGENT_BLOCKED`, `AGENT_STOPPED`, `OPERATOR_HANDOFF`, and
`ESCALATED` are
recorded outcomes in audit records, not durable phases. Blocker discussion is the
nullable `blocker` scope (`operator-handoff` or `agent-blocked`).
The reducer never retains message objects, clients, promises, or mutable
collections.

## Events, Guards, Effects

Events: `STATUS_BUSY`, `STATUS_IDLE`, `CONTEXT_LOADED`, `ROOT_BLOCK_DETECTED`,
`CLASSIFIER_RESULT`, `CLASSIFIER_FORMAT_RETRY`, `CLASSIFIER_ERROR`,
`TRACE_PERSISTED`, `CONTINUATION_PERSISTED`, `BUSY_VERIFIED`,
`CONTINUATION_TIMEOUT`, `COMPACTION_STARTED`, `COMPACTION_AUTOCONTINUE`,
`COMPACTION_COMPLETED`, `EFFECT_ERROR`.

Effects: `LOAD_CONTEXT`, `WRITE_DECISION`, `WRITE_TRACE`, `SHOW_TOAST`,
`CLASSIFY`, `SEND_CONTINUATION`, `VERIFY_PROMPT`, `WAIT_FOR_BUSY`.

The adapter executes effects in order, appends each result to the decision
evidence, and feeds the corresponding result event back into the queue. Failed
persistence, prompt, classifier, or transport operations enter `ERROR` and never
imply a pass.

## Moderation Path

1. `STATUS_BUSY` enters `OBSERVING`; the matching `STATUS_IDLE` loads context.
2. Context selection picks the newest assistant, then resolves the real
   user turn that originated it by walking `parentID` upward and skipping
   injected continuation/trace messages (chronological API ordering). This keeps
   a Build response produced in reply to an injected continuation eligible. An
   earlier turn is never re-moderated.
3. Deterministic-first filtering resolves nonterminal/tool-call finishes,
   duplicates, compaction, plan mode, non-Build agents, cancellations (an
   interrupted assistant with `info.error`, which has no `finish`, checked before
   terminality), and moderator traces with an explicit `ignored-*` decision type.
4. A fenced shell block containing `sudo` as a command token produces
   `root-handoff` (no classifier request).
5. Otherwise MiniCPM classifies. Input is the tracked todos, the last three real
   user prompts, and the latest assistant response, trimmed to 16,384 tokens via
   the Gateway token endpoint. MiniCPM is the single authority on completion:
   the todo state is classifier input, not a controller override, so a returned
   `AGENT_COMPLETE` stands even when todos remain `pending` or `in_progress`, and
   a returned `AGENT_STOPPED` (the most recent user message is an explicit halt)
   stands over unfinished work.
   Output is exactly two YAML lines enforced by the Gateway GBNF grammar;
   malformed or non-`stop` output is traced and retried three times, then
   reported as a visible classifier error. Each request pins deterministic
   greedy sampling (`temperature` 0, `top_k` 1, `top_p` 1, `min_p` 0, fixed
   seed); the serving model pins the same and runs single-slot with a fixed
   thread count, so identical inputs yield identical verdicts across runs.
6. `AGENT_COMPLETE` writes a single-line passive status (`✅ Automated Moderation:
   work completion verified.`) and stays idle. `AGENT_CONTINUING` /
   `AGENT_STALLED` send a single-line corrective status through `promptAsync`,
   marked and excluded from later real-user context. `AGENT_BLOCKED` writes a
   single-line status and activates blocker-discussion scope. `AGENT_STOPPED`
   writes no transcript line, sends no prompt, and stays idle with a toast.
7. Three consecutive `AGENT_STALLED` outcomes in one real-user cycle produce
   `moderation-escalated` (toast + audit only) and stop automatic continuation.
8. Internal outcomes (blocker discussion, escalation, error) and a user stop
   write no transcript line. Audit files hold the full verdict, rulings, reason,
   and decision ID.

## Classifier Protocol

```text
decision: AGENT_COMPLETE    reason: WORK_COMPLETE
decision: AGENT_CONTINUING  reason: WORK_REMAINS
decision: AGENT_STALLED     reason: NO_PROGRESS
decision: AGENT_BLOCKED     reason: AWAITING_USER | AWAITING_OPERATOR
decision: AGENT_STOPPED     reason: USER_STOP
```

`temperature` 0, `max_tokens` 128, `grammar` = `MODERATION_GRAMMAR`, `stream`
false. `finish_reason` MUST be `stop`.

## Audit Persistence

One atomic JSON document (valid YAML 1.2) per completed transition under
`${XDG_STATE_HOME:-$HOME/.local/state}/opencode/agentci/moderation/<sessionID>/`,
named `decision-<timestamp>-<random>.yaml`. Each record contains the event type,
decision type, guard/ignored result, previous and next phase, emitted effects,
effect results, verdict, error, and the durable state snapshot. Directories are
`0700`; files are written atomically (`0600`, temp + rename). `state.yaml`
mirrors the latest durable snapshot for restart restoration.

## Deployment

`workspace/scripts/install-agentci {install|verify|status|uninstall}` deploys an
esbuild single-file bundle plus the rendered `options.json` into
`~/.config/opencode/plugins/.agentci/releases/<id>` with an atomic `current`
symlink and a top-level `plugins/agentci.js` entry. `verify` re-reads the config
and queries the Gateway `/v1/models` endpoint to confirm the configured model is
served. Make targets: `install-agentci`, `verify-agentci`, `status-agentci`,
`uninstall-agentci`.

## Verification

- `npm test`: machine transition tests, classifier tests, context tests, audit
  tests, adapter integration tests, and the packaged release entrypoint test.
- `npm run test:release`: `npm pack` install path.
- `npm run test:live` (`make test-agentci-e2e`): real OpenCode loads the
  installed release under a temporary `HOME`/XDG root and writes moderation
  decision records; drives the build and title agents with the local MiniCPM5
  model through the Workspace Gateway's `workspace-gw-llamafile-no-auth`
  provider, pinning the title agent with `small_model` so no remote provider is
  contacted, and copies the test user's `auth.json` into the temporary data
  root. An operator may override the build model with `AGENTCI_LIVE_MODEL`.
  Excluded from hermetic CI.