# Specification: AgentCI

**Document ID:** WS-SPEC-AGENTCI-v1.0
**Status:** Draft
**Date:** 2026-08-12
**Requirements:** [REQ-AGENTCI](../requirements/REQ-AGENTCI.md)

## Package

`workspace/agentci/` is the complete TypeScript package. It exports one
OpenCode-discoverable server plugin and contains its schemas, reducers, and
tests.

## Plugin Options

The deployment configuration supplies explicit paths:

```json
{
  "plugin": [["file:///path/to/agentci/dist/server.js", {
    "policies": ["/path/to/policies.yaml"]
  }]]
}
```

`policies` is required and is the only policy-discovery mechanism. Relative
paths resolve relative to the declaring OpenCode configuration.

## Policy Schema

Each YAML file contains a `policies` array. Every policy has this shape:

```yaml
name: warn-failed-command
event: tool.execute.after
match:
  tool: bash
  exit: nonzero
action: warn
message: Fix the underlying command failure before continuing.
```

Optional match fields are `tool`, `command_regex`, `exit` (`zero` or
`nonzero`), `repository_path`, `session_id`, and `file`. `file` is required for
`inject`; it is read only after a policy matches. The loader rejects duplicate
names, unknown fields, invalid regexes, a pattern over 256 characters, message
or file content over 4 KiB, and incompatible event/action combinations.

| Event | Actions |
|---|---|
| `tool.execute.before` | `block`, `allow`, `warn` |
| `tool.execute.after` | `warn` |
| `experimental.chat.system.transform` | `inject` |

Policies run in declaration order. A matching `block` stops further evaluation
for that hook. Other matching policies append their bounded effect once.

## Runtime Inputs And Outputs

`tool.execute.before` receives the real tool identifier, arguments, session ID,
call ID, and repository path. AgentCI evaluates only these supplied fields and
returns a block or warning through the supported OpenCode hook output.

`tool.execute.after` receives the same metadata plus normal completion metadata.
AgentCI appends a warning only when a policy matches a finite numeric exit.

`experimental.chat.system.transform` receives a session ID and mutable system
context. AgentCI appends every matching configured file on every provider turn.
It retains no injection state across turns or compaction. It never creates a
user message, a new agent turn, or substitute context for a missing file.

Pre-execution prohibited-command policies use `tool.execute.before` and block
before execution. Post-command warning policies use `tool.execute.after` and
append guidance to the current tool output only. They are deterministic and do
not invoke a model or network service.

## Tests

Unit tests exercise schema validation, matching, policy order, command parsing,
post-command warnings, and per-turn file injection. Integration tests load the
packed TypeScript plugin through a temporary OpenCode configuration and verify
real hook dispatch and configured-file injection on consecutive provider turns.
`npm run test:live` uses a temporary HOME/XDG root and a permission-checked
temporary OAuth credential copy; it neither uses nor changes normal OpenCode
configuration or state.
