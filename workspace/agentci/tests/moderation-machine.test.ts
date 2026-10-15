import assert from "node:assert/strict";
import test from "node:test";
import { createInitialState, isValidState, transition } from "../src/moderation/machine.ts";
import type { ModerationEvent, ModerationState, Verdict } from "../src/moderation/types.ts";

const verdicts = {
  complete: verdict("AGENT_COMPLETE", "WORK_COMPLETE"),
  progress: verdict("AGENT_CONTINUING", "WORK_REMAINS"),
  noProgress: verdict("AGENT_STALLED", "NO_PROGRESS"),
  blocked: verdict("AGENT_BLOCKED", "AWAITING_OPERATOR"),
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

test("STATUS_BUSY from IDLE enters OBSERVING and increments the generation", () => {
  const result = transition(createInitialState(), { type: "STATUS_BUSY", generation: 4 });
  assert.equal(result.state.phase, "OBSERVING");
  assert.equal(result.state.busyGeneration, 4);
});

test("STATUS_IDLE queues a generation and requests context", () => {
  const busy = transition(createInitialState(), { type: "STATUS_BUSY", generation: 1 }).state;
  const result = transition(busy, { type: "STATUS_IDLE", generation: 1 });
  assert.deepEqual(result.state.pendingIdleGenerations, [1]);
  assert.ok(result.effects.some((effect) => effect.type === "LOAD_CONTEXT"));
});

test("stale STATUS_IDLE is ignored", () => {
  const busy = transition(createInitialState(), { type: "STATUS_BUSY", generation: 3 }).state;
  const result = transition(busy, { type: "STATUS_IDLE", generation: 1 });
  assert.equal(result.ignored, true);
  assert.deepEqual(result.state.pendingIdleGenerations, []);
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

test("progress verdict resets the no-progress counter", () => {
  const state = { ...classifying(), consecutiveNoProgressCount: 2 };
  const result = transition(state, { type: "CLASSIFIER_RESULT", verdict: verdicts.progress });
  assert.equal(result.state.consecutiveNoProgressCount, 0);
  assert.equal(result.state.phase, "CONTINUING");
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
  const result = transition(createInitialState(), { type: "STATUS_IDLE", generation: 0 });
  assert.equal(result.ignored, true);
});

function observing(): ModerationState {
  return transition(createInitialState(), { type: "STATUS_BUSY", generation: 1 }).state;
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