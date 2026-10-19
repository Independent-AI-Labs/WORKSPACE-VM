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

For the installed deployment, `workspace/scripts/install-agentci` is the
provisioning seam: it renders the release `options.json` with an absolute
`policies` array pointing at `workspace/config/opencode/agentci/policies.yaml`.
The auto-discovered plugin entry reads that `options.json` next to its bundle,
so no additional OpenCode configuration is required and the plugin loads once.

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
or file content over 4 KiB, and incompatible event/action combinations. Match
fields are bounded by event to those the hook actually supplies:
`experimental.chat.messages.transform` accepts only `file`.

| Event | Actions |
|---|---|
| `tool.execute.before` | `block`, `allow`, `warn` |
| `tool.execute.after` | `warn` |
| `experimental.chat.system.transform` | `inject` |
| `experimental.chat.messages.transform` | `inject` |

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

`experimental.chat.messages.transform` receives no input fields and the mutable
in-memory message list for the current provider turn. For every matching
`inject` policy, AgentCI appends `AgentCI (<name>): <file contents>` as a
synthetic text part to every user message in the list. The hook runs on the
in-memory request projection only: the parts are never written to session
storage, so they are visible to the model but absent from the persisted
transcript. As with the system transform, injection is re-evaluated every
provider turn with no state retained across turns or compaction, and a missing
or unreadable configured file is a visible error rather than substituted
context.

Pre-execution prohibited-command policies use `tool.execute.before` and block
before execution. Post-command warning policies use `tool.execute.after` and
append guidance to the current tool output only. They are deterministic and do
not invoke a model or network service.

## Tests

Unit tests exercise schema validation, matching, policy order, command parsing,
post-command warnings, and per-turn file injection. Integration tests load the
packed TypeScript plugin through a temporary OpenCode configuration and verify
real hook dispatch and configured-file injection on consecutive provider turns.
`messages-inject.live.ts` runs the real `opencode` binary against an isolated
HOME/XDG root and a recording OpenAI-compatible upstream: it asserts the
configured note reaches the upstream request exactly once per user message only
when the policy is enabled, and that the note never appears in the persisted
session parts (`opencode db`). The same file benchmarks a static question with
the note enabled and disabled against the real model, reports response length
and words-per-sentence, and records the run as
`workspace/agentci/benchmarks/note-injection-<model>.md` so model response
statistics stay in-repo. Set `AGENTCI_LIVE_MODEL` to benchmark a specific model
and `AGENTCI_BENCH_SAMPLES` to change the sample count.
`npm run test:live` uses a temporary HOME/XDG root and a permission-checked
temporary OAuth credential copy; it neither uses nor changes normal OpenCode
configuration or state.
