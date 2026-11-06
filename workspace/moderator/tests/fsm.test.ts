import test from "node:test";
import assert from "node:assert/strict";
import { createInitialState, isValidState, normalizeRestoredState, transition } from "../src/fsm.ts";
import type { ModerationState, TurnFact, Verdict } from "../src/types.ts";

const turn: TurnFact = {
  assistantID: "a1",
  userMessageID: "u1",
  agentMode: "build",
  todosOpen: 0,
  terminal: true,
  assistantPresent: true,
  duplicate: false,
  compaction: false,
  assistantError: false,
  userNewer: false,
  moderatorTrace: false,
  planMode: false,
  rootBlocked: false,
  blockerDiscussion: false,
  newCycle: true,
};

function verdict(decision: Verdict["decision"], reasonCode: Verdict["reasonCode"]): Verdict {
  return { decision, reasonCode, reason: `${decision} ${reasonCode}` };
}

function observing(): ModerationState {
  const busy = transition(createInitialState(), { type: "STATUS_BUSY" });
  return transition(busy.state, { type: "TURN_ENDED", turn }).state;
}

test("busy moves idle to observing", () => {
  const result = transition(createInitialState(), { type: "STATUS_BUSY" });
  assert.equal(result.state.phase, "OBSERVING");
  assert.deepEqual(result.effects, [{ type: "WRITE_DECISION", decisionType: "status-busy" }]);
});

test("turn end loads context", () => {
  const result = transition(observing(), { type: "TURN_ENDED", turn });
  assert.equal(result.state.inflightAssistantID, "a1");
  assert.ok(result.effects.some((effect) => effect.type === "LOAD_CONTEXT"));
});

test("valid context starts classification", () => {
  const result = transition(observing(), { type: "CONTEXT_LOADED", turn, originUserID: "u1", todos: [] });
  assert.equal(result.state.phase, "CLASSIFYING");
  assert.ok(result.effects.some((effect) => effect.type === "CLASSIFY"));
});

test("answer mode does not override a blocker", () => {
  const answerTurn = { ...turn, agentMode: "answer" as const };
  const classifying = transition(observing(), { type: "CONTEXT_LOADED", turn: answerTurn, originUserID: "u1", todos: [] }).state;
  const result = transition(classifying, {
    type: "VERDICT",
    verdict: verdict("AGENT_BLOCKED", "AWAITING_USER"),
    capture: { selector: "p/m", sessionID: "s1", attempts: 1, durationMs: 1, input: null },
    originUserID: "u1",
  });
  assert.equal(result.state.blocker?.source, "agent-blocked");
  assert.ok(result.effects.some((effect) => effect.type === "WRITE_TRACE"));
});

test("three stalled verdicts escalate", () => {
  let state = observing();
  state = transition(state, { type: "CONTEXT_LOADED", turn, originUserID: "u1", todos: [] }).state;
  state = transition(state, { type: "VERDICT", verdict: verdict("AGENT_STALLED", "NO_PROGRESS"), capture: { selector: "p/m", sessionID: null, attempts: 1, durationMs: 1, input: null }, originUserID: "u1" }).state;
  state = { ...state, phase: "CLASSIFYING", inflightAssistantID: "a2" };
  state = transition(state, { type: "VERDICT", verdict: verdict("AGENT_STALLED", "NO_PROGRESS"), capture: { selector: "p/m", sessionID: null, attempts: 1, durationMs: 1, input: null }, originUserID: "u1" }).state;
  state = { ...state, phase: "CLASSIFYING", inflightAssistantID: "a3" };
  const result = transition(state, { type: "VERDICT", verdict: verdict("AGENT_STALLED", "NO_PROGRESS"), capture: { selector: "p/m", sessionID: null, attempts: 1, durationMs: 1, input: null }, originUserID: "u1" });
  assert.equal(result.state.phase, "IDLE");
  assert.ok(result.effects.some((effect) => effect.type === "SHOW_TOAST" && effect.kind === "escalated"));
});

test("compaction toggles durable flag", () => {
  const started = transition(createInitialState(), { type: "COMPACTION_STARTED" });
  assert.equal(started.state.compactionActive, true);
  const completed = transition(started.state, { type: "COMPACTION_COMPLETED" });
  assert.equal(completed.state.compactionActive, false);
});

test("null ancestor still classifies", () => {
  const result = transition(observing(), { type: "CONTEXT_LOADED", turn: { ...turn, userMessageID: null }, originUserID: null, todos: [] });
  assert.equal(result.state.phase, "CLASSIFYING");
  assert.equal(result.ignored, false);
});

test("turn end while idle is outside phase", () => {
  const result = transition(createInitialState(), { type: "TURN_ENDED", turn });
  assert.equal(result.ignored, true);
  assert.equal(result.state.phase, "IDLE");
  assert.deepEqual(result.effects, [{ type: "WRITE_DECISION", decisionType: "ignored-outside-phase", reason: "outside-phase" }]);
});

test("eligibility writes one named decision", () => {
  const cases: { patch: Partial<TurnFact>; decisionType: string; reason: string }[] = [
    { patch: { terminal: false }, decisionType: "ignored-nonterminal", reason: "nonterminal" },
    { patch: { assistantError: true }, decisionType: "ignored-assistant-error", reason: "assistant-error" },
    { patch: { planMode: true }, decisionType: "ignored-plan-mode", reason: "plan-mode" },
    { patch: { compaction: true }, decisionType: "ignored-compaction", reason: "compaction" },
    { patch: { userNewer: true }, decisionType: "ignored-newer-user", reason: "newer-user" },
    { patch: { moderatorTrace: true }, decisionType: "ignored-moderator-trace", reason: "moderator-trace" },
    { patch: { duplicate: true }, decisionType: "ignored-duplicate", reason: "duplicate" },
  ];
  for (const item of cases) {
    const result = transition(observing(), { type: "CONTEXT_LOADED", turn: { ...turn, ...item.patch }, originUserID: "u1", todos: [] });
    assert.equal(result.ignored, true);
    assert.equal(result.state.phase, "IDLE");
    assert.deepEqual(result.effects, [{ type: "WRITE_DECISION", decisionType: item.decisionType, reason: item.reason }]);
  }
});

test("cancelled writes cancelled", () => {
  const classifying = transition(observing(), { type: "CONTEXT_LOADED", turn, originUserID: "u1", todos: [] }).state;
  const result = transition(classifying, { type: "CANCELLED", reason: "user" });
  assert.equal(result.ignored, false);
  assert.deepEqual(result.effects, [{ type: "WRITE_DECISION", decisionType: "cancelled", reason: "cancelled" }]);
});

function loaded(extra: Partial<TurnFact> = {}): ModerationState {
  return transition(observing(), { type: "CONTEXT_LOADED", turn: { ...turn, ...extra }, originUserID: "u1", todos: [] }).state;
}

function capture() {
  return { selector: "p/m", sessionID: null, attempts: 1, durationMs: 1, input: null };
}

test("nonterminal wins over later flags", () => {
  const result = transition(observing(), { type: "CONTEXT_LOADED", turn: { ...turn, terminal: false, duplicate: true, planMode: true }, originUserID: "u1", todos: [] });
  assert.equal(result.effects[0]?.type === "WRITE_DECISION" ? result.effects[0].decisionType : "", "ignored-nonterminal");
});

test("root block writes a handoff and does not classify", () => {
  const result = transition(observing(), { type: "CONTEXT_LOADED", turn: { ...turn, rootBlocked: true }, originUserID: "u1", todos: [] });
  assert.equal(result.state.blocker?.source, "operator-handoff");
  assert.deepEqual(result.effects.map((effect) => effect.type), ["WRITE_DECISION", "WRITE_TRACE", "SHOW_TOAST"]);
  assert.equal(result.effects.some((effect) => effect.type === "CLASSIFY"), false);
});

test("blocker discussion does not classify", () => {
  const result = transition(observing(), { type: "CONTEXT_LOADED", turn: { ...turn, blockerDiscussion: true }, originUserID: "u1", todos: [] });
  assert.equal(result.state.phase, "IDLE");
  assert.deepEqual(result.effects, [{ type: "WRITE_DECISION", decisionType: "blocker-discussion" }]);
});

test("user stop writes no trace", () => {
  const result = transition(loaded(), { type: "VERDICT", verdict: verdict("AGENT_STOPPED", "USER_STOP"), capture: capture(), originUserID: "u1" });
  assert.equal(result.effects.some((effect) => effect.type === "WRITE_TRACE"), false);
  assert.equal(result.effects.some((effect) => effect.type === "SHOW_TOAST" && effect.kind === "user-stop"), true);
});

test("blocker turns a later continue into completion", () => {
  const blocked = transition(loaded(), { type: "VERDICT", verdict: verdict("AGENT_BLOCKED", "AWAITING_USER"), capture: capture(), originUserID: "u1" }).state;
  const again = { ...blocked, phase: "CLASSIFYING" as const, inflightAssistantID: "a2" };
  const result = transition(again, { type: "VERDICT", verdict: verdict("AGENT_CONTINUING", "WORK_REMAINS"), capture: capture(), originUserID: "u1" });
  assert.equal(result.effects.some((effect) => effect.type === "WRITE_DECISION" && effect.decisionType === "moderation-complete"), true);
  assert.equal(result.effects.some((effect) => effect.type === "SEND_CONTINUATION"), false);
});

test("new user cycle clears a blocker unless the branch matches", () => {
  const blocked = transition(loaded(), { type: "VERDICT", verdict: verdict("AGENT_BLOCKED", "AWAITING_OPERATOR"), capture: capture(), originUserID: "u1" }).state;
  const cleared = transition(blocked, { type: "NEW_USER_CYCLE", originUserID: "u2", sameBranch: false });
  assert.equal(cleared.state.blocker, null);
  assert.equal(cleared.state.realUserCycleID, "u2");
  const kept = transition(blocked, { type: "NEW_USER_CYCLE", originUserID: "u1", sameBranch: true });
  assert.equal(kept.state.blocker?.source, "agent-blocked");
});

test("replay skip uses the eligibility name", () => {
  const result = transition(createInitialState(), { type: "REPLAY", turn: { ...turn, duplicate: true } });
  assert.equal(result.ignored, true);
  assert.equal(result.state.phase, "IDLE");
  assert.deepEqual(result.effects, [{ type: "WRITE_DECISION", decisionType: "ignored-duplicate", reason: "duplicate" }]);
});

test("effect error drops an unfinished assistant identity", () => {
  const classifying = loaded();
  const result = transition(classifying, { type: "EFFECT_ERROR", error: "classifier down" });
  assert.equal(result.state.phase, "ERROR");
  assert.equal(result.state.inflightAssistantID, null);
  assert.equal(result.state.lastTerminalAssistantID, null);
  assert.equal(result.effects.some((effect) => effect.type === "SHOW_TOAST" && effect.kind === "error"), true);
});

test("invalid state is rejected", () => {
  assert.equal(isValidState({ phase: "BROKEN" }), false);
});

test("restore clears transient fields", () => {
  const restored = normalizeRestoredState({ ...createInitialState(), phase: "CLASSIFYING", inflightAssistantID: "a1", compactionActive: true });
  assert.equal(restored.phase, "IDLE");
  assert.equal(restored.inflightAssistantID, null);
  assert.equal(restored.compactionActive, false);
});
