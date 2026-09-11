# Specification: OpenCode Isolated Integration Tests

**Status:** Draft  
**Date:** 2026-08-12  
**Scope:** Real OpenCode tests without global configuration, database, plugin, or credential mutation

## Commands

Use the released wrapper for runtime evidence:

```bash
workspace/scripts/bin/oc --db "$OPENCODE_DB" -- run --model <provider/model> <prompt>
```

Use `workspace/scripts/bin/ocb` only to test the source-built OpenCode binary.
Both wrappers accept `--db NAME` or `--db=NAME` and pass the value unchanged as
`OPENCODE_DB`. `--` sends an upstream OpenCode command without task conversion.

Run AgentCI tests from `workspace/agentci/` with `npm test`,
`npm run test:release`, and `npm run test:live`.

## Temporary Root

Every runtime test creates one private temporary root with `umask 077` and sets
these values before launching OpenCode:

```text
HOME=<root>/home
XDG_CONFIG_HOME=<root>/config
XDG_DATA_HOME=<root>/data
XDG_STATE_HOME=<root>/state
XDG_CACHE_HOME=<root>/cache
OPENCODE_CONFIG_DIR=<root>/opencode-config
OPENCODE_DB=<root>/data/opencode.db
```

The test creates only temporary configuration, state, database, provider, and
plugin paths. It removes the root on success and failure and proves removal.

## Plugin Contract

The test packages AgentCI from `workspace/agentci/`, installs it only under the
temporary root, and configures the resulting local plugin entrypoint. A runtime
test must assert OpenCode discovery plus an observable plugin effect; package
import alone is not runtime evidence.

Moderator runtime tests install only the moderator release under temporary
`XDG_CONFIG_HOME` and configure that temporary release. They must not load or
modify the user's installed moderator.

## Provider Contract

Deterministic tests use a temporary local provider that emits the intended
provider and Bash-tool sequence. They assert the actual OpenCode plugin hook
effect, not only process exit.

`npm run test:live` uses `openai/gpt-5.6-luna`. Before launch it copies only the
test user's normal `${XDG_DATA_HOME}/opencode/auth.json` to temporary XDG data.
The source must be owned by the test user and mode `0600`; the destination
directory is `0700` and file is `0600`. The test never logs credential content
or passes it through environment variables. A missing or invalid source
credential fails the command. Token refresh may affect only the temporary copy.

## Evidence Levels

| Level | Required proof |
| --- | --- |
| Source | Direct tests call exported behavior. |
| Isolated runtime | Real `oc` or `ocb` loads the temporary plugin and observes its named effect. |
| Live provider | Isolated runtime receives the required bounded provider response. |
| Deployment | Operator-installed release evidence. |

An isolated runtime or live provider result never establishes normal deployment.
