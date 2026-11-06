# REQ-AGENTCI-RESPONSE-MODERATION: Standalone Response Moderator

**Date:** 2026-11-04
**Status:** Draft for prototype implementation
**Type:** Requirements
**Supersedes:** All earlier revisions of this requirement

## 1. Purpose

Define a standalone response moderator for OpenCode.

The moderator watches completed Build responses. It decides whether the agent is
complete, still working, stalled, blocked, or stopped. It then records the
decision and applies the required control action.

The default model SHALL be `gpt-5.6-luna`, selected through OpenCode.

Configuration SHALL provide an ordered list of OpenCode model selectors. Each
selector SHALL be a provider and model pair. The moderator SHALL try selectors in
order. A valid verdict stops the list. A prompt or format failure moves to the
next selector. When every selector is exhausted, the moderator SHALL fail closed:
moderation error, no completion, no continuation.

The moderator SHALL use only OpenCode model facilities. It SHALL NOT call
upstream model APIs directly.

The moderator is a prototype first. It MUST later replace the existing AgentCI
moderation path through one composition point.

## 2. Scope

### In scope

- A new standalone package at `workspace/moderator/`.
- A pure finite-state machine.
- An OpenCode event adapter.
- An in-process classifier that calls `LLM.generate`.
- A deterministic effect policy.
- State persistence and audit records.
- A replay command for real sessions.
- Unit, integration, and live end-to-end tests.

### Out of scope

- Direct calls to external model providers outside OpenCode.
- Root access or privilege escalation.
- A new daemon.
- A new database.
- A new HTTP route.
- Shell commands that start or manage inference servers.
- Reuse of the broken AgentCI moderation implementation.

## 3. Terms

- **Terminal response**: the newest assistant message with `finish == "stop"`.
- **Real user message**: a user message that is not injected, not synthetic, and
  not a moderator trace.
- **Cycle**: the work span started by one real user message.
- **Eligible response**: a terminal response that passes every deterministic
  eligibility rule in section 4.2.
- **Verdict**: one decision and one reason code from section 4.4.
- **Effect**: an action selected by the finite-state machine.
- **Prototype**: the standalone package, not the installed AgentCI plugin.

## 4. Functional Requirements

### 4.1 Event Observation

1. The moderator SHALL expose OpenCode plugin hooks through a server entry point.
2. The moderator SHALL consume `session.status` events with status values
   `busy` and `idle`.
3. The moderator SHALL consume compaction lifecycle events from
   `experimental.session.compacting`, `experimental.compaction.autocontinue`,
   and `session.compacted`.
4. The moderator SHALL treat every event as untrusted input and SHALL validate
   session identifiers, event names, and message shapes.
5. The moderator SHALL process events per session in arrival order.
6. A duplicate idle event for an already-moderated assistant message SHALL NOT
   start a second classification.

### 4.2 Eligibility

7. The moderator SHALL select only the newest assistant message in the session.
8. The moderator SHALL moderate only a terminal response with
   `info.finish == "stop"`.
9. The moderator SHALL ignore a response with a nonterminal finish such as
    `tool-calls` and SHALL record `ignored-nonterminal`.
10. The moderator SHALL ignore a response with `info.error` and SHALL record
    `ignored-assistant-error`. This is not cancellation. Cancellation is the
    `CANCELLED` event and SHALL record `cancelled`.
11. The moderator SHALL moderate responses produced by the `build` and `answer`
    agents.
12. The moderator SHALL ignore plan-mode responses with `ignored-plan-mode`.
13. The moderator SHALL ignore compaction responses, summary responses, and
    `compaction` agents with `ignored-compaction`.
14. The moderator SHALL ignore a response when a newer real user message already
    exists and SHALL record `ignored-newer-user`.
15. The moderator SHALL ignore a response that is a moderator trace with
    `ignored-moderator-trace`.
16. The moderator SHALL suppress a response whose assistant identity equals
    `lastTerminalAssistantID` and SHALL record `ignored-duplicate`. A following
    moderator line is not a duplicate. `inflightAssistantID` is not duplicate
    suppression. A missing real-user ancestor SHALL NOT ignore the response.
    A continuation reply SHALL be classified when it is a new terminal `build`
    or `answer` assistant.

### 4.3 Context Selection

17. The moderator SHALL walk `parentID` links backward from the judged assistant
    response. It SHALL NOT use the flat session list.
18. The walk SHALL skip injected continuation messages, moderator traces,
    synthetic moderation parts, synthetic compaction notes, and summary
    messages. Those messages SHALL NOT end the walk and SHALL NOT count as
    chained user text.
19. The moderator SHALL use chronological message order from the OpenCode client.
20. The moderator SHALL NOT infer order from message identifier text.
21. The walk SHALL include every assistant message and tool call from the judged
    response back to, but not including, the first real user message. Assistant
    text in that span SHALL be kept. Each tool call SHALL include its name,
    input, and output.
22. Each tool output SHALL be truncated to `MODERATOR_TOOL_OUTPUT_CHARS`. The
    default is 1024. The cut SHALL be marked. The judged assistant text SHALL
    NOT be truncated.
23. If the messages immediately before that user message are also real user
    messages, with no assistant message between them, the moderator SHALL
    include all of them. It SHALL NOT include any assistant message from before
    that chain.
24. An empty or whitespace-only latest real user message SHALL be represented by
    an explicit continue sentinel. It SHALL NOT be treated as a stop.
25. The moderator SHALL include the todo list as it exists at classification
    time, and one mode line for the response agent mode.

### 4.4 Classifier

26. The classifier SHALL import and call `LLM.generate` from `packages/llm` in
    the same process. It SHALL NOT spawn a process, create a session, start a
    server, or take a separate URL or credential variable. The selector is
    `provider/model`. The route comes from that provider in `opencode.jsonc`.
27. The classifier SHALL use OpenCode provider and model selectors from the
    moderator model selection source.
28. The classifier SHALL NOT persist a transcript. The only classifier record
    SHALL be the audit log.
29. The classifier SHALL use a dedicated system prompt.
30. The classifier SHALL disable all tools except the verdict tool.
31. The verdict tool SHALL accept exactly one decision and one reason.
32. The only valid decision and reason pairs SHALL be:
    - `AGENT_COMPLETE` / `WORK_COMPLETE`
    - `AGENT_CONTINUING` / `WORK_REMAINS`
    - `AGENT_STALLED` / `NO_PROGRESS`
    - `AGENT_BLOCKED` / `AWAITING_USER`
    - `AGENT_BLOCKED` / `AWAITING_OPERATOR`
    - `AGENT_STOPPED` / `USER_STOP`
33. A missing verdict tool call, an invalid decision, an invalid reason, or a
    mismatched pair SHALL be a format failure.
34. The classifier SHALL make one `LLM.generate` call per selector per cycle. A
    format failure or a timeout SHALL move to the next selector. A timeout
    SHALL start another cycle through the selector list. The cycle limit is
    `MODERATOR_TIMEOUT_CYCLES`. The default is 3. A format failure SHALL NOT
    start another cycle. A valid verdict SHALL stop the list. `packages/llm`
    SHALL own transport retries.
35. When every selector fails, the moderator SHALL fail closed with a visible
    moderation error. It SHALL NOT become `AGENT_COMPLETE`.
36. The classifier input SHALL contain:
    - the assistant messages in the walk, with the latest response as the
      decision target
    - each tool call in that walk, with name, input, and truncated output
    - the chained real user messages that end the walk
    - the todo list at classification time
    - one mode message for the response agent mode
37. The counted size SHALL be the system prompt plus that input. The limit is
    `MODERATOR_CTX`. The default is 32768. A request over that limit SHALL
    throw. The moderator SHALL NOT call the model, SHALL NOT emit a verdict,
    SHALL show the error to the user, and SHALL write one
    `Automated Moderation:` record into the working session.
38. The classifier SHALL decide from the full assistant response. The adapter
    SHALL NOT rewrite a verdict by keyword matching or text parsing after the
    verdict tool returns.

### 4.5 Classification Rules

The classifier SHALL apply this order and stop at the first match.

39. `AGENT_BLOCKED` with `AWAITING_OPERATOR` when the response asks the operator
    to perform an external action that the agent cannot perform. Examples include
    click, press, play, launch, observe, watch, listen, hold, grant access,
    check, confirm, run a command, or report a result.
40. `AGENT_BLOCKED` with `AWAITING_USER` when the response asks the user to
    answer a question, choose, decide, approve, or clarify, and rule 39 does not
    apply.
41. Rule 39 SHALL win over rule 40 when the response asks both for an action and
    for an answer.
42. A handoff SHALL stand even when the task is unfinished and even when the
    response promises later work.
43. A question that the response answers itself in the same response SHALL NOT
    be a handoff.
44. `AGENT_STOPPED` with `USER_STOP` when the latest real user message explicitly
    tells the agent to halt, stop, cancel, abort, wait, or not continue.
45. A push to proceed such as `go`, `proceed`, `execute`, `continue`, or `do it`
    SHALL NOT be a stop.
46. A question about stopping SHALL NOT be a stop.
47. `AGENT_COMPLETE` with `WORK_COMPLETE` when the response fully satisfies the
    request.
48. `AGENT_CONTINUING` with `WORK_REMAINS` when work remains and the agent can
    continue on its own.
49. `AGENT_STALLED` with `NO_PROGRESS` when the agent can act but made no
    progress.
50. Listing remaining work, proposing a plan, or naming the agent's own next
    step SHALL NOT be a handoff.

### 4.6 Control Policy

51. `AGENT_COMPLETE` SHALL leave the session idle.
52. `AGENT_COMPLETE` SHALL write one passive status line to the transcript.
53. `AGENT_CONTINUING` and `AGENT_STALLED` SHALL send a corrective prompt to the
    same session.
54. The corrective prompt SHALL state that the work appears unfinished and that
    the agent must continue unless the operator or system requested a halt.
55. The corrective prompt SHALL be sent as one message with two parts:
    - a synthetic directive delivered to the model
    - a short visible note for the transcript
56. Both parts SHALL carry moderation metadata.
57. Moderator-generated messages SHALL be excluded from real user context by
    metadata, not by text.
58. `AGENT_BLOCKED` SHALL leave the session idle and write one passive status
    line.
59. `AGENT_STOPPED` SHALL leave the session idle and SHALL NOT write a transcript
    line.
60. `AGENT_STOPPED` SHALL reset the no-progress count.
61. `AGENT_CONTINUING` SHALL reset the no-progress count.
62. `AGENT_STALLED` SHALL increment the no-progress count.
63. Three consecutive `AGENT_STALLED` verdicts in one cycle SHALL stop automatic
    continuation and record `moderation-escalated`.
64. Every moderated agent mode SHALL append one mode-specific message to the
    classifier input. Mode messages SHALL NOT override a classifier verdict.
    `AGENT_BLOCKED` SHALL stand in every mode.
65. A new real user message SHALL start a new cycle and reset the no-progress
    count.
66. A new cycle SHALL clear blocker scope unless the message belongs to the
    blocker branch.

### 4.7 Blockers

67. The moderator SHALL inspect fenced shell-like code blocks before
    classification.
68. A fenced block containing `sudo` as a command token SHALL produce
    `root-handoff`.
69. `root-handoff` SHALL write one passive status line and SHALL NOT send a
    corrective prompt.
70. `root-handoff` SHALL start blocker-discussion scope.
71. A valid `AGENT_BLOCKED` verdict SHALL also start blocker-discussion scope.
72. Blocker scope SHALL store the originating real user message identity.
73. Blocker scope SHALL apply only to later responses in the same branch.
74. A response inside blocker scope SHALL record a passive `blocker-discussion`
    decision without a classifier call.
75. `AGENT_COMPLETE` in the blocker branch SHALL clear blocker scope.
76. An unrelated user task SHALL clear blocker scope.

### 4.8 Compaction

77. The moderator SHALL mark compaction active before compaction processing.
78. The moderator SHALL clear compaction state after successful compaction.
79. Compaction SHALL NOT consume, reset, or increment the real-user cycle.
80. A response that follows auto-continuation after compaction SHALL remain
    eligible for normal moderation.

### 4.9 Persistence and Audit

81. The moderator SHALL persist per-session state in the XDG state directory.
82. State writes SHALL be atomic.
83. Restored state SHALL be validated before use.
84. An invalid state document SHALL produce a visible moderation error.
85. Restore SHALL clear in-flight classification state.
86. An unfinished classification SHALL be re-evaluated after restart.
87. Every decision SHALL write an audit record with:
    - timestamp
    - session identity
    - assistant identity
    - event
    - decision
    - reason
    - previous phase
    - next phase
    - effects
    - effect results
    - previous state
    - next state
88. Audit records SHALL NOT contain credentials.
89. Audit records SHALL be append-only.

### 4.10 Replay

90. The moderator SHALL provide `oc --run-mod [sessionID]` and `oc --run-mod-force [sessionID]`.
91. Those commands SHALL open that session in the working OpenCode process. Plugin `server()` SHALL register hooks and return.
92. Replay SHALL read messages from that process's `session.messages` client.
93. Opening that session SHALL start the replay. Replay SHALL NOT wait for a new `session.status` idle event.
94. `--run-mod` SHALL revert the moderator trace after the terminal assistant, then apply section 4.6. `--run-mod-force` SHALL apply section 4.6 without revert.
95. Continuation SHALL be one `promptAsync` message with the two parts required by rules 55 and 56.
96. A replay failure SHALL show a toast and write an audit error. A successful replay SHALL write a `REPLAY` audit record and SHALL call `LLM.generate`.

### 4.11 Provisioning and Configuration

97. The package SHALL provide a production bundle entry point.
98. The user-configurable runtime source SHALL contain an ordered list of
    OpenCode provider and model selectors.
99. The runtime source SHALL reject an empty model selector list.
100. The runtime source SHALL reject a selector that OpenCode does not expose.
101. The installer SHALL seed `gpt-5.6-luna` as the default selector.
102. The installer SHALL verify that the bundle and runtime source match the
     source.
103. The installed release SHALL be activated atomically.
104. The moderator SHALL NOT read configuration from an environment variable
     that can override the user-configurable runtime model source.

## 5. Non-Functional Requirements

105. The implementation SHALL use TypeScript.
106. The implementation SHALL run on the repository Node.js version.
107. Every source file SHALL stay below 512 lines.
108. The implementation SHALL NOT use banned patterns or suppression comments.
109. The implementation SHALL NOT use `unsafe`.
110. The implementation SHALL NOT use `unwrap` equivalents in production paths.
111. The implementation SHALL surface every error.
112. The moderator SHALL keep every verdict transition in one finite-state machine.
113. The package SHALL NOT import from `workspace/agentci/`.
114. The package SHALL have no runtime dependency on the old moderation code.
115. The finite-state machine SHALL be pure and free of I/O.
116. The adapter SHALL own all I/O.
117. The classifier SHALL be replaceable through one interface.
118. The audit store SHALL be replaceable through one interface.
119. The audit record SHALL capture the selector, attempt count, and model
     response identity for every classifier run.
120. A verdict SHALL apply only to the assistant identity that produced it.
121. Classification SHALL have a finite timeout.
122. The timeout SHALL be visible as an error.
123. The moderator SHALL show client-visible feedback for checking, completion,
     blocking, stopping, continuation, escalation, and error through the toast
     queue in Section 11.
124. Transcript status lines SHALL be exactly one line.
125. Transcript status lines SHALL NOT contain decision codes, reason codes, or
     model names.

## 6. Evidence

The following evidence informed this requirement.

- A 50-case fixture was audited against real OpenCode transcripts.
- Eleven clear label errors were corrected.
- Five ambiguous cases were replaced with clearer real transcripts.
- The fixture contains 15 synthetic cases and 35 real transcript cases.
- Exact verdict scoring exposed a consistent ambiguity between
  `AWAITING_OPERATOR` and `AWAITING_USER`.
- The fixture exposed false-complete cases where a response offered a plan but
  performed no work.
- The fixture exposed false-stop cases where an emphatic `continue` instruction
  was misread as a halt.
- Default model result on the fixture:
    - `gpt-5.6-luna`: 45/50
- Local open-weight model results on the fixture:
    - MiniCPM5-1B: 22/50
    - MiniCPM5-2B FP8 to Q8_0: 29/50
    - LFM2.5-8B-A1B Q4_K_M: 23/50
    - LFM2.5-24B-A2B Q4_K_M: 42/50
- The extracted transcripts are the end-to-end cases.
- Each case SHALL run through the adapter, the FSM, and in-process `LLM.generate`.
- A side scorer that calls the classifier outside the adapter is not acceptance evidence.

## 7. Acceptance

The prototype is accepted when all of these are true.

126. Unit tests cover every state transition and every effect.
127. Integration tests drive the adapter with a real client interface and
     verify persisted state, decisions, and effects.
128. Every extracted transcript runs through the adapter and in-process `LLM.generate`.
129. That run writes the trace, the continuation decision, and `decisions.jsonl`.
130. The classifier capture includes the appended mode message.
131. The default model is `gpt-5.6-luna`.
132. Hosted and local selectors pass the same verdict parse test.
133. Type checking passes.
134. All tests pass.
135. The production bundle builds.
136. The installed release verifies.
137. The requirement and specification match the prototype behavior.
138. The old AgentCI moderation implementation is deleted only after the
     prototype passes its own acceptance tests.
139. The TUI entry exposes only model selection.

## 8. Migration

140. The prototype SHALL expose the same plugin hook surface as the production
     moderation adapter.
141. Replacement SHALL occur at one composition point.
142. The old implementation SHALL NOT be used as a comparison target.
143. The old implementation SHALL be deleted.
144. The replacement SHALL be one commit.
145. The replacement commit SHALL include tests, configuration, installer, and
     documentation.
146. A failed replacement SHALL be reported and SHALL NOT be hidden.

## 9. Model Selection

147. The plugin SHALL provide a `/moderator` command inside OpenCode.
148. `/moderator` SHALL open the existing OpenCode model picker UI.
149. The selected model SHALL replace only the topmost moderator model selector.
150. The remaining moderator model selectors SHALL remain unchanged.
151. The selection SHALL persist and apply to subsequent moderation calls without
     reinstalling or restarting the plugin.
152. `oc --set-mod` and `oc --set-mod-list` SHALL be aliases for one command.
153. Both aliases SHALL accept comma-separated `provider/model` selectors.
154. Both aliases SHALL replace the full moderator model selector list.
155. The plugin and the CLI SHALL validate selectors against the OpenCode
     provider and model registry.
156. An empty list, an invalid selector, or a duplicate selector SHALL fail
     without writing.
157. The plugin and the CLI SHALL use one user-configurable runtime model source.
158. Model selection SHALL NOT edit the installed release.
159. `/moderator` SHALL show the current topmost selector.
160. A missing selection source SHALL be an explicit startup error.

## 10. Model Selection Acceptance

161. `/moderator` opens the OpenCode model picker.
162. The picker selection replaces only the topmost selector.
163. `oc --set-mod` and `oc --set-mod-list` produce the same result.
164. The comma-separated syntax replaces the full selector list.
165. Invalid selectors fail without writing.
166. The selection survives restart.
167. The installed release is not modified by selection changes.

## 11. Toast Feedback

168. The moderator SHALL show checking, completion, blocking, stopping,
     continuation, escalation, and error feedback through one client-visible
     toast queue.
169. The toast queue SHALL be first-in, first-out.
170. The queue SHALL show one toast at a time.
171. A new toast SHALL NOT replace a toast that is already visible.
172. Each toast SHALL remain visible for its own duration before the next toast
     is shown.
173. The queue SHALL be owned by one plugin instance and SHALL accept toasts from
     every session.
174. Deleting a session SHALL remove that session's pending toasts.
175. The queue SHALL be bounded. When full, the oldest pending toast SHALL be
     dropped.
176. A toast failure SHALL use the existing moderation error path and SHALL NOT
     block later toasts.
177. The queue SHALL use only an in-memory array and promise sequencing.
178. The queue SHALL use the state duration for both the toast and its own
     wait.
