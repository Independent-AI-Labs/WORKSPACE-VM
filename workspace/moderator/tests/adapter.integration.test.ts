import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createModeratorAdapter, type ModeratorClient } from "../src/adapter.ts";
import type { MessageFact } from "../src/types.ts";

function history(response: string): MessageFact[] {
  return [
    { info: { id: "u1", role: "user", time: { created: 1 } }, parts: [{ type: "text", text: "finish the task" }] },
    { info: { id: "a1", role: "assistant", parentID: "u1", finish: "stop", time: { created: 2 }, agent: "build" }, parts: [{ type: "text", text: response }] },
  ];
}

interface Memory {
  client: ModeratorClient;
  traces: string[];
  continuations: number;
  toasts: string[];
}

function memory(response: string, decision: string, reason: string): Memory & { generate: (call: unknown) => Promise<{ toolInput: Record<string, string> }> } {
  const traces: string[] = [];
  const toasts: string[] = [];
  let continuations = 0;
  const messages = history(response);
  const client = {
    session: {
      async prompt(input: { path: { id: string }; body: Record<string, unknown> }) {
        const parts = input.body.parts as Array<{ text?: string }>;
        traces.push(parts[0]?.text ?? "");
        return { data: { info: { id: `m${traces.length}` } } };
      },
      async promptAsync() { continuations += 1; return { data: { info: { id: "c1" } } }; },
      async messages() { return { data: messages }; },
      async todo() { return { data: [] }; },
      async revert() { return {}; },
    },
    tui: {
      async showToast(input: { body: Record<string, unknown> }) {
        toasts.push(String(input.body.message ?? ""));
        return {};
      },
    },
  } as ModeratorClient;
  return {
    client,
    traces,
    toasts,
    get continuations() { return continuations; },
    generate: async () => ({ toolInput: { decision, reason } }),
  };
}

async function run(memoryValue: Memory & { generate: (call: unknown) => Promise<{ toolInput: Record<string, string> }> }, again = false): Promise<void> {
  const root = await mkdtemp(join(tmpdir(), "moderator-test-"));
  process.env.XDG_STATE_HOME = join(root, "state");
  process.env.XDG_CONFIG_HOME = join(root, "config");
  const adapter = createModeratorAdapter({ client: memoryValue.client, generate: memoryValue.generate }, [{ providerID: "p", modelID: "m" }]);
  adapter.event({ type: "session.status", properties: { sessionID: "s1", status: { type: "busy" } } });
  adapter.event({ type: "session.status", properties: { sessionID: "s1", status: { type: "idle" } } });
  await new Promise((resolve) => { setTimeout(resolve, 150); });
  if (!again) return;
  adapter.event({ type: "session.status", properties: { sessionID: "s1", status: { type: "busy" } } });
  adapter.event({ type: "session.status", properties: { sessionID: "s1", status: { type: "idle" } } });
  await new Promise((resolve) => { setTimeout(resolve, 150); });
}

test("complete response writes a trace and stops", async () => {
  const value = memory("done", "AGENT_COMPLETE", "WORK_COMPLETE");
  await run(value);
  assert.equal(value.traces.length, 1);
  assert.equal(value.continuations, 0);
});

test("unfinished response continues", async () => {
  const value = memory("more work remains", "AGENT_CONTINUING", "WORK_REMAINS");
  await run(value);
  assert.equal(value.continuations, 1);
  assert.equal(value.traces.length, 1);
});

test("a second idle for the same assistant does not classify again", async () => {
  const value = memory("done", "AGENT_COMPLETE", "WORK_COMPLETE");
  await run(value, true);
  assert.equal(value.traces.length, 1);
  assert.equal(value.continuations, 0);
});

test("root block writes the operator line and does not continue", async () => {
  const value = memory("```bash\nsudo reboot\n```", "AGENT_CONTINUING", "WORK_REMAINS");
  await run(value);
  assert.equal(value.continuations, 0);
  assert.equal(value.traces[0]?.includes("operator action required"), true);
});

test("replay reverts the moderator trace before classifying", async () => {
  const value = memory("Work remains.", "AGENT_CONTINUING", "WORK_REMAINS");
  const messages = value.client.session.messages as () => Promise<{ data: MessageFact[] }>;
  const history = (await messages()).data;
  history.push({ info: { id: "note", role: "user" }, parts: [{ type: "text", text: "⚠️ Automated Moderation: old ruling" }] });
  let reverted = "";
  value.client.session.revert = async (input: { body: { messageID: string } }) => {
    reverted = input.body.messageID;
    return {};
  };
  const root = await mkdtemp(join(tmpdir(), "moderator-test-"));
  process.env.XDG_STATE_HOME = join(root, "state");
  const adapter = createModeratorAdapter({ client: value.client, generate: value.generate }, [{ providerID: "p", modelID: "m" }]);
  await adapter.replay("s1", false);
  await new Promise((resolve) => { setTimeout(resolve, 150); });
  assert.equal(reverted, "note");
  assert.equal(value.continuations, 1);
});
