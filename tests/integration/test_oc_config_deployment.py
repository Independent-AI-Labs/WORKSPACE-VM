"""Integration tests for oc wrapper config deployment."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.integration.oc_config_test_helpers import (
    AMI_ROOT,
    MODERATOR_INSTALLER,
    OC_SRC,
    WRAPPERS,
    configured_instruction_files,
    run_wrapper,
)


@pytest.mark.integration
class TestOcWrappers:
    @pytest.mark.parametrize("wrapper", WRAPPERS)
    def test_normal_task_uses_fresh_xdg_config(self, tmp_path: Path, wrapper: Path):
        """A real wrapper process deploys config and converts a task to run."""
        values, args, home = run_wrapper(tmp_path, wrapper, ["normal task"])
        expected_config = tmp_path / f"xdg-config-{wrapper.name}" / "opencode"
        assert values["db"] == ""
        assert values["config"] == str(expected_config)
        assert args == [
            "run",
            "--dir",
            str(tmp_path / f"caller-{wrapper.name}"),
            "normal task",
        ]
        assert (expected_config / "opencode.jsonc").is_file()
        assert (expected_config / "ami-environment.md").is_file()
        instruction_files = configured_instruction_files(expected_config)
        assert instruction_files == [
            expected_config / "ami-environment.md",
            expected_config / "system-instruction.md",
        ]
        assert all(instruction_file.is_file() for instruction_file in instruction_files)
        config = json.loads(
            (expected_config / "opencode.jsonc").read_text(encoding="utf-8")
        )
        assert config["subagent_depth"] == 0
        assert config["agent"] == {
            "explore": {"disable": True},
            "general": {"disable": True},
        }
        assert config["permission"]["task"] == "deny"
        assert json.loads(values["content"]) == {
            "subagent_depth": 0,
            "agent": {"explore": {"disable": True}, "general": {"disable": True}},
            "permission": {"task": "deny"},
        }
        assert (
            instruction_files[0].read_text(encoding="utf-8")
            == "WORKSPACE-VM workspace\n"
        )
        assert instruction_files[1].read_text(encoding="utf-8") == (
            OC_SRC / "system-instruction.template.md"
        ).read_text(encoding="utf-8")
        assert not (expected_config / "plugins" / ".local-response-moderator").exists()
        assert not (home / ".config").exists()

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    @pytest.mark.parametrize(
        "database", ["relative.db", "/tmp/absolute.db", ":memory:"]
    )
    def test_database_option_is_exported_unchanged(
        self, tmp_path: Path, wrapper: Path, database: str
    ):
        """Both option forms are consumed before normal upstream dispatch."""
        option = "--db=" + database if database == ":memory:" else "--db"
        arguments = [option, "database task"]
        if option == "--db":
            arguments.insert(1, database)
        values, args, _ = run_wrapper(tmp_path, wrapper, arguments)
        assert values["db"] == database
        assert args[-1] == "database task"

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    def test_separator_dispatches_a_direct_command(self, tmp_path: Path, wrapper: Path):
        """The documented separator preserves real upstream command arguments."""
        values, args, _ = run_wrapper(
            tmp_path, wrapper, ["--db=relative.db", "--", "--version"]
        )
        assert values["db"] == "relative.db"
        assert args == ["--version"]

    def test_wrappers_have_identical_dispatch(self, tmp_path: Path):
        """The shared helper gives both binaries the same dispatch result."""
        config_dir = tmp_path / "isolated-config"
        oc_values, oc_args, _ = run_wrapper(tmp_path, WRAPPERS[0], [], config_dir)
        ocb_values, ocb_args, _ = run_wrapper(tmp_path, WRAPPERS[1], [], config_dir)
        assert (oc_values, oc_args) == (ocb_values, ocb_args)
        assert (config_dir / "opencode.jsonc").is_file()

    def test_symlinked_ocb_uses_the_source_repository_root(self, tmp_path: Path):
        """The source-build wrapper resolves its own symlink before finding its root."""
        symlink = tmp_path / "bin" / "ocb"
        symlink.parent.mkdir()
        symlink.symlink_to(WRAPPERS[1])
        values, args, _ = run_wrapper(tmp_path, symlink, ["symlink task"])
        assert values["db"] == ""
        assert args[-1] == "symlink task"

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    def test_unavailable_podman_does_not_block_opencode(
        self, tmp_path: Path, wrapper: Path
    ):
        """A blocked Podman command is not part of wrapper startup."""
        command_dir = tmp_path / "commands"
        command_dir.mkdir()
        podman = command_dir / "podman"
        podman.write_text(
            '#!/bin/bash\nset -euo pipefail\ntouch "$OC_PODMAN_CALLED"\nsleep 30\n',
            encoding="utf-8",
        )
        podman.chmod(0o755)
        marker = tmp_path / "podman-called"
        values, args, _ = run_wrapper(
            tmp_path,
            wrapper,
            ["normal task"],
            extra_env={
                "PATH": f"{command_dir}:{os.environ['PATH']}",
                "OC_PODMAN_CALLED": str(marker),
            },
        )
        assert values["db"] == ""
        assert args[-1] == "normal task"
        assert not marker.exists()


def _moderator_env(
    tmp_path: Path, models: str = '{"data":[{"id":"/zip/MiniCPM5-1B-Q8_0.gguf"}]}'
) -> dict[str, str]:
    """Provide an isolated XDG root and a deterministic Gateway model response."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    curl = bin_dir / "curl"
    curl.write_text(
        f"#!/bin/bash\nset -euo pipefail\nprintf '%s\\n' '{models}'\n",
        encoding="utf-8",
    )
    curl.chmod(0o755)
    return {
        **os.environ,
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "LOCAL_RESPONSE_MODERATOR_REPO_ROOT": str(AMI_ROOT),
    }


def _installer_root(tmp_path: Path) -> Path:
    root = tmp_path / "moderator-repo"
    source = AMI_ROOT / "workspace" / "config" / "opencode" / "plugins"
    destination = root / "workspace" / "config" / "opencode" / "plugins"
    destination.parent.mkdir(parents=True)
    shutil.copytree(source, destination)
    scripts = root / "workspace" / "scripts"
    scripts.mkdir()
    shutil.copy(MODERATOR_INSTALLER, scripts / "install-opencode-moderator")
    (scripts / "install-opencode-moderator").chmod(0o755)
    return root


@pytest.mark.integration
class TestModeratorInstaller:
    def test_install_verify_status_and_uninstall(self, tmp_path: Path):
        """A complete release is activated without changing unrelated plugins."""
        env = _moderator_env(tmp_path)
        plugin_dir = Path(env["XDG_CONFIG_HOME"]) / "opencode" / "plugins"
        plugin_dir.mkdir(parents=True)
        unrelated = plugin_dir / "unrelated.js"
        unrelated.write_text("export default {}\n", encoding="utf-8")

        install = subprocess.run(
            [str(MODERATOR_INSTALLER), "install"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert install.returncode == 0, install.stderr
        assert "installed release:" in install.stdout
        assert "destination:" in install.stdout
        assert "gateway: http://127.0.0.1:9080/llamafile" in install.stdout
        assert "model: /zip/MiniCPM5-1B-Q8_0.gguf" in install.stdout
        assert "verification: passed" in install.stdout
        entry = plugin_dir / "local-response-moderator.js"
        current = plugin_dir / ".local-response-moderator" / "current"
        assert entry.is_symlink()
        assert current.is_symlink()
        release = current.resolve()
        assert (release / "local-response-moderator.js").is_file()
        assert (release / "local-response-moderator-machine.js").is_file()
        assert (release / "local-response-moderator.sh").stat().st_mode & 0o111
        assert (release / "config.json").is_file()

        verify = subprocess.run(
            [str(MODERATOR_INSTALLER), "verify"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert verify.returncode == 0, verify.stderr
        status = subprocess.run(
            [str(MODERATOR_INSTALLER), "status"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert status.returncode == 0, status.stderr
        assert "source drift: none" in status.stdout

        uninstall = subprocess.run(
            [str(MODERATOR_INSTALLER), "uninstall"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert uninstall.returncode == 0, uninstall.stderr
        assert not entry.exists()
        assert unrelated.exists()

    def test_reinstall_is_idempotent_and_uninstall_preserves_foreign_entry(
        self, tmp_path: Path
    ):
        """The installer reuses a release and never removes another plugin owner."""
        env = _moderator_env(tmp_path)
        first = subprocess.run(
            [str(MODERATOR_INSTALLER), "install"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        plugin_dir = Path(env["XDG_CONFIG_HOME"]) / "opencode" / "plugins"
        first_release = (plugin_dir / ".local-response-moderator" / "current").resolve()
        second = subprocess.run(
            [str(MODERATOR_INSTALLER), "install"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert first.returncode == second.returncode == 0
        current = plugin_dir / ".local-response-moderator" / "current"
        assert current.resolve() == first_release
        entry = plugin_dir / "local-response-moderator.js"
        entry.unlink()
        entry.write_text("export default {}\n", encoding="utf-8")
        uninstall = subprocess.run(
            [str(MODERATOR_INSTALLER), "uninstall"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert uninstall.returncode != 0
        assert entry.read_text() == "export default {}\n"

    def test_verify_detects_modified_active_release(self, tmp_path: Path):
        """Verification fails when the active adapter no longer matches source."""
        env = _moderator_env(tmp_path)
        install = subprocess.run(
            [str(MODERATOR_INSTALLER), "install"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert install.returncode == 0, install.stderr
        current = (
            Path(env["XDG_CONFIG_HOME"])
            / "opencode"
            / "plugins"
            / ".local-response-moderator"
            / "current"
        )
        (current.resolve() / "local-response-moderator.js").write_text(
            "export default {}\n", encoding="utf-8"
        )
        verify = subprocess.run(
            [str(MODERATOR_INSTALLER), "verify"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert verify.returncode != 0

    def test_install_rejects_nonexecutable_classifier_and_direct_endpoint(
        self, tmp_path: Path
    ):
        root = _installer_root(tmp_path)
        installer = root / "workspace" / "scripts" / "install-opencode-moderator"
        env = _moderator_env(tmp_path / "permissions")
        env["LOCAL_RESPONSE_MODERATOR_REPO_ROOT"] = str(root)
        classifier = (
            root
            / "workspace"
            / "config"
            / "opencode"
            / "plugins"
            / "local-response-moderator.sh"
        )
        original = classifier.read_text()
        classifier.chmod(0o644)
        permissions = subprocess.run(
            [str(installer), "install"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert permissions.returncode != 0
        assert "not executable" in permissions.stderr

        classifier.chmod(0o755)
        classifier.write_text(original + "\nif then\n")
        invalid = subprocess.run(
            [str(installer), "install"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert invalid.returncode != 0
        classifier.write_text(original)
        config = (
            root
            / "workspace"
            / "config"
            / "opencode"
            / "plugins"
            / "local-response-moderator.template.json"
        )
        config.write_text(
            '{"gateway_url":"http://127.0.0.1:8080","model":"/zip/MiniCPM5-1B-Q8_0.gguf"}\n'
        )
        endpoint = subprocess.run(
            [str(installer), "install"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert endpoint.returncode != 0
        assert "Workspace Gateway relay" in endpoint.stderr

    def test_install_rejects_unreachable_gateway_and_missing_model(
        self, tmp_path: Path
    ):
        missing = _moderator_env(tmp_path / "missing", '{"data":[]}')
        missing_model = subprocess.run(
            [str(MODERATOR_INSTALLER), "install"],
            capture_output=True,
            text=True,
            env=missing,
            check=False,
        )
        assert missing_model.returncode != 0
        assert "does not expose configured model" in missing_model.stderr

        unreachable = _moderator_env(tmp_path / "unreachable")
        curl = Path(unreachable["PATH"].split(":", 1)[0]) / "curl"
        curl.write_text("#!/bin/bash\nexit 1\n")
        curl.chmod(0o755)
        failed_gateway = subprocess.run(
            [str(MODERATOR_INSTALLER), "install"],
            capture_output=True,
            text=True,
            env=unreachable,
            check=False,
        )
        assert failed_gateway.returncode != 0
        assert "Gateway model query failed" in failed_gateway.stderr

    def test_failed_activation_retains_previous_release(self, tmp_path: Path):
        root = _installer_root(tmp_path)
        installer = root / "workspace" / "scripts" / "install-opencode-moderator"
        env = _moderator_env(tmp_path / "activation")
        env["LOCAL_RESPONSE_MODERATOR_REPO_ROOT"] = str(root)
        assert (
            subprocess.run(
                [str(installer), "install"],
                capture_output=True,
                text=True,
                env=env,
                check=False,
            ).returncode
            == 0
        )
        current = (
            Path(env["XDG_CONFIG_HOME"])
            / "opencode"
            / "plugins"
            / ".local-response-moderator"
            / "current"
        )
        previous = current.resolve()
        source = (
            root
            / "workspace"
            / "config"
            / "opencode"
            / "plugins"
            / "local-response-moderator.js"
        )
        source.write_text(source.read_text() + "\n")
        bin_dir = tmp_path / "activation" / "activation-bin"
        bin_dir.mkdir()
        mover = bin_dir / "mv"
        mover.write_text(
            "#!/bin/bash\n"
            'if [[ "$*" == *"/current" ]]; then exit 1; fi\n'
            'exec /bin/mv "$@"\n'
        )
        mover.chmod(0o755)
        env["PATH"] = f"{bin_dir}:{env['PATH']}"
        interrupted = subprocess.run(
            [str(installer), "install"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert interrupted.returncode != 0
        assert current.resolve() == previous


@pytest.mark.integration
class TestRulesPlugin:
    def test_template_file_exists(self):
        """Template file is present in workspace."""
        tmpl = OC_SRC / "plugins" / "add-user-message-context.template.js"
        assert tmpl.is_file(), f"template missing: {tmpl}"

    def test_user_file_created_on_first_run(self, tmp_path: Path):
        """rules list creates user file from template if missing."""
        userfile = tmp_path / "add-user-message-context.js"
        tmpl = OC_SRC / "plugins" / "add-user-message-context.template.js"
        assert not userfile.exists()

        subprocess.run(
            ["cp", str(tmpl), str(userfile)],
            check=True,
        )
        assert userfile.is_file()
        content = userfile.read_text()
        assert "const RULES" in content
