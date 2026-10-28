import { classify, type ClassifyInput, type ClassifyOutcome, type FetchLike } from "./classifier.ts";
import type { ModerationOptions } from "./config.ts";

export async function resolveVerdict(options: ModerationOptions, input: ClassifyInput, fetchImpl: FetchLike = fetch): Promise<ClassifyOutcome> {
  return classify(options, input, fetchImpl);
}
