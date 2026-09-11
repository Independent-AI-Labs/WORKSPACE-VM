# Remediation TODO

**Status:** Active
**Rule:** Do not mark an item complete without recorded execution evidence.

Deferred implementation violations. Each item names the exact violation and
the required fix.

## Bare-interpreter invocations (hermetic-execution policy)

- [x] `workspace/scripts/bin/bootstrap-repos`: PATH-based resolution removed;
      boot-interpreter-only with explicit bootstrap error (2026-08-31,
      `bash -n` clean).
- [x] `workspace/scripts/utils/git-status-all` (2 sites): `uv run python -`
      heredocs (2026-08-31, `bash -n` clean).
- [x] `workspace/scripts/shell/shell-setup` (~206): `uv run python "$helper"`
      (2026-08-31, `bash -n` clean).
- [x] `workspace/cli/vm_main.py:28`: usage string now `uv run python -m ...`
      (2026-08-31, `py_compile` clean).
- [x] `scripts/setup/test_install_e2e.sh` (4 sites): `uv run python` probes,
      heredoc form (2026-08-31, `bash -n` clean).
- [x] `scripts/setup/test_install_e2e_moon_phases.sh` (~68): `uv run python -`
      heredoc (2026-08-31).
- [x] `scripts/setup/compute-llamafile-parallel.sh` (~57): `uv run python "$@"`
      with explicit uv-missing error (2026-08-31).

## Deployment / operator items

- [ ] `.boot-linux/bin/openvpn` symlink missing (openvpn bootstrap component
      never ran on this machine). `workspace/cli/vpn_core.py` now requires it.
      Fix: operator runs the openvpn bootstrap component.

## Test coverage gaps

- [ ] `workspace/agentci`: `test:live` script declared but unimplemented; no
      integration test against a real `oc` binary. Fix: implement both.
