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
  replay.ts       operator replay of the last moderation decision
workspace/agentci/scripts/
  source-classifier-cases.mjs   history miner for regression cases
workspace/agentci/tests/
  classifier-cases.test.ts      manifest integrity and prompt invariants
  classifier-cases.live.ts      mined-case live assertion
  support/classifier-cases.ts   manifest plus transcript-body loader
  fixtures/classifier-cases.json          tracked manifest
  fixtures/transcripts/<hash>.json        gitignored transcript bodies
  fixtures/reducer-cases.json
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
inflightAssistantID      assistant claim in progress
lastTerminalAssistantID  last moderated terminal assistant
realUserCycleID          latest real user turn id
consecutiveNoProgressCount
blocker                  null | { source, originUserID }
compaction               { active }
```

Turn completion is keyed on the completed assistant message identity, not on a
busy/idle counter. Duplicate suppression (`inflightAssistantID` /
`lastTerminalAssistantID`) and stale-idle protection (phase gating) are derived
from that identity, so two representations of the same fact cannot desynchronize
across a restart.

`AGENT_COMPLETE`, `AGENT_BLOCKED`, `AGENT_STOPPED`, `OPERATOR_HANDOFF`, and
`ESCALATED` are
recorded outcomes in audit records, not durable phases. Blocker discussion is the
nullable `blocker` scope (`operator-handoff` or `agent-blocked`).
The reducer never retains message objects, clients, promises, or mutable
collections.

On restore, the folded snapshot is normalized by `normalizeRestoredState`: the
phase is coerced to `IDLE`, the in-flight assistant claim is cleared, and an
unfinished `CLASSIFYING` claim also clears `lastTerminalAssistantID` so that turn
is re-evaluated. Continuation-start verification uses an adapter-local, in-memory
busy observation that is never persisted and never compared against durable
state.

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

1. `STATUS_BUSY` enters `OBSERVING`; the subsequent `STATUS_IDLE` loads context.
   A duplicate idle for an already-moderated terminal assistant is suppressed by
   the assistant-identity guard, so the same response is never moderated twice.
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
5. Otherwise MiniCPM classifies. The request places the latest assistant response
   first, labeled as the decision target, then the last three real user prompts,
   then the tracked todos, with a one-line instruction immediately above that
   data. An empty or whitespace-only latest user message is represented by an
   explicit continue sentinel rather than dropped, so an interrupted, cancelled,
   aborted, errored, or cleared turn is never treated as a halt. MiniCPM is the
   single authority on completion and applies the ordered procedure in
   "Classifier Prompt And Input Layout" below. The todo state is classifier
   input, not a controller override, so a returned `AGENT_COMPLETE` stands even
   when todos remain `pending` or `in_progress`, and a returned `AGENT_STOPPED`
   stands over unfinished work.
   Input is trimmed to 16,384 tokens via the Gateway token endpoint.
   Output is exactly two YAML lines enforced by the Gateway GBNF grammar;
   malformed or non-`stop` output is traced and retried three times, then
   reported as a visible classifier error. Each request pins deterministic
   greedy sampling (`temperature` 0, `top_k` 1, `top_p` 1, `min_p` 0, fixed
   seed) and sets `cache_prompt: false`; the serving model pins the same and
   runs single-slot with a fixed thread count. Prompt caching must stay off:
   llama.cpp reuses a cached prefix with a different batch shape, and the
   resulting logits are not bit-identical, so verdicts flip between runs even
   at temperature 0. With caching off, identical inputs yield identical
   verdicts across runs.
6. `AGENT_COMPLETE` writes a single-line passive status (`✅ Automated Moderation:
   work completion verified.`) and stays idle. `AGENT_CONTINUING` /
   `AGENT_STALLED` send a single-line corrective status through `promptAsync`
   as one message with two parts, both carrying moderation metadata: a synthetic
   directive (delivered to the model, not rendered) and a short visible note
   (rendered so the operator sees why the moderator spoke). The parts are
   excluded from later real-user context by metadata rather than text.
   `AGENT_BLOCKED` writes a single-line status and
   activates blocker-discussion scope. `AGENT_STOPPED` writes no transcript
   line, sends no prompt, and stays idle with a toast.
7. Three consecutive `AGENT_STALLED` outcomes in one real-user cycle produce
   `moderation-escalated` (toast + audit only) and stop automatic continuation.
8. Internal outcomes (blocker discussion, escalation, error) and a user stop
   write no transcript line. Audit files hold the full verdict, rulings, reason,
   and decision ID.

## Replay Path

`oc --run-mod [ses_ID]` sets `AGENTCI_RUN_MOD=1` (and `AGENTCI_RUN_MOD_SESSION`
when an id is given) and resumes the session in OpenCode. When the flag is set
and moderation is enabled, the plugin runs one replay on startup:

1. Resolve the target session: the explicit `AGENTCI_RUN_MOD_SESSION`, else the
   current project's most recently updated session from the OpenCode client's
   session list (the same session `--continue` resumes).
2. Wait until the session is readable, then select the last moderator-injected
   transcript line and the completed assistant response it followed.
3. Revert that injected line through the SDK (`session.revert` with its
   `messageID`), keeping the assistant response intact.
4. Resolve the verdict with a fresh classifier call over the current todos, the
   last three real user prompts, and that assistant response.
5. Reconcile the transcript to the new verdict, exactly as the moderation path:
   `AGENT_CONTINUING`/`AGENT_STALLED` send a corrective prompt through
   `promptAsync` (a new upstream turn); `AGENT_COMPLETE`/`AGENT_BLOCKED` write a
   passive status line; `AGENT_STOPPED` writes nothing.
6. Write a `REPLAY` audit record with the recomputed verdict and the reverted
   message id.

Replay is a one-shot startup action outside the per-session event queue; the
replayed session's later turns return to normal moderation. A failure (no
session, revert error, classifier error) is surfaced as a client toast and, when
a session is known, an error audit record; it is never treated as a completion.

## Classifier Prompt And Input Layout

The system prompt is a short ordered decision procedure. First match wins:

```text
1. AGENT_BLOCKED  when the assistant asks the user or operator to act or answer
                  before the agent can proceed.
                  AWAITING_OPERATOR: any external action, command, credential,
                  access, experiment, reproduction, observation, or reported
                  result the agent cannot perform itself.
                  AWAITING_USER: question, decision, approval, clarification.
                  A handoff stands even when the task is unfinished and even
                  when the assistant also promises later work.
2. AGENT_STOPPED  when the latest real user message explicitly halts, stops,
                  cancels, aborts, or waits.
3. AGENT_COMPLETE when the response fully satisfies the request.
4. AGENT_CONTINUING or AGENT_STALLED only when the agent can keep working on its
                  own. AGENT_STALLED stays a distinct decision.
```

The prompt states that the assistant response is the decision target. It states
that listing remaining work, or promising future work without asking the user to
act, is not a handoff. It contains examples for a handoff that asks the user to
act and report back, a launched-and-ready handoff, a game-up handoff, and a
decision question. It does not end with a continue instruction. An empty or
whitespace-only user message is a continue sentinel, not a halt, and that rule is
stated in the notes, not as the closing line.

The request layout is fixed and testable:

```text
<one-line instruction: judge the agent's latest response>
The agent's latest response (judge this):
<response>
User request(s):
- <prompt>
Tracked todos:
- [status] <content>
Reminder: if the response asks the user to run, test, play, listen, look,
check, confirm, report, or decide something, choose AGENT_BLOCKED. A question
to the user is a handoff.
```

The assistant response is first. The user request is context, never the decision
target. An empty or whitespace-only user message is replaced by the continue
sentinel `Continue the unfinished work.` The closing reminder corrects the small
model's observed bias toward continuing when a long response ends with a request
to the user. Unit tests assert the section order and labels. A frozen baseline
prompt fixture supports a live A/B against the predecessor prompt; the A/B
asserts the hardened prompt never newly stands down on unfinished work.

## Classifier Protocol

```text
decision: AGENT_COMPLETE    reason: WORK_COMPLETE
decision: AGENT_CONTINUING  reason: WORK_REMAINS
decision: AGENT_STALLED     reason: NO_PROGRESS
decision: AGENT_BLOCKED     reason: AWAITING_USER | AWAITING_OPERATOR
decision: AGENT_STOPPED     reason: USER_STOP
```

`temperature` 0, `max_tokens` 128, `grammar` = `MODERATION_GRAMMAR`, `stream`
false, `cache_prompt` false. `finish_reason` MUST be `stop`.

## Audit Persistence

One atomic JSON document (valid YAML 1.2) per completed transition under
`${XDG_STATE_HOME:-$HOME/.local/state}/opencode/agentci/moderation/<sessionID>/`,
named `decision-<timestamp>-<random>.yaml`. Each record contains the event type,
decision type, guard/ignored result, previous and next phase, emitted effects,
effect results, verdict, error, and the durable state snapshot. A
`CLASSIFIER_RESULT` record also embeds a `capture` object inline: the exact
messages sent, the raw completion, the model, the sampling settings, the seed,
the attempt count, and the request duration. Non-classifier records omit
`capture` and instead persist `eventPayload`, the replayable event without the
session ID. Every record carries `schemaVersion`. The capture is part of the
existing record; there is no separate
capture file, and auditing a decision does not require reconstructing the input
from the session database. Directories are
`0700`; files are written atomically (`0600`, temp + rename). `state.yaml`
mirrors the latest durable snapshot for restart restoration. An operator replay
writes a `REPLAY` event record (with the recomputed verdict and the reverted
message id) in the same directory.

## Failure Mining And Test Case Sourcing

The regression suite is grown from real history. The classifier verdict is not
ground truth; the user reaction after the verdict is the signal.

Sources (read-only):
- Audit decisions at `.../agentci/moderation/<sessionID>/decision-*.yaml`
  (JSON body). `previousState.inflightAssistantID` gives the assistant identity
  for a `CLASSIFIER_RESULT`.
- Shard databases `~/.local/share/opencode/shard-<hash>.db`, mapped by
  `shards.tsv`. `message` and `part` hold the current transcript.
- The append-only `event` table holds removed-message content.

Failure signals:
- False continue: verdict `AGENT_CONTINUING` or `AGENT_STALLED` with
  `SEND_CONTINUATION` persisted, followed within the window by
  `message.data.error.name = "MessageAbortedError"`, or a `message.removed.1`
  event for a moderator line.
- False stop: verdict `AGENT_BLOCKED`, `AGENT_COMPLETE`, or `AGENT_STOPPED`,
  followed within the window by a `message.removed.1` event for a moderator
  line. A normal user reply is expected and is not a failure signal.
- Window: 300 seconds by default, configurable.
- Aborts come from `message.data.error.name`. Removals come from
  `event.type = "message.removed.1"`; the removed content is reconstructed from
  earlier `message.updated.1` and `message.part.updated.1` rows because the
  `message` row is deleted. `session.revert` is transient and is not used.

Case shape: provenance (`sessionID`, `assistantID`, `decisionID`), `forbiddenDecision`,
optional `expectedDecision`, `labelSource` (`mined` or `operator`), a stable
content hash, and a `transcript` reference. A mined case asserts the
forbidden-decision constraint. An operator-confirmed case asserts the exact
expected decision. Transcript bodies (`previousResponse`, `userMessages`,
`todos`) live in `tests/fixtures/transcripts/<hash>.json` and are gitignored,
mirroring the transcript-classifier benchmark. They are machine-local data
regenerated from the session database. Only the metadata manifest, the reducer
fixture, and the ledger are tracked.

Sourcing script `scripts/source-classifier-cases.mjs`:
- Reads the audit directory and the shard databases, never writes them.
- Pairs each `CLASSIFIER_RESULT` with its assistant identity and transcript.
- Emits the classifier manifest to `tests/fixtures/classifier-cases.json` and
  each transcript body to `tests/fixtures/transcripts/<hash>.json`.
- Emits non-classifier reducer cases to `tests/fixtures/reducer-cases.json`.
- Keeps a consumed-decision ledger at `tests/fixtures/source-ledger.json`.
- Appends only unseen hashes and unconsumed decision IDs. Re-running over
  imported data writes nothing.
- Mines only records whose state shape carries the current schema version, so
  obsolete pre-fix states are not replayed.
- Atomic temp+rename write, deterministic sort by hash, and a body is rewritten
  only when its content changes.
- Reports added, skipped, total, and per-pathway coverage.
- Supports `--dry-run`, `--since`, and `--rebuild`. `--rebuild` re-derives every
  transcript body from its provenance and fails when a hash changes.
- Each run adds up to five fresh non-classifier cases from real decision
  records exercising ignored, duplicate, cancellation, compaction, timeout, or
  escalation paths. A shortage is reported.
- Runs as a development tool only. It is never imported by the shipped bundle.

The live suite `tests/classifier-cases.live.ts` runs each case through the
Gateway with a configurable case limit and asserts the exact or forbidden
decision. It is excluded from hermetic CI and requires the local transcript
bodies; a missing body fails with the single regeneration command.
`tests/classifier-cases.test.ts` validates the manifest offline: unique hashes,
pathway coverage, provenance, and the transcript reference. When bodies are
present it additionally verifies each body hash and the exact input layout.


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
  tests, adapter integration tests, fixture integrity tests, prompt invariants,
  input layout, mined reducer cases, and the packaged release entrypoint test.
- `npm run source-cases`: mine new regression cases from history. Idempotent;
  writes nothing when no new data exists.
- `npm run test:cases:live`: bounded mined-case classifier suite
  (`classifier-cases.live.ts`). Excluded from hermetic CI.
- `npm run test:prompt-ab`: live A/B of the hardened prompt against the frozen
  baseline prompt over the empty-message, handoff, and stop scenarios. It
  asserts the hardened prompt never newly stands down on unfinished work.
- `npm run test:release`: `npm pack` install path.
- `npm run test:live` (`make test-agentci-e2e`): real OpenCode loads the
  installed release under a temporary `HOME`/XDG root and writes moderation
  decision records; drives the build and title agents with the local MiniCPM5
  model through the Workspace Gateway's `workspace-gw-llamafile-no-auth`
  provider, pinning the title agent with `small_model` so no remote provider is
  contacted, and copies the test user's `auth.json` into the temporary data
  root. An operator may override the build model with `AGENTCI_LIVE_MODEL`.
  Excluded from hermetic CI.