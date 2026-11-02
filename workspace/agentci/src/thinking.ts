const EFFORT_ORDER = ["minimal", "low", "medium", "high", "max", "xhigh", "off", "none"] as const;
const NEVER = new Set(["off", "none"]);

export interface ThinkingParamsInput {
  model: { variants?: Record<string, unknown> };
}

export interface ThinkingParamsOutput {
  options?: Record<string, unknown>;
}

export function requestedEffort(value: string | undefined): string {
  const requested = value === undefined || value.length === 0 ? "low" : value;
  return NEVER.has(requested) ? "low" : requested;
}

export function chooseEffort(requested: string, variants: Record<string, unknown> | undefined): string | null {
  if (variants === undefined) return null;
  const names = Object.keys(variants);
  if (names.length === 0) return null;
  if (names.includes(requested)) return requested;
  for (const candidate of EFFORT_ORDER) {
    if (NEVER.has(candidate)) continue;
    if (names.includes(candidate)) return candidate;
  }
  return null;
}

export function applyThinkingEffort(input: ThinkingParamsInput, output: ThinkingParamsOutput): void {
  const chosen = chooseEffort(requestedEffort(process.env.OC_THINKING_EFFORT), input.model.variants);
  if (chosen === null) return;
  output.options = { ...(output.options ?? {}), reasoningEffort: chosen };
}
