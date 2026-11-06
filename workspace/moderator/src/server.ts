import { tool } from "@opencode-ai/plugin/tool";
import { createModeratorAdapter, type ModeratorClient } from "./adapter.ts";
import { readModels } from "./model-select.ts";
import { VERDICT_TOOL } from "./classifier.ts";

export interface ModeratorInput {
  client: ModeratorClient;
}

const verdictTool = tool({
  description: "Return the moderator verdict for the latest assistant response.",
  args: {
    decision: tool.schema.enum(["AGENT_COMPLETE", "AGENT_CONTINUING", "AGENT_STALLED", "AGENT_BLOCKED", "AGENT_STOPPED"]),
    reason: tool.schema.enum(["WORK_COMPLETE", "WORK_REMAINS", "NO_PROGRESS", "AWAITING_USER", "AWAITING_OPERATOR", "USER_STOP"]),
  },
  async execute(args) {
    return { title: "Moderator verdict", output: JSON.stringify(args) };
  },
});

export default {
  id: "moderator-server",
  server: async (input: ModeratorInput) => {
    try {
      const models = await readModels();
      const adapter = createModeratorAdapter(input, models);
      const replayID = process.env.AGENTCI_RUN_MOD === "1" ? process.env.AGENTCI_RUN_MOD_SESSION : undefined;
      if (replayID !== undefined && replayID.length > 0) {
        adapter.replay(replayID, process.env.AGENTCI_RUN_MOD_FORCE === "1").catch((error: unknown) => {
          throw error instanceof Error ? error : new Error(String(error));
        });
      }
      return {
        tool: { [VERDICT_TOOL]: verdictTool },
        event: (incoming: { event?: { type: string; properties?: { sessionID?: string; status?: { type?: string } } }; type?: string; properties?: { sessionID?: string; status?: { type?: string } } }) => {
          const event = incoming.event ?? incoming;
          if (event.type === undefined) return;
          adapter.event({ type: event.type, properties: event.properties });
        },
        "experimental.session.compacting": adapter["experimental.session.compacting"],
        "experimental.compaction.autocontinue": adapter["experimental.compaction.autocontinue"],
      };
    } catch (error) {
      throw error instanceof Error ? error : new Error(String(error));
    }
  },
};
