import { readFile } from "node:fs/promises";
import { bashCommand, matches, type Policy } from "./policies.ts";

export interface V1ToolExecuteAfterInput {
  tool: string;
  sessionID: string;
  callID: string;
  args: unknown;
}

export interface V1ToolExecuteAfterOutput {
  title: string;
  output: string;
  metadata: unknown;
}

export interface V1ToolExecuteBeforeInput {
  tool: string;
  sessionID: string;
  callID: string;
}

export interface V1ToolExecuteBeforeOutput {
  args: unknown;
}

export interface V1SystemTransformInput {
  sessionID?: string;
}

export interface V1SystemTransformOutput {
  system: string[];
}

export interface V1HookAdapter {
  "tool.execute.before": (input: V1ToolExecuteBeforeInput, output: V1ToolExecuteBeforeOutput) => Promise<void>;
  "tool.execute.after": (input: V1ToolExecuteAfterInput, output: V1ToolExecuteAfterOutput) => Promise<void>;
  "experimental.chat.system.transform": (input: V1SystemTransformInput, output: V1SystemTransformOutput) => Promise<void>;
}

export function createV1HookAdapter(policies: readonly Policy[]): V1HookAdapter {
  const before = policies.filter((policy) => policy.event === "tool.execute.before");
  const after = policies.filter((policy) => policy.event === "tool.execute.after");
  const inject = policies.filter((policy) => policy.event === "experimental.chat.system.transform");
  return {
    async "tool.execute.before"(input, output) {
      const command = bashCommand(output.args);
      for (const policy of before) {
        if (!matches(policy, input.tool, command, undefined, { sessionID: input.sessionID })) continue;
        if (policy.action === "block") throw new Error(`AgentCI policy '${policy.name}' blocked this tool: ${policy.message}`);
      }
    },
    async "tool.execute.after"(input, output) {
      const exit = exitCode(output.metadata);
      const command = bashCommand(input.args);
      for (const policy of after) {
        if (!matches(policy, input.tool, command, exit, { sessionID: input.sessionID })) continue;
        output.output += `\nAgentCI (${policy.name}): ${policy.message}`;
      }
    },
    async "experimental.chat.system.transform"(input, output) {
      for (const policy of inject) {
        if (policy.match.sessionID !== undefined && policy.match.sessionID !== input.sessionID) continue;
        const file = policy.match.file as string;
        const content = await readFile(file, "utf8");
        if (Buffer.byteLength(content, "utf8") > MAX_FILE_BYTES) {
          throw new Error(`AgentCI policy '${policy.name}' file exceeds ${MAX_FILE_BYTES} bytes: ${file}`);
        }
        output.system.push(`AgentCI (${policy.name}): ${content}`);
      }
    },
  };
}

const MAX_FILE_BYTES = 16384;

function exitCode(metadata: unknown): number | undefined {
  if (typeof metadata !== "object" || metadata === null || Array.isArray(metadata)) return undefined;
  const value = (metadata as { exit?: unknown }).exit;
  return typeof value === "number" && Number.isInteger(value) ? value : undefined;
}
