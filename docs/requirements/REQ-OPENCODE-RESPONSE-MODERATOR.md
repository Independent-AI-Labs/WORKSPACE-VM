# REQ-OPENCODE-RESPONSE-MODERATOR: Local Response Moderation

**Document ID:** WS-REQ-OPENCODE-RESPONSE-MODERATOR-v1.6  
**Status:** Active - checklist-free terminal-response policy approved
**Date:** 2026-08-10  
**Specification:** [SPEC-OPENCODE-RESPONSE-MODERATOR](../specifications/SPEC-OPENCODE-RESPONSE-MODERATOR.md)

## Goal

Before an OpenCode agent stops, use the existing local MiniCPM5 llamafile server
to decide whether the task is complete and whether the response follows the
user's instructions. A failure on either decision makes the agent continue.

## Requirements

1. A global OpenCode plugin SHALL use the installed server-plugin contract:
   default export an object containing a stable `id` and `server()` function.
2. The server plugin SHALL use the `event` hook and accept `session.status`,
   `experimental.session.compacting`, `experimental.compaction.autocontinue`,
   and `session.compacted` lifecycle events. It SHALL record each event before
   filtering, track a `busy` transition, and moderate only the matching
   subsequent `idle` event.
3. The idle event SHALL be emitted after the agent processing loop has finished
   the assistant response.
4. Completion moderation SHALL apply only when the completed assistant has
    `info.agent == "build"`. This is the installed OpenCode Build message
    identity; missing or other values SHALL be ignored with an auditable reason.
5. Plan-mode responses SHALL never receive a corrective prompt or MiniCPM
   classification.
6. Compaction summary responses SHALL never receive a corrective prompt or
   MiniCPM classification.
7. The plugin SHALL read that session's todo list and messages through the
   OpenCode client supplied to the plugin, using the installed SDK request
   shapes.
8. The plugin SHALL invoke one small Bash script with the todos and messages as
   JSON on standard input.
9. The Bash script SHALL use only `curl` and `jq` for HTTP and JSON handling.
10. The script SHALL call MiniCPM5 only through the Workspace Gateway's
    `/llamafile` relay. It SHALL NOT connect directly to the llamafile port or
    start, install, or manage an inference server.
11. The classifier input SHALL contain the todo list and the last three real
    user messages. It SHALL call the Gateway token-count endpoint on the final
    candidate request and remove oldest intervening agent context until the
    measured input is at most 16,384 tokens. A token-count failure or a request
    still above that bound is a visible classifier error and no request is sent.
12. The classifier SHALL return exactly two YAML lines: `decision` with one of
    `PASS`, `CONTINUE_PROGRESS`, `CONTINUE_NO_PROGRESS`, or `BLOCKED`, followed
    by a `reason` code from `COMPLETE`, `WORK_REMAINS`, `NO_PROGRESS`,
    `EXTERNAL_BLOCKER`, or `CLARIFICATION_REQUIRED`. Any extra, missing,
    title-case, prose, JSON, or ruling line is a classifier-format failure. The
    adapter SHALL trace and retry that failure three times before a visible
    classifier-unavailable stop. The adapter SHALL enforce this closed YAML
    language with the gateway's GBNF grammar, not only a natural-language
    instruction. The HTTP request is JSON because `/v1/chat/completions` is an
    OpenAI-compatible API; the llamafile server renders those messages with the
    MiniCPM5 GGUF's Jinja chat template before generation. Jinja is
    message-to-prompt serialization only and does not define, parse, or enforce
    the YAML protocol. The adapter SHALL map reason codes to human-readable
    audit and transcript text. A future protocol version MAY add a bounded free
    text `detail` field, but SHALL update the GBNF grammar and fixed validator
    together; the current two-line protocol SHALL not accept it.
13. The classifier SHALL reconcile todo state with the actual user request. An
   incomplete todo SHALL NOT force `FAIL` when the agent correctly requests
   clarification, reports a genuine external blocker, or intentionally defers
   non-required work; it SHALL contribute to `FAIL` when required work remains
    undone or verification is missing before a proposed `PASS`.
14. Every eligible terminal Build response SHALL enter one checklist-free,
    deterministic-first moderation path. The adapter SHALL resolve known policy
    violations, root handoffs, duplicates, nonterminal/tool-call updates,
    compaction, blocker discussion, and required work with no explicit blocker
    before invoking MiniCPM. MiniCPM SHALL run only when the terminal response
    remains semantically ambiguous.
15. `PASS` is completion-eligible only when no required high-priority todo is
    `pending` or `in_progress`. Required work with no explicit blocker SHALL
    produce the controller-only `CONTINUE_REQUIRED_WORK` outcome with
    `WORK_REMAINS` without a MiniCPM request. A genuine blocker, clarification
    requirement, or approved non-required deferral SHALL be represented by
    structured facts or a MiniCPM `BLOCKED` verdict, never as `PASS`.
16. `PASS` SHALL allow the session to remain idle only after the plugin persists
    a model-labeled passive audit trace in the transcript. The trace SHALL state
    the decision, derived completion/adherence rulings, reason, and decision ID, and SHALL
    be excluded from subsequent moderation context.
17. A completion-eligible MiniCPM `PASS` SHALL stop after its persisted passive
    audit trace. The adapter SHALL not request self-certification or a second
    adjudication of the same deterministic classifier input.
18. `CONTINUE_PROGRESS` and `CONTINUE_NO_PROGRESS` SHALL send a model-labeled
    corrective prompt to the same session with `promptAsync`. The prompt SHALL
    be a normal persisted user message, visible in the transcript and available
    to the next agent turn.
19. Moderator-generated prompts SHALL be marked and excluded from the last three
   real user messages.
20. The plugin SHALL show client-visible feedback while checking, after `PASS`,
    and when issuing a corrective prompt. Every toast and every
    moderator-generated transcript message SHALL identify the configured
    moderator model.
21. Invalid YAML classifier output or a failed llamafile request SHALL be reported as
    an error. It SHALL NOT be treated as `PASS`.
22. Duplicate idle events SHALL NOT process the same assistant message twice.
23. The adapter SHALL not issue a completion checklist or require a completion
    marker. Blocker-discussion state is a deterministic passive path that records
    its existing blocker source and does not invoke MiniCPM.
24. Moderator-generated retry and audit-trace prompts SHALL be
   marked and excluded from the last three real user messages.
25. The plugin SHALL write one YAML decision file per decision under
    `${XDG_STATE_HOME:-$HOME/.local/state}/opencode/local-response-moderator/<sessionID>/`.
26. Each decision file SHALL include timestamp, plugin version, session ID,
   assistant ID, decision ID, decision type, exact assistant response, marker
   results, todos, selected context, exact classifier prompt and request
    settings when applicable, raw YAML response when applicable, parsed verdict,
    blocker-discussion state and source, prompt/toast results, errors, and
    timings.
27. Decision types SHALL include `blocker-discussion`, `moderation-pass`,
      `moderation-fail`, `moderation-escalated`, `moderation-error`, `root-blocked`,
     `ignored-cancellation`,
    `ignored-duplicate`, `ignored-no-completed-assistant`, `ignored-plan-mode`,
    `ignored-non-build-agent`, `ignored-compaction`, and
    `ignored-nonterminal-assistant`, and `ignored-moderator-trace`.
28. `CONTINUE_PROGRESS` SHALL reset the consecutive no-progress count.
    `CONTINUE_NO_PROGRESS` SHALL increment it. `CONTINUE_REQUIRED_WORK` SHALL
    preserve the count because it is a controller eligibility outcome, not a
    MiniCPM progress ruling. Automatic continuation SHALL stop only after three
    consecutive MiniCPM `CONTINUE_NO_PROGRESS` decisions in one real-user cycle,
    with a visible `moderation-escalated` trace.
29. A new real user message SHALL start a new retry cycle and reset the
    per-cycle no-progress count. It SHALL clear blocker-discussion state unless
    its `parentID` continues the blocker-originating user branch.
30. The adapter SHALL inspect fenced shell-like code blocks before classifier
    invocation. A block containing `sudo` as a command token SHALL produce the
    terminal `root-blocked` decision. It is a legitimate operator blocker, not
    a failure, and SHALL create a visible passive trace and toast without an
    automatic continuation. It SHALL activate durable blocker-discussion state.
31. A valid MiniCPM `BLOCKED` verdict SHALL also activate blocker-discussion
    state. The state SHALL store its originating real-user message ID and persist
    across restart. It SHALL apply only to later prompt-response pairs in that
    `parentID` branch. It SHALL clear for an unrelated user task or a final
    accepted `PASS` in the blocker-originating branch. `CONTINUE_*` outcomes
    SHALL not clear it.
32. Blocker-discussion state is nudge-suppression context, not a continuing
    operator-action requirement. A markerless response in this state SHALL
    persist a deterministic passive `blocker-discussion` decision without a
    MiniCPM request, corrective prompt, or operator-action claim. The
    required-todo completion gate applies to every proposed `PASS`.
33. The corrective retry prompt and classifier decision check SHALL
    explicitly state that the work must be completed before stopping and that
    the agent must continue working rather than merely explain a limitation.
34. The plugin SHALL observe the OpenCode compaction lifecycle. It SHALL mark
    `experimental.session.compacting` before compaction processing and record
    `session.compacted` after successful compaction.
35. A completed assistant with `info.summary == true`, `info.mode ==
    "compaction"`, or `info.agent == "compaction"` SHALL be classified as a
    compaction summary and SHALL produce `ignored-compaction` without invoking
    MiniCPM or prompting the session.
36. A compaction event SHALL not consume, reset, or increment the real-user
    retry cycle. A later built-in Build response after auto-continuation SHALL
    be eligible for normal moderation.
37. The plugin SHALL process only the latest assistant response associated with
    the latest relevant user turn, using chronological API ordering and
    `parentID`; it SHALL not infer recency from lexicographic message IDs.
38. Moderator deployment SHALL have exactly one authority: a repository-aware
    installer. The `oc` wrapper SHALL NOT install, copy, update, or otherwise
    mutate moderator files during normal OpenCode execution.
39. The canonical JavaScript source SHALL be named
    `local-response-moderator.js`. A `.template.js` suffix SHALL be used only
    when the installer performs documented rendering.
40. The installer SHALL resolve its repository root from its own path and SHALL
    resolve its OpenCode configuration root as
    `${XDG_CONFIG_HOME:-$HOME/.config}/opencode`.
41. The installer SHALL validate the complete release before activation,
    including source existence, Bash syntax, executable permissions, Gateway
    configuration, and the configured model's presence at `/llamafile/v1/models`.
42. The JavaScript adapter SHALL dynamically load the configured moderator model
    from its release-local `config.json`. The JavaScript adapter, Bash
    classifier, and moderator configuration SHALL
    be activated as one atomic release. An interrupted install SHALL retain the
    previously active complete release.
43. The installer SHALL provide install, verify, status, and uninstall
    operations. Verify and status SHALL be non-mutating.
44. Installation output SHALL state the installed release identity, destination,
    Gateway endpoint, configured model, verification result, and that an
    already-running OpenCode process must restart before loading the release.
45. Gateway endpoint and MiniCPM model configuration SHALL come from one
    tracked moderator configuration template, rendered and validated by the
    installer. Runtime environment overrides SHALL NOT permit direct llamafile
    connections.
46. The runtime SHALL reject a configuration whose endpoint is not the existing
    Workspace Gateway `/llamafile` relay.
47. Completion moderation SHALL process only an assistant message whose
    `info.finish == "stop"`. Messages ending in `tool-calls` or another
    nonterminal finish state SHALL be ignored without a retry,
    classifier call, or retry-cycle mutation.

## Constraints

- Reuse the Gateway's existing `relay-llamafile` route at
  `http://127.0.0.1:9080/llamafile`, which proxies to the existing
  `llamafile-minicpm5-1b.service` upstream.
- The plugin SHALL be only the minimal JavaScript adapter required by OpenCode's
  plugin API: event handling, SDK reads, script invocation, verdict handling,
  and `promptAsync`.
- Transcript selection, JSON shaping, token counting, HTTP requests, and verdict
  validation SHALL remain in the Bash script.
- Do not modify OpenCode source.
- Do not add another daemon, service, model deployment path, database, queue,
  classifier framework, or Gateway route; reuse the existing `relay-llamafile`
  route.
- The tracked moderator configuration template is the sole source for the
  Gateway relay URL and MiniCPM model ID. The input limit is fixed at 16,384
  tokens.
- Moderation SHALL run asynchronously after the idle event and SHALL NOT delay
  the worker response or user-message submission.
- User messages SHALL be used only as context. The moderator SHALL never run on
  user-message arrival and SHALL never classify a user message as the response.
- Decision files SHALL be written under
   `${XDG_STATE_HOME:-$HOME/.local/state}/opencode/local-response-moderator/<sessionID>/`.
- Every status event and every decision outcome SHALL produce its own YAML
  file; missing files SHALL be treated as an observability failure.

## Acceptance

- Every moderation outcome produces one visible, passive transcript trace with
  the configured model, decision type, audit decision ID, and concise reason.
- `PASS` produces a passive trace without starting a new agent turn.
- `CONTINUE_PROGRESS` and `CONTINUE_NO_PROGRESS` each produce one corrective
  prompt visible as a persisted user message in the same transcript.
- Three consecutive MiniCPM no-progress decisions produce a visible escalation
  trace and no further automatic prompt.
- A fenced `sudo` command produces a visible root-blocked trace and no automatic
  prompt.
- A root-blocked or MiniCPM `BLOCKED` outcome records branch-scoped passive
  discussion context. This state survives restart and clears only after final
  accepted `PASS`.
- The client displays model-labeled checking and outcome feedback.
- The request includes all todos and the last three real user messages and does
  not exceed 16,384 input tokens.
- Repeated idle notification for one response produces at most one classifier
  request.
- A Build response ending in `tool-calls` produces no moderation action; the
  subsequent terminal parent response is moderated exactly once.
- The existing MiniCPM5 service and Make targets remain the only inference
  deployment mechanism, reached exclusively through the Gateway relay.
- A new system SHALL be installable with `make install-opencode-moderator`.
- Installation SHALL not modify moderator files when `oc` starts OpenCode.
- A fresh install under an isolated `XDG_CONFIG_HOME` SHALL produce one complete
  release containing the JavaScript adapter, Bash classifier, and rendered
  moderator configuration.
- Reinstallation SHALL atomically replace the active release without a mixed
  adapter/classifier/configuration state.
- `make verify-opencode-moderator` SHALL detect source drift, an invalid shell
  script, a non-executable classifier, an unreachable Gateway, and an absent
  configured model.
- `make status-opencode-moderator` SHALL report installed release metadata and
  `make uninstall-opencode-moderator` SHALL remove only moderator-owned files.
- Deployment tests SHALL execute the actual installer in an isolated
  `XDG_CONFIG_HOME`; source-string assertions alone are not acceptance coverage.
- An integration test SHALL load the actual plugin module, invoke its returned
  idle-event hook with test SDK clients, and verify every trace path, model
  attribution, false-pass prevention, toasts, classification, and persisted
  corrective prompting.
- An isolated OpenCode server test SHALL verify plugin discovery and event
  dispatch using the installed plugin contract.
- Moderator JavaScript tests SHALL run with
  `/home/agent/.bun/bin/bun test tests/integration/local-response-moderator-machine.test.js tests/integration/local-response-moderator.test.js`.
  The isolated runtime procedure is defined by
  [SPEC-OPENCODE-ISOLATED-INTEGRATION-TESTS](../specifications/SPEC-OPENCODE-ISOLATED-INTEGRATION-TESTS.md).

## Finite-State-Machine Architecture

The runtime SHALL use one dependency-free, pure reducer per session. The
reducer is the sole authority for moderation policy: it accepts an immutable
state and one named event, validates the transition, and returns the next state
plus ordered named effects. SDK calls, Bash classifier invocation, filesystem
writes, timers, and toasts SHALL execute outside the reducer and SHALL report
their result through a new event. No effect implementation may choose a state
transition.

The installed release SHALL contain the thin OpenCode adapter,
`local-response-moderator-machine.js`, the Bash classifier, and `config.json`.
The adapter owns event-hook wiring, one FIFO queue per session, effect execution,
and conversion between OpenCode/SDK data and machine events. The machine module
owns states, events, guards, transition table, initial state, and no I/O.

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
the current phase; it SHALL not silently fall through.

Effects SHALL be declarative values from this closed set:

```text
LOAD_CONTEXT, WRITE_DECISION, WRITE_TRACE, SHOW_TOAST, CLASSIFY,
SEND_CONTINUATION, VERIFY_PROMPT, WAIT_FOR_BUSY
```

The adapter SHALL execute effects in order. It SHALL append every effect result
to the relevant decision evidence and enqueue its corresponding result event.
`WRITE_DECISION` SHALL precede an externally visible trace or prompt that claims
that decision. Failed persistence, prompt verification, classifier, transport,
or toast operations SHALL enter `ERROR` visibly; they SHALL never imply a pass.

### Queue, Recovery, And Persistence

One serialized FIFO queue SHALL exist per session. The event hook SHALL enqueue
all relevant lifecycle events and return without awaiting moderation. While an
effect is active, later idle generations remain queued. A queued idle generation
SHALL be consumed once and only once after the preceding transition finishes.

Each completed transition SHALL write an atomic decision record containing the
previous phase, event type, guard results, next phase, emitted effects, effect
results, state snapshot, and existing required audit fields. Restore SHALL fold
the latest valid snapshots in chronological decision-record order. An incomplete
or corrupt record SHALL be observable and SHALL not manufacture a completed
claim. Recoverable errors SHALL release the in-flight assistant claim so the
same completed assistant can be retried deliberately.

Only final accepted `PASS` clears the blocker scope. A new real-user cycle resets
only `consecutiveNoProgressCount`; it clears blocker scope only when its user
message is outside the blocker-originating branch. Compaction lifecycle events
remain observable and cannot change retry, blocker, or completion state.

### Verification Requirements

The machine module SHALL have direct transition tests independent of OpenCode,
Bun subprocesses, the filesystem, and MiniCPM. Tests SHALL cover every phase
and every accepted event, invalid-event handling, effect order, duplicate idle
events, queued idle generations, branch-scoped blockers, restart restoration,
format-retry exhaustion, required-todo rejection, three no-progress escalation,
and error recovery. Adapter integration tests SHALL verify that each emitted
effect calls its installed SDK or classifier boundary exactly once and feeds the
observed result back to the machine.

The implementation SHALL use random temporary files for classifier snapshots and
captures, paginate message history when necessary, and preserve complete atomic
decision records including timings, raw classifier exchange, prompt/action
results, and the final state transition.
