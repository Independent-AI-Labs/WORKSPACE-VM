import { readFile } from "node:fs/promises";

export const GATEWAY_RELAY_URL = "http://127.0.0.1:9080/llamafile";
export const MINICPM_MODEL_ID = "/zip/MiniCPM5-1B-Q8_0.gguf";
export const MAX_INPUT_TOKENS = 16384;
export const MAX_COMPLETION_TOKENS = 128;
export const CLASSIFIER_FORMAT_RETRIES = 3;
export const CLASSIFIER_SEED = 0;
export const CLASSIFIER_TIMEOUT_MS = 30000;

export const MODERATION_GRAMMAR =
  'root ::= "decision: AGENT_COMPLETE\\nreason: WORK_COMPLETE" | "decision: AGENT_CONTINUING\\nreason: WORK_REMAINS" | "decision: AGENT_STALLED\\nreason: NO_PROGRESS" | "decision: AGENT_BLOCKED\\nreason: AWAITING_USER" | "decision: AGENT_BLOCKED\\nreason: AWAITING_OPERATOR" | "decision: AGENT_STOPPED\\nreason: USER_STOP"';

export interface ModerationOptions {
  gatewayURL: string;
  model: string;
}

export function resolveModerationOptions(raw: unknown): ModerationOptions {
  if (typeof raw !== "object" || raw === null || Array.isArray(raw)) {
    throw new Error("AgentCI moderation options are not a mapping");
  }
  const record = raw as Record<string, unknown>;
  const gatewayURL = record.gateway_url;
  const model = record.model;
  if (typeof gatewayURL !== "string" || gatewayURL.length === 0) {
    throw new Error("AgentCI moderation options require a non-empty 'gateway_url'");
  }
  if (gatewayURL !== GATEWAY_RELAY_URL) {
    throw new Error(`AgentCI moderation gateway must be the Workspace Gateway relay ${GATEWAY_RELAY_URL} (got '${gatewayURL}')`);
  }
  if (typeof model !== "string" || model.length === 0) {
    throw new Error("AgentCI moderation options require a non-empty 'model'");
  }
  return { gatewayURL, model };
}

export async function loadModerationOptions(path: string): Promise<ModerationOptions> {
  const raw = await readFile(path, "utf8");
  return resolveModerationOptions(JSON.parse(raw));
}