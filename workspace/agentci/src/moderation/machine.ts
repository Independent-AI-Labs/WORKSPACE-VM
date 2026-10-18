import type {
  Effect,
  ModerationEvent,
  ModerationState,
  Phase,
  TransitionResult,
  Verdict,
} from "./types.ts";

const PHASES: readonly Phase[] = ["IDLE", "OBSERVING", "CLASSIFYING", "CONTINUING", "ERROR"];
const ESCALATION_LIMIT = 3;

type BusyEvent = Extract<ModerationEvent, { type: "STATUS_BUSY" }>;
type IdleEvent = Extract<ModerationEvent, { type: "STATUS_IDLE" }>;
type ContextEvent = Extract<ModerationEvent, { type: "CONTEXT_LOADED" }>;
type ResultEvent = Extract<ModerationEvent, { type: "CLASSIFIER_RESULT" }>;
type ContinuationPersistedEvent = Extract<ModerationEvent, { type: "CONTINUATION_PERSISTED" }>;
type ContinuationFinishedEvent = Extract<ModerationEvent, { type: "BUSY_VERIFIED" | "CONTINUATION_TIMEOUT" }>;
type CompactionStartedEvent = Extract<ModerationEvent, { type: "COMPACTION_STARTED" }>;
type CompactionFinishedEvent = Extract<ModerationEvent, { type: "COMPACTION_AUTOCONTINUE" | "COMPACTION_COMPLETED" }>;
type EffectErrorEvent = Extract<ModerationEvent, { type: "EFFECT_ERROR" }>;

export function createInitialState(): ModerationState {
  return {
    phase: "IDLE",
    inflightAssistantID: null,
    lastTerminalAssistantID: null,
    realUserCycleID: null,
    consecutiveNoProgressCount: 0,
    blocker: null,
    compaction: { active: false },
  };
}

export function normalizeRestoredState(state: ModerationState): ModerationState {
  const reclassify = state.phase === "CLASSIFYING";
  return {
    phase: "IDLE",
    inflightAssistantID: null,
    lastTerminalAssistantID: reclassify ? null : state.lastTerminalAssistantID,
    realUserCycleID: state.realUserCycleID,
    consecutiveNoProgressCount: state.consecutiveNoProgressCount,
    blocker: state.blocker,
    compaction: { active: state.compaction.active },
  };
}

export function isValidState(state: ModerationState): boolean {
  return Boolean(
    state
      && PHASES.includes(state.phase)
      && Number.isInteger(state.consecutiveNoProgressCount)
      && state.compaction
      && typeof state.compaction.active === "boolean",
  );
}

export function transition(state: ModerationState, event: ModerationEvent): TransitionResult {
  if (!isValidState(state) || !event || typeof event.type !== "string") {
    return ignored(createInitialState(), event, "invalid-state-or-event");
  }
  switch (event.type) {
    case "STATUS_BUSY":
      return onBusy(state, event);
    case "STATUS_IDLE":
      return state.phase === "OBSERVING" ? onIdle(state, event) : ignored(state, event, "idle-outside-observation");
    case "CONTEXT_LOADED":
      return state.phase === "OBSERVING" ? onContextLoaded(state, event) : ignored(state, event, "context-outside-observation");
    case "CLASSIFIER_RESULT":
      return state.phase === "CLASSIFYING" ? classifierResult(state, event) : ignored(state, event, "result-outside-classification");
    case "CONTINUATION_PERSISTED":
      return state.phase === "CONTINUING" ? continuationPersisted(state, event) : ignored(state, event, "continuation-outside-continuing");
    case "BUSY_VERIFIED":
    case "CONTINUATION_TIMEOUT":
      return state.phase === "CONTINUING" ? continuationFinished(state, event) : ignored(state, event, "continuation-outside-continuing");
    case "COMPACTION_STARTED":
      return compactionStarted(state, event);
    case "COMPACTION_AUTOCONTINUE":
    case "COMPACTION_COMPLETED":
      return compactionFinished(state, event);
    case "EFFECT_ERROR":
      return effectError(state, event);
    case "TRACE_PERSISTED":
      return ignored(state, event, "trace-recorded");
    default:
      return assertNeverEvent(event);
  }
}

function assertNeverEvent(event: never): never {
  throw new Error(`AgentCI moderation received an unknown event: ${JSON.stringify(event)}`);
}

function onBusy(state: ModerationState, event: BusyEvent): TransitionResult {
  if (state.phase === "IDLE" || state.phase === "ERROR") {
    return result({ ...state, phase: "OBSERVING" }, event, [decision("status-busy")]);
  }
  return result(state, event, [decision("status-busy")]);
}

function onIdle(state: ModerationState, event: IdleEvent): TransitionResult {
  if (state.phase !== "OBSERVING") return ignored(state, event, "idle-outside-observation");
  return result(state, event, [loadContext(), decision("status-idle")]);
}

function onContextLoaded(state: ModerationState, event: ContextEvent): TransitionResult {
  const gate = evaluateContext(event);
  const next = withContext(state, event);
  if (gate.kind === "ignored") {
    const reset = { ...next, phase: "IDLE" as const };
    return {
      state: reset,
      effects: [decision(gate.reason)],
      ignored: true,
      transition: { previousPhase: state.phase, event: event.type, nextPhase: reset.phase },
    };
  }
  if (gate.kind === "root-blocked") return rootBlocked(next, event);
  if (gate.kind === "blocker-discussion") return blockerDiscussion(next, event);
  return result({ ...next, phase: "CLASSIFYING" }, event, [decision("classifying"), toast("checking"), classify()]);
}

function blockerDiscussion(state: ModerationState, event: ContextEvent): TransitionResult {
  return result({ ...state, phase: "IDLE" }, event, [decision("blocker-discussion")]);
}

function rootBlocked(state: ModerationState, event: ContextEvent): TransitionResult {
  const blocker = { source: "operator-handoff" as const, originUserID: event.originUserID ?? state.realUserCycleID };
  return result(
    { ...state, phase: "IDLE", blocker },
    event,
    [decision("root-handoff"), trace(), toast("operator-handoff")],
  );
}

function classifierResult(state: ModerationState, event: ResultEvent): TransitionResult {
  const verdict = event.verdict;
  if (verdict.decision === "AGENT_COMPLETE") {
    return result(
      { ...state, phase: "IDLE", blocker: null, consecutiveNoProgressCount: 0 },
      event,
      [decision("moderation-complete"), trace(verdict), toast("complete")],
    );
  }
  if (verdict.decision === "AGENT_BLOCKED") {
    const blocker = state.blocker ?? { source: "agent-blocked" as const, originUserID: event.originUserID ?? state.realUserCycleID };
    return result(
      { ...state, phase: "IDLE", blocker },
      event,
      [decision("moderation-agent-blocked"), trace(verdict), toast("agent-blocked")],
    );
  }
  if (verdict.decision === "AGENT_STOPPED") {
    return result(
      { ...state, phase: "IDLE", blocker: null, consecutiveNoProgressCount: 0 },
      event,
      [decision("moderation-user-stop"), toast("user-stop")],
    );
  }
  const count = verdict.decision === "AGENT_CONTINUING"
    ? 0
    : state.consecutiveNoProgressCount + 1;
  if (count >= ESCALATION_LIMIT) {
    return result(
      { ...state, phase: "IDLE", consecutiveNoProgressCount: count },
      event,
      [decision("moderation-escalated"), toast("escalated")],
    );
  }
  return result(
    { ...state, phase: "CONTINUING", consecutiveNoProgressCount: count },
    event,
    [decision("moderation-continue"), toast("continuing"), sendContinuation(verdict)],
  );
}

function continuationPersisted(state: ModerationState, event: ContinuationPersistedEvent): TransitionResult {
  return result(state, event, [verifyPrompt(), waitForBusy(), decision("continuation-persisted")]);
}

function continuationFinished(state: ModerationState, event: ContinuationFinishedEvent): TransitionResult {
  const effects = [decision(event.type === "BUSY_VERIFIED" ? "continuation-verified" : "continuation-timeout")];
  if (event.type === "CONTINUATION_TIMEOUT") effects.push(toast("continuation-error"));
  return result({ ...state, phase: "IDLE" }, event, effects);
}

function compactionStarted(state: ModerationState, event: CompactionStartedEvent): TransitionResult {
  return result(
    { ...state, compaction: { active: true } },
    event,
    [decision("compaction-started")],
  );
}

function compactionFinished(state: ModerationState, event: CompactionFinishedEvent): TransitionResult {
  return result({ ...state, compaction: { ...state.compaction, active: false } }, event, [decision("compaction-completed")]);
}

function effectError(state: ModerationState, event: EffectErrorEvent): TransitionResult {
  if (state.phase === "ERROR") return result(state, event, [decision("moderation-error"), toast("error")]);
  return result(
    { ...state, phase: "ERROR", inflightAssistantID: null, lastTerminalAssistantID: null },
    event,
    [decision("moderation-error"), toast("error")],
  );
}

function withContext(state: ModerationState, event: ContextEvent): ModerationState {
  const claimedAssistantID = event.terminal && event.assistantID ? event.assistantID : null;
  return {
    ...state,
    inflightAssistantID: claimedAssistantID ?? state.inflightAssistantID,
    lastTerminalAssistantID: claimedAssistantID ?? state.lastTerminalAssistantID,
    realUserCycleID: event.realUserCycleID ?? state.realUserCycleID,
    consecutiveNoProgressCount: isNewCycle(state, event) ? 0 : state.consecutiveNoProgressCount,
    blocker: event.blockerBranch === false && isNewCycle(state, event) ? null : state.blocker,
  };
}

type ContextGate =
  | { kind: "ignored"; reason: string }
  | { kind: "root-blocked" }
  | { kind: "blocker-discussion" }
  | { kind: "classify" };

function evaluateContext(event: ContextEvent): ContextGate {
  if (event.assistantError) return { kind: "ignored", reason: "ignored-cancellation" };
  if (event.terminal === false) return { kind: "ignored", reason: "ignored-nonterminal-assistant" };
  if (event.assistantPresent === false) return { kind: "ignored", reason: "ignored-no-completed-assistant" };
  if (event.duplicate || !event.assistantID) return { kind: "ignored", reason: "ignored-duplicate" };
  if (event.compaction) return { kind: "ignored", reason: "ignored-compaction" };
  if (event.planMode) return { kind: "ignored", reason: "ignored-plan-mode" };
  if (event.build === false) return { kind: "ignored", reason: "ignored-non-build-agent" };
  if (event.userNewer) return { kind: "ignored", reason: "ignored-no-completed-assistant" };
  if (event.moderatorTrace) return { kind: "ignored", reason: "ignored-moderator-trace" };
  if (event.rootBlocked) return { kind: "root-blocked" };
  if (event.blockerDiscussionActive) return { kind: "blocker-discussion" };
  return { kind: "classify" };
}

function isNewCycle(state: ModerationState, event: ContextEvent): boolean {
  return event.newCycle ?? (event.realUserCycleID != null && event.realUserCycleID !== state.realUserCycleID);
}

function result(state: ModerationState, event: ModerationEvent, effects: Effect[], phase?: Phase): TransitionResult {
  const next = phase ? { ...state, phase } : state;
  return {
    state: next,
    effects,
    ignored: false,
    transition: { previousPhase: state.phase, event: event.type, nextPhase: next.phase },
  };
}

function ignored(state: ModerationState, event: ModerationEvent | undefined, reason: string): TransitionResult {
  return {
    state,
    effects: [decision(reason)],
    ignored: true,
    transition: { previousPhase: state.phase, event: event?.type ?? "INVALID", nextPhase: state.phase },
  };
}

function decision(decisionType: string): Effect {
  return { type: "WRITE_DECISION", decisionType };
}

function trace(verdict?: Verdict): Effect {
  return { type: "WRITE_TRACE", verdict };
}

function toast(kind: string): Effect {
  return { type: "SHOW_TOAST", kind };
}

function classify(): Effect {
  return { type: "CLASSIFY" };
}

function sendContinuation(verdict: Verdict): Effect {
  return { type: "SEND_CONTINUATION", verdict };
}

function verifyPrompt(): Effect {
  return { type: "VERIFY_PROMPT" };
}

function waitForBusy(): Effect {
  return { type: "WAIT_FOR_BUSY" };
}

function loadContext(): Effect {
  return { type: "LOAD_CONTEXT" };
}
