import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createModerationAdapter, type ModerationClient } from "../src/moderation/adapter.ts";
import { classify } from "../src/moderation/classifier.ts";
import { sessionDirectory } from "../src/moderation/audit.ts";
import type { MessageFact, ReasonCode, TodoFact, Verdict, VerdictDecision } from "../src/moderation/types.ts";

const options = { gatewayURL: "http://127.0.0.1:9080/llamafile", model: "/zip/MiniCPM5-1B-Q8_0.gguf" };

interface Scenario {
  id: string;
  user: string;
  assistant: string;
  expectation: "CONTINUE" | "BLOCKED" | "STOP" | "ANY";
  reason?: ReasonCode;
  todos?: readonly TodoFact[];
}

const SCENARIOS: readonly Scenario[] = [
  {
    id: "ses_live_incomplete",
    user: "Implement the config loader and the CLI entrypoint, then test both.",
    assistant: "I implemented the config loader in src/config.ts. The CLI entrypoint is not started yet and no tests were written.",
    expectation: "CONTINUE",
  },
  {
    id: "ses_live_user_stop",
    user: "Why are you still running tests? Stop right now.",
    assistant: "Understood. I have stopped the test run.",
    expectation: "STOP",
    reason: "USER_STOP",
  },
  {
    id: "ses_live_empty_abort_continue",
    user: "",
    assistant: "I implemented the parser. The writer is not started yet.",
    expectation: "CONTINUE",
    reason: "WORK_REMAINS",
    todos: [
      { status: "in_progress", content: "Implement parser" },
      { status: "pending", content: "Implement writer" },
    ],
  },
  {
    id: "ses_live_blocked",
    user: "Deploy the service to production.",
    assistant: "I cannot deploy: the production deploy token is missing and only the operator can provision it. I need you to provide valid credentials before I can continue.",
    expectation: "BLOCKED",
  },
  {
    id: "ses_live_complete",
    user: "Add a hello() function to src/greeting.ts and run its test.",
    assistant: "Done. hello() is implemented in src/greeting.ts and I ran the test suite; it passes.",
    expectation: "ANY",
    reason: "WORK_COMPLETE",
  },
  {
    id: "ses_live_open_todos_continue",
    user: "Implement the config loader and the CLI entrypoint, then test both.",
    assistant: "I implemented the config loader in src/config.ts. I will implement the CLI entrypoint next, then add tests.",
    expectation: "CONTINUE",
    reason: "WORK_REMAINS",
    todos: [
      { status: "completed", content: "Implement the config loader" },
      { status: "pending", content: "Implement the CLI entrypoint" },
      { status: "pending", content: "Write tests for both" },
    ],
  },
  {
    id: "ses_live_open_todos_handover",
    user: "Fix the git guard pull --rebase deadlock and deploy it.",
    assistant: "Created /tmp/guard-rebase-064-deploy.sh (operator-only, not committed). Run it as the operator: `sudo bash /tmp/guard-rebase-064-deploy.sh`. I did not run it; tell me the result.",
    expectation: "BLOCKED",
    todos: [
      { status: "in_progress", content: "Refactor ArgState to ordered pull/merge modes" },
      { status: "pending", content: "Add scan_pull_args/scan_merge_args" },
      { status: "pending", content: "Update block.rs pull/merge/rebase rules" },
      { status: "pending", content: "Run make test / lint / test-shell" },
    ],
  },
  {
    id: "ses_live_operator_reproduction_handoff",
    user: "start the diag run, record a replay named something appropriate, I will reproduce it",
    assistant: "Diagnostic run is live.\n\n- Session: `lens-flare`\n- Video: recording\n- Replay file: `pfx/drive_c/recomp-record-lens-flare.txt`\n\nReproduce the flare now. Hold the view for about 15 seconds.\n\nWhen done, tell me. I will stop the video and game, then analyze.",
    expectation: "BLOCKED",
    todos: [{ status: "in_progress", content: "Capture the lens flare reproduction" }],
  },
  {
    id: "ses_live_open_todos_clarify",
    user: "Refactor the config loader to support env overrides.",
    assistant: "I can implement this with backward-compatible defaults or change the public API. Which behavior do you want? I need your decision before continuing.",
    expectation: "BLOCKED",
    reason: "AWAITING_USER",
    todos: [{ status: "in_progress", content: "Refactor the config loader" }],
  },
];

test("the live classifier returns grammar-valid verdicts through the Workspace Gateway relay", { timeout: 120000 }, async () => {
  for (const scenario of SCENARIOS) {
    const outcome = await classify(options, {
      todos: scenario.todos ?? [],
      previousResponse: scenario.assistant,
      userMessages: [scenario.user],
    });
    assert.equal(outcome.formatError, false, `${scenario.id}: no parseable verdict (capture: ${JSON.stringify(outcome.capture)})`);
    const verdict = outcome.verdict;
    assert.ok(verdict, `${scenario.id}: classifier returned no verdict`);
    assert.ok(isVerdictDecision(verdict.decision), `${scenario.id}: unexpected decision ${verdict.decision}`);
    assert.ok(verdict.reasonCode.length > 0, `${scenario.id}: verdict has no reason code`);
    if (scenario.expectation === "CONTINUE") assert.notEqual(verdict.decision, "AGENT_COMPLETE", `${scenario.id}: classifier passed an incomplete response`);
    if (scenario.expectation === "STOP") assert.equal(verdict.decision, "AGENT_STOPPED", `${scenario.id}: classifier did not honor the user's halt instruction`);
    if (scenario.expectation === "BLOCKED") assert.equal(verdict.decision, "AGENT_BLOCKED", `${scenario.id}: classifier did not detect the external blocker`);
    if (scenario.reason) assert.equal(verdict.reasonCode, scenario.reason, `${scenario.id}: expected reason ${scenario.reason} but got ${verdict.reasonCode}`);
  }
});

test("the live moderation pipeline classifies and acts on the real verdict", { timeout: 120000 }, async () => {
  for (const scenario of SCENARIOS) {
    await runScenario(scenario);
  }
});

async function runScenario(scenario: Scenario): Promise<void> {
  const home = await mkdtemp(join(tmpdir(), "agentci-pipeline-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  const store = new Harness(scenario.id, [user("user_1", scenario.user), assistant("msg_1", "user_1", scenario.assistant)], scenario.todos ?? []);
  const adapter = createModerationAdapter({ client: store.client }, options);
  try {
    adapter.event({ event: { type: "session.status", properties: { sessionID: scenario.id, status: { type: "busy" } } } });
    adapter.event({ event: { type: "session.status", properties: { sessionID: scenario.id, status: { type: "idle" } } } });
    await store.waitFor(() => store.verdicts.length > 0, `${scenario.id}: classifier verdict was never recorded`);
    const verdict = store.verdicts.at(-1) as Verdict;
    assert.ok(isVerdictDecision(verdict.decision), `${scenario.id}: recorded an invalid decision ${verdict.decision}`);

    if (scenario.expectation === "BLOCKED") {
      await store.waitFor(() => store.toasts.includes("agent-blocked"), `${scenario.id}: agent-blocked response did not surface an agent-blocked toast`);
      assert.equal(verdict.decision, "AGENT_BLOCKED", `${scenario.id}: recorded verdict was not AGENT_BLOCKED`);
      assert.equal(store.promptAsyncCalls.length, 0, `${scenario.id}: agent-blocked response must not prompt a continuation`);
    } else if (scenario.expectation === "CONTINUE") {
      assert.notEqual(verdict.decision, "AGENT_COMPLETE", `${scenario.id}: incomplete response was recorded as AGENT_COMPLETE`);
      await store.waitFor(() => store.promptAsyncCalls.length > 0, `${scenario.id}: continuation prompt was not sent`);
      assert.match(store.promptAsyncCalls[0].text, /Automated Moderation: work appears unfinished/, `${scenario.id}: continuation prompt marker missing`);
      adapter.event({ event: { type: "session.status", properties: { sessionID: scenario.id, status: { type: "busy" } } } });
      await store.waitFor(() => store.types.includes("continuation-verified") || store.types.includes("moderation-error"), `${scenario.id}: continuation verification did not settle`);
      assert.equal(store.types.includes("moderation-error"), false, `${scenario.id}: continuation verification reported an error`);
    } else if (scenario.expectation === "STOP") {
      assert.equal(verdict.decision, "AGENT_STOPPED", `${scenario.id}: recorded verdict was not AGENT_STOPPED`);
      await store.waitFor(() => store.toasts.includes("user-stop"), `${scenario.id}: user-stop response did not surface a user-stop toast`);
      assert.equal(store.promptAsyncCalls.length, 0, `${scenario.id}: a user stop must not prompt a continuation`);
    } else if (verdict.decision === "AGENT_COMPLETE") {
      await store.waitFor(() => store.toasts.includes("complete"), `${scenario.id}: complete verdict did not surface a complete toast`);
      assert.equal(store.promptAsyncCalls.length, 0, `${scenario.id}: passing response must not prompt a continuation`);
    } else {
      await store.waitFor(() => store.promptAsyncCalls.length > 0, `${scenario.id}: non-pass verdict did not prompt a continuation`);
    }
  } finally {
    adapter.event({ event: { type: "session.status", properties: { sessionID: scenario.id, status: { type: "busy" } } } });
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
}

class Harness {
  readonly messages: MessageFact[];
  readonly todos: readonly TodoFact[];
  readonly promptAsyncCalls: { text: string }[] = [];
  readonly toasts: string[] = [];
  readonly client: ModerationClient;
  verdicts: Verdict[] = [];
  types: string[] = [];
  private readonly sessionID: string;

  constructor(sessionID: string, messages: MessageFact[], todos: readonly TodoFact[] = []) {
    this.sessionID = sessionID;
    this.messages = messages;
    this.todos = todos;
    this.client = {
      session: {
        todo: async () => ({ data: [...this.todos] }),
        messages: async () => ({ data: this.messages }),
        prompt: async (call) => {
          const id = `trace_${this.messages.length}`;
          this.messages.push({ info: { id, role: "user", time: { created: Date.now() } }, parts: [{ type: "text", text: String((call.body.parts as { text: string }[])[0].text) }] });
          return { data: { info: { id } } };
        },
        promptAsync: async (call) => {
          const text = String((call.body.parts as { text: string }[])[0].text);
          this.promptAsyncCalls.push({ text });
          const id = `cont_${this.promptAsyncCalls.length}`;
          this.messages.push({ info: { id, role: "user", time: { created: Date.now() } }, parts: [{ type: "text", text }] });
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
    for (let attempt = 0; attempt < 200; attempt += 1) {
      this.verdicts = await readVerdicts(sessionDirectory(this.sessionID));
      this.types = await readDecisionTypes(sessionDirectory(this.sessionID));
      if (condition()) return;
      await new Promise((resolve) => { setTimeout(resolve, 50); });
    }
    throw new Error(message);
  }
}

async function readVerdicts(directory: string): Promise<Verdict[]> {
  let names: string[];
  try {
    names = await readdir(directory);
  } catch (error) {
    if ((error as { code?: string }).code === "ENOENT") return [];
    throw error;
  }
  const verdicts: Verdict[] = [];
  for (const name of names.filter((entry) => entry.startsWith("decision-") && entry.endsWith(".yaml"))) {
    const parsed = JSON.parse(await readFile(join(directory, name), "utf8")) as Record<string, unknown>;
    const candidate = parsed.verdict;
    if (candidate && typeof candidate === "object") verdicts.push(candidate as Verdict);
  }
  return verdicts;
}

function isVerdictDecision(value: string): value is VerdictDecision {
  return value === "AGENT_COMPLETE" || value === "AGENT_CONTINUING" || value === "AGENT_STALLED" || value === "AGENT_BLOCKED" || value === "AGENT_STOPPED";
}

async function readDecisionTypes(directory: string): Promise<string[]> {
  let names: string[];
  try {
    names = await readdir(directory);
  } catch (error) {
    if ((error as { code?: string }).code === "ENOENT") return [];
    throw error;
  }
  const types: string[] = [];
  for (const name of names.filter((entry) => entry.startsWith("decision-") && entry.endsWith(".yaml"))) {
    const parsed = JSON.parse(await readFile(join(directory, name), "utf8")) as Record<string, unknown>;
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

function user(id: string, content: string): MessageFact {
  return { info: { id, role: "user", time: { created: 1 } }, parts: [{ type: "text", text: content }] };
}

function assistant(id: string, parentID: string, content: string): MessageFact {
  return { info: { id, parentID, role: "assistant", finish: "stop", time: { created: 2 } }, parts: [{ type: "text", text: content }] };
}