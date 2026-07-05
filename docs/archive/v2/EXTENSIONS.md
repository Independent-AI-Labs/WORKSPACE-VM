# AMI Extension Model

## Categorization & Ownership

| Extension | Category | Project | Status |
| :--- | :--- | :--- | :--- |
| ami-mail | Enterprise | WORKSPACE-STREAMS | Ready |
| ami-chat | Enterprise | WORKSPACE-STREAMS | Ready |
| ami-backup | Dev | AMI-DATAOPS | Ready |
| ami-restore | Dev | AMI-DATAOPS | Ready |
| ami-serve | Infra | WORKSPACE-VM | Degraded |
| ami-intake | Infra | WORKSPACE-VM | Degraded |

Extensions are discovered dynamically from `extension.manifest.yaml` files. To register a new extension, add it to your project's manifest, ensure the binary is in your `PATH`, and implement the standard `HealthCheckResult` protocol.
