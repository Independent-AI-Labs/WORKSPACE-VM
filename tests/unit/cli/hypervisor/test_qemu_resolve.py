"""Unit tests for qemu_resolve."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from workspace.cli.hypervisor import qemu_resolve as qr


def test_resolve_qemu_system_unsupported_arch() -> None:
    with pytest.raises(ValueError, match="unsupported guest_arch"):
        qr.resolve_qemu_system("mips", allow_path=False)


def test_resolve_qemu_system_boot_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    boot = tmp_path / ".boot-macos" / "bin"
    boot.mkdir(parents=True)
    binary = boot / "qemu-system-aarch64"
    binary.write_text("")
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    result = qr.resolve_qemu_system("aarch64", allow_path=False)
    assert result == binary


def test_resolve_qemu_system_path_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    with patch.object(
        qr.shutil, "which", return_value="/usr/local/bin/qemu-system-aarch64"
    ):
        result = qr.resolve_qemu_system("aarch64")
    assert result == Path("/usr/local/bin/qemu-system-aarch64")


def test_resolve_qemu_system_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    with (
        patch.object(qr.shutil, "which", return_value=None),
        pytest.raises(FileNotFoundError, match="qemu-system-aarch64"),
    ):
        qr.resolve_qemu_system("aarch64", allow_path=False)


def test_probe_accel_delegates_to_process(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def _fake_run_ok(*_args: object, **_kwargs: object) -> bool:
        calls.append(True)
        return True

    monkeypatch.setattr(qr.proc, "run_ok", _fake_run_ok)
    assert qr.probe_accel(Path("/opt/qemu"), "hvf") is True
    assert calls


@pytest.mark.parametrize(
    ("system", "accel", "probe_result", "expected"),
    [
        ("Linux", "kvm", True, "kvm"),
        ("Linux", "kvm", False, "tcg"),
        ("Darwin", "hvf", True, "hvf"),
        ("Darwin", "hvf", False, "tcg"),
        ("Windows", "whpx", True, "whpx"),
        ("FreeBSD", "hvf", False, "tcg"),
    ],
)
def test_resolve_accel_auto(
    monkeypatch: pytest.MonkeyPatch,
    system: str,
    accel: str,
    probe_result: bool,
    expected: str,
) -> None:
    monkeypatch.setattr(qr.platform, "system", lambda: system)
    monkeypatch.setattr(
        qr, "probe_accel", lambda _bin, name: probe_result and name == accel
    )
    assert qr.resolve_accel("auto", Path("/opt/qemu")) == expected


def test_resolve_accel_explicit() -> None:
    assert qr.resolve_accel("tcg", Path("/opt/qemu")) == "tcg"


def test_resolve_aarch64_firmware_bundled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fw = tmp_path / ".boot-macos" / "share" / "qemu" / "firmware" / "QEMU_EFI.fd"
    fw.parent.mkdir(parents=True)
    fw.write_bytes(b"efi")
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    assert qr.resolve_aarch64_firmware() == fw


def test_resolve_qemu_img_boot_bin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    boot_bin = tmp_path / ".boot-macos" / "bin" / "qemu-img"
    boot_bin.parent.mkdir(parents=True)
    boot_bin.write_text("")
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    assert qr.resolve_qemu_img(allow_path=False) == boot_bin


def test_resolve_aarch64_firmware_darwin(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    monkeypatch.setattr(qr.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        qr.shutil,
        "which",
        lambda name: "/opt/homebrew/bin/brew" if name == "brew" else None,
    )
    candidate = tmp_path / "prefix" / "share" / "qemu" / "edk2-aarch64-code.fd"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"efi")
    monkeypatch.setattr(
        qr.subprocess,
        "check_output",
        lambda *_a, **_k: str(tmp_path / "prefix"),
    )
    assert qr.resolve_aarch64_firmware() == candidate


def test_resolve_cloud_localds_boot_bin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    boot_bin = tmp_path / ".boot-macos" / "bin" / "cloud-localds"
    boot_bin.parent.mkdir(parents=True)
    boot_bin.write_text("")
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    assert qr.resolve_cloud_localds(allow_path=False) == boot_bin
