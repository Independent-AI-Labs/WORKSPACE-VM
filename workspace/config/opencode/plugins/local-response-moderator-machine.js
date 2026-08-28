export const EVENT = Object.freeze({
  STATUS_BUSY: "STATUS_BUSY",
  STATUS_IDLE: "STATUS_IDLE",
  CONTEXT_LOADED: "CONTEXT_LOADED",
  ROOT_BLOCK_DETECTED: "ROOT_BLOCK_DETECTED",
  CLASSIFIER_RESULT: "CLASSIFIER_RESULT",
  CONTINUATION_PERSISTED: "CONTINUATION_PERSISTED",
  BUSY_VERIFIED: "BUSY_VERIFIED",
  CONTINUATION_TIMEOUT: "CONTINUATION_TIMEOUT",
  COMPACTION_STARTED: "COMPACTION_STARTED",
  COMPACTION_AUTOCONTINUE: "COMPACTION_AUTOCONTINUE",
  COMPACTION_COMPLETED: "COMPACTION_COMPLETED",
  EFFECT_ERROR: "EFFECT_ERROR",
})

export const EFFECT = Object.freeze({
  LOAD_CONTEXT: "LOAD_CONTEXT",
  WRITE_DECISION: "WRITE_DECISION",
  WRITE_TRACE: "WRITE_TRACE",
  SHOW_TOAST: "SHOW_TOAST",
  CLASSIFY: "CLASSIFY",
  SEND_CONTINUATION: "SEND_CONTINUATION",
  VERIFY_PROMPT: "VERIFY_PROMPT",
  WAIT_FOR_BUSY: "WAIT_FOR_BUSY",
})

const PHASES = new Set([
  "IDLE", "OBSERVING", "CLASSIFYING", "CONTINUING", "ERROR",
])

export function createInitialState() {
  return {
    phase: "IDLE",
    busyGeneration: 0,
    pendingIdleGenerations: [],
    inflightAssistantID: null,
    lastTerminalAssistantID: null,
    realUserCycleID: null,
    consecutiveNoProgressCount: 0,
    blocker: null,
    moderatorMessageIDs: [],
    compaction: { active: false, generation: 0 },
  }
}

export function isValidState(state) {
  return Boolean(
    state
    && PHASES.has(state.phase)
    && Number.isInteger(state.busyGeneration)
    && Array.isArray(state.pendingIdleGenerations)
    && Number.isInteger(state.consecutiveNoProgressCount)
    && (state.moderatorMessageIDs == null || (Array.isArray(state.moderatorMessageIDs) && state.moderatorMessageIDs.every((id) => typeof id === "string")))
    && state.compaction
    && typeof state.compaction.active === "boolean"
    && Number.isInteger(state.compaction.generation),
  )
}

export function transition(state, event) {
  if (!isValidState(state) || !event || typeof event.type !== "string") {
    return ignored(createInitialState(), event, "invalid-state-or-event")
  }
  const handler = TRANSITIONS[state.phase]?.[event.type] ?? GLOBAL_TRANSITIONS[event.type]
  if (handler) return handler(state, event)
  return ignored(state, event, "unsupported-event")
}

const TRANSITIONS = Object.freeze({
  OBSERVING: Object.freeze({ [EVENT.STATUS_IDLE]: onIdle, [EVENT.CONTEXT_LOADED]: onContextLoaded, [EVENT.ROOT_BLOCK_DETECTED]: onRootBlocked }),
  CLASSIFYING: Object.freeze({ [EVENT.CLASSIFIER_RESULT]: classifierResult }),
  CONTINUING: Object.freeze({ [EVENT.CONTINUATION_PERSISTED]: continuationPersisted, [EVENT.BUSY_VERIFIED]: continuationFinished, [EVENT.CONTINUATION_TIMEOUT]: continuationFinished }),
})

const GLOBAL_TRANSITIONS = Object.freeze({
  [EVENT.STATUS_BUSY]: onBusy,
  [EVENT.COMPACTION_STARTED]: compactionStarted,
  [EVENT.COMPACTION_AUTOCONTINUE]: compactionFinished,
  [EVENT.COMPACTION_COMPLETED]: compactionFinished,
  [EVENT.EFFECT_ERROR]: effectError,
})

const orDefault = (value, resolved) => value ?? resolved

function onBusy(state, event) {
  const busyGeneration = Math.max(state.busyGeneration + 1, orDefault(event.generation, 0))
  if (["IDLE", "ERROR"].includes(state.phase)) return result({ ...state, phase: "OBSERVING", busyGeneration }, event, [decision("status-busy")])
  return result({ ...state, busyGeneration }, event, [decision("status-busy")])
}

function onIdle(state, event) {
  if (state.phase !== "OBSERVING") return ignored(state, event, "idle-outside-observation")
  const generation = event.generation ?? state.busyGeneration
  if (generation > state.busyGeneration || state.pendingIdleGenerations.includes(generation)) return ignored(state, event, "stale-or-duplicate-idle")
  return result(
    { ...state, pendingIdleGenerations: [...state.pendingIdleGenerations, generation] },
    event,
    [loadContext(generation), decision("status-idle")],
  )
}

function onContextLoaded(state, event) {
  const outcome = contextOutcome(state, event)
  const next = withContext(state, event)
  if (outcome === "ignored") return result({ ...next, phase: "IDLE" }, event, [decision(contextReason(state, event))])
  if (outcome === "root-blocked") return rootBlocked(next, event)
  if (event.blockerDiscussionActive) return blockerDiscussion(next, event)
  if (event.requiredTodoPending) return requiredWork(next, event)
  if (outcome === "classify") {
    return result({ ...next, phase: "CLASSIFYING" }, event, [decision("classifying"), toast("checking"), classify()])
  }
  return ignored(state, event, "unknown-context-outcome")
}

function blockerDiscussion(state, event) {
  return result({ ...state, phase: "IDLE" }, event, [decision("blocker-discussion"), trace("BLOCKER DISCUSSION")])
}

function requiredWork(state, event) {
  const reason = "Required work remains."
  const verdict = { decision: "CONTINUE_REQUIRED_WORK", reason, reasonCode: "WORK_REMAINS", task_completion: { ruling: "FAIL", reason }, prompt_adherence: { ruling: "PASS", reason: "Deterministic controller outcome." } }
  return result({ ...state, phase: "CONTINUING" }, { ...event, verdict }, [decision("moderation-fail"), trace("CONTINUE_REQUIRED_WORK"), toast("continuing"), effect(EFFECT.SEND_CONTINUATION)])
}

function onRootBlocked(state, event) {
  return rootBlocked(withContext(state, event), event)
}

function rootBlocked(state, event) {
  const blocker = { source: "root-blocked", originUserID: event.originUserID ?? state.realUserCycleID }
  return result({ ...state, phase: "IDLE", blocker }, event, [decision("root-blocked"), trace("ROOT_BLOCKED"), toast("root-blocked")])
}

function classifierResult(state, event) {
  const verdict = guardedVerdict(event.verdict, event)
  const resolvedEvent = { ...event, verdict }
  if (verdict.decision === "PASS") return result({ ...state, phase: "IDLE", blocker: null, consecutiveNoProgressCount: 0 }, resolvedEvent, [decision("moderation-pass"), trace("PASS"), toast("passed")])
  if (verdict.decision === "BLOCKED") {
    const blocker = state.blocker ?? { source: "minicpm-blocked", originUserID: event.originUserID ?? state.realUserCycleID }
    return result({ ...state, phase: "IDLE", blocker }, resolvedEvent, [decision("moderation-blocked"), trace("BLOCKED"), toast("blocked")])
  }
  const count = verdict.decision === "CONTINUE_PROGRESS" ? 0 : verdict.decision === "CONTINUE_REQUIRED_WORK" ? state.consecutiveNoProgressCount : state.consecutiveNoProgressCount + 1
  if (count >= 3) return result({ ...state, phase: "IDLE", consecutiveNoProgressCount: count }, resolvedEvent, [decision("moderation-escalated"), trace("ESCALATED"), toast("escalated")])
  return result({ ...state, phase: "CONTINUING", consecutiveNoProgressCount: count }, resolvedEvent, [decision("moderation-fail"), trace(verdict.decision), toast("continuing"), effect(EFFECT.SEND_CONTINUATION)])
}

function continuationPersisted(state, event) {
  return result(state, event, [effect(EFFECT.VERIFY_PROMPT), effect(EFFECT.WAIT_FOR_BUSY), decision("continuation-persisted")])
}

function continuationFinished(state, event) {
  const effects = [decision(event.type === EVENT.BUSY_VERIFIED ? "continuation-verified" : "continuation-timeout")]
  if (event.type === EVENT.CONTINUATION_TIMEOUT) effects.push(toast("continuation-error"))
  return result({ ...state, phase: "IDLE" }, event, effects)
}

function compactionStarted(state, event) {
  return result({ ...state, compaction: { active: true, generation: state.compaction.generation + 1 } }, event, [decision("compaction-started")])
}

function compactionFinished(state, event) {
  return result({ ...state, compaction: { ...state.compaction, active: false } }, event, [decision("compaction-completed")])
}

function effectError(state, event) {
  if (state.phase === "ERROR") return result(state, event, [decision("moderation-error"), toast("error")])
  return result({ ...state, phase: "ERROR", inflightAssistantID: null, lastTerminalAssistantID: null }, event, [decision("moderation-error"), trace("ERROR"), toast("error")])
}

function withContext(state, event) {
  const claimedAssistantID = event.terminal && event.assistantID ? event.assistantID : null
  return {
    ...state,
    inflightAssistantID: claimedAssistantID ?? state.inflightAssistantID,
    lastTerminalAssistantID: claimedAssistantID ?? state.lastTerminalAssistantID,
    realUserCycleID: event.realUserCycleID ?? state.realUserCycleID,
    consecutiveNoProgressCount: isNewCycle(state, event) ? 0 : state.consecutiveNoProgressCount,
    blocker: event.blockerBranch === false && isNewCycle(state, event) ? null : state.blocker,
    pendingIdleGenerations: state.pendingIdleGenerations.slice(1),
  }
}

function contextOutcome(state, event) {
  if (!hasRawContextFacts(event)) return event.outcome
  if (event.terminal === false || event.assistantPresent === false) return "ignored"
  if (event.duplicate || !event.assistantID || event.assistantID === state.lastTerminalAssistantID || event.assistantID === state.inflightAssistantID) return "ignored"
  if (event.compaction || event.planMode || event.build === false || event.assistantError || event.userNewer || event.moderatorTrace) return "ignored"
  if (event.rootBlocked) return "root-blocked"
  return "classify"
}

function contextReason(state, event) {
  if (!hasRawContextFacts(event)) return orDefault(event.reason, "assistant-ignored")
  if (event.terminal === false) return "ignored-nonterminal-assistant"
  if (event.assistantPresent === false) return "ignored-no-assistant"
  if (event.duplicate || !event.assistantID || event.assistantID === state.lastTerminalAssistantID || event.assistantID === state.inflightAssistantID) return "ignored-duplicate"
  if (event.compaction) return "ignored-compaction"
  if (event.planMode) return "ignored-plan-mode"
  if (event.build === false) return "ignored-non-build-agent"
  if (event.assistantError) return "moderation-error"
  if (event.userNewer) return "ignored-no-completed-assistant"
  return "ignored-moderator-trace"
}

function hasRawContextFacts(event) {
  return ["terminal", "assistantPresent", "duplicate", "compaction", "build", "assistantError", "userNewer", "moderatorTrace", "rootBlocked", "blockerBranch"].some((key) => Object.hasOwn(event, key))
}

function isNewCycle(state, event) {
  return event.newCycle ?? (event.realUserCycleID != null && event.realUserCycleID !== state.realUserCycleID)
}

function guardedVerdict(verdict, event) {
  if (event.requiredTodoPending && verdict?.decision === "PASS") {
    const reason = "Required work remains."
    return { ...verdict, decision: "CONTINUE_REQUIRED_WORK", reason, reasonCode: "WORK_REMAINS", task_completion: { ruling: "FAIL", reason } }
  }
  return verdict ?? { decision: "CONTINUE_NO_PROGRESS", reason: "missing classifier verdict" }
}

function result(state, event, effects, phase) {
  const next = phase ? { ...state, phase } : state
  return { state: next, event, effects, ignored: false, transition: { previousPhase: state.phase, event: event.type, nextPhase: next.phase } }
}

function ignored(state, event, reason) {
  return { state, event, effects: [decision(reason)], ignored: true, transition: { previousPhase: state.phase, event: orDefault(event?.type, "INVALID"), nextPhase: state.phase } }
}

function effect(type, detail) { return detail ? { type, ...detail } : { type } }
function decision(reason) { return effect(EFFECT.WRITE_DECISION, { reason }) }
function trace(decisionType) { return effect(EFFECT.WRITE_TRACE, { decisionType }) }
function toast(kind) { return effect(EFFECT.SHOW_TOAST, { kind }) }
function loadContext(generation) { return effect(EFFECT.LOAD_CONTEXT, { generation }) }
function classify() { return effect(EFFECT.CLASSIFY) }
