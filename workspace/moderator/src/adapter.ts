import { rm } from "node:fs/promises";
import { appendDecision, auditRecord, persistState, restoreState, sessionDirectory } from "./audit.ts";
import { requireData } from "./client-read.ts";
import { classify } from "./classifier.ts";
import type { GenerateFn } from "./generate.ts";
import {
  assistantText,
  selectWindow,
  detectsRootBlock,
  inBranch,
  isAnswer,
  isInjectedUser,
  isPlan,
  isTerminal,
  newestModeratedAssistant,
  realUserAncestor,
} from "./context.ts";
import { createInitialState, isValidState, normalizeRestoredState, transition } from "./fsm.ts";
import { CONTINUATION_LINE, CONTINUATION_NOTE, OPERATOR_LINE, statusLine } from "./prompt.ts";
import type { ModelSelector } from "./model-select.ts";
import type {
  ClassifierCapture,
  ContextFact,
  Effect,
  MessageFact,
  ModerationEvent,
  ModerationState,
  ToastKind,
  TodoFact,
  TransitionResult,
  TurnFact,
  Verdict,
} from "./types.ts";

export interface ModeratorClient {
  session: {
    messages(input: { path: { id: string }; query?: Record<string, unknown> }): Promise<{ data?: MessageFact[]; error?: unknown }>;
    todo(input: { path: { id: string } }): Promise<{ data?: TodoFact[]; error?: unknown }>;
    prompt(input: { path: { id: string }; body: Record<string, unknown> }): Promise<{ data?: { info?: { id?: string } } }>;
    promptAsync(input: { path: { id: string }; body: Record<string, unknown> }): Promise<unknown>;
    revert(input: { path: { id: string }; body: { messageID: string } }): Promise<unknown>;
  };
  tui: { showToast(input: { body: Record<string, unknown> }): Promise<unknown> };
}

interface MessagePart {
  type?: string;
  text?: string;
  synthetic?: boolean;
  metadata?: Record<string, unknown>;
}

interface OpenCodeEvent {
  type: string;
  properties?: { sessionID?: string; status?: { type?: string } };
}

interface LoadedContext {
  turn: TurnFact;
  todos: readonly TodoFact[];
  originUserID: string | null;
  prompts: string[];
  toolActivity: string[];
  response: string;
}

interface Session {
  state: ModerationState;
  queue: ModerationEvent[];
  draining: boolean;
  restored: boolean;
  context: LoadedContext | null;
  moderatorMessageIDs: Set<string>;
  lastSelector: string;
  lastError: string | null;
}

const replayStarted = new Set<string>();
const CONTINUATION_VERIFY_ATTEMPTS = 20;
const VERIFY_INTERVAL_MS = 100;

export function createModeratorAdapter(input: { client: ModeratorClient; generate?: GenerateFn }, selectors: readonly ModelSelector[]) {
  const sessions = new Map<string, Session>();

  const get = (sessionID: string): Session => {
    const existing = sessions.get(sessionID);
    if (existing !== undefined) return existing;
    const created: Session = { state: createInitialState(), queue: [], draining: false, restored: false, context: null, moderatorMessageIDs: new Set(), lastSelector: "", lastError: null };
    sessions.set(sessionID, created);
    return created;
  };

  const enqueue = (sessionID: string, event: ModerationEvent, first = false): void => {
    const session = get(sessionID);
    session.queue[first ? "unshift" : "push"]({ ...event, sessionID });
    drain(sessionID, session).catch((error: unknown) => failClosed(sessionID, error));
  };

  const drain = async (sessionID: string, session: Session): Promise<void> => {
    if (session.draining) return;
    session.draining = true;
    try {
      if (!session.restored) {
        session.restored = true;
        const snapshot = await restoreState(sessionDirectory(sessionID));
        if (snapshot !== null) {
          if (!isValidState(snapshot)) throw new Error("moderator state snapshot is invalid");
          session.state = normalizeRestoredState(snapshot);
        }
      }
      while (session.queue.length > 0) {
        const event = session.queue.shift();
        if (event === undefined) break;
        const previous = session.state;
        const result = transition(previous, event);
        session.state = result.state;
        const effectResults: Record<string, unknown>[] = [];
        for (const effect of result.effects) {
          try {
            const followup = await perform(sessionID, session, effect);
            effectResults.push({ effect: effect.type, status: "ok" });
            if (followup !== null) enqueue(sessionID, followup, true);
          } catch (error) {
            const message = error instanceof Error ? error.message : String(error);
            effectResults.push({ effect: effect.type, status: "error", error: message });
            if (effect.type !== "WRITE_DECISION" && effect.type !== "WRITE_TRACE") {
              session.lastError = message;
              if (isContextLimit(message)) await writeTrace(sessionID, session, undefined, message);
            }
            if (effect.type !== "WRITE_DECISION") enqueue(sessionID, { type: "EFFECT_ERROR", error: message }, true);
          }
        }
        await appendDecision(sessionDirectory(sessionID), record(event, previous, result, effectResults));
        await persistState(sessionDirectory(sessionID), session.state);
      }
    } finally {
      session.draining = false;
      if (session.queue.length > 0) drain(sessionID, session).catch((error: unknown) => failClosed(sessionID, error));
    }
  };

  const perform = async (sessionID: string, session: Session, effect: Effect): Promise<ModerationEvent | null> => {
    if (effect.type === "WRITE_DECISION") return null;
    if (effect.type === "LOAD_CONTEXT") return loadContext(sessionID, session);
    if (effect.type === "CLASSIFY") return classifyContext(sessionID, session);
    if (effect.type === "WRITE_TRACE") {
      await writeTrace(sessionID, session, effect.verdict);
      return { type: "TRACE_PERSISTED" };
    }
    if (effect.type === "SEND_CONTINUATION") {
      await sendContinuation(sessionID, session, effect.verdict);
      return { type: "CONTINUATION_PERSISTED" };
    }
    if (effect.type === "VERIFY_PROMPT") {
      await verifyPrompt(sessionID);
      return null;
    }
    await showToast(input.client, effect.kind, effect.kind === "error" ? session.lastError : null);
    return null;
  };

  const loadContext = async (sessionID: string, session: Session): Promise<ModerationEvent> => {
    const [messages, todoResult] = await Promise.all([
      loadMessages(input.client, sessionID),
      input.client.session.todo({ path: { id: sessionID } }),
    ]);
    const todos = requireData(todoResult, "moderator session.todo");
    const loaded = buildContext(messages, todos, session);
    session.context = loaded;
    return { type: "CONTEXT_LOADED", turn: loaded.turn, originUserID: loaded.originUserID, todos };
  };

  const classifyContext = async (sessionID: string, session: Session): Promise<ModerationEvent> => {
    const context = session.context;
    if (context === null) throw new Error("moderator classification ran without context");
    const outcome = await classify(selectors, {
      parentSessionID: sessionID,
      todos: context.todos,
      previousResponse: context.response,
      userMessages: context.prompts,
      toolActivity: context.toolActivity,
      agentMode: context.turn.agentMode,
    }, input.generate);
    session.lastSelector = outcome.capture.selector;
    if (outcome.verdict === undefined) {
      throw new Error(outcome.error ?? "moderator classifier returned no verdict");
    }
    return { type: "VERDICT", verdict: outcome.verdict, capture: outcome.capture, originUserID: context.originUserID };
  };

  const writeTrace = async (sessionID: string, session: Session, verdict: Verdict | undefined, errorText?: string): Promise<void> => {
    const text = errorText !== undefined
      ? `⚠️ Automated Moderation: ${errorText}`
      : verdict === undefined ? OPERATOR_LINE : statusLine(verdict);
    const response = await input.client.session.prompt({ path: { id: sessionID }, body: { noReply: true, parts: [{ type: "text", text }] } });
    const id = response.data?.info?.id;
    if (typeof id === "string") session.moderatorMessageIDs.add(id);
  };

  const sendContinuation = async (sessionID: string, session: Session, verdict: Verdict): Promise<void> => {
    const existing = requireData(await input.client.session.messages({ path: { id: sessionID } }), "moderator session.messages");
    const assistant = newestModeratedAssistant(existing);
    const assistantIndex = assistant === undefined ? -1 : existing.findIndex((message) => message.info.id === assistant.info.id);
    const alreadyContinued = assistantIndex >= 0 && existing.slice(assistantIndex + 1).some((message) => message.parts.some((part) => part.synthetic === true && part.metadata?.moderation === true));
    if (alreadyContinued) {
      throw new Error("moderator continuation was not sent because a moderator continuation already follows the assistant");
    }
    const text = statusLine(verdict);
    const response = await input.client.session.promptAsync({
      path: { id: sessionID },
      body: {
        parts: [
          { type: "text", text, synthetic: true, metadata: { moderation: true } },
          { type: "text", text: CONTINUATION_NOTE, metadata: { moderation: true } },
        ],
      },
    });
    const id = messageID(response);
    if (id !== null) session.moderatorMessageIDs.add(id);
  };

  const verifyPrompt = async (sessionID: string): Promise<void> => {
    for (let attempt = 0; attempt < CONTINUATION_VERIFY_ATTEMPTS; attempt += 1) {
      const messages = requireData(await input.client.session.messages({ path: { id: sessionID } }), "moderator session.messages");
      if (messages.some((message) => message.parts.some((part) => part.synthetic === true && part.metadata?.moderation === true && typeof part.text === "string" && part.text.startsWith(CONTINUATION_LINE)))) return;
      await sleep(VERIFY_INTERVAL_MS);
    }
    throw new Error("moderator continuation prompt was not persisted");
  };

  const onEvent = (event: OpenCodeEvent): void => {
    const sessionID = event.properties?.sessionID;
    if (typeof sessionID !== "string" || sessionID.length === 0) return;
    if (event.type === "session.deleted") {
      sessions.delete(sessionID);
      rm(sessionDirectory(sessionID), { recursive: true, force: true }).catch((error: unknown) => failClosed(sessionID, error));
      return;
    }
    if (event.type === "session.compacted") {
      enqueue(sessionID, { type: "COMPACTION_COMPLETED" });
      return;
    }
    if (event.type !== "session.status") return;
    const status = event.properties?.status?.type;
    if (status === "busy") {
      enqueue(sessionID, { type: "STATUS_BUSY" });
      return;
    }
    if (status === "idle") {
      idle(sessionID).catch((error: unknown) => failClosed(sessionID, error));
    }
  };

  const idle = async (sessionID: string): Promise<void> => {
    try {
      const session = get(sessionID);
      const [messages, todoResult] = await Promise.all([
        loadMessages(input.client, sessionID),
        input.client.session.todo({ path: { id: sessionID } }),
      ]);
      const loaded = buildContext(messages, requireData(todoResult, "moderator session.todo"), session, false);
      if (loaded.turn.newCycle) {
        enqueue(sessionID, { type: "NEW_USER_CYCLE", originUserID: loaded.originUserID, sameBranch: loaded.turn.blockerDiscussion });
      }
      enqueue(sessionID, { type: "TURN_ENDED", turn: loaded.turn });
    } catch (error) {
      enqueue(sessionID, { type: "EFFECT_ERROR", error: error instanceof Error ? error.message : String(error) });
    }
  };

  const replay = async (sessionID: string, force: boolean): Promise<void> => {
    if (replayStarted.has(sessionID)) return;
    replayStarted.add(sessionID);
    try {
      const messages = requireData(await input.client.session.messages({ path: { id: sessionID } }), "moderator session.messages");
      const assistant = newestModeratedAssistant(messages);
      if (assistant?.info.id === undefined) throw new Error("moderator replay found no completed assistant response");
      if (!isTerminal(assistant)) throw new Error(`moderator replay found no finished assistant: finish=${String(assistant.info.finish)}`);
      if (!force) {
        const assistantIndex = messages.findIndex((message) => message.info.id === assistant.info.id);
        const trace = messages.slice(assistantIndex + 1).find((message) => isInjectedUser(message));
        if (trace?.info.id !== undefined) {
          await input.client.session.revert({ path: { id: sessionID }, body: { messageID: trace.info.id } });
        }
      }
      const session = get(sessionID);
      const todos = requireData(await input.client.session.todo({ path: { id: sessionID } }), "moderator session.todo");
      const loaded = buildContext(messages, todos, session, false);
      session.context = loaded;
      enqueue(sessionID, { type: "REPLAY", turn: loaded.turn });
    } catch (error) {
      replayStarted.delete(sessionID);
      const message = error instanceof Error ? error.message : String(error);
      if (isContextLimit(message)) await writeTrace(sessionID, get(sessionID), undefined, message);
      await input.client.tui.showToast({ body: { title: "Moderator failed", message, variant: "error", duration: 30000 } });
      await failClosed(sessionID, error);
    }
  };

  return {
    event: onEvent,
    replay,
    "experimental.session.compacting": async (hookInput: { sessionID?: string }) => {
      if (typeof hookInput.sessionID === "string") enqueue(hookInput.sessionID, { type: "COMPACTION_STARTED" });
    },
    "experimental.compaction.autocontinue": async (hookInput: { sessionID?: string }) => {
      if (typeof hookInput.sessionID === "string") enqueue(hookInput.sessionID, { type: "COMPACTION_COMPLETED" });
    },
  };
}

function buildContext(messages: readonly MessageFact[], todos: readonly TodoFact[], session: Session, force = false): LoadedContext {
  const assistant = newestModeratedAssistant(messages);
  const assistantIndex = assistant === undefined ? -1 : messages.findIndex((message) => message.info.id === assistant.info.id);
  const following = assistantIndex >= 0 ? messages.slice(assistantIndex + 1) : [];
  const origin = realUserAncestor(assistant, messages);
  const originUserID = origin?.info.id ?? null;
  const selected = selectWindow(assistant, messages);
  const response = assistant === undefined ? "" : assistantText(assistant);
  const turn: TurnFact = {
    assistantID: assistant?.info.id ?? null,
    userMessageID: originUserID,
    agentMode: assistant !== undefined && isAnswer(assistant) ? "answer" : "build",
    todosOpen: todos.filter((todo) => todo.status !== "completed").length,
    terminal: assistant !== undefined && isTerminal(assistant),
    assistantPresent: response.length > 0,
    duplicate: !force && assistant?.info.id !== undefined && assistant.info.id === session.state.lastTerminalAssistantID,
    compaction: assistant?.info.summary === true || assistant?.info.agent === "compaction",
    assistantError: assistant?.info.error !== undefined && assistant.info.error !== null,
    userNewer: following.some((message) => message.info.role === "user" && !isInjectedUser(message) && !session.moderatorMessageIDs.has(message.info.id ?? "")),
    moderatorTrace: assistant !== undefined && isInjectedUser(assistant),
    planMode: assistant !== undefined && isPlan(assistant),
    rootBlocked: detectsRootBlock(response),
    blockerDiscussion: session.state.blocker !== null && inBranch(origin, messages, session.state.blocker.originUserID),
    newCycle: originUserID !== null && originUserID !== session.state.realUserCycleID,
  };
  return {
    turn,
    todos,
    originUserID,
    prompts: selected.prompts,
    toolActivity: selected.toolActivity,
    response: selected.response.length > 0 ? selected.response : response,
  };
}

function record(event: ModerationEvent, previous: ModerationState, result: TransitionResult, effectResults: unknown[]): Record<string, unknown> {
  const verdict = event.type === "VERDICT" ? event.verdict : null;
  const capture = event.type === "VERDICT" ? event.capture : null;
  const error = event.type === "EFFECT_ERROR" ? event.error : null;
  return auditRecord({
    sessionID: event.sessionID ?? "",
    assistantID: previous.inflightAssistantID,
    event: event.type,
    decision: decisionOf(result),
    reason: verdict?.reasonCode ?? decisionReason(result),
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
  });
}

function decisionOf(result: TransitionResult): string {
  const effect = result.effects.find((entry) => entry.type === "WRITE_DECISION");
  return effect?.type === "WRITE_DECISION" ? effect.decisionType : "ignored-outside-phase";
}

function decisionReason(result: TransitionResult): string | null {
  const effect = result.effects.find((entry) => entry.type === "WRITE_DECISION");
  return effect?.type === "WRITE_DECISION" ? effect.reason ?? null : null;
}

function messageID(response: unknown): string | null {
  if (typeof response !== "object" || response === null) return null;
  const data = (response as { data?: { info?: { id?: unknown } } }).data;
  return typeof data?.info?.id === "string" ? data.info.id : null;
}

async function showToast(client: ModeratorClient, kind: ToastKind, errorText: string | null): Promise<void> {
  const detail = toast(kind, errorText);
  await Promise.race([
    client.tui.showToast({ body: detail }),
    sleep(2000),
  ]);
}

function isContextLimit(message: string): boolean {
  return message.includes("MODERATOR_CTX") || message.includes("moderator context is");
}

async function failClosed(sessionID: string, error: unknown): Promise<void> {
  const message = error instanceof Error ? error.message : String(error);
  await appendDecision(sessionDirectory(sessionID), {
    timestamp: new Date().toISOString(),
    schemaVersion: 1,
    sessionID,
    assistantID: null,
    event: "EFFECT_ERROR",
    decision: "moderation-error",
    reason: null,
    previousPhase: "ERROR",
    nextPhase: "ERROR",
    ignored: false,
    verdict: null,
    capture: null,
    error: message,
    effects: [],
    effectResults: [],
    previousState: null,
    stateSnapshot: null,
  });
}

function toast(kind: ToastKind, errorText: string | null): Record<string, unknown> {
  const table: Record<ToastKind, { title: string; message: string; variant: string; duration: number }> = {
    checking: { title: "Moderator", message: "Checking the completed response.", variant: "info", duration: 30000 },
    complete: { title: "Moderator: complete", message: "Work completion verified.", variant: "success", duration: 30000 },
    "agent-blocked": { title: "Moderator: blocked", message: "The agent is waiting for user or operator input.", variant: "warning", duration: 30000 },
    "user-stop": { title: "Moderator: stop", message: "Automation stood down.", variant: "info", duration: 30000 },
    "operator-handoff": { title: "Moderator: operator handoff", message: "A privileged command requires operator action.", variant: "warning", duration: 30000 },
    continuing: { title: "Moderator: continuing", message: "Prompting the agent to continue.", variant: "warning", duration: 30000 },
    escalated: { title: "Moderator: escalation", message: "Three stalled decisions stopped continuation.", variant: "error", duration: 30000 },
    error: { title: "Moderator failed", message: errorText ?? "Moderation failed.", variant: "error", duration: 30000 },
  };
  return table[kind];
}

async function loadMessages(client: ModeratorClient, sessionID: string): Promise<MessageFact[]> {
  return requireData(await client.session.messages({ path: { id: sessionID } }), "moderator session.messages");
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => { setTimeout(resolve, ms); });
}

export type { ClassifierCapture, ContextFact };
