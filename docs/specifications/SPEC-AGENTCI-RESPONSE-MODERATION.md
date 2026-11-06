# Specification: Standalone Response Moderator

**Status:** Draft
**Date:** 2026-11-04
**Requirement:** `docs/requirements/REQ-AGENTCI-RESPONSE-MODERATION.md`
**Supersedes:** All earlier revisions of this specification

## 1. Purpose

This specification defines the standalone moderator prototype.

The prototype lives at `workspace/moderator/`. It does not import or modify
`workspace/agentci/`. It exposes the OpenCode plugin hook surface that the
production plugin can later use.

The prototype SHALL implement this specification. Refinements discovered during
implementation SHALL update both documents.

## 2. Package Layout

```text
workspace/moderator/
  package.json
  tsconfig.json
  src/
    types.ts          shared state, event, effect, verdict types
    fsm.ts            pure reducer
    context.ts        message selection and classifier input
    classifier.ts     in-process LLM.generate caller
    prompt.ts         classifier system prompt
    config.ts         runtime model configuration
    model-select.ts   shared model selector persistence
    audit.ts          state and audit persistence
    adapter.ts        event wiring, effect execution, and replay
    cli.ts            replay command entry point
    server.ts         OpenCode server plugin entry point
    tui.ts            OpenCode TUI plugin entry point
  tests/
    fixtures/classifier-cases.json
    fsm.test.ts
    context.test.ts
    classifier.test.ts
    adapter.integration.test.ts
    replay.integration.test.ts
    server.test.ts
```

`package.json` exports `./server` and `./tui`.

No file in `src/` may import from `workspace/agentci/`.

## 3. Interfaces

### 3.1 Plugin Entry Point

`src/server.ts` exports one default object.

```text
id: "moderator-server"
server(input, options) -> OpenCode hooks
```

The returned hooks contain:

- `event`
- `experimental.session.compacting`
- `experimental.compaction.autocontinue`

### 3.2 OpenCode Client

The adapter consumes the client supplied by the plugin host.

Required methods:

- `session.messages`
- `session.todo`
- `session.prompt`
- `session.promptAsync`
- `session.revert`
- `session.list`
- `tui.showToast`

The adapter defines local TypeScript interfaces for these methods. It does not
import production moderation types.

### 3.3 Classifier Port

The classifier port has one operation.

```text
classify(models, input) -> ClassifierOutcome
```

`ClassifierOutcome` contains:

- `verdict` or `undefined`
- `error` or `undefined`
- `capture` with selector, attempts, and duration

The classifier port imports `LLM.generate` and calls it in-process.

It does not spawn a process.

It does not create a session.

It does not start a server.

It does not write to an OpenCode database.

### 3.4 TUI Entry Point

`src/tui.ts` exports one TUI plugin with id `moderator-tui`.

The TUI plugin registers the `/moderator` command.

The command opens the OpenCode model picker and writes the chosen selector to the
shared model selection source.

### 3.5 Model Selection Port

The model selection port has three operations.

```text
readModels() -> ModelSelector[]
writeModels(models) -> void
replaceTopModel(selector) -> void
```

The port validates selectors through the OpenCode provider and model registry.

### 3.6 Audit Port

The audit port has three operations.

```text
readState(sessionID) -> unknown | null
writeState(sessionID, state) -> void
appendRecord(sessionID, record) -> void
```

## 4. Runtime Configuration

The installer default is written to the user-configurable runtime source.

```json
{
  "models": [
    {
      "providerID": "workspace-gw-opencode-go-api-key",
      "modelID": "gpt-5.6-luna"
    }
  ]
}
```

The runtime reads only:

```text
$XDG_CONFIG_HOME/opencode/moderator/models.json
```

The installer seeds that file from `models.template.json` when absent.

Rules:

- `models` MUST be a non-empty ordered array.
- Each entry MUST have a non-empty `providerID`.
- Each entry MUST have a non-empty `modelID`.
- The first entry is the top moderator model.
- The default top selector MUST resolve to `gpt-5.6-luna`.
- Every selector MUST exist in the OpenCode provider and model registry.
- The installer validates selectors against the rendered configuration.
- The runtime validates selectors against the live registry at startup.
- The runtime MUST NOT call provider APIs directly.
- The runtime MUST NOT read provider credentials.
- Missing runtime source is an explicit startup error.
- Invalid runtime source is an explicit startup error.
- Startup validates each selector through `client.provider.list()`.
- The CLI validates each selector against the OpenCode config provider blocks.
- The CLI accepts `opencode.json` and `opencode.jsonc`.
- The CLI strips comments and trailing commas before parsing.

The plugin reads this file at startup and reloads it when it changes.

`/moderator` replaces only the first entry and updates the in-memory list.

`oc --set-mod` and `oc --set-mod-list` replace the full list.

The installed release is never edited.

### 4.1 Installer

The installer MUST:

- Build the bundle from source with `npm run build`.
- Install dependencies with `npm ci`.
- Render `models.json` from `models.template.json`.
- Copy the classifier prompt.
- Create a versioned release directory.
- Verify bundle, runtime source, and prompt presence.
- Verify each selector against the rendered OpenCode provider and model
  configuration.
- Register both the server and TUI plugin entries.
- Activate the release through an atomic symlink change.
- Compare the installed bundle and runtime source with the source on verify.
- Refuse to replace non-moderator plugin entries.

A failed build, failed model check, or failed verification MUST fail the install.

### 4.2 Model Selection Command

The TUI plugin registers `/moderator` through `api.command.register`.

The command opens `api.ui.DialogSelect`.

The options come from `api.state.provider`.

The chosen selector replaces only the first entry in
`$XDG_CONFIG_HOME/opencode/moderator/models.json`.

The remaining entries stay in order.

The write is atomic.

The in-memory selector list is updated before the next moderation call.

A toast confirms the new top selector.

### 4.3 CLI Model Selection

The CLI supports:

```text
oc --set-mod <provider>/<model>[,<provider>/<model>...]
oc --set-mod-list <provider>/<model>[,<provider>/<model>...]
```

The two flags are aliases.

Both replace the full selector list.

Both validate every selector before writing.

Empty input, an invalid selector, or a duplicate selector fails without writing.

A successful write prints the new list.

## 5. State Model

State is durable per session.

```text
phase                    IDLE | OBSERVING | CLASSIFYING | CONTINUING | ERROR
inflightAssistantID      assistant under moderation
lastTerminalAssistantID  last moderated terminal assistant
realUserCycleID          current real user message identity
consecutiveNoProgressCount
blocker                  null | { source, originUserID }
compactionActive         boolean
pendingContext           null | ContextFact
```

`ContextFact` contains:

```text
assistantID
userMessageID
agentMode
todosOpen
```

Rules:

- The state contains no client objects, promises, or message objects.
- State is validated before every transition.
- Invalid state produces `moderation-error`.
- Restore clears `inflightAssistantID` and `pendingContext`.
- Restore sets `phase` to `IDLE`.
- Restore clears `compactionActive`.
- Restore keeps `lastTerminalAssistantID` unless it belongs to an unfinished
  classification.
- Duplicate suppression uses `lastTerminalAssistantID` only.
- `inflightAssistantID` marks an in-flight classification. It is not a duplicate.
- A verdict applies only to the assistant identity that produced it.

## 6. Events

| Event | Accepted phases | Meaning |
|---|---|---|
| `STATUS_BUSY` | all | session started work |
| `TURN_ENDED` | `OBSERVING` | terminal assistant facts are available |
| `CONTEXT_LOADED` | `OBSERVING` | context load completed |
| `VERDICT` | `CLASSIFYING` | classifier returned a verdict |
| `CANCELLED` | `CLASSIFYING`, `CONTINUING` | user superseded the work |
| `CONTINUATION_PERSISTED` | `CONTINUING` | corrective prompt is durable |
| `NEW_USER_CYCLE` | all | real user started a new cycle |
| `COMPACTION_STARTED` | all | compaction began |
| `COMPACTION_COMPLETED` | all | compaction finished |
| `TRACE_PERSISTED` | all | transcript status is durable |
| `EFFECT_ERROR` | all | an effect failed |
| `REPLAY` | `IDLE`, `ERROR` | explicit replay classifies without a busy event |

Events outside their accepted phase produce `ignored-outside-phase`.
The phase does not change. The audit `reason` is `outside-phase`.

`NEW_USER_CYCLE` writes `new-user-cycle`.
`CANCELLED` writes `cancelled`.

Eligibility is checked on `CONTEXT_LOADED` and `REPLAY`.
One flag, one decision, no toast, no classifier call.
First match wins:

| Flag | Decision | Audit reason |
|---|---|---|
| not terminal | `ignored-nonterminal` | `nonterminal` |
| assistant error | `ignored-assistant-error` | `assistant-error` |
| plan mode | `ignored-plan-mode` | `plan-mode` |
| compaction | `ignored-compaction` | `compaction` |
| newer real user | `ignored-newer-user` | `newer-user` |
| moderator trace | `ignored-moderator-trace` | `moderator-trace` |
| same `lastTerminalAssistantID` | `ignored-duplicate` | `duplicate` |

A null real-user ancestor does not match a row.
A continuation reply is a normal next turn.

## 7. Effects

| Effect | Executor |
|---|---|
| `LOAD_CONTEXT` | read messages and todos |
| `CLASSIFY` | call the classifier port |
| `SEND_CONTINUATION` | send corrective prompt through `promptAsync` |
| `VERIFY_PROMPT` | confirm the corrective prompt is persisted |
| `WRITE_TRACE` | send one status line through `prompt` with `noReply` |
| `WRITE_DECISION` | append audit record |
| `SHOW_TOAST` | call `tui.showToast` |

Effects execute in order.

An effect failure produces `EFFECT_ERROR`.

`EFFECT_ERROR` sets phase `ERROR` and writes a visible error decision.

## 8. Adapter Flow

### 8.1 Busy

1. Receive `session.status` with `busy`.
2. Validate the session identity.
3. Increment the session generation.
4. Abort an in-flight classification.
5. Enqueue `STATUS_BUSY`.

### 8.2 Idle

1. Receive `session.status` with `idle`.
2. Load messages and todos.
3. Select the newest moderated assistant.
4. Build a `TurnFact`:
   - `assistantID`
   - `finish`
   - `errorName`
   - `agent`
   - `mode`
   - `summary`
   - `syntheticModeration`
   - `policyBlocked`
   - `blockerDiscussion`
5. Resolve the real user ancestor.
6. Enqueue `NEW_USER_CYCLE` when the real user identity changed.
   - `branchOfBlocker` is true when the new user belongs to the blocker branch.
7. Enqueue `TURN_ENDED`.

### 8.3 Context Load

1. `LOAD_CONTEXT` loads the target assistant and todos.
2. Verify the assistant identity still matches `inflightAssistantID`.
3. Build `ContextFact`.
4. Enqueue `CONTEXT_LOADED`.

### 8.4 Classification

1. `CLASSIFY` reloads messages and todos.
2. Verify the target assistant is still newest, terminal, and error-free.
3. Verify no newer real user message exists.
4. Verify the session generation did not change.
5. A null real-user ancestor does not skip `CLASSIFY`.
6. Build classifier input.
7. Call the classifier port with an abort signal.
8. Enqueue `VERDICT`.
9. On abort, enqueue `CANCELLED`.
10. On error, enqueue `EFFECT_ERROR`.

### 8.5 Continuation

1. `SEND_CONTINUATION` sends one message with two parts:
   - synthetic directive
   - visible note
2. Both parts carry `metadata.moderation = true`.
3. The adapter records the created message identity.
4. Enqueue `CONTINUATION_PERSISTED`.
5. `VERIFY_PROMPT` polls the session until the directive is visible.
6. A missing prompt after the timeout produces `EFFECT_ERROR`.

### 8.6 Trace

1. `WRITE_TRACE` sends one passive status line with `noReply`.
2. The adapter records the created message identity.
3. Moderator message identities are excluded from real user context.
4. Enqueue `TRACE_PERSISTED`.

### 8.7 Compaction

1. `experimental.session.compacting` enqueues `COMPACTION_STARTED`.
2. `session.compacted` enqueues `COMPACTION_COMPLETED`.
3. `experimental.compaction.autocontinue` enqueues
   `COMPACTION_COMPLETED`.
4. Compaction does not change the real-user cycle.

## 9. Context Derivation

### 9.1 Assistant Selection

Select the newest assistant message in chronological order.

Include plan, compaction, and empty text.
Eligibility names the skip. The selector does not hide it.

### 9.2 Real User Selection

Walk `parentID` from the assistant upward.

Skip:

- injected moderator continuations
- moderator status lines
- synthetic moderation parts
- synthetic compaction notes
- summary messages
- messages outside the branch

Reject a parent cycle with an explicit error.

### 9.3 Prompts

Collect real user prompts in the current cycle.

Return the continue sentinel for an empty or whitespace-only latest prompt.

### 9.4 Tool Activity

Collect completed and failed tool parts on the current branch.

Format each entry as `<tool>:<status>`.

Keep at most 20 entries from the current cycle.

### 9.5 Agent Mode Messages

The adapter appends one mode message for a moderated response.

```text
build   The agent is in build mode.
answer  The agent is answering a user question.
```

Mode messages are context only.

They never override a verdict.

Plan and compaction responses are excluded before classification.

### 9.6 Plan Mode

Plan mode is true when:

- `info.agent == "plan"`, or
- `info.mode == "plan"`

### 9.7 Compaction

Compaction is true when:

- `info.summary == true`, or
- `info.agent == "compaction"`, or
- `info.mode == "compaction"`

### 9.8 Root Block

Detect a fenced shell-like code block.

A root block is present when a `sudo` command token appears inside that block.

A `sudo` mention in normal prose is not a root block.

## 10. Classifier

### 10.1 Generate Call

The classifier imports `LLM.generate` and calls it once per selector in the same process.

It does not spawn `bun` or any other process.

The selector is `provider/model` from `models.json`.

The provider block in `opencode.jsonc` supplies `baseURL` and headers.

The OpenCode auth store supplies that provider's key.

The call sets `x-opencode-session` to the working session id so the gateway can route it.

That header does not create a session.

There is no moderator URL variable.

`opencode run` is not used. It creates a session.

The request carries the selected route, the system prompt, the case state, and one verdict tool.

The tool schema allows only the six legal decision and reason pairs.

The system prompt includes one exact tool-call example.

A text reply is a format failure.

The call writes no session and no transcript.

The verdict is stored only in `decisions.jsonl`.

### 10.2 Selector Order

The runtime tries selectors in list order.

A valid verdict stops the list.

A prompt or format failure moves to the next selector.

A timeout moves to the next selector. After the list is exhausted, a timeout
starts another cycle. `MODERATOR_TIMEOUT_CYCLES` is the cycle limit. The
default is 3. A format failure does not start another cycle.

When every selector is exhausted, the runtime fails closed with a moderation
error.

The runtime never reports completion after an exhausted list.

The audit records the selector, attempts, and model response identity.

### 10.3 Prompt

The system prompt is an ordered procedure.

1. Operator handoff.
2. User handoff.
3. User stop.
4. Complete.
5. Continuing.
6. Stalled.

The prompt contains short examples for:

- operator handoff with a report request
- user decision question
- complete work
- remaining work
- no progress
- user stop
- self-answered question
- next command left to the operator

The prompt states that the assistant response is the decision target.

The prompt states that an empty user message is a continue sentinel.

The prompt does not end with a continue instruction.

### 10.4 Input Layout

The user message contains these sections in order.

1. `The agent's latest response (judge this):` followed by the assistant text
   collected on the backward walk
2. `Tool calls:` name, input, and truncated output for each call on that walk
3. `User request(s):` the chained real user messages that ended the walk
4. `Tracked todos:` the todo list at classification time
5. the mode message for the response agent mode

The tool and todo sections are omitted when empty.

### 10.5 Context Bound

The walk starts at the judged assistant response and follows `parentID` links
backward. It does not use the flat session list.

Injected moderator notes, synthetic compaction continues, and summary messages
are skipped. They do not end the walk and they are not chained user text.

The walk keeps every assistant message and tool call until the first real user
message. It then keeps immediately preceding real user messages when no
assistant message sits between them. It does not keep assistant messages from
before that chain.

`MODERATOR_TOOL_OUTPUT_CHARS` truncates each tool output. The default is 1024.
The cut is marked. The judged assistant text is not truncated.

`MODERATOR_CTX` is the token limit. The default is 32768. The counted text is
the system prompt plus the sections above. The estimate is `ceil(chars / 4)`
until a tokenizer is wired.

Over the limit, context selection throws. The classifier is not called. No
verdict is emitted. The adapter shows a toast and writes one
`Automated Moderation:` line into the working session with `noReply: true`.

### 10.6 Verdict Tool

The plugin exposes one verdict tool.

Accepted arguments:

```text
decision: AGENT_COMPLETE | AGENT_CONTINUING | AGENT_STALLED | AGENT_BLOCKED | AGENT_STOPPED
reason: WORK_COMPLETE | WORK_REMAINS | NO_PROGRESS | AWAITING_USER | AWAITING_OPERATOR | USER_STOP
```

Only the six valid pairs are accepted.

The parser reads the completed `moderator_verdict` tool part.

It reads `state.input` and requires exactly `decision` and `reason`.

The parser does not read assistant text as a verdict.

The parser rejects:

- missing tool call
- extra arguments
- invalid decision
- invalid reason
- mismatched pair

### 10.7 Selector Failover

Failover order is defined in 10.2.

OpenCode owns transport retries.

The adapter never converts an exhausted list to `AGENT_COMPLETE`.

### 10.8 Timeout

Each classifier prompt has a 30 second timeout.

A timeout is a prompt failure.

A timeout is recorded with its attempt and selector.

## 11. Control Policy

| Verdict | Transcript | Prompt | Toast | State |
|---|---|---|---|---|
| checking | none | none | checking | classifying |
| `AGENT_COMPLETE` | one status line | none | complete | idle |
| `AGENT_CONTINUING` | one status line | corrective | continuing | continuing |
| `AGENT_STALLED` | one status line | corrective | continuing | continuing |
| `AGENT_BLOCKED` | one status line | none | blocked | idle with blocker |
| `AGENT_STOPPED` | none | none | stopped | idle |
| `root-handoff` | one status line | none | operator handoff | idle with blocker |
| `blocker-discussion` | none | none | none | idle with blocker |
| `moderation-escalated` | none | none | escalated | idle |
| `moderation-error` | none | none | error | error |

### 11.1 Status Lines

```text
✅ Automated Moderation: work completion verified.
⚠️ Automated Moderation: work appears unfinished; continue unless explicitly requested to halt by the operator or the system.
❔ Automated Moderation: awaiting user input.
⏹️ Automated Moderation: halt acknowledged; automation stood down.
```

The operator-handoff line comes from `operator.txt`.

### 11.2 Escalation

`AGENT_CONTINUING` resets the no-progress count.

`AGENT_STALLED` increments the no-progress count.

At a count of three in one cycle, the moderator stops automatic continuation and
records `moderation-escalated`.

A new real user message resets the count.

### 11.3 Mode Messages

The adapter appends the mode message defined in 9.5.

The classifier verdict stands unchanged.

`AGENT_BLOCKED` stands in every mode.

### 11.4 Blockers

A `root-handoff` or `AGENT_BLOCKED` stores the blocker origin.

A later response in that branch records `blocker-discussion` without a
classifier call.

A response outside the branch clears the blocker.

An `AGENT_COMPLETE` in the blocker branch clears the blocker.

## 12. Audit Persistence

The state directory is:

```text
$XDG_STATE_HOME/moderator/sessions/<sessionID>/
```

It contains:

```text
state.json
decisions.jsonl
```

`state.json` is written atomically through a temporary file and rename.

`decisions.jsonl` is append-only.

Each audit record contains:

```text
timestamp
schemaVersion
sessionID
assistantID
event
decision
reason
previousPhase
nextPhase
ignored
verdict
capture
error
effects
effectResults
previousState
stateSnapshot
```

Audit records do not contain credentials.

`decision` is the specific name. `reason` is the verdict reason code or the eligibility flag. Do not write a bare `ignored`.

## 13. Replay

The replay commands are:

```text
oc --run-mod [sessionID]
oc --run-mod-force [sessionID]
```

`oc --run-mod` and `oc --run-mod-force` open that session in the working OpenCode process.

`server()` registers hooks and returns. It does not start a server.

Replay reads `session.messages` from that process. Opening the session starts the replay. An already idle session does not emit `session.status` idle, so that event is not the trigger.

The replay flow:

1. Select the newest terminal assistant from the client message list.
2. `--run-mod` reverts the moderator trace after that assistant. `--run-mod-force` does not.
3. Enqueue `REPLAY` from `IDLE` or `ERROR`. Do not synthesize `STATUS_BUSY`. Call `LLM.generate` in-process.
4. Apply section 8.5 or 8.6. Continuation is one `promptAsync` with two parts, both carrying `metadata.moderation`.
5. Append a `REPLAY` audit record.

A failure shows a toast and writes an audit error. It does not write a verdict line.

## 14. Entry Points

The server entry point:

1. Reads the user-configurable runtime model source.
2. Registers live moderation hooks.
3. Creates the audit store.
4. Creates the `LLM.generate` classifier.
5. Creates the adapter.
6. Returns the hooks.

The TUI entry point:

1. Reads the OpenCode provider and model registry.
2. Registers `/moderator`.
3. Opens the model picker.
4. Persists the chosen selector at index zero.

Startup fails when the runtime source is missing or invalid.

## 15. Test Plan

### 15.1 Unit

- every state transition
- every rejected event
- every effect list
- every verdict branch
- escalation
- mode message does not override a verdict
- blocker scope
- compaction
- state validation
- restore normalization
- context selection
- root-block detection
- classifier parse and selector failover
- verdict tool schema
- verdict parser reads tool input only
- classifier writes no OpenCode session
- selector validation through `client.provider.list()`
- CLI JSONC comment stripping
- replay uses `LLM.generate`

### 15.2 Integration

Drive the adapter with an in-memory OpenCode client.

Verify:

- continuation persistence
- trace persistence
- duplicate suppression
- stale context cancellation
- user cancellation
- tool-call ignore records `ignored-nonterminal`
- assistant error records `ignored-assistant-error`
- blocker discussion
- compaction
- audit records
- state snapshots
- session-lifetime audit retention

### 15.3 Transcript end to end

Load every body in `tests/fixtures/`.

Feed each body through `createModeratorAdapter` as an idle turn.

Use the real in-process `generateWithLLM`.

Pass fixture todos through the adapter client.

The suite is 100 cases. Every case has one expected decision and one expected reason.

That expected pair is the only score.

A classifier-only scorer is not this test.

### 15.4 Replay

Run a real transcript through the replay command.

Verify the verdict, effects, and audit record.

### 15.4 Live End-to-End

Run the installed prototype with a real OpenCode session and the configured
model.

Verify:

- a passing response stays idle
- a failing response continues
- a blocked response stays idle
- a user stop stays idle
- audit records are written

### 15.5 Optional Classifier Evidence

The audited 50-case fixture MAY be run for information.

It is not part of acceptance.

It is not an integration test.

It is not an end-to-end test.

### 15.6 Model Selection

Verify:

- `/moderator` registers and opens the model picker
- picker selection replaces index zero only
- lower selectors remain unchanged
- selection persists across restart
- selection applies to the next moderation call
- selector file reload on change
- `oc --set-mod` and `oc --set-mod-list` are aliases
- comma-separated parsing
- full-list replacement
- invalid selector rejection
- duplicate selector rejection
- empty list rejection
- atomic write
- installed release remains unchanged

## 16. Migration

1. Build and test `workspace/moderator/`.
2. Add `workspace/scripts/install-moderator`.
3. Add `workspace/config/opencode/moderator/models.template.json`.
4. Add the TUI plugin entry and `/moderator` command.
5. Add `oc --set-mod` and `oc --set-mod-list`.
6. Replace the production moderation hook with the new server entry point.
7. Delete the old adapter, context, classifier, audit, replay, and prompt files.
8. Delete `workspace/agentci/src/moderation/machine.ts`.
9. Delete the old moderation tests.
10. Delete the old moderation fixtures.
11. Update documentation references.
12. Commit once.

There is no parity comparison with the old implementation.

The old implementation is broken and is not a behavior oracle.

A failed migration MUST be reported. It SHALL NOT be hidden by keeping both
implementations active.

## 17. Resolved Decisions

- Audit records are retained for the session lifetime.
- No automatic purge runs.
- Session deletion removes the session audit directory.
- The policy plugin keeps the AgentCI name and `agentci.js` entry.
- The moderation plugin is named `moderator`.
- The server entry is `moderator.js`.
- The TUI entry is `moderator-tui.js`.
- The runtime model source stays under `moderator/` to keep selection separate.

## 18. Implementation Choices

- The classifier imports `LLM.generate` and calls it in-process.
- The classifier does not spawn a process.
- The classifier does not create a session.
- The classifier does not start a server.
- The classifier does not write an OpenCode database.
- Control traces still use the plugin client on the working session.
- Audit records live in `decisions.jsonl`.
- Replay is `oc --run-mod` or `oc --run-mod-force` in the working OpenCode process.
- Replay classifies with `LLM.generate`.
