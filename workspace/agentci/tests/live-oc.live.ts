import assert from "node:assert/strict";
import { execFile, spawn } from "node:child_process";
import { closeSync, openSync } from "node:fs";
import { access, chmod, copyFile, mkdir, mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { homedir, tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

const run = promisify(execFile);
const workspaceRoot = dirname(dirname(dirname(dirname(fileURLToPath(import.meta.url)))));
const agentciRoot = join(workspaceRoot, "workspace", "agentci");
const installer = join(workspaceRoot, "workspace", "scripts", "install-agentci");
const oc = join(workspaceRoot, ".boot-linux", "bin", "opencode");
const localModel = "workspace-gw-llamafile-no-auth//zip/MiniCPM5-1B-Q8_0.gguf";
const liveModel = process.env.AGENTCI_LIVE_MODEL ?? localModel;
const livePrompt = "Reply with the single word ready. Do not use any tools.";

test("real OpenCode discovers the installed AgentCI plugin and dispatches lifecycle events", { timeout: 180000 }, async (context) => {
  const root = await mkdtemp(join(tmpdir(), "agentci-live-"));
  const config = join(root, "config");
  const data = join(root, "data");
  const state = join(root, "state");
  const home = join(root, "home");
  try {
    await prepareRoot({ root, config, data, state, home });
    await run(installer, ["install"], { env: { ...process.env, XDG_CONFIG_HOME: config, HOME: home } });
    await seedConfig(config);

    const outFile = join(root, "oc.out");
    await runWithCapture(oc, ["run", "--print-logs", "--log-level", "WARN", "--model", liveModel, livePrompt], {
      cwd: workspaceRoot,
      timeout: 120000,
      env: childEnvironment({ root, config, data, state, home }),
      outFile,
    });
    const output = await readFile(outFile, "utf8");
    context.diagnostic(`oc output: ${output.slice(0, 600)}`);

    const decisions = await moderationDecisionFiles(state);
    assert.ok(decisions.length > 0, "AgentCI moderation produced no decision record for the run");
    assert.ok(decisions.some((name) => name.endsWith(".yaml")), "AgentCI decision records are not YAML documents");
  } finally {
    await rm(root, { recursive: true, force: true });
  }
  await assert.rejects(access(root), { code: "ENOENT" });
});

interface RootPaths {
  root: string;
  config: string;
  data: string;
  state: string;
  home: string;
}

function childEnvironment(paths: RootPaths): NodeJS.ProcessEnv {
  const environment: NodeJS.ProcessEnv = {};
  for (const [key, value] of Object.entries(process.env)) {
    if (key === "OPENCODE" || key.startsWith("OPENCODE_")) continue;
    if (key === "HOME" || key.startsWith("XDG_")) continue;
    environment[key] = value;
  }
  environment.HOME = paths.home;
  environment.XDG_CONFIG_HOME = paths.config;
  environment.XDG_DATA_HOME = paths.data;
  environment.XDG_STATE_HOME = paths.state;
  environment.XDG_CACHE_HOME = join(paths.root, "cache");
  environment.OPENCODE_CONFIG_DIR = join(paths.config, "opencode");
  environment.OPENCODE_DB = join(paths.data, "opencode.db");
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

async function seedConfig(config: string): Promise<void> {
  const sourceRoot = process.env.XDG_CONFIG_HOME && process.env.XDG_CONFIG_HOME.length > 0
    ? process.env.XDG_CONFIG_HOME
    : join(process.env.HOME && process.env.HOME.length > 0 ? process.env.HOME : homedir(), ".config");
  const source = join(sourceRoot, "opencode", "opencode.jsonc");
  let parsed: Record<string, unknown> = {};
  try {
    parsed = JSON.parse(await readFile(source, "utf8")) as Record<string, unknown>;
  } catch (error) {
    if ((error as { code?: string }).code !== "ENOENT") throw error;
  }
  parsed.small_model = localModel;
  const destination = join(config, "opencode", "opencode.jsonc");
  await writeFile(destination, `${JSON.stringify(parsed, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
}

async function moderationDecisionFiles(state: string): Promise<string[]> {
  const moderationRoot = join(state, "opencode", "agentci", "moderation");
  const sessions = await readdir(moderationRoot, { withFileTypes: true });
  const names: string[] = [];
  for (const session of sessions) {
    if (!session.isDirectory()) continue;
    names.push(...await readdir(join(moderationRoot, session.name)));
  }
  return names;
}