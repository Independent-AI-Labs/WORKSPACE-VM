import { appendFile, mkdir, open, readFile, rename } from "node:fs/promises";
import { join } from "node:path";
import { randomBytes } from "node:crypto";
import type { ModerationState } from "./types.ts";

export const STATE_FILE = "state.json";
export const DECISIONS_FILE = "decisions.jsonl";
export const SCHEMA_VERSION = 1;

export function stateRoot(env: NodeJS.ProcessEnv = process.env): string {
  const xdg = env.XDG_STATE_HOME;
  if (xdg !== undefined && xdg.length > 0) return join(xdg, "moderator", "sessions");
  const home = env.HOME;
  if (home !== undefined && home.length > 0) return join(home, ".local", "state", "moderator", "sessions");
  throw new Error("moderator requires XDG_STATE_HOME or HOME");
}

export function isValidSessionID(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9_][A-Za-z0-9._-]*$/.test(value) && value !== "..";
}

export function sessionDirectory(sessionID: string, env: NodeJS.ProcessEnv = process.env): string {
  if (!isValidSessionID(sessionID)) throw new Error(`moderator received an invalid session id '${sessionID}'`);
  return join(stateRoot(env), sessionID);
}

export async function persistState(directory: string, state: ModerationState): Promise<void> {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  await atomicWrite(join(directory, STATE_FILE), `${JSON.stringify({ schemaVersion: SCHEMA_VERSION, state }, null, 2)}\n`);
}

export async function restoreState(directory: string): Promise<unknown | null> {
  let raw: string;
  try {
    raw = await readFile(join(directory, STATE_FILE), "utf8");
  } catch (error) {
    if ((error as { code?: string }).code === "ENOENT") return null;
    throw error;
  }
  const parsed = JSON.parse(raw) as unknown;
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("moderator state snapshot must be an object");
  }
  const record = parsed as Record<string, unknown>;
  if (record.schemaVersion !== SCHEMA_VERSION) {
    throw new Error(`moderator state snapshot has unsupported schema version '${String(record.schemaVersion)}'`);
  }
  return record.state ?? null;
}

export async function appendDecision(directory: string, record: Record<string, unknown>): Promise<void> {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  await appendFile(join(directory, DECISIONS_FILE), `${JSON.stringify(record)}\n`, { mode: 0o600 });
}

export function auditRecord(input: {
  sessionID: string;
  assistantID: string | null;
  event: string;
  decision: string;
  reason: string | null;
  previousPhase: string;
  nextPhase: string;
  ignored: boolean;
  verdict: unknown;
  capture: unknown;
  error: string | null;
  effects: unknown;
  effectResults: unknown;
  previousState: ModerationState;
  stateSnapshot: ModerationState;
}): Record<string, unknown> {
  return {
    timestamp: new Date().toISOString(),
    schemaVersion: SCHEMA_VERSION,
    ...input,
    nextState: input.stateSnapshot,
  };
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
