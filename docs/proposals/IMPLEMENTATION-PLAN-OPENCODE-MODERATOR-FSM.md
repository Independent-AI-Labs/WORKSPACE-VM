# Implementation Plan: OpenCode Moderator Finite-State Machine

**Status:** Superseded - requirements replaced by REQ-AGENTCI-RESPONSE-MODERATION
**Date:** 2026-08-10  
**Requirements:** [REQ-AGENTCI-RESPONSE-MODERATION](../requirements/REQ-AGENTCI-RESPONSE-MODERATION.md)
**Specification:** [SPEC-OPENCODE-RESPONSE-MODERATOR](../specifications/SPEC-OPENCODE-RESPONSE-MODERATOR.md)

## Scope

Replace the local response moderator's mutable maps and imperative decision
branches with a dependency-free, pure reducer and a per-session event queue.
Preserve existing classifier, deployment, transcript, audit, and Gateway
contracts. Do not introduce XState, Temporal, a database, a service, or a
second classifier protocol.

## Checklist-Free Amendment

The original checklist and second-adjudication backlog is superseded. A terminal
Build response shall not be asked to self-certify with `[WORK DONE]`. The
controller resolves deterministic facts before MiniCPM and calls MiniCPM only
for a semantically ambiguous terminal response. A required high-priority todo in
`pending` or `in_progress` with no explicit blocker makes `PASS` impossible; a
legitimate exception is represented by structured blocker facts or `BLOCKED`.

### 1. Make Completion Eligibility Deterministic

- [ ] Change the reducer so required open work with no explicit blocker becomes
  controller-only `CONTINUE_REQUIRED_WORK` with `WORK_REMAINS`, without a
  MiniCPM request or a no-progress counter mutation.
- [ ] Preserve `BLOCKED` as the only legitimate non-continuation exception for
  external blockers, clarification, or approved non-required deferral.
- [ ] Remove second-pass adjudication events, classifier calls, captures, and
  tests.
- [ ] Add a regression fixture from session
  `ses_0286484d8ffedoI4tw2MgDjRUd`: markerless progress plus required open
  todos and MiniCPM `PASS` must continue.

**Exit condition:** A classifier `PASS` cannot override required todo state.

### 2. Collapse Lifecycle State

- [ ] Reduce lifecycle phases to `IDLE`, `OBSERVING`, `CLASSIFYING`,
  `CONTINUING`, and recoverable `ERROR`.
- [ ] Record pass, block, root block, and escalation as decision outcomes, not
  durable phases.
- [ ] Keep blocker scope as nullable branch context and compaction as orthogonal
  metadata.
- [ ] Update snapshots, restore validation, transition tests, and audit records
  for the reduced state shape.

**Exit condition:** The reducer has no marker/checklist/adjudication lifecycle
state and no outcome phase retained beyond its decision record.

### 3. Verify And Deploy

- [ ] Run direct reducer tests and installed-release Bun integration tests from
  an external working directory.
- [ ] Run shell syntax, source-length, `git diff --check`, installer verify, and
  status checks.
- [ ] Restart OpenCode and replay the markerless-open-todo false-pass scenario.

**Exit condition:** The installed release continues rather than passes that
scenario, and no second classifier request occurs for a completion pass.

## Completion Criteria

- Every policy decision is made by `transition(state, event)`.
- The adapter has no independent policy maps for claims, retries, blockers, or
  actor phase.
- Every SDK, filesystem, classifier, timeout, and toast operation is an emitted
  effect with a recorded result event.
- Each decision record contains previous state, event, guards, next state,
  effects, effect results, and a validated state snapshot.
- Unit transition coverage and installed-release integration coverage pass.
- The active release includes the new machine module and verifies source drift.

## Deferred Work

Do not add XState unless the dependency-free reducer proves unable to represent
required independent concurrent regions. Do not add workflow infrastructure
unless moderation needs durable execution across process/service boundaries that
atomic decision records and queue recovery cannot satisfy.
