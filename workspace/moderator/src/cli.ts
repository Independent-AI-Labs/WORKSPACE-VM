import { validateAgainstConfig, readOpenCodeConfig } from "./config.ts";
import { parseSelectorList, readModels, writeModels, modelsPath } from "./model-select.ts";

async function main(argv: readonly string[]): Promise<void> {
  const command = argv[0];
  if (command === "models" && argv[1] === "set") {
    const value = argv[2];
    if (value === undefined) throw new Error("models set requires provider/model[,provider/model...]");
    const models = parseSelectorList(value);
    validateAgainstConfig(models, await readOpenCodeConfig());
    await writeModels(models);
    process.stdout.write(`${models.map((model) => `${model.providerID}/${model.modelID}`).join(",")}\n`);
    return;
  }
  if (command === "models" && argv[1] === "show") {
    const models = await readModels();
    process.stdout.write(`${models.map((model) => `${model.providerID}/${model.modelID}`).join(",")}\n`);
    return;
  }
  throw new Error(`usage: cli.js models show | models set <list>\nmodel source: ${modelsPath()}`);
}

main(process.argv.slice(2)).catch((error: unknown) => {
  process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
  process.exitCode = 1;
});
