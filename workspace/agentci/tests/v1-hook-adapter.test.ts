import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createV1HookAdapter } from "../src/v1-hook-adapter.ts";
import { loadPolicies } from "../src/policies.ts";

test("policy files drive block, warn, and inject behavior", async () => {
  await withPolicies(`
policies:
  - name: block-force-push
    event: tool.execute.before
    match:
      tool: bash
      command_regex: 'git push --force'
    action: block
    message: Force push is configured as blocked for this session.
  - name: warn-failed-gate
    event: tool.execute.after
    match:
      tool: bash
      command_regex: '^git (commit|push)'
      exit: nonzero
    action: warn
    message: Fix the failing gate and rerun it.
  - name: inject-guide
    event: experimental.chat.system.transform
    match:
      file: guide.md
    action: inject
    message: Session guidance.
`, { "guide.md": "Use approved interfaces.\n" }, async (directory) => {
    const policies = await loadPolicies([join(directory, "policies.yaml")]);
    const hooks = createV1HookAdapter(policies);

    await assert.rejects(
      hooks["tool.execute.before"]({ tool: "bash", sessionID: "ses-1", callID: "c1" }, { args: { command: "git push --force origin main" } }),
      /block-force-push/,
    );
    await hooks["tool.execute.before"]({ tool: "bash", sessionID: "ses-1", callID: "c2" }, { args: { command: "git push origin main" } });

    const failed = { title: "Bash", output: "hook failed", metadata: { exit: 1 } };
    await hooks["tool.execute.after"]({ tool: "bash", sessionID: "ses-1", callID: "c3", args: { command: "git commit -m ready" } }, failed);
    assert.match(failed.output, /AgentCI \(warn-failed-gate\): Fix the failing gate and rerun it\./);
    const passed = { title: "Bash", output: "ok", metadata: { exit: 0 } };
    await hooks["tool.execute.after"]({ tool: "bash", sessionID: "ses-1", callID: "c4", args: { command: "git commit -m ready" } }, passed);
    assert.equal(passed.output, "ok");

    for (const _turn of [1, 2]) {
      const system = { system: [] as string[] };
      await hooks["experimental.chat.system.transform"]({ sessionID: "ses-1" }, system);
      assert.equal(system.system.filter((entry) => entry.includes("Use approved interfaces.")).length, 1);
    }
  });
});

test("invalid policies reject startup", async () => {
  await withPolicies(`
policies:
  - name: bad-action
    event: tool.execute.after
    match: {}
    action: block
    message: Invalid combination.
`, {}, async (directory) => {
    await assert.rejects(loadPolicies([join(directory, "policies.yaml")]), /action 'block' is not valid for tool.execute.after/);
  });
  await withPolicies(`
policies:
  - name: duplicate
    event: tool.execute.before
    match: {}
    action: warn
    message: First.
  - name: duplicate
    event: tool.execute.before
    match: {}
    action: warn
    message: Second.
`, {}, async (directory) => {
    await assert.rejects(loadPolicies([join(directory, "policies.yaml")]), /unique/);
  });
  await withPolicies(`
policies:
  - name: unknown-field
    event: tool.execute.before
    match: {}
    action: warn
    message: Extra.
    priority: 5
`, {}, async (directory) => {
    await assert.rejects(loadPolicies([join(directory, "policies.yaml")]), /unknown field 'priority'/);
  });
});

test("missing inject file is a visible error without substitution", async () => {
  await withPolicies(`
policies:
  - name: inject-guide
    event: experimental.chat.system.transform
    match:
      file: missing.md
    action: inject
    message: Session guidance.
`, {}, async (directory) => {
    const policies = await loadPolicies([join(directory, "policies.yaml")]);
    const hooks = createV1HookAdapter(policies);
    await assert.rejects(hooks["experimental.chat.system.transform"]({ sessionID: "ses-1" }, { system: [] }), /ENOENT/);
  });
});

async function withPolicies(yaml: string, files: Record<string, string>, body: (directory: string) => Promise<void>): Promise<void> {
  const directory = await mkdtemp(join(tmpdir(), "agentci-policy-test-"));
  try {
    await writeFile(join(directory, "policies.yaml"), yaml);
    for (const [name, content] of Object.entries(files)) await writeFile(join(directory, name), content);
    await body(directory);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
}
