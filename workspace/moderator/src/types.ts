export type Phase = "IDLE" | "OBSERVING" | "CLASSIFYING" | "CONTINUING" | "ERROR";

export type AgentMode = "build" | "answer";

export type BlockerSource = "operator-handoff" | "agent-blocked";

export type VerdictDecision = "AGENT_COMPLETE" | "AGENT_CONTINUING" | "AGENT_STALLED" | "AGENT_BLOCKED" | "AGENT_STOPPED";

export type ReasonCode = "WORK_COMPLETE" | "WORK_REMAINS" | "NO_PROGRESS" | "AWAITING_USER" | "AWAITING_OPERATOR" | "USER_STOP";

export interface Blocker {
  source: BlockerSource;
  originUserID: string | null;
}

export interface ContextFact {
  assistantID: string;
  userMessageID: string | null;
  agentMode: AgentMode;
  todosOpen: number;
}

export interface ModerationState {
  phase: Phase;
  inflightAssistantID: string | null;
  lastTerminalAssistantID: string | null;
  realUserCycleID: string | null;
  consecutiveNoProgressCount: number;
  blocker: Blocker | null;
  compactionActive: boolean;
  pendingContext: ContextFact | null;
}

export interface MessageInfo {
  id?: string;
  role: "user" | "assistant";
  parentID?: string;
  sessionID?: string;
  agent?: string;
  mode?: string;
  finish?: string;
  error?: unknown;
  summary?: boolean;
  time?: { created?: number };
  path?: { cwd?: string };
}

export interface MessagePart {
  type?: string;
  text?: string;
  synthetic?: boolean;
  tool?: string;
  metadata?: Record<string, unknown>;
  state?: {
    status?: string;
    input?: Record<string, unknown>;
    output?: string;
  };
}

export interface MessageFact {
  info: MessageInfo;
  parts: MessagePart[];
}

export interface TodoFact {
  content?: string;
  status?: string;
}

export interface Verdict {
  decision: VerdictDecision;
  reason: string;
  reasonCode: ReasonCode;
}

export interface ClassifierCapture {
  selector: string;
  sessionID: string | null;
  attempts: number;
  durationMs: number;
  input: Record<string, unknown> | null;
}

export interface ClassifierOutcome {
  verdict?: Verdict;
  error?: string;
  capture: ClassifierCapture;
}

export type DecisionType =
  | "status-busy"
  | "checking"
  | "moderation-complete"
  | "moderation-agent-blocked"
  | "moderation-user-stop"
  | "moderation-escalated"
  | "moderation-continue"
  | "moderation-error"
  | "root-handoff"
  | "blocker-discussion"
  | "ignored-outside-phase"
  | "ignored-nonterminal"
  | "ignored-assistant-error"
  | "ignored-plan-mode"
  | "ignored-compaction"
  | "ignored-newer-user"
  | "ignored-moderator-trace"
  | "ignored-duplicate"
  | "cancelled"
  | "new-user-cycle"
  | "trace-recorded"
  | "continuation-persisted"
  | "compaction-started"
  | "compaction-completed";

export type ToastKind = "checking" | "complete" | "agent-blocked" | "user-stop" | "operator-handoff" | "continuing" | "escalated" | "error";

export type Effect =
  | { type: "LOAD_CONTEXT" }
  | { type: "CLASSIFY" }
  | { type: "WRITE_TRACE"; verdict?: Verdict }
  | { type: "SEND_CONTINUATION"; verdict: Verdict }
  | { type: "VERIFY_PROMPT" }
  | { type: "SHOW_TOAST"; kind: ToastKind }
  | { type: "WRITE_DECISION"; decisionType: DecisionType; reason?: string };

export interface TurnFact {
  assistantID: string | null;
  userMessageID: string | null;
  agentMode: AgentMode;
  todosOpen: number;
  terminal: boolean;
  assistantPresent: boolean;
  duplicate: boolean;
  compaction: boolean;
  assistantError: boolean;
  userNewer: boolean;
  moderatorTrace: boolean;
  planMode: boolean;
  rootBlocked: boolean;
  blockerDiscussion: boolean;
  newCycle: boolean;
}

export type ModerationEvent = { sessionID?: string } & (
  | { type: "STATUS_BUSY" }
  | { type: "TURN_ENDED"; turn: TurnFact }
  | { type: "CONTEXT_LOADED"; turn: TurnFact; originUserID: string | null; todos: TodoFact[] }
  | { type: "VERDICT"; verdict: Verdict; capture: ClassifierCapture; originUserID: string | null }
  | { type: "CANCELLED"; reason: string }
  | { type: "CONTINUATION_PERSISTED" }
  | { type: "NEW_USER_CYCLE"; originUserID: string | null; sameBranch: boolean }
  | { type: "COMPACTION_STARTED" }
  | { type: "COMPACTION_COMPLETED" }
  | { type: "TRACE_PERSISTED" }
  | { type: "EFFECT_ERROR"; error: string }
  | { type: "REPLAY"; turn: TurnFact }
);

export interface TransitionMeta {
  previousPhase: Phase;
  event: string;
  nextPhase: Phase;
}

export interface TransitionResult {
  state: ModerationState;
  effects: Effect[];
  ignored: boolean;
  transition: TransitionMeta;
}
