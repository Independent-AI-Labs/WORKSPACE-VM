import { mkdir, open, readFile, rename } from "node:fs/promises";
import { dirname, join } from "node:path";
import { randomBytes } from "node:crypto";

export interface ModelSelector {
  providerID: string;
  modelID: string;
}

export function configRoot(env: NodeJS.ProcessEnv = process.env): string {
  const xdg = env.XDG_CONFIG_HOME;
  if (xdg !== undefined && xdg.length > 0) return join(xdg, "opencode");
  const home = env.HOME;
  if (home !== undefined && home.length > 0) return join(home, ".config", "opencode");
  throw new Error("moderator requires XDG_CONFIG_HOME or HOME");
}

export function modelsPath(env: NodeJS.ProcessEnv = process.env): string {
  return join(configRoot(env), "moderator", "models.json");
}

export function parseModels(raw: unknown): ModelSelector[] {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    throw new Error("moderator models.json must be an object");
  }
  const models = (raw as { models?: unknown }).models;
  if (!Array.isArray(models) || models.length === 0) {
    throw new Error("moderator models.json requires a non-empty models array");
  }
  const result: ModelSelector[] = [];
  const seen = new Set<string>();
  for (const entry of models) {
    if (typeof entry !== "object" || entry === null || Array.isArray(entry)) {
      throw new Error("moderator model entry must be an object");
    }
    const record = entry as Record<string, unknown>;
    const providerID = record.providerID;
    const modelID = record.modelID;
    if (typeof providerID !== "string" || providerID.length === 0) {
      throw new Error("moderator model entry requires a non-empty providerID");
    }
    if (typeof modelID !== "string" || modelID.length === 0) {
      throw new Error("moderator model entry requires a non-empty modelID");
    }
    const key = `${providerID}/${modelID}`;
    if (seen.has(key)) throw new Error(`moderator model entry is duplicated: ${key}`);
    seen.add(key);
    result.push({ providerID, modelID });
  }
  return result;
}

export async function readModels(path: string = modelsPath()): Promise<ModelSelector[]> {
  let raw: string;
  try {
    raw = await readFile(path, "utf8");
  } catch (error) {
    if ((error as { code?: string }).code === "ENOENT") {
      throw new Error(`moderator model source is missing: ${path}`);
    }
    throw error;
  }
  return parseModels(JSON.parse(raw) as unknown);
}

export async function writeModels(models: readonly ModelSelector[], path: string = modelsPath()): Promise<void> {
  if (models.length === 0) throw new Error("moderator model list must not be empty");
  const keys = new Set<string>();
  for (const model of models) {
    if (model.providerID.length === 0 || model.modelID.length === 0) {
      throw new Error("moderator model selector requires providerID and modelID");
    }
    const key = `${model.providerID}/${model.modelID}`;
    if (keys.has(key)) throw new Error(`moderator model selector is duplicated: ${key}`);
    keys.add(key);
  }
  await mkdir(dirname(path), { recursive: true, mode: 0o700 });
  await atomicWrite(path, `${JSON.stringify({ models }, null, 2)}\n`);
}

export async function replaceTopModel(selector: ModelSelector, path: string = modelsPath()): Promise<ModelSelector[]> {
  const models = await readModels(path);
  const next = [selector, ...models.slice(1)];
  await writeModels(next, path);
  return next;
}

export function parseSelectorList(value: string): ModelSelector[] {
  const parts = value.split(",").map((part) => part.trim());
  if (parts.length === 0 || parts.some((part) => part.length === 0)) {
    throw new Error("model list must contain provider/model selectors");
  }
  const models: ModelSelector[] = [];
  for (const part of parts) {
    const slash = part.indexOf("/");
    if (slash <= 0 || slash === part.length - 1 || part.indexOf("/", slash + 1) >= 0) {
      throw new Error(`model selector must be provider/model: ${part}`);
    }
    models.push({ providerID: part.slice(0, slash), modelID: part.slice(slash + 1) });
  }
  const keys = new Set(models.map((model) => `${model.providerID}/${model.modelID}`));
  if (keys.size !== models.length) throw new Error("model list contains a duplicate selector");
  return models;
}

async function atomicWrite(path: string, content: string): Promise<void> {
  const temporary = `${path}.tmp-${process.pid}-${randomBytes(6).toString("hex")}`;
  const handle = await open(temporary, "wx", 0o600);
  try {
    await handle.writeFile(content, "utf8");
    await handle.sync();
  } finally {
    await handle.close();
  }
  await rename(temporary, path);
}
