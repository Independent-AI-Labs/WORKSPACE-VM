import test from "node:test";
import assert from "node:assert/strict";
import { classify, parseToolInput } from "../src/classifier.ts";
import type { GenerateFn } from "../src/generate.ts";

const input = {
  parentSessionID: "parent",
  todos: [],
  previousResponse: "work remains",
  userMessages: ["work"],
  toolActivity: [],
  agentMode: "build" as const,
};

test("parser accepts a valid tool pair", () => {
  const result = parseToolInput({ decision: "AGENT_COMPLETE", reason: "WORK_COMPLETE" });
  assert.equal(result?.verdict.decision, "AGENT_COMPLETE");
});

test("parser rejects extra arguments", () => {
  assert.equal(parseToolInput({ decision: "AGENT_COMPLETE", reason: "WORK_COMPLETE", extra: true }), undefined);
});

test("parser rejects a mismatched pair", () => {
  assert.equal(parseToolInput({ decision: "AGENT_COMPLETE", reason: "NO_PROGRESS" }), undefined);
});

test("classifier moves to the next selector and writes no session", async () => {
  const calls: string[] = [];
  const generate: GenerateFn = async (call) => {
    calls.push(`${call.providerID}/${call.modelID}`);
    if (calls.length === 1) return { text: "not a tool" };
    return { toolInput: { decision: "AGENT_CONTINUING", reason: "WORK_REMAINS" } };
  };
  const result = await classify([
    { providerID: "p", modelID: "one" },
    { providerID: "p", modelID: "two" },
  ], input, generate);
  assert.equal(result.verdict?.decision, "AGENT_CONTINUING");
  assert.equal(result.capture.attempts, 2);
  assert.equal(result.capture.sessionID, null);
  assert.deepEqual(calls, ["p/one", "p/two"]);
});

test("timeout cycles through the selector list", async () => {
  process.env.MODERATOR_TIMEOUT_CYCLES = "2";
  const calls: string[] = [];
  const generate: GenerateFn = async (call) => {
    calls.push(`${call.modelID}`);
    if (calls.length < 4) throw new Error("moderator classifier timed out");
    return { toolInput: { decision: "AGENT_CONTINUING", reason: "WORK_REMAINS" } };
  };
  const result = await classify([
    { providerID: "p", modelID: "one" },
    { providerID: "p", modelID: "two" },
  ], input, generate);
  delete process.env.MODERATOR_TIMEOUT_CYCLES;
  assert.equal(result.verdict?.decision, "AGENT_CONTINUING");
  assert.deepEqual(calls, ["one", "two", "one", "two"]);
});

test("format failure does not start another cycle", async () => {
  process.env.MODERATOR_TIMEOUT_CYCLES = "3";
  let calls = 0;
  const generate: GenerateFn = async () => {
    calls += 1;
    return { text: "no verdict" };
  };
  const result = await classify([{ providerID: "p", modelID: "one" }], input, generate);
  delete process.env.MODERATOR_TIMEOUT_CYCLES;
  assert.equal(result.verdict, undefined);
  assert.equal(calls, 1);
});

test("classifier fails closed after every selector", async () => {
  const generate: GenerateFn = async () => ({ text: "no verdict" });
  const result = await classify([{ providerID: "p", modelID: "one" }], input, generate);
  assert.equal(result.verdict, undefined);
  assert.equal(result.capture.sessionID, null);
  assert.ok(result.error);
});
