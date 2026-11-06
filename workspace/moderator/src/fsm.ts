import type {
  DecisionType,
  Effect,
  ModerationEvent,
  ModerationState,
  Phase,
  ToastKind,
  TransitionResult,
  TurnFact,
  Verdict,
} from "./types.ts";

const PHASES: readonly Phase[] = ["IDLE", "OBSERVING", "CLASSIFYING", "CONTINUING", "ERROR"];
const ESCALATION_LIMIT = 3;
const BLOCKER_SOURCES = ["operator-handoff", "agent-blocked"] as const;
type EventType = ModerationEvent["type"];

const EVENT_PHASES: Record<EventType, readonly Phase[]> = {
  STATUS_BUSY: PHASES,
  TURN_ENDED: ["OBSERVING"],
  CONTEXT_LOADED: ["OBSERVING"],
  VERDICT: ["CLASSIFYING"],
  CANCELLED: ["CLASSIFYING", "CONTINUING"],
  CONTINUATION_PERSISTED: ["CONTINUING"],
  NEW_USER_CYCLE: PHASES,
  COMPACTION_STARTED: PHASES,
  COMPACTION_COMPLETED: PHASES,
  TRACE_PERSISTED: PHASES,
  EFFECT_ERROR: PHASES,
  REPLAY: ["IDLE", "ERROR"],
};

const ELIGIBILITY: readonly { flag: string; decisionType: DecisionType; match: (turn: TurnFact) => boolean }[] = [
  { flag: "nonterminal", decisionType: "ignored-nonterminal", match: (turn) => !turn.terminal },
  { flag: "assistant-error", decisionType: "ignored-assistant-error", match: (turn) => turn.assistantError },
  { flag: "plan-mode", decisionType: "ignored-plan-mode", match: (turn) => turn.planMode },
  { flag: "compaction", decisionType: "ignored-compaction", match: (turn) => turn.compaction },
  { flag: "newer-user", decisionType: "ignored-newer-user", match: (turn) => turn.userNewer },
  { flag: "moderator-trace", decisionType: "ignored-moderator-trace", match: (turn) => turn.moderatorTrace },
  { flag: "duplicate", decisionType: "ignored-duplicate", match: (turn) => turn.duplicate },
];

export class ModerationStateError extends Error {
  constructor(reason: string) {
    super(`moderator received an invalid state: ${reason}`);
    this.name = "ModerationStateError";
  }
}

export function createInitialState(): ModerationState {
  return {
    phase: "IDLE",
    inflightAssistantID: null,
    lastTerminalAssistantID: null,
    realUserCycleID: null,
    consecutiveNoProgressCount: 0,
    blocker: null,
    compactionActive: false,
    pendingContext: null,
  };
}

export function normalizeRestoredState(state: ModerationState): ModerationState {
  return {
    phase: "IDLE",
    inflightAssistantID: null,
    lastTerminalAssistantID: state.phase === "CLASSIFYING" ? null : state.lastTerminalAssistantID,
    realUserCycleID: state.realUserCycleID,
    consecutiveNoProgressCount: state.consecutiveNoProgressCount,
    blocker: state.blocker,
    compactionActive: false,
    pendingContext: null,
  };
}

export function isValidState(input: unknown): input is ModerationState {
  if (typeof input !== "object" || input === null || Array.isArray(input)) return false;
  const state = input as Record<string, unknown>;
  if (!PHASES.includes(state.phase as Phase)) return false;
  if (!isNullableString(state.inflightAssistantID)) return false;
  if (!isNullableString(state.lastTerminalAssistantID)) return false;
  if (!isNullableString(state.realUserCycleID)) return false;
  if (typeof state.consecutiveNoProgressCount !== "number" || !Number.isInteger(state.consecutiveNoProgressCount) || state.consecutiveNoProgressCount < 0) return false;
  if (typeof state.compactionActive !== "boolean") return false;
  if (!isBlocker(state.blocker)) return false;
  return isContextFact(state.pendingContext);
}

export function transition(state: ModerationState, event: ModerationEvent): TransitionResult {
  if (!isValidState(state)) throw new ModerationStateError("field shapes are invalid");
  const accepted = EVENT_PHASES[event.type];
  if (accepted === undefined) throw new ModerationStateError(`unknown event '${String((event as { type?: unknown }).type)}'`);
  if (!accepted.includes(state.phase)) return ignored(state, event);
  const outcome = dispatch(state, event);
  return { ...outcome, transition: { previousPhase: state.phase, event: event.type, nextPhase: outcome.state.phase } };
}

function dispatch(state: ModerationState, event: ModerationEvent): TransitionResult {
  switch (event.type) {
    case "STATUS_BUSY": return result({ ...state, phase: "OBSERVING" }, [decision("status-busy")]);
    case "TURN_ENDED": return onTurnEnded(state, event.turn);
    case "CONTEXT_LOADED": return onContextLoaded(state, event.turn, event.originUserID);
    case "VERDICT": return onVerdict(state, event.verdict, event.originUserID);
    case "CANCELLED": return result({ ...state, phase: "IDLE", inflightAssistantID: null }, [decision("cancelled", "cancelled")]);
    case "CONTINUATION_PERSISTED": return result({ ...state, phase: "OBSERVING" }, [verifyPrompt(), decision("continuation-persisted")]);
    case "NEW_USER_CYCLE": return onNewUserCycle(state, event.originUserID, event.sameBranch);
    case "COMPACTION_STARTED": return result(state.compactionActive ? state : { ...state, compactionActive: true }, [decision("compaction-started")]);
    case "COMPACTION_COMPLETED": return result({ ...state, compactionActive: false }, [decision("compaction-completed")]);
    case "TRACE_PERSISTED": return result(state, [decision("trace-recorded")]);
    case "EFFECT_ERROR": return result({
      ...state,
      phase: "ERROR",
      inflightAssistantID: null,
      lastTerminalAssistantID: state.lastTerminalAssistantID === state.inflightAssistantID ? null : state.lastTerminalAssistantID,
    }, [decision("moderation-error"), toast("error")]);
    case "REPLAY": return onReplay(state, event.turn);
  }
}

function onReplay(state: ModerationState, turn: TurnFact): TransitionResult {
  const skip = eligibilitySkip(turn);
  if (turn.assistantID === null || skip !== null) {
    return eligibilityResult({ ...state, phase: "IDLE", pendingContext: null }, "REPLAY", skip ?? { flag: "nonterminal", decisionType: "ignored-nonterminal" });
  }
  return result({
    ...state,
    phase: "CLASSIFYING",
    inflightAssistantID: turn.assistantID,
    pendingContext: {
      assistantID: turn.assistantID,
      userMessageID: turn.userMessageID,
      agentMode: turn.agentMode,
      todosOpen: turn.todosOpen,
    },
  }, [decision("checking"), toast("checking"), classify()]);
}

function onTurnEnded(state: ModerationState, turn: TurnFact): TransitionResult {
  return result({
    ...state,
    phase: "OBSERVING",
    inflightAssistantID: turn.assistantID,
    pendingContext: turn.assistantID === null ? null : {
      assistantID: turn.assistantID,
      userMessageID: turn.userMessageID,
      agentMode: turn.agentMode,
      todosOpen: turn.todosOpen,
    },
  }, [loadContext(), decision("status-busy")]);
}

function onContextLoaded(state: ModerationState, turn: TurnFact, originUserID: string | null): TransitionResult {
  const next = withContext(state, turn, originUserID);
  const skip = eligibilitySkip(turn);
  if (skip !== null) {
    return eligibilityResult({ ...next, phase: "IDLE", pendingContext: null }, "CONTEXT_LOADED", skip);
  }
  if (turn.rootBlocked) {
    const blocker = { source: "operator-handoff" as const, originUserID: originUserID ?? next.realUserCycleID };
    return result({ ...next, phase: "IDLE", blocker, pendingContext: null }, [decision("root-handoff"), trace(), toast("operator-handoff")]);
  }
  if (turn.blockerDiscussion) {
    return result({ ...next, phase: "IDLE", pendingContext: null }, [decision("blocker-discussion")]);
  }
  return result({ ...next, phase: "CLASSIFYING", pendingContext: null }, [decision("checking"), toast("checking"), classify()]);
}

function onVerdict(state: ModerationState, verdict: Verdict, originUserID: string | null): TransitionResult {
  const terminal = terminalState(state);
  if (verdict.decision === "AGENT_COMPLETE") {
    return result(terminal, [decision("moderation-complete"), trace(verdict), toast("complete")]);
  }
  if (verdict.decision === "AGENT_BLOCKED") {
    const blocker = { source: "agent-blocked" as const, originUserID: originUserID ?? state.realUserCycleID };
    return result({ ...terminal, blocker }, [decision("moderation-agent-blocked"), trace(verdict), toast("agent-blocked")]);
  }
  if (verdict.decision === "AGENT_STOPPED") {
    return result(terminal, [decision("moderation-user-stop"), toast("user-stop")]);
  }
  if (state.blocker !== null) {
    return result(terminal, [decision("moderation-complete"), trace(verdict), toast("complete")]);
  }
  if (state.phase === "CLASSIFYING" && state.consecutiveNoProgressCount >= ESCALATION_LIMIT) {
    return result({ ...terminal, phase: "IDLE" }, [decision("moderation-escalated"), toast("escalated")]);
  }
  const count = verdict.decision === "AGENT_STALLED" ? state.consecutiveNoProgressCount + 1 : state.consecutiveNoProgressCount;
  if (count >= ESCALATION_LIMIT) {
    return result({ ...state, phase: "IDLE", consecutiveNoProgressCount: count, inflightAssistantID: null }, [decision("moderation-escalated"), toast("escalated")]);
  }
  return result({ ...state, phase: "CONTINUING", consecutiveNoProgressCount: count }, [decision("moderation-continue"), trace(verdict), toast("continuing"), sendContinuation(verdict)]);
}

function onNewUserCycle(state: ModerationState, originUserID: string | null, sameBranch: boolean): TransitionResult {
  return result({
    ...state,
    phase: state.phase === "CLASSIFYING" || state.phase === "CONTINUING" ? "IDLE" : state.phase,
    inflightAssistantID: null,
    realUserCycleID: originUserID ?? state.realUserCycleID,
    consecutiveNoProgressCount: 0,
    blocker: sameBranch ? state.blocker : null,
    pendingContext: null,
  }, [decision("new-user-cycle", "new-user-cycle")]);
}

function withContext(state: ModerationState, turn: TurnFact, originUserID: string | null): ModerationState {
  return {
    ...state,
    inflightAssistantID: turn.assistantID ?? state.inflightAssistantID,
    realUserCycleID: originUserID ?? state.realUserCycleID,
    consecutiveNoProgressCount: turn.newCycle ? 0 : state.consecutiveNoProgressCount,
    blocker: turn.newCycle && !turn.blockerDiscussion ? null : state.blocker,
  };
}

function terminalState(state: ModerationState): ModerationState {
  return {
    ...state,
    phase: "IDLE",
    inflightAssistantID: null,
    lastTerminalAssistantID: state.inflightAssistantID ?? state.lastTerminalAssistantID,
    blocker: null,
    consecutiveNoProgressCount: 0,
    compactionActive: false,
    pendingContext: null,
  };
}

function result(state: ModerationState, effects: Effect[]): TransitionResult {
  return {
    state,
    effects,
    ignored: false,
    transition: { previousPhase: state.phase, event: "", nextPhase: state.phase },
  };
}

function ignored(state: ModerationState, event: ModerationEvent): TransitionResult {
  return { state, effects: [decision("ignored-outside-phase", "outside-phase")], ignored: true, transition: { previousPhase: state.phase, event: event.type, nextPhase: state.phase } };
}

function eligibilitySkip(turn: TurnFact): { flag: string; decisionType: DecisionType } | null {
  return ELIGIBILITY.find((row) => row.match(turn)) ?? null;
}

function eligibilityResult(state: ModerationState, event: string, skip: { flag: string; decisionType: DecisionType }): TransitionResult {
  return { state, effects: [decision(skip.decisionType, skip.flag)], ignored: true, transition: { previousPhase: state.phase, event, nextPhase: state.phase } };
}

function decision(decisionType: DecisionType, reason?: string): Effect {
  return reason === undefined ? { type: "WRITE_DECISION", decisionType } : { type: "WRITE_DECISION", decisionType, reason };
}

function trace(verdict?: Verdict): Effect {
  return { type: "WRITE_TRACE", verdict };
}

function toast(kind: ToastKind): Effect {
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

function loadContext(): Effect {
  return { type: "LOAD_CONTEXT" };
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isBlocker(value: unknown): value is ModerationState["blocker"] {
  if (value === null) return true;
  if (typeof value !== "object" || Array.isArray(value)) return false;
  const blocker = value as Record<string, unknown>;
  return typeof blocker.source === "string"
    && BLOCKER_SOURCES.includes(blocker.source as typeof BLOCKER_SOURCES[number])
    && isNullableString(blocker.originUserID);
}

function isContextFact(value: unknown): value is ModerationState["pendingContext"] {
  if (value === null) return true;
  if (typeof value !== "object" || Array.isArray(value)) return false;
  const fact = value as Record<string, unknown>;
  return typeof fact.assistantID === "string"
    && isNullableString(fact.userMessageID)
    && (fact.agentMode === "build" || fact.agentMode === "answer")
    && typeof fact.todosOpen === "number";
}
