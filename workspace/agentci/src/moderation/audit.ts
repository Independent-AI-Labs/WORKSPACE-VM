import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { join } from "node:path";
import { randomBytes } from "node:crypto";
import type { ModerationState } from "./types.ts";

export const DECISION_PREFIX = "decision-";
export const STATE_FILE = "state.yaml";

export function stateRoot(): string {
  const base = process.env.XDG_STATE_HOME && process.env.XDG_STATE_HOME.length > 0
    ? process.env.XDG_STATE_HOME
    : join(process.env.HOME && process.env.HOME.length > 0 ? process.env.HOME : homedir(), ".local", "state");
  return join(base, "opencode", "agentci", "moderation");
}

export function sessionDirectory(sessionID: string): string {
  if (!/^[A-Za-z0-9._-]+$/.test(sessionID)) throw new Error(`AgentCI moderation received an invalid session id '${sessionID}'`);
  return join(stateRoot(), sessionID);
}

export async function writeDecisionRecord(directory: string, record: Record<string, unknown>): Promise<string> {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const decisionID = `${Date.now()}-${randomBytes(6).toString("hex")}`;
  const path = join(directory, `${DECISION_PREFIX}${decisionID}.yaml`);
  await atomicWrite(path, serialize({ decisionID, ...record }));
  return path;
}

export async function persistSnapshot(directory: string, state: ModerationState): Promise<string> {
  await mkdir(directory, { recursive: true, mode: 0o700 });
  const path = join(directory, STATE_FILE);
  await atomicWrite(path, serialize({ state }));
  return path;
}

export async function restoreSnapshot(directory: string): Promise<ModerationState | null> {
  const document = await readDocument(join(directory, STATE_FILE));
  const state = document?.state;
  if (state === undefined || state === null) return null;
  return state as ModerationState;
}

async function readDocument(path: string): Promise<Record<string, unknown> | null> {
  try {
    const raw = await readFile(path, "utf8");
    const parsed = JSON.parse(raw) as unknown;
    return typeof parsed === "object" && parsed !== null && !Array.isArray(parsed) ? parsed as Record<string, unknown> : null;
  } catch (error) {
    if ((error as { code?: string }).code === "ENOENT") return null;
    throw error;
  }
}

function serialize(value: Record<string, unknown>): string {
  return `${JSON.stringify(value, null, 2)}\n`;
}

async function atomicWrite(path: string, content: string): Promise<void> {
  const temporary = `${path}.tmp-${process.pid}-${randomBytes(6).toString("hex")}`;
  await writeFile(temporary, content, { encoding: "utf8", mode: 0o600 });
  await rename(temporary, path);
}