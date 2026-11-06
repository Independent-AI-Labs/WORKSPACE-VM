import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { classify } from "../src/classifier.ts";
import { readOpenCodeConfig } from "../src/config.ts";
import { loadClassifierCases, scoreClassifierCase } from "./support/classifier-cases.ts";

interface RankedModel {
  providerID: string;
  modelID: string;
  inputCost: number;
  outputCost: number;
  price: number;
}

const skipName = /embed|image|video|tts|whisper|audio|moderation/i;

export async function cheapestModels(limit: number): Promise<RankedModel[]> {
  const config = await readOpenCodeConfig();
  const providers = config.provider;
  if (typeof providers !== "object" || providers === null || Array.isArray(providers)) {
    throw new Error("opencode config has no provider block");
  }
  const ranked: RankedModel[] = [];
  for (const [providerID, provider] of Object.entries(providers as Record<string, unknown>)) {
    if (providerID !== "workspace-gw-opencode-go-api-key") continue;
    if (typeof provider !== "object" || provider === null || Array.isArray(provider)) continue;
    const models = (provider as { models?: unknown }).models;
    if (typeof models !== "object" || models === null || Array.isArray(models)) continue;
    for (const [modelID, model] of Object.entries(models as Record<string, unknown>)) {
      if (typeof model !== "object" || model === null || Array.isArray(model)) continue;
      if (skipName.test(modelID)) continue;
      const cost = (model as { cost?: { input?: unknown; output?: unknown } }).cost;
      const input = cost?.input;
      const output = cost?.output;
      if (typeof input !== "number" || typeof output !== "number") continue;
      ranked.push({ providerID, modelID, inputCost: input, outputCost: output, price: input + output });
    }
  }
  const auth = await readAuthProviders();
  ranked.sort((left, right) => left.price - right.price || left.modelID.localeCompare(right.modelID));
  const seen = new Set<string>();
  const unique: RankedModel[] = [];
  for (const model of ranked) {
    if (seen.has(model.modelID)) continue;
    if (!auth.has(model.providerID)) continue;
    seen.add(model.modelID);
    unique.push(model);
    if (unique.length === limit) break;
  }
  return unique;
}

async function readAuthProviders(): Promise<Set<string>> {
  const root = process.env.XDG_DATA_HOME && process.env.XDG_DATA_HOME.length > 0
    ? process.env.XDG_DATA_HOME
    : join(process.env.HOME ?? "", ".local", "share");
  const parsed = JSON.parse(await readFile(join(root, "opencode", "auth.json"), "utf8")) as Record<string, unknown>;
  return new Set(Object.keys(parsed));
}

export interface CaseScore {
  id: string;
  expectedDecision: string;
  expectedReason: string;
  gotDecision: string | null;
  gotReason: string | null;
  match: boolean;
  ms: number;
  error: string | null;
}

export async function scoreModel(providerID: string, modelID: string): Promise<{ matched: number; total: number; avgMs: number; cases: CaseScore[] }> {
  const loaded = await loadClassifierCases();
  const limit = Number(process.env.SCORE_LIMIT ?? "0");
  const cases = limit > 0 ? loaded.slice(0, limit) : loaded;
  const scored: CaseScore[] = [];
  let matched = 0;
  let duration = 0;
  for (const item of cases) {
    const started = Date.now();
    const outcome = await classify([{ providerID, modelID }], {
      parentSessionID: item.id,
      todos: item.inputs.todos,
      previousResponse: item.inputs.previousResponse,
      userMessages: item.inputs.userMessages,
      toolActivity: [],
      agentMode: item.inputs.answerMode === true ? "answer" : "build",
    });
    const ms = Date.now() - started;
    duration += ms;
    const mismatch = outcome.verdict === undefined ? outcome.error ?? "no verdict" : scoreClassifierCase(item, outcome.verdict);
    const row: CaseScore = {
      id: item.id,
      expectedDecision: item.expectedDecision,
      expectedReason: item.expectedReason,
      gotDecision: outcome.verdict?.decision ?? null,
      gotReason: outcome.verdict?.reasonCode ?? null,
      match: mismatch === null,
      ms,
      error: mismatch,
    };
    if (row.match) matched += 1;
    scored.push(row);
    process.stdout.write(`${modelID} ${item.id} ${row.gotDecision ?? "ERROR"}/${row.gotReason ?? ""}\n`);
  }
  return { matched, total: cases.length, avgMs: Math.round(duration / cases.length), cases: scored };
}

async function probe(model: RankedModel): Promise<string> {
  const cases = await loadClassifierCases();
  const item = cases[0];
  if (item === undefined) return "no cases";
  const outcome = await classify([{ providerID: model.providerID, modelID: model.modelID }], {
    parentSessionID: item.id,
    todos: item.inputs.todos,
    previousResponse: item.inputs.previousResponse,
    userMessages: item.inputs.userMessages,
    toolActivity: [],
    agentMode: "build",
  });
  if (outcome.verdict !== undefined) return `${outcome.verdict.decision}/${outcome.verdict.reasonCode}`;
  return outcome.error ?? "no verdict";
}

async function main(): Promise<void> {
  const limit = Number(process.argv[2] ?? "10");
  const listed = process.argv.slice(3).filter((arg) => arg !== "probe");
  const catalog = await cheapestModels(200);
  const models = listed.length > 0
    ? listed.map((entry) => {
      const split = entry.indexOf("/");
      const providerID = split > 0 ? entry.slice(0, split) : "workspace-gw-opencode-go-api-key";
      const modelID = split > 0 ? entry.slice(split + 1) : entry;
      return catalog.find((row) => row.modelID === modelID) ?? { providerID, modelID, inputCost: 0, outputCost: 0, price: 0 };
    })
    : catalog.slice(0, limit);
  if (process.argv[3] === "probe") {
    for (const model of models) {
      const result = await probe(model);
      process.stdout.write(`${model.price}\t${model.providerID}/${model.modelID}\t${result}\n`);
    }
    return;
  }
  const report = [];
  for (const model of models) {
    process.stdout.write(`MODEL ${model.providerID}/${model.modelID} price=${model.price}\n`);
    const result = await scoreModel(model.providerID, model.modelID);
    const times = result.cases.map((row) => row.ms).sort((left, right) => left - right);
    const pick = (ratio: number) => times[Math.min(times.length - 1, Math.floor(ratio * (times.length - 1)))] ?? 0;
    report.push({
      ...model,
      matched: result.matched,
      total: result.total,
      avgMs: result.avgMs,
      minMs: times[0] ?? 0,
      p50Ms: pick(0.5),
      p95Ms: pick(0.95),
      maxMs: times[times.length - 1] ?? 0,
      totalMs: times.reduce((sum, value) => sum + value, 0),
      cases: result.cases,
    });
    process.stdout.write(`SUMMARY ${model.modelID} ${result.matched}/${result.total} avg_ms=${result.avgMs} input=${model.inputCost} output=${model.outputCost} price=${model.price}\n`);
    const out = process.env.SCORE_OUT ?? join(import.meta.dirname, "results", "score.json");
    await mkdir(join(import.meta.dirname, "results"), { recursive: true });
    await writeFile(out, `${JSON.stringify({ createdAt: new Date().toISOString(), models: report }, null, 2)}\n`);
  }
  process.stdout.write(`WROTE ${process.env.SCORE_OUT ?? join(import.meta.dirname, "results", "score.json")}\n`);
}

if (process.argv[1]?.endsWith("score-models.ts")) {
  main().catch((error: unknown) => {
    process.stderr.write(`${error instanceof Error ? error.stack ?? error.message : String(error)}\n`);
    process.exit(1);
  });
}
