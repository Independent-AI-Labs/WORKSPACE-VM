import test from "node:test";
import assert from "node:assert/strict";
import { buildCaseState, collectToolActivity, detectsRootBlock, inBranch, newestModeratedAssistant, realUserAncestor } from "../src/context.ts";
import type { MessageFact } from "../src/types.ts";

function user(id: string, text: string, parentID?: string): MessageFact {
  return { info: { id, role: "user", parentID, time: { created: 1 } }, parts: [{ type: "text", text }] };
}

function assistant(id: string, text: string, parentID: string, extra: Partial<MessageFact["info"]> = {}): MessageFact {
  return { info: { id, role: "assistant", parentID, finish: "stop", time: { created: 2 }, ...extra }, parts: [{ type: "text", text }] };
}

test("builds sections in order with mode message last", () => {
  const text = buildCaseState({ todos: [], previousResponse: "done", userMessages: ["do it"], toolActivity: [], agentMode: "answer" });
  assert.ok(text.indexOf("The agent's latest response") < text.indexOf("User request(s):"));
  assert.ok(text.endsWith("The agent is answering a user question."));
});

test("tool output is truncated and older turns are excluded", () => {
  process.env.MODERATOR_TOOL_OUTPUT_CHARS = "8";
  const messages: MessageFact[] = [
    user("u0", "old task"),
    assistant("a0", "old reply", "u0"),
    user("u1", "new task", "a0"),
    user("u2", "also this", "u1"),
    {
      info: { id: "a1", role: "assistant", parentID: "u2", finish: "stop", time: { created: 2 } },
      parts: [
        { type: "text", text: "judged" },
        { type: "tool", tool: "bash", state: { status: "completed", input: { command: "ls" }, output: "0123456789abcdef" } },
      ],
    },
  ];
  const activity = collectToolActivity(messages[4], messages);
  assert.equal(activity.length, 1);
  assert.match(activity[0] ?? "", /\[truncated\]/);
  assert.equal(activity[0]?.includes("old"), false);
  delete process.env.MODERATOR_TOOL_OUTPUT_CHARS;
});

test("newest assistant includes plan and compaction", () => {
  const messages = [
    user("u1", "work"),
    assistant("a1", "plan", "u1", { mode: "plan" }),
    assistant("a2", "summary", "u1", { summary: true }),
  ];
  assert.equal(newestModeratedAssistant(messages)?.info.id, "a2");
});

test("root block requires sudo inside a fence", () => {
  assert.equal(detectsRootBlock("Prose sudo mention"), false);
  assert.equal(detectsRootBlock("```bash\nsudo systemctl restart x\n```"), true);
});

test("branch walk resolves real user", () => {
  const messages = [user("u1", "work"), assistant("a1", "done", "u1")];
  assert.equal(realUserAncestor(messages[1], messages)?.info.id, "u1");
  assert.equal(inBranch(messages[0], messages, "u1"), true);
});

test("parent cycle fails closed", () => {
  const messages = [
    { info: { id: "a1", role: "assistant" as const, parentID: "a2" }, parts: [{ type: "text", text: "one" }] },
    { info: { id: "a2", role: "assistant" as const, parentID: "a1" }, parts: [{ type: "text", text: "two" }] },
  ];
  assert.throws(() => realUserAncestor(messages[0], messages), /parent cycle/);
});

test("injected moderator line is not the real user", () => {
  const messages = [
    user("u1", "work"),
    assistant("a1", "done", "u1"),
    { info: { id: "note", role: "user" as const, parentID: "a1" }, parts: [{ type: "text", text: "⚠️ Automated Moderation: old" }] },
    assistant("a2", "next", "note"),
  ];
  assert.equal(realUserAncestor(messages[3], messages)?.info.id, "u1");
});
