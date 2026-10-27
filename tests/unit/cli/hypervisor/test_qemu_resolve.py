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

    def _fake_run(*_args: object, **_kwargs: object) -> None:
        calls.append(True)

    monkeypatch.setattr(qr.subprocess, "run", _fake_run)
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


def test_resolve_qemu_img_path_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    monkeypatch.setattr(qr.shutil, "which", lambda _name: "/usr/bin/qemu-img")
    assert qr.resolve_qemu_img() == Path("/usr/bin/qemu-img")
    assert "using PATH qemu-img" in capsys.readouterr().err


def test_resolve_qemu_img_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    monkeypatch.setattr(qr.shutil, "which", lambda _name: None)
    with pytest.raises(FileNotFoundError, match="qemu-img"):
        qr.resolve_qemu_img()


def test_resolve_cloud_localds_path_and_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    monkeypatch.setattr(qr.shutil, "which", lambda _name: "/usr/bin/cloud-localds")
    assert qr.resolve_cloud_localds() == Path("/usr/bin/cloud-localds")
    monkeypatch.setattr(qr.shutil, "which", lambda _name: None)
    with pytest.raises(FileNotFoundError, match="cloud-localds"):
        qr.resolve_cloud_localds()


def test_resolve_aarch64_firmware_linux_distro(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        qr, "workspace_boot_dir", lambda root=None: tmp_path / ".boot-macos"
    )
    monkeypatch.setattr(qr.platform, "system", lambda: "Linux")
    distro = tmp_path / "distro.fd"
    distro.write_bytes(b"efi")
    monkeypatch.setattr(qr, "Path", lambda _value: distro)
    assert qr.resolve_aarch64_firmware() == distro


def test_probe_accel_timeout_is_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def _timeout(*_a: object, **_k: object) -> None:
        raise qr.subprocess.TimeoutExpired("qemu", 5)

    monkeypatch.setattr(qr.subprocess, "run", _timeout)
    assert qr.probe_accel(Path("/opt/qemu"), "kvm") is True


def test_probe_accel_failures_surface(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    def _failed(*_a: object, **_k: object) -> None:
        raise qr.subprocess.CalledProcessError(1, "qemu", stderr="no kvm")

    monkeypatch.setattr(qr.subprocess, "run", _failed)
    assert qr.probe_accel(Path("/opt/qemu"), "kvm") is False
    assert "no kvm" in capsys.readouterr().err

    def _oserror(*_a: object, **_k: object) -> None:
        raise OSError("missing")

    monkeypatch.setattr(qr.subprocess, "run", _oserror)
    assert qr.probe_accel(Path("/opt/qemu"), "kvm") is False
    assert "missing" in capsys.readouterr().err
