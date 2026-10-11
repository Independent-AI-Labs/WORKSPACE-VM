# Requirements: Install-Time Storage Planning Step (SUPERSEDED)

**Document ID:** WS-REQ-INSTALL-STORAGE-v0.1
**Status:** Superseded 2026-10-10, absorbed into WORKSPACE-DATAOPS
[REQ-STORAGE](../../projects/WORKSPACE-DATAOPS/docs/requirements/REQ-STORAGE.md)
**Last Updated:** 2026-10-10

The storage-planning step is now owned by WORKSPACE-DATAOPS. Two outcomes from
this document carried forward:

- **R8 (storage-locations seam):** implemented in DATAOPS
  [REQ-STORAGE](../../projects/WORKSPACE-DATAOPS/docs/requirements/REQ-STORAGE.md)
  FR-1 as `workspace/config/storage-locations.yaml` (env → seam → default).
- **R9 (installer integration):** the WORKSPACE-VM installer keeps only a thin
  hook that calls the DATAOPS storage-planning path; the locations themselves
  and the provisioning/migration scripts live in DATAOPS
  [SPEC-STORAGE](../../projects/WORKSPACE-DATAOPS/docs/specifications/SPEC-STORAGE.md).
- **R10 (destructive steps are operator-run):** preserved; DATAOPS prints the
  interactive `wipefs`/`parted`/`mkfs` commands rather than executing them.

See the migration record in
[`docs/proposals/MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md`](../proposals/MIGRATION-CLI-COMPONENTS-TO-DATAOPS.md)
§16.