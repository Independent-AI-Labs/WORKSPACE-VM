import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { closeSync, openSync } from "node:fs";
import { createServer } from "node:http";
import { chmod, copyFile, mkdir, mkdtemp, readFile, rm, stat, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

const run = promisify(execFile);
const workspaceRoot = dirname(dirname(dirname(dirname(fileURLToPath(import.meta.url)))));
const installer = join(workspaceRoot, "workspace", "scripts", "install-agentci");
const oc = join(workspaceRoot, ".boot-linux", "bin", "opencode");
const policiesPath = join(workspaceRoot, "workspace", "config", "opencode", "agentci", "policies.yaml");
const notePath = join(workspaceRoot, "workspace", "config", "opencode", "agentci", "user-note.md");
const benchmarkDirectory = join(workspaceRoot, "workspace", "agentci", "benchmarks");
const marker = "AgentCI (user-note):";
const localModel = "workspace-gw-llamafile-no-auth//zip/MiniCPM5-1B-Q8_0.gguf";
const staticQuestion = "Explain how photosynthesis works in as much detail as you can.";

interface RootPaths {
  root: string;
  config: string;
  data: string;
  state: string;
  home: string;
}

interface Recorded {
  path: string;
  body: Record<string, unknown>;
}

interface MockModel {
  baseURL: string;
  requests: Recorded[];
  close: () => Promise<void>;
}

function startMockModel(): Promise<MockModel> {
  const requests: Recorded[] = [];
  const server = createServer((request, response) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk: Buffer) => chunks.push(chunk));
    request.on("end", () => {
      const raw = Buffer.concat(chunks).toString("utf8");
      const body = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
      if (request.method === "GET" && (request.url ?? "").startsWith("/v1/models")) {
        response.writeHead(200, { "content-type": "application/json" });
        response.end(JSON.stringify({ object: "list", data: [{ id: "static", object: "model", owned_by: "mock" }] }));
        return;
      }
      requests.push({ path: request.url ?? "", body });
      if (body.stream === true) {
        response.writeHead(200, { "content-type": "text/event-stream", "cache-control": "no-cache" });
        response.write(chunk({ role: "assistant" }));
        response.write(chunk({ content: "ok" }));
        response.write(
          `data: ${JSON.stringify({ id: "chatcmpl", object: "chat.completion.chunk", choices: [{ index: 0, delta: {}, finish_reason: "stop" }], usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 } })}\n\n`,
        );
        response.write("data: [DONE]\n\n");
        response.end();
        return;
      }
      response.writeHead(200, { "content-type": "application/json" });
      response.end(
        JSON.stringify({
          id: "chatcmpl",
          object: "chat.completion",
          choices: [{ index: 0, message: { role: "assistant", content: "ok" }, finish_reason: "stop" }],
          usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
        }),
      );
    });
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address !== null ? address.port : 0;
      resolve({
        baseURL: `http://127.0.0.1:${port}/v1`,
        requests,
        close: () => new Promise((done) => server.close(() => done())),
      });
    });
  });
}

function chunk(delta: Record<string, unknown>): string {
  return `data: ${JSON.stringify({ id: "chatcmpl", object: "chat.completion.chunk", choices: [{ index: 0, delta }] })}\n\n`;
}

function childEnvironment(paths: RootPaths): NodeJS.ProcessEnv {
  const environment: NodeJS.ProcessEnv = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (key === "OPENCODE" || key.startsWith("OPENCODE_")) continue;
    if (key === "HOME" || key.startsWith("XDG_")) continue;
    if (key === "AGENTCI_MODERATION") continue;
    environment[key] = value;
  }
  environment.HOME = paths.home;
  environment.XDG_CONFIG_HOME = paths.config;
  environment.XDG_DATA_HOME = paths.data;
  environment.XDG_STATE_HOME = paths.state;
  environment.XDG_CACHE_HOME = join(paths.root, "cache");
  environment.OPENCODE_CONFIG_DIR = join(paths.config, "opencode");
  environment.OPENCODE_DB = join(paths.data, "opencode.db");
  environment.AGENTCI_MODERATION = "off";
  return environment;
}

async function runWithCapture(file: string, args: string[], options: { cwd: string; timeout: number; env: NodeJS.ProcessEnv; outFile: string }): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    const descriptor = openSync(options.outFile, "w");
    const child = spawn(file, args, { cwd: options.cwd, env: options.env, stdio: ["ignore", descriptor, descriptor] });
    let settled = false;
    const timer = setTimeout(() => { child.kill("SIGTERM"); }, options.timeout);
    const finish = (error?: Error): void => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      closeSync(descriptor);
      if (error) reject(error);
      else resolve();
    };
    child.on("error", (error) => { finish(error); });
    child.on("close", () => { finish(); });
  });
}

async function prepareRoot(paths: RootPaths): Promise<void> {
  await mkdir(join(paths.config, "opencode"), { recursive: true, mode: 0o700 });
  await mkdir(join(paths.data, "opencode"), { recursive: true, mode: 0o700 });
  await mkdir(join(paths.state, "opencode"), { recursive: true, mode: 0o700 });
  await mkdir(paths.home, { recursive: true, mode: 0o700 });
  await copyAuth(paths.data);
}

async function copyAuth(data: string): Promise<void> {
  const sourceRoot = process.env.XDG_DATA_HOME && process.env.XDG_DATA_HOME.length > 0
    ? process.env.XDG_DATA_HOME
    : join(process.env.HOME && process.env.HOME.length > 0 ? process.env.HOME : homedir(), ".local", "share");
  const source = join(sourceRoot, "opencode", "auth.json");
  const destination = join(data, "opencode", "auth.json");
  await copyFile(source, destination);
  await chmod(destination, 0o600);
}

async function writeMockConfig(paths: RootPaths, baseURL: string): Promise<void> {
  const config = {
    $schema: "https://opencode.ai/config.json",
    model: "mock/static",
    small_model: "mock/static",
    provider: {
      mock: {
        npm: "@ai-sdk/openai-compatible",
        name: "Mock upstream",
        options: { baseURL, apiKey: "test" },
        models: { static: { name: "Static" } },
      },
    },
  };
  await writeFile(join(paths.config, "opencode", "opencode.jsonc"), `${JSON.stringify(config, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
}

async function seedRealConfig(paths: RootPaths): Promise<void> {
  const sourceRoot = process.env.XDG_CONFIG_HOME && process.env.XDG_CONFIG_HOME.length > 0
    ? process.env.XDG_CONFIG_HOME
    : join(process.env.HOME && process.env.HOME.length > 0 ? process.env.HOME : homedir(), ".config");
  const source = join(sourceRoot, "opencode", "opencode.jsonc");
  const raw = await readFile(source, "utf8");
  const parsed = JSON.parse(raw) as Record<string, unknown>;
  parsed.small_model = localModel;
  await writeFile(join(paths.config, "opencode", "opencode.jsonc"), `${JSON.stringify(parsed, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
}

async function installPlugin(paths: RootPaths, inject: boolean): Promise<void> {
  await run(installer, ["install"], { env: { ...process.env, XDG_CONFIG_HOME: paths.config, HOME: paths.home } });
  const release = await readFile(join(paths.config, "opencode", "plugins", ".agentci", "current"), "utf8").catch(() => "");
  const releaseDir = release.trim().length > 0
    ? release.startsWith("/") ? release.trim() : join(paths.config, "opencode", "plugins", ".agentci", release.trim())
    : "";
  const options = inject ? { policies: [policiesPath] } : {};
  const target = releaseDir.length > 0 ? releaseDir : join(paths.config, "opencode", "plugins", ".agentci", "current");
  await writeFile(join(target, "options.json"), `${JSON.stringify(options)}\n`, "utf8");
}

function userMessageTexts(body: Record<string, unknown>): string[] {
  const messages = body.messages;
  if (!Array.isArray(messages)) return [];
  const out: string[] = [];
  for (const message of messages) {
    if (!message || typeof message !== "object") continue;
    const record = message as { role?: unknown; content?: unknown };
    if (record.role !== "user") continue;
    if (typeof record.content === "string") {
      out.push(record.content);
      continue;
    }
    if (Array.isArray(record.content)) {
      out.push(record.content.map((part) => (part && typeof part === "object" && "text" in part && typeof (part as { text?: unknown }).text === "string" ? (part as { text: string }).text : "")).join("\n"));
    }
  }
  return out;
}

async function countPersisted(env: NodeJS.ProcessEnv, needle: string): Promise<number> {
  const database = env.OPENCODE_DB;
  if (database === undefined || database.length === 0) throw new Error("OPENCODE_DB was not configured for the isolated environment");
  const candidates = [database, `${database}-wal`, `${database}-shm`, `${database}-journal`];
  let total = 0;
  for (const candidate of candidates) {
    if (!(await fileExists(candidate))) continue;
    const bytes = await readFile(candidate);
    total += countOccurrences(bytes.toString("latin1"), needle);
  }
  return total;
}

async function fileExists(path: string): Promise<boolean> {
  try {
    await stat(path);
    return true;
  } catch (error) {
    if (error instanceof Error && (error as NodeJS.ErrnoException).code === "ENOENT") return false;
    throw error;
  }
}

function countOccurrences(haystack: string, needle: string): number {
  if (needle.length === 0) return 0;
  let count = 0;
  let index = haystack.indexOf(needle);
  while (index !== -1) {
    count += 1;
    index = haystack.indexOf(needle, index + needle.length);
  }
  return count;
}

interface ScenarioResult {
  inject: boolean;
  requests: Recorded[];
  persistedMarker: number;
  persistedQuestion: number;
}

async function runMockScenario(inject: boolean): Promise<ScenarioResult> {
  const root = await mkdtemp(join(tmpdir(), "agentci-inject-"));
  const paths: RootPaths = { root, config: join(root, "config"), data: join(root, "data"), state: join(root, "state"), home: join(root, "home") };
  const mock = await startMockModel();
  try {
    await prepareRoot(paths);
    await writeMockConfig(paths, mock.baseURL);
    await installPlugin(paths, inject);
    const outFile = join(root, "oc.out");
    await runWithCapture(oc, ["run", "--print-logs", "--log-level", "WARN", "--model", "mock/static", staticQuestion], {
      cwd: workspaceRoot,
      timeout: 60000,
      env: childEnvironment(paths),
      outFile,
    });
    const env = childEnvironment(paths);
    const persistedMarker = await countPersisted(env, `AgentCI (user-note):`);
    const persistedQuestion = await countPersisted(env, `photosynthesis`);
    return { inject, requests: mock.requests, persistedMarker, persistedQuestion };
  } finally {
    await mock.close();
    await rm(root, { recursive: true, force: true });
  }
}

test("AgentCI injects the note upstream on every user message without persisting it", { timeout: 300000 }, async (context) => {
  const note = (await readFile(notePath, "utf8")).trim();
  const off = await runMockScenario(false);
  const on = await runMockScenario(true);

  const offBodies = off.requests.map((entry) => JSON.stringify(entry.body)).join("\n");
  assert.equal(offBodies.includes(marker), false, "note was injected while the policy was disabled");

  const injectedRequests = on.requests.filter((entry) => JSON.stringify(entry.body).includes(marker));
  assert.ok(injectedRequests.length > 0, "note was never injected upstream while the policy was enabled");
  for (const entry of injectedRequests) {
    const userTexts = userMessageTexts(entry.body);
    assert.ok(userTexts.length > 0, "recorded upstream request had no user messages");
    for (const text of userTexts) {
      assert.equal(text.split(marker).length - 1, 1, "note was not injected exactly once per user message");
      assert.ok(text.includes(note), "injected upstream text did not carry the configured note");
    }
  }

  assert.ok(on.persistedQuestion > 0, "sanity: the user prompt is absent from the persisted transcript");
  assert.equal(on.persistedMarker, 0, "injected note leaked into the persisted transcript");
  assert.equal(off.persistedMarker, 0, "note persisted even though the policy was disabled");
  context.diagnostic(`mock upstream requests: off=${off.requests.length} on=${on.requests.length} injected=${injectedRequests.length}`);
});

test("benchmark: note changes the model response to a static question", { timeout: 600000 }, async (context) => {
  const samples = Number(process.env.AGENTCI_BENCH_SAMPLES ?? "3");
  const model = process.env.AGENTCI_LIVE_MODEL ?? localModel;
  const note = (await readFile(notePath, "utf8")).trim();
  const results: BenchmarkResult[] = [];
  for (const inject of [false, true]) {
    const words: number[] = [];
    const sentences: number[] = [];
    const chars: number[] = [];
    const wordsPerSentence: number[] = [];
    for (let sample = 0; sample < samples; sample++) {
      const root = await mkdtemp(join(tmpdir(), "agentci-bench-"));
      const paths: RootPaths = { root, config: join(root, "config"), data: join(root, "data"), state: join(root, "state"), home: join(root, "home") };
      try {
        await prepareRoot(paths);
        await seedRealConfig(paths);
        await installPlugin(paths, inject);
        const outFile = join(root, "oc.out");
        await runWithCapture(oc, ["run", "--print-logs", "--log-level", "WARN", "--model", model, staticQuestion], {
          cwd: workspaceRoot,
          timeout: 180000,
          env: childEnvironment(paths),
          outFile,
        });
        const response = responseText(await readFile(outFile, "utf8"));
        const wordCount = countWords(response);
        const sentenceCount = countSentences(response);
        context.diagnostic(`${inject ? "on" : "off"} sample ${sample + 1}: ${JSON.stringify(response.slice(0, 240))}`);
        words.push(wordCount);
        sentences.push(sentenceCount);
        chars.push(response.length);
        wordsPerSentence.push(sentenceCount > 0 ? wordCount / sentenceCount : 0);
      } finally {
        await rm(root, { recursive: true, force: true });
      }
    }
    results.push({ inject, words, sentences, chars, wordsPerSentence });
  }
  for (const result of results) {
    context.diagnostic(
      `${result.inject ? "note-on " : "note-off"}: words=${average(result.words).toFixed(1)} sentences=${average(result.sentences).toFixed(1)} words/sentence=${average(result.wordsPerSentence).toFixed(1)} chars=${average(result.chars).toFixed(1)}`,
    );
  }
  await mkdir(benchmarkDirectory, { recursive: true });
  const reportPath = join(benchmarkDirectory, `note-injection-${slug(model)}.md`);
  await writeFile(reportPath, benchmarkReport({ model, note, samples, results }), "utf8");
  context.diagnostic(`wrote ${reportPath}`);
});

interface BenchmarkResult {
  inject: boolean;
  words: number[];
  sentences: number[];
  chars: number[];
  wordsPerSentence: number[];
}

function benchmarkReport(input: { model: string; note: string; samples: number; results: BenchmarkResult[] }): string {
  const lines: string[] = [
    "# AgentCI note-injection benchmark",
    "",
    `- model: \`${input.model}\``,
    `- question: ${staticQuestion}`,
    `- note: ${input.note}`,
    `- samples: ${input.samples}`,
    `- generatedAt: ${new Date().toISOString()}`,
    "",
    "## Summary",
    "",
    "| mode | words | sentences | words/sentence | chars |",
    "|---|---|---|---|---|",
  ];
  for (const result of input.results) {
    lines.push(
      `| ${result.inject ? "note-on" : "note-off"} | ${average(result.words).toFixed(1)} | ${average(result.sentences).toFixed(1)} | ${average(result.wordsPerSentence).toFixed(1)} | ${average(result.chars).toFixed(1)} |`,
    );
  }
  lines.push("", "## Samples", "", "| mode | sample | words | sentences | words/sentence | chars |", "|---|---|---|---|---|---|");
  for (const result of input.results) {
    result.words.forEach((wordCount, index) => {
      lines.push(
        `| ${result.inject ? "note-on" : "note-off"} | ${index + 1} | ${wordCount} | ${result.sentences[index]} | ${result.wordsPerSentence[index].toFixed(1)} | ${result.chars[index]} |`,
      );
    });
  }
  return `${lines.join("\n").trimEnd()}\n`;
}

function slug(value: string): string {
  return value.replace(/[^a-zA-Z0-9]+/g, "-").replace(/^-+|-+$/g, "").toLowerCase();
}

function average(values: number[]): number {
  if (values.length === 0) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function countWords(value: string): number {
  return value.trim().split(/\s+/).filter((word) => word.length > 0).length;
}

function countSentences(value: string): number {
  return value.split(/[.!?]+/).map((part) => part.trim()).filter((part) => part.length > 0).length;
}

function stripAnsi(value: string): string {
  return value.replace(/\u001b\[[0-9;]*m/g, "");
}

function responseText(value: string): string {
  return stripAnsi(value)
    .split("\n")
    .filter((line) => !line.trim().startsWith(">"))
    .join("\n")
    .trim();
}