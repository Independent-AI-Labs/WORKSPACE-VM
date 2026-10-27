import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readdir } from "node:fs/promises";
import test from "node:test";
import { buildMessages, SYSTEM_PROMPT } from "../src/moderation/classifier.ts";
import { loadClassifierCases, loadClassifierManifest, type ClassifierCaseInputs, type ClassifierCaseManifest } from "./support/classifier-cases.ts";

const TRANSCRIPTS = new URL("./fixtures/transcripts/", import.meta.url);

function caseHash(value: ClassifierCaseManifest, inputs: ClassifierCaseInputs): string {
  return createHash("sha256").update(JSON.stringify({
    previousResponse: inputs.previousResponse,
    userMessages: inputs.userMessages,
    forbidden: [...value.forbiddenDecisions].sort(),
  })).digest("hex");
}

async function transcriptBodies(): Promise<string[]> {
  try {
    return (await readdir(TRANSCRIPTS)).filter((name) => name.endsWith(".json"));
  } catch (error) {
    if (typeof error === "object" && error !== null && "code" in error && (error as { code?: unknown }).code === "ENOENT") return [];
    throw error;
  }
}

test("classifier case manifest has unique content hashes and transcript references", async () => {
  const fixture = await loadClassifierManifest();
  assert.equal(fixture.version, 1);
  assert.ok(fixture.cases.length > 0, "expected at least one classifier case");
  const seen = new Set<string>();
  for (const value of fixture.cases) {
    assert.equal(typeof value.id, "string");
    assert.ok(value.labelSource === "operator" || value.labelSource === "mined");
    assert.equal(typeof value.hash, "string", `${value.id}: missing hash`);
    assert.equal(value.transcript, `transcripts/${value.hash}.json`, `${value.id}: transcript reference must match the hash`);
    assert.ok(!seen.has(value.hash), `${value.id}: duplicate case content`);
    seen.add(value.hash);
  }
});

test("classifier case manifest covers every decision and reason pair", async () => {
  const fixture = await loadClassifierManifest();
  const covered = new Set<string>();
  for (const value of fixture.cases) {
    if (value.expectedDecision && value.expectedReason) covered.add(`${value.expectedDecision}/${value.expectedReason}`);
  }
  const required = [
    "AGENT_COMPLETE/WORK_COMPLETE",
    "AGENT_CONTINUING/WORK_REMAINS",
    "AGENT_STALLED/NO_PROGRESS",
    "AGENT_BLOCKED/AWAITING_USER",
    "AGENT_BLOCKED/AWAITING_OPERATOR",
    "AGENT_STOPPED/USER_STOP",
  ];
  for (const pair of required) assert.ok(covered.has(pair), `missing pathway coverage: ${pair}`);
});

test("mined cases constrain the verdict and carry provenance", async () => {
  const fixture = await loadClassifierManifest();
  const mined = fixture.cases.filter((value) => value.labelSource === "mined");
  assert.ok(mined.length > 0, "expected at least one mined case");
  for (const value of mined) {
    assert.ok(value.forbiddenDecisions.length > 0, `${value.id}: mined case has no forbidden decision`);
    assert.equal(value.expectedDecision, null, `${value.id}: mined case must not assert an unverified exact decision`);
    assert.ok(value.provenance.sessionID, `${value.id}: mined case has no session provenance`);
  }
});

test("every present transcript body matches its manifest hash and layout", async (t) => {
  const bodies = await transcriptBodies();
  if (bodies.length === 0) {
    t.skip("no local transcript bodies; run npm run source-cases -- --rebuild");
    return;
  }
  const cases = await loadClassifierCases();
  assert.equal(bodies.length, cases.length, "every manifest case must have exactly one transcript body");
  assert.match(SYSTEM_PROMPT, /The agent's latest response is the decision target\./);
  for (const value of cases) {
    assert.equal(caseHash(value, value.inputs), value.hash, `${value.id}: transcript body does not match the manifest hash`);
    const content = buildMessages({ todos: value.inputs.todos, previousResponse: value.inputs.previousResponse, userMessages: value.inputs.userMessages })[1].content;
    const responseIndex = content.indexOf("The agent's latest response (judge this):");
    const requestIndex = content.indexOf("User request(s):");
    assert.ok(responseIndex >= 0, `${value.id}: missing response section`);
    assert.ok(responseIndex < requestIndex, `${value.id}: response must precede the user requests`);
    assert.ok(content.includes(value.inputs.previousResponse), `${value.id}: response text missing from the request`);
  }
});
