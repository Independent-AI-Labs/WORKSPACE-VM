import { expect, test } from "bun:test"
import { EFFECT, EVENT, createInitialState, transition } from "../../workspace/config/opencode/plugins/local-response-moderator-machine.js"

test("queues an eligible idle generation for context loading", () => {
  const busy = transition(createInitialState(), { type: EVENT.STATUS_BUSY, generation: 1 })
  const idle = transition(busy.state, { type: EVENT.STATUS_IDLE, generation: 1 })
  expect(idle.state.pendingIdleGenerations).toEqual([1])
  expect(idle.effects[0]).toEqual({ type: EFFECT.LOAD_CONTEXT, generation: 1 })
})

test("retains later idle generations in FIFO order", () => {
  const firstBusy = transition(createInitialState(), { type: EVENT.STATUS_BUSY, generation: 1 })
  const firstIdle = transition(firstBusy.state, { type: EVENT.STATUS_IDLE, generation: 1 })
  const secondBusy = transition(firstIdle.state, { type: EVENT.STATUS_BUSY, generation: 2 })
  const secondIdle = transition(secondBusy.state, { type: EVENT.STATUS_IDLE, generation: 2 })
  expect(secondIdle.state.pendingIdleGenerations).toEqual([1, 2])
})

test("does not claim a nonterminal assistant and releases claims after an effect error", () => {
  const observing = { ...createInitialState(), phase: "OBSERVING" }
  const nonterminal = transition(observing, {
    type: EVENT.CONTEXT_LOADED,
    terminal: false,
    assistantPresent: true,
    build: true,
    assistantID: "a1",
  })
  expect(nonterminal.state.lastTerminalAssistantID).toBeNull()
  const failed = transition({ ...observing, inflightAssistantID: "a1", lastTerminalAssistantID: "a1" }, { type: EVENT.EFFECT_ERROR, error: "write failed" })
  expect(failed.state.inflightAssistantID).toBeNull()
  expect(failed.state.lastTerminalAssistantID).toBeNull()
  const traceFailure = transition(failed.state, { type: EVENT.EFFECT_ERROR, error: "trace failed" })
  expect(traceFailure.effects.map((effect) => effect.type)).not.toContain(EFFECT.WRITE_TRACE)
})

test("continues required pending work before classification", () => {
  const state = { ...createInitialState(), phase: "OBSERVING" }
  const outcome = transition(state, {
    type: EVENT.CONTEXT_LOADED,
    terminal: true,
    assistantPresent: true,
    build: true,
    assistantID: "a1",
    requiredTodoPending: true,
  })
  expect(outcome.state.phase).toBe("CONTINUING")
  expect(outcome.effects).not.toContainEqual({ type: EFFECT.CLASSIFY })
  expect(outcome.effects).toContainEqual({ type: EFFECT.WRITE_TRACE, decisionType: "CONTINUE_REQUIRED_WORK" })
  expect(outcome.event.verdict.decision).toBe("CONTINUE_REQUIRED_WORK")
  expect(outcome.effects.at(-1)).toEqual({ type: EFFECT.SEND_CONTINUATION })
})

test("requests classification and accepts a classifier pass", () => {
  const observing = { ...createInitialState(), phase: "OBSERVING" }
  const classified = transition(observing, {
    type: EVENT.CONTEXT_LOADED,
    terminal: true,
    assistantPresent: true,
    build: true,
    assistantID: "a1",
  })
  expect(classified.state.phase).toBe("CLASSIFYING")
  expect(classified.effects).toContainEqual({ type: EFFECT.CLASSIFY })

  const passed = transition(classified.state, { type: EVENT.CLASSIFIER_RESULT, verdict: { decision: "PASS" } })
  expect(passed.state.phase).toBe("IDLE")
  expect(passed.effects).toContainEqual({ type: EFFECT.WRITE_TRACE, decisionType: "PASS" })
})

test("handles blocker discussion without classification or continuation", () => {
  const state = { ...createInitialState(), phase: "OBSERVING", blocker: { source: "root-blocked", originUserID: "u1" } }
  const outcome = transition(state, {
    type: EVENT.CONTEXT_LOADED,
    terminal: true,
    assistantPresent: true,
    build: true,
    assistantID: "a1",
    blockerDiscussionActive: true,
  })
  expect(outcome.state.phase).toBe("IDLE")
  expect(outcome.effects.map((effect) => effect.type)).not.toContain(EFFECT.SEND_CONTINUATION)
  expect(outcome.effects.map((effect) => effect.type)).not.toContain(EFFECT.CLASSIFY)
})

test("records escalation after three consecutive no-progress decisions", () => {
  const state = { ...createInitialState(), phase: "CLASSIFYING", consecutiveNoProgressCount: 2 }
  const outcome = transition(state, { type: EVENT.CLASSIFIER_RESULT, verdict: { decision: "CONTINUE_NO_PROGRESS" } })
  expect(outcome.state.phase).toBe("IDLE")
  expect(outcome.state.consecutiveNoProgressCount).toBe(3)
})

test("required work preserves the no-progress escalation budget", () => {
  const state = { ...createInitialState(), phase: "OBSERVING", consecutiveNoProgressCount: 2 }
  const outcome = transition(state, { type: EVENT.CONTEXT_LOADED, terminal: true, assistantPresent: true, build: true, assistantID: "a1", requiredTodoPending: true })
  expect(outcome.state.phase).toBe("CONTINUING")
  expect(outcome.state.consecutiveNoProgressCount).toBe(2)
  expect(outcome.event.verdict.decision).toBe("CONTINUE_REQUIRED_WORK")
})

test("uses raw context facts to ignore an ineligible assistant", () => {
  const state = { ...createInitialState(), phase: "OBSERVING" }
  const outcome = transition(state, {
    type: EVENT.CONTEXT_LOADED,
    terminal: true,
    assistantPresent: true,
    assistantID: "a1",
    build: true,
    userNewer: true,
  })
  expect(outcome.state.phase).toBe("IDLE")
  expect(outcome.effects).toEqual([{ type: EFFECT.WRITE_DECISION, reason: "ignored-no-completed-assistant" }])
})

test("ignores plan mode from the assistant mode field", () => {
  const state = { ...createInitialState(), phase: "OBSERVING" }
  const outcome = transition(state, { type: EVENT.CONTEXT_LOADED, terminal: true, assistantPresent: true, build: true, planMode: true, assistantID: "a1" })
  expect(outcome.effects).toEqual([{ type: EFFECT.WRITE_DECISION, reason: "ignored-plan-mode" }])
})

test("uses state and raw assistant facts to reject duplicates", () => {
  const state = { ...createInitialState(), phase: "OBSERVING", lastTerminalAssistantID: "a1" }
  const outcome = transition(state, { type: EVENT.CONTEXT_LOADED, terminal: true, assistantPresent: true, build: true, assistantID: "a1" })
  expect(outcome.effects).toEqual([{ type: EFFECT.WRITE_DECISION, reason: "ignored-duplicate" }])
})

test("uses raw context facts to classify without a completion marker", () => {
  const state = { ...createInitialState(), phase: "OBSERVING" }
  const facts = { type: EVENT.CONTEXT_LOADED, terminal: true, assistantPresent: true, build: true, assistantID: "a1" }
  const classify = transition(state, facts)
  expect(classify.state.phase).toBe("CLASSIFYING")
  expect(classify.effects).toContainEqual({ type: EFFECT.CLASSIFY })
})

test("blocks a root-required response from raw context facts", () => {
  const state = { ...createInitialState(), phase: "OBSERVING" }
  const outcome = transition(state, {
    type: EVENT.CONTEXT_LOADED,
    terminal: true,
    assistantPresent: true,
    build: true,
    assistantID: "a1",
    realUserCycleID: "u1",
    originUserID: "u1",
    rootBlocked: true,
  })
  expect(outcome.state.phase).toBe("IDLE")
  expect(outcome.state.blocker).toEqual({ source: "root-blocked", originUserID: "u1" })
  expect(outcome.effects).toContainEqual({ type: EFFECT.WRITE_DECISION, reason: "root-blocked" })
  expect(outcome.effects.map((effect) => effect.type)).not.toContain(EFFECT.CLASSIFY)
})
