import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { isValidState, transition } from "../src/moderation/machine.ts";
import type { ModerationEvent, ModerationState } from "../src/moderation/types.ts";

interface ReducerCase {
  id: string;
  provenance: { sessionID: string; decisionID: string | null };
  event: Record<string, unknown> & { type: string };
  previousState: ModerationState;
  expected: { ignored: boolean; nextPhase: string; decisionType: string };
  hash?: string;
}

interface ReducerFixture {
  version: number;
  cases: ReducerCase[];
}

const fixture = JSON.parse(await readFile(new URL("./fixtures/reducer-cases.json", import.meta.url), "utf8")) as ReducerFixture;

function caseHash(value: ReducerCase): string {
  return createHash("sha256").update(JSON.stringify({
    event: value.event,
    previousState: value.previousState,
    expected: value.expected,
  })).digest("hex");
}

test("mined reducer cases replay the recorded deterministic transition", { skip: fixture.cases.length === 0 }, () => {
  assert.equal(fixture.version, 1);
  const seen = new Set<string>();
  for (const value of fixture.cases) {
    const computed = caseHash(value);
    if (value.hash !== undefined) assert.equal(value.hash, computed, `${value.id}: stored hash is stale`);
    assert.ok(!seen.has(computed), `${value.id}: duplicate reducer case`);
    seen.add(computed);
    assert.ok(isValidState(value.previousState), `${value.id}: recorded previous state is invalid`);
    const result = transition(value.previousState, value.event as ModerationEvent);
    assert.equal(result.ignored, value.expected.ignored, `${value.id}: ignored flag drifted`);
    assert.equal(result.transition.nextPhase, value.expected.nextPhase, `${value.id}: next phase drifted`);
  }
});
