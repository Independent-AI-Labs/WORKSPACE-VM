"""Integration tests for vm_main dispatch, vm_sync, and status display.

These exercise the CLI dispatch layer, file-sync pipeline, and status
rendering against real filesystem state with subprocess calls mocked.
They close the integration coverage gap for modules that were previously
only exercised by unit tests (which run in a separate --cov session).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

import workspace.cli.status as status_mod
from workspace.cli import vm_lifecycle, vm_main, vm_sync
from workspace.types.common import ContainerSizeData, ContainerStatsData
from workspace.types.status import ServiceDisplayInfo, SystemdService

# ── vm_main dispatch ─────────────────────────────────────────────────────────


class TestVMMainDispatch:
    """In-process dispatch exercising main() / _dispatch / _require_arg."""

    def test_no_args_prints_usage(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert vm_main.main([]) == 1
        assert "usage:" in capsys.readouterr().err

    def test_unknown_subcommand(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert vm_main.main(["bogus-cmd"]) == 1
        assert "unknown subcommand" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "sub",
        [
            "create",
            "rebuild",
            "sync",
            "start",
            "stop",
            "delete",
            "shell",
            "kill",
            "status",
            "logs",
        ],
    )
    def test_missing_uuid_returns_1(
        self, sub: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert vm_main.main([sub]) == 1
        assert "missing argument" in capsys.readouterr().err

    def test_exec_missing_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        result = vm_main.main(["exec", "some-uuid"])
        assert result == 1
        assert "missing command" in capsys.readouterr().err

    def test_exec_with_dashdash_no_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        result = vm_main.main(["exec", "some-uuid", "--"])
        assert result == 1

    def test_list_dispatches_to_list_vms(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        vms = tmp_path / ".vms"
        vms.mkdir()
        monkeypatch.setattr(vm_lifecycle, "_VMS_DIR", vms)
        rc = vm_main.main(["list"])
        assert rc == 0
        assert "No VMs found" in capsys.readouterr().out

    def test_create_dispatches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        cfg = tmp_path / "vm.yaml"
        cfg.write_text(yaml.dump({"components": ["uv"]}))
        called: dict[str, object] = {}

        def fake_create(path: str) -> None:
            called["path"] = path

        monkeypatch.setattr(vm_main, "create", fake_create)
        rc = vm_main.main(["create", str(cfg)])
        assert rc == 0
        assert called["path"] == str(cfg)

    def test_rebuild_dispatches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called: dict[str, str] = {}

        def fake_rebuild(uuid: str) -> None:
            called["uuid"] = uuid

        monkeypatch.setattr(vm_main, "rebuild", fake_rebuild)
        rc = vm_main.main(["rebuild", "my-uuid"])
        assert rc == 0
        assert called["uuid"] == "my-uuid"

    def test_sync_dispatches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called: dict[str, str] = {}

        def fake_sync(uuid: str) -> None:
            called["uuid"] = uuid

        monkeypatch.setattr(vm_main, "sync", fake_sync)
        rc = vm_main.main(["sync", "sync-uuid"])
        assert rc == 0
        assert called["uuid"] == "sync-uuid"

    @pytest.mark.parametrize("sub", ["start", "stop", "shell", "kill", "status"])
    def test_single_uuid_dispatch(
        self, sub: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called: dict[str, str] = {}
        fn_name = {"status": "show_status"}.get(sub, sub)

        def fake_fn(uuid: str) -> None:
            called["uuid"] = uuid

        monkeypatch.setattr(vm_main, fn_name, fake_fn)
        rc = vm_main.main([sub, f"{sub}-uuid"])
        assert rc == 0
        assert called["uuid"] == f"{sub}-uuid"

    def test_delete_without_purge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called: dict[str, object] = {}

        def fake_delete(uuid: str, *, purge: bool = False) -> None:
            called["uuid"] = uuid
            called["purge"] = purge

        monkeypatch.setattr(vm_main, "delete", fake_delete)
        rc = vm_main.main(["delete", "del-uuid"])
        assert rc == 0
        assert called["uuid"] == "del-uuid"
        assert called["purge"] is False

    def test_delete_with_purge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called: dict[str, object] = {}

        def fake_delete(uuid: str, *, purge: bool = False) -> None:
            called["purge"] = purge

        monkeypatch.setattr(vm_main, "delete", fake_delete)
        rc = vm_main.main(["delete", "del-uuid", "--purge"])
        assert rc == 0
        assert called["purge"] is True

    def test_logs_dispatches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        called: dict[str, object] = {}

        def fake_show_logs(uuid: str, extra: list[str]) -> None:
            called["uuid"] = uuid
            called["extra"] = extra

        monkeypatch.setattr(vm_main, "show_logs", fake_show_logs)
        rc = vm_main.main(["logs", "log-uuid", "-f", "--tail", "10"])
        assert rc == 0
        assert called["uuid"] == "log-uuid"
        assert called["extra"] == ["-f", "--tail", "10"]

    def test_exec_dispatches_with_command(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called: dict[str, object] = {}

        def fake_exec_cmd(uuid: str, cmd: list[str]) -> None:
            called["uuid"] = uuid
            called["cmd"] = cmd

        monkeypatch.setattr(vm_main, "exec_cmd", fake_exec_cmd)
        rc = vm_main.main(["exec", "ex-uuid", "ls", "-la"])
        assert rc == 0
        assert called["uuid"] == "ex-uuid"
        assert called["cmd"] == ["ls", "-la"]

    def test_exec_dispatches_strips_dashdash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called: dict[str, object] = {}

        def fake_exec_cmd(uuid: str, cmd: list[str]) -> None:
            called["cmd"] = cmd

        monkeypatch.setattr(vm_main, "exec_cmd", fake_exec_cmd)
        rc = vm_main.main(["exec", "ex-uuid", "--", "echo", "hi"])
        assert rc == 0
        assert called["cmd"] == ["echo", "hi"]

    def test_main_with_cli_args_none_uses_argv(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.argv", ["vm_main", "list"])
        vms = tmp_path / ".vms"
        vms.mkdir()
        monkeypatch.setattr(vm_lifecycle, "_VMS_DIR", vms)
        rc = vm_main.main()
        assert rc == 0


# ── vm_sync ──────────────────────────────────────────────────────────────────


class TestVMSyncIntegration:
    """Exercise sync() and _remove_hosts_entry with real files."""

    def test_sync_no_vm_yaml_exits(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(vm_sync, "_VMS_DIR", tmp_path)
        with pytest.raises(SystemExit) as exc_info:
            vm_sync.sync("no-such-uuid")
        assert exc_info.value.code == 1

    def test_sync_no_sync_rules_prints_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        vms = tmp_path / ".vms"
        vm_dir = vms / "sync-uuid"
        vm_dir.mkdir(parents=True)
        (vm_dir / "vm.yaml").write_text(yaml.dump({"components": ["uv"]}))
        monkeypatch.setattr(vm_sync, "_VMS_DIR", vms)
        vm_sync.sync("sync-uuid")
        assert "no sync rules" in capsys.readouterr().out

    def test_sync_volume_not_found_exits(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        vms = tmp_path / ".vms"
        vm_dir = vms / "vol-uuid"
        vm_dir.mkdir(parents=True)
        (vm_dir / "vm.yaml").write_text(
            yaml.dump({"components": ["uv"], "sync": [{"dir": str(tmp_path)}]})
        )
        monkeypatch.setattr(vm_sync, "_VMS_DIR", vms)

        def fail_podman(*_args: str) -> None:
            raise subprocess.CalledProcessError(1, ["podman"])

        monkeypatch.setattr(vm_sync, "_podman", fail_podman)
        with pytest.raises(SystemExit) as exc_info:
            vm_sync.sync("vol-uuid")
        assert exc_info.value.code == 1

    def test_sync_source_not_found_skips(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        vms = tmp_path / ".vms"
        vm_dir = vms / "skip-uuid"
        vm_dir.mkdir(parents=True)
        (vm_dir / "vm.yaml").write_text(
            yaml.dump(
                {
                    "components": ["uv"],
                    "sync": [{"dir": "/nonexistent/path/xyz"}],
                }
            )
        )
        monkeypatch.setattr(vm_sync, "_VMS_DIR", vms)

        def fake_podman(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                ["podman"], 0, stdout=str(tmp_path / "mnt"), stderr=""
            )

        monkeypatch.setattr(vm_sync, "_podman", fake_podman)
        vm_sync.sync("skip-uuid")
        out = capsys.readouterr().out
        assert "source directory" in out
        assert "not found, skipping" in out

    def test_sync_overwrite_strategy(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        src = tmp_path / "src"
        src.mkdir()
        (src / "file.txt").write_text("hello")
        vms = tmp_path / ".vms"
        vm_dir = vms / "ow-uuid"
        vm_dir.mkdir(parents=True)
        mnt = tmp_path / "mnt"
        mnt.mkdir()
        (vm_dir / "vm.yaml").write_text(
            yaml.dump(
                {
                    "components": ["uv"],
                    "sync": [{"dir": str(src), "strategy": "overwrite"}],
                }
            )
        )
        monkeypatch.setattr(vm_sync, "_VMS_DIR", vms)

        def fake_podman(*args: str) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                ["podman"], 0, stdout=str(mnt), stderr=""
            )

        recorded: list[list[str]] = []

        def fake_run(
            cmd: list[str], **_kwargs: object
        ) -> subprocess.CompletedProcess[str]:
            recorded.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, "", "")

        monkeypatch.setattr(vm_sync, "_podman", fake_podman)
        monkeypatch.setattr(subprocess, "run", fake_run)
        vm_sync.sync("ow-uuid")
        assert recorded
        assert "--delete" in recorded[0]
        out = capsys.readouterr().out
        assert "synced 1 directory" in out

    def test_remove_hosts_entry_no_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(vm_sync, "Path", lambda p: tmp_path / "noexist")
        vm_sync._remove_hosts_entry("test-uuid")

    def test_remove_hosts_entry_no_match(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hosts = tmp_path / "hosts"
        hosts.write_text("127.0.0.1 localhost\n")
        monkeypatch.setattr(vm_sync, "Path", lambda p: hosts)
        vm_sync._remove_hosts_entry("absent-uuid")

    def test_remove_hosts_entry_removes_match(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hosts = tmp_path / "hosts"
        hosts.write_text(
            "127.0.0.1 localhost\n"
            "192.168.1.1 vm-uuid.vm.local\n"
            "10.0.0.1 other.vm.local\n"
        )
        monkeypatch.setattr(vm_sync, "Path", lambda p: hosts)
        vm_sync._remove_hosts_entry("vm-uuid")
        content = hosts.read_text()
        assert "vm-uuid.vm.local" not in content
        assert "other.vm.local" in content


# ── status display ─────────────────────────────────────────────────────────


class TestStatusDisplayIntegration:
    """Exercise _print_header, _print_footer, _print_service_entry."""

    def test_print_header(self, capsys: pytest.CaptureFixture[str]) -> None:
        status_mod._print_header()
        out = capsys.readouterr().out
        assert "SYSTEM STATUS REPORT" in out

    def test_print_footer(self, capsys: pytest.CaptureFixture[str]) -> None:
        status_mod._print_footer()
        out = capsys.readouterr().out
        assert out.strip()

    def test_print_service_entry_active(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        svc = SystemdService(
            name="ami-test",
            active="active",
            sub="running",
            enabled="enabled",
            pid="12345",
            path="/etc/systemd/user/ami-test.service",
            restart="always",
        )
        info = ServiceDisplayInfo(
            row_type="service",
            row_details=["extra info"],
            ports_str="0.0.0.0:8080",
        )
        status_mod._print_service_entry(svc, info, [], [])
        out = capsys.readouterr().out
        assert "ami-test" in out
        assert "PID:" in out
        assert "Ports:" in out

    def test_print_service_entry_inactive(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        svc = SystemdService(
            name="ami-dead",
            active="inactive",
            sub="dead",
            pid="0",
            path="/etc/systemd/system/ami-dead.service",
        )
        info = ServiceDisplayInfo(row_type="service")
        status_mod._print_service_entry(svc, info, [], [])
        out = capsys.readouterr().out
        assert "ami-dead" in out
        assert "PID:" not in out

    def test_print_service_entry_failed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        svc = SystemdService(
            name="ami-fail",
            active="failed",
            sub="failed",
            path="/tmp/ami-fail.service",
        )
        info = ServiceDisplayInfo(row_type="service")
        status_mod._print_service_entry(svc, info, [], [])
        out = capsys.readouterr().out
        assert "ami-fail" in out

    def test_print_service_entry_activating(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        svc = SystemdService(
            name="ami-starting",
            active="activating",
            sub="auto-restart",
            path="/tmp/x.service",
        )
        info = ServiceDisplayInfo(row_type="service")
        status_mod._print_service_entry(svc, info, [], [])
        out = capsys.readouterr().out
        assert "ami-starting" in out

    def test_print_service_entry_unknown_status(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        svc = SystemdService(
            name="ami-unknown",
            active="maintenance",
            sub="",
            path="/tmp/u.service",
        )
        info = ServiceDisplayInfo(row_type="service")
        status_mod._print_service_entry(svc, info, [], [])
        out = capsys.readouterr().out
        assert "ami-unknown" in out

    def test_print_service_entry_with_containers(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        svc = SystemdService(
            name="ami-with-kids",
            active="active",
            sub="running",
            enabled="enabled",
            pid="100",
            path="/tmp/wk.service",
        )
        info = ServiceDisplayInfo(row_type="service")
        stats: list[ContainerStatsData] = [
            ContainerStatsData(
                name="child-c1",
                cpu="0.5%",
                mem_usage="100MB / 1GB",
                mem_percent="10.0",
            )
        ]
        sizes: list[ContainerSizeData] = [
            ContainerSizeData(
                name="child-c1",
                writable="10MB",
                virtual="50MB",
            )
        ]
        status_mod._print_service_entry(svc, info, stats, sizes)
        out = capsys.readouterr().out
        assert "ami-with-kids" in out
