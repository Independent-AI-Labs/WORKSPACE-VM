# Persistent QEMU VM Guide

**Status:** Current capabilities plus delivery roadmap
**Date:** 2026-10-23
**Requirements:** [REQ-VM-HYPERVISOR](../requirements/REQ-VM-HYPERVISOR.md)
**Specification:** [SPEC-VM-HYPERVISOR](../specifications/SPEC-VM-HYPERVISOR.md)

---

## 1. What Exists Today

QEMU VMs use a per-VM QCOW2 overlay. The overlay is retained across `vm stop`
and `vm start`. The shared Ubuntu base image stays under `_base/`.

The host has been validated on Linux KVM for:

- QEMU boot and SSH
- full-ci provisioning
- WORKSPACE-GUARD E2E
- shell-guard E2E
- boot-posture E2E

Current day-2 commands:

```bash
make vm workspace/config/vm-full-ci-qemu.yaml
make vm-list
make vm-status <uuid>
make vm-stop <uuid>
make vm-start <uuid>
make vm-shell <uuid>
make vm-exec <uuid> <command>
make vm-logs <uuid>
make vm-delete <uuid>
```

## 2. Implemented and Remaining

Implemented:

- Persistent `state.yaml` with PID identity and stale-process recovery.
- Data-preserving `vm delete` by default; `--purge` removes artifacts.
- ACPI shutdown through QMP, then SIGTERM, then SIGKILL.
- QEMU `rebuild`, including `--fresh`.
- QEMU `sync` over SSH with merge, overwrite, skip, and excludes.
- Snapshot, export, and import.
- Systemd user autostart.
- `files`, read-only `mounts` (virtio-9p), `env`, `provider`,
  `credentials: clone`, and `ssh` parity.
- E2E cleanup protection for persistent VMs.
- `network.mode: none` enforced with QEMU `restrict=on`.
- Provisioned VMs boot once with host networking for cloud-init, package
  install, and guard prebuild, then restart with restricted networking.
- The guard profile prebuilds shell, git, and debug binaries and stores the
  cargo cache in `/var/tmp`, so the air-gapped guest can rebuild offline.
- `network.mode: bridge` adds a second virtio NIC on the configured host bridge.
  The bridge must already exist on the host.
- Bridge `policy: internet` blocks private-range egress on the bridge NIC.
- Bridge `policy: proxy` allows only the proxy host and exports proxy env vars.
- `network.whitelist` is rejected for QEMU.
- `network.mode: openvpn` uses user networking and runs the OpenVPN client in
  the guest with a systemd unit.
- `web_ui: true` runs `opencode web` on guest `127.0.0.1:4096`.
- `resources.pids_limit` maps to systemd `DefaultTasksMax`.
- Explicit rejection of `credentials.mode: api`, `network.mode: host`,
  OpenVPN `vpn_type: netns`, non-unrestricted bridge policy, and
  `security.cap_add`.

Remaining:

- Bridge and OpenVPN live runtime E2E.
- QEMU Traefik and mTLS web proxy.
- Guest mapping for `security.*` beyond `cap_add`.
- macOS, WSL, and chroot validation for the persistent suite.

Access the web UI through the VM SSH forward:

```bash
ssh -i <vm_dir>/qemu_ssh_ed25519 -p <ssh_port> \
  -L 4096:127.0.0.1:4096 workspace@127.0.0.1
```

Then open `http://127.0.0.1:4096`.

The export bundle contains the per-VM SSH private key and VM password. Treat
exported bundles as secrets.

## 3. Storage Layout

```text
.vms/
  _base/
    workspace-vm-base-ubuntu-24.04-x86_64.qcow2
    workspace-vm-base-ubuntu-24.04-aarch64.qcow2
  <uuid>/
    vm.yaml
    vm-install-defaults.yaml
    disk.qcow2
    ssh_port
    qemu.pid
    qemu.log
    provision.log
    state.yaml
    password
    qemu_ssh_ed25519
    cloud-init/
  _archive/
    <uuid>/
```

Set `WS_VM_DIR` to keep large disks on fast local storage:

```bash
WS_VM_DIR=/mnt/ws-fast/qemu make vm workspace/config/vm-full-ci-qemu.yaml
```

## 4. Recommended Current Workflow

1. Run `make install-qemu`.
2. Choose a permanent storage path with `WS_VM_DIR`.
3. Create the VM with `vm-full-ci-qemu.yaml`.
4. Wait for `provision.log` to report completion.
5. Verify tools with `vm exec`.
6. Stop from inside the guest for a clean filesystem:

```bash
make vm-exec <uuid> sudo systemctl poweroff
```

7. Start again with `make vm-start <uuid>`.
8. Delete with `make vm-delete <uuid>` to archive, or add `--purge` to remove.

Keep the QCOW2 backing image because the overlay depends on it. Do not delete
`.vms/_base/`.

## 5. Day-2 Operations

```bash
make test-vm-persistent
make vm-rebuild <uuid>
make vm-rebuild <uuid> --fresh
make vm-sync <uuid>
make vm-snapshot <uuid> create <name>
make vm-snapshot <uuid> list
make vm-snapshot <uuid> delete <name>
make vm-export <uuid> <path>
make vm-import <path>
make vm-autostart enable <uuid>
make vm-autostart disable <uuid>
```

Semantics:

- `rebuild` preserves the overlay by default.
- `rebuild --fresh` creates a new overlay and keeps the old disk.
- `sync` applies `config.sync` rules over SSH.
- `snapshot` requires a stopped or quiesced VM.
- `export` includes disk, config, state, password, SSH key, cloud-init seed,
  and manifest.
- `import` creates a new UUID, allocates a new SSH port, and preserves the
  bundled key and password.
- `autostart` uses a systemd user unit.
- `delete` archives the VM under `_archive/` unless `--purge` is given.

## 7. Platform Support

Native Linux and macOS are the QEMU product targets.

Windows and Android developer support uses the rootless bootstrap path on local
Debian or Ubuntu under WSL or chroot. That path runs the same bootstrap, QEMU
backend, CLI, and E2E gates.

Native Windows, Android, and macOS end-user packages are separate workstreams.
They are not part of current QEMU validation.

## 8. E2E Coverage

`test_vm_qemu_persistent.py` currently covers:

- data persistence across stop and start
- delete purge and cleanup
- rebuild preserve
- snapshot create, list, and delete
- export and import roundtrip
- host data survival after import

The remaining QEMU suites cover POC boot, full-ci, guard, shell guard, and boot
posture. Target additions:

- delete archive and restore
- sync merge, overwrite, skip, and exclude
- files, mounts, env, provider, credentials, ssh, and web UI assertions
- network bridge and OpenVPN runtime
- systemd autostart
- WSL and chroot bootstrap

## 9. Related Documents

- [REQ-VM-HYPERVISOR](../requirements/REQ-VM-HYPERVISOR.md)
- [SPEC-VM-HYPERVISOR](../specifications/SPEC-VM-HYPERVISOR.md)
- [REQ-ANDROID-WORKSPACE](../requirements/REQ-ANDROID-WORKSPACE.md)
- [REQ-OPENVPN](../requirements/REQ-OPENVPN.md)
