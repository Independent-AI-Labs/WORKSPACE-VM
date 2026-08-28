import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { promisify } from "node:util";
import test from "node:test";

const run = promisify(execFile);
const root = dirname(dirname(new URL(import.meta.url).pathname));

test("temporary package installation exposes the OpenCode server entrypoint", async (context) => {
  const directory = await mkdtemp(join(tmpdir(), "agentci-release-test-"));
  try {
    const artifact = join(directory, "artifact");
    const installation = join(directory, "installation");
    await mkdir(artifact);
    const packed = await run("npm", ["pack", "--json", "--pack-destination", artifact], { cwd: root });
    const packageFile = join(artifact, JSON.parse(packed.stdout)[0].filename);
    await run("npm", ["install", "--ignore-scripts", "--no-package-lock", "--prefix", installation, packageFile]);
    await writeFile(join(installation, "opencode.json"), JSON.stringify({ plugin: ["agentci"] }));
    await writeFile(join(installation, "policies.yaml"), "policies: []\n");
    await run(process.execPath, ["--experimental-strip-types", "--input-type=module", "--eval", [
      'import { readFile } from "node:fs/promises"',
      'const config = JSON.parse(await readFile("opencode.json", "utf8"))',
         'const plugin = (await import(config.plugin[0])).default',
          'if (plugin.id !== "agentci" || typeof plugin.server !== "function") throw new Error("server entrypoint was not discovered")',
         'const hooks = await plugin.server({}, { policies: ["policies.yaml"] })',
         'if (typeof hooks["tool.execute.before"] !== "function" || typeof hooks["tool.execute.after"] !== "function") throw new Error("server entrypoint did not compose source adapters")',
    ].join("; ")], { cwd: installation });
    assert.deepEqual(Object.keys(JSON.parse(await readFile(join(installation, "node_modules", "agentci", "package.json"), "utf8")).exports), [".", "./server"]);
  } finally {
    await rm(directory, { recursive: true, force: true });
  }
  await assert.rejects(access(directory), { code: "ENOENT" });
  context.diagnostic(`removed temporary installation ${directory}`);
});
