import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createModerationAdapter, type ModerationClient } from "../src/moderation/adapter.ts";
import { sessionDirectory } from "../src/moderation/audit.ts";
import type { MessageFact, TodoFact } from "../src/moderation/types.ts";

const options = { gatewayURL: "http://127.0.0.1:9080/llamafile", model: "/zip/MiniCPM5-1B-Q8_0.gguf" };

test("a failed response triggers a persisted continuation prompt", async (context) => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter01";
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "I stopped early.")]);
  const adapter = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_CONTINUING\nreason: WORK_REMAINS"));
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.promptAsyncCalls.length > 0, "continuation prompt was not sent");
    assert.equal(store.promptAsyncCalls.length, 1);
    assert.match(store.promptAsyncCalls[0].text, /Automated Moderation: work appears unfinished/);
    assert.equal(store.promptAsyncCalls[0].synthetic, true);
    assert.deepEqual(store.promptAsyncCalls[0].metadata, { moderation: true });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    await store.waitFor(() => store.toasts.includes("continuing"), "continuation toast was not shown");
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
  context.diagnostic(`adapter session ${sessionID}`);
});

test("a passing response does not prompt the agent again", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-pass-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter02";
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "All done.")]);
  const adapter = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_COMPLETE\nreason: WORK_COMPLETE"));
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.toasts.includes("complete"), "complete toast was not shown");
    assert.equal(store.promptAsyncCalls.length, 0);
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("a mid-turn tool-calling step is ignored, not moderated", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-toolcalls-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter07";
  const step = assistant("msg_1", "user_1", "Running the tests now.");
  step.info.finish = "tool-calls";
  const store = new Harness([user("user_1", "Finish the task."), step]);
  const captured: string[] = [];
  const adapter = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_COMPLETE\nreason: WORK_COMPLETE", captured));
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await waitForDecisionType(sessionID, "ignored-nonterminal-assistant", "a tool-calling step was not ignored");
    assert.equal(captured.length, 0, "a tool-calling step must never reach the classifier");
    assert.equal(store.promptAsyncCalls.length, 0, "a tool-calling step must not prompt the agent");
    assert.equal(store.toasts.length, 0, "a tool-calling step must not show a moderation outcome");
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("a user-stop verdict stands down without prompting or writing a transcript line", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-userstop-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter08";
  const store = new Harness([user("user_1", "Optimize the build until it is as fast as possible."), assistant("msg_1", "user_1", "I stopped the test run.")], [{ status: "in_progress", priority: "high" }]);
  const captured: string[] = [];
  const adapter = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_STOPPED\nreason: USER_STOP", captured));
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.toasts.includes("user-stop"), "user-stop toast was not shown");
    await waitForDecisionType(sessionID, "moderation-user-stop", "user-stop decision was not recorded");
    assert.equal(captured.length, 1, "the classifier should decide the user-stop outcome");
    assert.equal(store.promptAsyncCalls.length, 0, "a user stop must never prompt a continuation");
    assert.equal(store.messages.length, 2, "a user stop must not write a transcript line");
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("an interrupted assistant is ignored as a cancellation, never re-moderated", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-cancel-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter09";
  const aborted = assistant("msg_2", "msg_1", "");
  aborted.info.error = { name: "MessageAbortedError" };
  delete aborted.info.finish;
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "I stopped early."), aborted]);
  const captured: string[] = [];
  const adapter = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_CONTINUING\nreason: WORK_REMAINS", captured));
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await waitForDecisionType(sessionID, "ignored-cancellation", "an interrupted assistant was not ignored");
    assert.equal(captured.length, 0, "an interrupted assistant must not be classified");
    assert.equal(store.promptAsyncCalls.length, 0, "an interrupted assistant must not prompt the agent");
    assert.equal(store.toasts.length, 0, "an interrupted assistant must not show a moderation outcome");
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("pending todos are handed to the classifier, whose AGENT_COMPLETE ends the cycle", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-required-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter03";
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "Partially done.")], [{ status: "pending", priority: "high" }]);
  const captured: string[] = [];
  const adapter = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_COMPLETE\nreason: WORK_COMPLETE", captured));
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.toasts.includes("complete"), "complete toast was not shown");
    assert.equal(captured.length, 1);
    assert.match(captured[0], /\[pending\]/);
    assert.equal(store.promptAsyncCalls.length, 0);
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("pending todos with an AGENT_CONTINUING verdict trigger a continuation", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-required-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter04";
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "Partially done.")], [{ status: "in_progress", priority: "high" }]);
  const captured: string[] = [];
  const adapter = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_CONTINUING\nreason: WORK_REMAINS", captured));
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.promptAsyncCalls.length > 0, "continuation was not sent");
    assert.equal(captured.length, 1);
    assert.match(captured[0], /\[in_progress\]/);
    assert.match(store.promptAsyncCalls[0].text, /Automated Moderation: work appears unfinished/);
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("a response to an injected continuation is moderated", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-continuation-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter05";
  const continuation = user("cont_1", "⚠️ Automated Moderation: work appears unfinished; continue unless explicitly requested to halt by the operator or the system.");
  continuation.info.parentID = "msg_1";
  const store = new Harness([
    user("user_1", "Finish the task."),
    assistant("msg_1", "user_1", "I stopped early."),
    continuation,
    assistant("msg_2", "cont_1", "Now I finished the task."),
  ]);
  const captured: string[] = [];
  const adapter = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_COMPLETE\nreason: WORK_COMPLETE", captured));
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.toasts.includes("complete"), "continuation reply was not moderated");
    assert.equal(captured.length, 1);
    assert.match(captured[0], /Now I finished the task/);
    assert.equal(store.promptAsyncCalls.length, 0);
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("the agent's reply to an injected continuation is classified and can complete", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-second-cycle-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter06";
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "I stopped early.")]);
  const captured: string[] = [];
  const adapter = createModerationAdapter(
    { client: store.client },
    options,
    classifierSequence(["decision: AGENT_CONTINUING\nreason: WORK_REMAINS", "decision: AGENT_COMPLETE\nreason: WORK_COMPLETE"], captured),
  );
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.promptAsyncCalls.length === 1, "first cycle did not send a continuation");
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    await waitForDecisionType(sessionID, "continuation-verified", "continuation was not verified");
    store.messages.push(assistant("msg_2", "cont_1", "Now I finished the task and the tests pass."));
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.toasts.includes("complete"), "the reply to the continuation was never moderated");
    assert.equal(captured.length, 2);
    assert.match(captured[1], /Now I finished the task/);
    assert.equal(store.promptAsyncCalls.length, 1);
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("the status protocol is appended to the system prompt once", async () => {
  const store = new Harness([]);
  const adapter = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_COMPLETE\nreason: WORK_COMPLETE"));
  const output = { system: [] as string[] };
  await adapter["experimental.chat.system.transform"]({}, output);
  await adapter["experimental.chat.system.transform"]({}, output);
  assert.equal(output.system.length, 1);
  assert.match(output.system[0], /STATUS: COMPLETE/);
});

test("a declared status line decides without the classifier", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-declared-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter12";
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "I need your answer.\nSTATUS: WAITING_FOR_USER")]);
  const captured: string[] = [];
  const adapter = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_CONTINUING\nreason: WORK_REMAINS", captured));
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.toasts.includes("agent-blocked"), "the declared status was not applied");
    assert.equal(captured.length, 0, "a declared status must not call the classifier");
    assert.equal(store.promptAsyncCalls.length, 0, "a declared handoff must not prompt a continuation");
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("a user message arriving during classification cancels the continuation", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-race-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter11";
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "I stopped early.")]);
  const fetchImpl = async (url: string, init?: RequestInit) => {
    if (url.endsWith("/input_tokens")) return new Response(JSON.stringify({ input_tokens: 64 }), { status: 200 });
    store.messages.push(user("user_2", "Wait, stop the work."));
    return new Response(JSON.stringify({ choices: [{ finish_reason: "stop", message: { content: "decision: AGENT_CONTINUING\nreason: WORK_REMAINS" } }] }), { status: 200 });
  };
  const adapter = createModerationAdapter({ client: store.client }, options, fetchImpl);
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await waitForDecisionType(sessionID, "moderation-error", "the cancelled continuation was not recorded");
    assert.equal(store.promptAsyncCalls.length, 0, "a user message after the judged response must cancel the continuation");
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("moderation resumes after a restart instead of going stale", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-adapter-restart-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const sessionID = "ses_adapter10";
  const store = new Harness([user("user_1", "Finish the task."), assistant("msg_1", "user_1", "All done.")]);
  try {
    const first = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_COMPLETE\nreason: WORK_COMPLETE"));
    first.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    first.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.toasts.includes("complete"), "the first session did not complete");

    store.messages.push(assistant("msg_2", "user_1", "I stopped early again."));
    const captured: string[] = [];
    const second = createModerationAdapter({ client: store.client }, options, classifierFetch("decision: AGENT_CONTINUING\nreason: WORK_REMAINS", captured));
    second.event({ event: { type: "session.status", properties: { sessionID, status: { type: "busy" } } } });
    second.event({ event: { type: "session.status", properties: { sessionID, status: { type: "idle" } } } });
    await store.waitFor(() => store.promptAsyncCalls.length > 0, "the resumed session was not moderated");
    assert.equal(captured.length, 1, "a new terminal assistant after restore must be classified");
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

class Harness {
  readonly messages: MessageFact[];
  readonly todos: TodoFact[];
  readonly promptAsyncCalls: { text: string; synthetic?: boolean; metadata?: unknown }[] = [];
  readonly toasts: string[] = [];
  readonly client: ModerationClient;

  constructor(messages: MessageFact[], todos: TodoFact[] = []) {
    this.messages = messages;
    this.todos = todos;
    this.client = {
      session: {
        todo: async () => ({ data: this.todos }),
        messages: async () => ({ data: this.messages }),
        prompt: async (call) => {
          const id = `trace_${this.messages.length}`;
          this.messages.push({ info: { id, role: "user", time: { created: Date.now() } }, parts: [{ type: "text", text: String((call.body.parts as { text: string }[])[0].text) }] });
          return { data: { info: { id } } };
        },
        promptAsync: async (call) => {
          const part = (call.body.parts as { text: string; synthetic?: boolean; metadata?: unknown }[])[0];
          const text = String(part.text);
          this.promptAsyncCalls.push({ text, synthetic: part.synthetic, metadata: part.metadata });
          const id = `cont_${this.promptAsyncCalls.length}`;
          this.messages.push({ info: { id, role: "user", time: { created: Date.now() } }, parts: [{ type: "text", text, synthetic: part.synthetic, metadata: part.metadata as { moderation?: boolean } }] });
        },
      },
      tui: {
        showToast: async (call) => {
          this.toasts.push(toastKind(String(call.body.title)));
          return null;
        },
      },
    };
  }

  async waitFor(condition: () => boolean, message: string): Promise<void> {
    for (let attempt = 0; attempt < 100; attempt += 1) {
      if (condition()) return;
      await new Promise((resolve) => { setTimeout(resolve, 50); });
    }
    throw new Error(message);
  }
}

async function waitForDecisionType(sessionID: string, type: string, message: string): Promise<void> {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if ((await decisionTypes(sessionID)).includes(type)) return;
    await new Promise((resolve) => { setTimeout(resolve, 50); });
  }
  throw new Error(message);
}

async function decisionTypes(sessionID: string): Promise<string[]> {
  let names: string[];
  try {
    names = await readdir(sessionDirectory(sessionID));
  } catch (error) {
    if ((error as { code?: string }).code === "ENOENT") return [];
    throw error;
  }
  const types: string[] = [];
  for (const name of names.filter((entry) => entry.startsWith("decision-") && entry.endsWith(".yaml"))) {
    const parsed = JSON.parse(await readFile(join(sessionDirectory(sessionID), name), "utf8")) as Record<string, unknown>;
    if (typeof parsed.decisionType === "string") types.push(parsed.decisionType);
  }
  return types;
}

function toastKind(title: string): string {
  if (title.includes("complete")) return "complete";
  if (title.includes("agent blocked")) return "agent-blocked";
  if (title.includes("operator handoff")) return "operator-handoff";
  if (title.includes("user stop")) return "user-stop";
  if (title.includes("continuing")) return "continuing";
  if (title.includes("escalation")) return "escalated";
  if (title.includes("error")) return "error";
  return "checking";
}

function classifierFetch(verdict: string, captured: string[] = []): (url: string, init?: RequestInit) => Promise<Response> {
  return async (url, init) => {
    if (url.endsWith("/input_tokens")) return new Response(JSON.stringify({ input_tokens: 64 }), { status: 200 });
    captured.push(String(init?.body));
    return new Response(JSON.stringify({ choices: [{ finish_reason: "stop", message: { content: verdict } }] }), { status: 200 });
  };
}

function classifierSequence(verdicts: string[], captured: string[] = []): (url: string, init?: RequestInit) => Promise<Response> {
  let index = 0;
  return async (url, init) => {
    if (url.endsWith("/input_tokens")) return new Response(JSON.stringify({ input_tokens: 64 }), { status: 200 });
    captured.push(String(init?.body));
    const verdict = verdicts[Math.min(index, verdicts.length - 1)];
    index += 1;
    return new Response(JSON.stringify({ choices: [{ finish_reason: "stop", message: { content: verdict } }] }), { status: 200 });
  };
}

function user(id: string, content: string): MessageFact {
  return { info: { id, role: "user", time: { created: 1 } }, parts: [{ type: "text", text: content }] };
}

function assistant(id: string, parentID: string, content: string): MessageFact {
  return { info: { id, parentID, role: "assistant", finish: "stop", time: { created: 2 } }, parts: [{ type: "text", text: content }] };
}