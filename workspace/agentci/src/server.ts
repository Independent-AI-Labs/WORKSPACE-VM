import { appendFile, readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createV1HookAdapter, validatePolicyFiles } from "./v1-hook-adapter.ts";
import { loadPolicies } from "./policies.ts";
import { applyThinkingEffort } from "./thinking.ts";

interface AgentCIOptions {
  policies?: string[];
}

const moduleDirectory = dirname(fileURLToPath(import.meta.url));

export default {
  id: "agentci",
  server: async (input: unknown, options: AgentCIOptions = {}) => {
    const fileOptions = await readOptionsFile();
    const policies = await resolvePolicies(options, fileOptions);
    const requestedEffort = process.env.OC_THINKING_EFFORT;
    const hooks: Record<string, unknown> = {
      "chat.params": (hookInput: Parameters<typeof applyThinkingEffort>[0], output: Parameters<typeof applyThinkingEffort>[1]) => {
        applyThinkingEffort(hookInput, output, requestedEffort);
      },
    };
    if (policies === null || policies.length === 0) {
      throw new Error("AgentCI requires a non-empty 'policies' array");
    }
    const loaded = await loadPolicies(policies);
    await validatePolicyFiles(loaded);
    const v1 = createV1HookAdapter(loaded);
    const evidence = process.env.AGENTCI_EVIDENCE_FILE;
    hooks["tool.execute.before"] = v1["tool.execute.before"];
    hooks["tool.execute.after"] = evidence === undefined
      ? v1["tool.execute.after"]
      : withEvidence(v1["tool.execute.after"], evidence);
    hooks["experimental.chat.system.transform"] = evidence === undefined
      ? v1["experimental.chat.system.transform"]
      : withEvidence(v1["experimental.chat.system.transform"], evidence);
    hooks["experimental.chat.messages.transform"] = evidence === undefined
      ? v1["experimental.chat.messages.transform"]
      : withEvidence(v1["experimental.chat.messages.transform"], evidence);
    void input;
    return hooks;
  },
};

async function readOptionsFile(): Promise<Record<string, unknown> | null> {
  try {
    const raw = await readFile(join(moduleDirectory, "options.json"), "utf8");
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      throw new Error("AgentCI options.json is not a mapping");
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    if ((error as { code?: string }).code === "ENOENT") return null;
    throw error;
  }
}

async function resolvePolicies(options: AgentCIOptions, fileOptions: Record<string, unknown> | null): Promise<string[] | null> {
  if (options.policies !== undefined) return parsePolicies(options.policies);
  if (fileOptions === null) return null;
  return parsePolicies(fileOptions.policies);
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

function withEvidence<A extends unknown[], R>(hook: (...args: A) => Promise<R>, file: string): (...args: A) => Promise<R> {
  return async (...args: A): Promise<R> => {
    const result = await hook(...args);
    await appendFile(file, `${JSON.stringify({ args })}\n`);
    return result;
  };
}
