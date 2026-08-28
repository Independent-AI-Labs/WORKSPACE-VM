import { chmod, lstat, mkdir, readdir, realpath, rename, unlink } from "node:fs/promises"
import { isAbsolute, join, relative } from "node:path"
import { EFFECT, EVENT, createInitialState, isValidState, transition } from "./local-response-moderator-machine.js"

const RETRY_MARKER = "⚠️ Local Moderator Continuation"
const TRACE_MARKER = "🔎 Local Moderator Decision"
const CONTINUE = "The work must be completed before stopping. Continue working now; do not merely explain the limitation."
const VERSION = "2026-08-10.1"
const script = `${import.meta.dir}/local-response-moderator.sh`
const config = await Bun.file(`${import.meta.dir}/config.json`).json()
export function stateRoot(stateHome, home = process.env.HOME) { return stateHome || join(home, ".local", "state") }
export const auditRoot = join(stateRoot(process.env.XDG_STATE_HOME), "opencode", "local-response-moderator")
let lastDecisionTimestamp = 0

export default {
  id: "local-response-moderator",
  server: async ({ client, $ }) => {
    const sessions = new Map()
    await restore(sessions)
    const record = (sessionID) => sessions.get(sessionID) ?? sessions.set(sessionID, { state: createInitialState(), queue: [], draining: false, nextBusyGeneration: 0 }).get(sessionID)
    const enqueue = (sessionID, event, first = false) => {
      const session = record(sessionID)
      session.queue[first ? "unshift" : "push"](Object.freeze({ ...event, sessionID }))
      if (!session.draining) void drain(sessionID, session)
    }
    const drain = async (sessionID, session) => {
      session.draining = true
      try {
        while (session.queue.length) {
          const event = session.queue.shift()
          const previousState = session.state
          const result = transition(previousState, event)
          session.state = result.state
          const auditDecisionID = decisionID()
          let audit
          const effectResults = []
          for (const effect of result.effects) {
            try {
                const startedAt = new Date().toISOString(), started = performance.now()
                const effectResult = await perform(sessionID, session, effect, { ...(result.event ?? event), auditDecisionID })
               if ((effect.type === EFFECT.WRITE_TRACE || effect.type === EFFECT.SEND_CONTINUATION) && effectResult?.messageID) session.state = { ...session.state, moderatorMessageIDs: [...(session.state.moderatorMessageIDs ?? []), effectResult.messageID] }
               const outcome = { effect: effect.type, status: "ok", result: effectResult?.type ? { event: effectResult.type } : effectResult ?? null, timing: { startedAt, completedAt: new Date().toISOString(), durationMs: performance.now() - started } }
              effectResults.push(outcome)
              if (effect.type === EFFECT.WRITE_DECISION) {
                audit = await writeDecision(sessionID, decisionRecord(effect, { ...(result.event ?? event), auditDecisionID }, previousState, result, effectResults))
                outcome.result = { path: audit.path }
              }
               if (audit) { audit.record.nextState = audit.record.stateSnapshot = session.state; audit.record.stateSnapshotBase64 = btoa(JSON.stringify(session.state)); await updateDecision(audit, effectResults) }
              if (effectResult?.type) enqueue(sessionID, effectResult, true)
            } catch (error) {
              const message = error instanceof Error ? error.message : String(error)
              console.error(`[local-response-moderator] ${message}`)
               effectResults.push({ effect: effect.type, status: "error", error: message, timing: { completedAt: new Date().toISOString() } })
               if (audit) { audit.record.nextState = audit.record.stateSnapshot = session.state; audit.record.stateSnapshotBase64 = btoa(JSON.stringify(session.state)); await updateDecision(audit, effectResults) }
              if (effect.type === EFFECT.WRITE_DECISION) throw error
              enqueue(sessionID, { type: EVENT.EFFECT_ERROR, error: message, context: result.event?.context }, true)
            }
          }
        }
      } finally {
        session.draining = false
        if (session.queue.length) void drain(sessionID, session)
      }
    }
    const perform = async (sessionID, session, effect, event) => {
      if (effect.type === EFFECT.LOAD_CONTEXT) return loadContext(sessionID, session, effect.generation)
      if (effect.type === EFFECT.WRITE_TRACE) return writeTrace(sessionID, session, effect, event)
      if (effect.type === EFFECT.SHOW_TOAST) return showToast(sessionID, effect, event)
      if (effect.type === EFFECT.CLASSIFY) return classifyEffect(sessionID, effect, event)
      if (effect.type === EFFECT.SEND_CONTINUATION) return sendContinuation(sessionID, event)
      if (effect.type === EFFECT.VERIFY_PROMPT) return verifyPrompt(sessionID, event)
      if (effect.type === EFFECT.WAIT_FOR_BUSY) return waitForBusy(sessionID, session, event)
      return null
    }
    const loadContext = async (sessionID, session) => {
      const [todoResult, messageResult] = await timeout(Promise.all([
        client.session.todo({ path: { id: sessionID } }),
          loadMessages(client, sessionID),
      ]), 15000, "session context request timed out")
      const todos = todoResult.data ?? []
        const messages = messageResult
        const latestUser = realUser(messages, session.state.moderatorMessageIDs)
        const latestMessage = latestUser
      const assistant = messages.filter((message) => message.info?.role === "assistant" && message.info?.parentID === latestUser?.info?.id).at(-1)
      const assistantIndex = assistant ? messages.indexOf(assistant) : -1
      const user = latestUser
      const assistantID = assistant?.info?.id
      const base = { todos, messages, assistantID, assistantResponse: text(assistant), retryCycle: orDefault(realUser(messages, session.state.moderatorMessageIDs)?.info?.id, "none"), blockerSource: session.state.blocker?.source ?? null, blockerOrigin: session.state.blocker?.originUserID ?? null }
      const blockerActive = session.state.blocker && inBranch(user, messages, session.state.blocker.originUserID)
      if (session.state.blocker && !blockerActive) base.blockerSource = base.blockerOrigin = null
      base.blockerDiscussionActive = Boolean(blockerActive)
      base.newCycle = base.retryCycle !== session.state.realUserCycleID
      base.requiredTodoPending = pending(todos)
      base.originUserID = user?.info?.id ?? base.retryCycle
      return {
        type: EVENT.CONTEXT_LOADED,
        terminal: assistant?.info?.finish === "stop",
        assistantPresent: Boolean(assistantID),
        duplicate: !assistantID || assistantID === session.state.lastTerminalAssistantID || assistantID === session.state.inflightAssistantID,
        compaction: Boolean(assistant?.info?.summary || assistant?.info?.mode === "compaction" || assistant?.info?.agent === "compaction"),
        build: assistant?.info?.agent === "build",
        planMode: assistant?.info?.mode === "plan",
        assistantError: Boolean(assistant?.info?.error),
        userNewer: assistantIndex < 0 || Boolean(latestUser && messages.indexOf(latestUser) > assistantIndex),
        moderatorTrace: moderatorMessage(latestMessage, session.state.moderatorMessageIDs),
        rootBlocked: sudo(text(assistant)),
        blockerBranch: Boolean(blockerActive),
        originUserID: base.originUserID,
        assistantID,
        realUserCycleID: base.retryCycle,
        newCycle: base.newCycle,
        context: base,
      }
    }
    const writeTrace = async (sessionID, session, effect, event) => {
      const context = event.context ?? {}
      const verdict = event.verdict
      const decisionID = event.auditDecisionID
      const passive = effect.decisionType === "BLOCKER DISCUSSION"
      const body = [TRACE_MARKER, "", `Decision: ${effect.decisionType}`, `Audit decision ID: ${decisionID}`, `Reason: ${verdict?.reason ?? traceReason(effect.decisionType, event)}`, passive ? "" : verdict ? `Task completion: ${orDefault(verdict.task_completion?.ruling, "FAIL")} - ${verdict.task_completion?.reason ?? verdict.reason}` : "", passive ? "" : verdict ? `Prompt adherence: ${orDefault(verdict.prompt_adherence?.ruling, "FAIL")} - ${verdict.prompt_adherence?.reason ?? verdict.reason}` : "", "This is an audit trace only. No agent response is requested."].filter((line, index) => line || index === 1).join("\n")
      const response = await client.session.prompt({ path: { id: sessionID }, body: { noReply: true, parts: [{ type: "text", text: labeled(body) }] } })
      const id = response.data?.info?.id
      return { messageID: id ?? null }
    }
    const showToast = async (sessionID, effect, event) => {
      const detail = toast(effect.kind, event)
      await Promise.race([client.tui.showToast({ body: { ...detail, message: labeled(detail.message) } }), Bun.sleep(2000)])
      return { shown: true }
    }
    const classifyEffect = async (sessionID, effect, event) => {
      const context = event.context
      const result = await classify(sessionID, context.todos, context.messages)
      if (result.error) throw new Error(result.error)
      return { type: EVENT.CLASSIFIER_RESULT, verdict: result.verdict, capture: result.capture, passiveBlockerDiscussion: context.blockerDiscussionActive, ...context, context }
    }
    const sendContinuation = async (sessionID, event) => {
      const verdict = event.verdict
      const prompt = labeled([RETRY_MARKER, "", `Decision: ${verdict.decision}`, `Reason: ${verdict.reason}`, `Task completion: ${orDefault(verdict.task_completion?.ruling, "FAIL")} - ${verdict.task_completion?.reason ?? verdict.reason}`, `Prompt adherence: ${orDefault(verdict.prompt_adherence?.ruling, "FAIL")} - ${verdict.prompt_adherence?.reason ?? verdict.reason}`, "Continue working and correct every failed item. Do not merely explain it.", CONTINUE].join("\n"))
      const response = await client.session.promptAsync({ path: { id: sessionID }, body: { parts: [{ type: "text", text: prompt }] } })
      return { type: EVENT.CONTINUATION_PERSISTED, context: event.context, messageID: response?.data?.info?.id ?? null }
    }
    const verifyPrompt = async (sessionID, event) => {
      if (!await persisted(sessionID, event.messageID)) throw new Error("continuation prompt was not persisted")
      return { persisted: true }
    }
    const waitForBusy = async (sessionID, session, event) => {
      const generation = session.state.busyGeneration
      for (let attempt = 0; attempt < 50; attempt += 1) { if (session.queue.some((queued) => queued.type === EVENT.STATUS_BUSY && queued.generation > generation)) return { type: EVENT.BUSY_VERIFIED, context: event.context }; await Bun.sleep(100) }
      return { type: EVENT.CONTINUATION_TIMEOUT, context: event.context }
    }
    const persisted = async (sessionID, needle) => {
      if (!needle) return false
      for (let attempt = 0; attempt < 5; attempt += 1) { const messages = (await client.session.messages({ path: { id: sessionID }, query: { limit: 20 } })).data ?? []; if (messages.some((message) => message.info?.id === needle && moderatorMessage(message, sessions.get(sessionID)?.state.moderatorMessageIDs))) return true; await Bun.sleep(100) }
      return false
    }
    const classify = async (sessionID, todos, messages) => {
      let last
      for (let retry = 0; retry <= 3; retry += 1) {
        last = await runClassifier(sessionID, todos, messages)
        if (!last.error || !last.formatError) return last
        await Bun.sleep(100)
      }
      return { ...last, error: "MiniCPM did not return the required decision YAML after three format retries." }
    }
    const runClassifier = async (sessionID, todos, messages) => {
      const id = crypto.randomUUID(), snapshot = `/tmp/local-response-moderator-${id}.json`, capture = `/tmp/local-response-moderator-${id}.yaml`
      await Bun.write(snapshot, JSON.stringify({ session_id: sessionID, todos, messages })); await Bun.write(capture, "")
      try {
        const result = await $`OPENCODE_MODERATOR_VERSION=${VERSION} OPENCODE_MODERATOR_CAPTURE=${capture} OPENCODE_MODERATOR_CONFIG=${import.meta.dir}/config.json bash ${script} < ${snapshot}`.quiet().nothrow()
        const raw = await Bun.file(capture).text()
        if (result.exitCode !== 0) { const error = `moderator script exited ${result.exitCode}: ${result.stderr.toString("utf8")}`; return { capture: raw, error, formatError: /invalid moderator (YAML|finish reason|reason code)|incomplete moderator YAML/.test(error) } }
        return { verdict: verdict(result.text()), capture: raw }
      } catch (error) { return { capture: await Bun.file(capture).text(), error: error instanceof Error ? error.message : String(error) } } finally { await unlink(snapshot); await unlink(capture) }
    }
    const eventHook = ({ event }) => {
      const sessionID = event.properties?.sessionID
      if (!isSessionID(sessionID)) return
      if (event.type === "session.status") { const session = record(sessionID), status = event.properties.status.type, generation = status === "busy" ? ++session.nextBusyGeneration : session.nextBusyGeneration; enqueue(sessionID, { type: status === "busy" ? EVENT.STATUS_BUSY : status === "idle" ? EVENT.STATUS_IDLE : `STATUS_${status}`, generation }); return }
      if (event.type === "session.compacted") enqueue(sessionID, { type: EVENT.COMPACTION_COMPLETED })
    }
    const enqueueSessionEvent = (sessionID, event) => { if (isSessionID(sessionID)) enqueue(sessionID, event) }
    return { event: eventHook, "experimental.session.compacting": async (input) => enqueueSessionEvent(input.sessionID, { type: EVENT.COMPACTION_STARTED }), "experimental.compaction.autocontinue": async (input) => enqueueSessionEvent(input.sessionID, { type: EVENT.COMPACTION_AUTOCONTINUE }) }
  },
}

const orDefault = (value, resolved) => value ?? resolved
function text(message) { return orDefault(message?.parts?.filter((part) => part.type === "text").map((part) => part.text).join("\n"), "") }
async function loadMessages(client, sessionID) { const history = [], seen = new Set(); let cursor; do { const page = await client.session.messages({ path: { id: sessionID }, query: cursor ? { limit: 200, cursor } : { limit: 200, order: "asc" } }); history.push(...(page.data ?? [])); cursor = page.cursor?.next; if (cursor && seen.has(cursor)) throw new Error("session message pagination cursor repeated"); if (cursor) seen.add(cursor) } while (cursor); return history }
function fact(message) { return message ? { id: message.info?.id ?? null, parentID: message.info?.parentID ?? null, role: message.info?.role ?? null, timestamp: message.info?.time?.created ?? message.info?.createdAt ?? null, text: text(message) } : null }
function realUser(messages, moderatorMessageIDs) { return messages.filter((message) => message.info?.role === "user" && !moderatorMessage(message, moderatorMessageIDs)).at(-1) }
function moderatorMessage(message, moderatorMessageIDs = []) { return typeof message?.info?.id === "string" && moderatorMessageIDs.includes(message.info.id) }
function sudo(value) { return [...value.matchAll(/```(?:bash|sh|shell|zsh)?\s*\n([\s\S]*?)```/gi)].some((match) => /(?:^|[;&|()]\s*|\b(?:if|then|do)\s+)sudo(?:\s|$)/m.test(match[1])) }
function pending(todos) { return todos.some((todo) => ["pending", "in_progress"].includes(todo.status) && todo.priority === "high") }
function inBranch(message, messages, origin) { for (let current = message; current; current = messages.find((item) => item.info?.id === current.info?.parentID)) if (current.info?.id === origin) return true; return false }
function labeled(value) { return `${value}\n\n[Moderator model: ${config.model}]` }
function traceReason(type, event) { return { ROOT_BLOCKED: "A fenced command block requires sudo; operator action is required.", ERROR: orDefault(event.error, "Moderation failed.") }[type] ?? orDefault(event.verdict?.reason, "Moderator decision.") }
function toast(kind) { return { checking: { title: "Local moderator", message: "Checking the completed response...", variant: "info", duration: 3000 }, passed: { title: "Local moderator: passed", message: "Task completion and prompt adherence passed.", variant: "success", duration: 5000 }, blocked: { title: "Local moderator: blocked", message: "The agent requires operator input before continuing.", variant: "warning", duration: 8000 }, "root-blocked": { title: "Local moderator: root blocked", message: "A privileged command requires operator action.", variant: "warning", duration: 8000 }, continuing: { title: "Local moderator: continuing", message: "MiniCPM reviewed the response and is prompting the agent to continue.", variant: "warning", duration: 6000 }, escalated: { title: "Local moderator: escalation", message: "Three consecutive no-progress decisions stopped automatic continuation.", variant: "error", duration: 8000 }, "continuation-error": { title: "Local moderator: continuation error", message: "The corrective prompt was persisted but the agent did not start a new turn.", variant: "error", duration: 8000 }, error: { title: "Local moderator: error", message: "Moderation failed to run; inspect the audit log.", variant: "error", duration: 8000 } }[kind] }
function verdict(value) { const lines = value.trim().split("\n").map((line) => line.trim()), decision = lines.find((line) => line.startsWith("decision: "))?.slice(10), code = lines.find((line) => line.startsWith("reason: "))?.slice(8); const reason = { COMPLETE: "All required work is complete.", WORK_REMAINS: "Required work or verification remains.", NO_PROGRESS: "The response did not make meaningful progress.", EXTERNAL_BLOCKER: "An external blocker requires operator action.", CLARIFICATION_REQUIRED: "Clarification is required before work can continue." }[scalar(orDefault(code, ""))]; if (!reason || !["PASS", "CONTINUE_PROGRESS", "CONTINUE_NO_PROGRESS", "BLOCKED"].includes(decision)) throw new Error("invalid YAML verdict: missing loop decision"); const ruling = decision === "PASS" ? "PASS" : "FAIL"; return { decision, reason, reasonCode: scalar(code), task_completion: { ruling, reason }, prompt_adherence: { ruling, reason } } }
function scalar(value) { return value.startsWith("'") ? value.slice(1, -1).replaceAll("''", "'") : value.startsWith('"') ? value.slice(1, -1).replaceAll('\\"', '"').replaceAll("\\\\", "\\") : value }
function decisionRecord(effect, event, previousState, result, effectResults) { const context = event.context ?? {}; const types = { "status-busy": "session-status", "status-idle": "session-status", classifying: "classifying", "moderation-pass": "moderation-pass", "moderation-blocked": "moderation-blocked", "moderation-fail": "moderation-fail", "moderation-escalated": "moderation-escalated", "root-blocked": "root-blocked", "blocker-discussion": "blocker-discussion", "compaction-started": "compaction-started", "compaction-completed": "compaction-completed", "moderation-error": "moderation-error" }; return { ...context, auditDecisionID: event.auditDecisionID, decisionType: types[effect.reason] ?? effect.reason, reason: effect.reason, verdict: event.verdict, classifierCapture: event.capture, classifier: { model: config.model, gateway: config.gateway_url, version: VERSION }, selectedFacts: { user: fact(context.messages?.find((message) => message.info?.id === context.originUserID)), assistant: fact(context.messages?.find((message) => message.info?.id === context.assistantID)), context: context.messages?.map(fact) ?? [] }, error: event.error, consecutiveNoProgressCount: result.state.consecutiveNoProgressCount, blockerDiscussionActive: Boolean(result.state.blocker), blockerSource: result.state.blocker?.source ?? null, blockerOrigin: result.state.blocker?.originUserID ?? null, previousState, event, effects: result.effects, effectResults, nextState: result.state, stateSnapshot: result.state, stateSnapshotBase64: btoa(JSON.stringify(result.state)) } }
function within(root, path) { const resolved = relative(root, path); return resolved !== "" && !resolved.startsWith("..") && !isAbsolute(resolved) }
async function privateDirectory(path) { await mkdir(path, { recursive: true, mode: 0o700 }); const status = await lstat(path); if (!status.isDirectory() || status.isSymbolicLink()) throw new Error(`audit directory is not a private directory: ${path}`); await chmod(path, 0o700) }
async function auditDirectory(sessionID) { await privateDirectory(auditRoot); const root = await realpath(auditRoot), directory = join(root, sessionID); if (!within(root, directory)) throw new Error("audit path escapes audit root"); await privateDirectory(directory); const resolved = await realpath(directory); if (!within(root, resolved)) throw new Error("audit path escapes audit root"); return resolved }
export async function writeDecision(sessionID, record) { if (!isSessionID(sessionID)) throw new Error("invalid session ID for audit path"); const decisionID = record.auditDecisionID, directory = await auditDirectory(sessionID), path = join(directory, `${decisionID}-${orDefault(record.assistantID, "none")}.yaml`); const audit = { path, record: { timestamp: new Date().toISOString(), version: VERSION, decisionID, ...record } }; await updateDecision(audit, record.effectResults); return audit }
async function updateDecision(audit, effectResults) { audit.record.effectResults = effectResults; const temporary = `${audit.path}.tmp-${crypto.randomUUID()}`; await Bun.write(temporary, JSON.stringify(audit.record, null, 2)); await chmod(temporary, 0o600); await rename(temporary, audit.path); await chmod(audit.path, 0o600) }
async function restore(sessions) { await privateDirectory(auditRoot); const root = await realpath(auditRoot), directories = await readdir(root, { withFileTypes: true }); await Promise.all(directories.filter((entry) => entry.isDirectory() && isSessionID(entry.name)).map(async (entry) => { const directory = join(root, entry.name); if (!within(root, directory)) throw new Error("audit path escapes audit root"); const files = (await readdir(directory)).filter((name) => name.endsWith(".yaml")).sort().reverse(); for (const file of files) { const path = join(directory, file), status = await lstat(path); if (!status.isFile() || status.isSymbolicLink() || !within(directory, path)) throw new Error(`audit record is not a regular file: ${path}`); const content = await Bun.file(path).text(); let encoded; try { encoded = JSON.parse(content).stateSnapshotBase64 } catch { encoded = content.match(/^stateSnapshotBase64: (\S+)$/m)?.[1] } if (!encoded) { await restoreError(entry.name, file, "missing state snapshot"); continue } try { const state = JSON.parse(atob(encoded)); if (isValidState(state)) { sessions.set(entry.name, { state, queue: [], draining: false, nextBusyGeneration: state.busyGeneration }); break } await restoreError(entry.name, file, "invalid state snapshot") } catch (error) { const message = error instanceof Error ? error.message : String(error); console.error(`[local-response-moderator] invalid state snapshot ${file}: ${message}`); await restoreError(entry.name, file, message) } } })) }
async function restoreError(sessionID, file, error) { const state = createInitialState(), auditDecisionID = decisionID(); await writeDecision(sessionID, { auditDecisionID, decisionType: "restore-error", reason: "corrupt-restore-record", restoreFile: file, error, effects: [], effectResults: [{ effect: "RESTORE", status: "error", error }], previousState: null, event: { type: "RESTORE" }, nextState: state, stateSnapshot: state, stateSnapshotBase64: btoa(JSON.stringify(state)) }) }
function decisionID() { lastDecisionTimestamp = Math.max(Date.now(), lastDecisionTimestamp + 1); return `${lastDecisionTimestamp}-${crypto.randomUUID()}` }
export function isSessionID(value) { return typeof value === "string" && /^[A-Za-z0-9_-]+$/.test(value) }
async function timeout(promise, duration, message) { let timer; try { return await Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(message)), duration) })]) } finally { clearTimeout(timer) } }
