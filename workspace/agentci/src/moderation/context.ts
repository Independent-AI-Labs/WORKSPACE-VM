import type { ContextSnapshot, MessageFact, TodoFact } from "./types.ts";

export const MODERATION_MARKER = "Automated Moderation:";
export const EMPTY_USER_PROMPT = "Continue the unfinished work.";

const INJECTED_MESSAGE = new RegExp(`^[^\\p{L}\\p{N}]*${MODERATION_MARKER}`, "u");

const ROOT_BLOCK_FENCE = /```(?:bash|sh|shell|zsh)?\s*\n([\s\S]*?)```/gi;
const ROOT_BLOCK_COMMAND = /(?:^|[;&|()]\s*|\b(?:if|then|do)\s+)sudo(?:\s|$)/m;
const REAL_USER_CONTEXT_LIMIT = 3;

export interface ContextInput {
  messages: readonly MessageFact[];
  assistantID: string | null;
  lastTerminalAssistantID: string | null;
  inflightAssistantID: string | null;
}

export function deriveContext(input: ContextInput): ContextSnapshot {
  const index = input.messages.findIndex((message) => message.info.id === input.assistantID);
  const assistant = index >= 0 ? input.messages[index] : undefined;
  const following = index >= 0 ? input.messages.slice(index + 1) : [];
  const response = assistant ? assistantText(assistant) : "";
  const duplicates = input.assistantID !== null && input.assistantID !== undefined
    && (input.assistantID === input.lastTerminalAssistantID || input.assistantID === input.inflightAssistantID);
  return {
    terminal: assistant !== undefined && isTerminal(assistant),
    assistantPresent: assistant !== undefined && response.length > 0,
    duplicate: duplicates,
    compaction: assistant?.info.summary === true,
    planMode: isPlanMode(assistant),
    build: !isPlanMode(assistant),
    assistantError: assistant !== undefined && assistant.info.error !== undefined && assistant.info.error !== null,
    userNewer: following.some((message) => message.info.role === "user" && !isInjectedUser(message) && !isSyntheticUser(message)),
    moderatorTrace: INJECTED_MESSAGE.test(response),
    rootBlocked: detectsRootBlock(response),
    blockerDiscussionActive: false,
    realUserCycleID: realUserCycleID(input.messages),
    realUserPrompts: lastRealUserPrompts(input.messages),
    assistantResponse: response,
  };
}

export function assistantText(message: MessageFact): string {
  return message.parts
    .filter((part) => part.type === "text" && part.synthetic !== true && typeof part.text === "string")
    .map((part) => part.text as string)
    .join("\n")
    .trim();
}

export function isSyntheticUser(message: MessageFact): boolean {
  return message.info.role === "user" && message.parts.some((part) => part.synthetic === true && part.metadata?.compaction_continue === true);
}

export function isTerminal(message: MessageFact): boolean {
  const info = message.info;
  return info.time?.created !== undefined && (info.finish === "stop" || info.summary === true);
}

export function newestAssistant(messages: readonly MessageFact[]): MessageFact | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.info.role === "assistant") return message;
  }
  return undefined;
}

export function realUserAncestor(assistant: MessageFact | undefined, messages: readonly MessageFact[]): MessageFact | undefined {
  const byID = new Map(messages.map((message) => [message.info.id ?? "", message]));
  let current: MessageFact | undefined = assistant;
  while (current) {
    if (current.info.role === "user" && !isInjectedUser(current) && !isSyntheticUser(current)) return current;
    current = current.info.parentID !== undefined ? byID.get(current.info.parentID) : undefined;
  }
  return undefined;
}

export function isPlanMode(message: MessageFact | undefined): boolean {
  if (!message) return false;
  return message.info.mode === "plan" || message.info.agent === "plan";
}

export function isInjectedUser(message: MessageFact): boolean {
  return INJECTED_MESSAGE.test(assistantText(message));
}

export function detectsRootBlock(text: string): boolean {
  for (const match of text.matchAll(ROOT_BLOCK_FENCE)) {
    if (ROOT_BLOCK_COMMAND.test(match[1])) return true;
  }
  return false;
}

export function lastRealUserPrompts(messages: readonly MessageFact[]): string[] {
  const prompts: string[] = [];
  for (let index = messages.length - 1; index >= 0 && prompts.length < REAL_USER_CONTEXT_LIMIT; index -= 1) {
    const message = messages[index];
    if (message.info.role !== "user" || isInjectedUser(message) || isSyntheticUser(message)) continue;
    const value = assistantText(message);
    if (value.length === 0) {
      if (prompts.length === 0) prompts.unshift(EMPTY_USER_PROMPT);
      continue;
    }
    prompts.unshift(value);
  }
  return prompts;
}

export function inBranch(message: MessageFact | undefined, messages: readonly MessageFact[], originID: string | null): boolean {
  if (!message || originID === null) return false;
  let current: MessageFact | undefined = message;
  while (current) {
    if (current.info.id === originID) return true;
    current = messages.find((candidate) => candidate.info.id === current?.info.parentID);
  }
  return false;
}

export function realUserCycleID(messages: readonly MessageFact[]): string | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.info.role !== "user" || isInjectedUser(message) || isSyntheticUser(message)) continue;
    return message.info.id ?? null;
  }
  return null;
}

export function summarizeTodos(todos: readonly TodoFact[]): string {
  if (todos.length === 0) return "No tracked todos.";
  return todos
    .map((todo) => `- [${todo.status ?? "unknown"}] ${todo.content ?? "(untitled)"}`)
    .join("\n");
}