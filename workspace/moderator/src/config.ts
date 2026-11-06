import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { configRoot, type ModelSelector } from "./model-select.ts";

export interface ProviderModel {
  id: string;
  providerID: string;
}

export interface ProviderRecord {
  id?: string;
  models?: Record<string, unknown>;
}

export function selectorKey(model: ModelSelector): string {
  return `${model.providerID}/${model.modelID}`;
}

export function modelDisplayName(config: Record<string, unknown>, selector: string): string {
  const split = selector.indexOf("/");
  if (split <= 0) return selector;
  const providerID = selector.slice(0, split);
  const modelID = selector.slice(split + 1);
  const providers = config.provider;
  if (typeof providers !== "object" || providers === null || Array.isArray(providers)) return modelID;
  const provider = (providers as Record<string, unknown>)[providerID];
  if (typeof provider !== "object" || provider === null || Array.isArray(provider)) return modelID;
  const models = (provider as { models?: unknown }).models;
  if (typeof models !== "object" || models === null || Array.isArray(models)) return modelID;
  const model = (models as Record<string, unknown>)[modelID];
  if (typeof model !== "object" || model === null || Array.isArray(model)) return modelID;
  const name = (model as { name?: unknown }).name;
  if (typeof name === "string" && name.length > 0) return name;
  return modelID;
}

export function validateAgainstProviders(models: readonly ModelSelector[], providers: readonly ProviderRecord[]): ModelSelector[] {
  const available = new Set<string>();
  for (const provider of providers) {
    const providerID = provider.id;
    if (typeof providerID !== "string") continue;
    for (const modelID of Object.keys(provider.models ?? {})) available.add(`${providerID}/${modelID}`);
  }
  for (const model of models) {
    if (!available.has(selectorKey(model))) {
      throw new Error(`moderator selector is not available in OpenCode: ${selectorKey(model)}`);
    }
  }
  return [...models];
}

export function validateAgainstConfig(models: readonly ModelSelector[], config: Record<string, unknown>): ModelSelector[] {
  const providers = config.provider;
  if (typeof providers !== "object" || providers === null || Array.isArray(providers)) {
    throw new Error("opencode config has no provider block");
  }
  const available = new Set<string>();
  for (const [providerID, value] of Object.entries(providers as Record<string, unknown>)) {
    if (typeof value !== "object" || value === null || Array.isArray(value)) continue;
    const models = (value as { models?: unknown }).models;
    if (typeof models !== "object" || models === null || Array.isArray(models)) continue;
    for (const modelID of Object.keys(models as Record<string, unknown>)) available.add(`${providerID}/${modelID}`);
  }
  for (const model of models) {
    if (!available.has(selectorKey(model))) {
      throw new Error(`moderator selector is not available in the OpenCode config: ${selectorKey(model)}`);
    }
  }
  return [...models];
}

export async function readOpenCodeConfig(root: string = configRoot()): Promise<Record<string, unknown>> {
  const json = join(root, "opencode.json");
  const jsonc = join(root, "opencode.jsonc");
  let raw: string;
  try {
    raw = await readFile(jsonc, "utf8");
  } catch (error) {
    if ((error as { code?: string }).code !== "ENOENT") throw error;
    raw = await readFile(json, "utf8");
  }
  const parsed = JSON.parse(stripJsonComments(raw)) as unknown;
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("opencode config must be a JSON object");
  }
  return parsed as Record<string, unknown>;
}

export function stripJsonComments(input: string): string {
  let output = "";
  let index = 0;
  let inString = false;
  let escaped = false;
  while (index < input.length) {
    const char = input[index];
    const next = input[index + 1];
    if (inString) {
      output += char;
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === "\"") inString = false;
      index += 1;
      continue;
    }
    if (char === "\"") {
      inString = true;
      output += char;
      index += 1;
      continue;
    }
    if (char === "/" && next === "/") {
      while (index < input.length && input[index] !== "\n") index += 1;
      continue;
    }
    if (char === "/" && next === "*") {
      index += 2;
      while (index < input.length && !(input[index] === "*" && input[index + 1] === "/")) index += 1;
      index += 2;
      continue;
    }
    output += char;
    index += 1;
  }
  return removeTrailingCommas(output);
}

function removeTrailingCommas(input: string): string {
  let output = "";
  let inString = false;
  let escaped = false;
  for (let index = 0; index < input.length; index += 1) {
    const char = input[index];
    if (inString) {
      output += char;
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === "\"") inString = false;
      continue;
    }
    if (char === "\"") {
      inString = true;
      output += char;
      continue;
    }
    if (char === ",") {
      let cursor = index + 1;
      while (cursor < input.length && /\s/.test(input[cursor])) cursor += 1;
      if (input[cursor] === "}" || input[cursor] === "]") continue;
    }
    output += char;
  }
  return output;
}
