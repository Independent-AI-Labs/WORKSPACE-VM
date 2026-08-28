# REQ-AGENTCI: TypeScript OpenCode Policy Plugin

**Document ID:** WS-REQ-AGENTCI-v1.0
**Status:** Draft
**Date:** 2026-08-12
**Specification:** [SPEC-AGENTCI](../specifications/SPEC-AGENTCI.md)

## Goal

AgentCI is a TypeScript OpenCode plugin that evaluates configured local policy
files against real OpenCode hooks. Its only inputs are configured files, current
session messages, real tool metadata, and actual shell command outcomes.

## Policy Files

1. AgentCI SHALL load policy files only from explicit plugin configuration.
   There is no implicit repository scan or generated policy.
2. A policy SHALL contain `name`, `event`, `match`, `action`, and `message`.
   `name` is unique across configured files.
3. `event` SHALL be one of `tool.execute.before`, `tool.execute.after`, or
   `experimental.chat.system.transform`.
4. `match` SHALL use only hook fields supplied by OpenCode: tool name, command
   text, numeric exit status, repository path, session ID, and configured file
   path. Regexes are syntax-checked and policy text and patterns are bounded.
5. `action` SHALL be one of `block`, `allow`, `warn`, or `inject`.
   An unknown field, event, action, or invalid regex SHALL reject plugin startup
   with a visible error.
6. Policy files and configured context files are source inputs. AgentCI SHALL
   never edit, generate, or deploy them.

## Hook Behavior

7. Before a tool executes, AgentCI SHALL evaluate matching
   `tool.execute.before` policies against the real tool name and arguments.
   `block` prevents execution and surfaces its message. `warn` surfaces its
   message.
8. After a tool completes, AgentCI SHALL evaluate matching `tool.execute.after`
   policies against the real command, normal numeric exit status, and bounded
   stdout/stderr. A missing or non-numeric exit is not a successful outcome.
9. A matching `warn` policy SHALL append its message to the completed tool
   output. It SHALL not persist state, inject a later turn, or rerun a command.
10. An `inject` policy SHALL read only its configured file path and inject its
   bounded contents when the real hook input matches. Missing or unreadable
   configured files are visible errors; AgentCI SHALL not substitute other
   context.
11. A matching `inject` policy SHALL append its configured file on every provider
    turn. AgentCI SHALL not deduplicate injection across turns or retain
    injection state through compaction. Completion and continuation decisions
    belong to the moderator or automation that consumes the current context.

## Separation Of Enforcement

12. A post-command warning policy MAY match a normal numeric shell exit and append
    corrective guidance to that tool result.
13. AgentCI SHALL NOT ship any built-in prohibited-command list, security
    invariant, or default enforcement. Git-safety, privilege, hook-bypass, and
    source-quality invariants are owned by WORKSPACE-GUARD, the CI pre-commit
    hooks, and OpenCode permissions. AgentCI never duplicates them.
14. Pre-execution `block`/`warn`/`allow` policies are user-configured session
    policies only. They are deterministic and require no classifier, model, or
    network service.

## Implementation And Evidence

15. AgentCI source, schemas, plugin, and tests SHALL be TypeScript under
    `workspace/agentci/` with strict compilation.
16. The release artifact SHALL be built only from `workspace/agentci/`.
17. Tests SHALL prove policy validation, pre-execution block/warn behavior,
    post-command warnings, per-turn file injection, and real OpenCode plugin
    discovery from an isolated temporary configuration.
18. The live-provider test SHALL run only from isolated temporary HOME and XDG
    roots. It may copy the normal OpenCode OAuth credential file only after
    validating ownership and mode `0600`; copied credentials remain mode `0600`,
    never enter environment variables or logs, and are deleted with the temporary
    root.
