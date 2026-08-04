# Dependency Audit

## Scope

This audit covers first-party files that participate in root `make install`,
`make install-ci`, `make init`, and VM provisioning. It excludes language lock
files, generated files, build output, and third-party source repositories.

## Current Registries

| Registry | Current purpose | Consumer |
|---|---|---|
| `config/system-deps.yaml` | Host apt/brew packages and binary checks | `projects/CI/scripts/install-system-deps` via root Make targets |
| `workspace/config/bootstrap-components.yaml` | Component identity, installation script, detection, and grouping | `bootstrap_component_defs.py`, installer TUI |
| `workspace/config/install-defaults.yaml` | Default selected components | `bootstrap_installer.py --defaults` |
| `workspace/config/vm-*.yaml` | Guest component selections | Rendered as `vm-install-defaults.yaml` for guest `make install-ci` |
| `res/qemu-pins.yaml` | QEMU artifact versions, guest image URLs, and hashes | QEMU bootstrap/backend |

## Current Flow

`make init-check` and `make init` delegate system dependency validation and
installation to `projects/CI/scripts/install-system-deps`. `make core` installs
CI-provided tools and invokes VM-specific bootstrap scripts. `make install-ci`
passes a component list into `bootstrap_installer.py`, which resolves each name
through `bootstrap-components.yaml` and invokes its script.

## Completed Extraction

The prior migration extracted the shared host prerequisite list from bootstrap
component metadata into `config/system-deps.yaml`. It did not extract all
external dependency pins.

## Gaps

The following remain hardcoded in executable VM code rather than a dependency
artifact catalog:

- Bun, Go, GitHub CLI, GitLab CLI, kubectl, Helm, Pandoc, sd, Traefik, and
  git-xet release versions.
- wkhtmltopdf and fallback package artifact versions.
- Bootlin toolchain and cosmocc versions.
- Release URLs and artifact selection rules associated with those tools.
- GitHub Action references in `.github/workflows/ci.yml`.
- Inline package installation in component-specific setup scripts, including
  OpenVPN, QEMU, Vulkan, Intel, and oneAPI setup.

`res/qemu-pins.yaml` is the correct precedent for artifact pins. `config/` is
for host package policy and runtime configuration, not release artifacts.

## Structural Findings

- `bootstrap_component_defs.py` still models `requires` fields despite
  `bootstrap-components.yaml` declaring them removed. The fields are no longer
  used to select or install host dependencies.
- `system-deps.yaml` component tags are not passed from selected components to
  the system dependency resolver in the root Make flow.
- `workspace/config/install-all.yaml` is stale: it is not consumed by the
  documented E2E path and includes names absent from the current component
  catalog. Unknown names are only warned about and skipped.
- `init-check` requires the CI resolver before later installation steps clone
  or synchronize projects, so a fresh checkout is not self-contained.

## Required End State

Create `res/dependency-pins.yaml` in this repository as the single source for
VM-owned downloaded tools, image artifacts, checksums, and workflow action
references. Keep language dependencies in their native manifests and host
packages in `config/system-deps.yaml`. Each bootstrap component should point to
one pin entry, not carry a duplicate version. The dependency scanner must audit
the catalog and fail on undeclared executable pins.
