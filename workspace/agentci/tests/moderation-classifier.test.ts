import assert from "node:assert/strict";
import test from "node:test";
import { buildMessages, classify, parseVerdict, SYSTEM_PROMPT, type FetchLike } from "../src/moderation/classifier.ts";
import { BOOLEAN_GRAMMAR, MAX_INPUT_TOKENS, MODERATION_GRAMMAR, resolveModerationOptions } from "../src/moderation/config.ts";

const options = { gatewayURL: "http://127.0.0.1:9080/llamafile", model: "/zip/MiniCPM5-1B-Q8_0.gguf" };
const input = { todos: [], previousResponse: "Done.", userMessages: ["Do the thing."] };

test("resolveModerationOptions accepts the Gateway relay only", () => {
  assert.deepEqual(resolveModerationOptions({ gateway_url: options.gatewayURL, model: options.model }), options);
  assert.throws(() => resolveModerationOptions({ gateway_url: "http://127.0.0.1:8765/v1", model: options.model }), /Workspace Gateway relay/);
  assert.throws(() => resolveModerationOptions({ gateway_url: options.gatewayURL }), /model/);
});

test("parseVerdict accepts the grammar output and rejects anything else", () => {
  assert.equal(parseVerdict("decision: AGENT_COMPLETE\nreason: WORK_COMPLETE")?.decision, "AGENT_COMPLETE");
  assert.equal(parseVerdict("decision: AGENT_BLOCKED\nreason: AWAITING_OPERATOR")?.reasonCode, "AWAITING_OPERATOR");
  assert.equal(parseVerdict("decision: AGENT_STOPPED\nreason: USER_STOP")?.decision, "AGENT_STOPPED");
  assert.equal(parseVerdict("decision: AGENT_COMPLETE\nreason: WORK_REMAINS"), undefined);
  assert.equal(parseVerdict("decision: AGENT_STOPPED\nreason: WORK_REMAINS"), undefined);
  assert.equal(parseVerdict("decision: MAYBE\nreason: WORK_COMPLETE"), undefined);
  assert.equal(parseVerdict("decision: AGENT_COMPLETE"), undefined);
});

test("buildMessages replaces empty user messages with the continue sentinel", () => {
  const messages = buildMessages({ todos: [], previousResponse: "Working.", userMessages: ["", "   ", "real request"] });
  assert.match(messages[1].content, /- Continue the unfinished work\./);
  assert.match(messages[1].content, /- real request/);
});

test("buildMessages omits the todos section when there are no tracked todos", () => {
  const messages = buildMessages({ todos: [], previousResponse: "Done.", userMessages: ["first", "stop now"] });
  const content = messages[1].content;
  assert.match(content, /User request\(s\):/);
  assert.match(content, /- stop now/);
  assert.doesNotMatch(content, /Tracked todos:/);
  const withTodos = buildMessages({ todos: [{ status: "pending", content: "writer" }], previousResponse: "Done.", userMessages: ["go"] });
  assert.match(withTodos[1].content, /Tracked todos:/);
});

test("the system prompt prioritizes handoffs and has no trailing continue bias", () => {
  assert.match(SYSTEM_PROMPT, /The agent's latest response is the decision target\./);
  assert.match(SYSTEM_PROMPT, /Step 1 always beats step 2\. A request to act and report a result is AWAITING_OPERATOR, not AWAITING_USER\./);
  assert.match(SYSTEM_PROMPT, /Listing remaining work, proposing a plan, or promising future work without asking the user to act is not a handoff\./);
  assert.match(SYSTEM_PROMPT, /An empty or whitespace-only user message is an interruption artifact, not a halt\./);
  assert.match(SYSTEM_PROMPT, /Reproduce the flare now/);
  assert.doesNotMatch(SYSTEM_PROMPT, /continue the work/i);
});

test("buildMessages places the assistant response before the user requests and todos", () => {
  const content = buildMessages({ todos: [{ status: "pending", content: "writer" }], previousResponse: "Working.", userMessages: ["go"] })[1].content;
  const responseIndex = content.indexOf("The agent's latest response (judge this):");
  const requestIndex = content.indexOf("User request(s):");
  const todoIndex = content.indexOf("Tracked todos:");
  assert.ok(responseIndex >= 0, "expected the assistant response section");
  assert.ok(responseIndex < requestIndex, "assistant response must precede the user requests");
  assert.ok(requestIndex < todoIndex, "user requests must precede the todos");
  assert.match(content, /Judge the agent's latest response\. It is the decision target/);
});

test("classify returns an inline capture of the exact request", async () => {
  const result = await classify(options, input, router({
    tokens: 100,
    completion: { finish: "stop", content: "decision: AGENT_COMPLETE\nreason: WORK_COMPLETE" },
  }));
  assert.equal(result.capture.model, options.model);
  assert.equal(result.capture.messages[0].role, "system");
  assert.match(result.capture.messages[1].content, /judge this/);
  assert.equal(result.capture.sampling.seed, 0);
  assert.equal(result.capture.sampling.temperature, 0);
  assert.equal(result.capture.attempts, 1);
  assert.equal(result.capture.completion, "decision: AGENT_COMPLETE\nreason: WORK_COMPLETE");
  assert.equal(result.capture.finishReason, "stop");
  assert.ok(result.capture.durationMs >= 0);
});

test("classify returns a verdict on a valid completion", async () => {
  const result = await classify(options, input, router({
    tokens: 100,
    completion: { finish: "stop", content: "decision: AGENT_COMPLETE\nreason: WORK_COMPLETE" },
  }));
  assert.equal(result.formatError, false);
  assert.equal(result.verdict?.decision, "AGENT_COMPLETE");
});

test("classify retries malformed output before returning a verdict", async () => {
  let calls = 0;
  const result = await classify(options, input, router(async () => {
    calls += 1;
    if (calls === 1) return completion("stop", "garbage");
    return completion("stop", "decision: AGENT_CONTINUING\nreason: WORK_REMAINS");
  }, 100));
  assert.equal(result.verdict?.decision, "AGENT_CONTINUING");
  assert.equal(calls, 2);
});

test("classify overrides a continuing verdict when the response asks the user to act", async () => {
  const result = await classify(options, input, router({
    tokens: 100,
    completion: { finish: "stop", content: "decision: AGENT_CONTINUING\nreason: WORK_REMAINS" },
  }, 100, "YES"));
  assert.equal(result.verdict?.decision, "AGENT_BLOCKED");
  assert.equal(result.verdict?.reasonCode, "AWAITING_OPERATOR");
  assert.equal(result.capture.attempts, 3);
});

test("classify keeps the verdict when the response asks the user to do nothing", async () => {
  const result = await classify(options, input, router({
    tokens: 100,
    completion: { finish: "stop", content: "decision: AGENT_CONTINUING\nreason: WORK_REMAINS" },
  }));
  assert.equal(result.verdict?.decision, "AGENT_CONTINUING");
  assert.equal(result.capture.attempts, 1);
});

test("classify fails after exhausting format retries", async () => {
  const result = await classify(options, input, router({ tokens: 100, completion: { finish: "stop", content: "nope" } }));
  assert.equal(result.formatError, true);
  assert.equal(result.verdict, undefined);
});

test("classify rejects a completion that did not stop", async () => {
  const result = await classify(options, input, router({ tokens: 100, completion: { finish: "length", content: "decision: AGENT_COMPLETE\nreason: WORK_COMPLETE" } }));
  assert.equal(result.formatError, true);
});

test("classify trims the prompt to the fixed token budget", async () => {
  const calls: number[] = [];
  const result = await classify(options, input, async (url, init) => {
    if (url.endsWith("/input_tokens")) {
      const body = JSON.parse(String(init?.body)) as { messages: { content: string }[] };
      const truncated = body.messages.some((message) => message.content.includes("[truncated by AgentCI classifier]"));
      const tokens = truncated ? 100 : MAX_INPUT_TOKENS + 1;
      calls.push(tokens);
      return new Response(JSON.stringify({ input_tokens: tokens }), { status: 200 });
    }
    if (booleanRequest(init)) return completion("stop", "NO");
    return completion("stop", "decision: AGENT_COMPLETE\nreason: WORK_COMPLETE");
  });
  assert.equal(result.verdict?.decision, "AGENT_COMPLETE");
  assert.ok(calls.length > 1, "expected at least one truncation round");
  assert.ok(calls.at(-1)! <= MAX_INPUT_TOKENS);
});

test("grammar encodes the accepted decision and reason pairs", () => {
  assert.match(MODERATION_GRAMMAR, /AGENT_STALLED\\nreason: NO_PROGRESS/);
  assert.match(MODERATION_GRAMMAR, /AGENT_BLOCKED\\nreason: AWAITING_USER/);
  assert.match(MODERATION_GRAMMAR, /AGENT_STOPPED\\nreason: USER_STOP/);
});

function completion(finish: string, content: string): Response {
  return new Response(JSON.stringify({ choices: [{ finish_reason: finish, message: { content } }] }), { status: 200 });
}

function booleanRequest(init?: RequestInit): boolean {
  if (typeof init?.body !== "string") return false;
  const body = JSON.parse(init.body) as { grammar?: string };
  return body.grammar === BOOLEAN_GRAMMAR;
}

function router(spec: number | { tokens: number; completion: { finish: string; content: string } } | (() => Promise<Response>), forcedTokens?: number, booleanAnswer = "NO"): FetchLike {
  return async (url, init) => {
    if (url.endsWith("/input_tokens")) {
      const tokens = forcedTokens ?? (typeof spec === "object" && spec !== null && "tokens" in spec ? spec.tokens : 100);
      return new Response(JSON.stringify({ input_tokens: tokens }), { status: 200 });
    }
    if (booleanRequest(init)) return completion("stop", booleanAnswer);
    if (typeof spec === "function") return spec();
    if (typeof spec === "number") throw new Error("numeric spec requires a completion function");
    return completion(spec.completion.finish, spec.completion.content);
  };
}