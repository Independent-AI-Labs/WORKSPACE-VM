"""Regression tests: fast-storage provisioning and migration invariants.

The 2026-09-11/12 stalls (dm-crypt write queue at 7.5s w_await, IO PSI 94%)
come from every IO-heavy tree sharing the encrypted root. These tests pin
the two scripts that move podman store / models / QEMU / caches / swap onto
unencrypted nvme1 storage, the env path configs consumers honor, and the
Makefile wiring.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
CONFIGURE = ROOT / "scripts" / "setup" / "configure-fast-storage.sh"
MIGRATE = ROOT / "scripts" / "setup" / "migrate-fast-storage.sh"
RUNBOOK = ROOT / "docs" / "OPS-FAST-STORAGE.md"
VM_BIN = ROOT / "workspace" / "scripts" / "bin" / "vm"
BUNDLE = ROOT / "scripts" / "setup" / "build-llamafile-bundle.sh"
VULKAN_TEST = ROOT / "scripts" / "setup" / "test-llamafile-vulkan.sh"


def _recipe(target: str, text: str) -> str:
    match = re.search(
        rf"^{re.escape(target)}:.*?\n((?:\t.*\n|[^\S\n]*\n)+)",
        text,
        re.MULTILINE,
    )
    assert match is not None, f"target not found: {target}"
    return match.group(0)


def _assert_guard_clean(text: str) -> None:
    for line in text.splitlines():
        assert "| head" not in line, f"suppress-pipe: {line}"
        assert "| tail" not in line, f"suppress-pipe: {line}"
        assert "2>/dev/null" not in line, f"suppress-null: {line}"
        assert "|| true" not in line, f"suppress-swallow: {line}"
        assert not re.search(r"\brc=", line), f"alt-shell rc var: {line}"


class TestConfigureFastStorage:
    def test_script_bash_strict_and_root_gated(self) -> None:
        text = CONFIGURE.read_text(encoding="utf-8")
        assert text.startswith("#!/bin/bash\n")
        assert "set -euo pipefail" in text
        assert 'id -u)" -ne 0' in text
        assert "sudo" in text

    def test_dry_run_and_runbook_delegation(self) -> None:
        """Dry-run supported; destructive tools delegate to the operator
        runbook (shell guard REQ-SHG-300 blocks them in script bodies)."""
        text = CONFIGURE.read_text(encoding="utf-8")
        assert "--dry-run)" in text
        assert "OPS-FAST-STORAGE.md" in text
        # the destructive tokens must stay OUT of the executable body
        for token in ("parted", "mkfs", "wipefs", "fdisk"):
            assert token not in text, f"banned-in-body token {token} present"

    def test_refuses_root_disk_and_foreign_mounts(self) -> None:
        text = CONFIGURE.read_text(encoding="utf-8")
        assert "carries the root filesystem" in text
        assert "Refusing to wipe a disk with foreign mounts" in text

    def test_persistence_and_layout(self) -> None:
        text = CONFIGURE.read_text(encoding="utf-8")
        assert "/etc/fstab" in text
        assert "noatime" in text
        for d in ("containers", "models", "qemu", "caches"):
            assert d in text

    def test_swap_moves_off_luks(self) -> None:
        text = CONFIGURE.read_text(encoding="utf-8")
        assert "SWAP_FAST_GB" in text
        assert "swap0.img" in text
        assert "sw,nofail" in text
        assert "/swap.img" in text
        assert "/swap2.img" in text
        assert "moved-to-fast-storage" in text

    def test_guard_clean(self) -> None:
        _assert_guard_clean(CONFIGURE.read_text(encoding="utf-8"))


class TestMigrateFastStorage:
    def test_script_bash_strict_and_agent_gated(self) -> None:
        text = MIGRATE.read_text(encoding="utf-8")
        assert text.startswith("#!/bin/bash\n")
        assert "set -euo pipefail" in text
        assert 'id -u)" -eq 0' in text

    def test_dry_run_and_env_override(self) -> None:
        text = MIGRATE.read_text(encoding="utf-8")
        assert "--dry-run)" in text
        assert "WS_FAST_DIR:-/mnt/ws-fast" in text

    def test_podman_migration_mechanism(self) -> None:
        text = MIGRATE.read_text(encoding="utf-8")
        # hardlinks must survive or overlay dedup explodes
        assert "rsync -aHAX" in text
        assert "storage.conf" in text
        assert "graphroot = " in text
        assert "runroot" in text
        # the .boot-linux podman wrapper blocks system migrate by design
        assert "blocks system migrate" in text or "BLOCKS" in text

    def test_target_user_is_checkout_owner_not_sudo_user(self) -> None:
        """2026-09-12 runs chowned dirs to `admin`/root via SUDO_USER and a
        fragile BASH_SOURCE derivation. Pin: explicit WS_ROOT + marker
        verification + blank/root refusal."""
        text = CONFIGURE.read_text(encoding="utf-8")
        assert 'TARGET_USER="${SUDO_USER' not in text
        assert "${BASH_SOURCE" not in text
        assert "getent passwd agent" in text
        assert "pyproject.toml" in text
        assert "refusing" in text

    def test_refuses_running_containers(self) -> None:
        text = MIGRATE.read_text(encoding="utf-8")
        assert "conmon" in text
        assert "stop all containers first" in text

    def test_refuses_live_qemu_guest(self) -> None:
        """Copying .vms under a running guest would create a stale copy
        that WS_VM_DIR later points at (split-brain). Must skip + say so."""
        text = MIGRATE.read_text(encoding="utf-8")
        assert "qemu-system" in text
        assert "live QEMU guest" in text
        assert "VMS_MIGRATED" in text

    def test_env_path_configs_persisted(self) -> None:
        text = MIGRATE.read_text(encoding="utf-8")
        assert "WS_MODELS_DIR" in text
        assert "WS_VM_DIR" in text
        assert "workspace fast-storage paths" in text

    def test_caches_env_configs_copy_only(self) -> None:
        text = MIGRATE.read_text(encoding="utf-8")
        assert "caches/cargo" in text
        assert "caches/uv" in text
        assert "CARGO_HOME" in text
        assert "UV_CACHE_DIR" in text

    def test_copy_only_no_moves_or_deletions(self) -> None:
        """Operator rule 2026-09-12: every migrated original stays at its
        old location; cleanup is ALWAYS manual (swap exempt, handled by
        configure-fast-storage.sh)."""
        text = MIGRATE.read_text(encoding="utf-8")
        assert "ln -s" not in text
        assert ".pre-fast" not in text
        assert not re.search(r"^\s*mv\s", text, re.MULTILINE)
        for line in text.splitlines():
            if re.search(r"\brm\s", line):
                assert "_probe" in line, f"non-probe rm: {line}"

    def test_store_copy_guards(self) -> None:
        """Subuid store copy needs root; the agent script must refuse to
        point podman at a missing/partial store. podman 5.x uses db.sql;
        older releases used libpod/bolt_state.db."""
        text = MIGRATE.read_text(encoding="utf-8")
        assert "db.sql" in text
        assert "bolt_state.db" in text
        assert "cannot run as agent" in text or "cannot run here" in text

    def test_guard_clean(self) -> None:
        _assert_guard_clean(MIGRATE.read_text(encoding="utf-8"))


class TestConsumersHonorEnvPaths:
    def test_vm_script_ws_vm_dir(self) -> None:
        text = VM_BIN.read_text(encoding="utf-8")
        assert "WS_VM_DIR:-.vms" in text

    def test_llamafile_bundle_ws_models_dir(self) -> None:
        text = BUNDLE.read_text(encoding="utf-8")
        assert "WS_MODELS_DIR:-$PROJECT_ROOT/models" in text

    def test_vulkan_test_ws_models_dir(self) -> None:
        text = VULKAN_TEST.read_text(encoding="utf-8")
        assert "WS_MODELS_DIR:-$PROJECT_ROOT/models" in text


class TestOperatorRunbook:
    def test_runbook_exists_with_provision_commands(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        assert "mklabel gpt" in text
        assert "ws-fast" in text
        assert "interactively" in text

    def test_runbook_documents_all_phases(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        assert "configure-fast-storage" in text
        assert "migrate-fast-storage" in text
        assert "graphroot" in text
        assert "WS_MODELS_DIR" in text
        assert "WS_VM_DIR" in text


class TestMakefileWiring:
    def test_configure_target_root_gated(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        recipe = _recipe("configure-fast-storage", text)
        assert 'id -u)" != "0"' in recipe
        assert "configure-fast-storage.sh" in recipe
        assert "FAST_STORAGE_ARGS" in recipe

    def test_migrate_target_runs_as_agent(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        recipe = _recipe("migrate-fast-storage", text)
        assert "migrate-fast-storage.sh" in recipe
        assert "MIGRATE_ARGS" in recipe
        assert "id -u" not in recipe
