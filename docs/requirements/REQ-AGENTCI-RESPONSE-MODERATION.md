# REQ-AGENTCI-RESPONSE-MODERATION: Local Response Moderation

**Date:** 2026-08-29
**Status:** Active
**Type:** Requirements

> Completion-gating requirements for the AgentCI plugin (`workspace/agentci/`,
> TypeScript only): before an OpenCode agent stops, the local MiniCPM5
> llamafile server decides whether the task is complete and whether the
> response follows the user's instructions. A failure on either decision makes
> the agent continue.

---

## Goal

Moderate terminal Build responses using the existing local MiniCPM5 llamafile
server reached through the Workspace Gateway `/llamafile` relay. A response
that fails completion or adherence makes the agent continue; a pass lets the
session stay idle.

## Requirements

### Event Observation

1. The AgentCI plugin SHALL use the `event` hook and accept `session.status`,
   `experimental.session.compacting`, `experimental.compaction.autocontinue`,
   and `session.compacted` lifecycle events. It SHALL record each event before
   filtering, track a `busy` transition, and moderate only the matching
   subsequent `idle` event.
2. The idle event SHALL be emitted after the agent processing loop has finished
   the assistant response. Duplicate idle events SHALL NOT process the same
   assistant message twice.
3. Completion moderation SHALL apply only when the completed assistant has
   `info.agent == "build"`. Missing or other values SHALL be ignored with an
   auditable reason.
4. Plan-mode responses and compaction summary responses SHALL never receive a
   corrective prompt or classifier request. A completed assistant with
   `info.summary == true`, `info.mode == "compaction"`, or
   `info.agent == "compaction"` SHALL produce `ignored-compaction`.
5. Completion moderation SHALL process only an assistant message whose
   `info.finish == "stop"`. Messages ending in `tool-calls` or another
   nonterminal finish state SHALL be ignored without retry, classifier call,
   or retry-cycle mutation.
6. The plugin SHALL process only the latest assistant response associated with
   the latest relevant user turn, using chronological API ordering and
   `parentID`; it SHALL not infer recency from lexicographic message IDs.

### Classifier

7. The plugin SHALL read that session's todo list and messages through the
   OpenCode client supplied to the plugin, using the installed SDK request
   shapes.
8. The classifier SHALL call MiniCPM5 only through the Workspace Gateway's
   `/llamafile` relay. It SHALL NOT connect directly to the llamafile port or
   start, install, or manage an inference server.
9. The classifier input SHALL contain the todo list and the last three real
   user messages. It SHALL call the Gateway token-count endpoint on the final
   candidate request and remove oldest intervening agent context until the
   measured input is at most 16,384 tokens. A token-count failure or a request
   still above that bound is a visible classifier error and no request is sent.
10. The classifier SHALL return exactly two YAML lines: `decision` with one of
    `PASS`, `CONTINUE_PROGRESS`, `CONTINUE_NO_PROGRESS`, or `BLOCKED`, followed
    by a `reason` code from `COMPLETE`, `WORK_REMAINS`, `NO_PROGRESS`,
    `EXTERNAL_BLOCKER`, or `CLARIFICATION_REQUIRED`. Any extra, missing,
    title-case, prose, JSON, or ruling line is a classifier-format failure. The
    adapter SHALL trace and retry that failure three times before a visible
    classifier-unavailable stop. The adapter SHALL enforce this closed YAML
    language with the gateway's GBNF grammar, not only a natural-language
    instruction. A future protocol version MAY add a bounded free-text `detail`
    field, but SHALL update the GBNF grammar and fixed validator together; the
    current two-line protocol SHALL not accept it.
11. The classifier SHALL reconcile todo state with the actual user request. An
    incomplete todo SHALL NOT force a failure when the agent correctly requests
    clarification, reports a genuine external blocker, or intentionally defers
    non-required work; it SHALL contribute to a failure when required work
    remains undone or verification is missing before a proposed `PASS`.
12. Invalid classifier output or a failed relay request SHALL be reported as an
    error. It SHALL NOT be treated as `PASS`.

### Moderation Path

13. Every eligible terminal Build response SHALL enter one checklist-free,
    deterministic-first moderation path. The adapter SHALL resolve known policy
    violations, root handoffs, duplicates, nonterminal/tool-call updates,
    compaction, blocker discussion, and required work with no explicit blocker
    before invoking MiniCPM. MiniCPM SHALL run only when the terminal response
    remains semantically ambiguous. The adapter SHALL not issue a completion
    checklist or require a completion marker.
14. `PASS` is completion-eligible only when no required high-priority todo is
    `pending` or `in_progress`. Required work with no explicit blocker SHALL
    produce the controller-only `CONTINUE_REQUIRED_WORK` outcome with
    `WORK_REMAINS` without a classifier request. A genuine blocker,
    clarification requirement, or approved non-required deferral SHALL be
    represented by structured facts or a classifier `BLOCKED` verdict, never as
    `PASS`.
15. `PASS` SHALL allow the session to remain idle only after the plugin
    persists a model-labeled passive audit trace in the transcript stating the
    decision, derived completion/adherence rulings, reason, and decision ID;
    the trace SHALL be excluded from subsequent moderation context. A
    completion-eligible `PASS` SHALL stop after its persisted passive audit
    trace; the adapter SHALL not request self-certification or a second
    adjudication of the same deterministic classifier input.
16. `CONTINUE_PROGRESS` and `CONTINUE_NO_PROGRESS` SHALL send a model-labeled
    corrective prompt to the same session with `promptAsync`. The prompt SHALL
    be a normal persisted user message, visible in the transcript and available
    to the next agent turn. Moderator-generated prompts SHALL be marked and
    excluded from the last three real user messages.
17. The corrective retry prompt and classifier decision check SHALL explicitly
    state that the work must be completed before stopping and that the agent
    must continue working rather than merely explain a limitation.
18. The plugin SHALL show client-visible feedback while checking, after `PASS`,
    and when issuing a corrective prompt. Every toast and every
    moderator-generated transcript message SHALL identify the configured
    moderator model.

### Retry Cycle

19. `CONTINUE_PROGRESS` SHALL reset the consecutive no-progress count.
    `CONTINUE_NO_PROGRESS` SHALL increment it. `CONTINUE_REQUIRED_WORK` SHALL
    preserve the count because it is a controller eligibility outcome, not a
    progress ruling. Automatic continuation SHALL stop only after three
    consecutive `CONTINUE_NO_PROGRESS` decisions in one real-user cycle, with a
    visible `moderation-escalated` trace.
20. A new real user message SHALL start a new retry cycle and reset the
    per-cycle no-progress count. It SHALL clear blocker-discussion state unless
    its `parentID` continues the blocker-originating user branch.

### Blockers

21. The adapter SHALL inspect fenced shell-like code blocks before classifier
    invocation. A block containing `sudo` as a command token SHALL produce the
    terminal `root-blocked` decision. It is a legitimate operator blocker, not
    a failure, and SHALL create a visible passive trace and toast without an
    automatic continuation. It SHALL activate durable blocker-discussion state.
22. A valid `BLOCKED` verdict SHALL also activate blocker-discussion state. The
    state SHALL store its originating real-user message ID and persist across
    restart. It SHALL apply only to later prompt-response pairs in that
    `parentID` branch. It SHALL clear for an unrelated user task or a final
    accepted `PASS` in the blocker-originating branch. `CONTINUE_*` outcomes
    SHALL not clear it.
23. Blocker-discussion state is nudge-suppression context, not a continuing
    operator-action requirement. A response in this state SHALL persist a
    deterministic passive `blocker-discussion` decision without a classifier
    request, corrective prompt, or operator-action claim. The required-todo
    completion gate applies to every proposed `PASS`.

### Compaction

24. The plugin SHALL observe the OpenCode compaction lifecycle. It SHALL mark
    `experimental.session.compacting` before compaction processing and record
    `session.compacted` after successful compaction. A compaction event SHALL
    not consume, reset, or increment the real-user retry cycle. A later Build
    response after auto-continuation SHALL be eligible for normal moderation.

### Audit Persistence

25. The plugin SHALL write one YAML decision file per decision under
    `${XDG_STATE_HOME:-$HOME/.local/state}/opencode/agentci/moderation/<sessionID>/`.
    Every status event and every decision outcome SHALL produce its own YAML
    file; missing files SHALL be treated as an observability failure.
26. Each decision file SHALL include timestamp, plugin version, session ID,
    assistant ID, decision ID, decision type, exact assistant response, marker
    results, todos, selected context, exact classifier prompt and request
    settings when applicable, raw YAML response when applicable, parsed
    verdict, blocker-discussion state and source, prompt/toast results, errors,
    and timings.
27. Decision types SHALL include `blocker-discussion`, `moderation-pass`,
    `moderation-fail`, `moderation-escalated`, `moderation-error`,
    `root-blocked`, `ignored-cancellation`, `ignored-duplicate`,
    `ignored-no-completed-assistant`, `ignored-plan-mode`,
    `ignored-non-build-agent`, `ignored-compaction`,
    `ignored-nonterminal-assistant`, and `ignored-moderator-trace`.

## Constraints

- Reuse the Gateway's existing `relay-llamafile` route at
  `http://127.0.0.1:9080/llamafile`, which proxies to the existing
  `llamafile-minicpm5-1b.service` upstream.
- All moderation logic SHALL be TypeScript inside `workspace/agentci/`; no
  shell-out classifier, no new daemon, service, model deployment path,
  database, queue, classifier framework, or Gateway route.
- Gateway endpoint and MiniCPM model configuration SHALL come from the plugin
  option configuration validated at startup. Runtime environment overrides
  SHALL NOT permit direct llamafile connections. The runtime SHALL reject a
  configuration whose endpoint is not the Workspace Gateway `/llamafile`
  relay. The input limit is fixed at 16,384 tokens.
- Do not modify OpenCode source.
- Moderation SHALL run asynchronously after the idle event and SHALL NOT delay
  the worker response or user-message submission.
- User messages SHALL be used only as context. The moderator SHALL never run on
  user-message arrival and SHALL never classify a user message as the response.

## Acceptance

- Every moderation outcome produces one visible, passive transcript trace with
  the configured model, decision type, audit decision ID, and concise reason.
- `PASS` produces a passive trace without starting a new agent turn.
- `CONTINUE_PROGRESS` and `CONTINUE_NO_PROGRESS` each produce one corrective
  prompt visible as a persisted user message in the same transcript.
- Three consecutive no-progress decisions produce a visible escalation trace
  and no further automatic prompt.
- A fenced `sudo` command produces a visible root-blocked trace and no
  automatic prompt.
- A root-blocked or `BLOCKED` outcome records branch-scoped passive discussion
  context. This state survives restart and clears only after final accepted
  `PASS`.
- The client displays model-labeled checking and outcome feedback.
- The request includes all todos and the last three real user messages and does
  not exceed 16,384 input tokens.
- Repeated idle notification for one response produces at most one classifier
  request.
- A Build response ending in `tool-calls` produces no moderation action; the
  subsequent terminal parent response is moderated exactly once.
- An integration test SHALL load the actual plugin module, invoke its returned
  idle-event hook with test SDK clients, and verify every trace path, model
  attribution, false-pass prevention, toasts, classification, and persisted
  corrective prompting.
- An isolated OpenCode server test SHALL verify plugin discovery and event
  dispatch using the installed plugin contract.

## Finite-State-Machine Architecture

The runtime SHALL use one dependency-free, pure reducer per session, written in
TypeScript. The reducer is the sole authority for moderation policy: it accepts
an immutable state and one named event, validates the transition, and returns
the next state plus ordered named effects. SDK calls, classifier invocation,
filesystem writes, timers, and toasts SHALL execute outside the reducer and
SHALL report their result through a new event. No effect implementation may
choose a state transition.

The adapter owns event-hook wiring, one FIFO queue per session, effect
execution, and conversion between OpenCode/SDK data and machine events. The
machine module owns states, events, guards, transition table, initial state,
and no I/O.

### State Model

Each session has exactly one lifecycle phase:

```text
IDLE -> OBSERVING -> CLASSIFYING -> CONTINUING | BLOCKED | ROOT_BLOCKED | ERROR
CLASSIFYING -> PASS | ESCALATED
ERROR -> OBSERVING | IDLE
```

`PASS`, `BLOCKED`, `ROOT_BLOCKED`, and `ESCALATED` are recorded outcomes, not
durable lifecycle phases. The next `STATUS_BUSY` begins observation of a later
response. Blocker discussion is a nullable branch scope, not a lifecycle phase.
A new unrelated real-user branch clears that scope before classification.

The durable state record SHALL contain only facts required to reconstruct legal
future transitions:

```text
phase
busyGeneration
pendingIdleGenerations
inflightAssistantID
lastTerminalAssistantID
realUserCycleID
consecutiveNoProgressCount
blocker: null | { source, originUserID }
compaction: { active, generation }
```

Transcript snapshots, classifier captures, prompts, toasts, and decision IDs
are decision evidence, not machine state. The reducer SHALL not retain message
objects, client objects, promises, or mutable collections in its state.

### Events, Guards, And Effects

The machine SHALL expose a closed event vocabulary at least covering:

```text
STATUS_BUSY, STATUS_IDLE, COMPACTION_STARTED, COMPACTION_AUTOCONTINUE,
COMPACTION_COMPLETED, CONTEXT_LOADED, ASSISTANT_IGNORED, ROOT_BLOCK_DETECTED,
CLASSIFIER_RESULT, CLASSIFIER_FORMAT_RETRY, CLASSIFIER_ERROR, TRACE_PERSISTED,
CONTINUATION_PERSISTED, BUSY_VERIFIED, CONTINUATION_TIMEOUT, EFFECT_ERROR
```

Guards SHALL be pure predicates over the state and event payload. They include
assistant eligibility, duplicate suppression, chronological parent selection,
real-user-cycle changes, blocker-branch membership, completion-claim validity,
required-todo gating, classifier result validity, and no-progress escalation.
The reducer SHALL reject or explicitly record every event that is invalid for
the current phase; it SHALL surface an explicit error rather than continue.

Effects SHALL be declarative values from this closed set:

```text
LOAD_CONTEXT, WRITE_DECISION, WRITE_TRACE, SHOW_TOAST, CLASSIFY,
SEND_CONTINUATION, VERIFY_PROMPT, WAIT_FOR_BUSY
```

The adapter SHALL execute effects in order. It SHALL append every effect result
to the relevant decision evidence and enqueue its corresponding result event.
`WRITE_DECISION` SHALL precede an externally visible trace or prompt that
claims that decision. Failed persistence, prompt verification, classifier,
transport, or toast operations SHALL enter `ERROR` visibly; they SHALL never
imply a pass.

### Queue, Recovery, And Persistence

One serialized FIFO queue SHALL exist per session. The event hook SHALL enqueue
all relevant lifecycle events and return without awaiting moderation. While an
effect is active, later idle generations remain queued. A queued idle
generation SHALL be consumed once and only once after the preceding transition
finishes.

Each completed transition SHALL write an atomic decision record containing the
previous phase, event type, guard results, next phase, emitted effects, effect
results, state snapshot, and existing required audit fields. Restore SHALL fold
the latest valid snapshots in chronological decision-record order. An
incomplete or corrupt record SHALL be observable and SHALL not manufacture a
completed claim. Recoverable errors SHALL release the in-flight assistant
claim so the same completed assistant can be retried deliberately.

Only final accepted `PASS` clears the blocker scope. A new real-user cycle
resets only `consecutiveNoProgressCount`; it clears blocker scope only when its
user message is outside the blocker-originating branch. Compaction lifecycle
events remain observable and cannot change retry, blocker, or completion
state.

### Verification Requirements

The machine module SHALL have direct transition tests independent of OpenCode,
the filesystem, and MiniCPM. Tests SHALL cover every phase and every accepted
event, invalid-event handling, effect order, duplicate idle events, queued idle
generations, branch-scoped blockers, restart restoration, format-retry
exhaustion, required-todo rejection, three no-progress escalation, and error
recovery. Adapter integration tests SHALL verify that each emitted effect calls
its installed SDK or classifier boundary exactly once and feeds the observed
result back to the machine.

The implementation SHALL use random temporary files for classifier snapshots
and captures, paginate message history when necessary, and preserve complete
atomic decision records including timings, raw classifier exchange,
prompt/action results, and the final state transition.
