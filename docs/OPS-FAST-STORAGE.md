# OPS: Fast storage provisioning and migration (MOVED)

**Document ID:** WS-OPS-FAST-STORAGE-v0.1
**Status:** Superseded 2026-10-10, see WORKSPACE-DATAOPS
**Last Updated:** 2026-10-10

This runbook moved to
[`projects/WORKSPACE-DATAOPS/docs/runbooks/RUNBOOK-STORAGE.md`](../projects/WORKSPACE-DATAOPS/docs/runbooks/RUNBOOK-STORAGE.md)
as part of the host storage management consolidation (WORKSPACE-DATAOPS
[REQ-STORAGE](../projects/WORKSPACE-DATAOPS/docs/requirements/REQ-STORAGE.md) /
[SPEC-STORAGE](../projects/WORKSPACE-DATAOPS/docs/specifications/SPEC-STORAGE.md)).

WORKSPACE-DATAOPS now owns fast-storage provisioning, data migration, data-disk
mount/persist, and the storage-locations seam. The former
`make configure-fast-storage` / `make migrate-fast-storage` targets are replaced
by `make storage-provision` / `make storage-migrate` in WORKSPACE-DATAOPS.