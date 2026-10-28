import { statusLine, isSessionID, loadMessages, type ModerationClient } from "./adapter.ts";
import { sessionDirectory, writeDecisionRecord } from "./audit.ts";
import type { FetchLike } from "./classifier.ts";
import type { ModerationOptions } from "./config.ts";
import { assistantText, isInjectedUser, lastRealUserPrompts } from "./context.ts";
import { resolveVerdict } from "./verdict.ts";
import type { MessageFact, TodoFact, Verdict, VerdictDecision } from "./types.ts";

const REPLAY_READY_ATTEMPTS = 40;
const REPLAY_READY_INTERVAL_MS = 250;
const REPLAY_TOAST_MS = 2000;

export interface ReplaySessionSummary {
  id: string;
  time: { updated: number };
}

export interface ReplayClient extends ModerationClient {
  session: ModerationClient["session"] & {
    revert(input: { path: { id: string }; body: { messageID: string; partID?: string } }): Promise<unknown>;
    list(input?: { query?: { directory?: string } }): Promise<{ data?: ReplaySessionSummary[] }>;
  };
}

export interface ReplayInput {
  client: ReplayClient;
  options: ModerationOptions;
  sessionID: string;
  fetchImpl?: FetchLike;
}

export interface ReplayResult {
  sessionID: string;
  revertedMessageID: string | null;
  decision: VerdictDecision;
  decisionType: string;
}

interface ReplayTarget {
  assistant: MessageFact;
  moderatorMessageID: string | null;
}

export async function resolveReplaySession(client: ReplayClient, explicit?: string): Promise<string> {
  if (explicit !== undefined && explicit.length > 0) {
    if (!isSessionID(explicit)) throw new Error(`AgentCI replay received an invalid session id '${explicit}'`);
    return explicit;
  }
  const sessions = (await client.session.list()).data ?? [];
  let newest: ReplaySessionSummary | null = null;
  for (const session of sessions) {
    if (!isSessionID(session.id)) continue;
    if (newest === null || session.time.updated > newest.time.updated) newest = session;
  }
  if (newest === null) throw new Error("AgentCI replay found no moderated session to replay");
  return newest.id;
}

export async function replayLastDecision(input: ReplayInput): Promise<ReplayResult> {
  const messages = await loadMessages(input.client, input.sessionID);
  const todos: readonly TodoFact[] = (await input.client.session.todo({ path: { id: input.sessionID } })).data ?? [];
  const target = selectReplayTarget(messages);
  if (target === null) throw new Error("AgentCI replay found no completed assistant response to re-moderate");
  if (target.moderatorMessageID !== null) {
    await input.client.session.revert({ path: { id: input.sessionID }, body: { messageID: target.moderatorMessageID } });
  }
  const outcome = await resolveVerdict(
    input.options,
    { todos, previousResponse: assistantText(target.assistant), userMessages: lastRealUserPrompts(messages) },
    input.fetchImpl ?? fetch,
  );
  if (outcome.error) throw new Error(outcome.error);
  if (!outcome.verdict) throw new Error("AgentCI replay classifier returned no verdict");
  const verdict = outcome.verdict;
  const decisionType = replayDecisionType(verdict.decision);
  const effects = await applyReplay(input, verdict);
  await writeDecisionRecord(sessionDirectory(input.sessionID), {
    event: "REPLAY",
    decisionType,
    verdict,
    revertedMessageID: target.moderatorMessageID,
    effects,
  });
  return { sessionID: input.sessionID, revertedMessageID: target.moderatorMessageID, decision: verdict.decision, decisionType };
}

export async function runReplay(client: ReplayClient, options: ModerationOptions, explicit?: string): Promise<void> {
  let sessionID: string | null = null;
  try {
    sessionID = await resolveReplaySession(client, explicit);
    await awaitSessionReady(client, sessionID);
    await replayLastDecision({ client, options, sessionID });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (sessionID !== null) {
      await writeDecisionRecord(sessionDirectory(sessionID), { event: "REPLAY", decisionType: "moderation-error", error: message });
    }
    await showReplayToast(client, `AgentCI replay failed: ${message}`);
  }
}

export function replayDecisionType(decision: VerdictDecision): string {
  if (decision === "AGENT_COMPLETE") return "moderation-complete";
  if (decision === "AGENT_BLOCKED") return "moderation-agent-blocked";
  if (decision === "AGENT_STOPPED") return "moderation-user-stop";
  return "moderation-continue";
}

function selectReplayTarget(messages: readonly MessageFact[]): ReplayTarget | null {
  let moderatorIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (isInjectedUser(messages[index])) {
      moderatorIndex = index;
      break;
    }
  }
  const upper = moderatorIndex >= 0 ? moderatorIndex : messages.length;
  let assistant: MessageFact | undefined;
  for (let index = upper - 1; index >= 0; index -= 1) {
    if (messages[index].info.role === "assistant") {
      assistant = messages[index];
      break;
    }
  }
  if (!assistant || assistantText(assistant).length === 0) return null;
  const moderatorMessageID = moderatorIndex >= 0 ? messages[moderatorIndex].info.id ?? null : null;
  return { assistant, moderatorMessageID };
}

async function applyReplay(input: ReplayInput, verdict: Verdict): Promise<Record<string, unknown>[]> {
  const text = statusLine(verdict.decision, verdict.reasonCode);
  if (verdict.decision === "AGENT_CONTINUING" || verdict.decision === "AGENT_STALLED") {
    await input.client.session.promptAsync({ path: { id: input.sessionID }, body: { parts: [{ type: "text", text }] } });
    return [{ effect: "SEND_CONTINUATION", status: "ok" }];
  }
  if (verdict.decision === "AGENT_STOPPED") {
    await showReplayToast(input.client, text);
    return [{ effect: "SHOW_TOAST", status: "ok" }];
  }
  await input.client.session.prompt({ path: { id: input.sessionID }, body: { noReply: true, parts: [{ type: "text", text }] } });
  return [{ effect: "WRITE_TRACE", status: "ok" }];
}

async function awaitSessionReady(client: ReplayClient, sessionID: string): Promise<void> {
  for (let attempt = 0; attempt < REPLAY_READY_ATTEMPTS; attempt += 1) {
    try {
      await client.session.messages({ path: { id: sessionID }, query: { limit: 1 } });
      return;
    } catch (error) {
      if (attempt + 1 === REPLAY_READY_ATTEMPTS) throw error;
      await sleep(REPLAY_READY_INTERVAL_MS);
    }
  }
}

async function showReplayToast(client: ReplayClient, message: string): Promise<void> {
  await Promise.race([
    client.tui.showToast({ body: { title: "AgentCI moderation: replay", message, variant: "info", duration: REPLAY_TOAST_MS } }),
    sleep(REPLAY_TOAST_MS),
  ]);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => { setTimeout(resolve, ms); });
}