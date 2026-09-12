# OPS: Fast storage provisioning and migration (nvme1n1)

Operator runbook for moving IO-heavy trees (podman store, llamafile
weights, QEMU overlays, cargo/uv caches, swap) off the dm-crypt root onto
the second NVMe. Motivation: the 2026-09-11/12 stalls showed all workloads
sharing one encrypted write queue (dm w_await 7.5s, IO PSI 94% full while
the raw NVMe sat at 32% util).

## Why two phases

The shell guard (REQ-SHG-300, `WORKSPACE-GUARD/config/shell_guard_policy.yaml`)
hard-blocks partition/format tools (`wipefs`, `parted`, `mkfs.*`, fdisk
family) inside ANY executed script body: root included, by design. The
sanctioned operator channel for them is typing interactively at a root
prompt (verified 2026-09-12: interactive `swapoff -a` executes; the same
token inside a script is blocked). Everything else is automatable and
lives in the repo scripts.

## Phase 1: one-time provision (type at a root prompt)

Destroys everything on `/dev/nvme1n1` (former OS install; wipe confirmed
by operator 2026-09-12). Override `FAST_DISK`/`FAST_LABEL` env vars in the
repo script if the defaults are wrong.

```
sudo wipefs -a /dev/nvme1n1
sudo parted -s /dev/nvme1n1 mklabel gpt
sudo parted -s /dev/nvme1n1 mkpart ws-fast ext4 1MiB 100%
sudo mkfs.ext4 -F -L ws-fast /dev/nvme1n1p1
```

## Phase 2: mount + persist + swap relocation (root, scripted)

```
sudo make configure-fast-storage FAST_STORAGE_ARGS='--dry-run'   # preview
sudo make configure-fast-storage                                 # apply
```

Mounts `/mnt/ws-fast` (fstab by UUID, `noatime`), creates
`containers/ models/ qemu/ caches/` owned by the agent, and relocates
swap: creates `/mnt/ws-fast/swap/swap0.img` (32G, unencrypted, `sw,nofail`),
drains and removes the encrypted `/swap.img` and `/swap2.img`.

## Phase 3: data migration (copy-only; originals kept)

**Rule: nothing is moved or deleted. Every original stays at its old
location; reclaiming space is manual cleanup once the fast copies are
trusted. (Swap files are the sole exception: phase 2 removes them.)**

The podman store copy must run as ROOT (the store contains subuid-owned
trees the agent uid cannot read); the relief operator script does this:

```
sudo bash /tmp/opencode/relieve-and-migrate.sh
```

Or piecemeal: root copies the store, agent flips the config:

```
sudo rsync -aHAX "$HOME/.local/share/containers/" /mnt/ws-fast/containers/   # as root, agent account
make migrate-fast-storage                                                          # as agent
```

The agent-side script verifies the store copy exists (bolt_state.db
check: it will refuse to point podman at a partial store), writes
`~/.config/containers/storage.conf` (graphroot on fast storage), copies
`models/`, `.vms/` (skipped while a guest runs), `~/.cargo`, and
`~/.cache/uv`, and appends env path configs (`WS_MODELS_DIR`,
`WS_VM_DIR`, `CARGO_HOME`, `UV_CACHE_DIR`) to `~/.bashrc`.

Then verify as the agent user against the deployed wrapper
(`/opt/workspace-ci/.boot-linux/bin/podman`; the wrapper BLOCKS
`podman system migrate` by design: do not run it). A graphroot move with
a copied store additionally needs a DBConfig path rewrite in the copied
db.sql (StaticDir/GraphRoot/VolumeDir), because the copied DB pins the
old absolute paths and even `system migrate` refuses to open it.

```
podman info | grep -i graphroot
podman images && podman volume ls
```

## Manual cleanup (after soak)

When the fast copies are trusted, originals can be deleted BY HAND:
`~/.local/share/containers` (110G), repo `models/*` content, `.vms/*`
content, `~/.cargo`, `~/.cache/uv`.

## Optional immediate relief

Drain stale swap into RAM (type at a root prompt):

```
sudo swapoff -a && sudo swapon -a
```

## Verification

```
findmnt /mnt/ws-fast
swapon --show
podman info | grep -i graphroot      # as agent
cat /proc/pressure/io                # full avg10 should stay near 0
```

## Rollback

Everything is copy-only, so rollback is config reversion, not data
restoration:
- Remove/comment `~/.config/containers/storage.conf` → podman reads the
  untouched original store again.
- Comment out the `workspace fast-storage paths` env block in `~/.bashrc`
  → `WS_*`/`CARGO_HOME`/`UV_CACHE_DIR` revert to defaults.
- fstab lines added by phase 2 are one-per-step; comment them out.

## User-manageable path configs (env)

| Var | Default | Consumer |
|-----|---------|----------|
| `WS_FAST_DIR` | `/mnt/ws-fast` | migrate script target root |
| `FAST_DISK` | `/dev/nvme1n1` | provisioning script |
| `FAST_MOUNT` | `/mnt/ws-fast` | provisioning script |
| `FAST_LABEL` | `ws-fast` | provisioning script |
| `SWAP_FAST_GB` | `32` | provisioning script swap file size |
| `WS_MODELS_DIR` | `$REPO/models` (set by migrate to fast path) | llamafile bundle/test scripts, `vm` |
| `WS_VM_DIR` | `.vms` (set by migrate to fast path) | `workspace/scripts/bin/vm` |
