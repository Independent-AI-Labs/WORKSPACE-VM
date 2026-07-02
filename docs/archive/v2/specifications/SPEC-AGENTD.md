# SPEC-AGENTD: Gateway and OIDC/A2A Proxy

## Overview
`ami-agentd` serves as the centralized Rust (Axum) gateway for the WORKSPACE-VM ecosystem, bridging external HTTPS/SSE requests to local, container-isolated AI agents via A2A protocol over Unix Domain Sockets (UDS).

## Architecture
- **Host Layer:** Single binary CLI/Daemon.
- **Proxy Layer:** Handles OIDC JWT validation, A2A schema enforcement, and TLS termination.
- **Agent Layer:** Proxies A2A v0.3 requests to agent-specific UDS endpoints (`.mesh/`).

## API Contract
- `POST /agents/{agent_name}/messages:stream`
- Authorization: Bearer {jwt}
- Protocol: A2A v0.3 (streamed SSE artifacts)

## Security
- OIDC multi-issuer validation.
- UDS-only agent communication (no TCP ports exposed on agents).
- Structured audit logging to `AMI-DATAOPS` PostgreSQL.