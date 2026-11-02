# Gateway SQL and Data Stores

**Date:** 2026-11-02
**Status:** Open
**Scope:** ClickHouse usage insert, OpenBao KV, and shared-dict quota state in `projects/WORKSPACE-GATEWAY`. Product code was not changed.

## Executive Summary

Usage rows are inserted as JSONEachRow, not by concatenating caller strings into SQL. The database name is substituted from plugin config. Quota and key caches live in worker shared memory and do not survive restart. OpenBao is the durable secret store and is reached with one token from the data plane.

## Finding 1: Database name is interpolated into the insert

`plugins/custom/sse-usage.lua:80-90` reads `conf/sql` template `ingest/usage-log.insert.sql` and replaces `{{ DB }}` with `conf.db` using `gsub`, with no identifier check. The row body is JSON (`sse-usage.lua:412-415`), so caller fields are not spliced into the SQL text. The HTTP query is the fixed template plus that database name.

Impact: a bad `db` value in route config becomes SQL. It is not request-controlled today. A future template that interpolates a header would be an injection.

Fix: allow only `[A-Za-z0-9_]+` for `conf.db`. Keep all caller data in the JSON body. Do not add request fields to the query string.

## Finding 2: Budgets are in-memory only

`key-resolver.lua:354-373` enforces `token_budget` and `cost_budget` with `ngx.shared.quota_counters`. `sse-usage.lua:447-459` increments that dict after the response. There is no ClickHouse read before admit. Restart clears the dict. `policy: local` on `limit-count` is per node.

Impact: a restart or a second gateway node resets spend. A client can exceed the configured budget by the number of nodes and by every restart.

Fix: admit against a durable counter (ClickHouse or OpenBao) or treat the shared dict as a hint and reconcile. Document budgets as advisory until that exists.

## Finding 3: OpenBao file storage is the secret of record

Key and pool records live at `secret/data/gateway/keys/` and `secret/data/gateway/upstream-pools/` (`docs/architecture/KEY-MANAGEMENT.md`, `key-resolver.lua` schema defaults). Pool records include raw provider keys. `disable_pool_key_in_openbao` writes `active: false` with the same `OPENBAO_TOKEN` the data plane uses to read.

Impact: APISIX process compromise is full read/write of gateway secrets. File-backed OpenBao snapshots are copies of those secrets.

Fix: split read and write tokens. Encrypt snapshots. Do not mount the OpenBao data volume into any other container.
