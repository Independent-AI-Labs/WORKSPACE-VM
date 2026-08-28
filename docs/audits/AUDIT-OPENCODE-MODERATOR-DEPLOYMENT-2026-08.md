# Audit: OpenCode Moderator Deployment

**Date:** 2026-08-09  
**Status:** Findings confirmed; replacement work pending evidence  
**Scope:** Deployment, configuration, testing, and Gateway routing for the
local OpenCode response moderator.

## Executive Summary

At audit start, the response moderator had two separate deployment
implementations:

1. `make install-opencode-moderator` copies the plugin files to the OpenCode
   user configuration directory.
2. Every `oc` launch copies the same files to the same directory again.

This is an invalid ownership model. The installer is not authoritative because
the runtime wrapper redeploys on every invocation. Both implementations copy
live files one at a time without validation, atomic replacement, status, or
drift detection. The deployment tests mostly assert source-code strings rather
than exercising installation behavior.

The Workspace Gateway route itself is correctly configured and verified live.
The moderator's direct llamafile default was changed to use the Gateway relay,
but that configuration remains embedded in the classifier script and model
identity is duplicated outside the Gateway's provider definition.

The replacement design below is a target. This document preserves the baseline
defects, target design, and required verification criteria; it does not claim
installation, deployment, or runtime acceptance.

## Target Remediation

The duplicate Make and `oc` copy paths shall be replaced with one installer at
`workspace/scripts/install-opencode-moderator`. It shall create an XDG-aware,
validated release and atomically switch the release target behind OpenCode's
direct top-level plugin entry. The `oc` wrapper shall not deploy moderator
files. Make shall expose install, verify, status, and uninstall targets that
delegate to the installer.


The classifier shall receive its release-local configuration path from the
adapter and reject any endpoint other than the Workspace Gateway relay. The
installer shall validate Gateway model availability before release activation.

Behavioral tests must cover isolated install, verify, status, drift detection,
and uninstall while preserving unrelated plugins. Source-string assertions are
not deployment acceptance evidence.

## Scope And Evidence

| Area | Evidence | Result |
| --- | --- | --- |
| Explicit installation | `Makefile:670-680` | Duplicated, non-atomic copy implementation |
| Implicit installation | `workspace/scripts/bin/oc:59-67` | Redeploys on every wrapper invocation |
| Runtime source | `workspace/config/opencode/plugins/local-response-moderator.template.js` and `.sh` | Two-file plugin with a misleading template filename |
| Installed destination | `~/.config/opencode/plugins/local-response-moderator.{js,sh}` | Hardcoded destination, no XDG support |
| Deployment tests | `tests/integration/test_oc_config_deployment.py` | Source-string checks, not installer behavior |
| Gateway route | `projects/WORKSPACE-GATEWAY/conf/apisix.yaml:426-463` | Correct route and rewrite |
| Gateway provider | `projects/WORKSPACE-GATEWAY/conf/providers/workspace-gw-llamafile-no-auth.yaml` | Canonical endpoint and model metadata present |
| Live Gateway checks | 2026-08-09 HTTP requests | `/models`, token count, and completion succeeded through port 9080 |

## Current Deployment Flow

```text
workspace source files
  ├─ Make target copies files to ~/.config/opencode/plugins/
  └─ oc wrapper copies the same files to ~/.config/opencode/plugins/
       └─ OpenCode loads the installed JavaScript module at process startup
```

The source JavaScript file is named
`local-response-moderator.template.js`, but neither path renders it. Both copy
it byte-for-byte to `local-response-moderator.js`.

## Findings

### F-01: Two Independent Deployment Authorities

**Severity:** High  
**Files:** `Makefile:670-680`; `workspace/scripts/bin/oc:59-67`

The Make target and wrapper both own the same deployment process. Each embeds:

- The source directory.
- The user configuration directory.
- The source and destination filenames.
- Directory creation.
- Copy operations.
- Shell permission updates.

Any improvement must be duplicated. A future change can update one path but
not the other, producing different installed plugin behavior depending on
whether an operator ran `make` or `oc` most recently.

**Impact:** There is no single source of truth for deployment behavior.

### F-02: Normal Runtime Launch Mutates User Configuration

**Severity:** High  
**File:** `workspace/scripts/bin/oc:65-67`

Every normal `oc` invocation overwrites the installed moderator JavaScript and
shell script. This happens after the wrapper resolves the workspace root and
before it executes OpenCode.

The operation is unrelated to starting OpenCode. It causes a command intended
to run an agent to silently alter user configuration.

**Impact:**

- Explicit installation has no durable meaning.
- Local intentional changes are silently overwritten.
- A changed workspace branch changes deployed configuration as a side effect of
  opening OpenCode.
- Troubleshooting cannot distinguish an intentional installation from an
  implicit overwrite.

### F-03: Non-Atomic Two-File Deployment

**Severity:** High  
**Files:** `Makefile:677-679`; `workspace/scripts/bin/oc:65-67`

The JavaScript adapter and Bash classifier form one runtime unit, but they are
copied directly to separate live destination paths. The first copy can succeed
and the second can fail or be interrupted. Permission handling follows the
second copy rather than being part of one validated installation transaction.

**Impact:** The installed adapter can reference a classifier from a different
release. A concurrently starting OpenCode process can load a mixed release.

### F-04: No Post-Installation Validation

**Severity:** High  
**Files:** `Makefile:674-680`; `workspace/scripts/bin/oc:62-67`

The Make target validates only that source files exist. Neither path validates:

- The shell script with `bash -n`.
- The installed files after copying.
- That the installed shell file is executable.
- That source and installed content match.
- That the Gateway relay is reachable.
- That the Gateway exposes the configured MiniCPM model.
- That OpenCode can load the installed JavaScript module.

The target emits an unconditional success message after copies complete. The
manual `cmp` checks used during this session are not part of the target.

**Impact:** Operators receive a success result that does not establish a
working plugin.

### F-05: Misleading `.template.js` Source Name

**Severity:** Medium  
**Files:** `workspace/config/opencode/plugins/local-response-moderator.template.js`;
`Makefile:677`; `workspace/scripts/bin/oc:65`

The JavaScript source contains no template variables and is copied verbatim.
The `.template.js` suffix falsely communicates a render step and forces every
deployment implementation to translate the filename.

**Impact:** It obscures that the source is canonical executable code and adds
unnecessary naming divergence between source and installed files.

### F-06: Deployment Ignores XDG Configuration Roots

**Severity:** Medium  
**Files:** `Makefile:673`; `workspace/scripts/bin/oc:61`

Both deployment paths hardcode `~/.config/opencode`. They ignore
`XDG_CONFIG_HOME` and offer no destination override.

**Impact:** Isolated tests, non-default desktop configuration, multiple
profiles, packaging, and alternate user environments cannot use the supported
installer without altering `$HOME`.

### F-07: Make Uses Caller Working Directory as Repository Root

**Severity:** Medium  
**File:** `Makefile:672`

The target uses `$(CURDIR)` to locate workspace source files. `CURDIR` is the
directory from which `make` was invoked, not necessarily the directory
containing this Makefile.

For example, `make -f /path/to/Makefile install-opencode-moderator` from a
different directory resolves `workspace/config/opencode/plugins` relative to
the caller and fails or selects unrelated files.

**Impact:** The target is not reliably repository-aware.

### F-08: No Explicit Reload Contract

**Severity:** Medium  
**Files:** `Makefile:680`; `docs/specifications/SPEC-OPENCODE-RESPONSE-MODERATOR.md:237-241`

OpenCode loads plugins at startup. Copying files does not replace a module
already loaded by a running OpenCode server. The Make target says only that the
files were installed, while the specification separately tells the operator to
restart OpenCode.

**Impact:** The command's success message can be interpreted as immediate
activation when a restart is actually required.

### F-09: No Supported Lifecycle Operations

**Severity:** Medium  
**Files:** `Makefile:670-680`; `workspace/scripts/bin/oc:59-67`

There is no supported:

- `status` operation to show installed source version and drift.
- `verify` operation to validate installed files and Gateway reachability.
- `uninstall` operation to remove the moderator.
- Explicit `reload` operation or precise restart instruction.

**Impact:** Deployment state is observable only through ad hoc shell commands.

### F-10: Tests Do Not Exercise the Installer

**Severity:** High  
**File:** `tests/integration/test_oc_config_deployment.py:151-229`

The primary moderator deployment test reads source files and asserts that
expected strings occur. It does not run `make install-opencode-moderator` in
an isolated configuration root. It does not invoke the wrapper deployment
path, compare installed output, verify permissions, or detect partial install
behavior.

The fixture near the start of the file tests only a minimal inline config copy
snippet. It does not represent either actual moderator deployment path.

**Impact:** The test reports confidence about static text rather than the
installation behavior users depend on.

### F-11: Brittle Source-String Assertions

**Severity:** Medium  
**File:** `tests/integration/test_oc_config_deployment.py:151-220`

The test asserts internal variable names, expressions, and literal snippets.
Examples include `sessionActors`, `latestAssistant.info.parentID`, and exact
decision-type expressions. Refactoring implementation structure can break the
test without changing behavior. Conversely, a broken runtime path can pass if
the expected text remains.

**Impact:** The test is costly to maintain and weak at preventing behavioral
regressions.

### F-12: Gateway Configuration Is Embedded in Classifier Code

**Severity:** Medium  
**File:** `workspace/config/opencode/plugins/local-response-moderator.sh:5-6`

The Gateway relay URL is a shell-script default. Changing deployment topology
requires editing source code, redeploying the plugin, and restarting OpenCode.
The script accepts `OPENCODE_MODERATOR_URL`, but the installer neither writes
nor validates it.

**Impact:** Infrastructure configuration and classifier logic are coupled.

### F-13: MiniCPM Model Identity Is Duplicated

**Severity:** Medium  
**Files:** `workspace/config/opencode/plugins/local-response-moderator.sh:97`;
`projects/WORKSPACE-GATEWAY/conf/providers/workspace-gw-llamafile-no-auth.yaml:19`

The classifier sends `/zip/MiniCPM5-1B-Q8_0.gguf`. The Gateway provider
definition separately declares the same API ID. APISIX does not rewrite request
model IDs on `relay-llamafile`; it only rewrites the URL path.

**Impact:** A model rename, replacement, or route migration can leave the
Gateway healthy while moderator inference fails.

### F-14: Gateway-Only Policy Is Not Enforced as an Invariant

**Severity:** Medium  
**Files:** `workspace/config/opencode/plugins/local-response-moderator.sh:5-6`;
`docs/requirements/REQ-OPENCODE-RESPONSE-MODERATOR.md:36-38`

The default points at the Gateway, but any value of `OPENCODE_MODERATOR_URL` is
accepted. In particular, a direct `http://127.0.0.1:8765` value bypasses the
Gateway, telemetry, redaction, request IDs, and rate limiting.

`BASE_URL="${BASE_URL%/v1}"` strips only an exact `/v1` suffix. It does not
normalize a trailing slash and cannot reject an unintended direct upstream.

**Impact:** The runtime does not enforce its documented routing requirement.

### F-15: Root Makefile Owns a Specialized Deployment Recipe

**Severity:** Low  
**File:** `Makefile:666-680`

The root Makefile includes component-specific Makefiles for LlamaServer and
llamafile, then embeds the moderator installer directly at the end. The
moderator has enough lifecycle and validation needs to justify a focused,
repository-aware script or included component Makefile.

**Impact:** The root Makefile becomes a collection of unrelated deployment
implementations rather than a stable orchestration surface.

## Gateway Route Review

The Gateway route is correctly set up. No Gateway route modification is
required for the moderator.

| Property | Verified value | Evidence |
| --- | --- | --- |
| Public Gateway URL | `http://127.0.0.1:9080` | Docker port mapping and live request |
| Moderator route prefix | `/llamafile/*` | `conf/apisix.yaml:426-427` |
| Upstream | `host.docker.internal:8765` | `conf/apisix.yaml:428-433` |
| Rewrite | `^/llamafile/(.*)` to `/$1` | `conf/apisix.yaml:435-436` |
| Authentication | None for local relay | `conf/apisix.yaml`, provider definition |
| Rate limit | 600 requests per 60 seconds by `remote_addr` | `conf/apisix.yaml:457-463` |
| Provider base route | `/llamafile/v1` | provider definition line 7 |
| Canonical MiniCPM ID | `/zip/MiniCPM5-1B-Q8_0.gguf` | provider definition line 19 and live models response |

Live checks performed on 2026-08-09:

```text
GET  /llamafile/v1/models
POST /llamafile/v1/chat/completions/input_tokens
POST /llamafile/v1/chat/completions
```

All requests succeeded through port `9080`. The completion request returned
`ok` from `/zip/MiniCPM5-1B-Q8_0.gguf`.

## Required Replacement Design

### One Deployment Authority

Create one repository-aware installer, for example:

```text
workspace/scripts/install-opencode-moderator
```

The root Make target must delegate to it. The `oc` wrapper must not copy,
modify, or install plugins during normal execution.

### Canonical Source Names

The executable source should be named exactly as deployed:

```text
workspace/config/opencode/plugins/local-response-moderator.js
workspace/config/opencode/plugins/local-response-moderator.sh
```

If a template is actually needed, it must have documented substitution inputs
and a single rendering step. Otherwise, the `.template.js` file should be
renamed and the false template abstraction removed.

### Atomic Installation

The installer must:

1. Resolve the repository root from its own location.
2. Resolve the target configuration root as
   `${XDG_CONFIG_HOME:-$HOME/.config}/opencode/plugins`, with an explicit test
   override.
3. Validate source files before touching the target.
4. Copy both files into a temporary directory under the target's parent.
5. Apply executable permissions to the temporary shell file.
6. Run `bash -n` against the temporary shell file.
7. Compare version metadata or checksums before activation.
8. Atomically replace the installed plugin directory or release directory.
9. Report the installed version, source path, target path, and required
   OpenCode restart.

Because the plugin has two files, release-directory swapping is preferred over
two independent file renames. OpenCode auto-discovers only direct
`plugins/*.js` entries, so the installer retains one top-level
`local-response-moderator.js` symlink whose target remains inside the plugin
directory and resolves through an atomically switched `current` release
symlink. The deployed JavaScript adapter resolves its shell script from its own
release directory. OpenCode must restart after activation; no compatibility
launcher is retained for prior loaded adapters.

### Explicit Lifecycle Surface

Expose non-mutating and mutating commands through the same installer:

```text
install-opencode-moderator
verify-opencode-moderator
status-opencode-moderator
uninstall-opencode-moderator
```

`verify` must compare installed content, validate the shell script, identify
the configured Gateway endpoint, fetch `/llamafile/v1/models`, and verify the
configured model is present.

### Configuration Ownership

Gateway endpoint and model identity must not be duplicated arbitrarily inside
classifier logic. Choose one explicit configuration source:

1. An installed moderator configuration file generated by the installer from a
   tracked template.
2. A documented environment contract, validated by the installer and runtime.
3. A Gateway endpoint discovery step that reads the model ID from
   `/llamafile/v1/models` and fails explicitly when the expected model is not
   available.

The selected approach must enforce the Gateway-only policy. A direct llamafile
URL must fail startup or classification with a clear error, not silently bypass
the Gateway.

## Required Test Replacement

Replace static source-string assertions with behavioral coverage:

| Test | Required assertion |
| --- | --- |
| Fresh install | Both files installed under an isolated `XDG_CONFIG_HOME` |
| Reinstall | A complete release replaces the prior release without mixed files |
| Verify | Detects changed content, missing shell executable bit, invalid shell syntax, unreachable Gateway, and absent model |
| Wrapper | `oc` does not modify moderator installation state |
| Gateway default | Generated configuration targets `/llamafile`, never direct port `8765` |
| Runtime route | Token-count and completion URLs are `/llamafile/v1/...` |
| Reload contract | Installer reports that restart is required; status reports installed versus running version when observable |
| Uninstall | Removes only moderator-owned files and leaves unrelated plugins unchanged |

The classifier's existing fake-curl tests can remain for transcript and verdict
behavior. They must not be treated as installer or Gateway configuration tests.

## Remediation Order

1. Remove the moderator copy operations from `workspace/scripts/bin/oc`.
2. Create the single installer and route Make targets through it.
3. Rename the non-template JavaScript source.
4. Implement atomic release installation and XDG-aware destination resolution.
5. Add install, verify, status, and uninstall behaviors.
6. Move and validate Gateway endpoint/model configuration.
7. Replace the source-string deployment test with isolated behavioral tests.
8. Add a live optional Gateway sanity test and a deterministic fake-Gateway test.
9. Update requirements and specification documents to describe the replacement
   contract.

## Non-Goals

- Do not modify the existing Gateway `relay-llamafile` route. It is correctly
  configured and working.
- Do not connect the moderator directly to port `8765`.
- Do not add another inference daemon or Gateway route.
- Do not make the `oc` wrapper a configuration deployment mechanism.

## Follow-Up: Continuation Controller

The deployment remediation does not establish correct moderation behavior after
an agent stops. Session `ses_0286484d8ffedoI4tw2MgDjRUd` exposed two separate
runtime defects: MiniCPM could pass an unsupported `[WORK DONE]` claim, and the
adapter treated a later markerless interim progress report as a second failure
and escalated it. The next implementation revision SHALL replace the
marker-only, one-retry policy with the requirements and specification's
MiniCPM-controlled continuation controller.

The controller must preserve the deployment guarantees above while adding:

1. Release-local dynamic model identity in every prompt, trace, and toast.
2. Passive, model-labeled transcript traces for checklist, pass, continuation,
   escalation, root block, and error outcomes. A trace must use `noReply: true`
   and must not accidentally start a new GPT turn.
3. MiniCPM review for every eligible terminal Build response after the initial
   checklist, including markerless interim reports.
4. A deterministic rejection of `[WORK DONE]` while required todos remain
   pending or in progress.
5. Unlimited productive continuations, with escalation only after three
   consecutive MiniCPM `CONTINUE_NO_PROGRESS` rulings in one real-user cycle.
6. A deterministic `root-blocked` operator handoff when a fenced shell-like
   code block contains a `sudo` command token.

The follow-up tests must run against the installed release after reinstall and
OpenCode restart. They must cover every transcript trace, model attribution,
false-pass rejection, no-progress escalation, root handoff, and passive trace
behavior.

### Follow-Up Status: Finite-State-Machine Refactor

On 2026-08-10, the continuation-controller follow-up was approved for a
dependency-free reducer and transition-table implementation. The current
adapter's mutable session maps and imperative branches are implementation debt;
they are not the target architecture. The authoritative requirements and
implementation contract are now
[`REQ-OPENCODE-RESPONSE-MODERATOR`](../requirements/REQ-OPENCODE-RESPONSE-MODERATOR.md)
and
[`SPEC-OPENCODE-RESPONSE-MODERATOR`](../specifications/SPEC-OPENCODE-RESPONSE-MODERATOR.md).
The detailed execution order is
[`IMPLEMENTATION-PLAN-OPENCODE-MODERATOR-FSM`](../proposals/IMPLEMENTATION-PLAN-OPENCODE-MODERATOR-FSM.md).
This audit remains a historical deployment record and does not claim that the
runtime refactor has been implemented.

### Follow-Up Status: Checklist-Free Completion Gate

On 2026-08-10, a persisted false-pass decision showed MiniCPM returning `PASS`
for a markerless progress report despite required high-priority todos remaining
open. The classifier prompt already prohibited that result, demonstrating that a
small local model cannot be the authority for deterministic completion facts.
The target correction removes completion checklists, `[WORK DONE]` markers, and
duplicate pass adjudication. Every proposed `PASS` is specified to pass
through a deterministic required-todo eligibility gate; a valid exception must
be classified as `BLOCKED`. The authoritative migration backlog is
[`IMPLEMENTATION-PLAN-OPENCODE-MODERATOR-FSM`](../proposals/IMPLEMENTATION-PLAN-OPENCODE-MODERATOR-FSM.md).

## Conclusion

The baseline deployment mechanism was not maintainable because it had duplicate
ownership, hidden runtime mutation, no atomicity, and no behavioral installer
tests. The target replacement is one explicit, XDG-aware installer without
deployment side effects from `oc`; its acceptance remains pending recorded
evidence. The Gateway route remains healthy and unchanged.
