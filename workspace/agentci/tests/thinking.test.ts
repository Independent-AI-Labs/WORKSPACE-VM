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
  const previous = process.env.OC_THINKING_EFFORT;
  try {
    process.env.OC_THINKING_EFFORT = "low";
    const output: { options?: Record<string, unknown> } = { options: { existing: true } };
    applyThinkingEffort({ model: { variants: LADDER } }, output);
    assert.deepEqual(output.options, { existing: true, reasoningEffort: "low" });

    const empty: { options?: Record<string, unknown> } = {};
    applyThinkingEffort({ model: { variants: { high: {}, max: {} } } }, empty);
    assert.deepEqual(empty.options, { reasoningEffort: "high" });

    const unsupported: { options?: Record<string, unknown> } = {};
    applyThinkingEffort({ model: { variants: {} } }, unsupported);
    assert.deepEqual(unsupported, {});
  } finally {
    if (previous === undefined) delete process.env.OC_THINKING_EFFORT;
    else process.env.OC_THINKING_EFFORT = previous;
  }
});
