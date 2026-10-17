import assert from "node:assert/strict";
import test from "node:test";
import {
  deriveContext,
  detectsRootBlock,
  inBranch,
  isInjectedUser,
  isTerminal,
  lastRealUserPrompts,
  newestAssistant,
  realUserAncestor,
  realUserCycleID,
} from "../src/moderation/context.ts";
import type { MessageFact } from "../src/moderation/types.ts";

test("deriveContext selects the assistant response and detects a fresh cycle", () => {
  const messages = [user("user_1", "Please finish."), assistant("msg_1", "user_1", "All done.")];
  const snapshot = deriveContext({ messages, assistantID: "msg_1", lastTerminalAssistantID: null, inflightAssistantID: null });
  assert.equal(snapshot.terminal, true);
  assert.equal(snapshot.assistantPresent, true);
  assert.equal(snapshot.duplicate, false);
  assert.equal(snapshot.assistantResponse, "All done.");
  assert.equal(snapshot.realUserCycleID, "user_1");
});

test("deriveContext marks a repeated assistant as duplicate", () => {
  const messages = [user("user_1", "hi"), assistant("msg_1", "user_1", "done")];
  const snapshot = deriveContext({ messages, assistantID: "msg_1", lastTerminalAssistantID: "msg_1", inflightAssistantID: null });
  assert.equal(snapshot.duplicate, true);
});

test("deriveContext treats a newer user message as a boundary", () => {
  const messages = [assistant("msg_1", null, "done"), user("user_2", "next thing")];
  const snapshot = deriveContext({ messages, assistantID: "msg_1", lastTerminalAssistantID: null, inflightAssistantID: null });
  assert.equal(snapshot.userNewer, true);
});

test("deriveContext detects plan mode and compaction messages", () => {
  const plan = assistant("msg_1", "user_1", "plan");
  plan.info.mode = "plan";
  assert.equal(deriveContext({ messages: [plan], assistantID: "msg_1", lastTerminalAssistantID: null, inflightAssistantID: null }).planMode, true);
  const summary = assistant("msg_2", "user_1", "summary");
  summary.info.summary = true;
  assert.equal(deriveContext({ messages: [summary], assistantID: "msg_2", lastTerminalAssistantID: null, inflightAssistantID: null }).compaction, true);
});

test("root block detection flags privileged fenced command blocks", () => {
  assert.equal(detectsRootBlock("Run:\n```bash\nsudo make init\n```\n"), true);
  assert.equal(detectsRootBlock("```sh\nif true; then sudo rm -rf /tmp/x; fi\n```"), true);
  assert.equal(detectsRootBlock("Use `sudo make init`.\n"), false);
  assert.equal(detectsRootBlock("```bash\nmake init\n```"), false);
  assert.equal(detectsRootBlock("Everything completed successfully."), false);
});

test("the last three real user prompts are selected for classifier context", () => {
  const messages = [
    user("u1", "first"),
    user("u2", "second"),
    user("u3", "third"),
    user("u4", "fourth"),
    user("injected", "⚠️ Automated Moderation: work appears unfinished; continue unless explicitly requested to halt by the operator or the system."),
  ];
  assert.deepEqual(lastRealUserPrompts(messages), ["second", "third", "fourth"]);
});

test("injected moderation messages are excluded from the real user cycle", () => {
  const injected = user("injected", "⚠️ Automated Moderation: work appears unfinished; continue unless explicitly requested to halt by the operator or the system.");
  assert.equal(isInjectedUser(injected), true);
  assert.equal(isInjectedUser(user("trace", "✅ Automated Moderation: work completion verified.")), true);
  assert.equal(isInjectedUser(user("blocked", "❔ Automated Moderation: awaiting user input.")), true);
  const messages = [user("user_1", "real"), injected];
  assert.equal(realUserCycleID(messages), "user_1");
});

test("newestAssistant selects the newest assistant regardless of terminality", () => {
  const messages = [user("u1", "hi"), assistant("a1", "u1", "first"), assistant("a2", "a1", "second")];
  assert.equal(newestAssistant(messages)?.info.id, "a2");
});

test("a trailing tool-calls step is the newest assistant and is not terminal", () => {
  const messages = [user("u1", "hi"), assistant("a1", "u1", "done"), assistant("a2", "a1", "running the tests")];
  messages[2].info.finish = "tool-calls";
  assert.equal(isTerminal(messages[2]), false);
  assert.equal(newestAssistant(messages)?.info.id, "a2");
});

test("a lone tool-calls response is the newest assistant but is not terminal", () => {
  const messages = [user("u1", "hi"), assistant("a1", "u1", "running the tests")];
  messages[1].info.finish = "tool-calls";
  assert.equal(newestAssistant(messages)?.info.id, "a1");
  assert.equal(isTerminal(messages[1]), false);
});

test("realUserAncestor walks past injected continuation messages", () => {
  const continuation = user("c1", "⚠️ Automated Moderation: work appears unfinished; continue unless explicitly requested to halt by the operator or the system.");
  continuation.info.parentID = "a1";
  const messages = [user("u1", "task"), assistant("a1", "u1", "partial"), continuation, assistant("a2", "c1", "done")];
  assert.equal(newestAssistant(messages)?.info.id, "a2");
  assert.equal(realUserAncestor(messages.at(-1), messages)?.info.id, "u1");
});

test("branch membership follows parent links to the blocker origin", () => {
  const origin = user("user_1", "needs sudo");
  const reply = assistant("msg_1", "user_1", "awaiting operator");
  const followUp = user("user_2", "what now");
  followUp.info.parentID = "msg_1";
  const unrelated = user("user_9", "different task");
  const messages = [origin, reply, followUp, unrelated];
  assert.equal(inBranch(followUp, messages, "user_1"), true);
  assert.equal(inBranch(unrelated, messages, "user_1"), false);
  assert.equal(inBranch(followUp, messages, null), false);
});

function user(id: string, content: string): MessageFact {
  return { info: { id, role: "user", time: { created: 1 } }, parts: [{ type: "text", text: content }] };
}

function assistant(id: string, parentID: string | null, content: string): MessageFact {
  return { info: { id, parentID: parentID ?? undefined, role: "assistant", finish: "stop", time: { created: 2 } }, parts: [{ type: "text", text: content }] };
}