import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import { buildCaseState } from "../src/context.ts";
import { loadClassifierCases, loadClassifierManifest, type ClassifierCaseInputs, type ClassifierCaseManifest } from "./support/classifier-cases.ts";

function caseHash(value: ClassifierCaseManifest, inputs: ClassifierCaseInputs): string {
  return createHash("sha256").update(JSON.stringify({
    previousResponse: inputs.previousResponse,
    userMessages: inputs.userMessages,
    todos: inputs.todos,
  })).digest("hex");
}

test("classifier case manifest covers every decision and reason pair", async () => {
  const fixture = await loadClassifierManifest();
  assert.equal(fixture.cases.length, 100);
  const covered = new Set<string>();
  for (const value of fixture.cases) {
    if (value.expectedDecision && value.expectedReason) covered.add(`${value.expectedDecision}/${value.expectedReason}`);
  }
  for (const pair of [
    "AGENT_COMPLETE/WORK_COMPLETE",
    "AGENT_CONTINUING/WORK_REMAINS",
    "AGENT_STALLED/NO_PROGRESS",
    "AGENT_BLOCKED/AWAITING_USER",
    "AGENT_BLOCKED/AWAITING_OPERATOR",
    "AGENT_STOPPED/USER_STOP",
  ]) {
    assert.ok(covered.has(pair), `missing pathway coverage: ${pair}`);
  }
});

test("every transcript body matches its manifest hash and layout", async () => {
  const cases = await loadClassifierCases();
  assert.equal(cases.length, 100);
  for (const value of cases) {
    assert.equal(caseHash(value, value.inputs), value.hash, `${value.id}: transcript body does not match the manifest hash`);
    const content = buildCaseState({
      todos: value.inputs.todos,
      previousResponse: value.inputs.previousResponse,
      userMessages: value.inputs.userMessages,
      toolActivity: [],
      agentMode: value.inputs.answerMode === true ? "answer" : "build",
    });
    const responseIndex = content.indexOf("The agent's latest response (judge this):");
    const requestIndex = content.indexOf("User request(s):");
    assert.ok(responseIndex >= 0 && responseIndex < requestIndex, `${value.id}: response must precede the user requests`);
    assert.ok(content.includes(value.inputs.previousResponse), `${value.id}: response text missing from the request`);
  }
});
