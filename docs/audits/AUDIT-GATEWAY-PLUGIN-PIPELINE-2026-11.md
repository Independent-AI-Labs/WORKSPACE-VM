# Gateway Plugin Pipeline and Request Mutation

**Date:** 2026-11-02
**Status:** Open
**Scope:** `projects/WORKSPACE-GATEWAY/plugins/custom` access-phase header and identity mutation. Product code was not changed.

## Executive Summary

Callers can set `X-Gateway-Key-Id` on routes that do not overwrite it. `key-meta` and `sse-usage` then treat that header as the credential. Rate-limit and usage attribution follow the header, not the bearer. OAuth upstream tokens are decoded without signature checks; session lookup still uses the store.

## Finding 1: Client identity headers drive rate limit and usage

`key-meta.lua:42-47` hashes `X-Gateway-Key-Id` when it is non-empty and not `passthrough`, and ignores the bearer. `conf/apisix.yaml` `limit-count` uses `key: http_x_key_hash`. `sse-usage.lua:317-328` uses the same rule for `usage_log.key_id`. `key-resolver` (priority 2555) overwrites the header only on routes that mount it. `key-meta` (priority 2530) does not strip a caller header first. Passthrough routes never mount `key-resolver`.

Impact: on `/opencode/*` and the other passthrough relays, a caller rotates `X-Gateway-Key-Id` and gets a new rate-limit bucket. The same header attributes spend to another key hash in ClickHouse. Federated routes are safe only because `key-resolver` runs first and replaces the header.

Fix: delete `X-Gateway-*` and `X-Key-Hash` at the start of access, before any plugin reads them. Set them only from resolver or OAuth session state. Rate-limit on the hashed bearer or on `ctx.consumer`, not on a request header.

## Finding 2: Upstream JWT claims are unverified

`plugins/custom/oauth_jwt.lua:29-38` base64-decodes the payload and returns claims. It does not check the signature, `iss`, or `aud`. `expires_at` and `subject` use that decode. Session load is by bearer hash in `oauth_store`, so a forged bearer is not accepted unless it is already stored.

Impact: expiry and `sub` for a stored token can be wrong if the provider token is tampered after storage, or if a future caller passes an unverified JWT into `subject()`. Refresh decisions can run early or late.

Fix: verify provider JWTs with the provider JWKS before using `exp` or `sub`. If the token is opaque, do not decode it; trust only the token-endpoint JSON stored at issue time.

## Finding 3: Device start is unauthenticated by design, poll is the only gate

`provider-oauth.lua:332-337` starts a device flow with no caller auth. `oauth_broker.lua:6-15` builds the client `device_code` as `gw-` plus SHA-256 of upstream code, request id, `ngx.now()`, and `math.random()`. Poll loads that code from OpenBao (`provider-oauth.lua:166-171`).

Impact: anyone who can reach `/openai/*/auth/device` or the Kimi equivalent can start a provider device login. The gateway code is not guessable if `math.random` is seeded, but the endpoint is an unauthenticated write into OpenBao and an unauthenticated call to the provider.

Fix: require a virtual key or an admin credential before `start_device_flow`. Keep the gateway device code. Seed `math.random` from `resty.random` bytes, not libc `math.random`.
