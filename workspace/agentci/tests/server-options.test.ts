import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import plugin from "../src/server.ts";
import type { ReplayClient } from "../src/moderation/replay.ts";

const moderation = { gateway_url: "http://127.0.0.1:9080/llamafile", model: "/zip/MiniCPM5-1B-Q8_0.gguf" };

const client: ReplayClient = {
  session: {
    todo: async () => ({ data: [] }),
    messages: async () => ({ data: [] }),
    list: async () => ({ data: [] }),
    prompt: async () => ({ data: { info: { id: "trace" } } }),
    promptAsync: async () => undefined,
    revert: async () => undefined,
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

test("AGENTCI_RUN_MOD requests a replay alongside the moderation hooks", async () => {
  const previousMod = process.env.AGENTCI_MODERATION;
  const previousRun = process.env.AGENTCI_RUN_MOD;
  const previousState = process.env.XDG_STATE_HOME;
  const home = await mkdtemp(join(tmpdir(), "agentci-server-runmod-"));
  delete process.env.AGENTCI_MODERATION;
  process.env.AGENTCI_RUN_MOD = "1";
  process.env.XDG_STATE_HOME = home;
  try {
    const hooks = await plugin.server({ client }, { moderation });
    assert.equal(typeof hooks.event, "function");
  } finally {
    restoreEnv("AGENTCI_MODERATION", previousMod);
    restoreEnv("AGENTCI_RUN_MOD", previousRun);
    restoreEnv("XDG_STATE_HOME", previousState);
    await rm(home, { recursive: true, force: true });
  }
});

function restoreEnv(name: string, value: string | undefined): void {
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
}