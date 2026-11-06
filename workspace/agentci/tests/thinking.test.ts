import test from "node:test";
import assert from "node:assert/strict";
import { applyThinkingEffort, chooseEffort, requestedEffort } from "../src/thinking.ts";

const LADDER = { minimal: {}, low: {}, medium: {}, high: {}, max: {}, xhigh: {}, none: {}, off: {} };

test("chooseEffort prefers the requested variant when the model defines it", () => {
  assert.equal(chooseEffort("low", { high: {}, max: {} }), "high");
  assert.equal(chooseEffort("low", LADDER), "low");
  assert.equal(chooseEffort("medium", LADDER), "medium");
});

test("chooseEffort falls back to the minimum non-off variant", () => {
  assert.equal(chooseEffort("low", { high: {}, max: {} }), "high");
  assert.equal(chooseEffort("low", { max: {} }), "max");
  assert.equal(chooseEffort("low", { medium: {}, high: {} }), "medium");
  assert.equal(chooseEffort("low", { none: {} }), null);
  assert.equal(chooseEffort("low", {}), null);
  assert.equal(chooseEffort("low", undefined), null);
});

test("requestedEffort uses low and refuses off", () => {
  assert.equal(requestedEffort(undefined), "low");
  assert.equal(requestedEffort(""), "low");
  assert.equal(requestedEffort("none"), "low");
  assert.equal(requestedEffort("off"), "low");
  assert.equal(requestedEffort("high"), "high");
});

test("applyThinkingEffort writes the chosen effort into provider options", () => {
  const output: { options?: Record<string, unknown> } = { options: { existing: true } };
  applyThinkingEffort({ model: { variants: LADDER } }, output, "low");
  assert.deepEqual(output.options, { existing: true, reasoningEffort: "low" });

  const empty: { options?: Record<string, unknown> } = {};
  applyThinkingEffort({ model: { variants: { high: {}, max: {} } } }, empty, "low");
  assert.deepEqual(empty.options, { reasoningEffort: "high" });

  const unsupported: { options?: Record<string, unknown> } = {};
  applyThinkingEffort({ model: { variants: {} } }, unsupported, "low");
  assert.deepEqual(unsupported, {});
});
