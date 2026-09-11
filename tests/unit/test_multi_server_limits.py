"""Regression tests: multi-server capacity limits are repo-owned and root-only.

The 2026-09-11 incident (conmon "Failed to create inotify fd", Turbopack
"Too many open files" crash loop) came from stock kernel/systemd limits.
These tests pin the provisioning script invariants: the capacity-critical
keys must stay, the script must refuse non-root, the shell guard rules
must hold, and the Makefile must wire it into the privileged bootstrap.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = ROOT / "Makefile"
SCRIPT = ROOT / "scripts" / "setup" / "configure-multi-server-limits.sh"


def _recipe(target: str, text: str) -> str:
    match = re.search(
        rf"^{re.escape(target)}:.*?\n((?:\t.*\n|[^\S\n]*\n)+)",
        text,
        re.MULTILINE,
    )
    assert match is not None, f"target not found: {target}"
    return match.group(0)


class TestCapacityScript:
    def test_script_exists_and_is_bash_strict(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        assert text.startswith("#!/bin/bash\n")
        assert "set -euo pipefail" in text

    def test_script_refuses_non_root(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        assert 'id -u)" -ne 0' in text
        assert "sudo" in text
        assert "exit 1" in text

    def test_incident_keys_present(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        for key in (
            "fs.inotify.max_user_instances",
            "fs.inotify.max_user_watches",
            "fs.nr_open",
            "net.core.somaxconn",
            "net.ipv4.tcp_max_syn_backlog",
            "net.ipv4.ip_local_port_range",
            "net.ipv4.tcp_max_tw_buckets",
            "net.ipv4.tcp_fin_timeout",
            "net.netfilter.nf_conntrack_max",
        ):
            assert key in text, f"missing capacity key: {key}"

    def test_transient_conntrack_capacity(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        assert "nf_conntrack_max = 1048576" in text
        assert "tcp_max_tw_buckets = 1048576" in text

    def test_systemd_nofile_defaults(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        assert "DefaultLimitNOFILE" in text
        assert "system.conf.d" in text
        assert "user.conf.d" in text
        assert "daemon-reexec" in text

    def test_persistence_not_runtime_only(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        assert "/etc/sysctl.d/70-workspace-multi-server.conf" in text
        assert "/etc/modprobe.d/nf_conntrack-workspace.conf" in text

    def test_guard_compliance(self) -> None:
        """No shell-guard banned patterns in the script."""
        text = SCRIPT.read_text(encoding="utf-8")
        for line in text.splitlines():
            assert "| head" not in line, f"suppress-pipe: {line}"
            assert "| tail" not in line, f"suppress-pipe: {line}"
            assert "2>/dev/null" not in line, f"suppress-null: {line}"
            assert "|| true" not in line, f"suppress-swallow: {line}"
            assert not re.search(r"\brc=", line), f"alt-shell rc var: {line}"

    def test_idempotent_generator_fix(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        assert "chmod 0755" in text
        assert "user-generators/podman-user-generator" in text

    def test_swap_extension_to_32g(self) -> None:
        """Total swap must be raised to 32G via an added swapfile + fstab."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert "SWAP_TARGET_GB=32" in text
        assert "/swap2.img" in text
        assert "fallocate" in text
        assert "mkswap" in text
        assert "swapon" in text
        assert "/etc/fstab" in text
        # Never disables the existing in-use swap device (no swapoff command;
        # prose comments mentioning it are fine)
        assert not re.search(r"^\s*swapoff\b", text, re.MULTILINE)

    def test_operator_run_regressions_fixed(self) -> None:
        """Pin the three failures from the 2026-09-11 operator run:
        tab/space read-back mismatch, unsupported swapon --output=NAME,
        and the mkswap metadata-page shortfall vs an exact 32G check."""
        text = SCRIPT.read_text(encoding="utf-8")
        # sysctl read-back whitespace normalization, including edge trim
        # (tr turns the trailing newline into a trailing space)
        assert "tr -s '[:space:]' ' '" in text
        assert 'actual="${actual% }"' in text
        assert 'expected="${expected% }"' in text
        # active-swap detection must not use `swapon --output=`
        assert "swapon --show" not in text
        assert "--output=NAME" not in text
        assert "/proc/swaps" in text
        # tolerance for mkswap-reserved pages instead of exact compare
        assert "SWAP_SLACK_KB=" in text
        assert 'lt "$SWAP_FLOOR_KB"' in text


class TestMakefileWiring:
    def test_target_root_gated(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        recipe = _recipe("enforce-multi-server-limits", text)
        assert 'id -u)" != "0"' in recipe
        assert "exit 1" in recipe
        assert "configure-multi-server-limits.sh" in recipe

    def test_init_root_applies_capacity_limits(self) -> None:
        text = MAKEFILE.read_text(encoding="utf-8")
        recipe = _recipe("init-root", text)
        assert "enforce-multi-server-limits" in recipe
