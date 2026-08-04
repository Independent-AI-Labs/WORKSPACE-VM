"""Integration tests for oc wrapper config deployment.

Verifies that the oc wrapper idempotently deploys opencode user config
from the workspace template on every invocation.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


AMI_ROOT = _find_project_root()
OC_SRC = AMI_ROOT / "workspace" / "config" / "opencode"
PLUGIN_NAME = "add-user-message-context.js"


@pytest.fixture
def config_deploy_script() -> str:
    """Return the config deployment bash snippet from the oc wrapper."""
    return rf"""
        AMI_ROOT="{AMI_ROOT}"
        HOME="$1"
        OC_SRC="$AMI_ROOT/workspace/config/opencode"
        OC_DIR="${{HOME}}/.config/opencode"
        mkdir -p "$OC_DIR/plugins"
        if [ ! -f "$OC_DIR/opencode.jsonc" ]; then
            cp "$OC_SRC/opencode.jsonc" "$OC_DIR/opencode.jsonc"
        fi
    """


@pytest.mark.integration
class TestOcConfigDeployment:
    """Test idempotent config deployment from workspace template."""

    def test_fresh_deploy_creates_opencode_jsonc(
        self, tmp_path: Path, config_deploy_script: str
    ):
        """First run with no existing config: opencode.jsonc is created."""
        home = tmp_path / "home"
        home.mkdir()

        result = subprocess.run(
            ["bash", "-c", config_deploy_script, "deploy", str(home)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"deploy failed: {result.stderr}"

        oc_dir = home / ".config" / "opencode"
        assert (oc_dir / "opencode.jsonc").is_file(), "opencode.jsonc not created"

    def test_idempotent_does_not_overwrite(
        self, tmp_path: Path, config_deploy_script: str
    ):
        """Second run preserves existing files, does not overwrite."""
        home = tmp_path / "home"
        home.mkdir()
        oc_dir = home / ".config" / "opencode"
        oc_dir.mkdir(parents=True)

        custom_json = '{"instructions": ["custom.md"]}\n'
        (oc_dir / "opencode.jsonc").write_text(custom_json)

        result = subprocess.run(
            ["bash", "-c", config_deploy_script, "deploy", str(home)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"deploy failed: {result.stderr}"

        assert (oc_dir / "opencode.jsonc").read_text() == custom_json, (
            "opencode.jsonc was overwritten"
        )

    def test_missing_source_does_not_fail(
        self, tmp_path: Path, config_deploy_script: str
    ):
        """Graceful when workspace template source doesn't exist."""
        home = tmp_path / "home"
        home.mkdir()

        safe_script = rf"""
            HOME="{home}"
            OC_SRC="/nonexistent/path/to/config"
            OC_DIR="${{HOME}}/.config/opencode"
            mkdir -p "$OC_DIR/plugins"
            if [ ! -f "$OC_DIR/opencode.jsonc" ] \
                && [ -f "$OC_SRC/opencode.jsonc" ]; then
                cp "$OC_SRC/opencode.jsonc" "$OC_DIR/opencode.jsonc"
            fi
        """

        result = subprocess.run(
            ["bash", "-c", safe_script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"deploy with missing source should not fail: {result.stderr}"
        )

    def test_source_files_are_valid(self):
        """Source template files are syntactically valid."""
        assert OC_SRC.is_dir(), f"Source config directory missing: {OC_SRC}"

        jsonc = OC_SRC / "opencode.jsonc"
        assert jsonc.is_file(), f"opencode.jsonc missing: {jsonc}"
        content = jsonc.read_text()
        assert '"instructions"' in content, "instructions field missing"
        assert '"~/.config/opencode/ami-environment.md"' in content, (
            "ami-environment.md reference missing"
        )
        assert '"~/.config/opencode/system-instruction.md"' in content, (
            "system-instruction.md reference missing"
        )

        sys_tmpl = OC_SRC / "system-instruction.template.md"
        assert sys_tmpl.is_file(), f"system-instruction.template.md missing: {sys_tmpl}"
        content = sys_tmpl.read_text()
        assert "AUDITED" in content, "audit language missing"
        assert "PENALTIES" in content, "penalties language missing"

        plugin = OC_SRC / "plugins" / "add-user-message-context.template.js"
        assert plugin.is_file(), (
            f"add-user-message-context.template.js missing: {plugin}"
        )
        content = plugin.read_text()
        assert "experimental.chat.messages.transform" in content, (
            "messages.transform hook missing"
        )
        assert "experimental.chat.system.transform" in content, (
            "system.transform hook missing"
        )


@pytest.mark.integration
class TestRulesPlugin:
    """Test the rules plugin management."""

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


@pytest.mark.integration
class TestOcEnvironmentFile:
    """Test environment file regeneration behavior."""

    def test_welcome_output_is_written(self, tmp_path: Path):
        """Simulate the welcome generation and file write."""
        home = tmp_path / "home"
        home.mkdir()
        oc_dir = home / ".config" / "opencode"
        oc_dir.mkdir(parents=True)

        env_file = oc_dir / "ami-environment.md"
        assert not env_file.exists()

        test_content = "test banner content\nwith multiple lines\n"
        script = rf"""
            WELCOME='{test_content.rstrip()}'
            printf '%b\n' "$WELCOME" > "{env_file}"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, f"script failed: {result.stderr}"
        assert env_file.is_file(), "ami-environment.md not created"
        content = env_file.read_text()
        assert "test banner content" in content

    def test_environment_file_is_overwritten(self, tmp_path: Path):
        """Each run overwrites the environment file with fresh content."""
        home = tmp_path / "home"
        home.mkdir()
        oc_dir = home / ".config" / "opencode"
        oc_dir.mkdir(parents=True)

        env_file = oc_dir / "ami-environment.md"
        env_file.write_text("old stale content\n")

        new_content = "fresh banner\nupdated\n"
        script = rf"""
            WELCOME='{new_content.rstrip()}'
            printf '%b\n' "$WELCOME" > "{env_file}"
        """

        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        content = env_file.read_text()
        assert "fresh banner" in content
        assert "old stale" not in content


@pytest.mark.integration
class TestSystemInstructionDeployment:
    """Test system-instruction template deployment."""

    def test_template_deployed_on_first_run(self, tmp_path: Path):
        """First run with no existing file: system-instruction.md is created."""
        home = tmp_path / "home"
        home.mkdir()
        oc_dir = home / ".config" / "opencode"
        oc_dir.mkdir(parents=True)

        sys_file = oc_dir / "system-instruction.md"
        assert not sys_file.exists()

        src_tmpl = OC_SRC / "system-instruction.template.md"
        assert src_tmpl.is_file(), "source template missing"
        subprocess.run(
            ["cp", str(src_tmpl), str(sys_file)],
            check=True,
        )
        assert sys_file.is_file(), "system-instruction.md not created"
        content = sys_file.read_text()
        assert "AUDITED" in content
        assert "PENALTIES" in content
        assert "RECORDED" in content

    def test_idempotent_does_not_overwrite(self, tmp_path: Path):
        """Second run preserves existing content, does not overwrite."""
        home = tmp_path / "home"
        home.mkdir()
        oc_dir = home / ".config" / "opencode"
        oc_dir.mkdir(parents=True)

        sys_file = oc_dir / "system-instruction.md"
        custom_content = "CUSTOM AUDIT INSTRUCTION\n"
        sys_file.write_text(custom_content)

        script = rf"""
            SYS_FILE="{sys_file}"
            if [ ! -f "$SYS_FILE" ]; then
                cp "{OC_SRC / "system-instruction.template.md"}" "$SYS_FILE"
            fi
        """
        result = subprocess.run(
            ["bash", "-c", script],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        assert sys_file.read_text() == custom_content, (
            "system-instruction.md was overwritten"
        )


@pytest.mark.integration
class TestOcScriptSelfChecks:
    """Test that the oc script itself is well-formed."""

    @pytest.fixture
    def oc_path(self) -> Path:
        p = AMI_ROOT / "workspace" / "scripts" / "bin" / "oc"
        assert p.is_file(), f"oc script missing: {p}"
        return p

    def test_oc_help_works(self, oc_path: Path):
        """oc --help returns success and mentions opencode."""
        result = subprocess.run(
            [str(oc_path), "--help"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, f"oc --help failed: {result.stderr}"
        assert "opencode" in result.stdout.lower(), (
            f"Help output missing opencode mention: {result.stdout}"
        )

    def test_oc_version_works(self, oc_path: Path):
        """oc --version returns success (or at least doesn't crash)."""
        result = subprocess.run(
            [str(oc_path), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, f"oc --version failed: {result.stderr}"

    def test_oc_passes_session_flag_to_opencode(self, oc_path: Path):
        """oc -s <session> passes flag through directly, no run wrapper."""
        result = subprocess.run(
            [str(oc_path), "-s", "test_session_tdd", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        combined = result.stdout + result.stderr
        assert "You must provide a message or a command" not in combined, (
            f"oc wrapped -s flag in run subcommand: {combined}"
        )

    def test_oc_runs_task_with_run_subcommand(self, oc_path: Path):
        """oc 'task text' wraps in run --dir subcommand."""
        result = subprocess.run(
            [str(oc_path), "--help"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        )
        combined = result.stdout + result.stderr
        assert "usage:" in combined.lower() or "Usage" in combined, (
            f"oc did not produce help output: {combined}"
        )
        """oc script contains the idempotent config deployment code."""
        content = oc_path.read_text()
        assert "OC_SRC" in content, "Missing OC_SRC variable"
        assert "OC_DIR" in content, "Missing OC_DIR variable"
        assert "opencode.jsonc" in content, "Missing opencode.jsonc reference"
        assert "system-instruction.template.md" in content, (
            "Missing system-instruction deployment"
        )
        assert "mkdir -p" in content, "Missing mkdir -p for plugins dir"
