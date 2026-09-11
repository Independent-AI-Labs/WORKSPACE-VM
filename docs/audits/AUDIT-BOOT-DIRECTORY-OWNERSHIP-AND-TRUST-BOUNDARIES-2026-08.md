# Boot Directory Ownership and Trust Boundary Audit

**Date:** 2026-08-30  
**Scope:** Checkout-local `.boot-*`, immutable `/opt/workspace-ci`, component
installation, protected CI execution, and service runtime tooling  
**Status:** Architecture recommendation; implementation pending

## Executive Summary

`make install` is currently broken for an unprivileged user because the local
workspace `.boot-linux` directory is owned by `root:root` while the installer
still dispatches many component scripts that write into that directory.

The repository currently conflates two distinct trust domains under the same
`.boot-linux` name:

1. A checkout-local development tool directory populated by `make install`.
2. The protected boot directory inside the immutable `/opt/workspace-ci`
   deployment used by CI enforcement.

The WORKSPACE-CI requirements already distinguish these domains. They require
only `/opt/workspace-ci/.boot-linux` to be root-owned and immutable. They
describe checkout-local `.boot-linux` as a source-development directory.
However, workspace-level operating rules now describe every `.boot-linux` and
`.boot-macos` directory as a root-owned trust boundary. The installed ownership
follows that broader rule, while the installer still follows the original
development-directory model.

Neither making all tools root-only nor making all tools user-owned is correct.
The recommended architecture has three explicit domains while preserving the
existing `.boot-*` composition contract:

| Domain | Proposed path | Ownership | Mutation model |
| --- | --- | --- | --- |
| Developer tools | `<checkout>/.boot-linux` or `.boot-macos` | Developer | Mutable and disposable |
| CI enforcement | `/opt/workspace-ci` | Root | Verified, atomically deployed, immutable |
| Protected service runtime | `/opt/workspace-runtime` or OS packages | Root | Reviewed deployment only |

Boot ownership must be derived from the complete path and deployment context,
not from the `.boot-*` basename. Checkout boot directories remain user-owned so
projects can compose one another's tools. Boot directories inside root-deployed
artifacts remain verified and immutable.

`make install` should remain entirely unprivileged. It should install ordinary
development tools into the user-owned checkout `.boot-*`. `make init` should
install operating-system dependencies and invoke only narrowly defined
privileged deployment interfaces. Protected CI tools should continue to be
constructed and sealed exclusively through WORKSPACE-CI's deployment process.

## Incident and Observed State

The reported failure occurred while Playwright attempted to download browsers
to:

```text
/home/agent/WORKSPACE-VM/.boot-linux/playwright-browsers
```

Filesystem inspection showed:

```text
drwxr-xr-x root:root .boot-linux
drwxr-xr-x root:root .boot-linux/bin
drwxr-xr-x root:root .boot-linux/playwright-browsers
drwxr-xr-x root:root .boot-linux/python-env
drwxr-xr-x root:root .boot-linux/uv-tools
```

The unprivileged workspace user cannot create or update files there. A direct
write check failed with `Permission denied`.

The Playwright browser directories already contained completion markers, but
the bootstrap script's installation check still entered its download path. The
download then failed because the target directory was not writable. This was
the first visible failure, but Playwright is not the underlying architectural
problem.

The component manifest contains many installers that write to checkout-local
`.boot-linux`, including:

- Python and its local environment;
- GCC/musl and Git Xet;
- Go and OpenCode;
- Traefik, Kubernetes tools, and QEMU;
- Google Cloud, GitHub, GitLab, and Hugging Face clients;
- cloudflared and OpenVPN;
- Pandoc, TeX Live, PDF utilities, and wkhtmltopdf;
- ADB and Matrix administration tools.

As a result, a root-owned checkout `.boot-linux` makes the non-root installer
structurally unable to perform its declared work.

## Current Installation Model

### `make install`

The root Makefile documents `make install` and `make install-ci` as non-root
operations. They invoke `bootstrap_installer.py`, which resolves components from
`workspace/config/bootstrap-components.yaml` and executes component bootstrap
scripts from the writable workspace checkout or selected scripts from the
sealed WORKSPACE-CI deployment.

The local scripts generally derive their installation root from the checkout:

```text
<workspace>/.boot-linux
```

They then download archives, extract software, create virtual environments,
install npm or uv tools, and create command links beneath that directory.

These operations are ordinary developer environment management. They require
write access by the developer and should not require root authority.

### `make init`

`make init` has two responsibilities:

1. Resolve and install host operating-system dependencies.
2. When invoked as root, execute `init-root` for privileged machine setup.

`init-root` deploys the sealed WORKSPACE-CI artifact, installs the Git guard,
installs protected hooks and exemptions, and configures system logging limits.
Those operations affect machine-wide paths or enforcement boundaries and
legitimately require privileged authority.

### `/opt/workspace-ci`

`/opt/workspace-ci` is a separate deployment artifact. Its source is reviewed
WORKSPACE-CI history rather than arbitrary local working-tree content. The
deployment process constructs a root-controlled candidate, verifies its source
identity and runtime behavior, atomically publishes it, and applies immutable
attributes.

Protected hooks and commands resolve this artifact by absolute path. They fail
closed when it is absent, mutable, or unverifiable. This is materially
different from a developer tool cache.

## Repository Contract Analysis

### WORKSPACE-CI boot layout

`projects/WORKSPACE-CI/docs/requirements/REQ-BOOT-LAYOUT.md` defines:

- `<checkout>/.boot-linux` for Linux source development;
- `<checkout>/.boot-macos` for macOS source development;
- `/opt/workspace-ci/.boot-linux` for protected Linux execution;
- `/opt/.workspace-ci.candidate/.boot-linux` for candidate construction.

The requirement states that protected commands must not use a boot directory
from HOME or a writable sibling project. It separately states that the complete
**deployed** `.boot-linux` directory is root-owned and immutable as part of
`/opt/workspace-ci`.

`projects/WORKSPACE-CI/docs/specifications/SPEC-BOOT-LAYOUT.md` reinforces that
split:

- source-development commands resolve tools from the checkout;
- deployment construction resolves tools inside the candidate namespace;
- protected runtime commands resolve tools from `/opt/workspace-ci`;
- no post-publication operation writes into the deployed artifact.

### Workspace operating rule

The workspace-level `AGENTS.md` describes `.boot-linux` and `.boot-macos` as
root-owned protected boot boundaries without qualifying the path. That broad
statement conflicts with the more precise WORKSPACE-CI contract and with the
non-root component installation design.

### Git history

Repository history shows that checkout-local `.boot-linux` was originally
intended to be user-writable.

Commit `338fb5c` described a root-owned local `.boot-linux` as the result of a
"prior broken sudo install." Its remediation expected the local directory to be
recreated by the normal user.

Commit `7644b7a` introduced `sudo make init` for privileged deployment, guard,
hook, and system-limit operations. Its stated goal was to keep `make install`
and `make install-ci` strictly non-root. It did not move the general development
tool catalog into the privileged trust domain.

The present state therefore appears to be architectural drift rather than a
coherent root-only installation design.

## External Guidance

### Filesystem Hierarchy Standard

The Filesystem Hierarchy Standard reserves `/opt` for administrator-installed
add-on application packages. It separates static package content from mutable
runtime state, which belongs under `/var/opt`, and host-specific configuration,
which belongs under `/etc/opt`.

This supports using `/opt/workspace-ci` for a machine-managed static enforcement
artifact. It does not imply that disposable project-development environments
should also be installed by root.

Source:
[Filesystem Hierarchy Standard: `/opt`](https://specifications.freedesktop.org/fhs/latest/opt.html).

### Python virtual environments

Python's documentation describes virtual environments as isolated directories
commonly located in a project as `.venv`. They are not committed to source
control, are considered disposable, and should be recreated instead of moved.

This model aligns with a user-owned checkout `.boot-*`. Making ordinary
project environments root-owned prevents their intended update and recreation
lifecycle.

Source:
[Python `venv` documentation](https://docs.python.org/3/library/venv.html).

### uv tool environments

uv distinguishes temporary or persistent isolated tool environments from
project dependencies. Tool environments are managed state and can be upgraded,
reinstalled, or recreated. uv advises against manually mutating their internal
contents, but it does not require root ownership for user tools.

Source: [uv tool environments](https://docs.astral.sh/uv/concepts/tools/).

### Supply-chain integrity

SLSA focuses on source and build integrity: accepted source should represent the
producer's intent, artifacts should be built from the expected source and
dependencies, and artifacts should not be modified between development stages.

That model supports the reviewed candidate and immutable publication process
for `/opt/workspace-ci`. Merely making arbitrary downloaded developer tools
root-owned does not establish provenance or integrity. It can instead increase
risk if unverified downloads are performed with root authority.

Source:
[SLSA supply-chain threats](https://slsa.dev/spec/v1.2/threats-overview).

### Secure development practices

NIST SP 800-218 recommends integrating security practices into the software
development lifecycle to reduce vulnerabilities, mitigate impact, and address
root causes. Applied here, the relevant principle is to protect the release and
enforcement boundary without unnecessarily granting the development installer
machine-wide authority.

Source:
[NIST SP 800-218](https://csrc.nist.gov/pubs/sp/800/218/final).

## Architecture Options

### Option A: Make all installation root-only

Under this model, `sudo make install` would populate checkout `.boot-linux`, and
ordinary users would consume but not update those tools.

#### Benefits

- Straightforward filesystem permissions.
- Users cannot replace installed executables after installation.
- Shared tools could be consistent across users if installed outside a single
  checkout.

#### Risks

- The root process executes shell scripts and Makefile logic from an
  agent-writable checkout.
- npm, uv, browser downloads, tar extraction, and third-party bootstrap scripts
  receive unnecessary root authority.
- Generated files and environments inside the checkout become root-owned.
- Routine development-tool updates require operator intervention.
- A compromised branch or installer can modify the entire machine.
- The privileged review surface expands from a deployment mechanism to dozens
  of heterogeneous bootstrap scripts.
- Tools installed into one user's checkout are not naturally suitable as
  machine-wide packages.

#### Assessment

Rejected. Root-only installation solves the immediate write failure by greatly
expanding privileged execution and operational cost.

### Option B: Make all tooling user-owned

Under this model, both local development tools and protected CI tools would be
writable by the workspace user.

#### Benefits

- Simple installation and updates.
- No operator involvement for routine tool management.
- Familiar development environment behavior.

#### Risks

- A user can replace the same hook implementation intended to constrain that
  user's Git operations.
- Policy, scanners, interpreters, and protected command dependencies become
  advisory rather than enforceable.
- Services may execute binaries writable by an account they are intended to
  isolate or constrain.
- Post-review artifact tampering is not prevented.

#### Assessment

Rejected. Protected enforcement cannot rely on user-writable implementation or
runtime dependencies.

### Option C: Path-qualified `.boot-*` ownership

This model would retain the name `.boot-linux`, treating it as user-owned in a
checkout and root-owned beneath `/opt`.

#### Benefits

- Smallest path migration.
- Consistent internal directory layout.
- Matches the current WORKSPACE-CI boot-layout wording.

#### Requirements

- Ownership checks must use the resolved full path, not the basename.
- General development composition may include owner-writable project boots.
- Protected hooks must use fixed `/opt/workspace-ci` paths and must not consume
  general composed PATH entries.
- Inherited boot directories must be non-world-writable and owned by the
  inherited project owner.
- Symlink resolution must not escape the declared inherited project.

#### Assessment

Recommended. This preserves boot composition while making the trust decision
explicit at each consumer.

## Recommended Architecture

### Domain 1: Developer tools

Use:

```text
<checkout>/.boot-linux
<checkout>/.boot-macos
```

Properties:

- owned by the checkout owner;
- writable only by that owner under normal permissions;
- ignored by Git;
- disposable and reproducible from pinned manifests;
- populated only by non-root installation commands;
- never used by protected Git hooks;
- never used by root services;
- never treated as machine-wide policy or enforcement state.

Candidate tools include Playwright, OpenCode, Go, developer Python, cloud CLIs,
document tools, ADB, interactive Kubernetes clients, and similar workstation
utilities.

Local tools should still be pinned and checksum-verified where practical.
User ownership is not a reason to accept unverified downloads. It simply keeps
developer tooling outside the privileged machine boundary.

### Domain 2: Protected CI enforcement

Continue using:

```text
/opt/workspace-ci
```

Properties:

- constructed from reviewed upstream source;
- built in a root-controlled candidate;
- uses pinned and verified dependencies;
- verifies runtime paths and executable identities;
- published atomically;
- root-owned and non-writable by other users;
- sealed with immutable attributes;
- consumed through absolute paths;
- never modified in place after publication.

This artifact should contain only what the protected CI and guard workflows
need. Examples include hook implementation, policy data, CI Python and Node
runtimes, Moon, Gitleaks, and other enforcement dependencies.

### Domain 3: Protected service runtime

Use operating-system packages where they meet version and functionality needs.
For software that must be vendored, pinned, or built independently, use a
separate deployment such as:

```text
/opt/workspace-runtime
```

Properties:

- deployed through an explicit reviewed privileged interface;
- contains static service executables, not mutable state;
- runtime state belongs under an appropriate user directory, `/var/lib`, or
  `/var/opt` depending on service ownership;
- configuration belongs under a protected configuration path;
- services use absolute executable paths;
- ordinary user installers cannot modify service executables.

This domain prevents `/opt/workspace-ci` from becoming a general-purpose binary
warehouse for VPN, proxy, browser, document, and VM tooling.

## Tool Classification Rules

Each component should be classified by its consumer and authority rather than
by language or installation mechanism.

### Local developer tool

A tool belongs in the checkout-local `.boot-*` when all of the following are
true:

- it is invoked interactively or by user-owned development automation;
- replacing it gives no authority beyond that user's existing account;
- it is not relied upon to enforce policy against that user;
- no privileged service executes it;
- it can be recreated from repository configuration.

### CI-protected tool

A tool belongs in `/opt/workspace-ci` when any of the following are true:

- protected Git hooks execute it;
- it interprets or applies protected policy;
- its output directly determines whether a protected commit or push proceeds;
- the Git guard depends on its behavior or executable identity.

### Runtime-protected tool

A tool belongs in OS packages or `/opt/workspace-runtime` when any of the
following are true:

- a root service executes it;
- multiple users or services rely on one administrator-controlled identity;
- it handles privileged networking, credentials, or machine-wide state;
- changing it would cross an authority boundary;
- service reproducibility requires a reviewed immutable version.

### Dual-use tools

Some tools legitimately need two installations. For example, a developer may
use a local Podman or browser while CI or a service requires a protected pinned
version. These should be distinct artifacts with distinct paths. A writable
local installation must never be promoted implicitly into protected use.

## Immutability Analysis

### Where immutability is valuable

Immutability is justified when it protects a reviewed trust decision:

- CI policy and hook implementation;
- guard executables;
- system or security-sensitive service binaries;
- runtime dependencies whose replacement would alter enforcement;
- a published artifact that must remain identical to the verified candidate.

### Where immutability is counterproductive

Immutability is not justified merely because a file is executable. It is
counterproductive for:

- disposable project virtual environments;
- browser downloads used for local testing;
- interactive cloud and repository clients;
- frequently updated coding assistants;
- local SDKs and compilers selected by the developer;
- caches and generated package state.

### Limitations

Root ownership and immutable flags do not establish artifact trust by
themselves. They protect whatever bytes were installed, including malicious or
incorrect bytes. The deployment must first establish source identity,
dependency identity, expected checksums, and runtime behavior.

Immutability also adds availability and recovery costs. Updates require an
operator, filesystems must support the attributes, and interrupted publication
must remain recoverable. It should therefore be applied only to the smallest
complete artifact that requires protection.

## Privileged Execution Risk

The most important negative requirement is:

> A privileged target must not execute arbitrary bootstrap logic from the
> writable workspace checkout as its installation mechanism.

The root-owned WORKSPACE-CI deployment is comparatively defensible because it
resolves reviewed upstream source, constructs a controlled candidate, verifies
it, and publishes atomically.

By contrast, moving ordinary component scripts directly into `init-root` means
that root executes the current writable checkout. A local edit, compromised
branch, malicious dependency response, unsafe archive, or script defect can then
modify the host with full authority.

Privileged deployment should therefore be narrow and data-driven:

- fixed destination paths;
- reviewed source identity;
- pinned versions and checksums;
- safe archive extraction;
- explicit ownership and modes;
- candidate verification before publication;
- no use of user-controlled PATH entries;
- no environment-variable redirect of protected destinations;
- no post-publication mutation.

## Playwright Disposition

Playwright exposed the problem but does not warrant making the whole installer
privileged.

For local development and browser testing:

- install Playwright and browsers into the user-owned checkout `.boot-*`;
- pin the Playwright package and browser revision;
- keep browser state out of HOME if project containment is required;
- allow the developer to update or recreate it without root.

If protected CI genuinely executes browser tests:

- install a separate Playwright runtime inside the WORKSPACE-CI candidate;
- pin and verify browser assets;
- verify the browser runs before publication;
- seal it with the artifact;
- never let protected CI resolve the developer's browser directory.

The writable-checkout Playwright bootstrap therefore remains in the non-root
component installer and must reject foreign-owned or non-writable local boots.

## Proposed Command Contract

### `make install`

- Must run as a non-root user.
- Must reject root invocation to prevent root-owned local state.
- May write the checkout, `.venv`, checkout `.boot-*`, and documented user
  configuration paths.
- Must not write `/opt`, protected `.boot-*`, system configuration, or protected
  hooks.
- Must complete without asking for sudo.

### `make install-ci`

- Must use the same non-root component semantics as `make install`.
- Must be deterministic from its defaults file.
- Must not imply that local developer tools are protected CI artifacts.

### `make init`

- May install operating-system dependencies through the approved package
  manager flow.
- May invoke narrowly defined privileged deployment targets.
- Must not become the general developer tool installer.
- Must not populate user-owned local development state as root.

### `make deploy-ci`

- Remains the sole writer of `/opt/workspace-ci`.
- Must continue to use reviewed source rather than local dirty content.
- Must preserve candidate verification, atomic publication, and sealing.

### Runtime deployment

- Should use a separate explicit target only if OS packages are insufficient.
- Must deploy from reviewed and verified inputs.
- Must not invoke the interactive component catalog as root.

## Migration Plan

### Phase 1: Define boundaries

1. Update the workspace and WORKSPACE-CI requirements to define the three trust
   domains.
2. Define checkout `.boot-linux` and `.boot-macos` as user-owned disposable
   development state.
3. Define `.boot-*` beneath root-deployed artifacts as protected state.
4. Define the criteria for service-runtime protection.
5. Record that protected consumers must use absolute paths.

### Phase 2: Centralize path resolution

1. Introduce one platform-aware local tools path resolver.
2. Replace script-specific defaults such as `AMI_ROOT/.boot-linux` and
   `BOOT_LINUX_DIR` where they select developer destinations.
3. Keep protected path resolution fixed and non-overridable.
4. Preserve explicit path parameters only for tests and controlled build
   functions.
5. Reject attempts to point a local installer at `/opt` or a protected boot
   directory.

### Phase 3: Classify the catalog

1. Inventory every component and every executable consumer.
2. Mark each component as local, CI-protected, runtime-protected, or dual-use.
3. Remove duplicate local entries for tools that are only CI implementation
   details.
4. Add a separate deployment source for service binaries only where required.
5. Document dual installations rather than allowing implicit cross-domain use.

### Phase 4: Repair the target graph

1. Make `make install` fail clearly when invoked as root.
2. Ensure all selected local component scripts write only to
   checkout `.boot-*` or other documented user-owned paths.
3. Remove ordinary component bootstraps from `init-root`.
4. Keep WORKSPACE-CI deployment and protected hook installation privileged.
5. Keep operating-system package installation in `make init`.
6. Add a distinct runtime deployment target if the classification proves it is
   required.

### Phase 5: Migrate consumers

Update:

- shell PATH setup;
- component detection and version commands;
- extension registration;
- browser scripts;
- service templates;
- VM image synchronization;
- QEMU boot copying;
- test fixtures;
- installation documentation;
- environment containment checks.

Every system or protected service should be inspected to ensure it does not
resolve a writable checkout executable through PATH or a symlink.

### Phase 6: Build fresh local state

1. Require the checkout `.boot-*` to be owned and writable by the normal user.
2. Run the corrected installer to populate it.
3. Verify versions, key executable behavior, and inherited boot composition.
4. Do not mutate a foreign-owned checkout boot automatically.

### Phase 7: Retire the legacy path

1. Prove no tracked configuration, process, service, shell startup, or test
   resolves the checkout's old `.boot-linux`.
2. Produce an exact operator inventory of the legacy path.
3. Perform retirement through a narrow reviewed operator action.
4. Preserve `/opt/workspace-ci/.boot-linux` as part of the protected artifact.

## Required Tests

### Local installation

- A clean non-root `make install-ci` succeeds.
- Selected components install beneath the checkout `.boot-*`.
- The installer does not write `/opt`, protected `.boot-*`, or HOME-global
  package locations.
- Local tools can be deleted and recreated without privileged actions.
- Root invocation fails before creating local state.

### Protected CI

- Hooks resolve every implementation dependency from `/opt/workspace-ci`.
- Environment variables cannot redirect protected tool paths.
- Missing, writable, replaced, or unsealed artifacts fail closed.
- Deployment uses reviewed source and verified dependency identities.
- Candidate publication remains atomic and final paths remain executable.

### Services

- Root and security-sensitive services use absolute protected executable paths.
- No protected service resolves a binary beneath a writable checkout.
- Mutable service data is outside static `/opt` artifacts.
- User services are classified explicitly rather than inheriting PATH behavior.

### Boundary regression

- A repository test enumerates all configured executables and their trust
  domains.
- No component is simultaneously local and protected without an explicit
  dual-use declaration.
- No root target dispatches an ordinary writable-checkout component script.
- Local path aliases cannot resolve into `/opt` through symlinks.

## Risks During Migration

### Path coupling

Python environments and generated entrypoints contain absolute interpreter
paths. They must be recreated at the final new path rather than copied or
rewritten. The Python documentation explicitly treats virtual environments as
non-portable.

### Service drift

Existing units may continue running old executable paths after source changes.
Unit rendering and deployed unit verification must be part of migration
acceptance.

### Duplicate versions

A local and protected installation of the same tool may diverge. This is
acceptable when their trust purposes differ, but versions should be pinned and
reported clearly.

### Partial conversion

Changing only shell PATH or only component destinations will produce hard-to-
diagnose mixed execution. Each component should migrate with its installer,
detection, consumers, and tests as one logical change.

### Privileged cleanup

An existing foreign-owned checkout `.boot-linux` must stop installation with an
exact diagnostic. Migration must not silently apply broad ownership changes or
ad-hoc deletion. Any existing machine repair requires a reviewed operator
handoff after the path-qualified policy is deployed.

## Decision

Adopt the three-domain, path-qualified architecture:

1. User-owned checkout `.boot-*` for disposable and composable developer tools.
2. Root-owned immutable `/opt/workspace-ci` for CI enforcement.
3. OS packages or a separate root-deployed `/opt/workspace-runtime` for
   security-sensitive and system service executables.

Reject a root-only `make install`. Reject a user-writable `/opt/workspace-ci`.
Protected consumers must select their root-deployed boot by absolute path and
must not inherit checkout boot entries.

## Acceptance Criteria

The remediation is complete when:

1. `make install` and `make install-ci` succeed as an unprivileged user on a
   clean checkout.
2. They do not write any protected boot or `/opt` path.
3. Local tools reside in an explicitly user-owned disposable directory.
4. Protected hooks resolve only immutable `/opt/workspace-ci` dependencies.
5. Root and security-sensitive services execute only administrator-deployed
   binaries.
6. No privileged target executes general component scripts from writable
   checkout content.
7. Every component has a declared trust domain and tested consumer path.
8. The old checkout `.boot-linux` has no consumers before operator retirement.
9. WORKSPACE-CI retains verified candidate construction, atomic publication,
   final-path validation, and immutable sealing.
