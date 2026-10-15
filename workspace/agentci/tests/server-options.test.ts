import assert from "node:assert/strict";
import test from "node:test";
import plugin from "../src/server.ts";
import type { ModerationClient } from "../src/moderation/adapter.ts";

const moderation = { gateway_url: "http://127.0.0.1:9080/llamafile", model: "/zip/MiniCPM5-1B-Q8_0.gguf" };

const client: ModerationClient = {
  session: {
    todo: async () => ({ data: [] }),
    messages: async () => ({ data: [] }),
    prompt: async () => ({ data: { info: { id: "trace" } } }),
    promptAsync: async () => undefined,
  },
  tui: { showToast: async () => null },
};

test("AGENTCI_MODERATION=off returns empty hooks and skips moderation", async () => {
  const previous = process.env.AGENTCI_MODERATION;
  process.env.AGENTCI_MODERATION = "off";
  try {
    const hooks = await plugin.server({ client }, { moderation });
    assert.deepEqual(hooks, {});
  } finally {
    if (previous === undefined) delete process.env.AGENTCI_MODERATION;
    else process.env.AGENTCI_MODERATION = previous;
  }
});

test("moderation options enable the lifecycle event hook", async () => {
  const previous = process.env.AGENTCI_MODERATION;
  delete process.env.AGENTCI_MODERATION;
  try {
    const hooks = await plugin.server({ client }, { moderation });
    assert.equal(typeof hooks.event, "function");
  } finally {
    if (previous !== undefined) process.env.AGENTCI_MODERATION = previous;
  }
});