import { createV1HookAdapter, type V1ToolExecuteAfterInput, type V1ToolExecuteAfterOutput, type V1SystemTransformInput, type V1SystemTransformOutput } from "./v1-hook-adapter.ts";
import { loadPolicies } from "./policies.ts";
import { appendFile } from "node:fs/promises";

interface AgentCIOptions {
  policies?: string[];
}

export default {
  id: "agentci",
  server: async (_input: unknown, options: AgentCIOptions = {}) => {
    if (!Array.isArray(options.policies) || options.policies.length === 0) {
      throw new Error("AgentCI requires an explicit 'policies' array of policy file paths in plugin options");
    }
    const policies = await loadPolicies(options.policies);
    const hooks = createV1HookAdapter(policies);
    const evidence = process.env.AGENTCI_EVIDENCE_FILE;
    const toolAfter = evidence === undefined ? hooks["tool.execute.after"] : async (input: V1ToolExecuteAfterInput, output: V1ToolExecuteAfterOutput) => {
      await hooks["tool.execute.after"](input, output);
      await appendFile(evidence, `${JSON.stringify({ input, output })}\n`);
    };
    const system = evidence === undefined ? hooks["experimental.chat.system.transform"] : async (input: V1SystemTransformInput, output: V1SystemTransformOutput) => {
      await hooks["experimental.chat.system.transform"](input, output);
      await appendFile(evidence, `${JSON.stringify({ input, output })}\n`);
    };
    return {
      "tool.execute.before": hooks["tool.execute.before"],
      "tool.execute.after": toolAfter,
      "experimental.chat.system.transform": system,
    };
  },
}
