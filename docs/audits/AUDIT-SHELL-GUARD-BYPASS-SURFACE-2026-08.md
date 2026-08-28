# Shell Guard Bypass Surface Audit

**Date:** 2026-08-14  
**Status:** Open critical findings  
**Scope:** All readable workspace source files with executable references to
`/bin/bash.real`, generated Makefile templates, and tests that assert this
execution model.

## Executive Summary

The shell guard's non-root model is that `/bin/bash` validates an invocation,
removes dangerous environment variables, then executes the sealed original
Bash at `/bin/bash.real`. The original executable must exist for that internal
transition.

The workspace extends that implementation detail into an unrestricted root
execution channel. Multiple Makefiles select `/bin/bash.real` as their global
`SHELL` and `SCRIPT_BASH` when invoked by root. GNU Make consequently launches
every recipe in those Makefiles outside the shell guard. Several scripts also
execute `/bin/bash.real` directly, including scripts which download or stage
code before execution.

This is a critical policy violation if privileged work is required to remain
subject to the shell guard. The current design instead establishes a broad
root bypass as normal operational behavior.

## Intended Guard Transition

`projects/WORKSPACE-GUARD/src/shell_guard.rs:22` defines the sealed interpreter
as `REAL_SHELL = "/bin/bash.real"`. After validation, `exec_real` verifies its
ownership and mode, builds a filtered environment, and invokes that absolute
path with `execve` at lines 384-412. This internal transition is required for
the guard to execute an approved Bash command.

The direct root channel is separately codified at lines 435-443. The comment
states that root already has an unconditional escape hatch through
`/bin/bash.real`, and the `AT_SECURE` rejection is skipped for root. This turns
root access to the sealed implementation detail into an accepted bypass model.

## Finding 1: Global Root Makefile Bypass

Every Makefile below conditionally sets `SHELL := /bin/bash.real` for root.
GNU Make executes every recipe with `SHELL`; therefore every root recipe in
each file bypasses shell-guard scanning, script staging, and environment
scrubbing. `SCRIPT_BASH := /bin/bash.real` additionally bypasses the guard for
scripts explicitly launched by recipes.

| File | `SHELL` | `SCRIPT_BASH` | Effect |
|---|---:|---:|---|
| `Makefile` | 24 | 25 | All root workspace targets bypass the guard. |
| `projects/WORKSPACE-GUARD/Makefile` | 45 | 65 | All root guard-management and test targets bypass the guard. |
| `projects/CI/Makefile` | 31 | 48 | All root CI bootstrap and deployment targets bypass the guard. |
| `projects/WORKSPACE-CI/Makefile` | 31 | 48 | Same bypass in the deployed CI tree. |
| `projects/WORKSPACE-GATEWAY/Makefile` | 23 | 31 | All root gateway targets bypass the guard. |
| `projects/WORKSPACE-PORTAL/Makefile` | 19 | 27 | All root portal targets bypass the guard. |
| `projects/WORKSPACE-STREAMS/Makefile` | 16 | 24 | All root streams targets bypass the guard. |
| `projects/DATAOPS/Makefile` | 35 | 47 | All root data operations targets bypass the guard. |
| `projects/RUST-ZK-COMPLIANCE-API/Makefile` | 27 | 38 | All root API targets bypass the guard. |
| `projects/WORLD-GENERATION/Makefile` | n/a | 23 | Root scripts launched through this variable bypass the guard. |

`projects/WORKSPACE-VM/Makefile:24-25` duplicates the root workspace
Makefile's assignments.

The propagation sources are `projects/CI/templates/Makefile.consumer:27,38`
and `projects/WORKSPACE-CI/templates/Makefile.consumer:27,38`. Every consumer
generated from either template inherits the same root bypass.

## Finding 2: Synthetic Bash Path Bypass

`Makefile:554-566` implements a second bypass mechanism for `build-ocb`:

1. Line 555 creates a temporary directory in `_shim`.
2. Line 557 creates `$_shim/bash` as a symlink to `/bin/bash.real`.
3. Line 559 prepends that directory to `PATH`.
4. Line 559 invokes bare `bash scripts/setup/build-opencode.sh`.

The bare command resolves to the symlink rather than guarded `/bin/bash`.
This is an intentional PATH-based route around the guard.

The identifier `_shim` evades the shared banned-word pattern `\bshims?\b` in
`projects/CI/config/banned_words.yaml:779`. An underscore is a regex word
character, so no word boundary exists before the s-prefixed token in `_shim`.
No root-project
exception authorizes this: `config/banned_words_exceptions.yaml` contains no
Makefile path and `quality_exceptions.yaml` declares `exceptions: []`.

## Finding 3: Direct Production Calls

The following are direct calls to the sealed interpreter rather than normal
guarded Bash execution.

| File | Lines | Invocation and effect |
|---|---:|---|
| `projects/WORKSPACE-GUARD/Makefile` | 263-267 | Builds a temporary Bash launcher that executes `/bin/bash.real`, then runs Bats through it. |
| `projects/WORKSPACE-GUARD/Makefile` | 377-378 | Runs `scripts/shell-guard-check` through `/bin/bash.real`. |
| `projects/WORKSPACE-GUARD/scripts/guard-operator.sh` | 84-85 | Runs `shell-guard-check` directly through `/bin/bash.real` as root. |
| `projects/WORKSPACE-GUARD/scripts/install-shell-guard` | 139-140 | Re-executes the staged installer through `/bin/bash.real`. |
| `projects/WORKSPACE-GUARD/scripts/uninstall-shell-guard` | 89-90 | Re-executes the staged uninstaller through `/bin/bash.real`. |
| `projects/CI/scripts/deploy-ci` | 42-46 | Defines `_REAL_BASH=/bin/bash.real` and refuses to proceed without it. |
| `projects/CI/scripts/deploy-ci` | 217, 233, 237, 240, 299 | Executes `lock-repo` five times through `_REAL_BASH`. |
| `projects/CI/scripts/bootstrap-rust` | 219-220 | Executes downloaded `rustup-init.sh` through `/bin/bash.real` when root. |
| `projects/WORKSPACE-CI/scripts/bootstrap-rust` | 219-220 | Duplicate downloaded-installer execution path. |
| `scripts/e2e/workspace-guard-shell-guest.sh` | 147, 377, 472 | Selects and executes `/bin/bash.real` for root-side test work and the recovery script. |

The downloaded-installer paths are particularly high risk. A privileged
execution bypass should not be used to run a network-fetched shell script.

## Finding 4: Tests Codify the Bypass

The test suite asserts and preserves the bypass behavior rather than rejecting
it.

| Test or fixture | Lines | Assertion or behavior |
|---|---:|---|
| `projects/WORKSPACE-GUARD/tests/shell/19-guard-operator-makefile.bats` | 18 | Requires `SCRIPT_BASH := /bin/bash.real`. |
| Same file | 115-119 | Requires root `shell-guard-check` to route through `/bin/bash.real`. |
| Same file | 135-137 | Requires `guard-operator.sh` to use `/bin/bash.real`. |
| Same file | 143 | Requires the Bats launcher to use `/bin/bash.real`. |
| `projects/WORKSPACE-GUARD/tests/shell/21-shell-guard.bats` | 5-7, 37, 70 | Requires the sealed root-only interpreter for runtime tests. |
| `projects/WORKSPACE-GUARD/tests/shell/22-shell-guard-install.bats` | 58, 72-82, 161, 211-216, 240-245, 259 | Creates and validates fixture `bash.real` files, including mode and immutable-flag behavior. |
| `projects/WORKSPACE-GUARD/tests/shell/lib/harness.bash` | 260 | Uses `/bin/bash.real` as the stock interpreter fixture. |
| `projects/WORKSPACE-GUARD/scripts/podman/run-shell-tests-in-container.sh` | 10-11 | Creates a root-only `bash.real` in the test container. |
| `projects/WORKSPACE-GUARD/Containerfile.test` | 25 | Creates a root-only `bash.real` in the test image. |
| `projects/WORKSPACE-CI/web/Containerfile` | 49 | Creates a `bash.real` symlink in the web container. |
| `tests/e2e/qemu_host_isolation.py` | 14 | Captures `/usr/bin/bash.real` in the host integrity fingerprint. |

Tests must be changed alongside production code. Otherwise a removal of the
direct execution channel will be treated as a regression by the current suite.

## Non-Bypass References

`projects/WORKSPACE-GUARD/src/exec.rs:418-425` launches `/bin/bash`, not
`/bin/bash.real`, to execute the CI contract script. It remains on the guarded
entry point and is not a direct real-shell bypass.

Documentation references were not counted as execution paths.

## Required Remediation

1. Remove every root `SHELL := /bin/bash.real` and
   `SCRIPT_BASH := /bin/bash.real` assignment, including the two consumer
   templates.
2. Remove the temporary PATH launcher in `Makefile:554-566`; no temporary
   executable named `bash` may point to the sealed interpreter.
3. Replace direct interpreter calls with guarded execution paths and repair
   commands or scripts that the guard rejects.
4. Treat privileged operations as explicit, narrow operator interfaces with
   absolute executable paths and deterministic environments; do not grant an
   unmediated general-purpose shell.
5. Delete or invert tests that assert the direct root channel. Add regression
   tests proving root Make recipes and root-launched scripts enter the guard.
6. Remove the root exception in `shell_guard.rs:435-443` if root execution is
   within the guard's required policy boundary.
7. Update the shell-guard requirements, specification, operator runbook, and
   generated templates so they no longer describe `/bin/bash.real` as an
   operator execution channel.

## Verification Criteria

The remediation is complete only when all are true:

- No application Makefile or Makefile template selects `/bin/bash.real` as
  `SHELL` or `SCRIPT_BASH`.
- No production script executes `/bin/bash.real` directly or via a PATH alias.
- Root Make recipes execute through guarded `/bin/bash`.
- The only runtime reference to `/bin/bash.real` is the guard's verified,
  post-validation `execve` transition.
- Tests fail if a root recipe, root script, or temporary PATH entry attempts to
  resolve `bash` to the sealed interpreter.
