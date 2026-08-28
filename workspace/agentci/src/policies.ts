import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { parse } from "yaml";

export type PolicyEvent = "tool.execute.before" | "tool.execute.after" | "experimental.chat.system.transform";
export type PolicyAction = "block" | "allow" | "warn" | "inject";

const EVENTS: readonly PolicyEvent[] = ["tool.execute.before", "tool.execute.after", "experimental.chat.system.transform"];
const BEFORE_ACTIONS: readonly PolicyAction[] = ["block", "allow", "warn"];
const AFTER_ACTIONS: readonly PolicyAction[] = ["warn"];
const INJECT_ACTIONS: readonly PolicyAction[] = ["inject"];
const MATCH_FIELDS = ["tool", "command_regex", "exit", "repository_path", "session_id", "file"] as const;

export const MAX_REGEX_LENGTH = 256;
export const MAX_MESSAGE_BYTES = 4096;
export const MAX_FILE_BYTES = 16384;

export interface Policy {
  name: string;
  event: PolicyEvent;
  match: {
    tool?: string;
    commandRegex?: RegExp;
    exit?: "zero" | "nonzero";
    repositoryPath?: string;
    sessionID?: string;
    file?: string;
  };
  action: PolicyAction;
  message: string;
}

export async function loadPolicies(files: readonly string[]): Promise<Policy[]> {
  const policies: Policy[] = [];
  for (const file of files) {
    const raw = await readFile(file, "utf8");
    const document = parse(raw);
    if (typeof document !== "object" || document === null || Array.isArray(document)) {
      throw new Error(`AgentCI policy file is not a mapping: ${file}`);
    }
    const list = (document as { policies?: unknown }).policies;
    if (!Array.isArray(list)) throw new Error(`AgentCI policy file has no policies array: ${file}`);
    for (const entry of list) policies.push(policy(entry, file));
  }
  const names = new Set(policies.map((item) => item.name));
  if (names.size !== policies.length) throw new Error("AgentCI policy names must be unique across configured files");
  return policies;
}

function policy(value: unknown, file: string): Policy {
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error(`AgentCI policy is not a mapping in ${file}`);
  const record = value as Record<string, unknown>;
  for (const key of Object.keys(record)) {
    if (key !== "name" && key !== "event" && key !== "match" && key !== "action" && key !== "message") {
      throw new Error(`AgentCI policy has unknown field '${key}' in ${file}`);
    }
  }
  const name = stringField(record.name, "name", file);
  const event = EVENTS.find((candidate) => candidate === record.event);
  if (event === undefined) throw new Error(`AgentCI policy '${name}' has unknown event in ${file}`);
  const action = actionField(record.action, event, name, file);
  const message = bounded(stringField(record.message, "message", file), MAX_MESSAGE_BYTES, `message of policy '${name}'`);
  return { name, event, match: matchFields(record.match, action, name, file), action, message };
}

function matchFields(value: unknown, action: PolicyAction, name: string, file: string): Policy["match"] {
  if (value === undefined) return {};
  if (typeof value !== "object" || value === null || Array.isArray(value)) throw new Error(`AgentCI policy '${name}' match is not a mapping in ${file}`);
  const record = value as Record<string, unknown>;
  const match: Policy["match"] = {};
  for (const key of Object.keys(record)) {
    if (!(MATCH_FIELDS as readonly string[]).includes(key)) throw new Error(`AgentCI policy '${name}' has unknown match field '${key}' in ${file}`);
    if (key === "command_regex") {
      const pattern = stringField(record.command_regex, `${name} command_regex`, file);
      if (pattern.length > MAX_REGEX_LENGTH) throw new Error(`AgentCI policy '${name}' command_regex exceeds ${MAX_REGEX_LENGTH} characters`);
      try {
        match.commandRegex = new RegExp(pattern);
      } catch {
        throw new Error(`AgentCI policy '${name}' command_regex is invalid in ${file}`);
      }
    } else if (key === "exit") {
      const exit = record.exit;
      if (exit !== "zero" && exit !== "nonzero") throw new Error(`AgentCI policy '${name}' exit must be 'zero' or 'nonzero' in ${file}`);
      match.exit = exit;
    } else if (key === "file") {
      if (action !== "inject") throw new Error(`AgentCI policy '${name}' file match requires action 'inject' in ${file}`);
      match.file = resolve(dirname(file), stringField(record.file, `${name} file`, file));
    } else if (key === "tool") {
      match.tool = stringField(record.tool, `${name} tool`, file);
    } else if (key === "repository_path") {
      match.repositoryPath = stringField(record.repository_path, `${name} repository_path`, file);
    } else if (key === "session_id") {
      match.sessionID = stringField(record.session_id, `${name} session_id`, file);
    }
  }
  if (action === "inject" && match.file === undefined) throw new Error(`AgentCI policy '${name}' action 'inject' requires match field 'file' in ${file}`);
  return match;
}

function actionField(value: unknown, event: PolicyEvent, name: string, file: string): PolicyAction {
  const allowed = event === "tool.execute.before" ? BEFORE_ACTIONS : event === "tool.execute.after" ? AFTER_ACTIONS : INJECT_ACTIONS;
  const action = allowed.find((candidate) => candidate === value);
  if (action === undefined) {
    throw new Error(`AgentCI policy '${name}' action '${String(value)}' is not valid for ${event} in ${file} (allowed: ${allowed.join(", ")})`);
  }
  return action;
}

function stringField(value: unknown, field: string, file: string): string {
  if (typeof value !== "string" || value.length === 0) throw new Error(`AgentCI policy field '${field}' must be a non-empty string in ${file}`);
  return value;
}

function bounded(value: string, limit: number, label: string): string {
  if (Buffer.byteLength(value, "utf8") > limit) throw new Error(`AgentCI ${label} exceeds ${limit} bytes`);
  return value;
}

export function matches(policy: Policy, tool: string | undefined, command: string | undefined, exit: number | undefined, input: { sessionID?: string; repositoryPath?: string }): boolean {
  if (policy.match.tool !== undefined && policy.match.tool !== tool) return false;
  if (policy.match.commandRegex !== undefined && (command === undefined || !policy.match.commandRegex.test(command))) return false;
  if (policy.match.exit !== undefined) {
    if (exit === undefined) return false;
    if (policy.match.exit === "zero" && exit !== 0) return false;
    if (policy.match.exit === "nonzero" && exit === 0) return false;
  }
  if (policy.match.sessionID !== undefined && policy.match.sessionID !== input.sessionID) return false;
  if (policy.match.repositoryPath !== undefined && policy.match.repositoryPath !== input.repositoryPath) return false;
  return true;
}

export function bashCommand(args: unknown): string | undefined {
  if (typeof args !== "object" || args === null || Array.isArray(args)) return undefined;
  const value = (args as { command?: unknown }).command;
  return typeof value === "string" ? value : undefined;
}
