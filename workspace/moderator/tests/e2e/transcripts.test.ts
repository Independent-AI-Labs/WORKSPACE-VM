import assert from "node:assert/strict";
import { mkdtemp, readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createModeratorAdapter, type ModeratorClient } from "../../src/adapter.ts";
import { sessionDirectory } from "../../src/audit.ts";
import { generateWithLLM } from "../../src/generate.ts";
import type { MessageFact } from "../../src/types.ts";
import { loadClassifierCases, scoreClassifierCase } from "../support/classifier-cases.ts";

function history(sessionID: string, userMessages: readonly string[], response: string, answer: boolean): MessageFact[] {
  const users = userMessages.map((text, index) => ({
    info: { id: `${sessionID}-u${index}`, role: "user" as const, parentID: index === 0 ? undefined : `${sessionID}-u${index - 1}`, time: { created: index + 1 } },
    parts: [{ type: "text", text }],
  }));
  const parent = users.at(-1)?.info.id;
  return [
    ...users,
    {
      info: { id: `${sessionID}-a`, role: "assistant", parentID: parent, finish: "stop", time: { created: users.length + 1 }, agent: answer ? "answer" : "build" },
      parts: [{ type: "text", text: response }],
    },
  ];
}

async function runCase(sessionID: string, messages: MessageFact[], todos: Array<{ status?: string; content?: string }>, selectors: Array<{ providerID: string; modelID: string }>): Promise<{ traces: string[]; continuations: number; decisions: string }> {
  const root = await mkdtemp(join(tmpdir(), "moderator-e2e-"));
  process.env.XDG_STATE_HOME = join(root, "state");
  const traces: string[] = [];
  let continuations = 0;
  const client = {
    session: {
      async prompt(input: { body: Record<string, unknown> }) {
        const parts = input.body.parts as Array<{ text?: string }>;
        traces.push(parts[0]?.text ?? "");
        return { data: { info: { id: `m${traces.length}` } } };
      },
      async promptAsync() {
        continuations += 1;
        return { data: { info: { id: "c1" } } };
      },
      async messages() { return { data: messages }; },
      async todo() { return { data: todos }; },
      async revert() { return {}; },
    },
    tui: { async showToast() { return {}; } },
  } as ModeratorClient;
  const adapter = createModeratorAdapter({ client, generate: generateWithLLM }, selectors);
  adapter.event({ type: "session.status", properties: { sessionID, status: { type: "busy" } } });
  adapter.event({ type: "session.status", properties: { sessionID, status: { type: "idle" } } });
  const decisionPath = join(sessionDirectory(sessionID), "decisions.jsonl");
  const started = Date.now();
  let decisions = "";
  while (Date.now() - started < 45000) {
    try {
      decisions = await readFile(decisionPath, "utf8");
      if (decisions.includes("VERDICT") || decisions.includes("EFFECT_ERROR")) break;
    } catch {
      decisions = "";
    }
    await new Promise((resolve) => { setTimeout(resolve, 200); });
  }
  return { traces, continuations, decisions };
}

const cases = await loadClassifierCases();
const selectors = [{ providerID: "workspace-gw-opencode-go-api-key", modelID: "gpt-6-luna" }];
let labeled = 0;
let labeledMatched = 0;
for (const item of cases) {
  const messages = history(item.id, item.inputs.userMessages, item.inputs.previousResponse, item.inputs.answerMode === true);
  const result = await runCase(item.id, messages, item.inputs.todos, selectors);
  const line = result.decisions.split("\n").find((entry) => entry.includes("\"VERDICT\""));
  const record = line === undefined ? undefined : JSON.parse(line) as { verdict?: { decision?: string; reasonCode?: string }; error?: string };
  const verdict = record?.verdict?.decision && record.verdict.reasonCode
    ? { decision: record.verdict.decision, reasonCode: record.verdict.reasonCode }
    : undefined;
  const errorLine = result.decisions.split("\n").find((entry) => entry.includes("EFFECT_ERROR"));
  const errorRecord = errorLine === undefined ? undefined : JSON.parse(errorLine) as { error?: string };
  const mismatch = verdict === undefined ? errorRecord?.error ?? "no verdict" : scoreClassifierCase(item, verdict);
  if (mismatch === null) labeledMatched += 1;
  labeled += 1;
  process.stdout.write(`${item.id} got=${verdict ? `${verdict.decision}/${verdict.reasonCode}` : "ERROR"} traces=${result.traces.length} continuations=${result.continuations} ${mismatch ?? "ok"}\n`);
}
assert.equal(labeled, 100);
assert.equal(labeledMatched, labeled);
