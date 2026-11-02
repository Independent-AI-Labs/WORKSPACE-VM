# Gateway Scripts, Hooks, and Secret Handling

**Date:** 2026-11-02
**Status:** Open
**Scope:** `projects/WORKSPACE-GATEWAY/res/scripts` key tooling and repo-root env files. Product code was not changed. Secret values are not copied into this audit.

## Executive Summary

Key scripts talk to OpenBao through `podman exec` and the env token. Issue prints the new virtual key to stdout. Show masks the upstream key. The on-disk env files are gitignored but hold live secrets, and dev and prod share admin and OpenBao tokens.

## Finding 1: Issue prints the virtual key; logs may capture it

`res/scripts/issue-key.sh` writes the new `vgw-*` id to stdout (`echo` of `Bearer ${KEY_ID}`). That id is the credential. `list-keys.sh` prints key ids, tenant, user, and active flag, not the upstream key. `gateway-key.sh` show masks `upstream_key` to four characters plus four. `pool-key.sh` `mask` does the same for pool keys.

Impact: CI logs, shell history, and Ansible output from `make key ARGS='issue ...'` retain a usable virtual key. Upstream keys are masked on the show path.

Fix: print the virtual key only to a mode-600 file or a tty, and not when stdout is not a terminal. Keep the mask on every list path.

## Finding 2: OpenBao calls use the ambient root-style token

`issue-key.sh`, `revoke-key.sh`, `list-keys.sh`, `pool-key.sh`, and `gateway-key.sh` call `curl` inside the OpenBao container with `X-Vault-Token` from `OPENBAO_TOKEN`. There is no per-command policy. Revoke is a read-modify-write of the whole JSON record (`revoke-key.sh`).

Impact: whoever can run these scripts can read and write every gateway key and pool. A partial failure on revoke can write a stale record back.

Fix: use a management token that is not the data-plane token. Revoke with a JSON merge patch that sets only `active` and `revoked_at`.

## Finding 3: Live env files are present and duplicated

`.gitignore` ignores `.env` and `.env.*`. `.env.example` is tracked and contains dummy values only. The working tree still has `.env` and `.env.prod` with non-dummy `ADMIN_KEY`, `OPENBAO_TOKEN`, provider keys, Grafana, ClickHouse, and etcd passwords. `ADMIN_KEY` and `OPENBAO_TOKEN` match across the two files. `RUNBOOK` text in `docker-compose.prod.yml` says the stacks do not share credentials.

Impact: any process that can read the repo directory can use admin, OpenBao, and data-store passwords. Dev and prod are not isolated for those two tokens.

Fix: rotate every value in both files. Generate distinct prod tokens. Confirm mode 600 and that backup jobs exclude both files.
