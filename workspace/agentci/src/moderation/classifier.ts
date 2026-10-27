import { readFileSync } from "node:fs";
import { CLASSIFIER_FORMAT_RETRIES, CLASSIFIER_SEED, MAX_COMPLETION_TOKENS, MAX_INPUT_TOKENS, MINICPM_MODEL_ID, MODERATION_GRAMMAR, type ModerationOptions } from "./config.ts";
import { EMPTY_USER_PROMPT, summarizeTodos } from "./context.ts";
import type { ChatMessage, ClassifierCapture, ReasonCode, Ruling, TodoFact, Verdict, VerdictDecision } from "./types.ts";

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export interface ClassifyInput {
  todos: readonly TodoFact[];
  previousResponse: string;
  userMessages: readonly string[];
}

export interface ClassifyOutcome {
  verdict?: Verdict;
  capture: ClassifierCapture;
  formatError: boolean;
  error?: string;
}

const SAMPLING = {
  temperature: 0,
  top_k: 1,
  top_p: 1,
  min_p: 0,
  seed: CLASSIFIER_SEED,
  max_tokens: MAX_COMPLETION_TOKENS,
} as const;

export function loadPrompt(name: string): string {
  return readFileSync(new URL(`./prompts/${name}`, import.meta.url), "utf8");
}

export const SYSTEM_PROMPT = loadPrompt("classifier-system.txt");

const VALID_DECISIONS: Record<string, readonly ReasonCode[]> = {
  AGENT_COMPLETE: ["WORK_COMPLETE"],
  AGENT_CONTINUING: ["WORK_REMAINS"],
  AGENT_STALLED: ["NO_PROGRESS"],
  AGENT_BLOCKED: ["AWAITING_USER", "AWAITING_OPERATOR"],
  AGENT_STOPPED: ["USER_STOP"],
};

export async function classify(options: ModerationOptions, input: ClassifyInput, fetchImpl: FetchLike = fetch): Promise<ClassifyOutcome> {
  return classifyWithPrompt(options, input, SYSTEM_PROMPT, fetchImpl);
}

export async function classifyWithPrompt(options: ModerationOptions, input: ClassifyInput, systemPrompt: string, fetchImpl: FetchLike = fetch): Promise<ClassifyOutcome> {
  const startedAt = Date.now();
  const messages = buildMessages(input, systemPrompt);
  let attemptCount = 0;
  let lastMessages = messages;
  let lastCompletion = "";
  let lastFinish = "";
  const capture = (): ClassifierCapture => ({
    messages: lastMessages,
    completion: lastCompletion,
    finishReason: lastFinish,
    model: options.model,
    sampling: { ...SAMPLING },
    attempts: attemptCount,
    durationMs: Date.now() - startedAt,
  });
  for (let attempt = 0; attempt < CLASSIFIER_FORMAT_RETRIES; attempt += 1) {
    attemptCount = attempt + 1;
    const trimmed = await trimToBudget(options, messages, fetchImpl);
    lastMessages = trimmed;
    const response = await requestCompletion(options, trimmed, fetchImpl);
    lastCompletion = response.content;
    lastFinish = response.finishReason;
    if (response.finishReason !== "stop") {
      if (attempt + 1 === CLASSIFIER_FORMAT_RETRIES) return { capture: capture(), formatError: true, error: `classifier finished with reason '${response.finishReason}'` };
      continue;
    }
    const parsed = parseVerdict(response.content);
    if (parsed) return { verdict: parsed, capture: capture(), formatError: false };
  }
  return { capture: capture(), formatError: true, error: "classifier did not return a valid verdict" };
}

export function buildMessages(input: ClassifyInput, systemPrompt: string = SYSTEM_PROMPT): ChatMessage[] {
  const sections = [
    "Judge the agent's latest response. It is the decision target; the user request is context.",
    "",
    "The agent's latest response (judge this):",
    input.previousResponse,
    "",
    "User request(s):",
    input.userMessages.length > 0 ? input.userMessages.map((message) => `- ${message.trim().length > 0 ? message : EMPTY_USER_PROMPT}`).join("\n") : "- (none recorded)",
  ];
  if (input.todos.length > 0) sections.push("", "Tracked todos:", summarizeTodos(input.todos));
  sections.push("", "Reminder: if the response asks the user to run, test, play, listen, look, check, confirm, report, or decide something, choose AGENT_BLOCKED.");
  return [
    { role: "system", content: systemPrompt },
    { role: "user", content: sections.join("\n") },
  ];
}

export function parseVerdict(content: string): Verdict | undefined {
  const lines = content.trim().split("\n").map((line) => line.trim()).filter((line) => line.length > 0);
  if (lines.length !== 2) return undefined;
  const decisionLine = /^decision:\s*([A-Z_]+)$/.exec(lines[0]);
  const reasonLine = /^reason:\s*([A-Z_]+)$/.exec(lines[1]);
  if (!decisionLine || !reasonLine) return undefined;
  const decision = decisionLine[1] as VerdictDecision;
  const allowed = VALID_DECISIONS[decision];
  if (!allowed || !allowed.includes(reasonLine[1] as ReasonCode)) return undefined;
  return verdict(decision, reasonLine[1] as ReasonCode);
}

function verdict(decision: VerdictDecision, reasonCode: ReasonCode): Verdict {
  const pass = decision === "AGENT_COMPLETE";
  const completion: Ruling = pass
    ? { ruling: "PASS", reason: "Classifier reported the request complete." }
    : { ruling: "FAIL", reason: `Classifier decision ${decision} (${reasonCode}).` };
  const adherence: Ruling = decision === "AGENT_BLOCKED"
    ? { ruling: "FAIL", reason: "Classifier reported the agent is awaiting an external party." }
    : { ruling: "PASS", reason: "Classifier found no prompt-adherence violation." };
  return {
    decision,
    reason: `Classifier decision ${decision} (${reasonCode}).`,
    reasonCode,
    task_completion: completion,
    prompt_adherence: adherence,
  };
}

async function trimToBudget(options: ModerationOptions, messages: ChatMessage[], fetchImpl: FetchLike): Promise<ChatMessage[]> {
  let current = messages;
  for (;;) {
    const tokens = await countInputTokens(options, current, fetchImpl);
    if (tokens <= MAX_INPUT_TOKENS) return current;
    if (current.length < 2) throw new Error(`AgentCI classifier prompt (${tokens} tokens) exceeds the fixed ${MAX_INPUT_TOKENS}-token budget`);
    current = [current[0], truncate(current[1]), ...current.slice(2)];
  }
}

function truncate(message: ChatMessage): ChatMessage {
  const limit = Math.max(1, Math.floor(message.content.length / 2));
  return { role: message.role, content: `${message.content.slice(0, limit)}\n[truncated by AgentCI classifier]` };
}

async function countInputTokens(options: ModerationOptions, messages: ChatMessage[], fetchImpl: FetchLike): Promise<number> {
  const response = await fetchImpl(`${options.gatewayURL}/v1/chat/completions/input_tokens`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ model: options.model, messages }),
  });
  if (!response.ok) throw new Error(`AgentCI classifier token endpoint failed with HTTP ${response.status}`);
  const payload = await response.json() as Record<string, unknown>;
  const tokens = payload.input_tokens ?? payload.tokens;
  if (typeof tokens !== "number" || !Number.isFinite(tokens)) throw new Error("AgentCI classifier token endpoint returned no numeric token count");
  return tokens;
}

interface CompletionResult {
  content: string;
  finishReason: string;
}

async function requestCompletion(options: ModerationOptions, messages: ChatMessage[], fetchImpl: FetchLike): Promise<CompletionResult> {
  const response = await fetchImpl(`${options.gatewayURL}/v1/chat/completions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model: options.model,
      messages,
      temperature: SAMPLING.temperature,
      top_k: SAMPLING.top_k,
      top_p: SAMPLING.top_p,
      min_p: SAMPLING.min_p,
      seed: SAMPLING.seed,
      max_tokens: SAMPLING.max_tokens,
      grammar: MODERATION_GRAMMAR,
      cache_prompt: false,
      stream: false,
    }),
  });
  if (!response.ok) throw new Error(`AgentCI classifier completion failed with HTTP ${response.status}`);
  const payload = await response.json() as { choices?: Array<{ finish_reason?: string; message?: { content?: string } }> };
  const choice = payload.choices?.[0];
  if (!choice || typeof choice.finish_reason !== "string" || typeof choice.message?.content !== "string") {
    throw new Error("AgentCI classifier completion returned an unexpected payload");
  }
  return { content: choice.message.content, finishReason: choice.finish_reason };
}

export function isMiniCPM(model: string): boolean {
  return model === MINICPM_MODEL_ID;
}
