"""Integration tests for oc wrapper config deployment."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.integration.oc_config_test_helpers import (
    OC_SRC,
    WORKSPACE_ROOT,
    WRAPPERS,
    configured_instruction_files,
    run_wrapper,
    run_wrapper_result,
)

EXIT_USAGE = 2


def _agent_block(output: str, name: str) -> str:
    start = output.index(f"{name} (primary)")
    end = output.index("\n]", start) + 2
    return output[start:end]


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
        assert (expected_config / "workspace-environment.md").is_file()
        instruction_files = configured_instruction_files(expected_config)
        assert instruction_files == [
            expected_config / "workspace-environment.md",
            expected_config / "system-instruction.md",
        ]
        assert all(instruction_file.is_file() for instruction_file in instruction_files)
        config = json.loads(
            (expected_config / "opencode.jsonc").read_text(encoding="utf-8")
        )
        assert config["subagent_depth"] == 0
        assert config["agent"] == {
            "build": {"color": "#FFFFFF"},
            "plan": {"color": "#A855F7"},
            "explore": {"disable": True},
            "general": {"disable": True},
        }
        assert config["permission"]["task"] == "deny"
        assert json.loads(values["content"]) == {
            "subagent_depth": 0,
            "agent": {
                "build": {"color": "#FFFFFF"},
                "plan": {"color": "#A855F7"},
                "explore": {"disable": True},
                "general": {"disable": True},
            },
            "permission": {"task": "deny"},
        }
        answer = expected_config / "agents" / "answer.md"
        assert answer.is_file()
        assert answer.read_text(encoding="utf-8") == (
            OC_SRC / "agents" / "answer.md"
        ).read_text(encoding="utf-8")
        assert (
            instruction_files[0].read_text(encoding="utf-8")
            == "WORKSPACE-VM workspace\n"
        )
        assert instruction_files[1].read_text(encoding="utf-8") == (
            OC_SRC / "system-instruction.template.md"
        ).read_text(encoding="utf-8")
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

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    @pytest.mark.parametrize("option", [["--agent", "answer"], ["--agent=answer"]])
    def test_agent_option_keeps_task_conversion(
        self, tmp_path: Path, wrapper: Path, option: list[str]
    ):
        """A selected agent rides the run conversion instead of becoming a command."""
        _, args, _ = run_wrapper(tmp_path, wrapper, [*option, "answer task"])
        assert args == [
            "run",
            "--dir",
            str(tmp_path / f"caller-{wrapper.name}"),
            "--agent",
            "answer",
            "answer task",
        ]

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    def test_agent_option_without_task_starts_interactive(
        self, tmp_path: Path, wrapper: Path
    ):
        """An agent alone opens the TUI with that primary agent."""
        _, args, _ = run_wrapper(tmp_path, wrapper, ["--agent", "answer"])
        assert args == ["--agent", "answer"]

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    def test_agent_option_with_upstream_flag_stays_direct(
        self, tmp_path: Path, wrapper: Path
    ):
        """An agent plus an upstream flag bypasses task conversion."""
        _, args, _ = run_wrapper(tmp_path, wrapper, ["--agent", "answer", "--continue"])
        assert args == ["--agent", "answer", "--continue"]

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    @pytest.mark.parametrize(
        ("option", "message"),
        [
            (["--agent"], "--agent requires a name"),
            (["--agent="], "--agent requires a non-empty name"),
        ],
    )
    def test_agent_option_requires_a_name(
        self, tmp_path: Path, wrapper: Path, option: list[str], message: str
    ):
        """A missing or empty agent name fails before opencode starts."""
        result = run_wrapper_result(tmp_path, wrapper, option)
        assert result.returncode == EXIT_USAGE
        assert message in result.stderr

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    def test_existing_answer_agent_is_refreshed(self, tmp_path: Path, wrapper: Path):
        """Provision-owned agent files update while user instructions stay."""
        config_dir = tmp_path / "existing-config"
        agents = config_dir / "agents"
        agents.mkdir(parents=True)
        (agents / "answer.md").write_text("stale\n", encoding="utf-8")
        (config_dir / "opencode.jsonc").write_text("{}\n", encoding="utf-8")
        (config_dir / "system-instruction.md").write_text("custom\n", encoding="utf-8")
        run_wrapper(tmp_path, wrapper, ["normal task"], config_dir)
        assert (agents / "answer.md").read_text(encoding="utf-8") == (
            OC_SRC / "agents" / "answer.md"
        ).read_text(encoding="utf-8")
        assert (config_dir / "system-instruction.md").read_text(
            encoding="utf-8"
        ) == "custom\n"

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


@pytest.mark.integration
class TestAnswerAgent:
    def test_answer_agent_is_read_only_and_requires_verified_answers(self):
        """The Answer agent keeps Plan's bash access but cannot write or track work."""
        text = (OC_SRC / "agents" / "answer.md").read_text(encoding="utf-8")
        assert "mode: primary" in text
        assert 'color: "#22C55E"' in text
        assert "edit: deny" in text
        assert "todowrite: deny" in text
        assert "bash: allow" in text
        assert "question: allow" in text
        assert "Do not create plan files." in text
        assert "Never guess." in text

    @pytest.mark.parametrize("boot_dir", [".boot-linux", ".boot-macos"])
    def test_real_opencode_loads_answer_agent(self, tmp_path: Path, boot_dir: str):
        """opencode parses the deployed agent and keeps the intended permissions."""
        binary = WORKSPACE_ROOT / boot_dir / "bin" / "opencode"
        if not binary.is_file():
            pytest.skip(f"opencode binary not installed at {binary}")
        home = tmp_path / "home"
        config = tmp_path / "config"
        data = tmp_path / "data"
        for directory in (home, config, data):
            directory.mkdir()
        env = {
            **os.environ,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(config),
            "XDG_DATA_HOME": str(data),
            "OPENCODE_BINARY": str(binary),
            "OPENCODE_DB": str(tmp_path / "verify.db"),
        }
        result = subprocess.run(
            [str(WRAPPERS[0]), "--", "agent", "list"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )
        assert result.returncode == 0, result.stderr
        block = _agent_block(result.stdout, "answer")
        assert '"permission": "edit",\n    "action": "deny"' in block
        assert '"permission": "todowrite",\n    "action": "deny"' in block
        assert '"permission": "bash",\n    "action": "allow"' in block
        assert '"permission": "question",\n    "action": "allow"' in block


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
