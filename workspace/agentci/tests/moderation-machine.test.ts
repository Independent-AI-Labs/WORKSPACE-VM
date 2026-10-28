import assert from "node:assert/strict";
import test from "node:test";
import { createInitialState, isValidState, normalizeRestoredState, transition } from "../src/moderation/machine.ts";
import type { ModerationEvent, ModerationState, Verdict } from "../src/moderation/types.ts";

const verdicts = {
  complete: verdict("AGENT_COMPLETE", "WORK_COMPLETE"),
  progress: verdict("AGENT_CONTINUING", "WORK_REMAINS"),
  noProgress: verdict("AGENT_STALLED", "NO_PROGRESS"),
  blocked: verdict("AGENT_BLOCKED", "AWAITING_OPERATOR"),
  stopped: verdict("AGENT_STOPPED", "USER_STOP"),
};

test("initial state is valid and idle", () => {
  const state = createInitialState();
  assert.equal(isValidState(state), true);
  assert.equal(state.phase, "IDLE");
});

test("invalid state is reset on transition", () => {
  const result = transition({ phase: "BOGUS" } as unknown as ModerationState, { type: "STATUS_BUSY" });
  assert.equal(result.ignored, true);
  assert.equal(result.state.phase, "IDLE");
});

test("STATUS_BUSY from IDLE enters OBSERVING", () => {
  const result = transition(createInitialState(), { type: "STATUS_BUSY" });
  assert.equal(result.state.phase, "OBSERVING");
});

test("STATUS_IDLE requests a context load without tracking a generation", () => {
  const busy = transition(createInitialState(), { type: "STATUS_BUSY" }).state;
  const result = transition(busy, { type: "STATUS_IDLE" });
  assert.equal(result.state.phase, "OBSERVING");
  assert.ok(result.effects.some((effect) => effect.type === "LOAD_CONTEXT"));
});

test("a second STATUS_IDLE during observation requests context; identity suppresses the duplicate later", () => {
  const busy = transition(createInitialState(), { type: "STATUS_BUSY" }).state;
  const first = transition(busy, { type: "STATUS_IDLE" });
  const second = transition(first.state, { type: "STATUS_IDLE" });
  assert.equal(second.ignored, false);
  assert.ok(second.effects.some((effect) => effect.type === "LOAD_CONTEXT"));
});

test("controllable context starts classification", () => {
  const result = transition(observing(), contextEvent());
  assert.equal(result.state.phase, "CLASSIFYING");
  assert.ok(result.effects.some((effect) => effect.type === "CLASSIFY"));
});

test("non-terminal assistant is ignored", () => {
  const result = transition(observing(), contextEvent({ terminal: false }));
  assert.equal(result.ignored, true);
  assert.equal(result.state.phase, "IDLE");
});

test("an interrupted assistant is ignored as a cancellation", () => {
  const result = transition(observing(), contextEvent({ assistantError: true, terminal: false }));
  assert.equal(result.ignored, true);
  assert.equal(result.state.phase, "IDLE");
  assert.ok(result.effects.some((effect) => effect.type === "WRITE_DECISION" && effect.decisionType === "ignored-cancellation"));
});

test("duplicate assistant id is ignored", () => {
  const result = transition(observing(), contextEvent({ assistantID: "msg_seen", duplicate: true }));
  assert.equal(result.ignored, true);
});

test("root block records an operator-handoff outcome", () => {
  const result = transition(observing(), contextEvent({ rootBlocked: true }));
  assert.equal(result.state.phase, "IDLE");
  assert.equal(result.state.blocker?.source, "operator-handoff");
});

test("a context with unfinished work is classified, not short-circuited", () => {
  const result = transition(observing(), contextEvent());
  assert.equal(result.state.phase, "CLASSIFYING");
  assert.ok(result.effects.some((effect) => effect.type === "CLASSIFY"));
  assert.equal(result.effects.some((effect) => effect.type === "SEND_CONTINUATION"), false);
});

test("AGENT_COMPLETE verdict returns to IDLE", () => {
  const result = transition(classifying(), { type: "CLASSIFIER_RESULT", verdict: verdicts.complete });
  assert.equal(result.state.phase, "IDLE");
  assert.equal(result.state.blocker, null);
  assert.equal(result.effects.some((effect) => effect.type === "SEND_CONTINUATION"), false);
  assert.ok(result.effects.some((effect) => effect.type === "WRITE_TRACE"), "user-meaningful outcome must write a transcript line");
});

test("AGENT_BLOCKED verdict records an agent-blocked outcome", () => {
  const result = transition(classifying(), { type: "CLASSIFIER_RESULT", verdict: verdicts.blocked });
  assert.equal(result.state.phase, "IDLE");
  assert.equal(result.state.blocker?.source, "agent-blocked");
  assert.ok(result.effects.some((effect) => effect.type === "WRITE_TRACE"), "user-meaningful outcome must write a transcript line");
});

test("AGENT_STOPPED verdict stands down without a transcript line or continuation", () => {
  const result = transition(classifying(), { type: "CLASSIFIER_RESULT", verdict: verdicts.stopped });
  assert.equal(result.state.phase, "IDLE");
  assert.equal(result.state.blocker, null);
  assert.equal(result.effects.some((effect) => effect.type === "SEND_CONTINUATION"), false);
  assert.equal(result.effects.some((effect) => effect.type === "WRITE_TRACE"), false, "a user stop must not write a transcript line");
  assert.ok(result.effects.some((effect) => effect.type === "WRITE_DECISION" && effect.decisionType === "moderation-user-stop"));
});

test("progress verdict keeps the no-progress counter", () => {
  const state = { ...classifying(), consecutiveNoProgressCount: 2 };
  const result = transition(state, { type: "CLASSIFIER_RESULT", verdict: verdicts.progress });
  assert.equal(result.state.consecutiveNoProgressCount, 2);
  assert.equal(result.state.phase, "CONTINUING");
});

test("verified continuation returns to observation so the next idle is classified", () => {
  const continuing = transition(classifying(), { type: "CLASSIFIER_RESULT", verdict: verdicts.progress }).state;
  const result = transition(continuing, { type: "BUSY_VERIFIED" });
  assert.equal(result.state.phase, "OBSERVING");
  const idle = transition(result.state, { type: "STATUS_IDLE" });
  assert.ok(idle.effects.some((effect) => effect.type === "LOAD_CONTEXT"));
});

test("timed-out continuation returns to idle", () => {
  const continuing = transition(classifying(), { type: "CLASSIFIER_RESULT", verdict: verdicts.progress }).state;
  const result = transition(continuing, { type: "CONTINUATION_TIMEOUT" });
  assert.equal(result.state.phase, "IDLE");
});

test("three consecutive no-progress verdicts escalate", () => {
  let state = classifying();
  let result = transition(state, { type: "CLASSIFIER_RESULT", verdict: verdicts.noProgress });
  state = { ...result.state, phase: "CLASSIFYING" };
  result = transition(state, { type: "CLASSIFIER_RESULT", verdict: verdicts.noProgress });
  state = { ...result.state, phase: "CLASSIFYING" };
  result = transition(state, { type: "CLASSIFIER_RESULT", verdict: verdicts.noProgress });
  assert.equal(result.state.consecutiveNoProgressCount, 3);
  assert.equal(result.state.phase, "IDLE");
  assert.ok(result.effects.some((effect) => effect.type === "SHOW_TOAST" && effect.kind === "escalated"));
  assert.equal(result.effects.some((effect) => effect.type === "WRITE_TRACE"), false, "internal outcome must not write a transcript line");
});

test("an AGENT_COMPLETE verdict is not overridden by tracked work", () => {
  const result = transition(classifying(), { type: "CLASSIFIER_RESULT", verdict: verdicts.complete });
  assert.equal(result.state.phase, "IDLE");
  assert.equal(result.state.blocker, null);
  assert.equal(result.effects.some((effect) => effect.type === "SEND_CONTINUATION"), false);
});

test("compaction start and completion toggle the flag", () => {
  const started = transition(observing(), { type: "COMPACTION_STARTED" });
  assert.equal(started.state.compaction.active, true);
  const completed = transition(started.state, { type: "COMPACTION_COMPLETED" });
  assert.equal(completed.state.compaction.active, false);
});

test("effect errors move the machine into ERROR", () => {
  const result = transition(observing(), { type: "EFFECT_ERROR", error: "boom" });
  assert.equal(result.state.phase, "ERROR");
});

test("STATUS_IDLE outside observation is ignored", () => {
  const result = transition(createInitialState(), { type: "STATUS_IDLE" });
  assert.equal(result.ignored, true);
});

test("restore coerces an in-flight phase to IDLE without losing settled facts", () => {
  const restored = normalizeRestoredState({
    phase: "CONTINUING",
    inflightAssistantID: "msg_inflight",
    lastTerminalAssistantID: "msg_terminal",
    realUserCycleID: "user_1",
    consecutiveNoProgressCount: 2,
    blocker: { source: "agent-blocked", originUserID: "user_1" },
    compaction: { active: true },
  });
  assert.equal(restored.phase, "IDLE");
  assert.equal(restored.inflightAssistantID, null);
  assert.equal(restored.lastTerminalAssistantID, "msg_terminal");
  assert.equal(restored.realUserCycleID, "user_1");
  assert.equal(restored.consecutiveNoProgressCount, 2);
  assert.equal(restored.blocker?.source, "agent-blocked");
  assert.equal(restored.compaction.active, true);
});

test("restore clears the unfinished classification claim so it is re-evaluated", () => {
  const restored = normalizeRestoredState({ ...createInitialState(), phase: "CLASSIFYING", lastTerminalAssistantID: "msg_half_classified" });
  assert.equal(restored.phase, "IDLE");
  assert.equal(restored.lastTerminalAssistantID, null);
});

function observing(): ModerationState {
  return transition(createInitialState(), { type: "STATUS_BUSY" }).state;
}

function classifying(): ModerationState {
  return transition(observing(), contextEvent()).state;
}

function contextEvent(overrides: Record<string, unknown> = {}): ModerationEvent {
  return {
    type: "CONTEXT_LOADED",
    terminal: true,
    assistantPresent: true,
    duplicate: false,
    compaction: false,
    planMode: false,
    build: true,
    assistantError: false,
    userNewer: false,
    moderatorTrace: false,
    rootBlocked: false,
    blockerDiscussionActive: false,
    assistantID: "msg_1",
    realUserCycleID: "user_1",
    newCycle: true,
    originUserID: "user_1",
    ...overrides,
  };
}

function verdict(decision: Verdict["decision"], reasonCode: Verdict["reasonCode"]): Verdict {
  return {
    decision,
    reason: `reason ${reasonCode}`,
    reasonCode,
    task_completion: { ruling: decision === "AGENT_COMPLETE" ? "PASS" : "FAIL", reason: "test" },
    prompt_adherence: { ruling: "PASS", reason: "test" },
  };
}