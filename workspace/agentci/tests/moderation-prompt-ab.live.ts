import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { classifyWithPrompt, SYSTEM_PROMPT } from "../src/moderation/classifier.ts";
import type { TodoFact, Verdict, VerdictDecision } from "../src/moderation/types.ts";

const options = { gatewayURL: "http://127.0.0.1:9080/llamafile", model: "/zip/MiniCPM5-1B-Q8_0.gguf" };
const BASELINE_PROMPT = await readFile(new URL("./fixtures/moderation-system-prompt-baseline.txt", import.meta.url), "utf8");

type Expectation = "CONTINUE" | "STOP" | "HANDOFF";

interface Scenario {
  id: string;
  userMessages: readonly string[];
  previousResponse: string;
  todos?: readonly TodoFact[];
  expectation: Expectation;
}

const SCENARIOS: readonly Scenario[] = [
  {
    id: "empty-abort-work-remains",
    userMessages: [""],
    previousResponse: "I implemented the parser. The writer is not started yet.",
    todos: [
      { status: "in_progress", content: "Implement parser" },
      { status: "pending", content: "Implement writer" },
    ],
    expectation: "CONTINUE",
  },
  {
    id: "whitespace-abort-work-remains",
    userMessages: ["   "],
    previousResponse: "I fixed the backdrop. The copy-based scene pass is not done.",
    todos: [{ status: "pending", content: "Copy-based scene pass" }],
    expectation: "CONTINUE",
  },
  {
    id: "empty-abort-after-error",
    userMessages: [""],
    previousResponse: "The last command failed. I will retry the verification step.",
    todos: [{ status: "in_progress", content: "Retry verification" }],
    expectation: "CONTINUE",
  },
  {
    id: "rhetorical-done-question",
    userMessages: ["Are we done here? Keep going until the tests pass."],
    previousResponse: "The tests do not pass yet. I am fixing the remaining failures.",
    todos: [{ status: "in_progress", content: "Fix failing tests" }],
    expectation: "CONTINUE",
  },
  {
    id: "explicit-stop-control",
    userMessages: ["Stop right now. Do not continue."],
    previousResponse: "Understood. I have stopped.",
    todos: [{ status: "pending", content: "Finish the task" }],
    expectation: "STOP",
  },
  {
    id: "operator-reproduction-handoff",
    userMessages: ["start the diag run, record a replay named something appropriate, I will reproduce it"],
    previousResponse: "Diagnostic run is live. Reproduce the flare now. Hold the view for about 15 seconds. When done, tell me. I will stop the video and game, then analyze.",
    todos: [{ status: "in_progress", content: "Capture the lens flare reproduction" }],
    expectation: "HANDOFF",
  },
];

test("classifier prompt A/B: hardened empty-message rule", { timeout: 180000 }, async () => {
  for (const scenario of SCENARIOS) {
    const baseline = await verdictFor(BASELINE_PROMPT, scenario);
    const hardened = await verdictFor(SYSTEM_PROMPT, scenario);
    console.log(`A/B ${scenario.id}: baseline=${baseline.decision} hardened=${hardened.decision}`);
    if (scenario.expectation === "STOP") {
      assert.equal(hardened.decision, "AGENT_STOPPED", `${scenario.id}: hardened prompt lost the explicit halt`);
      assert.equal(hardened.reasonCode, "USER_STOP", `${scenario.id}: hardened prompt used the wrong stop reason`);
    } else if (scenario.expectation === "HANDOFF") {
      assert.equal(hardened.decision, "AGENT_BLOCKED", `${scenario.id}: hardened prompt missed the handoff`);
      assert.equal(hardened.reasonCode, "AWAITING_OPERATOR", `${scenario.id}: hardened prompt used the wrong handoff reason`);
    } else {
      const hardenedContinues = hardened.decision === "AGENT_CONTINUING" || hardened.decision === "AGENT_STALLED";
      const stoodDown = hardened.decision === "AGENT_STOPPED" && baseline.decision !== "AGENT_STOPPED";
      assert.ok(
        hardenedContinues || !stoodDown,
        `${scenario.id}: hardened prompt stood down on unfinished work (baseline ${baseline.decision}, hardened ${hardened.decision})`,
      );
    }
  }
});

async function verdictFor(systemPrompt: string, scenario: Scenario): Promise<Verdict> {
  const outcome = await classifyWithPrompt(options, {
    todos: scenario.todos ?? [],
    previousResponse: scenario.previousResponse,
    userMessages: scenario.userMessages,
  }, systemPrompt);
  assert.equal(outcome.formatError, false, `${scenario.id}: classifier returned no parseable verdict`);
  const verdict = outcome.verdict;
  assert.ok(verdict, `${scenario.id}: classifier returned no verdict`);
  assert.ok(isDecision(verdict.decision), `${scenario.id}: classifier returned an invalid decision`);
  return verdict;
}

function isDecision(value: string): value is VerdictDecision {
  return value === "AGENT_COMPLETE" || value === "AGENT_CONTINUING" || value === "AGENT_STALLED" || value === "AGENT_BLOCKED" || value === "AGENT_STOPPED";
}
