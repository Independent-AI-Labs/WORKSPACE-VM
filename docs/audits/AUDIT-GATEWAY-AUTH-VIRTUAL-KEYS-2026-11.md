# Gateway Auth, Virtual Keys, and Credential Storage

**Date:** 2026-11-02
**Status:** Open
**Scope:** `projects/WORKSPACE-GATEWAY` inbound auth, `vgw-*` resolution, OpenBao key records, and on-disk credential files. Product code was not changed.

## Executive Summary

Virtual keys are resolved in `key-resolver` and cached with the upstream secret. Non-`vgw-` bearers are accepted as passthrough and forwarded upstream. Revocation is delayed by the route cache TTL. Dev and prod env files on disk reuse the same admin and OpenBao tokens. Those files are gitignored; the values are not repeated here.

## Finding 1: Passthrough is an unauthenticated credential class

`plugins/custom/key-resolver.lua:286-296` treats any bearer that does not start with `vgw-` as success. It sets `X-Gateway-Key-Id: passthrough` and returns without an OpenBao lookup. Routes that do not mount `key-resolver` (`conf/apisix.yaml` `relay-opencode`, `relay-anthropic-coding-plan`, `relay-grok`, `relay-llamafile`) forward the caller `Authorization` as-is.

Impact: possession of any non-empty bearer, or no gateway key at all on routes without `key-resolver`, reaches the upstream with the caller credential. There is no gateway identity.

Fix: mount an explicit auth plugin on every data-plane route. Reject non-`vgw-` bearers unless the route is marked passthrough in config and the edge network is not public. Do not infer passthrough from prefix mismatch.

## Finding 2: Revocation lags the key cache

`key-resolver.lua:251-268` returns the cached OpenBao record, including `active`, until `cache_ttl`. Federated routes set `cache_ttl: 5` (`conf/apisix.yaml:109`). The plugin default is 300 seconds (`key-resolver.lua:37-39`). A revoked key still authenticates until that entry expires. Cache stores the full record, including `upstream_key`, in `ngx.shared.key_cache`.

Impact: revoke is not immediate. A worker memory dump exposes upstream provider keys.

Fix: cache only a hash plus non-secret attributes, or store a generation counter and check `active` on a short path. Document the 5s window as the revoke SLA and reject the 300s default on any route that can issue keys.

## Finding 3: Dev and prod share admin and OpenBao tokens

`.env` and `.env.prod` are gitignored (`.gitignore` lines 33-34). Both files on this host contain the same `ADMIN_KEY` and `OPENBAO_TOKEN`. `res/docker/docker-compose.prod.yml` says the stacks share no credential file. `key-resolver` uses that token for KV reads and for pool-disable writes (`key-resolver.lua:110` area, `openbao_put`).

Impact: a dev token leak is a prod OpenBao and Admin API credential. The data-plane token can rewrite pool records.

Fix: issue distinct tokens. Give the data plane a read-only policy on `secret/data/gateway/keys/*` and a narrow write on pool `active` flags. Rotate the shared values that are already on disk.
