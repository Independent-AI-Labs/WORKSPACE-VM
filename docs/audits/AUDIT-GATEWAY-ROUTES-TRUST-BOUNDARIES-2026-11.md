# Gateway Routes and Passthrough Trust Boundaries

**Date:** 2026-11-02
**Status:** Open
**Scope:** `projects/WORKSPACE-GATEWAY/conf/apisix.yaml`, admin allowlist, Grafana auth-proxy publish, and provider-sync. Product code was not changed.

## Executive Summary

Several relay routes are open proxies. The provider catalog and its sync trigger are unauthenticated. Admin API trust is the whole compose subnet. Grafana on loopback honors `X-WEBAUTH-USER` from `127.0.0.1`.

## Finding 1: Unauthenticated relays

`conf/apisix.yaml` routes `relay-opencode` (`/opencode/*`), `relay-opencode-zen`, `relay-anthropic`, `relay-anthropic-coding-plan`, `relay-grok`, `relay-token-plan`, and `relay-llamafile` have no `key-resolver` or `provider-oauth`. `relay-llamafile` (`conf/apisix.yaml:739-751`) proxies to `host.docker.internal:8765` over HTTP with no auth plugin. Host port `9080` is published (`res/docker/docker-compose.yml`).

Impact: anyone who can reach the gateway can use those upstreams, and can reach the host llamafile listener through the container.

Fix: require a virtual key or a network ACL per route. Do not publish llamafile on the same listener as public relays. Bind it to an internal listener.

## Finding 2: Provider catalog sync is world-callable

`conf/apisix.yaml:875-891` exposes `/gateway/providers*` with only `limit-count` on `remote_addr`. `plugins/custom/provider-sync.lua:169-183` runs `M.sync` on `POST /gateway/providers/sync` with no credential check. GET returns the enriched catalog, including auth route metadata (`provider-sync.lua:192-215`).

Impact: an anonymous caller can force outbound fetches to models.dev and provider endpoints, and can read which auth flows the gateway publishes.

Fix: require the admin key or a virtual key with a control-plane role. Keep GET catalog behind the same check if the deployment is not a public client bootstrap.

## Finding 3: Admin API allowlist is the compose network

`conf/config.yaml:19-31` `allow_admin` includes `10.99.0.0/16` plus specific gateway IPs, and `enable_admin_ui: true`. Dev publishes `127.0.0.1:9180` (`res/docker/docker-compose.yml:21`). Prod does not publish 9180, but the in-network allowlist still applies.

Impact: any container on `10.99.0.0/16` that learns `ADMIN_KEY` can change routes. The comment says this exists so rootless port-forward reaches the admin API.

Fix: allow only the published-port source and the seed host. Do not allow the whole `/16`. Keep the admin key out of data-plane containers.

## Finding 4: Grafana auth proxy trusts loopback

`res/docker/docker-compose.yml:224-228` sets `GF_AUTH_PROXY_ENABLED`, `GF_AUTH_PROXY_AUTO_SIGN_UP`, and a whitelist of `127.0.0.1/32` plus the edge CIDR. The port is `127.0.0.1:3030:3000`.

Impact: a local process that can open `localhost:3030` can send `X-WEBAUTH-USER` and receive an auto-provisioned session if the container sees the peer as `127.0.0.1`.

Fix: remove `127.0.0.1` from the whitelist when the port is published on the host. Require the edge proxy identity only. Disable auto sign-up or map the header to a fixed viewer.
