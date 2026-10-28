import { appendFile, readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createV1HookAdapter, type V1MessagesTransformOutput, type V1SystemTransformInput, type V1SystemTransformOutput, type V1ToolExecuteAfterInput, type V1ToolExecuteAfterOutput } from "./v1-hook-adapter.ts";
import { loadPolicies } from "./policies.ts";
import { createModerationAdapter, type ModerationClient } from "./moderation/adapter.ts";
import { loadModerationOptions, resolveModerationOptions, type ModerationOptions } from "./moderation/config.ts";
import { runReplay, type ReplayClient } from "./moderation/replay.ts";

interface AgentCIOptions {
  policies?: string[];
  moderation?: unknown;
}

export interface AgentCIInput {
  client: ModerationClient;
}

const moduleDirectory = dirname(fileURLToPath(import.meta.url));

export default {
  id: "agentci",
  server: async (input: AgentCIInput, options: AgentCIOptions = {}) => {
    const policies = await resolvePolicies(options);
    const moderation = moderationDisabled() ? null : await resolveModeration(options);
    if (policies === null && moderation === null) {
      if (moderationDisabled()) return {};
      throw new Error("AgentCI requires either a non-empty 'policies' array or moderation options");
    }
    const hooks: Record<string, unknown> = {};
    if (policies !== null) {
      const loaded = await loadPolicies(policies);
      const v1 = createV1HookAdapter(loaded);
      const evidence = process.env.AGENTCI_EVIDENCE_FILE;
      hooks["tool.execute.before"] = v1["tool.execute.before"];
      hooks["tool.execute.after"] = evidence === undefined ? v1["tool.execute.after"] : async (toolInput: V1ToolExecuteAfterInput, output: V1ToolExecuteAfterOutput) => {
        await v1["tool.execute.after"](toolInput, output);
        await appendFile(evidence, `${JSON.stringify({ input: toolInput, output })}\n`);
      };
      hooks["experimental.chat.system.transform"] = evidence === undefined ? v1["experimental.chat.system.transform"] : async (transformInput: V1SystemTransformInput, transformOutput: V1SystemTransformOutput) => {
        await v1["experimental.chat.system.transform"](transformInput, transformOutput);
        await appendFile(evidence, `${JSON.stringify({ input: transformInput, output: transformOutput })}\n`);
      };
      hooks["experimental.chat.messages.transform"] = evidence === undefined ? v1["experimental.chat.messages.transform"] : async (transformInput: Record<string, never>, transformOutput: V1MessagesTransformOutput) => {
        await v1["experimental.chat.messages.transform"](transformInput, transformOutput);
        await appendFile(evidence, `${JSON.stringify({ input: transformInput, output: transformOutput })}\n`);
      };
    }
    if (moderation !== null) {
      const adapter = createModerationAdapter(input, moderation);
      hooks.event = adapter.event;
      hooks["experimental.session.compacting"] = adapter["experimental.session.compacting"];
      hooks["experimental.compaction.autocontinue"] = adapter["experimental.compaction.autocontinue"];
      if (runModRequested()) {
        void runReplay(input.client as unknown as ReplayClient, moderation, process.env.AGENTCI_RUN_MOD_SESSION);
      }
    }
    return hooks;
  },
};

function runModRequested(): boolean {
  const value = process.env.AGENTCI_RUN_MOD;
  if (value === undefined) return false;
  const normalized = value.trim().toLowerCase();
  return normalized === "1" || normalized === "true" || normalized === "on" || normalized === "yes";
}

function moderationDisabled(): boolean {
  const value = process.env.AGENTCI_MODERATION;
  if (value === undefined) return false;
  const normalized = value.trim().toLowerCase();
  return normalized === "off" || normalized === "0" || normalized === "false" || normalized === "none";
}

async function resolveModeration(options: AgentCIOptions): Promise<ModerationOptions | null> {
  if (options.moderation !== undefined) return resolveModerationOptions(options.moderation);
  try {
    return await loadModerationOptions(join(moduleDirectory, "options.json"));
  } catch (error) {
    if ((error as { code?: string }).code === "ENOENT") return null;
    throw error;
  }
}

async function resolvePolicies(options: AgentCIOptions): Promise<string[] | null> {
  if (options.policies !== undefined) return parsePolicies(options.policies);
  let raw: string;
  try {
    raw = await readFile(join(moduleDirectory, "options.json"), "utf8");
  } catch (error) {
    if ((error as { code?: string }).code === "ENOENT") return null;
    throw error;
  }
  return parsePolicies((JSON.parse(raw) as { policies?: unknown }).policies);
}

function parsePolicies(raw: unknown): string[] | null {
  if (raw === undefined) return null;
  if (!Array.isArray(raw) || raw.length === 0) {
    throw new Error("AgentCI 'policies' must be a non-empty array of string file paths");
  }
  for (const entry of raw) {
    if (typeof entry !== "string" || entry.length === 0) {
      throw new Error("AgentCI 'policies' entries must be string file paths");
    }
  }
  return raw as string[];
}
