import assert from "node:assert/strict";
import { mkdtemp, readdir, rm, stat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { persistSnapshot, restoreSnapshot, sessionDirectory, writeDecisionRecord } from "../src/moderation/audit.ts";
import { createInitialState } from "../src/moderation/machine.ts";

test("sessionDirectory rejects path traversal", () => {
  assert.throws(() => sessionDirectory("../../etc"), /invalid session id/);
  assert.throws(() => sessionDirectory("a/b"), /invalid session id/);
});

test("audit records are private, append-only, and restorable", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-audit-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  try {
    const directory = sessionDirectory("ses_test01");
    await writeDecisionRecord(directory, { decisionType: "classifying" });
    await writeDecisionRecord(directory, { decisionType: "moderation-complete" });
    const records = (await readdir(directory)).filter((name) => name.startsWith("decision-") && name.endsWith(".yaml"));
    assert.equal(records.length, 2);

    const state = { ...createInitialState(), phase: "CONTINUING" as const, consecutiveNoProgressCount: 2 };
    await persistSnapshot(directory, state);
    const restored = await restoreSnapshot(directory);
    assert.equal(restored?.phase, "CONTINUING");
    assert.equal(restored?.consecutiveNoProgressCount, 2);

    const mode = (await stat(directory)).mode & 0o777;
    assert.equal(mode, 0o700);
    const fileMode = (await stat(join(directory, "state.yaml"))).mode & 0o777;
    assert.equal(fileMode, 0o600);
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});

test("restoreSnapshot returns null when no snapshot exists", async () => {
  const home = await mkdtemp(join(tmpdir(), "agentci-audit-none-"));
  const previous = process.env.XDG_STATE_HOME;
  process.env.XDG_STATE_HOME = home;
  try {
    assert.equal(await restoreSnapshot(sessionDirectory("ses_missing")), null);
  } finally {
    if (previous === undefined) delete process.env.XDG_STATE_HOME;
    else process.env.XDG_STATE_HOME = previous;
    await rm(home, { recursive: true, force: true });
  }
});