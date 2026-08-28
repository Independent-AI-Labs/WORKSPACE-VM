# Research: OpenCode API Feasibility For AgentCI

**Date:** 2026-08-11  
**Status:** Informative source audit and architecture decision  
**Scope:** Current `projects/opencode` source; no installed-runtime claim

## Correction

The prior conclusion that V1 plugins cannot observe a normal Bash exit code was
wrong. A normal Bash result reaches `tool.execute.after`, whose runtime metadata
contains `exit: number | null`. The public V1 hook type describes metadata as an
untyped value, which hid that fact during the earlier incomplete review.

This document replaces that conclusion. AgentCI V1 is feasible for the accepted
numeric-exit CI trigger today; no OpenCode core patch is required for it.

## Required Facts

AgentCI requires command intent, session/call/part correlation, settled result
and exit evidence, policy intervention before execution, durable remediation
state, next-turn system context, and compaction retention.

| Fact | V1 hooks | V1 event path |
| --- | --- | --- |
| Bash command before execution | Yes | N/A |
| Normal Bash exit | Runtime metadata only | Completed tool part |
| Thrown/interrupted tool outcome | No terminal hook | Error tool part |
| Session/call/part correlation | Session and call IDs | Full tool part IDs |
| Pre-execution policy action | Yes | Too late |
| Per-turn context injection | Yes, experimental hook | N/A |
| Compaction context | Yes, experimental hook | Observe part updates |
| Ordered, awaited terminal delivery | Normal completion only | No, event dispatch is fire-and-forget |

## V1 Evidence

### Tool Lifecycle

`tool.execute.before` receives tool name, session ID, call ID, and mutable
arguments. `tool.execute.after` receives the same IDs, command arguments,
title, output, and metadata. See
`projects/opencode/packages/plugin/src/index.ts:266-281` and
`projects/opencode/packages/opencode/src/session/tools.ts:102-132`.

The Bash command is `before.output.args.command`. The Bash implementation
returns nonzero exits as normal results, with `metadata.exit`; timeout or abort
uses `exit: null`. See
`projects/opencode/packages/opencode/src/tool/shell.ts:542-594`.

`tool.execute.after` runs only after `item.execute` returns. A thrown or
interrupted tool skips it. This is the V1 gap, not normal nonzero Bash exit
handling.

### Tool-Part Events

`message.part.updated` carries a complete tool part with session ID, message
ID, part ID, call ID, tool name, and terminal completed or error state. See
`projects/opencode/packages/schema/src/v1/session.ts:259-325,612-620` and
`projects/opencode/packages/opencode/src/session/session.ts:637-645`.

The plugin manager forwards this event as an internal cast and does not await
handlers. See `projects/opencode/packages/opencode/src/plugin/index.ts:253-260`.
It is usable as observational evidence but cannot prove durable plugin handling
before process exit.

### Context And Compaction

`experimental.chat.system.transform` mutates the system prompt immediately
before provider submission. It has a session ID on the normal session path, but
that ID is optional because agent-generation calls omit it. See
`projects/opencode/packages/plugin/src/index.ts:291-296` and
`projects/opencode/packages/opencode/src/session/llm/request.ts:56-112`.

`experimental.session.compacting` receives the session ID and mutable context
or compaction prompt before summary generation. See
`projects/opencode/packages/plugin/src/index.ts:299-326` and
`projects/opencode/packages/opencode/src/session/compaction.ts:328-402`.

## Experimental APIs

The experimental V1 hooks are usable but are V1 plugin hooks, not a separate
durable event system. They provide system-prompt transformation, message-history
transformation, compaction context, automatic-continuation control, and final
text transformation. They do not add a typed terminal tool result contract.

Use system transformation and compaction only with a session ID. AgentCI must
skip calls without one rather than sharing context across sessions.

## Architecture Decision

### Use Existing V1 Numeric Exit Evidence

The accepted CI trigger is a direct supported Bash `git commit` or `git push`
with normal numeric `tool.execute.after` `metadata.exit`. A nonzero exit creates
one matching remediation record; a matching zero resolves it. Timeout, abort,
tool error, interruption, host failure, missing exit, and non-numeric exit do
nothing to CI remediation. Existing V1 before hooks remain the independent
policy boundary. Existing V1 system and compaction hooks remain the temporary
context path.

## Acceptance Research Plan

1. Run an isolated real-`oc` AgentCI test with a temporary database, temporary
   OpenCode configuration, and temporary plugin installation.
2. Verify normal nonzero exit, matching zero resolution, persistence/restart,
   session isolation, system injection, and compaction. Excluded terminal states
   must not create or clear CI remediation.
3. Run required explicit `npm run test:live` using `openai/gpt-5.6-luna` after the
   deterministic suite passes. It copies only test-user-owned mode-`0600`
   `${XDG_DATA_HOME}/opencode/auth.json` into temporary XDG data, uses destination
   directory mode `0700` and file mode `0600`, keeps credential content out of the
   environment and logs, confines refresh to that copy, and cleans up on every
   outcome. A missing or invalid credential fails the test rather than skipping it.
