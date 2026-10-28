import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { classify, classifyWithPrompt } from "../src/moderation/classifier.ts";
import { loadClassifierCases, scoreClassifierCase } from "./support/classifier-cases.ts";

const options = {
  gatewayURL: "http://127.0.0.1:9080/llamafile",
  model: process.env.AGENTCI_LIVE_MODEL ?? "/zip/MiniCPM5-1B-Q8_0.gguf",
};

const REPEAT = Number(process.env.AGENTCI_CASES_REPEAT ?? 1);
const REPORT = process.env.AGENTCI_CASES_REPORT === "1";
const PROMPT_PATH = process.env.AGENTCI_CASE_PROMPT;

test("mined classifier cases honor their exact or forbidden decision", { timeout: 900000 }, async () => {
  assert.ok(Number.isInteger(REPEAT) && REPEAT >= 1, "AGENTCI_CASES_REPEAT must be a positive integer");
  const fixture = await loadClassifierCases();
  const set = process.env.AGENTCI_CASES_SET;
  if (set !== undefined && !["operator", "mined"].includes(set)) throw new Error("AGENTCI_CASES_SET must be 'operator' or 'mined'");
  const only = process.env.AGENTCI_CASES_IDS?.split(",").map((value) => value.trim()).filter((value) => value.length > 0);
  const selected = only === undefined
    ? (set === undefined ? fixture : fixture.filter((value) => value.labelSource === set))
    : fixture.filter((value) => only.includes(value.id) && (set === undefined || value.labelSource === set));
  const limit = Number(process.env.AGENTCI_CASES_LIMIT ?? selected.length);
  const cases = selected.slice(0, limit);
  assert.ok(cases.length > 0, "expected at least one classifier case");
  const prompt = PROMPT_PATH === undefined ? null : await readFile(PROMPT_PATH, "utf8");
  const failures: string[] = [];
  const observed = new Map<string, number>();
  let total = 0;
  for (let run = 1; run <= REPEAT; run += 1) {
    for (const value of cases) {
      total += 1;
      const input = { todos: value.inputs.todos, previousResponse: value.inputs.previousResponse, userMessages: value.inputs.userMessages };
      const outcome = prompt === null ? await classify(options, input) : await classifyWithPrompt(options, input, prompt);
      if (outcome.formatError || !outcome.verdict) {
        failures.push(`run ${run} ${value.id}: no parseable verdict (capture: ${JSON.stringify(outcome.capture.completion)})`);
        continue;
      }
      const verdict = outcome.verdict;
      observed.set(`${verdict.decision}/${verdict.reasonCode}`, (observed.get(`${verdict.decision}/${verdict.reasonCode}`) ?? 0) + 1);
      const detail = scoreClassifierCase(value, verdict);
      if (detail === null) {
        if (REPORT) console.log(`PASS run ${run} ${value.id} ${verdict.decision}/${verdict.reasonCode}`);
      } else {
        failures.push(`run ${run} ${value.id}: ${detail}`);
        console.log(`FAIL run ${run} ${value.id}: ${detail}`);
      }
    }
  }
  console.log(`cases: ${cases.length} repeat: ${REPEAT} attempts: ${total} prompt: ${PROMPT_PATH ?? "source"}`);
  console.log(`observed: ${[...observed.entries()].sort().map(([key, count]) => `${key}=${count}`).join(", ")}`);
  assert.deepEqual(failures, [], `classifier case failures:\n${failures.join("\n")}`);
});
