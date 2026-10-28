import { readFile } from "node:fs/promises";

export interface ClassifierCaseInputs {
  previousResponse: string;
  userMessages: string[];
  todos: Array<{ status?: string; content?: string }>;
}

export interface ClassifierCaseManifest {
  id: string;
  provenance: { sessionID: string | null; assistantID: string | null; decisionID: string | null };
  expectedDecision: string | null;
  expectedReason: string | null;
  forbiddenDecisions: string[];
  labelSource: string;
  hash: string;
  transcript: string;
  observed?: { decision: string; reasonCode: string; signal: string; source: string };
}

export interface ClassifierFixture {
  version: number;
  cases: ClassifierCaseManifest[];
}

export interface LoadedClassifierCase extends ClassifierCaseManifest {
  inputs: ClassifierCaseInputs;
}

const MANIFEST = new URL("../fixtures/classifier-cases.json", import.meta.url);

export async function loadClassifierManifest(): Promise<ClassifierFixture> {
  return JSON.parse(await readFile(MANIFEST, "utf8")) as ClassifierFixture;
}

function missingFile(error: unknown): boolean {
  return typeof error === "object" && error !== null && "code" in error && (error as { code?: unknown }).code === "ENOENT";
}

export interface ClassifierVerdictFact {
  decision: string;
  reasonCode: string;
}

export function scoreClassifierCase(value: ClassifierCaseManifest, verdict: ClassifierVerdictFact): string | null {
  if (value.expectedDecision) {
    if (verdict.decision !== value.expectedDecision) return `expected ${value.expectedDecision}, got ${verdict.decision}`;
    if (value.expectedReason && verdict.reasonCode !== value.expectedReason) return `expected ${value.expectedReason}, got ${verdict.reasonCode}`;
    return null;
  }
  if (value.forbiddenDecisions.includes(verdict.decision)) return `repeated mined failure ${verdict.decision}/${verdict.reasonCode}`;
  return null;
}

export async function loadClassifierCases(): Promise<LoadedClassifierCase[]> {
  const fixture = await loadClassifierManifest();
  const cases: LoadedClassifierCase[] = [];
  for (const value of fixture.cases) {
    const body = new URL(`../fixtures/${value.transcript}`, import.meta.url);
    let inputs: ClassifierCaseInputs;
    try {
      inputs = JSON.parse(await readFile(body, "utf8")) as ClassifierCaseInputs;
    } catch (error) {
      if (missingFile(error)) {
        throw new Error(`classifier case ${value.id} transcript body is missing; run npm run source-cases -- --rebuild`);
      }
      throw error;
    }
    cases.push({ ...value, inputs });
  }
  return cases;
}
