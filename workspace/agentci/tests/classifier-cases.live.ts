import assert from "node:assert/strict";
import test from "node:test";
import { classify } from "../src/moderation/classifier.ts";
import { loadClassifierCases } from "./support/classifier-cases.ts";

const options = {
  gatewayURL: "http://127.0.0.1:9080/llamafile",
  model: process.env.AGENTCI_LIVE_MODEL ?? "/zip/MiniCPM5-1B-Q8_0.gguf",
};

test("mined classifier cases honor their exact or forbidden decision", { timeout: 600000 }, async () => {
  const fixture = await loadClassifierCases();
  const limit = Number(process.env.AGENTCI_CASES_LIMIT ?? fixture.length);
  const cases = fixture.slice(0, limit);
  assert.ok(cases.length > 0, "expected at least one classifier case");
  const failures: string[] = [];
  for (const value of cases) {
    const outcome = await classify(options, {
      todos: value.inputs.todos,
      previousResponse: value.inputs.previousResponse,
      userMessages: value.inputs.userMessages,
    });
    if (outcome.formatError || !outcome.verdict) {
      failures.push(`${value.id}: no parseable verdict (capture: ${JSON.stringify(outcome.capture.completion)})`);
      continue;
    }
    const verdict = outcome.verdict;
    if (value.expectedDecision) {
      if (verdict.decision !== value.expectedDecision) failures.push(`${value.id}: expected ${value.expectedDecision}, got ${verdict.decision}`);
      else if (value.expectedReason && verdict.reasonCode !== value.expectedReason) failures.push(`${value.id}: expected ${value.expectedReason}, got ${verdict.reasonCode}`);
    } else if (value.forbiddenDecisions.includes(verdict.decision)) {
      failures.push(`${value.id}: repeated the mined failure ${verdict.decision} (${verdict.reasonCode})`);
    }
  }
  assert.deepEqual(failures, [], `classifier case failures:\n${failures.join("\n")}`);
});
