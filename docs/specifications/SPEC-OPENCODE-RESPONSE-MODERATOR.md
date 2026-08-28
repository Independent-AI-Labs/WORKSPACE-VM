# Specification: OpenCode Response Moderator

**Document ID:** WS-SPEC-OPENCODE-RESPONSE-MODERATOR-v1.6  
**Status:** Approved implementation design - checklist-free terminal-response policy
**Date:** 2026-08-10  
**Requirements:** [REQ-OPENCODE-RESPONSE-MODERATOR](../requirements/REQ-OPENCODE-RESPONSE-MODERATOR.md)

## Deployment Design

The moderator has one repository-owned installation path. The `oc` wrapper
starts OpenCode only; it does not install or update moderator files.

The tracked source release contains:

```text
workspace/config/opencode/plugins/local-response-moderator.js
workspace/config/opencode/plugins/local-response-moderator-machine.js
workspace/config/opencode/plugins/local-response-moderator.sh
workspace/config/opencode/plugins/local-response-moderator.template.json
```

OpenCode discovers only direct `plugins/*.js` entries. The installer therefore
maintains one stable top-level entry and atomically switches its release target:

```text
${XDG_CONFIG_HOME:-$HOME/.config}/opencode/plugins/local-response-moderator.js
  -> .local-response-moderator/current/local-response-moderator.js

${XDG_CONFIG_HOME:-$HOME/.config}/opencode/plugins/.local-response-moderator/
  releases/<release-id>/{local-response-moderator.js,local-response-moderator-machine.js,local-response-moderator.sh,config.json}
  current -> releases/<release-id>
```

The installer renders the configuration template into each release. It atomically
switches `current` only after validating the complete release. OpenCode loads
the top-level entry, while the adapter resolves the classifier and rendered
configuration relative to its release directory. It does not depend on
workspace source paths after installation.

The existing `llamafile-minicpm5-1b.service` and Gateway
`relay-llamafile` route remain unchanged.

### Installer Lifecycle

One repository-aware installer owns all moderator deployment operations. Make
targets delegate to it:

```text
make install-opencode-moderator
make verify-opencode-moderator
make status-opencode-moderator
make uninstall-opencode-moderator
```

The installer determines the repository root from its own script location, not
the caller's working directory. It resolves the destination with
`XDG_CONFIG_HOME`, allowing isolated installations without changing `$HOME`.

Install performs these steps in order:

1. Load and validate the tracked configuration template.
2. Reject an endpoint outside the Workspace Gateway `/llamafile` relay.
3. Validate the canonical source adapter and classifier, including `bash -n`.
4. Query `<gateway>/v1/models` and require the configured MiniCPM model ID.
5. Build a complete release in a temporary sibling directory.
6. Set the classifier executable bit and verify the temporary release.
7. Atomically switch the `current` release symlink while retaining the prior
   complete release if activation fails.
8. Report release identity, destination, Gateway endpoint, model ID, and the
   required OpenCode restart.

Verify is non-mutating. It validates the active release, compares it with the
expected source release, checks the classifier syntax and permissions, and
checks Gateway/model availability. Status is non-mutating and reports active
release metadata and drift. Uninstall removes only files owned by the moderator
release directory.

## Plugin Flow

The module SHALL use this installed-compatible shape:

```js
export default {
  id: "local-response-moderator",
  server: async ({ client, $ }) => ({
    event: async ({ event }) => {},
  }),
}
```

1. Register the `event` hook for `session.status`,
   `experimental.session.compacting`, `experimental.compaction.autocontinue`,
   and `session.compacted`, and create no global policy state outside the
   per-session finite-state-machine records.
2. Record and enqueue every `session.status` event before filtering.
3. Convert `busy` and matching subsequent `idle` notifications into immutable
   machine events with their generation values.
4. Read `sessionID` from `event.properties.sessionID` and enqueue the event in
   that session's FIFO queue.
5. Start a detached queue drain and return immediately from the event callback.
   MiniCPM latency must not block the worker or user interface.
6. The `LOAD_CONTEXT` effect selects the newest terminal assistant message with
   `info.finish === "stop"`. An assistant ending in `tool-calls` is in progress
   and SHALL NOT be claimed, checked, prompted, or classified. A claimed
   terminal assistant ID SHALL NOT be processed again.
7. Inspect fenced shell-like code blocks before invoking MiniCPM. A block with
   `sudo` as a command token is a legitimate root-required blocker. Write a
   `root-blocked` decision, persist a passive operator-handoff trace, show a
     model-labeled toast, activate blocker-discussion state with source
     `root-blocked` and the relevant real-user message ID, and do not continue
     automatically.
8. Resolve deterministic terminal outcomes before MiniCPM: root handoff,
   duplicate/nonterminal/compaction responses, blocker discussion, and required
   high-priority work with no explicit blocker. The controller does not request
   self-certification and does not require `[WORK DONE]`. An unrelated real-user
   task clears blocker-discussion state before this decision.
9. Invoke MiniCPM only when the terminal response remains semantically
   ambiguous. Before accepting a MiniCPM `PASS`, deterministically reject it
   when a required high-priority todo is `pending` or `in_progress`. Genuine
   blockers, clarification requests, and approved non-required deferrals are
   `BLOCKED`, not passes.
10. In blocker-discussion state, a markerless response is informational
    discourse, not a completion claim. Persist a deterministic passive
    `blocker-discussion` decision without MiniCPM, `promptAsync`, or an
    operator-action claim. Omit completion and adherence rulings from its visible
    trace and preserve the original blocker source.
11. Show a client-visible checking toast with `client.tui.showToast` only after
   a valid completed assistant response is confirmed.
12. Fetch todos with the installed SDK shape
   `client.session.todo({ path: { id: sessionID } })`.
13. Fetch messages with
   `client.session.messages({ path: { id: sessionID }, query: { limit: 200 } })`.
14. Run the Bash script once, passing one JSON object on standard input:

```json
{"session_id":"...","todos":[],"messages":[]}
```

15. Parse the script's YAML loop decision and write one YAML decision file for
    the attempt and result.
16. Persist a passive marked trace for every decision: pass,
    continuation, escalation, root block, and error. Each trace includes the
    configured MiniCPM model, decision type, audit decision ID, verdict when
    applicable, and concise reason. Use `session.prompt` with `noReply: true`;
    a trace is visible context, not a new GPT turn.
17. One completion-eligible `PASS` stops after the passive trace and clears
    blocker-discussion state. `BLOCKED` activates or retains blocker-discussion
    state, then stops after an operator-handoff trace. `CONTINUE_PROGRESS`
    resets the no-progress count. `CONTINUE_NO_PROGRESS` increments it;
    controller-only `CONTINUE_REQUIRED_WORK` preserves it. On the third
    consecutive MiniCPM no-progress decision, write an escalation trace and stop
    automatic prompts.
18. Otherwise issue one labeled continuation prompt with
    `client.session.promptAsync` with the installed SDK shape:

```js
client.session.promptAsync({
  path: { id: sessionID },
  body: { parts: [{ type: "text", text }] },
})
```

```text
[LOCAL_MODERATOR_RETRY]
Task completion: FAIL - <reason>
Prompt adherence: PASS - <reason>
Continue working and correct every failed item. Do not merely explain it.
```

`promptAsync` is deliberate for continuations: it creates a normal persisted user message in the
same session, making the violation, reasons, and corrective instruction visible
in the transcript and available to the next agent turn. The next idle event
evaluates the new agent response. The marker prevents this corrective prompt
from counting as one of the last three real user messages.

The adapter loads the model dynamically from release-local `config.json`.
Continuation and every passive trace append
`[Moderator model: <model>]`. Every moderator toast appends the same configured
model identity so the Build agent and the MiniCPM moderator are visibly
distinguishable in the UI.

On classifier or transport error, write the error to a `moderation-error`
decision file, show an
error toast, and do not create a `PASS` result. All SDK calls, script execution,
verdict parsing, audit writing, toast publication, and corrective prompting
belong to one error boundary so every failure is observable.

The adapter SHALL not parse or reshape transcript content. It only passes the
SDK's structured JSON to the Bash script and handles the returned verdict.
It SHALL not register `chat.message` or `experimental.text.complete`; user
messages and partial assistant text are never moderation triggers.

## Eligibility And Compaction Guards

Completion moderation is an opt-in path for the installed OpenCode Build agent.
Before classifier invocation, the actor SHALL require this value on the
completed assistant message:

```text
info.agent == "build"
```

The built-in `plan` mode is never moderated. Custom agents and subagents are
also outside this completion contract until a separate policy defines their
completion semantics. These paths write an ignored decision and consume the
idle generation without changing retry state:

| Condition | Decision | Side effects |
| --- | --- | --- |
| `info.mode == "plan"` | `ignored-plan-mode` | No prompt, toast, or MiniCPM call |
| Missing/non-Build agent | `ignored-non-build-agent` | No prompt, toast, or MiniCPM call |
| Compaction summary assistant | `ignored-compaction` | No prompt, toast, or MiniCPM call |

The plugin SHALL identify compaction summaries before ordinary completion
processing. A completed assistant is a compaction summary when any of the
following authoritative fields applies:

```text
info.summary == true
info.mode == "compaction"
info.agent == "compaction"
```

The plugin SHALL observe both compaction lifecycle hooks:

- `experimental.session.compacting`: mark the session as compacting and record
  the lifecycle start before the summary is generated.
- `experimental.compaction.autocontinue`: record whether OpenCode will resume
  the session after compaction.

The plugin SHALL also accept the `session.compacted` event as the successful
compaction boundary. Compaction state is cleared only after the corresponding
summary/compacted event has been recorded. A compaction summary cannot reset
or increment the retry cycle. If auto-continuation creates a later built-in
Build response, that later response is a new eligible moderation target.

The actor SHALL select the latest assistant using chronological message order
and the latest relevant user's `parentID`. Lexicographic comparison of message
IDs is not a recency algorithm and SHALL NOT be used.

An assistant message with `info.finish !== "stop"` is not a completed response.
This includes `tool-calls`, which can launch a subtask while the parent Build
turn is still active. The actor SHALL write `ignored-nonterminal-assistant` and
wait for the later terminal parent response; it SHALL not send any moderator
prompt or alter retry state.

## Bash Script Flow

1. Read the JSON snapshot from standard input.
2. Use `jq` to preserve the complete todo list and select the last three
   unmarked user messages by `info.role` and text parts.
3. Use `jq` to preserve agent messages between the first selected user message
   and the latest response. Tool parts without text are omitted; text parts are
   retained in order.
4. POST the final candidate messages with `curl` through the Gateway's
   `/llamafile` relay to `/v1/chat/completions/input_tokens`; remove the oldest
   agent context and measure again until the count is at most 16,384. A failed
   count or a remaining over-bound request is a classifier error and prevents
   the completion request.
5. POST the final JSON request through the same relay using the model from the
   release-local configuration, temperature `0`, and `max_tokens` set to `128`.
   The finite grammar normally stops well before this ceiling. The server renders
   the JSON `messages` through the MiniCPM5 GGUF's Jinja chat template. That
   rendering serializes message roles into model tokens; it is not JSON
   processing and it does not constrain the generated classifier response.
6. Require exactly this YAML shape:

```yaml
decision: PASS | CONTINUE_PROGRESS | CONTINUE_NO_PROGRESS | BLOCKED
reason: COMPLETE | WORK_REMAINS | NO_PROGRESS | EXTERNAL_BLOCKER | CLARIFICATION_REQUIRED
```

7. Pass a GBNF grammar in the llamafile-specific `grammar` request field that
   permits only the exact two-line YAML protocol and finite decision/reason-code
   enums. This grammar constrains token sampling and prevents copied transcript
   text, JSON, prose, headings, and extra keys. Use the fixed YAML validator as
   a defense-in-depth boundary, require the API response to finish with `stop`,
   and map the accepted reason code to human-readable text. A malformed or
   incomplete response is retried three times with a passive transcript trace
   before a visible classifier-unavailable stop. Write canonical YAML to standard
   output, write diagnostics to standard error, and exit nonzero on HTTP,
   token-budget, finish-reason, or parsing errors.

The protocol is versioned. A later version may append a bounded free-text
`detail` field for operator-facing context, but must update the grammar and
validator atomically. It must not relax the current V2 two-line validator.

The system prompt tells MiniCPM that it is the moderator, not the working agent.
It must classify every terminal response as pass, substantive progress requiring
continuation, no progress requiring continuation, or a genuine blocker. It also
defines the two completion decisions:

- `task_completion`: the requested work is actually complete, including stated
  verification. Unresolved todos are evidence to weigh against completion, not
  an automatic failure: clarification, genuine external blockers, and
  intentionally deferred non-required work may be valid outcomes.
- `prompt_adherence`: the agent followed the active user instructions and did
  not substitute a different task.

## Diagnostics

Every decision SHALL be written as one YAML file at:

```text
${XDG_STATE_HOME:-$HOME/.local/state}/opencode/local-response-moderator/<sessionID>/<timestamp>-<assistantID>-<decisionID>.yaml
```

Each file SHALL include plugin version, session and assistant IDs, decision
type, exact assistant response, marker `contains` results,
todos, selected context, exact classifier prompt and HTTP request settings when
applicable, raw YAML response when applicable, parsed verdict when applicable,
blocker-discussion state and source, prompt/toast results, errors, and timings.
Classifier evidence SHALL include structured `model`, `gateway`, and `version`
facts. Selected user, assistant, and context facts SHALL include IDs, parent IDs,
roles, timestamps, and text. Every completed effect SHALL include start,
completion, and duration timing facts. JSON is permitted because it is a valid
YAML 1.2 document, avoiding unsafe handwritten YAML serialization.
The file SHALL be flushed before
the decision operation is reported complete. This replaces the shared JSONL
audit file.

For every classifier call, the Bash script SHALL write the exact request and
raw YAML response into the capture included in the same decision file. The
capture is the authoritative record of the system prompt, selected transcript,
todo list, model, temperature, max tokens, and token-budget result used for
that classification.

## Configuration

The tracked configuration template is rendered into the active release. It
contains the only allowed classifier endpoint and model identity:

```json
{
  "gateway_url": "http://127.0.0.1:9080/llamafile",
  "model": "/zip/MiniCPM5-1B-Q8_0.gguf"
}
```

The installer validates that `gateway_url` is the existing Workspace Gateway
relay and that `model` is returned by `<gateway_url>/v1/models`. The classifier
does not accept an environment override that can bypass Gateway observability,
redaction, request IDs, or rate limiting.

The Bash script requires `bash`, `curl`, and `jq`. No provider SDK or OpenCode
provider configuration is needed.

## Installation

- Deploy MiniCPM with the existing command:
  `make install-llamafile MODEL=minicpm5-1b GPU=vulkan`; the moderator reaches
  it only through the existing Workspace Gateway `relay-llamafile` route.
- Run `make install-opencode-moderator` to create and activate a validated
  moderator release.
- Run `make verify-opencode-moderator` after installation or configuration
  changes to validate the active release and Gateway model availability.
- Restart OpenCode after activation because plugins load at startup.

No new systemd unit, Ansible role, llamafile target, or Gateway route is added.

## Finite-State-Machine Implementation

### Module Boundaries

The refactor adds one local module and no dependency:

```text
local-response-moderator.js          OpenCode event hooks, session queues, effects
local-response-moderator-machine.js  Pure state, events, guards, transition reducer
local-response-moderator.sh          Transcript selection and MiniCPM protocol adapter
```

The installer SHALL copy all three runtime files into a release before atomically
activating it. The adapter imports the machine with a release-local relative
import. The machine module SHALL not import `node:fs`, Bun subprocess APIs, or
OpenCode SDK types. Its only exports are initial-state creation, event constants,
transition, and state restoration validation.

### Session State

The machine state is a plain serializable object:

```js
{
  phase: "IDLE", // IDLE | OBSERVING | CLASSIFYING | CONTINUING | ERROR
  busyGeneration: 0,
  pendingIdleGenerations: [],
  inflightAssistantID: null,
  lastTerminalAssistantID: null,
  realUserCycleID: null,
  consecutiveNoProgressCount: 0,
  blocker: null, // { source, originUserID }
  compaction: { active: false, generation: 0 },
}
```

The adapter's queue and effect promises are runtime-only and are not part of
this object. The event payload supplies short-lived context snapshots, selected
assistant/user IDs, marker state, classifier results, and effect outcomes. A
transition must create a new state object; it must not mutate input state or
event payloads.

### Transition Contract

`transition(state, event)` returns:

```js
{
  state: nextState,
  effects: [{ type: "WRITE_DECISION", record: {} }],
  ignored: false,
}
```

For an unsupported event/phase pair it returns the unchanged state, a
`WRITE_DECISION` effect with an explicit ignored reason, and `ignored: true`.
The reducer never throws for an external event. Programmer-invalid event shapes
throw at the adapter boundary before enqueueing so they cannot be mistaken for
moderation outcomes.

The following table is authoritative for normal transitions. An effect result
is always reintroduced through its named result event; no effect may call
`transition` recursively.

| Current phase | Event | Next phase | Required effects |
| --- | --- | --- | --- |
| `IDLE` | `STATUS_BUSY` | `OBSERVING` | `WRITE_DECISION` |
| `OBSERVING` | `STATUS_IDLE` | `OBSERVING` | `LOAD_CONTEXT`, `WRITE_DECISION` |
| `OBSERVING` | `CONTEXT_LOADED` ineligible/duplicate | `IDLE` | `WRITE_DECISION` |
| `OBSERVING` | `ROOT_BLOCK_DETECTED` | `ROOT_BLOCKED` | `WRITE_DECISION`, `WRITE_TRACE`, `SHOW_TOAST` |
| `OBSERVING` | eligible `CONTEXT_LOADED` | `CLASSIFYING` | `WRITE_DECISION`, `SHOW_TOAST`, `CLASSIFY` |
| `CLASSIFYING` | valid `CLASSIFIER_RESULT` | outcome phase | outcome effects |
| `CONTINUING` | `CONTINUATION_PERSISTED` | `CONTINUING` | `VERIFY_PROMPT`, `WAIT_FOR_BUSY`, `WRITE_DECISION` |
| `CONTINUING` | `BUSY_VERIFIED` or `CONTINUATION_TIMEOUT` | `IDLE` | `WRITE_DECISION`, optional `SHOW_TOAST` |
| `IDLE` | `STATUS_BUSY` with blocker scope | `OBSERVING` | `WRITE_DECISION` |
| Any nonterminal phase | `CLASSIFIER_ERROR` or `EFFECT_ERROR` | `ERROR` | `WRITE_DECISION`, `WRITE_TRACE`, `SHOW_TOAST` |

Outcome effects are fixed:

| Outcome | Next phase | Effects |
| --- | --- | --- |
| Completion-eligible `PASS` | `IDLE` | `WRITE_DECISION`, `WRITE_TRACE`, `SHOW_TOAST` |
| `BLOCKED` | `IDLE` with blocker scope | `WRITE_DECISION`, `WRITE_TRACE`, `SHOW_TOAST` |
| Markerless blocker discussion | `IDLE` with blocker scope | `WRITE_DECISION`, `WRITE_TRACE` |
| `CONTINUE_PROGRESS` | `CONTINUING` | `WRITE_DECISION`, `WRITE_TRACE`, `SHOW_TOAST`, `SEND_CONTINUATION` |
| `CONTINUE_NO_PROGRESS`, count below three | `CONTINUING` | `WRITE_DECISION`, `WRITE_TRACE`, `SHOW_TOAST`, `SEND_CONTINUATION` |
| `CONTINUE_REQUIRED_WORK` | `CONTINUING` | `WRITE_DECISION`, `WRITE_TRACE`, `SHOW_TOAST`, `SEND_CONTINUATION` |
| `CONTINUE_NO_PROGRESS`, count three | `ESCALATED` then `IDLE` | `WRITE_DECISION`, `WRITE_TRACE`, `SHOW_TOAST` |

Before an outcome transition, the reducer applies deterministic guards in this
order: root-required block, required high-priority todo completion eligibility,
blocker-branch scope, classifier result, then no-progress count. A `PASS` with
required unfinished work always becomes controller-only
`CONTINUE_REQUIRED_WORK`, which does not alter the no-progress count.
`BLOCKED` is the only classifier outcome that stops for a genuine external
blocker; final accepted `PASS`, root-required block, and no-progress escalation
also stop under their respective deterministic conditions.

### Effect Executor

The adapter owns an `executeEffect(sessionID, effect)` dispatcher. It is the only
code permitted to call the SDK, Bash classifier, timeout helper, filesystem, or
toast API. It returns exactly one event to the session queue for each effect.
`WRITE_DECISION` records the prior phase, source event, next phase, guard
results, effect payload, effect result, and snapshot. `WRITE_TRACE` uses
`session.prompt(... noReply: true)`. `SEND_CONTINUATION` uses `promptAsync`.
`VERIFY_PROMPT` rereads messages. `WAIT_FOR_BUSY` observes a
later busy generation for the bounded existing timeout.

Effects for one transition execute in listed order. Failure to write the
decision record stops later externally visible effects and yields `EFFECT_ERROR`.
Failures after the decision record are appended by a follow-up error record.
The executor does not silently retry semantic decisions; only the existing
three format retries are represented by `CLASSIFIER_FORMAT_RETRY` events.

### Queue And Recovery

`session.status`, compaction hooks, and effect result events enqueue immutable
machine events in a per-session FIFO queue. A drain operation processes one event,
executes its emitted effects, and continues until the queue is empty. It never
runs two transitions for one session concurrently. Idle events retain their busy
generation, allowing duplicate and stale idle notifications to be explicitly
ignored without losing a later eligible idle event.

On startup, the adapter restores the most recent valid state snapshot for each
session from atomic YAML decision records. It validates the phase and all finite
fields before accepting a snapshot. If the latest record is incomplete or
invalid, it writes a visible recovery error record and restores the preceding
valid snapshot. In-flight claims are restored only when their durable decision
record proves a decision completed; otherwise the assistant is eligible for a
safe retry.

### Migration Compatibility

The refactor preserves the V2 classifier protocol, audit directory, release
configuration, Gateway-only route, visible strings, and decision types. It
removes checklist and `[WORK DONE]` marker compatibility, along with second-pass
adjudication, because they are redundant self-certification paths.
Existing YAML records lacking a `stateSnapshot` remain readable as audit evidence
but are not authoritative snapshots. Recovery derives the minimum compatible
state from their decision type, retry count, blocker fields, and chronological
order; new records always include a complete snapshot.

The adapter version changes with the release. Installation verification SHALL
confirm that `local-response-moderator-machine.js` is present in source and the
active release, and that its content matches the tracked source.

## Verification

- Test the Bash script's transcript selection, marker exclusion, token trimming,
  verdict parsing, and duplicate-response suppression.
- Import the actual plugin module in a test and invoke its returned `server()`
  hook with recording SDK clients.
- Verify a completion-eligible `PASS` emits checking and success toasts, writes an audit record,
  writes a model-labeled passive transcript trace with `noReply: true`, and
  does not start another agent turn.
- Verify continuation, escalation, root-blocked, and error decisions
  each emit model-labeled toasts and passive transcript traces containing the
  decision ID and concise reason.
- Verify `CONTINUE_PROGRESS` resets the count, `CONTINUE_REQUIRED_WORK`
  preserves it, three consecutive MiniCPM `CONTINUE_NO_PROGRESS` decisions
  escalate, and no productive-turn cap exists.
- Verify a fenced `sudo` command blocks before MiniCPM and creates an operator
  handoff without a continuation prompt.
- Verify root-blocked -> real-user prompt -> markerless Build response invokes
  MiniCPM directly.
- Verify MiniCPM `BLOCKED` activates the same direct-classification mode across
  later real-user cycles and after plugin restart.
- Verify a markerless proposed `PASS` with required todos in blocker-discussion
  state becomes a passive `blocker-discussion` decision without a continuation
  prompt or operator-action claim.
- Verify final accepted `PASS` clears blocker-discussion state.
- Verify a markerless terminal response with required pending or in-progress
  todos cannot pass even when MiniCPM returns `PASS`.
- Verify SDK, script, parser, and HTTP failures emit an error toast and passive
  audit trace.
- Verify Plan-mode responses produce `ignored-plan-mode` without a
  corrective prompt, toast, or MiniCPM request.
- Verify non-Build agents produce `ignored-non-build-agent` without completion
  moderation side effects.
- Verify compaction summaries produce `ignored-compaction`, including when the
  summary contains completion wording or an error.
- Verify compaction start, autocontinue, and `session.compacted` lifecycle
  records are written and do not reset retry state.
- Verify a Build response after compaction is moderated exactly once.
- Verify latest-assistant selection follows chronological order and `parentID`,
  not lexicographic message IDs.
- Verify a Build message ending in `tool-calls` produces
  `ignored-nonterminal-assistant` with no retry, toast, or MiniCPM
  request, and that its later `finish === "stop"` parent response is moderated
  once.
- Execute the actual installer against an isolated `XDG_CONFIG_HOME` and verify
  the complete release layout, rendered configuration, file permissions, and
  source/install identity.
- Verify interrupted or failed activation leaves the prior complete release
  active and never exposes a mixed adapter/classifier/configuration state.
- Verify `oc` does not modify moderator installation state.
- Verify install rejects a direct llamafile URL, an unreachable Gateway, and a
  configured model absent from `/llamafile/v1/models`.
- Verify status and verify are non-mutating, and uninstall removes only the
  moderator release directory.
- Start an isolated OpenCode server with the plugin configured and verify the
  plugin is discovered and receives a real idle event.
- Run a live sanity check through the existing Gateway `/llamafile` relay.
- Run `/home/agent/.bun/bin/bun test tests/integration/local-response-moderator-machine.test.js tests/integration/local-response-moderator.test.js` before an installed-release claim.
