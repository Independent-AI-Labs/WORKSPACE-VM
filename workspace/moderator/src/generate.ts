import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join } from "node:path";
import { readOpenCodeConfig } from "./config.ts";

export interface GenerateCall {
  providerID: string;
  modelID: string;
  system: string;
  prompt: string;
  toolName: string;
  sessionID: string;
}

export interface GenerateResult {
  toolInput?: Record<string, unknown>;
  text?: string;
}

export type GenerateFn = (call: GenerateCall) => Promise<GenerateResult>;

const here = dirname(fileURLToPath(import.meta.url));
const workspaceRoot = process.env.WORKSPACE_ROOT;
const llmRoot = workspaceRoot ? join(workspaceRoot, "projects/opencode/packages/llm") : join(here, "../../../projects/opencode/packages/llm");

export async function generateWithLLM(call: GenerateCall): Promise<GenerateResult> {
  const route = await providerRoute(call.providerID);
  const api = await loadApi();
  const key = await providerKey(call.providerID);
  const routed = api.route.with({
    provider: call.providerID,
    endpoint: { baseURL: route.baseURL },
    auth: key.length > 0 ? api.bearer(key) : api.passthrough,
    headers: { ...route.headers, "x-opencode-session": call.sessionID },
  });
  const request = api.LLM.request({
    model: routed.model({ id: call.modelID, provider: call.providerID }),
    system: call.system,
    prompt: call.prompt,
    tools: [{
      name: call.toolName,
      description: "Return the moderator verdict.",
      inputSchema: {
        type: "object",
        properties: {
          decision: { type: "string", enum: ["AGENT_COMPLETE", "AGENT_CONTINUING", "AGENT_STALLED", "AGENT_BLOCKED", "AGENT_STOPPED"] },
          reason: { type: "string", enum: ["WORK_COMPLETE", "WORK_REMAINS", "NO_PROGRESS", "AWAITING_USER", "AWAITING_OPERATOR", "USER_STOP"] },
        },
        required: ["decision", "reason"],
        additionalProperties: false,
      },
    }],
    toolChoice: "required",
  });
  const response = await api.Effect.runPromise(
    api.LLMClient.generate(request).pipe(
      api.Effect.provide(api.LLMClient.layer),
      api.Effect.provide(api.RequestExecutor.fetchLayer),
    ),
  );
  const input = response.toolCalls[0]?.input;
  return {
    toolInput: input !== null && typeof input === "object" && !Array.isArray(input) ? input as Record<string, unknown> : undefined,
    text: response.text,
  };
}

async function loadApi(): Promise<{
  Effect: { runPromise: (value: unknown) => Promise<LlmResponse>; provide: (layer: unknown) => unknown };
  LLM: { request: (input: Record<string, unknown>) => unknown };
  LLMClient: { generate: (request: unknown) => { pipe: (...args: unknown[]) => unknown }; layer: unknown };
  bearer: (key: string) => unknown;
  passthrough: unknown;
  route: { with: (input: Record<string, unknown>) => { model: (input: { id: string; provider: string }) => unknown } };
  RequestExecutor: { fetchLayer: unknown };
}> {
  const require = createRequire(join(llmRoot, "package.json"));
  const effect = await import(pathToFileURL(require.resolve("effect")).href);
  const llm = await import(pathToFileURL(join(llmRoot, "src/index.ts")).href);
  const compatible = await import(pathToFileURL(join(llmRoot, "src/protocols/openai-compatible-chat.ts")).href);
  const auth = await import(pathToFileURL(join(llmRoot, "src/route/auth.ts")).href);
  const executor = await import(pathToFileURL(join(llmRoot, "src/route/executor.ts")).href);
  return {
    Effect: effect.Effect,
    LLM: llm.LLM,
    LLMClient: llm.LLMClient,
    bearer: auth.bearer,
    passthrough: auth.passthrough,
    route: compatible.route,
    RequestExecutor: executor.RequestExecutor,
  };
}

interface LlmResponse {
  text: string;
  toolCalls: Array<{ input?: unknown }>;
}

async function providerRoute(providerID: string): Promise<{ baseURL: string; headers: Record<string, string> }> {
  const config = await readOpenCodeConfig();
  const providers = config.provider;
  if (typeof providers !== "object" || providers === null || Array.isArray(providers)) {
    throw new Error("opencode config has no provider block");
  }
  const provider = (providers as Record<string, unknown>)[providerID];
  if (typeof provider !== "object" || provider === null || Array.isArray(provider)) {
    throw new Error(`moderator selector provider is missing: ${providerID}`);
  }
  const options = (provider as { options?: unknown }).options;
  if (typeof options !== "object" || options === null || Array.isArray(options)) {
    throw new Error(`moderator selector provider has no route: ${providerID}`);
  }
  const baseURL = (options as { baseURL?: unknown }).baseURL;
  if (typeof baseURL !== "string" || baseURL.length === 0) {
    throw new Error(`moderator selector provider has no baseURL: ${providerID}`);
  }
  const headers: Record<string, string> = {};
  const rawHeaders = (options as { headers?: unknown }).headers;
  if (typeof rawHeaders === "object" && rawHeaders !== null && !Array.isArray(rawHeaders)) {
    for (const [key, value] of Object.entries(rawHeaders)) {
      if (typeof value === "string") headers[key] = value;
    }
  }
  return { baseURL, headers };
}

async function providerKey(providerID: string): Promise<string> {
  const root = process.env.XDG_DATA_HOME && process.env.XDG_DATA_HOME.length > 0
    ? process.env.XDG_DATA_HOME
    : join(process.env.HOME ?? "", ".local", "share");
  const raw = await readFile(join(root, "opencode", "auth.json"), "utf8");
  const parsed = JSON.parse(raw) as Record<string, { key?: string }>;
  const key = parsed[providerID]?.key;
  if (typeof key !== "string") throw new Error(`moderator selector provider has no OpenCode auth entry: ${providerID}`);
  return key;
}
