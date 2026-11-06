import { readFile } from "node:fs/promises";

export interface ClassifierCaseInputs {
  previousResponse: string;
  userMessages: string[];
  todos: Array<{ status?: string; content?: string }>;
  answerMode?: boolean;
}

export interface ClassifierCaseManifest {
  id: string;
  provenance: { sessionID: string | null; assistantID: string | null; decisionID: string | null };
  expectedDecision: string;
  expectedReason: string;
  labelSource: string;
  hash: string;
  transcript: string;
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

export function scoreClassifierCase(value: ClassifierCaseManifest, verdict: { decision: string; reasonCode: string }): string | null {
  if (verdict.decision !== value.expectedDecision) return `expected ${value.expectedDecision}, got ${verdict.decision}`;
  if (verdict.reasonCode !== value.expectedReason) return `expected ${value.expectedReason}, got ${verdict.reasonCode}`;
  return null;
}

export async function loadClassifierCases(): Promise<LoadedClassifierCase[]> {
  const fixture = await loadClassifierManifest();
  const cases: LoadedClassifierCase[] = [];
  for (const value of fixture.cases) {
    const body = new URL(`../fixtures/${value.transcript}`, import.meta.url);
    const inputs = JSON.parse(await readFile(body, "utf8")) as ClassifierCaseInputs;
    cases.push({ ...value, inputs });
  }
  return cases;
}
