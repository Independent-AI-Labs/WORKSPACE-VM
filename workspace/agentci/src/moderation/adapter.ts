import { loadPrompt, type FetchLike } from "./classifier.ts";
import { deriveContext, inBranch, isInjectedUser, isSyntheticUser, newestAssistant, realUserAncestor } from "./context.ts";
import { resolveVerdict } from "./verdict.ts";
import type { ModerationOptions } from "./config.ts";
import { persistSnapshot, restoreSnapshot, sessionDirectory, writeDecisionRecord } from "./audit.ts";
import { createInitialState, isValidState, normalizeRestoredState, transition } from "./machine.ts";
import type { ContextSnapshot, Effect, MessageFact, ModerationEvent, ModerationState, ReasonCode, TodoFact, TransitionResult, Verdict, VerdictDecision } from "./types.ts";

const CONTINUATION_LINE = loadPrompt("continuation.txt").trimEnd();
const CONTINUATION_NOTE = loadPrompt("continuation-note.txt").trimEnd();
const OPERATOR_LINE = loadPrompt("operator.txt").trimEnd();
const STATUS_INSTRUCTION = loadPrompt("status-protocol.txt").trimEnd();
const CONTEXT_TIMEOUT_MS = 15000;
const BUSY_POLL_ATTEMPTS = 50;
const BUSY_POLL_INTERVAL_MS = 100;
const CONTINUATION_VERIFY_ATTEMPTS = 15;

export function statusLine(decision: VerdictDecision, reasonCode: ReasonCode): string {
  if (decision === "AGENT_COMPLETE") return "✅ Automated Moderation: work completion verified.";
  if (decision === "AGENT_BLOCKED") {
    return reasonCode === "AWAITING_USER"
      ? "❔ Automated Moderation: awaiting user input."
      : OPERATOR_LINE;
  }
  if (decision === "AGENT_STOPPED") return "⏹️ Automated Moderation: halt acknowledged; automation stood down.";
  return CONTINUATION_LINE;
}

export interface TodoCall {
  data?: TodoFact[];
}

export interface MessagesCall {
  data?: MessageFact[];
  cursor?: { next?: string };
}

export interface PromptCall {
  data?: { info?: { id?: string } };
}

export interface ModerationClient {
  session: {
    todo(input: { path: { id: string } }): Promise<TodoCall>;
    messages(input: { path: { id: string }; query?: Record<string, unknown> }): Promise<MessagesCall>;
    prompt(input: { path: { id: string }; body: Record<string, unknown> }): Promise<PromptCall>;
    promptAsync(input: { path: { id: string }; body: Record<string, unknown> }): Promise<unknown>;
  };
  tui: {
    showToast(input: { body: Record<string, unknown> }): Promise<unknown>;
  };
}

export interface ModerationServerInput {
  client: ModerationClient;
}

interface Session {
  state: ModerationState;
  queue: ModerationEvent[];
  draining: boolean;
  busyCount: number;
  continuationBaseline: number;
  judgedAssistantID: string | null;
  moderatorMessageIDs: Set<string>;
  context: ContextSnapshot | null;
  userMessages: string[];
}

export interface ModerationAdapter {
  event(input: { event: OpenCodeEvent }): void;
  "experimental.session.compacting"(input: { sessionID?: string }): Promise<void>;
  "experimental.compaction.autocontinue"(input: { sessionID?: string }): Promise<void>;
  "experimental.chat.system.transform"(input: { sessionID?: string }, output: { system: string[] }): Promise<void>;
}

interface OpenCodeEvent {
  type: string;
  properties?: { sessionID?: string; status?: { type?: string } };
}

export function createModerationAdapter(input: ModerationServerInput, options: ModerationOptions, fetchImpl: FetchLike = fetch): ModerationAdapter {
  const sessions = new Map<string, Session>();
  const restored = new Set<string>();
  const restoreOnce = async (sessionID: string, session: Session): Promise<void> => {
    if (restored.has(sessionID)) return;
    restored.add(sessionID);
    const snapshot = await restoreSnapshot(sessionDirectory(sessionID));
    if (snapshot === null) return;
    if (isValidState(snapshot)) {
      session.state = normalizeRestoredState(snapshot);
      return;
    }
    await writeDecisionRecord(sessionDirectory(sessionID), { event: "RESTORE", decisionType: "moderation-error", error: "invalid state snapshot", stateSnapshot: session.state });
  };
  const record = (sessionID: string): Session => {
    const existing = sessions.get(sessionID);
    if (existing) return existing;
    const created: Session = {
      state: createInitialState(),
      queue: [],
      draining: false,
      busyCount: 0,
      continuationBaseline: 0,
      judgedAssistantID: null,
      moderatorMessageIDs: new Set(),
      context: null,
      userMessages: [],
    };
    sessions.set(sessionID, created);
    return created;
  };
  const enqueue = (sessionID: string, event: ModerationEvent, first = false): void => {
    const session = record(sessionID);
    session.queue[first ? "unshift" : "push"]({ ...event, sessionID });
    if (!session.draining) void drain(sessionID, session);
  };
  const drain = async (sessionID: string, session: Session): Promise<void> => {
    session.draining = true;
    try {
      await restoreOnce(sessionID, session);
      while (session.queue.length) {
        const event = session.queue.shift() as ModerationEvent;
        const previous = session.state;
        const result = transition(previous, event);
        session.state = result.state;
        const effectResults: Record<string, unknown>[] = [];
        for (const effect of result.effects) {
          try {
            const effectResult = await perform(sessionID, session, effect, event);
            effectResults.push({ effect: effect.type, status: "ok", result: effectResult === null ? null : effectResult.type ?? null });
            if (effectResult && typeof effectResult.type === "string") enqueue(sessionID, effectResult, true);
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            effectResults.push({ effect: effect.type, status: "error", error: message });
            if (effect.type !== "WRITE_DECISION") enqueue(sessionID, { type: "EFFECT_ERROR", error: message });
          }
        }
        await writeDecisionRecord(sessionDirectory(sessionID), decisionRecord(event, previous, result, effectResults));
        await persistSnapshot(sessionDirectory(sessionID), session.state);
      }
    } finally {
      session.draining = false;
      if (session.queue.length) void drain(sessionID, session);
    }
  };
  const perform = async (sessionID: string, session: Session, effect: Effect, event: ModerationEvent): Promise<ModerationEvent | null> => {
    switch (effect.type) {
      case "LOAD_CONTEXT": return loadContext(sessionID, session);
      case "CLASSIFY": return classifyEffect(session, event);
      case "WRITE_TRACE": return writeTrace(sessionID, session, effect.verdict);
      case "SHOW_TOAST": return showToast(input.client, effect.kind);
      case "SEND_CONTINUATION": return sendContinuation(sessionID, session, effect.verdict);
      case "VERIFY_PROMPT": return verifyPrompt(sessionID);
      case "WAIT_FOR_BUSY": return waitForBusy(sessionID, session);
      case "WRITE_DECISION": return null;
      default: return assertNever(effect);
    }
  };
  const loadContext = async (sessionID: string, session: Session): Promise<ModerationEvent> => {
    const [todoResult, messages] = await withTimeout(Promise.all([
      input.client.session.todo({ path: { id: sessionID } }),
      loadMessages(input.client, sessionID),
    ]), CONTEXT_TIMEOUT_MS, "AgentCI moderation context request timed out");
    const todos = todoResult.data ?? [];
    const assistant = newestAssistant(messages);
    const origin = realUserAncestor(assistant, messages) ?? realUser(messages, session.moderatorMessageIDs);
    const assistantID = assistant?.info.id ?? null;
    session.judgedAssistantID = assistantID;
    const blockerBranch = inBranch(origin, messages, session.state.blocker?.originUserID ?? null);
    session.context = deriveContext({
      messages,
      assistantID,
      lastTerminalAssistantID: session.state.lastTerminalAssistantID,
      inflightAssistantID: session.state.inflightAssistantID,
    });
    session.context = { ...session.context, blockerDiscussionActive: blockerBranch };
    session.userMessages = session.context.realUserPrompts;
    const realUserCycleID = origin?.info.id ?? null;
    return {
      type: "CONTEXT_LOADED",
      todos,
      assistantID,
      terminal: session.context.terminal,
      assistantPresent: session.context.assistantPresent,
      duplicate: session.context.duplicate,
      compaction: session.context.compaction,
      planMode: session.context.planMode,
      build: session.context.build,
      assistantError: session.context.assistantError,
      userNewer: session.context.userNewer,
      moderatorTrace: session.context.moderatorTrace,
      rootBlocked: session.context.rootBlocked,
      blockerDiscussionActive: blockerBranch,
      blockerBranch,
      realUserCycleID,
      newCycle: realUserCycleID !== session.state.realUserCycleID,
      originUserID: realUserCycleID,
    };
  };
  const classifyEffect = async (session: Session, event: ModerationEvent): Promise<ModerationEvent> => {
    const context = session.context;
    if (!context) throw new Error("AgentCI moderation classifier ran without a context snapshot");
    const todos = event.type === "CONTEXT_LOADED" ? event.todos ?? [] : [];
    const outcome = await resolveVerdict(options, { todos, previousResponse: context.assistantResponse, userMessages: session.userMessages }, fetchImpl);
    if (outcome.error) throw new Error(outcome.error);
    const verdict = outcome.verdict;
    if (!verdict) throw new Error("AgentCI moderation classifier returned no verdict");
    const originUserID = event.type === "CONTEXT_LOADED" ? event.originUserID ?? null : null;
    return { type: "CLASSIFIER_RESULT", verdict, originUserID, capture: outcome.capture };
  };
  const writeTrace = async (sessionID: string, session: Session, verdict: Verdict | undefined): Promise<ModerationEvent> => {
    const text = verdict ? statusLine(verdict.decision, verdict.reasonCode) : OPERATOR_LINE;
    const response = await input.client.session.prompt({ path: { id: sessionID }, body: { noReply: true, parts: [{ type: "text", text }] } });
    const id = response.data?.info?.id;
    if (id) session.moderatorMessageIDs.add(id);
    return { type: "TRACE_PERSISTED", messageID: id ?? null };
  };
  const userSpokeAfterJudged = async (sessionID: string, session: Session): Promise<boolean> => {
    const judged = session.judgedAssistantID;
    if (judged === null) return false;
    const history = await loadMessages(input.client, sessionID);
    const index = history.findIndex((message) => message.info.id === judged);
    if (index < 0) return false;
    return history.slice(index + 1).some((message) => message.info.role === "user"
      && !isInjectedUser(message)
      && !isSyntheticUser(message)
      && !session.moderatorMessageIDs.has(message.info.id ?? ""));
  };
  const sendContinuation = async (sessionID: string, session: Session, verdict: Verdict | undefined): Promise<ModerationEvent> => {
    if (!verdict) throw new Error("AgentCI moderation continuation ran without a verdict");
    if (await userSpokeAfterJudged(sessionID, session)) throw new Error("AgentCI moderation cancelled the continuation: a user message arrived after the judged response");
    session.continuationBaseline = session.busyCount;
    const response = await sendContinuationPrompt(input.client, sessionID, statusLine(verdict.decision, verdict.reasonCode));
    const id = promptAsyncMessageID(response);
    if (id !== null) session.moderatorMessageIDs.add(id);
    return { type: "CONTINUATION_PERSISTED" };
  };
  const verifyPrompt = async (sessionID: string): Promise<null> => {
    if (!await continuationPersisted(input.client, sessionID)) throw new Error("AgentCI moderation continuation prompt was not persisted");
    return null;
  };
  const waitForBusy = async (sessionID: string, session: Session): Promise<ModerationEvent> => {
    const baseline = session.continuationBaseline;
    for (let attempt = 0; attempt < BUSY_POLL_ATTEMPTS; attempt += 1) {
      if (session.busyCount > baseline) return { type: "BUSY_VERIFIED" };
      await sleep(BUSY_POLL_INTERVAL_MS);
    }
    return { type: "CONTINUATION_TIMEOUT" };
  };
  const eventHook = ({ event }: { event: OpenCodeEvent }): void => {
    const sessionID = event.properties?.sessionID;
    if (!isSessionID(sessionID)) return;
    if (event.type === "session.status") {
      const session = record(sessionID);
      const status = event.properties?.status?.type;
      if (status === "busy") session.busyCount += 1;
      enqueue(sessionID, { type: status === "busy" ? "STATUS_BUSY" : "STATUS_IDLE" });
      return;
    }
    if (event.type === "session.compacted") enqueue(sessionID, { type: "COMPACTION_COMPLETED" });
  };
  const sessionEvent = (sessionID: string | undefined, event: ModerationEvent): void => {
    if (isSessionID(sessionID)) enqueue(sessionID, event);
  };
  return {
    event: eventHook,
    async "experimental.session.compacting"(hookInput) {
      sessionEvent(hookInput.sessionID, { type: "COMPACTION_STARTED" });
    },
    async "experimental.compaction.autocontinue"(hookInput) {
      sessionEvent(hookInput.sessionID, { type: "COMPACTION_AUTOCONTINUE" });
    },
    async "experimental.chat.system.transform"(_hookInput, hookOutput) {
      if (!hookOutput.system.includes(STATUS_INSTRUCTION)) hookOutput.system.push(STATUS_INSTRUCTION);
    },
  };
}

export function isSessionID(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9_-]+$/.test(value);
}

export async function loadMessages(client: ModerationClient, sessionID: string): Promise<MessageFact[]> {
  const history: MessageFact[] = [];
  const seen = new Set<string>();
  let cursor: string | undefined;
  do {
    const page = await client.session.messages({ path: { id: sessionID }, query: cursor ? { limit: 200, cursor } : { limit: 200, order: "asc" } });
    history.push(...(page.data ?? []));
    cursor = page.cursor?.next;
    if (cursor !== undefined && seen.has(cursor)) throw new Error("AgentCI moderation message pagination cursor repeated");
    if (cursor !== undefined) seen.add(cursor);
  } while (cursor !== undefined);
  return history;
}

function realUser(messages: MessageFact[], moderatorMessageIDs: Set<string>): MessageFact | undefined {
  return messages.filter((message) => message.info.role === "user" && !moderatorMessageIDs.has(message.info.id ?? "") && !isInjectedUser(message) && !isSyntheticUser(message)).at(-1);
}

export async function sendContinuationPrompt(client: ModerationClient, sessionID: string, text: string): Promise<unknown> {
  return client.session.promptAsync({
    path: { id: sessionID },
    body: {
      parts: [
        { type: "text", text, synthetic: true, metadata: { moderation: true } },
        { type: "text", text: CONTINUATION_NOTE, metadata: { moderation: true } },
      ],
    },
  });
}

export async function continuationPersisted(client: ModerationClient, sessionID: string): Promise<boolean> {
  for (let attempt = 0; attempt < CONTINUATION_VERIFY_ATTEMPTS; attempt += 1) {
    const messages = (await client.session.messages({ path: { id: sessionID }, query: { limit: 20 } })).data ?? [];
    if (messages.some((message) => message.parts.some((part) => part.text === CONTINUATION_LINE))) return true;
    await sleep(BUSY_POLL_INTERVAL_MS);
  }
  return false;
}

function promptAsyncMessageID(response: unknown): string | null {
  if (typeof response !== "object" || response === null) return null;
  const data = (response as { data?: { info?: { id?: unknown } } }).data;
  const id = data?.info?.id;
  return typeof id === "string" ? id : null;
}

async function showToast(client: ModerationClient, kind: string): Promise<null> {
  const detail = toast(kind);
  await Promise.race([client.tui.showToast({ body: { title: detail.title, message: detail.message, variant: detail.variant, duration: detail.duration } }), sleep(2000)]);
  return null;
}

function decisionRecord(event: ModerationEvent, previous: ModerationState, result: TransitionResult, effectResults: unknown[]): Record<string, unknown> {
  const decision = result.effects.find((effect) => effect.type === "WRITE_DECISION");
  const verdict = event.type === "CLASSIFIER_RESULT" ? event.verdict : null;
  const capture = event.type === "CLASSIFIER_RESULT" ? event.capture ?? null : null;
  const error = event.type === "EFFECT_ERROR" ? event.error ?? null : null;
  const assistantID = event.type === "CONTEXT_LOADED" ? event.assistantID ?? null : null;
  return {
    timestamp: new Date().toISOString(),
    schemaVersion: 1,
    sessionID: event.sessionID ?? null,
    assistantID,
    event: event.type,
    eventPayload: event.type === "CLASSIFIER_RESULT" ? null : eventPayload(event),
    decisionType: decision?.decisionType ?? event.type,
    previousPhase: result.transition.previousPhase,
    nextPhase: result.transition.nextPhase,
    ignored: result.ignored,
    verdict,
    capture,
    error,
    effects: result.effects,
    effectResults,
    previousState: previous,
    stateSnapshot: result.state,
  };
}

function eventPayload(event: ModerationEvent): Record<string, unknown> {
  const payload = { ...event } as Record<string, unknown>;
  delete payload.sessionID;
  return payload;
}

function toast(kind: string): { title: string; message: string; variant: string; duration: number } {
  const table: Record<string, { title: string; message: string; variant: string; duration: number }> = {
    checking: { title: "AgentCI moderation", message: "Checking the completed response...", variant: "info", duration: 3000 },
    complete: { title: "AgentCI moderation: complete", message: "Automated moderation verified the work is complete.", variant: "success", duration: 5000 },
    "agent-blocked": { title: "AgentCI moderation: agent blocked", message: "The agent is waiting on you or an operator before continuing.", variant: "warning", duration: 8000 },
    "user-stop": { title: "AgentCI moderation: user stop", message: "Automated moderation stood down at the user's request.", variant: "info", duration: 4000 },
    "operator-handoff": { title: "AgentCI moderation: operator handoff", message: "A privileged command requires operator action.", variant: "warning", duration: 8000 },
    continuing: { title: "AgentCI moderation: continuing", message: "Automated moderation is prompting the agent to continue.", variant: "warning", duration: 6000 },
    escalated: { title: "AgentCI moderation: escalation", message: "Three consecutive no-progress decisions stopped automatic continuation.", variant: "error", duration: 8000 },
    "continuation-error": { title: "AgentCI moderation: continuation error", message: "The corrective prompt was persisted but the agent did not start a new turn.", variant: "error", duration: 8000 },
    error: { title: "AgentCI moderation: error", message: "Moderation failed to run; inspect the audit log.", variant: "error", duration: 8000 },
  };
  return table[kind] ?? table.error;
}

function assertNever(value: never): never {
  throw new Error(`AgentCI moderation encountered an unknown effect: ${JSON.stringify(value)}`);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => { setTimeout(resolve, ms); });
}

async function withTimeout<T>(promise: Promise<T>, ms: number, message: string): Promise<T> {
  let timer: NodeJS.Timeout | undefined;
  try {
    return await Promise.race([promise, new Promise<never>((_resolve, reject) => { timer = setTimeout(() => reject(new Error(message)), ms); })]);
  } finally {
    if (timer !== undefined) clearTimeout(timer);
  }
}