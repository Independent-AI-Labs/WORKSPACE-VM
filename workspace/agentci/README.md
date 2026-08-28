# AgentCI

This directory is the proposed implementation root for AgentCI TypeScript
sources, schemas, tests, and release tooling. It is not an authority or runtime
declaration; current authority remains the applicable installed machine policy.

The minimum temporary release-test contract is one OpenCode-discoverable server
entrypoint and an artifact built only from this directory. The test installs that
artifact in a temporary location with a temporary OpenCode configuration outside
the existing configuration, records discovery/load/cleanup evidence, and removes
the temporary installation. This is not a normal AgentCI installation claim.

`tests/real-oc.integration.test.ts` packages AgentCI into a temporary prefix,
configures temporary HOME/XDG/OpenCode/AgentCI roots, then invokes the real
`oc` database option and separator dispatch path. It records configuration and
cleanup isolation evidence and explicitly skips runtime paths that the server
does not yet register or persist.

Authoritative design documents:

- [`REQ-AGENTCI`](../../docs/requirements/REQ-AGENTCI.md) (Draft target)
- [`SPEC-AGENTCI`](../../docs/specifications/SPEC-AGENTCI.md) (Draft target)
