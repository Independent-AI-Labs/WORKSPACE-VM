import { modeMessage } from "./prompt.ts";
import type { AgentMode, MessageFact, TodoFact } from "./types.ts";

export const EMPTY_USER_PROMPT = "Continue the unfinished work.";
export const MODERATOR_CTX_DEFAULT = 32768;
export const MODERATOR_TOOL_OUTPUT_CHARS_DEFAULT = 1024;
const MODERATION_MARKER = "Automated Moderation:";
const INJECTED_MESSAGE = new RegExp(`^[^\\p{L}\\p{N}]*${MODERATION_MARKER}`, "u");
const ROOT_BLOCK_FENCE = /```(?:bash|sh|shell|zsh)?\s*\n([\s\S]*?)```/gi;
const ROOT_BLOCK_COMMAND = /(?:^|[;&|()]\s*|\b(?:if|then|do)\s+)sudo(?:\s|$)/m;

export function assistantText(message: MessageFact): string {
  return message.parts
    .filter((part) => part.type === "text" && part.synthetic !== true && typeof part.text === "string")
    .map((part) => part.text ?? "")
    .join("\n")
    .trim();
}

export function isSyntheticUser(message: MessageFact): boolean {
  if (message.info.role !== "user") return false;
  if (message.info.summary === true) return true;
  return message.parts.some((part) => part.synthetic === true
    && (part.metadata?.compaction_continue === true || part.metadata?.moderation === true));
}

export function isInjectedUser(message: MessageFact): boolean {
  if (message.info.role === "user" && message.parts.some((part) => part.synthetic === true && part.metadata?.moderation === true)) return true;
  return INJECTED_MESSAGE.test(assistantText(message));
}

export function isTerminal(message: MessageFact): boolean {
  const info = message.info;
  return info.time?.created !== undefined && (info.finish === "stop" || info.summary === true);
}

export function isPlan(message: MessageFact): boolean {
  return message.info.mode === "plan" || message.info.agent === "plan";
}

export function isAnswer(message: MessageFact): boolean {
  return message.info.mode === "answer" || message.info.agent === "answer";
}

export function isCompaction(message: MessageFact): boolean {
  return message.info.summary === true || message.info.agent === "compaction" || message.info.mode === "compaction";
}

export function newestModeratedAssistant(messages: readonly MessageFact[]): MessageFact | undefined {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message.info.role !== "assistant") continue;
    return message;
  }
  return undefined;
}

export function realUserAncestor(assistant: MessageFact | undefined, messages: readonly MessageFact[]): MessageFact | undefined {
  const byID = new Map(messages.map((message) => [message.info.id ?? "", message]));
  const visited = new Set<string>();
  let current: MessageFact | undefined = assistant;
  while (current) {
    const id = current.info.id ?? "";
    if (visited.has(id)) throw new Error(`moderator detected a parent cycle at message '${id}'`);
    visited.add(id);
    if (current.info.role === "user" && !isInjectedUser(current) && !isSyntheticUser(current)) return current;
    current = current.info.parentID !== undefined ? byID.get(current.info.parentID) : undefined;
  }
  return undefined;
}

export function inBranch(message: MessageFact | undefined, messages: readonly MessageFact[], originID: string | null): boolean {
  if (message === undefined || originID === null) return false;
  const byID = new Map(messages.map((candidate) => [candidate.info.id ?? "", candidate]));
  const visited = new Set<string>();
  let current: MessageFact | undefined = message;
  while (current) {
    const id = current.info.id ?? "";
    if (visited.has(id)) throw new Error(`moderator detected a parent cycle at message '${id}'`);
    visited.add(id);
    if (id === originID) return true;
    current = current.info.parentID !== undefined ? byID.get(current.info.parentID) : undefined;
  }
  return false;
}

export function toolOutputCharLimit(): number {
  const raw = process.env.MODERATOR_TOOL_OUTPUT_CHARS;
  if (raw === undefined || raw.length === 0) return MODERATOR_TOOL_OUTPUT_CHARS_DEFAULT;
  if (!/^[1-9][0-9]*$/.test(raw)) throw new Error(`MODERATOR_TOOL_OUTPUT_CHARS must be a positive integer, got '${raw}'`);
  return Number(raw);
}

export function truncateToolOutput(text: string): string {
  const limit = toolOutputCharLimit();
  if (text.length <= limit) return text;
  return `${text.slice(0, limit)}\n[truncated]`;
}

function skipped(message: MessageFact): boolean {
  return isInjectedUser(message) || isSyntheticUser(message) || isCompaction(message);
}

function parentOf(message: MessageFact, byID: Map<string, MessageFact>): MessageFact | undefined {
  return message.info.parentID === undefined ? undefined : byID.get(message.info.parentID);
}

function toolLine(part: MessageFact["parts"][number]): string | null {
  if (part.type !== "tool" || typeof part.tool !== "string") return null;
  const input = part.state?.input === undefined ? "" : JSON.stringify(part.state.input);
  return `${part.tool} input=${input} output=${truncateToolOutput(part.state?.output ?? "")}`;
}

export function selectWindow(assistant: MessageFact | undefined, messages: readonly MessageFact[]): { response: string; prompts: string[]; toolActivity: string[] } {
  if (assistant === undefined) return { response: "", prompts: [EMPTY_USER_PROMPT], toolActivity: [] };
  const byID = new Map(messages.map((message) => [message.info.id ?? "", message]));
  const visited = new Set<string>();
  const assistants: MessageFact[] = [];
  let current: MessageFact | undefined = assistant;
  while (current) {
    const id = current.info.id ?? "";
    if (visited.has(id)) throw new Error(`moderator detected a parent cycle at message '${id}'`);
    if (!skipped(current) && current.info.role === "user") break;
    visited.add(id);
    if (!skipped(current) && current.info.role === "assistant") assistants.push(current);
    current = parentOf(current, byID);
  }
  const prompts: string[] = [];
  while (current) {
    const id = current.info.id ?? "";
    if (visited.has(id)) throw new Error(`moderator detected a parent cycle at message '${id}'`);
    visited.add(id);
    if (skipped(current)) {
      current = parentOf(current, byID);
      continue;
    }
    if (current.info.role !== "user") break;
    const text = assistantText(current).trim();
    prompts.unshift(text.length > 0 ? text : EMPTY_USER_PROMPT);
    current = parentOf(current, byID);
  }
  const toolActivity: string[] = [];
  for (const message of assistants) {
    for (const part of [...message.parts].reverse()) {
      const line = toolLine(part);
      if (line !== null) toolActivity.push(line);
    }
  }
  const response = assistants.map((message) => assistantText(message)).filter((text) => text.length > 0).join("\n\n");
  return { response, prompts: prompts.length > 0 ? prompts : [EMPTY_USER_PROMPT], toolActivity };
}

export function collectToolActivity(assistant: MessageFact | undefined, messages: readonly MessageFact[]): string[] {
  return selectWindow(assistant, messages).toolActivity;
}

export function detectsRootBlock(text: string): boolean {
  for (const match of text.matchAll(ROOT_BLOCK_FENCE)) {
    if (ROOT_BLOCK_COMMAND.test(match[1])) return true;
  }
  return false;
}

export function buildCaseState(input: {
  todos: readonly TodoFact[];
  previousResponse: string;
  userMessages: readonly string[];
  toolActivity: readonly string[];
  agentMode: AgentMode;
}): string {
  const sections: string[] = [
    "The agent's latest response (judge this):",
    input.previousResponse,
  ];
  if (input.toolActivity.length > 0) {
    sections.push("", "Tool calls:", ...input.toolActivity.map((entry) => `- ${entry}`));
  }
  sections.push(
    "",
    "User request(s):",
    input.userMessages.length > 0
      ? input.userMessages.map((message) => `- ${message.trim().length > 0 ? message : EMPTY_USER_PROMPT}`).join("\n")
      : "- (none recorded)",
  );
  if (input.todos.length > 0) sections.push("", "Tracked todos:", summarizeTodos(input.todos));
  sections.push("", modeMessage(input.agentMode));
  const text = sections.join("\n");
  assertFitsModeratorContext(text);
  return text;
}

export function moderatorContextLimit(): number {
  const raw = process.env.MODERATOR_CTX;
  if (raw === undefined || raw.length === 0) return MODERATOR_CTX_DEFAULT;
  if (!/^[1-9][0-9]*$/.test(raw)) throw new Error(`MODERATOR_CTX must be a positive integer, got '${raw}'`);
  return Number(raw);
}

export function assertFitsModeratorContext(text: string): void {
  const limit = moderatorContextLimit();
  const tokens = Math.ceil(text.length / 4);
  if (tokens > limit) throw new Error(`moderator context is ${tokens} tokens and MODERATOR_CTX is ${limit}`);
}

export function summarizeTodos(todos: readonly TodoFact[]): string {
  return todos.map((todo) => `- [${todo.status ?? "unknown"}] ${todo.content ?? "(untitled)"}`).join("\n");
}
