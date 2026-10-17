import assert from "node:assert/strict";
import test from "node:test";
import { buildMessages, classify, parseVerdict, type FetchLike } from "../src/moderation/classifier.ts";
import { MAX_INPUT_TOKENS, MODERATION_GRAMMAR, resolveModerationOptions } from "../src/moderation/config.ts";

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

test("buildMessages omits the todos section when there are no tracked todos", () => {
  const messages = buildMessages({ todos: [], previousResponse: "Done.", userMessages: ["first", "stop now"] });
  const content = messages[1].content;
  assert.match(content, /User request\(s\):/);
  assert.match(content, /- stop now/);
  assert.doesNotMatch(content, /Tracked todos:/);
  const withTodos = buildMessages({ todos: [{ status: "pending", content: "writer" }], previousResponse: "Done.", userMessages: ["go"] });
  assert.match(withTodos[1].content, /Tracked todos:/);
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

function router(spec: number | { tokens: number; completion: { finish: string; content: string } } | (() => Promise<Response>), forcedTokens?: number): FetchLike {
  return async (url, init) => {
    if (url.endsWith("/input_tokens")) {
      const tokens = forcedTokens ?? (typeof spec === "object" && spec !== null && "tokens" in spec ? spec.tokens : 100);
      return new Response(JSON.stringify({ input_tokens: tokens }), { status: 200 });
    }
    if (typeof spec === "function") return spec();
    if (typeof spec === "number") throw new Error("numeric spec requires a completion function");
    return completion(spec.completion.finish, spec.completion.content);
  };
}