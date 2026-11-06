import { readFileSync } from "node:fs";

const path = process.argv[2];
if (path === undefined) throw new Error("model path is required");
const parsed = JSON.parse(readFileSync(path, "utf8"));
if (!Array.isArray(parsed.models) || parsed.models.length === 0) throw new Error("models array is empty");
for (const entry of parsed.models) {
  if (typeof entry.providerID !== "string" || entry.providerID.length === 0) throw new Error("providerID is missing");
  if (typeof entry.modelID !== "string" || entry.modelID.length === 0) throw new Error("modelID is missing");
}
