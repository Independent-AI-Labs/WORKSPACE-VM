# Specification: Agent Policy Engine

**Document ID:** AMI-SPEC-POLICY-v1.0
**Status:** Draft
**Date:** 2026-06-08
**Classification:** Internal — Enterprise
**Requirements:** [REQ-AGENT-POLICY](REQ-AGENT-POLICY.md)
**References:**
- opencode Plugin Hooks Interface (`@opencode-ai/plugin`, 24 hook types)
- A2A Protocol Specification v1.0
- EU AI Act (Regulation (EU) 2024/1689)
- [SPEC-HOOKS](../docs/archive/v2/specifications/SPEC-HOOKS.md) (V2 Hook Validation Pipeline)
- [SPEC-EXTENSIONS](../docs/archive/v2/specifications/SPEC-EXTENSIONS.md) (Extension Registry)

---

## Overview

The Agent Policy Engine is a declarative, YAML-driven governance system for opencode agents. It replaces the current shell-scripted JS-array-parsing `rules`/`hooks` tooling with:

1. **A YAML Policy DSL** — unified Event → Match → Action schema covering all 24 opencode hook types
2. **Bash + yq Rendering Pipeline** — validates YAML, converts to `policies.json` via `yq`, deploys alongside a static plugin JS
3. **A Static Plugin JS** — written once, tested once, never regenerated; loads `policies.json` at runtime via `fs.readFileSync`
4. **Domain-Specific CLIs** — `rules`, `guards`, `tool-guards`, `shell-guards`, `system-rules` for per-domain editing
5. **A Profile System** — save, load, share, and switch between named policy bundles
6. **An Audit Trail** — tamper-evident JSONL log written by the static plugin at runtime

**Implementation stack:** Bash (CLIs + shared library) + `yq` (YAML → JSON conversion) + static JavaScript (runtime plugin). Zero Python VMs, zero code generation.

---

## Artifact Persistence

The system mirrors the current `template.js → userfile.js → deploy` pattern exactly:

```
workspace/config/opencode/policies/
├── template/                         ← TRACKED in git (immutable, seeded on first use)
│   ├── rules.template.yaml           ← 5 default context injection rules
│   ├── guards.template.yaml          ← 1 default speculation-words guard
│   ├── tool-guards.template.yaml     ← (empty) — placeholder for tool guardrails
│   ├── shell-guards.template.yaml    ← (empty) — placeholder for shell guardrails
│   ├── system-rules.template.yaml    ← (empty) — placeholder for system rules
│   └── profiles/
│       ├── standard.template.yaml    ← built-in standard profile
│       ├── strict.template.yaml      ← built-in strict profile
│       └── lenient.template.yaml     ← built-in lenient profile
├── rules.yaml                        ← GITIGNORED — user's working copy (seeded from template)
├── guards.yaml                       ← GITIGNORED — user's working copy
├── tool-guards.yaml                  ← GITIGNORED — user's working copy
├── shell-guards.yaml                 ← GITIGNORED — user's working copy
├── system-rules.yaml                 ← GITIGNORED — user's working copy
└── profiles/                         ← GITIGNORED — user profiles
    └── my-custom.yaml

workspace/config/opencode/plugins/
├── add-user-message-context.js       ← TRACKED in git (static, written once)
└── policies.json                     ← GITIGNORED (rendered from userfiles by yq)

~/.config/opencode/plugins/
├── add-user-message-context.js       ← deployed static plugin
└── policies.json                     ← deployed policy data
```

**Seeding:** On first `rules` invocation, if `rules.yaml` does not exist, copy `template/rules.template.yaml` → `rules.yaml`. Same for each domain CLI via `_init_userfile`. After seeding, the template is never touched again.

**Gitignore boundary:** `*.yaml` directly in `policies/`, `profiles/*.yaml` (user profiles), and `plugins/policies.json` are all gitignored. Only `template/` and `add-user-message-context.js` are tracked.

---

## Architecture

### System Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  workspace/config/opencode/policies/                         │
│  ├── template/                  ← TRACKED (immutable)        │
│  │   ├── rules.template.yaml    ← seeded on first use        │
│  │   ├── guards.template.yaml                                │
│  │   └── profiles/                                           │
│  ├── rules.yaml                 ← GITIGNORED (userfile)      │
│  ├── guards.yaml                ← GITIGNORED                 │
│  ├── tool-guards.yaml           ← GITIGNORED                 │
│  ├── profiles/                                              │
│  │   └── my-custom.yaml         ← GITIGNORED (user profile)  │
└──────────────┬──────────────────────────────────────────────┘
               │  policy render (yq merges userfiles → policies.json)
               ▼
┌─────────────────────────────────────────────────────────────┐
│  workspace/config/opencode/plugins/                           │
│  ├── add-user-message-context.js    ← TRACKED (static)       │
│  └── policies.json                 ← GITIGNORED (rendered)   │
└──────────────┬──────────────────────────────────────────────┘
               │  policy apply (cp both files)
               ▼
┌─────────────────────────────────────────────────────────────┐
│  ~/.config/opencode/plugins/                                  │
│  ├── add-user-message-context.js    ← deployed static plugin  │
│  └── policies.json                 ← deployed policy data    │
│                                                               │
│  ~/.config/opencode/logs/                                     │
│  └── policy-decisions.jsonl        ← Runtime audit trail     │
└─────────────────────────────────────────────────────────────┘
```

### Component Overview

```
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│   rules CLI  │  │  guards CLI  │  │ tool-guards  │  ...
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────┬───────┴─────────────────┘
                 │  source
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  lib/context.sh              ← Shared bash library            │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ _yq_query()       _insert_policy()   _delete_policy()    ││
│  │ _validate()       _deploy()          _remind()           ││
│  │ _render_json()    _audit()           _resolve_profile()  ││
│  │ _render_json() uses yq:  yq -o=json '.' *.yaml           ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  policy CLI   ← Lifecycle: validate / render / apply          │
│  profile CLI  ← Save / load / list / delete profiles         │
└─────────────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│  add-user-message-context.js  ← STATIC plugin (never changes) │
│  policies.json               ← RENDERED by yq (YAML→JSON)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. YAML Policy DSL Schema

### 1.1 Top-Level File Structure

```yaml
# rules.yaml — Context injection rules (user-message scope)
# All policy domain files follow this top-level structure.
version: "1"
name: "rules"                              # domain identifier
description: "Context injection rules for user messages"

policies:                                  # array of policy objects
  - name: no-premature-conclusions
    description: "Prevent agent from jumping to conclusions"
    enabled: true
    event: chat.messages.transform
    scope: user-message
    priority: 0
    agent: "*"
    match:
      - field: text
        operator: regex
        value: ".+"
        flags: ""
    action:
      type: inject
      system_prompt: |
        ## DO NOT JUMP TO CONCLUSIONS WITHOUT EXHAUSTING ALL ONLINE
        (EXA SEARCH) AND LOCAL (DOCUMENTATION, SOURCE CODE, ETC.)
        RESOURCES — MAKE SURE YOU HAVE ENOUGH KNOWLEDGE BEFORE
        GENERATING A RESPONSE. BE PROACTIVE!

  - name: auto-route-effort
    description: "Route to thorough approach"
    enabled: true
    event: chat.messages.transform
    scope: user-message
    priority: 0
    agent: "*"
    match:
      - field: text
        operator: regex
        value: ".+"
    action:
      type: inject
      system_prompt: |
        ## ALWAYS TAKE THE PROPER, LONG ROUTE EVEN WHEN YOU DON'T FEEL LIKE IT
```

### 1.2 Policy Object Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string (kebab-case) | **Yes** | — | Unique policy identifier within the domain file. Pattern: `[a-z][a-z0-9._-]+`. |
| `description` | string | No | `""` | Human-readable purpose. Included in audit logs and `policy show`. |
| `enabled` | boolean | No | `true` | `false` → skipped during rendering. |
| `event` | HookEvent | **Yes** | — | opencode hook event name. One of the 24 defined hook types. |
| `scope` | string | No | — | Refines matching within the event: `user-message`, `assistant-message`, `system`, `shell`, `file`, `tool-call`. The static plugin uses this to dispatch to the correct handler logic. |
| `priority` | integer | No | `0` | Higher values evaluate first. Within equal priority, declaration order prevails. |
| `agent` | string | No | `"*"` | Agent filter. `"*"` = all agents. Specific name = scoped to that agent. |
| `match` | MatchCondition[] | No | `[]` | AND conditions. Empty = always matches (fire on every event). |
| `match_groups` | MatchCondition[][] | No | — | OR-of-ANDs. If present, `match` is ignored. |
| `action` | ActionBlock | **Yes** | — | What to do when conditions match. |

### 1.3 Hook Event Enumeration

All 24 opencode hook types from `@opencode-ai/plugin` Hooks interface + PluginV2:

```yaml
event: chat.messages.transform        # Before LLM context sent (messages array mutable)
event: chat.system.transform          # Before system prompt finalized (system[] mutable)
event: chat.message                   # User sends message (message + parts mutable)
event: chat.params                    # Before LLM request (temperature, topP, maxOutputTokens mutable)
event: chat.headers                   # Before LLM request (headers mutable)
event: command.execute.before         # Before slash command runs (parts mutable)
event: tool.execute.before            # Before tool execution (args mutable, can block)
event: tool.execute.after             # After tool execution (title, output, metadata mutable)
event: tool.definition                # When tool schema sent to LLM (description, parameters mutable)
event: shell.env                      # Before shell/PTY spawn (env vars injectable)
event: permission.ask                 # Permission check (status: ask|deny|allow mutable)
event: experimental.text.complete     # After LLM finishes text block (text mutable)
event: experimental.session.compacting       # Before compaction (context[], prompt? mutable)
event: experimental.compaction.autocontinue  # After compaction (enabled boolean)
event: event                         # Subscribe to all system events (fire-and-forget)
event: config                        # Receive config at init (mutable providers/agents)
# PluginV2 hooks (core-level)
event: catalog.transform              # Modify provider/model catalog
event: account.switched               # React to auth account switch
event: aisdk.sdk                      # Override AI SDK provider module
event: aisdk.language                 # Override AI SDK language model
```

### 1.4 Match Condition Fields

```yaml
match:
  - field: text             # Dot-path into the event's input context
    operator: regex         # regex | equals | contains | in | starts_with | ends_with | glob
    value: "pattern"        # Pattern or value to match against
    flags: ""               # Regex flags: "" | "i" | "m" | "s" | "im" etc. (ignored for non-regex)
```

| Operator | Semantics | Example |
|----------|-----------|---------|
| `regex` | POSIX ERE match | `value: "rm\\s+-rf\\s+/"` |
| `equals` | Exact string equality | `value: "Bash"` |
| `contains` | Substring match | `value: "sudo"` |
| `in` | Set membership (comma-separated) | `value: "Bash,Write,Edit"` |
| `starts_with` | Prefix match | `value: "infra/"` |
| `ends_with` | Suffix match | `value: ".py"` |
| `glob` | Glob (fnmatch) pattern | `value: "**/*.env"` |

**Common field paths** (by event):

| Event | Available Fields |
|-------|-----------------|
| `chat.messages.transform` | `text` (message content), `role` (user/assistant/system) |
| `tool.execute.before` | `tool_name`, `args.command`, `args.file_path`, `args.content` |
| `tool.execute.after` | `tool_name`, `args.*`, `output.text`, `title` |
| `shell.env` | `cwd`, `session_id` |
| `chat.params` | `model.providerID`, `model.modelID`, `agent` |
| `command.execute.before` | `command`, `arguments` |

Match conditions use AND logic. All conditions in the `match` array must be satisfied for the policy to trigger.

`match_groups` provides OR-of-ANDs:
```yaml
match_groups:
  - - field: tool_name          # Group 1 (AND): tool is Bash AND command contains rm
      operator: equals
      value: "Bash"
    - field: args.command
      operator: regex
      value: "rm.*-rf.*/"
  - - field: tool_name          # Group 2 (AND): tool is Write AND path ends with .env
      operator: equals
      value: "Write"
    - field: args.file_path
      operator: ends_with
      value: ".env"
```

Any group fully matching triggers the policy.

### 1.5 Action Block

```yaml
action:
  type: inject | block | allow | warn | ask | modify | env | run
  # type-specific fields:
  system_prompt: |            # for inject: system prompt text (markdown)
    ## Multi-line content
  reason: "Blocked: ..."      # for block/ask: explanation
  context: "guide.md"         # for inject: optional file reference for context
  fields:                     # for modify: field overrides
    maxOutputTokens: 8000
    temperature: 0.3
  variables:                  # for env: environment variables
    GITHUB_TOKEN: "$env:GITHUB_TOKEN"
    NPM_TOKEN: "$env:NPM_TOKEN"
  command: "script.sh"        # for run: script to execute
```

| Action | Compatible Events | Effect |
|--------|-------------------|--------|
| `inject` | `chat.messages.transform`, `chat.system.transform`, `experimental.session.compacting` | Add `system_prompt` text to system context |
| `block` | `tool.execute.before`, `command.execute.before`, `permission.ask` | Block the operation; show `reason` |
| `allow` | `permission.ask`, `tool.execute.before` | Explicitly permit (override lower-priority policies) |
| `warn` | `tool.execute.before`, `chat.messages.transform` | Allow but log warning with `reason` |
| `ask` | `tool.execute.before`, `permission.ask` | Pause for human approval; show `reason` |
| `modify` | `chat.params`, `chat.headers`, `tool.execute.before`, `tool.execute.after`, `shell.env`, `experimental.text.complete` | Modify output fields in place |
| `env` | `shell.env` | Inject environment variables |
| `run` | `tool.execute.before`, `tool.execute.after`, `command.execute.before` | Execute script for custom logic |

**Event-Action Compatibility Matrix:**

| Event | inject | block | allow | warn | ask | modify | env | run |
|-------|--------|-------|-------|------|-----|--------|-----|-----|
| `chat.messages.transform` | ✓ | — | — | ✓ | — | ✓ | — | — |
| `chat.system.transform` | ✓ | — | — | — | — | ✓ | — | — |
| `tool.execute.before` | — | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| `tool.execute.after` | — | — | — | ✓ | — | ✓ | — | ✓ |
| `shell.env` | — | — | — | — | — | ✓ | ✓ | — |
| `chat.params` | — | — | — | — | — | ✓ | — | — |
| `chat.headers` | — | — | — | — | — | ✓ | — | — |
| `permission.ask` | — | ✓ | ✓ | — | ✓ | — | — | — |
| `experimental.text.complete` | — | — | — | — | — | ✓ | — | — |

---

## 2. Static Plugin + JSON Rendering

### 2.1 Architecture Principle

The plugin JS file is **static** — written once, tested once, version-controlled, never regenerated. It loads `policies.json` at runtime via `fs.readFileSync`. The "render" step is purely YAML → JSON conversion via `yq`. This eliminates the entire code generation layer: no Python scripts, no JS templating, no injection vulnerabilities.

### 2.2 Render Pipeline

```
policy render
  │
  ├── 1. Validate all userfile YAMLs (rules.yaml, guards.yaml, ...)
  │      policy validate (schema check + event-action compat)
  │
  ├── 2. Merge all userfile YAML policies into policies.json via yq:
  │      yq eval-all '
  │        .policies | map(select(.enabled != false))
  │        | sort_by(.priority) | reverse
  │      ' "$POLICY_DIR"/*.yaml -o=json > "$PLUGINS_DIR"/policies.json
  │
  │      Note: templates in template/ are NOT read during rendering.
  │      Only userfiles (the gitignored *.yaml directly in policies/) are merged.
  │
  └── 3. Output: plugins/policies.json — flat array of policy objects
```

### 2.3 Deploy Pipeline

```
policy apply
  │
  ├── 1. policy render (produces policies.json)
  │
  ├── 2. cp add-user-message-context.js → ~/.config/opencode/plugins/
  │      cp policies.json               → ~/.config/opencode/plugins/
  │
  └── 3. Display active policy count + restart reminder
```

### 2.4 Static Plugin JS Structure

The static plugin (`add-user-message-context.js`) is committed to git and never modified by any CLI command. Its structure:

```javascript
// ── Load policies at init ──
const fs = require("fs");
const path = require("path");

let POLICIES = [];
try {
  const policyPath = path.join(__dirname, "policies.json");
  POLICIES = JSON.parse(fs.readFileSync(policyPath, "utf-8"));
} catch (e) {
  console.error("[ami-policy] Failed to load policies.json:", e.message);
}

// ── Match engine (static, generic) ──
function getField(obj, path) { /* dot-path traversal */ }
function evaluateConditions(conditions, context) { /* generic condition evaluator */ }
function evaluateMatchGroups(groups, context) { /* OR-of-ANDs evaluator */ }

// ── Audit trail ──
const auditEntries = [];
function auditLog(policy, context, matched, action, detail) { /* append to array */ }
function flushAudit() { /* write auditEntries to JSONL */ }

// ── opencode plugin export ──
export const amiContext = async () => {
  return {
    "experimental.chat.messages.transform": async (_input, output) => {
      const policies = POLICIES.filter(p =>
        p.event === "chat.messages.transform" && p.enabled
      );
      const injections = [];
      for (const msg of output.messages) {
        for (const policy of policies) {
          if (policy.scope === "user-message" && msg.info.role !== "user") continue;
          if (policy.scope === "assistant-message" && msg.info.role !== "assistant") continue;
          for (const part of msg.parts) {
            if (part.type !== "text" || !part.text?.trim()) continue;
            const ctx = { role: msg.info.role, text: part.text };
            const matched = policy.match_groups
              ? evaluateMatchGroups(policy.match_groups, ctx)
              : evaluateConditions(policy.match, ctx);
            if (matched) {
              if (policy.action.type === "inject") injections.push(policy.action.system_prompt);
              if (policy.action.type === "warn") console.error(`[POLICY WARN] ${policy.name}`);
              auditLog(policy, ctx, true, policy.action.type, "");
            }
          }
        }
      }
      globalThis.__amiInjections = injections;
    },

    "experimental.chat.system.transform": async (_input, output) => {
      const injections = globalThis.__amiInjections || [];
      for (const policy of POLICIES.filter(p =>
        p.event === "chat.system.transform" && p.enabled
      )) {
        if (policy.action.type === "inject") injections.push(policy.action.system_prompt);
      }
      for (const inj of injections) output.system.push(inj);
      globalThis.__amiInjections = [];
    },

    "tool.execute.before": async (input, output) => {
      for (const policy of POLICIES.filter(p =>
        p.event === "tool.execute.before" && p.enabled
      ).sort((a, b) => b.priority - a.priority)) {
        const ctx = { tool_name: input.tool, ...expandArgs(input, output.args) };
        const matched = policy.match_groups
          ? evaluateMatchGroups(policy.match_groups, ctx)
          : evaluateConditions(policy.match, ctx);
        if (matched) {
          auditLog(policy, ctx, true, policy.action.type, "");
          switch (policy.action.type) {
            case "block": throw new Error(`[POLICY BLOCK] ${policy.name}: ${policy.action.reason}`);
            case "allow": return;
            case "ask": return { __ami_ask: true, policy: policy.name, reason: policy.action.reason };
            case "modify": applyModifications(output.args, policy.action.fields); break;
          }
        }
      }
    },

    "shell.env": async (input, output) => {
      for (const policy of POLICIES.filter(p =>
        p.event === "shell.env" && p.enabled
      )) {
        const ctx = { cwd: input.cwd, sessionID: input.sessionID };
        const matched = policy.match_groups
          ? evaluateMatchGroups(policy.match_groups, ctx)
          : evaluateConditions(policy.match, ctx);
        if (matched && policy.action.type === "env") {
          for (const [k, v] of Object.entries(policy.action.variables)) {
            output.env[k] = resolveEnvVar(v);
          }
        }
      }
    },

    // ... additional hook handlers for tool.execute.after, chat.params,
    //     chat.headers, command.execute.before, experimental.text.complete,
    //     permission.ask, etc. — each following the same pattern:

    "dispose": async () => { flushAudit(); },
  };
};
```

### 2.5 Hook Event → opencode Hook Function Mapping

The static plugin maps policy `event` field values to opencode hook function names. This mapping is coded once in the static plugin, not generated:

| Policy `event` | opencode Hook Function | Handler Present? |
|----------------|------------------------|------------------|
| `chat.messages.transform` | `experimental.chat.messages.transform` | Always (core) |
| `chat.system.transform` | `experimental.chat.system.transform` | Always (core) |
| `tool.execute.before` | `tool.execute.before` | Always (core) |
| `tool.execute.after` | `tool.execute.after` | Always (core) |
| `shell.env` | `shell.env` | Always (core) |
| `chat.params` | `chat.params` | Always |
| `chat.headers` | `chat.headers` | Always |
| `command.execute.before` | `command.execute.before` | Always |
| `experimental.text.complete` | `experimental.text.complete` | Always |
| `permission.ask` | `permission.ask` | Always |
| `chat.message` | `chat.message` | Phase 2 |
| `tool.definition` | `tool.definition` | Phase 2 |
| `experimental.session.compacting` | `experimental.session.compacting` | Phase 2 |
| `experimental.compaction.autocontinue` | `experimental.compaction.autocontinue` | Phase 2 |
| `event` | `event` | Phase 3 |
| `config` | `config` | Phase 3 |
| `catalog.transform` | `catalog.transform` | Phase 3 |
| `account.switched` | `account.switched` | Phase 3 |
| `aisdk.sdk` | `aisdk.sdk` | Phase 3 |
| `aisdk.language` | `aisdk.language` | Phase 3 |

### 2.6 Adding a New Hook Handler to the Static Plugin

1. Add a new handler block to the static plugin JS file following the template:
   ```javascript
   "<hook_function_name>": async (input, output) => {
     for (const policy of POLICIES.filter(p =>
       p.event === "<yaml_event_name>" && p.enabled
     )) {
       const ctx = buildContext(input, output);
       const matched = evaluatePolicies(policy, ctx);
       if (matched) {
         auditLog(policy, ctx, true, policy.action.type, "");
         applyAction(policy, input, output);
       }
     }
   },
   ```
2. Add the mapping entry to the table above.
3. Add the YAML event name to the relevant domain file.
4. Test with `policy dry-run`.

No changes to the rendering pipeline, CLI scripts, or profile system.

---

## 3. CLI Script Architecture

### 3.1 Shared Library (`lib/context.sh`)

```bash
#!/usr/bin/env bash
# lib/context.sh — shared functions for policy CLI tools
# Sourced by: rules, guards, tool-guards, shell-guards, system-rules, policy, profile
#
# Dependencies: yq (https://github.com/mikefarah/yq) — single Go binary for YAML processing

set -euo pipefail

# ── Path resolution ──
_ami_root() { ... }                           # walk up to find pyproject.toml
_policy_dir() { echo "$(_ami_root)/workspace/config/opencode/policies"; }
_template_dir() { echo "$(_policy_dir)/template"; }
_static_plugin() { echo "$(_ami_root)/workspace/config/opencode/plugins/add-user-message-context.js"; }
_rendered_json() { echo "$(_ami_root)/workspace/config/opencode/plugins/policies.json"; }
_deploy_dir() { echo "${HOME}/.config/opencode/plugins"; }
_audit_dir() { echo "${HOME}/.config/opencode/logs"; }

# ── Template seeding (mirrors current _init_userfile) ──
_init_userfile() {
  local domain="$1"                          # e.g., "rules", "guards"
  local userfile="$(_policy_dir)/${domain}.yaml"
  local template="$(_template_dir)/${domain}.template.yaml"
  if [[ ! -f "$userfile" ]]; then
    [[ ! -f "$template" ]] && _err "Template not found: $template"
    cp "$template" "$userfile"
    _ok "Created ${domain}.yaml from template"
  fi
}

# ── YAML operations (via yq) ──
_yq_query() { yq eval "$1" "$2"; }
_list_policies() { yq eval '.policies[] | .name' "$1"; }
_show_policy() { yq eval ".policies[] | select(.name == \"$2\")" "$1"; }
_insert_policy() { ... }                      # yq eval '.policies += [new_obj]' -i "$1"
_delete_policy() { yq eval "del(.policies[] | select(.name == \"$2\"))" -i "$1"; }
_toggle_policy() { yq eval "(.policies[] | select(.name == \"$2\")).enabled = $3" -i "$1"; }

# ── Validation ──
_validate_policy_file() { ... }               # yq schema check + event-action compat
_validate_all() { ... }                       # validate all userfile *.yaml in policy dir

# ── Rendering (YAML → JSON from userfiles) ──
_render_json() {
  # Merge all userfile YAMLs (not templates), filter enabled, sort by priority desc
  local dir="$(_policy_dir)"
  yq eval-all '
    .policies | map(select(.enabled != false))
    | sort_by(.priority) | reverse
  ' "$dir"/*.yaml -o=json > "$(_rendered_json)"
}

# ── Deployment ──
_deploy() {
  mkdir -p "$(_deploy_dir)"
  cp "$(_static_plugin)" "$(_deploy_dir)/"
  cp "$(_rendered_json)" "$(_deploy_dir)/"
}
_remind() { echo "Restart all opencode sessions to pick up changes."; }

# ── Audit ──
_read_audit_log() { tail -n "${1:-50}" "$(_audit_dir)/policy-decisions.jsonl"; }

# ── Profiles ──
_list_profiles() { ls "$(_policy_dir)/profiles/"*.yaml 2>/dev/null || true; }
_load_profile() { ... }
_save_profile() { ... }
```

### 3.2 Domain CLI Wrapper Example (`rules`)

```bash
#!/usr/bin/env bash
# rules — manage context injection rules (user-message scope)
# Sources: lib/context.sh

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
source "$SCRIPT_DIR/lib/context.sh"

DOMAIN="rules"                                # maps to rules.yaml
SECTION="user-message"                        # scope within chat.messages.transform

case "${1:-list}" in
    list|"")     _list_policies "$DOMAIN" ;;
    add)         shift; _add_policy "$DOMAIN" "$@" ;;
    delete)      shift; _delete_policy "$DOMAIN" "${1:-}" ;;
    update)      shift; _update_policy "$DOMAIN" "$@" ;;
    enable)      shift; _toggle_policy "$DOMAIN" "${1:-}" true ;;
    disable)     shift; _toggle_policy "$DOMAIN" "${1:-}" false ;;
    --help|-h)   _usage "$DOMAIN" ;;
    *)           _err "Unknown command: $1" ;;
esac
```

Each domain CLI is ~30 lines — a thin wrapper around the shared library.

### 3.3 Policy Lifecycle CLI (`policy`)

```
USAGE: policy <command> [args]

COMMANDS:
  validate          Validate all policy YAML files against schema
  render            Convert YAML policies → policies.json via yq
  apply             Render + deploy static plugin + policies.json
  list              List all policies across all domain files
  show NAME         Show full details of a specific policy
  dry-run NAME -i JSON_INPUT   Simulate policy evaluation
  audit [N]         Show last N audit log entries (default: 50)
```

### 3.4 Profile CLI (`profile`)

```
USAGE: profile <command> [args]

COMMANDS:
  list              List all available profiles
  show NAME         Show profile YAML content
  apply NAME        Activate a profile (render + deploy from profile's policy set)
  save NAME -i FILES...   Save current policies as a named profile
  delete NAME       Delete a saved profile
  install SOURCE    Install profile from file/git/URL
```

---

## 4. Profile System

### 4.1 Profile YAML Format

```yaml
# profiles/strict.yaml
name: strict
version: "1.0"
description: "Full enforcement — no speculation, no shortcuts, block destructive ops"
extends: standard                          # optional base profile

policies:
  - file: rules.yaml                       # include all policies from this file
    overrides:                             # optional per-policy overrides
      no-premature-conclusions:
        enabled: true
  - file: guards.yaml
  - file: tool-guards.yaml
  - file: shell-guards.yaml

# Profile-level defaults (applied to all policies during rendering)
defaults:
  enabled: true                            # default enable state
  priority: 0
```

### 4.2 Profile Resolution

```
profile apply strict
  │
  ├── 1. Load strict.yaml
  │
  ├── 2. Load extends chain (standard.yaml → merge)
  │      - standard.yaml policies merged first
  │      - strict.yaml overrides applied on top
  │
  ├── 3. For each policy file reference:
  │      - Load all policies from that file
  │      - Apply per-policy overrides (enabled, priority, etc.)
  │
  ├── 4. Apply profile defaults
  │
  ├── 5. Merge into single YAML set via yq
  │
  ├── 6. policy render (YAML → policies.json)
  │
  └── 7. policy apply (deploy static JS + policies.json)
```

---

## 5. File Map

| File | Purpose | Tracked? |
|------|---------|----------|
| `workspace/scripts/bin/rules` | Domain CLI: rules editing (~30 lines) | Git |
| `workspace/scripts/bin/guards` | Domain CLI: guards editing (~30 lines) | Git |
| `workspace/scripts/bin/policy` | Policy lifecycle CLI (~120 lines) | Git |
| `workspace/scripts/bin/profile` | Profile lifecycle CLI (~120 lines) | Git |
| `workspace/scripts/bin/lib/context.sh` | Shared bash library (~420 lines) | Git |
| `workspace/config/opencode/policies/template/*.template.yaml` | Immutable policy templates | **Git** |
| `workspace/config/opencode/policies/template/profiles/*.template.yaml` | Immutable profile templates | **Git** |
| `workspace/config/opencode/policies/*.yaml` | User working copies | **Gitignored** |
| `workspace/config/opencode/policies/profiles/*.yaml` | User profiles | **Gitignored** |
| `workspace/config/opencode/plugins/add-user-message-context.js` | Static plugin JS | **Git** |
| `workspace/config/opencode/plugins/policies.json` | Rendered by yq | **Gitignored** |
| `~/.config/opencode/plugins/` | Deployed runtime copies | _Not in repo_ |
| `~/.config/opencode/logs/policy-decisions.jsonl` | Audit trail | _Not in repo_ |

---

## 6. Migration Path

### 6.1 Current State → Target State

```
Step 1: Create lib/context.sh with shared functions (bash + yq)
   ✓ _yq_query, _validate_policy_file, _insert_policy, _delete_policy
   ✓ _render_json (yq eval-all → policies.json), _deploy, _remind
   ✓ _init_userfile (template → userfile seeding)

Step 2: Create template YAMLs from existing template.js
   → Extract RULES[] → template/rules.template.yaml (5 entries)
   → Extract BLOCK_PATTERNS[] → template/guards.template.yaml (1 entry)
   → Create empty templates for future domains (tool-guards, shell-guards, system-rules)

Step 3: Create the static plugin JS (written once, tested once)
   → Loads policies.json at runtime from its own directory
   → Generic match engine covers all 24 hook types
   → Audit trail with hash chain

Step 4: Create policy CLI
   → policy validate, policy render (yq), policy apply

Step 5: Create rules + guards domain CLIs
   → Each calls _init_userfile on first invocation
   → Thin wrappers sourcing lib/context.sh
   → Replace existing 'rules' script entirely

Step 6: Create profile CLI
   → profile list, save, load, apply, delete

Step 7: Add gitignore entries
   → workspace/config/opencode/policies/*.yaml
   → workspace/config/opencode/policies/profiles/*.yaml
   → workspace/config/opencode/plugins/policies.json

Step 8: Update extension.manifest.yaml + Makefile targets
```

### 6.2 Backward Compatibility

The migration SHALL be backward compatible:
- The old `rules` script is replaced, not deleted. Old commands map to new equivalents.
- The existing `add-user-message-context.template.js` is superseded by `template/*.template.yaml` files.
- The deployed plugin has the same filename and deploy path.
- opencode continues to load the plugin from `~/.config/opencode/plugins/`.
- `make rules` and `make hooks` targets are updated (hooks → guards).
- On first run, userfiles are auto-seeded from templates — seamless upgrade.

### 6.3 Validation Checklist

Before cutting over:
- [ ] Templates exist: `template/rules.template.yaml` (5 rules), `template/guards.template.yaml` (1 guard)
- [ ] First `rules` invocation seeds `rules.yaml` from template
- [ ] First `guards` invocation seeds `guards.yaml` from template
- [ ] `policy render` produces `policies.json` from userfiles (not templates)
- [ ] The static plugin loads and evaluates `policies.json` correctly
- [ ] Functionally identical behavior to the current plugin (same system prompt injections)
- [ ] `rules add -r /.+/ -t "test"` edits rules.yaml, not the template
- [ ] `rules delete no-premature-conclusions` removes via yq from userfile
- [ ] Userfiles and `policies.json` are gitignored
- [ ] All scripts pass shellcheck and remain under 512 lines

---

## 7. Extension Manifest Registration

```yaml
# Additions to workspace/scripts/bin/extension.manifest.yaml

  - name: rules
    binary: workspace/scripts/bin/rules
    description: Manage opencode context injection rules (user-message)
    category: core
    features:
      - list
      - add
      - delete
      - update
      - enable
      - disable
    bannerPriority: 20
    check:
      command: ["{binary}", "--help"]
      healthExpect: "Usage"
      timeout: 5

  - name: guards
    binary: workspace/scripts/bin/guards
    description: Manage opencode assistant response guards
    category: core
    features:
      - list
      - add
      - delete
      - update
      - enable
      - disable
    bannerPriority: 21
    check:
      command: ["{binary}", "--help"]
      healthExpect: "Usage"
      timeout: 5

  - name: policy
    binary: workspace/scripts/bin/policy
    description: Agent policy lifecycle management
    category: core
    features:
      - validate
      - render
      - apply
      - list
      - show
      - dry-run
      - audit
    bannerPriority: 22
    check:
      command: ["{binary}", "--help"]
      healthExpect: "Usage"
      timeout: 5

  - name: profile
    binary: workspace/scripts/bin/profile
    description: Manage agent policy profiles
    category: core
    features:
      - list
      - show
      - apply
      - save
      - delete
      - install
    bannerPriority: 23
    check:
      command: ["{binary}", "--help"]
      healthExpect: "Usage"
      timeout: 5
```

---

## 8. Makefile Target Additions

```makefile
# Rules (context injection — user-message scope)
.PHONY: rules rules-add rules-delete rules-update
rules: ## List all user-message context injection rules
	@bash workspace/scripts/bin/rules

rules-add: ## Add a rule: make rules-add REGEX="/.+/" RULE="instruction"
	@[ -n "$$REGEX" ] || { echo "ERROR: REGEX= is required"; exit 1; }
	@[ -n "$$RULE" ] || { echo "ERROR: RULE= is required"; exit 1; }
	@bash workspace/scripts/bin/rules add -r "$$REGEX" -t "$$RULE"

rules-delete: ## Delete a rule: make rules-delete NAME="no-speculation"
	@[ -n "$$NAME" ] || { echo "ERROR: NAME= is required"; exit 1; }
	@bash workspace/scripts/bin/rules delete "$$NAME"

rules-update: ## Update a rule: make rules-update NAME="rule" REGEX="/.+/" RULE="text"
	@[ -n "$$REGEX" ] && [ -n "$$RULE" ] && [ -n "$$NAME" ] || \
		{ echo "ERROR: NAME= REGEX= RULE= are required"; exit 1; }
	@bash workspace/scripts/bin/rules update "$$NAME" -r "$$REGEX" -t "$$RULE"

# Guards (assistant response — assistant-message scope)
.PHONY: guards guards-add guards-delete guards-update
guards: ## List all assistant response guards
	@bash workspace/scripts/bin/guards

guards-add: ## Add a guard: make guards-add REGEX="/likely|maybe/i" RULE="instruction"
	@[ -n "$$REGEX" ] || { echo "ERROR: REGEX= is required"; exit 1; }
	@[ -n "$$RULE" ] || { echo "ERROR: RULE= is required"; exit 1; }
	@bash workspace/scripts/bin/guards add -r "$$REGEX" -t "$$RULE"

guards-delete: ## Delete a guard: make guards-delete NAME="guard-name"
	@[ -n "$$NAME" ] || { echo "ERROR: NAME= is required"; exit 1; }
	@bash workspace/scripts/bin/guards delete "$$NAME"

guards-update: ## Update a guard: make guards-update NAME="guard" REGEX="/pat/" RULE="text"
	@[ -n "$$REGEX" ] && [ -n "$$RULE" ] && [ -n "$$NAME" ] || \
		{ echo "ERROR: NAME= REGEX= RULE= are required"; exit 1; }
	@bash workspace/scripts/bin/guards update "$$NAME" -r "$$REGEX" -t "$$RULE"

# Policy lifecycle
.PHONY: policy-validate policy-render policy-apply policy-list policy-audit
policy-validate: ## Validate all policy YAML files
	@bash workspace/scripts/bin/policy validate

policy-render: ## Render policies.json from YAML (yq)
	@bash workspace/scripts/bin/policy render

policy-apply: ## Render + deploy static plugin + policies.json
	@bash workspace/scripts/bin/policy apply

policy-list: ## List all policies across all domains
	@bash workspace/scripts/bin/policy list

policy-audit: ## Show last 50 audit log entries
	@bash workspace/scripts/bin/policy audit

# Profiles
.PHONY: profile-list profile-apply profile-save profile-delete
profile-list: ## List available profiles
	@bash workspace/scripts/bin/profile list

profile-apply: ## Activate a profile: make profile-apply NAME=strict
	@[ -n "$$NAME" ] || { echo "ERROR: NAME= is required"; exit 1; }
	@bash workspace/scripts/bin/profile apply "$$NAME"

profile-save: ## Save current policies as profile: make profile-save NAME=my-profile
	@[ -n "$$NAME" ] || { echo "ERROR: NAME= is required"; exit 1; }
	@bash workspace/scripts/bin/profile save "$$NAME"

profile-delete: ## Delete a profile: make profile-delete NAME=my-profile
	@[ -n "$$NAME" ] || { echo "ERROR: NAME= is required"; exit 1; }
	@bash workspace/scripts/bin/profile delete "$$NAME"
```

---

## 9. Implementation Phases

### Phase 1: Core Migration (Week 1-2)

| Deliverable | Status |
|-------------|--------|
| `lib/context.sh` shared library with bash + yq functions (incl. _init_userfile) | NOT STARTED |
| `template/rules.template.yaml` + `template/guards.template.yaml` from existing template.js | NOT STARTED |
| Static plugin JS (`add-user-message-context.js`) written + tested | NOT STARTED |
| Gitignore: policies/*.yaml, profiles/*.yaml, plugins/policies.json | NOT STARTED |
| `policy` CLI: validate, render (yq), apply, list | NOT STARTED |
| `rules` CLI rewrite (thin wrapper, sources lib) | NOT STARTED |
| `guards` CLI (new, thin wrapper) | NOT STARTED |
| Migration validation: static plugin + policies.json functionally matches current plugin | NOT STARTED |
| Extension manifest updated (rules, guards, policy, profile) | NOT STARTED |
| Makefile targets updated | NOT STARTED |

### Phase 2: Profiles + Audit (Week 3-4)

| Deliverable | Status |
|-------------|--------|
| `profile` CLI: list, save, load, apply, delete | NOT STARTED |
| Built-in profiles: standard, strict, lenient, code-review | NOT STARTED |
| Audit trail generation in plugin (JSONL hash chain) | NOT STARTED |
| `policy dry-run` command | NOT STARTED |
| `policy audit` command (read audit log) | NOT STARTED |
| Profile inheritance (`extends`) | NOT STARTED |

### Phase 3: Advanced Governance (Week 5-6)

| Deliverable | Status |
|-------------|--------|
| Additional domain CLIs: `tool-guards`, `shell-guards`, `system-rules` | NOT STARTED |
| Agent-scoped policies (`agent: "explore"`) functional | NOT STARTED |
| Compound conditions (`match_groups`) functional | NOT STARTED |
| Circuit breaker for repeated A2A policy violations | NOT STARTED |
| `profile install` from git sources | NOT STARTED |
| Full schema validation for all 24 hook events | NOT STARTED |

---

*This specification implements the requirements defined in [REQ-AGENT-POLICY](REQ-AGENT-POLICY.md). Architecture: bash + yq for YAML processing and CLI management; static JavaScript for the opencode runtime plugin (loaded once, not generated). Zero Python VMs in the rendering pipeline. Industry standards referenced: A2A Protocol v1.0, opencode Plugin Hooks Interface (@opencode-ai/plugin), EU AI Act (Regulation (EU) 2024/1689), ISO/IEC 42001:2023, NIST AI RMF 1.0, OWASP Top 10 for LLM Applications (2025), and design patterns observed across 10+ AI agent policy engines.*
