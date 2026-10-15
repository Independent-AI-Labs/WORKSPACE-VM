export type Phase = "IDLE" | "OBSERVING" | "CLASSIFYING" | "CONTINUING" | "ERROR";

export type BlockerSource = "operator-handoff" | "agent-blocked";

export interface BlockerScope {
  source: BlockerSource;
  originUserID: string | null;
}

export interface CompactionState {
  active: boolean;
  generation: number;
}

export interface ModerationState {
  phase: Phase;
  busyGeneration: number;
  pendingIdleGenerations: number[];
  inflightAssistantID: string | null;
  lastTerminalAssistantID: string | null;
  realUserCycleID: string | null;
  consecutiveNoProgressCount: number;
  blocker: BlockerScope | null;
  compaction: CompactionState;
}

export type VerdictDecision = "AGENT_COMPLETE" | "AGENT_CONTINUING" | "AGENT_STALLED" | "AGENT_BLOCKED";

export type ReasonCode = "WORK_COMPLETE" | "WORK_REMAINS" | "NO_PROGRESS" | "AWAITING_USER" | "AWAITING_OPERATOR";

export interface Ruling {
  ruling: "PASS" | "FAIL";
  reason: string;
}

export interface Verdict {
  decision: VerdictDecision;
  reason: string;
  reasonCode: ReasonCode;
  task_completion: Ruling;
  prompt_adherence: Ruling;
}

export type Effect =
  | { type: "LOAD_CONTEXT"; generation: number }
  | { type: "WRITE_DECISION"; decisionType: string }
  | { type: "WRITE_TRACE"; verdict?: Verdict }
  | { type: "SHOW_TOAST"; kind: string }
  | { type: "CLASSIFY" }
  | { type: "SEND_CONTINUATION"; verdict: Verdict }
  | { type: "VERIFY_PROMPT" }
  | { type: "WAIT_FOR_BUSY" };

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

export interface ContextSnapshot {
  terminal: boolean;
  assistantPresent: boolean;
  duplicate: boolean;
  compaction: boolean;
  planMode: boolean;
  build: boolean;
  assistantError: boolean;
  userNewer: boolean;
  moderatorTrace: boolean;
  rootBlocked: boolean;
  blockerDiscussionActive: boolean;
  realUserCycleID: string | null;
  realUserPrompts: string[];
  assistantResponse: string;
}

export type ModerationEvent = { sessionID?: string } & (
  | { type: "STATUS_BUSY"; generation?: number }
  | { type: "STATUS_IDLE"; generation?: number }
  | {
      type: "CONTEXT_LOADED";
      generation?: number;
      todos?: TodoFact[];
      assistantID?: string | null;
      terminal?: boolean;
      assistantPresent?: boolean;
      duplicate?: boolean;
      compaction?: boolean;
      planMode?: boolean;
      build?: boolean;
      assistantError?: boolean;
      userNewer?: boolean;
      moderatorTrace?: boolean;
      rootBlocked?: boolean;
      blockerDiscussionActive?: boolean;
      blockerBranch?: boolean;
      realUserCycleID?: string | null;
      newCycle?: boolean;
      originUserID?: string | null;
    }
  | { type: "CLASSIFIER_RESULT"; verdict: Verdict; originUserID?: string | null }
  | { type: "CONTINUATION_PERSISTED" }
  | { type: "BUSY_VERIFIED" }
  | { type: "CONTINUATION_TIMEOUT" }
  | { type: "TRACE_PERSISTED"; messageID?: string | null }
  | { type: "COMPACTION_STARTED" }
  | { type: "COMPACTION_AUTOCONTINUE" }
  | { type: "COMPACTION_COMPLETED" }
  | { type: "EFFECT_ERROR"; error?: string }
);

export interface TodoFact {
  id?: string;
  content?: string;
  status?: string;
  priority?: string;
}

export interface MessagePartFact {
  type: string;
  text?: string;
}

export interface MessageInfoFact {
  id?: string;
  parentID?: string;
  role?: string;
  agent?: string;
  mode?: string;
  summary?: boolean;
  error?: unknown;
  finish?: string;
  time?: { created?: number };
}

export interface MessageFact {
  info: MessageInfoFact;
  parts: MessagePartFact[];
}