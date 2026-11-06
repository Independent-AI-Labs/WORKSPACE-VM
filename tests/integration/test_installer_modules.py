"""Integration tests for the auxiliary host installer modules."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from workspace.scripts import bootstrap_aux
from workspace.scripts import host_setup_installer as host
from workspace.scripts.bootstrap_aux import (
    AuxResult,
    _detect_command,
    _detect_failure,
    _feature_args,
    _owner_home,
    _wrap_as_owner,
    build_commands,
    detect_configured,
    run_feature,
    run_selected,
)
from workspace.scripts.bootstrap_aux_defs import (
    AUX_YAML,
    AuxArg,
    AuxDefaults,
    AuxFeature,
    AuxManifest,
    AuxSelection,
    features_by_group,
    load_defaults,
    load_registry,
    ordered_features,
    validate_defaults,
)
from workspace.scripts.host_setup_installer_ui import (
    print_section,
    print_status,
    restore_terminal,
)


class DetectFailure(OSError):
    def __init__(self) -> None:
        super().__init__("no exec")


class RegistryError(ValueError):
    def __init__(self) -> None:
        super().__init__("bad registry")


def feature(**overrides: object) -> AuxFeature:
    data: dict[str, object] = {
        "id": "demo",
        "label": "Demo",
        "description": "Demo feature",
        "group": "Storage",
        "scope": "agent",
        "action": "install-diagnostics",
        "order": 10,
    }
    data.update(overrides)
    return AuxFeature.model_validate(data)


class TestRegistry:
    def test_load_registry_and_groups(self):
        manifest = load_registry()
        assert manifest.groups == ["Storage", "Host Services"]
        grouped = features_by_group(manifest)
        assert [name for name, _ in grouped] == ["Storage", "Host Services"]
        assert grouped[0][1][0].id == "storage-locations"

    def test_load_registry_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="auxiliary registry missing"):
            load_registry(tmp_path / "absent.yaml")

    def test_load_defaults_and_validate(self):
        manifest = load_registry()
        defaults = load_defaults()
        validate_defaults(manifest, defaults)
        assert defaults.features["storage-locations"].args["fast"] == "/mnt/ws-fast"

    def test_load_defaults_missing_file(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="auxiliary defaults missing"):
            load_defaults(tmp_path / "absent.yaml")

    def test_duplicate_id_rejected(self, tmp_path: Path):
        target = tmp_path / "aux.yaml"
        target.write_text(
            "features:\n"
            "  - id: demo\n    label: A\n    description: A\n    group: G\n"
            "    scope: agent\n    action: install-diagnostics\n"
            "  - id: demo\n    label: B\n    description: B\n    group: G\n"
            "    scope: agent\n    action: install-diagnostics\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="duplicate auxiliary feature id"):
            load_registry(target)

    def test_unknown_action_rejected(self, tmp_path: Path):
        target = tmp_path / "aux.yaml"
        target.write_text(
            "features:\n"
            "  - id: demo\n    label: A\n    description: A\n    group: G\n"
            "    scope: agent\n    action: nope\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="unknown auxiliary action"):
            load_registry(target)

    def test_unknown_dependency_rejected(self, tmp_path: Path):
        target = tmp_path / "aux.yaml"
        target.write_text(
            "features:\n"
            "  - id: demo\n    label: A\n    description: A\n    group: G\n"
            "    scope: agent\n    action: install-diagnostics\n"
            "    requires: [missing]\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="unknown auxiliary dependency"):
            load_registry(target)

    def test_unknown_default_rejected(self):
        manifest = AuxManifest(features=[feature()])
        defaults = AuxDefaults(features={"ghost": AuxSelection()})
        with pytest.raises(ValueError, match="unknown auxiliary feature in defaults"):
            validate_defaults(manifest, defaults)

    def test_ordered_features_dependency_and_cycle(self):
        manifest = AuxManifest(
            features=[
                feature(id="later", order=20, requires=["first"]),
                feature(id="first", order=10),
            ]
        )
        ordered = ordered_features(manifest, {"later", "first"})
        assert [item.id for item in ordered] == ["first", "later"]

        cycle = AuxManifest(
            features=[
                feature(id="a", requires=["b"]),
                feature(id="b", requires=["a"]),
            ]
        )
        with pytest.raises(ValueError, match="dependency cycle"):
            ordered_features(cycle, {"a", "b"})

    def test_features_by_group_appends_undeclared(self):
        manifest = AuxManifest(
            groups=["Declared"],
            features=[feature(group="Declared"), feature(id="extra", group="Extra")],
        )
        assert [name for name, _ in features_by_group(manifest)] == [
            "Declared",
            "Extra",
        ]


class TestCommands:
    def test_build_commands_for_registry(self):
        manifest = load_registry()
        for entry in manifest.features:
            commands = build_commands(entry, {})
            assert commands
            assert all(isinstance(command, list) for command in commands)

    def test_build_commands_unknown_action(self):
        unknown = feature(action="does-not-exist")
        with pytest.raises(ValueError, match="unknown auxiliary action"):
            build_commands(unknown, {})

    def test_feature_args_use_defaults(self):
        entry = feature(args={"fast": AuxArg(default="/mnt/ws-fast")})
        assert _feature_args(entry, {}) == {"fast": "/mnt/ws-fast"}
        assert _feature_args(entry, {"fast": "/x"}) == {"fast": "/x"}


class TestDetect:
    def test_detect_path_relative(self):
        entry = feature(detect_path="workspace/config/install-aux.yaml")
        assert detect_configured(entry)

    def test_detect_path_absolute_missing(self, tmp_path: Path):
        entry = feature(detect_path=str(tmp_path / "absent"))
        assert not detect_configured(entry)

    def test_detect_mount(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(bootstrap_aux.os.path, "ismount", lambda _: True)
        assert detect_configured(feature(detect_mount="/mnt/ws-backup"))

    def test_detect_command_success(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(bootstrap_aux.subprocess, "run", lambda *a, **k: None)
        assert detect_configured(feature(detect_cmd=["true"]))

    def test_detect_command_failure_with_stderr(self, monkeypatch: pytest.MonkeyPatch):
        def boom(*args: object, **kwargs: object) -> None:
            raise subprocess.CalledProcessError(2, ["x"], stderr=b"bad\n")

        monkeypatch.setattr(bootstrap_aux.subprocess, "run", boom)
        assert not _detect_command(feature(detect_cmd=["x"], label="Demo"))

    def test_detect_command_failure_without_stderr(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        def boom(*args: object, **kwargs: object) -> None:
            raise subprocess.CalledProcessError(3, ["x"])

        monkeypatch.setattr(bootstrap_aux.subprocess, "run", boom)
        entry = feature(label="Demo", detect_cmd=["x"])
        assert not _detect_command(entry)
        exc = subprocess.CalledProcessError(3, ["x"])
        assert _detect_failure(entry, exc) == "Demo detect failed rc=3\n"

    def test_detect_command_oserror(self, monkeypatch: pytest.MonkeyPatch):
        def boom(*args: object, **kwargs: object) -> None:
            raise DetectFailure

        monkeypatch.setattr(bootstrap_aux.subprocess, "run", boom)
        assert not _detect_command(feature(detect_cmd=["missing"]))


class TestRunFeature:
    def test_root_scope_skipped_for_agent(self):
        result = run_feature(feature(scope="root"), {}, effective_uid=1000)
        assert not result.success
        assert "root action skipped" in result.message

    def test_agent_scope_requires_sudo_user(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        with pytest.raises(ValueError, match="requires SUDO_USER"):
            run_feature(feature(scope="agent"), {}, effective_uid=0)

    def test_agent_scope_wraps_as_owner(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SUDO_USER", "agent")
        monkeypatch.setattr(
            bootstrap_aux.pwd,
            "getpwnam",
            lambda _: SimpleNamespace(pw_dir="/tmp/owner"),
        )
        captured: list[list[str]] = []

        def record(command: list[str], **kwargs: object) -> None:
            captured.append(command)

        monkeypatch.setattr(bootstrap_aux.subprocess, "run", record)
        result = run_feature(feature(scope="agent"), {}, effective_uid=0)
        assert result.success
        assert captured[0][:3] == ["runuser", "-u", "agent"]

    def test_owner_home_unknown_user(self, monkeypatch: pytest.MonkeyPatch):
        def missing(_: str) -> SimpleNamespace:
            raise KeyError("nobody")

        monkeypatch.setattr(bootstrap_aux.pwd, "getpwnam", missing)
        with pytest.raises(ValueError, match="does not resolve"):
            _owner_home("nobody")

    def test_wrap_rejects_root(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setenv("SUDO_USER", "root")
        with pytest.raises(ValueError, match="requires SUDO_USER"):
            _wrap_as_owner(["true"])

    def test_run_one_called_process_error(self, monkeypatch: pytest.MonkeyPatch):
        def boom(*args: object, **kwargs: object) -> None:
            raise subprocess.CalledProcessError(1, ["false"])

        monkeypatch.setattr(bootstrap_aux.subprocess, "run", boom)
        result = run_feature(feature(), {}, effective_uid=1000)
        assert not result.success
        assert "rc=1" in result.message

    def test_run_one_oserror(self, monkeypatch: pytest.MonkeyPatch):
        def boom(*args: object, **kwargs: object) -> None:
            raise OSError("gone")

        monkeypatch.setattr(bootstrap_aux.subprocess, "run", boom)
        result = run_feature(feature(), {}, effective_uid=1000)
        assert not result.success
        assert "gone" in result.message

    def test_run_selected_stops_on_failure(self, caplog: pytest.LogCaptureFixture):
        first = feature(id="first")
        second = feature(id="second")
        calls: list[str] = []

        def fake_run(entry: AuxFeature, values: dict[str, str], effective_uid: int):
            calls.append(entry.id)
            return AuxResult(entry.id, False, "stop")

        original = bootstrap_aux.run_feature
        bootstrap_aux.run_feature = fake_run
        try:
            results = run_selected([first, second], {}, effective_uid=1000)
        finally:
            bootstrap_aux.run_feature = original
        assert calls == ["first"]
        assert len(results) == 1


class TestHostSelection:
    def test_allowed_branches(self):
        agent = feature(scope="agent")
        root = feature(scope="root")
        assert host._allowed(agent, "agent", 0)
        assert not host._allowed(root, "agent", 0)
        assert host._allowed(root, "root", 1000)
        assert not host._allowed(agent, "root", 1000)
        assert host._allowed(root, "all", 0)
        assert not host._allowed(root, "all", 1000)

    def test_select_defaults(self):
        manifest = load_registry()
        defaults = AuxDefaults(
            features={
                "storage-locations": AuxSelection(
                    args={"fast": "/fast", "backup": "/backup"}
                ),
                "storage-migrate": AuxSelection(enabled=False),
            }
        )
        selected, values = host._select_defaults(manifest, defaults, "all", 1000)
        assert [item.id for item in selected] == ["storage-locations"]
        assert values["storage-locations"]["backup"] == "/backup"

    def test_prompt_args(self, monkeypatch: pytest.MonkeyPatch):
        entry = feature(args={"fast": AuxArg(default="/mnt", description="Fast")})
        monkeypatch.setattr("builtins.input", lambda _: " /x ")
        assert host._prompt_args([entry]) == {"demo": {"fast": "/x"}}
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert host._prompt_args([entry]) == {"demo": {"fast": "/mnt"}}

    def test_select_interactive(self, monkeypatch: pytest.MonkeyPatch):
        manifest = AuxManifest(features=[feature(enabled_by_default=True)])
        monkeypatch.setattr(host, "detect_configured", lambda _: True)
        captured: dict[str, object] = {}

        def fake_multiselect(items, **kwargs):
            captured["items"] = items
            captured["preselected"] = kwargs["preselected"]
            captured["skippable"] = kwargs["skippable_ids"]
            return items

        monkeypatch.setattr(host._dialogs, "multiselect", fake_multiselect)
        selected = host._select_interactive(manifest, "all", 1000)
        assert [item.id for item in selected] == ["demo"]
        assert captured["preselected"] == {"demo"}
        assert captured["skippable"] == {"demo"}


class TestHostRun:
    def test_run_success(self, monkeypatch: pytest.MonkeyPatch, capsys):
        manifest = load_registry()
        monkeypatch.setattr(host, "load_defaults", lambda *a: _defaults())
        monkeypatch.setattr(
            host,
            "run_selected",
            lambda ordered, values: [AuxResult(ordered[0].id, True, "ok")],
        )
        code = host._run(manifest, "agent", AUX_YAML.parent / "missing.yaml")
        assert code == 0
        assert "Host configuration complete" in capsys.readouterr().out

    def test_run_failure(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
        manifest = load_registry()
        monkeypatch.setattr(
            host,
            "run_selected",
            lambda ordered, values: [AuxResult(ordered[0].id, False, "bad")],
        )
        defaults = _write_defaults(manifest, tmp_path)
        assert host._run(manifest, "agent", defaults) == 1

    def test_run_no_selection(self, monkeypatch: pytest.MonkeyPatch):
        manifest = load_registry()
        monkeypatch.setattr(host, "_select_defaults", lambda *a: ([], {}))
        monkeypatch.setattr(host, "load_defaults", lambda *a: AuxDefaults())
        assert host._run(manifest, "agent", Path("/tmp/x.yaml")) == 0

    def test_run_interactive_confirmed(self, monkeypatch: pytest.MonkeyPatch):
        manifest = AuxManifest(features=[feature()])
        monkeypatch.setattr(host.sys, "stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(host, "_select_interactive", lambda *a: [feature()])
        monkeypatch.setattr(host, "_prompt_args", lambda *a: {})
        monkeypatch.setattr(host._dialogs, "confirm", lambda *a: True)
        monkeypatch.setattr(
            host,
            "run_selected",
            lambda ordered, values: [AuxResult(ordered[0].id, True, "ok")],
        )
        assert host._run(manifest, "all", None) == 0

    def test_run_interactive_cancelled(self, monkeypatch: pytest.MonkeyPatch):
        manifest = AuxManifest(features=[feature()])
        monkeypatch.setattr(host.sys, "stdin", SimpleNamespace(isatty=lambda: True))
        monkeypatch.setattr(host, "_select_interactive", lambda *a: [feature()])
        monkeypatch.setattr(host, "_prompt_args", lambda *a: {})
        monkeypatch.setattr(host._dialogs, "confirm", lambda *a: False)
        assert host._run(manifest, "all", None) == 0

    def test_main_success(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(sys, "argv", ["host_setup_installer"])

        def registry() -> AuxManifest:
            return AuxManifest()

        monkeypatch.setattr(host, "load_registry", registry)
        monkeypatch.setattr(host, "_run", lambda *a: 0)
        assert host.main() == 0

    def test_main_error(self, monkeypatch: pytest.MonkeyPatch, capsys):
        monkeypatch.setattr(sys, "argv", ["host_setup_installer"])

        def boom() -> AuxManifest:
            raise RegistryError

        monkeypatch.setattr(host, "load_registry", boom)
        assert host.main() == 1
        assert "bad registry" in capsys.readouterr().err


class TestUi:
    def test_print_helpers(self, capsys):
        print_section("Title")
        print_status("✓", "done")
        restore_terminal()
        output = capsys.readouterr().out
        assert "Title" in output
        assert "done" in output


def _defaults() -> AuxDefaults:
    return AuxDefaults(
        features={
            "storage-locations": AuxSelection(
                args={"fast": "/mnt/ws-fast", "backup": "/mnt/ws-backup"}
            )
        }
    )


def _write_defaults(manifest: AuxManifest, tmp_path: Path) -> Path:
    lines = ["features:"]
    for entry in manifest.features:
        lines.extend([f"  {entry.id}:", "    enabled: true"])
    target = tmp_path / "install-aux-defaults.yaml"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
