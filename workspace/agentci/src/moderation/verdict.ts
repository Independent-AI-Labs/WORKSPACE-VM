import { classify, verdictFor, type ClassifyInput, type ClassifyOutcome, type FetchLike } from "./classifier.ts";
import { CLASSIFIER_SEED, MAX_COMPLETION_TOKENS, type ModerationOptions } from "./config.ts";
import { declaredStatus, type DeclaredStatus } from "./context.ts";
import type { Verdict } from "./types.ts";

export function declaredVerdict(status: DeclaredStatus): Verdict {
  if (status === "COMPLETE") return verdictFor("AGENT_COMPLETE", "WORK_COMPLETE");
  if (status === "WAITING_FOR_OPERATOR") return verdictFor("AGENT_BLOCKED", "AWAITING_OPERATOR");
  if (status === "STOPPED") return verdictFor("AGENT_STOPPED", "USER_STOP");
  return verdictFor("AGENT_BLOCKED", "AWAITING_USER");
}

export async function resolveVerdict(options: ModerationOptions, input: ClassifyInput, fetchImpl: FetchLike = fetch): Promise<ClassifyOutcome> {
  const declared = declaredStatus(input.previousResponse);
  if (declared === null) return classify(options, input, fetchImpl);
  return {
    verdict: declaredVerdict(declared),
    formatError: false,
    capture: {
      messages: [],
      completion: `STATUS: ${declared}`,
      finishReason: "declared",
      model: options.model,
      sampling: {
        temperature: 0,
        top_k: 1,
        top_p: 1,
        min_p: 0,
        seed: CLASSIFIER_SEED,
        max_tokens: MAX_COMPLETION_TOKENS,
      },
      attempts: 0,
      durationMs: 0,
    },
  };
}
