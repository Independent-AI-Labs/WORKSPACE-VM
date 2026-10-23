import { CLASSIFIER_FORMAT_RETRIES, CLASSIFIER_SEED, MAX_COMPLETION_TOKENS, MAX_INPUT_TOKENS, MINICPM_MODEL_ID, MODERATION_GRAMMAR, type ModerationOptions } from "./config.ts";
import { EMPTY_USER_PROMPT, summarizeTodos } from "./context.ts";
import type { ReasonCode, Ruling, TodoFact, Verdict, VerdictDecision } from "./types.ts";

export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export interface ClassifyInput {
  todos: readonly TodoFact[];
  previousResponse: string;
  userMessages: readonly string[];
}

export interface ClassifyOutcome {
  verdict?: Verdict;
  capture: string;
  formatError: boolean;
  error?: string;
}

interface ChatMessage {
  role: "system" | "user";
  content: string;
}

export const SYSTEM_PROMPT = [
  "You classify an autonomous coding agent's latest response. Output exactly two lines: 'decision: <DECISION>' then 'reason: <REASON>'.",
  "",
  "Decide whether the agent may stop now. Apply this priority order:",
  "1. If the agent hands off to an operator or another external action (it tells the user to run a command, for example as the operator, or it needs credentials, permission, or access it does not have), choose AGENT_BLOCKED with reason AWAITING_OPERATOR. Asking the user to run a command and report the output is an operator handoff, not a question.",
  "2. If the agent asks the user a question or requests a decision, approval, or clarification and no external action is required, choose AGENT_BLOCKED with reason AWAITING_USER.",
  "3. If the user's request is fully and correctly complete, choose AGENT_COMPLETE with reason WORK_COMPLETE.",
  "4. If the most recent user message tells the agent to stop, cancel, abort, or not continue the work, choose AGENT_STOPPED with reason USER_STOP. This holds even when tracked work remains and takes precedence over an automatic continuation. Judge the direction of the instruction, not its tone: an emphatic, impatient, or angry push to proceed, to hurry, or to get on with the requested work reaffirms the request and is not a halt.",
  "5. Otherwise the request is unfinished and the agent can keep working on its own, so choose a CONTINUE decision even when todos are pending: AGENT_CONTINUING with reason WORK_REMAINS if it made progress, AGENT_STALLED with reason NO_PROGRESS if it made none. Merely listing remaining work, proposing a plan, or promising to continue is NOT a stop.",
  "",
  "Example 1",
  "User request(s):",
  "- Add hello() and run its test",
  "Tracked todos:",
  "- [completed] Implement hello()",
  "- [completed] Run the test",
  "Assistant response: Done. hello() is implemented and its test passes.",
  "Output:",
  "decision: AGENT_COMPLETE",
  "reason: WORK_COMPLETE",
  "",
  "Example 2",
  "User request(s):",
  "- Implement the parser and the writer",
  "Tracked todos:",
  "- [completed] Implement parser",
  "- [pending] Implement writer",
  "Assistant response: I implemented the parser. I will implement the writer next.",
  "Output:",
  "decision: AGENT_CONTINUING",
  "reason: WORK_REMAINS",
  "",
  "Example 3",
  "User request(s):",
  "- Implement the parser and the writer",
  "Tracked todos:",
  "- [in_progress] Implement parser",
  "- [pending] Implement writer",
  "Assistant response: I explored the code but did not change anything yet.",
  "Output:",
  "decision: AGENT_STALLED",
  "reason: NO_PROGRESS",
  "",
  "Example 4",
  "User request(s):",
  "- Refactor the config loader",
  "Tracked todos:",
  "- [in_progress] Refactor the loader",
  "Assistant response: I can keep the existing behavior or change the public API. Which do you want me to do?",
  "Output:",
  "decision: AGENT_BLOCKED",
  "reason: AWAITING_USER",
  "",
  "Example 5",
  "User request(s):",
  "- Deploy the guard fix",
  "Tracked todos:",
  "- [pending] Apply the deploy script",
  "Assistant response: I prepared the deploy script. Run `sudo bash /tmp/deploy.sh` as the operator to apply it, then tell me the result.",
  "Output:",
  "decision: AGENT_BLOCKED",
  "reason: AWAITING_OPERATOR",
  "",
  "Example 6",
  "User request(s):",
  "- Fix the guard and deploy it",
  "Tracked todos:",
  "- [in_progress] Refactor the guard",
  "- [pending] Deploy the fix",
  "Assistant response: I created /tmp/guard-deploy.sh (not committed). Run it as the operator: sudo bash /tmp/guard-deploy.sh. I did not run it; tell me the result.",
  "Output:",
  "decision: AGENT_BLOCKED",
  "reason: AWAITING_OPERATOR",
  "",
  "Example 7",
  "User request(s):",
  "- Optimize the build until it is as fast as possible",
  "- Why are you still running tests? Stop now.",
  "Assistant response: I have stopped the test run.",
  "Output:",
  "decision: AGENT_STOPPED",
  "reason: USER_STOP",
  "",
  "Example 8",
  "User request(s):",
  "- Implement the parser and the writer",
  "- Cancel this; do not continue.",
  "Tracked todos:",
  "- [in_progress] Implement parser",
  "- [pending] Implement writer",
  "Assistant response: Understood, I have stopped.",
  "Output:",
  "decision: AGENT_STOPPED",
  "reason: USER_STOP",
  "",
  "Example 9",
  "User request(s):",
  "- Implement the parser and the writer",
  "- GO GO GO",
  "Tracked todos:",
  "- [in_progress] Implement parser",
  "- [pending] Implement writer",
  "Assistant response: I implemented the parser. The writer is not started yet.",
  "Output:",
  "decision: AGENT_CONTINUING",
  "reason: WORK_REMAINS",
  "",
  "Empty or whitespace-only user messages are interruption artifacts, not halts: continue the work.",
].join("\n");

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
  const messages = buildMessages(input, systemPrompt);
  let lastCapture = "";
  for (let attempt = 0; attempt < CLASSIFIER_FORMAT_RETRIES; attempt += 1) {
    const trimmed = await trimToBudget(options, messages, fetchImpl);
    const response = await requestCompletion(options, trimmed, fetchImpl);
    lastCapture = response.content;
    if (response.finishReason !== "stop") {
      if (attempt + 1 === CLASSIFIER_FORMAT_RETRIES) return { capture: lastCapture, formatError: true, error: `classifier finished with reason '${response.finishReason}'` };
      continue;
    }
    const parsed = parseVerdict(response.content);
    if (parsed) return { verdict: parsed, capture: lastCapture, formatError: false };
  }
  return { capture: lastCapture, formatError: true, error: "classifier did not return a valid verdict" };
}

export function buildMessages(input: ClassifyInput, systemPrompt: string = SYSTEM_PROMPT): ChatMessage[] {
  const sections = [
    "User request(s):",
    input.userMessages.length > 0 ? input.userMessages.map((message) => `- ${message.trim().length > 0 ? message : EMPTY_USER_PROMPT}`).join("\n") : "- (none recorded)",
  ];
  if (input.todos.length > 0) sections.push("", "Tracked todos:", summarizeTodos(input.todos));
  sections.push("", "Assistant response:", input.previousResponse);
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
      temperature: 0,
      top_k: 1,
      top_p: 1,
      min_p: 0,
      seed: CLASSIFIER_SEED,
      max_tokens: MAX_COMPLETION_TOKENS,
      grammar: MODERATION_GRAMMAR,
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