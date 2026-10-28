#!/usr/bin/env node
import { createHash } from "node:crypto";
import { mkdir, readFile, readdir, rename, writeFile } from "node:fs/promises";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { DatabaseSync } from "node:sqlite";

const WINDOW_MS = Number(process.env.AGENTCI_MINER_WINDOW_MS ?? 300000);
const LIMIT = Number(process.env.AGENTCI_MINER_LIMIT ?? 500);
const NON_CLASSIFIER_LIMIT = 5;
const DRY_RUN = process.argv.includes("--dry-run");
const REBUILD = process.argv.includes("--rebuild");
const SINCE = readSince();
const CLASSIFIER_FIXTURE = fileURLToPath(new URL("../tests/fixtures/classifier-cases.json", import.meta.url));
const OPERATOR_FIXTURE = fileURLToPath(new URL("../tests/fixtures/operator-cases.json", import.meta.url));
const REDUCER_FIXTURE = fileURLToPath(new URL("../tests/fixtures/reducer-cases.json", import.meta.url));
const LEDGER_FIXTURE = fileURLToPath(new URL("../tests/fixtures/source-ledger.json", import.meta.url));
const TRANSCRIPTS_DIR = fileURLToPath(new URL("../tests/fixtures/transcripts/", import.meta.url));
const SQL_DIR = fileURLToPath(new URL("../../sql/", import.meta.url));
const MARKER = "Automated Moderation:";
const CONTINUE_DECISIONS = new Set(["AGENT_CONTINUING", "AGENT_STALLED"]);
const STOP_DECISIONS = new Set(["AGENT_BLOCKED", "AGENT_COMPLETE", "AGENT_STOPPED"]);
const IGNORED_TYPES = new Set(["moderation-escalated", "root-handoff", "blocker-discussion", "moderation-error", "REPLAY"]);
const PAYLOAD_FREE = new Set(["STATUS_BUSY", "STATUS_IDLE", "COMPACTION_STARTED", "COMPACTION_AUTOCONTINUE", "COMPACTION_COMPLETED", "CONTINUATION_PERSISTED", "BUSY_VERIFIED", "CONTINUATION_TIMEOUT"]);

function readSince() {
  const index = process.argv.indexOf("--since");
  if (index < 0) return 0;
  const value = process.argv[index + 1];
  const parsed = value ? Date.parse(value) : NaN;
  if (!Number.isFinite(parsed)) throw new Error("--since requires an ISO timestamp");
  return parsed;
}

async function sqlSource(name) {
  return (await readFile(join(SQL_DIR, name), "utf8")).trim();
}

const SQL = {
  sessionExists: await sqlSource("oc_agentci_session_exists.sql"),
  messageData: await sqlSource("oc_agentci_message_data.sql"),
  messageParts: await sqlSource("oc_agentci_message_parts.sql"),
  userMessagesBefore: await sqlSource("oc_agentci_user_messages_before.sql"),
  abortedMessages: await sqlSource("oc_agentci_aborted_messages.sql"),
  assistantSeq: await sqlSource("oc_agentci_assistant_seq.sql"),
  removalAfter: await sqlSource("oc_agentci_removal_after.sql"),
  removalParts: await sqlSource("oc_agentci_removal_parts.sql"),
};

function stateRoot() {
  const base = process.env.XDG_STATE_HOME && process.env.XDG_STATE_HOME.length > 0
    ? process.env.XDG_STATE_HOME
    : join(process.env.HOME && process.env.HOME.length > 0 ? process.env.HOME : homedir(), ".local", "state");
  return join(base, "opencode", "agentci", "moderation");
}

function dataRoot() {
  const base = process.env.XDG_DATA_HOME && process.env.XDG_DATA_HOME.length > 0
    ? process.env.XDG_DATA_HOME
    : join(process.env.HOME && process.env.HOME.length > 0 ? process.env.HOME : homedir(), ".local", "share");
  return join(base, "opencode");
}

function hash(value) {
  return createHash("sha256").update(JSON.stringify(value)).digest("hex");
}

function classifierHash(value) {
  return hash({
    previousResponse: value.inputs?.previousResponse,
    userMessages: value.inputs?.userMessages ?? [],
    forbidden: [...(value.forbiddenDecisions ?? [])].sort(),
  });
}

function reducerHash(value) {
  return hash({ event: value.event, previousState: value.previousState, expected: value.expected });
}

async function readJson(path, missing) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return missing;
    throw error;
  }
}

async function writeAtomic(path, value) {
  const temporary = `${path}.tmp-${process.pid}`;
  await mkdir(dirname(path), { recursive: true });
  await writeFile(temporary, `${JSON.stringify(value, null, 2)}\n`, { encoding: "utf8", mode: 0o600 });
  await rename(temporary, path);
}

async function writeAtomicIfChanged(path, value) {
  const existing = await readJson(path, null);
  if (existing && JSON.stringify(existing) === JSON.stringify(value)) return false;
  await writeAtomic(path, value);
  return true;
}

function transcriptPath(caseHash) {
  return join(TRANSCRIPTS_DIR, `${caseHash}.json`);
}

function classifierInputs(value) {
  return {
    previousResponse: value.previousResponse ?? value.inputs?.previousResponse,
    userMessages: value.userMessages ?? value.inputs?.userMessages ?? [],
    todos: value.todos ?? value.inputs?.todos ?? [],
  };
}

function manifestOf(value) {
  const manifest = {
    id: value.id,
    provenance: value.provenance,
    expectedDecision: value.expectedDecision,
    expectedReason: value.expectedReason,
    forbiddenDecisions: value.forbiddenDecisions,
    labelSource: value.labelSource,
    hash: value.hash,
    transcript: `transcripts/${value.hash}.json`,
  };
  if (value.observed) manifest.observed = value.observed;
  return manifest;
}

async function writeBody(caseHash, inputs) {
  await writeAtomicIfChanged(transcriptPath(caseHash), inputs);
}

async function rebuildBodies(manifest, shards) {
  const cache = new Map();
  let written = 0;
  for (const value of manifest.cases ?? []) {
    if (value.labelSource === "operator") {
      const inputs = classifierInputs(value);
      const computed = classifierHash({ inputs, forbiddenDecisions: value.forbiddenDecisions });
      if (computed !== value.hash) throw new Error(`classifier case ${value.id}: operator hash does not match its inputs`);
      await writeBody(value.hash, inputs);
      written += 1;
      continue;
    }
    const sessionID = value.provenance?.sessionID;
    const assistantID = value.provenance?.assistantID;
    if (!sessionID || !assistantID) throw new Error(`classifier case ${value.id} has no provenance to rebuild from`);
    const db = databaseFor(shards, cache, sessionID);
    if (!db) throw new Error(`classifier case ${value.id} has no shard database for session ${sessionID}`);
    const found = textOf(db, assistantID);
    if (!found || found.text.length === 0) throw new Error(`classifier case ${value.id} has no assistant transcript`);
    const inputs = { previousResponse: found.text, userMessages: userPromptsBefore(db, sessionID, found.info.time?.created ?? 0), todos: [] };
    const computed = hash({ previousResponse: inputs.previousResponse, userMessages: inputs.userMessages, forbidden: [...value.forbiddenDecisions].sort() });
    if (computed !== value.hash) throw new Error(`classifier case ${value.id}: rebuilt transcript hash does not match the manifest`);
    await writeBody(value.hash, inputs);
    written += 1;
  }
  for (const db of cache.values()) db.close();
  return written;
}

async function auditSessions() {
  const root = stateRoot();
  let entries;
  try {
    entries = await readdir(root, { withFileTypes: true });
  } catch (error) {
    if (error.code === "ENOENT") return [];
    throw error;
  }
  const sessions = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    const directory = join(root, entry.name);
    const files = (await readdir(directory)).filter((name) => name.startsWith("decision-") && name.endsWith(".yaml"));
    files.sort();
    const records = [];
    for (const file of files) {
      const record = await readJson(join(directory, file), null);
      if (record && typeof record.timestamp === "string") records.push(record);
    }
    sessions.push({ sessionID: entry.name, records });
  }
  return sessions;
}

function shardDatabases() {
  const root = dataRoot();
  return readdir(root).then((names) => names.filter((name) => name.startsWith("shard-") && name.endsWith(".db")).map((name) => join(root, name)));
}

function openDatabase(path) {
  return new DatabaseSync(path, { readOnly: true });
}

function databaseFor(shards, cache, sessionID) {
  const existing = cache.get(sessionID);
  if (existing) return existing;
  for (const path of shards) {
    const db = openDatabase(path);
    const row = db.prepare(SQL.sessionExists).get(sessionID);
    if (row) {
      cache.set(sessionID, db);
      return db;
    }
    db.close();
  }
  return null;
}

function textOf(db, messageID) {
  const row = db.prepare(SQL.messageData).get(messageID);
  if (!row) return null;
  const info = JSON.parse(row.data);
  const parts = db.prepare(SQL.messageParts).all(messageID).map((part) => JSON.parse(part.data));
  const synthetic = parts.some((part) => part.synthetic === true);
  const text = parts
    .filter((part) => part.type === "text" && part.synthetic !== true && typeof part.text === "string")
    .map((part) => part.text)
    .join("\n")
    .trim();
  return { info, text, synthetic };
}

function injected(text) {
  return text.includes(MARKER);
}

function userPromptsBefore(db, sessionID, before) {
  const rows = db.prepare(SQL.userMessagesBefore).all(sessionID, before);
  const prompts = [];
  for (const row of rows) {
    const info = JSON.parse(row.data);
    if (info.role !== "user") continue;
    const found = textOf(db, row.id);
    if (!found || found.synthetic || found.text.length === 0 || injected(found.text)) continue;
    prompts.unshift(found.text);
    if (prompts.length === 3) break;
  }
  return prompts;
}

function signalAfter(db, sessionID, timestamp) {
  const end = timestamp + WINDOW_MS;
  const aborted = db.prepare(SQL.abortedMessages).all(sessionID, timestamp, end)
    .find((row) => JSON.parse(row.data).role === "assistant" && JSON.parse(row.data).error?.name === "MessageAbortedError");
  return aborted ? "aborted" : null;
}

function rulingRemoved(text, decision) {
  if (!text.includes(MARKER)) return false;
  if (decision === "AGENT_COMPLETE") return text.includes("work completion verified");
  if (decision === "AGENT_BLOCKED") return text.includes("awaiting user input") || text.includes("operator action required");
  return false;
}

function assistantSeq(db, sessionID, assistantID) {
  const row = db.prepare(SQL.assistantSeq).get(sessionID, assistantID);
  return row && typeof row.seq === "number" ? row.seq : 0;
}

function removalAfter(db, sessionID, seq) {
  const row = db.prepare(SQL.removalAfter).get(sessionID, seq);
  if (!row || !row.messageID) return null;
  const parts = db.prepare(SQL.removalParts).all(sessionID, row.messageID);
  const text = parts.map((part) => JSON.parse(part.data).part.text).filter((value) => typeof value === "string").join("\n").trim();
  return text;
}

function classifierCase(sessionID, record, db) {
  const assistantID = record.previousState?.inflightAssistantID ?? record.assistantID ?? null;
  if (!assistantID) return null;
  const timestamp = Date.parse(record.timestamp);
  if (!Number.isFinite(timestamp) || timestamp < SINCE) return null;
  const found = textOf(db, assistantID);
  if (!found || found.text.length === 0) return null;
  const decision = record.verdict?.decision;
  const reasonCode = record.verdict?.reasonCode;
  if (typeof decision !== "string" || typeof reasonCode !== "string") return null;
  const continuationSent = Array.isArray(record.effectResults) && record.effectResults.some((result) => result.effect === "SEND_CONTINUATION" && result.status === "ok");
  let forbidden = null;
  if (CONTINUE_DECISIONS.has(decision) && continuationSent) forbidden = ["AGENT_CONTINUING", "AGENT_STALLED"];
  else if (STOP_DECISIONS.has(decision)) forbidden = [decision];
  if (!forbidden) return null;
  const userMessages = userPromptsBefore(db, sessionID, found.info.time?.created ?? timestamp);
  if (userMessages.length === 0) return null;
  const observed = signalAfter(db, sessionID, timestamp);
  let signal = CONTINUE_DECISIONS.has(decision) && observed === "aborted" ? observed : null;
  if (!signal && (decision === "AGENT_COMPLETE" || decision === "AGENT_BLOCKED")) {
    const removed = removalAfter(db, sessionID, assistantSeq(db, sessionID, assistantID));
    if (removed && rulingRemoved(removed, decision)) signal = "removed";
  }
  if (!signal) return null;
  const caseHash = hash({ previousResponse: found.text, userMessages, forbidden: [...forbidden].sort() });
  return {
    id: `mined-${caseHash.slice(0, 16)}`,
    provenance: { sessionID, assistantID, decisionID: record.decisionID ?? null },
    inputs: { previousResponse: found.text, userMessages, todos: [] },
    expectedDecision: null,
    expectedReason: null,
    forbiddenDecisions: forbidden,
    observed: { decision, reasonCode, signal, source: "transcript" },
    labelSource: "mined",
    hash: caseHash,
  };
}

function currentState(state) {
  if (!state || typeof state !== "object") return false;
  if ("busyGeneration" in state || "pendingIdleGenerations" in state) return false;
  if (state.compaction && "generation" in state.compaction) return false;
  if (state.blocker && !["operator-handoff", "agent-blocked"].includes(state.blocker.source)) return false;
  return true;
}

function reducerCase(sessionID, record) {
  if (!record.previousState || !currentState(record.previousState)) return null;
  if (record.event === "CLASSIFIER_RESULT") return null;
  const isIgnored = record.ignored === true || String(record.decisionType ?? "").startsWith("ignored-") || IGNORED_TYPES.has(record.decisionType);
  if (!isIgnored) return null;
  const timestamp = Date.parse(record.timestamp);
  if (!Number.isFinite(timestamp) || timestamp < SINCE) return null;
  const event = record.eventPayload ?? (PAYLOAD_FREE.has(record.event) ? { type: record.event } : null);
  if (!event) return null;
  const expected = { ignored: record.ignored === true, nextPhase: record.nextPhase, decisionType: record.decisionType };
  const caseHash = hash({ event, previousState: record.previousState, expected });
  return {
    id: `reducer-${caseHash.slice(0, 16)}`,
    provenance: { sessionID, decisionID: record.decisionID ?? null },
    event,
    previousState: record.previousState,
    expected,
    hash: caseHash,
  };
}

function merge(existing, discovered, limit, hashOf) {
  const seen = new Set();
  const cases = [];
  for (const value of existing.cases ?? []) {
    const key = value.hash ?? hashOf(value);
    if (seen.has(key)) continue;
    seen.add(key);
    cases.push({ ...value, hash: key });
  }
  const added = [];
  const ordered = [...discovered].sort((left, right) => left.hash.localeCompare(right.hash));
  for (const value of ordered) {
    if (cases.length >= limit) break;
    if (seen.has(value.hash)) continue;
    seen.add(value.hash);
    cases.push(value);
    added.push(value);
  }
  cases.sort((left, right) => left.hash.localeCompare(right.hash));
  return { document: { version: 1, cases }, added };
}

const operatorDocument = await readJson(OPERATOR_FIXTURE, { version: 1, cases: [] });
const operatorCases = (operatorDocument.cases ?? []).map((value) => ({ ...value, hash: classifierHash(value) }));
const manifestDocument = await readJson(CLASSIFIER_FIXTURE, { version: 1, cases: [] });
const classifierExisting = { version: 1, cases: [...(manifestDocument.cases ?? []).filter((value) => value.labelSource !== "operator"), ...operatorCases] };
const reducerExisting = await readJson(REDUCER_FIXTURE, { version: 1, cases: [] });
const ledger = await readJson(LEDGER_FIXTURE, { version: 1, seenDecisionIDs: [] });
const seenDecisionIDs = new Set(ledger.seenDecisionIDs ?? []);
const shards = await shardDatabases();
if (REBUILD) {
  if (DRY_RUN) throw new Error("--rebuild and --dry-run are mutually exclusive");
  const written = await rebuildBodies(classifierExisting, shards);
  console.log(`rebuilt transcript bodies: ${written}`);
  process.exit(0);
}
const cache = new Map();
const classifierDiscovered = [];
const reducerDiscovered = [];
const reducerEligible = [];
let skippedSessions = 0;

for (const session of await auditSessions()) {
  const db = databaseFor(shards, cache, session.sessionID);
  if (!db) {
    skippedSessions += 1;
    continue;
  }
  for (const record of session.records) {
    if (record.event === "CLASSIFIER_RESULT") {
      const value = classifierCase(session.sessionID, record, db);
      if (value) classifierDiscovered.push(value);
    } else {
      const value = reducerCase(session.sessionID, record);
      if (value) {
        if (record.decisionID) reducerEligible.push(record.decisionID);
        if (!seenDecisionIDs.has(record.decisionID)) reducerDiscovered.push(value);
      }
    }
  }
}

for (const db of cache.values()) db.close();

const classifierMerged = merge(classifierExisting, classifierDiscovered, LIMIT, classifierHash);
const reducerMerged = merge(reducerExisting, reducerDiscovered, Number.MAX_SAFE_INTEGER, reducerHash);
const freshReducer = reducerMerged.added.slice(0, NON_CLASSIFIER_LIMIT);

const coverage = new Map();
for (const value of classifierMerged.document.cases) {
  const key = value.expectedDecision && value.expectedReason ? `${value.expectedDecision}/${value.expectedReason}` : null;
  if (key) coverage.set(key, (coverage.get(key) ?? 0) + 1);
}
const required = ["AGENT_COMPLETE/WORK_COMPLETE", "AGENT_CONTINUING/WORK_REMAINS", "AGENT_STALLED/NO_PROGRESS", "AGENT_BLOCKED/AWAITING_USER", "AGENT_BLOCKED/AWAITING_OPERATOR", "AGENT_STOPPED/USER_STOP"];
const missing = required.filter((key) => !coverage.has(key));

if (!DRY_RUN) {
  const manifestCases = [];
  for (const value of classifierMerged.document.cases) {
    const inputs = value.inputs ?? await readJson(transcriptPath(value.hash), null);
    if (!inputs) throw new Error(`classifier case ${value.id} has no transcript body; run with --rebuild`);
    await writeBody(value.hash, classifierInputs(inputs));
    manifestCases.push(manifestOf(value));
  }
  await writeAtomicIfChanged(CLASSIFIER_FIXTURE, { version: 1, cases: manifestCases });
}
if (!DRY_RUN && freshReducer.length > 0) {
  const document = { version: 1, cases: [...(reducerExisting.cases ?? []), ...freshReducer] };
  document.cases.sort((left, right) => left.hash.localeCompare(right.hash));
  await writeAtomic(REDUCER_FIXTURE, document);
}
const newDecisionIDs = reducerEligible.filter((id) => !seenDecisionIDs.has(id));
for (const id of reducerEligible) seenDecisionIDs.add(id);
if (!DRY_RUN && newDecisionIDs.length > 0) {
  await writeAtomic(LEDGER_FIXTURE, { version: 1, seenDecisionIDs: [...seenDecisionIDs].sort() });
}

console.log(`classifier cases: added ${classifierMerged.added.length}, total ${classifierMerged.document.cases.length}`);
console.log(`reducer cases: added ${freshReducer.length} of ${reducerMerged.added.length} available, total ${(reducerExisting.cases ?? []).length + freshReducer.length}`);
console.log(`sessions skipped without a shard database: ${skippedSessions}`);
console.log(`coverage: ${[...coverage.entries()].map(([key, count]) => `${key}=${count}`).join(", ") || "none"}`);
if (missing.length > 0) console.log(`missing pathway coverage: ${missing.join(", ")}`);
if (freshReducer.length < NON_CLASSIFIER_LIMIT) console.log(`non-classifier shortage: wanted ${NON_CLASSIFIER_LIMIT}, added ${freshReducer.length}`);
if (DRY_RUN) console.log("dry run: no files written");
