import assert from "node:assert/strict";
import test from "node:test";
import { continuationPersisted, type ModerationClient } from "../src/moderation/adapter.ts";
import type { MessageFact } from "../src/moderation/types.ts";

const continuation: MessageFact = {
  info: { id: "msg_cont", role: "user", time: { created: 1 } },
  parts: [{ type: "text", text: "⚠️ Automated Moderation: work appears unfinished; continue unless explicitly requested to halt by the operator or the system." }],
};

const ordinary: MessageFact = {
  info: { id: "msg_user", role: "user", time: { created: 1 } },
  parts: [{ type: "text", text: "please finish the task" }],
};

test("continuation persistence is verified by the marker, not a promptAsync id", async () => {
  assert.equal(await continuationPersisted(clientWith([ordinary, continuation]), "ses_verify"), true);
});

test("a session without the continuation marker is not verified", async () => {
  assert.equal(await continuationPersisted(clientWith([ordinary]), "ses_verify"), false);
});

function clientWith(messages: MessageFact[]): ModerationClient {
  return {
    session: {
      todo: async () => ({ data: [] }),
      messages: async () => ({ data: messages }),
      prompt: async () => ({ data: { info: { id: "trace" } } }),
      promptAsync: async () => undefined,
    },
    tui: { showToast: async () => null },
  };
}