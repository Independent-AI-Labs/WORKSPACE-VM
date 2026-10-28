import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { continuationPersisted, loadMessages, statusLine, type ModerationClient } from "../src/moderation/adapter.ts";
import { isInjectedUser, isSyntheticUser, lastRealUserPrompts, realUserCycleID } from "../src/moderation/context.ts";
import type { MessageFact } from "../src/moderation/types.ts";

const workspaceRoot = dirname(dirname(dirname(dirname(fileURLToPath(import.meta.url)))));
const opencode = join(workspaceRoot, ".boot-linux", "bin", "opencode");
const continuation = statusLine("AGENT_CONTINUING", "WORK_REMAINS");
const realPrompt = "the mouse look is broken";

interface Harness {
  baseURL: string;
  child: ReturnType<typeof spawn>;
}

test("a moderation continuation round-trips through a real OpenCode server", { timeout: 180000 }, async () => {
  const root = await mkdtemp(join(tmpdir(), "agentci-persistence-"));
  const config = join(root, "config");
  const server = await startServer(root, config);
  try {
    const sessionID = await createSession(server.baseURL);
    const client = httpClient(server.baseURL);
    const user = await sendMessage(server.baseURL, sessionID, realPrompt, false);
    const nudge = await sendMessage(server.baseURL, sessionID, continuation, true);

    const messages = await loadMessages(client, sessionID);
    const storedNudge = messages.find((message) => message.info.id === nudge.messageID);
    const storedUser = messages.find((message) => message.info.id === user.messageID);
    assert.ok(storedNudge !== undefined, "the continuation message was not persisted");
    assert.ok(storedUser !== undefined, "the real user message was not persisted");

    const part = storedNudge.parts[0];
    assert.equal(part.type, "text");
    assert.equal(part.text, continuation);
    assert.equal(part.synthetic, true, "the server dropped the synthetic marker");
    assert.deepEqual(part.metadata, { moderation: true }, "the server dropped the moderation metadata");

    assert.equal(isInjectedUser(storedNudge), true, "metadata detection missed the persisted continuation");
    assert.equal(isSyntheticUser(storedNudge), true);
    assert.equal(isInjectedUser(storedUser), false, "a real user message was treated as injected");
    assert.deepEqual(lastRealUserPrompts(messages), [realPrompt], "the continuation leaked into real user prompts");
    assert.equal(realUserCycleID(messages), user.messageID, "the continuation replaced the real user cycle");
    assert.equal(await continuationPersisted(client, sessionID), true, "continuation verification missed the persisted part");

    await revert(server.baseURL, sessionID, nudge.messageID);
    assert.equal(await revertMessageID(server.baseURL, sessionID), nudge.messageID, "replay could not revert the continuation");
    const afterRevert = await loadMessages(client, sessionID);
    assert.equal(afterRevert.some((message) => message.info.id === user.messageID), true, "revert removed the real user message");

    const asyncSession = await createSession(server.baseURL);
    await sendAsync(server.baseURL, asyncSession, continuation);
    const persisted = await waitForMessage(client, asyncSession, continuation);
    assert.equal(persisted.parts[0].synthetic, true, "the async path dropped the synthetic marker");
    assert.deepEqual(persisted.parts[0].metadata, { moderation: true }, "the async path dropped the moderation metadata");
    assert.equal(isInjectedUser(persisted), true, "metadata detection missed the async continuation");
    await abort(server.baseURL, asyncSession);
  } finally {
    await stopServer(server.child);
    await rm(root, { recursive: true, force: true });
  }
});

async function startServer(root: string, config: string): Promise<Harness> {
  const data = join(root, "data");
  const state = join(root, "state");
  const home = join(root, "home");
  const cache = join(root, "cache");
  await mkdir(join(config, "opencode"), { recursive: true, mode: 0o700 });
  await mkdir(data, { recursive: true, mode: 0o700 });
  await mkdir(state, { recursive: true, mode: 0o700 });
  await mkdir(home, { recursive: true, mode: 0o700 });
  await mkdir(cache, { recursive: true, mode: 0o700 });
  const model = {
    $schema: "https://opencode.ai/config.json",
    model: "offline/static",
    provider: {
      offline: {
        npm: "@ai-sdk/openai-compatible",
        name: "Offline upstream",
        options: { baseURL: "http://127.0.0.1:9/v1", apiKey: "test" },
        models: { static: { name: "Static" } },
      },
    },
  };
  await writeFile(join(config, "opencode", "opencode.jsonc"), `${JSON.stringify(model, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  const environment: NodeJS.ProcessEnv = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (key === "OPENCODE" || key.startsWith("OPENCODE_")) continue;
    if (key === "HOME" || key.startsWith("XDG_")) continue;
    environment[key] = value;
  }
  environment.HOME = home;
  environment.XDG_CONFIG_HOME = config;
  environment.XDG_DATA_HOME = data;
  environment.XDG_STATE_HOME = state;
  environment.XDG_CACHE_HOME = cache;
  environment.OPENCODE_CONFIG_DIR = join(config, "opencode");
  const port = await freePort();
  const child = spawn(opencode, ["serve", "--pure", "--port", String(port)], { cwd: workspaceRoot, env: environment, stdio: ["ignore", "pipe", "pipe"] });
  let output = "";
  child.stdout?.setEncoding("utf8");
  child.stderr?.setEncoding("utf8");
  child.stdout?.on("data", (chunk: string) => { output += chunk; });
  child.stderr?.on("data", (chunk: string) => { output += chunk; });
  const baseURL = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 30000;
  let lastError = "";
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`OpenCode server exited before listening:\n${output}`);
    try {
      const response = await fetch(`${baseURL}/session`, { signal: AbortSignal.timeout(1000) });
      if (response.ok) return { baseURL, child };
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await sleep(200);
  }
  await stopServer(child);
  throw new Error(`OpenCode server did not become ready (last error: ${lastError}):\n${output}`);
}

async function freePort(): Promise<number> {
  const probe = createServer();
  await new Promise<void>((resolve) => { probe.listen(0, "127.0.0.1", resolve); });
  const address = probe.address();
  const port = typeof address === "object" && address !== null ? address.port : 0;
  await new Promise<void>((resolve, reject) => { probe.close((error) => (error ? reject(error) : resolve())); });
  if (port === 0) throw new Error("could not allocate a local port for the OpenCode server");
  return port;
}

async function stopServer(child: ReturnType<typeof spawn>): Promise<void> {
  if (child.exitCode !== null) return;
  child.kill("SIGTERM");
  await once(child, "exit");
}

function httpClient(baseURL: string): ModerationClient {
  return {
    session: {
      todo: async () => ({ data: [] }),
      messages: async (input) => {
        const url = new URL(`${baseURL}/session/${input.path.id}/message`);
        if (input.query !== undefined) {
          for (const [key, value] of Object.entries(input.query)) url.searchParams.set(key, String(value));
        }
        const response = await fetch(url, { signal: AbortSignal.timeout(10000) });
        if (!response.ok) throw new Error(`message read failed with HTTP ${response.status}`);
        return { data: await response.json() as MessageFact[] };
      },
      prompt: async () => ({ data: {} }),
      promptAsync: async () => ({}),
    },
    tui: { showToast: async () => ({}) },
  };
}

async function createSession(baseURL: string): Promise<string> {
  const response = await fetch(`${baseURL}/session`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title: "persistence" }),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`session create failed with HTTP ${response.status}`);
  const payload = await response.json() as { id?: string };
  if (payload.id === undefined) throw new Error("session create returned no id");
  return payload.id;
}

async function sendMessage(baseURL: string, sessionID: string, text: string, moderation: boolean): Promise<{ messageID: string }> {
  const part = moderation ? { type: "text", text, synthetic: true, metadata: { moderation: true } } : { type: "text", text };
  const response = await fetch(`${baseURL}/session/${sessionID}/message`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ noReply: true, parts: [part] }),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`message send failed with HTTP ${response.status}`);
  const payload = await response.json() as { info?: { id?: string } };
  const messageID = payload.info?.id;
  if (messageID === undefined) throw new Error("message send returned no id");
  return { messageID };
}

async function sendAsync(baseURL: string, sessionID: string, text: string): Promise<void> {
  const response = await fetch(`${baseURL}/session/${sessionID}/prompt_async`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ parts: [{ type: "text", text, synthetic: true, metadata: { moderation: true } }] }),
    signal: AbortSignal.timeout(10000),
  });
  if (response.status !== 204) throw new Error(`async send failed with HTTP ${response.status}`);
}

async function waitForMessage(client: ModerationClient, sessionID: string, text: string): Promise<MessageFact> {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    const messages = await loadMessages(client, sessionID);
    const found = messages.find((message) => message.parts.some((part) => part.text === text));
    if (found !== undefined) return found;
    await sleep(200);
  }
  throw new Error("the async continuation was not persisted");
}

async function abort(baseURL: string, sessionID: string): Promise<void> {
  const response = await fetch(`${baseURL}/session/${sessionID}/abort`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`abort failed with HTTP ${response.status}`);
}

async function revertMessageID(baseURL: string, sessionID: string): Promise<string | null> {
  const response = await fetch(`${baseURL}/session/${sessionID}`, { signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error(`session read failed with HTTP ${response.status}`);
  const payload = await response.json() as { revert?: { messageID?: string } };
  return payload.revert?.messageID ?? null;
}

async function revert(baseURL: string, sessionID: string, messageID: string): Promise<void> {
  const response = await fetch(`${baseURL}/session/${sessionID}/revert`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ messageID }),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) throw new Error(`revert failed with HTTP ${response.status}: ${await response.text()}`);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => { setTimeout(resolve, ms); });
}
