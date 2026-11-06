import { assertFitsModeratorContext, buildCaseState } from "./context.ts";
import type { ClassifierCapture, ClassifierOutcome, ReasonCode, TodoFact, Verdict, VerdictDecision } from "./types.ts";
import type { ModelSelector } from "./model-select.ts";
import { CLASSIFIER_SYSTEM_PROMPT } from "./prompt.ts";
import { generateWithLLM, type GenerateFn } from "./generate.ts";

export const VERDICT_TOOL = "moderator_verdict";
const CLASSIFIER_TIMEOUT_MS = 30000;

export interface ClassifyInput {
  parentSessionID: string;
  todos: readonly TodoFact[];
  previousResponse: string;
  userMessages: readonly string[];
  toolActivity: readonly string[];
  agentMode: "build" | "answer";
}

const DECISIONS: readonly VerdictDecision[] = ["AGENT_COMPLETE", "AGENT_CONTINUING", "AGENT_STALLED", "AGENT_BLOCKED", "AGENT_STOPPED"];
const REASONS: readonly ReasonCode[] = ["WORK_COMPLETE", "WORK_REMAINS", "NO_PROGRESS", "AWAITING_USER", "AWAITING_OPERATOR", "USER_STOP"];
const VALID: Record<VerdictDecision, readonly ReasonCode[]> = {
  AGENT_COMPLETE: ["WORK_COMPLETE"],
  AGENT_CONTINUING: ["WORK_REMAINS"],
  AGENT_STALLED: ["NO_PROGRESS"],
  AGENT_BLOCKED: ["AWAITING_USER", "AWAITING_OPERATOR"],
  AGENT_STOPPED: ["USER_STOP"],
};

export async function classify(
  selectors: readonly ModelSelector[],
  input: ClassifyInput,
  generate: GenerateFn = generateWithLLM,
  signal?: AbortSignal,
): Promise<ClassifierOutcome> {
  const startedAt = Date.now();
  const cycles = timeoutCycles();
  let lastError = "moderator classifier did not run";
  let attempts = 0;
  for (let cycle = 0; cycle < cycles; cycle += 1) {
    let timedOut = false;
    for (let index = 0; index < selectors.length; index += 1) {
      const selector = selectors[index];
      const name = `${selector.providerID}/${selector.modelID}`;
      attempts += 1;
      if (signal?.aborted) return captureOutcome(selector, attempts, startedAt, "moderator classification was cancelled");
      try {
        const prompt = buildCaseState(input);
        assertFitsModeratorContext(`${CLASSIFIER_SYSTEM_PROMPT}\n${prompt}`);
        const response = await withTimeout(generate({
          providerID: selector.providerID,
          modelID: selector.modelID,
          system: CLASSIFIER_SYSTEM_PROMPT,
          prompt,
          toolName: VERDICT_TOOL,
          sessionID: input.parentSessionID,
        }), CLASSIFIER_TIMEOUT_MS);
        const parsed = parseToolInput(response.toolInput);
        if (parsed === undefined) {
          throw new Error(`moderator selector did not return a valid verdict: ${name} input=${JSON.stringify(response.toolInput ?? null)} text=${response.text ?? ""}`);
        }
        return { verdict: parsed.verdict, capture: { selector: name, sessionID: null, attempts, durationMs: Date.now() - startedAt, input: parsed.input } };
      } catch (error) {
        lastError = error instanceof Error ? error.message : String(error);
        if (lastError === "moderator classifier timed out") timedOut = true;
      }
    }
    if (!timedOut) break;
  }
  return captureOutcome(selectors[0], attempts, startedAt, lastError);
}

export function timeoutCycles(): number {
  const raw = process.env.MODERATOR_TIMEOUT_CYCLES;
  if (raw === undefined || raw.length === 0) return 3;
  if (!/^[1-9][0-9]*$/.test(raw)) throw new Error(`MODERATOR_TIMEOUT_CYCLES must be a positive integer, got '${raw}'`);
  return Number(raw);
}

export function parseToolInput(input: Record<string, unknown> | undefined): { verdict: Verdict; input: Record<string, unknown> } | undefined {
  if (input === undefined) return undefined;
  const keys = Object.keys(input).sort();
  if (keys.length !== 2 || keys[0] !== "decision" || keys[1] !== "reason") return undefined;
  const decision = input.decision;
  const reasonCode = input.reason;
  if (typeof decision !== "string" || typeof reasonCode !== "string") return undefined;
  if (!isDecision(decision) || !isReason(reasonCode)) return undefined;
  if (!VALID[decision].includes(reasonCode)) return undefined;
  return { verdict: { decision, reasonCode, reason: `Classifier decision ${decision} (${reasonCode}).` }, input };
}

function captureOutcome(selector: ModelSelector | undefined, attempts: number, startedAt: number, error: string): ClassifierOutcome {
  return {
    capture: {
      selector: selector === undefined ? "" : `${selector.providerID}/${selector.modelID}`,
      sessionID: null,
      attempts,
      durationMs: Date.now() - startedAt,
      input: null,
    },
    error,
  };
}

function isDecision(value: string): value is VerdictDecision {
  return (DECISIONS as readonly string[]).includes(value);
}

function isReason(value: string): value is ReasonCode {
  return (REASONS as readonly string[]).includes(value);
}

async function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  let timer: NodeJS.Timeout | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<never>((_resolve, reject) => { timer = setTimeout(() => reject(new Error("moderator classifier timed out")), ms); }),
    ]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}
