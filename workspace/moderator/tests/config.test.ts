import test from "node:test";
import assert from "node:assert/strict";
import { modelDisplayName, stripJsonComments, validateAgainstConfig, validateAgainstProviders } from "../src/config.ts";
import { parseModels, parseSelectorList } from "../src/model-select.ts";

test("display name comes from the provider model name", () => {
  const name = modelDisplayName({ provider: { p: { models: { one: { name: "GPT-6 Luna" } } } } }, "p/one");
  assert.equal(name, "GPT-6 Luna");
});

test("selector list parses provider and model pairs", () => {
  const models = parseSelectorList("p/one,p/two");
  assert.deepEqual(models, [{ providerID: "p", modelID: "one" }, { providerID: "p", modelID: "two" }]);
});

test("selector list rejects duplicates", () => {
  assert.throws(() => parseSelectorList("p/one,p/one"), /duplicate/);
});

test("model source rejects an empty list", () => {
  assert.throws(() => parseModels({ models: [] }), /non-empty/);
});

test("jsonc stripping keeps strings and removes comments", () => {
  const text = stripJsonComments(`{"url":"https://x//y","models":["a",],}`);
  assert.equal(JSON.parse(text).url, "https://x//y");
  assert.deepEqual(JSON.parse(text).models, ["a"]);
});

test("provider validation rejects absent selectors", () => {
  assert.throws(() => validateAgainstProviders([{ providerID: "p", modelID: "missing" }], [{ id: "p", models: { one: {} } }]), /not available/);
});

test("config validation accepts present selectors", () => {
  const result = validateAgainstConfig([{ providerID: "p", modelID: "one" }], { provider: { p: { models: { one: {} } } } });
  assert.equal(result.length, 1);
});
