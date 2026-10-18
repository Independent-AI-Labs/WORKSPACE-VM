import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { sessionDirectory } from "../src/moderation/audit.ts";
import { replayDecisionType, replayLastDecision, resolveReplaySession, runReplay, type ReplayClient, type ReplaySessionSummary } from "../src/moderation/replay.ts";
import type { MessageFact, TodoFact } from "../src/moderation/types.ts";

const options = { gatewayURL: "http://127.0.0.1:9080/llamafile", model: "/zip/MiniCPM5-1B-Q8_0.gguf" };
const CONTINUATION_LINE = "⚠️ Automated Moderation: work appears unfinished; continue unless explicitly requested to halt by the operator or the system.";
const COMPLETE_LINE = "✅ Automated Moderation: work completion verified.";

test("resolveReplaySession honors an explicit id and otherwise picks the newest listed session", async () => {
  const store = new Harness([], []);
  assert.equal(await resolveReplaySession(store.client, "ses_explicit"), "ses_explicit");
  await assert.rejects(resolveReplaySession(store.client, "not a session id"), /invalid session id/);
  await assert.rejects(resolveReplaySession(store.client), /no moderated session/);
  store.sessions.push(
    { id: "ses_older", time: { updated: 1000 } },
    { id: "ses_newer", time: { updated: 2000 } },
    { id: "ses_middle", time: { updated: 1500 } },
  );
  assert.equal(await resolveReplaySession(store.client), "ses_newer");
});

test("replaying a continuation reverts the moderator line, recomputes, and sends a new prompt", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-replay-continue-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_replay01";
  const store = new Harness([
    user("user_1", "Finish the task."),
    assistant("msg_1", "user_1", "I stopped early."),
    user("cont_1", CONTINUATION_LINE),
  ]);
  try {
    const captured: string[] = [];
    const result = await replayLastDecision({ client: store.client, options, sessionID, fetchImpl: classifierFetch("decision: AGENT_CONTINUING\nreason: WORK_REMAINS", captured) });
    assert.deepEqual(store.revertCalls, ["cont_1"]);
    assert.equal(captured.length, 1);
    assert.match(captured[0], /I stopped early/);
    assert.equal(store.promptAsyncCalls.length, 1);
    assert.match(store.promptAsyncCalls[0], /work appears unfinished/);
    assert.equal(result.revertedMessageID, "cont_1");
    assert.equal(result.decisionType, "moderation-continue");
    const replay = await replayRecords(sessionID);
    assert.equal(replay.length, 1);
    assert.equal(replay[0].revertedMessageID, "cont_1");
  } finally {
    await restoreState(previous);
    await rm(home, { recursive: true, force: true });
  }
});

test("replaying a completion writes a passive trace and never prompts upstream", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-replay-complete-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_replay02";
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "All done.")], []);
  try {
    const result = await replayLastDecision({ client: store.client, options, sessionID, fetchImpl: classifierFetch("decision: AGENT_COMPLETE\nreason: WORK_COMPLETE") });
    assert.deepEqual(store.revertCalls, []);
    assert.equal(store.promptAsyncCalls.length, 0);
    assert.equal(store.promptCalls.length, 1);
    assert.equal(store.promptCalls[0], COMPLETE_LINE);
    assert.equal(result.decisionType, "moderation-complete");
  } finally {
    await restoreState(previous);
    await rm(home, { recursive: true, force: true });
  }
});

test("replaying a user stop writes no transcript line and only toasts", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-replay-stop-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_replay03";
  const store = new Harness([user("user_1", "Stop now."), assistant("msg_1", "user_1", "Stopped.")]);
  try {
    const result = await replayLastDecision({ client: store.client, options, sessionID, fetchImpl: classifierFetch("decision: AGENT_STOPPED\nreason: USER_STOP") });
    assert.equal(store.promptAsyncCalls.length, 0);
    assert.equal(store.promptCalls.length, 0);
    assert.equal(store.toasts.length, 1);
    assert.equal(result.decisionType, "moderation-user-stop");
  } finally {
    await restoreState(previous);
    await rm(home, { recursive: true, force: true });
  }
});

test("runReplay surfaces a missing session as a toast without rejecting", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-replay-empty-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "Done.")]);
  try {
    await runReplay(store.client, options);
    assert.equal(store.toasts.length, 1);
    assert.match(store.toasts[0], /replay failed/);
    assert.equal(store.revertCalls.length, 0);
  } finally {
    await restoreState(previous);
    await rm(home, { recursive: true, force: true });
  }
});

test("replayDecisionType maps every verdict decision to its audit type", () => {
  assert.equal(replayDecisionType("AGENT_COMPLETE"), "moderation-complete");
  assert.equal(replayDecisionType("AGENT_BLOCKED"), "moderation-agent-blocked");
  assert.equal(replayDecisionType("AGENT_STOPPED"), "moderation-user-stop");
  assert.equal(replayDecisionType("AGENT_CONTINUING"), "moderation-continue");
  assert.equal(replayDecisionType("AGENT_STALLED"), "moderation-continue");
});

class Harness {
  readonly messages: MessageFact[];
  readonly todos: TodoFact[];
  readonly sessions: ReplaySessionSummary[] = [];
  readonly revertCalls: string[] = [];
  readonly promptAsyncCalls: string[] = [];
  readonly promptCalls: string[] = [];
  readonly toasts: string[] = [];
  readonly client: ReplayClient;

  constructor(messages: MessageFact[], todos: TodoFact[] = []) {
    this.messages = messages;
    this.todos = todos;
    this.client = {
      session: {
        todo: async () => ({ data: this.todos }),
        messages: async () => ({ data: this.messages }),
        list: async () => ({ data: this.sessions }),
        prompt: async (call) => {
          const text = String((call.body.parts as { text: string }[])[0].text);
          this.promptCalls.push(text);
          return { data: { info: { id: `trace_${this.promptCalls.length}` } } };
        },
        promptAsync: async (call) => {
          this.promptAsyncCalls.push(String((call.body.parts as { text: string }[])[0].text));
        },
        revert: async (call) => {
          this.revertCalls.push(call.body.messageID);
        },
      },
      tui: {
        showToast: async (call) => {
          this.toasts.push(String(call.body.message));
          return null;
        },
      },
    };
  }
}

async function replayRecords(sessionID: string): Promise<Record<string, unknown>[]> {
  const directory = sessionDirectory(sessionID);
  const names = await readdir(directory);
  const records: Record<string, unknown>[] = [];
  for (const name of names.filter((entry) => entry.startsWith("decision-") && entry.endsWith(".yaml"))) {
    const parsed = JSON.parse(await readFile(join(directory, name), "utf8")) as Record<string, unknown>;
    if (parsed.event === "REPLAY") records.push(parsed);
  }
  return records;
}

async function restoreState(previous: string | undefined): Promise<void> {
  if (previous === undefined) delete process.env.XDG_STATE_HOME;
  else process.env.XDG_STATE_HOME = previous;
}

function classifierFetch(verdict: string, captured: string[] = []): (url: string, init?: RequestInit) => Promise<Response> {
  return async (url, init) => {
    if (url.endsWith("/input_tokens")) return new Response(JSON.stringify({ input_tokens: 64 }), { status: 200 });
    captured.push(String(init?.body));
    return new Response(JSON.stringify({ choices: [{ finish_reason: "stop", message: { content: verdict } }] }), { status: 200 });
  };
}

function user(id: string, content: string): MessageFact {
  return { info: { id, role: "user", time: { created: 1 } }, parts: [{ type: "text", text: content }] };
}

function assistant(id: string, parentID: string, content: string): MessageFact {
  return { info: { id, parentID, role: "assistant", finish: "stop", time: { created: 2 } }, parts: [{ type: "text", text: content }] };
}