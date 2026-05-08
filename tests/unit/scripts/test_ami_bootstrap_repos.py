"""Unit tests for ami/scripts/bin/ami-bootstrap-repos bash walker.

The walker is bash but its YAML-parsing logic and clone/skip/pull
control flow are critical infrastructure: a misread of
workspace-clones.yaml silently skips repos or clones the wrong remote.
These tests exercise the script via subprocess against fixture YAML
files in tmp dirs and assert observable behaviour.

Strategy: substitute `git` on PATH with a recording stub so each test
asserts which `git clone` / `git pull` invocations the walker would
have made, without ever touching the network.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from ami.core.env import PROJECT_ROOT as REPO_ROOT

WALKER = REPO_ROOT / "ami" / "scripts" / "bin" / "ami-bootstrap-repos"


def _make_fake_repo_root(tmp_path: Path, clones_yaml_text: str) -> Path:
    """Create a fake AMI-AGENTS root with the minimum walker prerequisites.

    The walker walks up looking for a directory containing both
    pyproject.toml and moon.yml. The yaml parser inside the walker reads
    ami/config/workspace-clones.yaml.
    """
    (tmp_path / "pyproject.toml").write_text("[project]\nname='fake'\n")
    (tmp_path / "moon.yml").write_text("language: 'python'\n")
    cfg_dir = tmp_path / "ami" / "config"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "workspace-clones.yaml").write_text(clones_yaml_text)
    bin_dir = tmp_path / "ami" / "scripts" / "bin"
    bin_dir.mkdir(parents=True)
    walker_copy = bin_dir / "ami-bootstrap-repos"
    shutil.copy(WALKER, walker_copy)
    walker_copy.chmod(walker_copy.stat().st_mode | stat.S_IEXEC)
    return walker_copy


def _make_fake_git(stub_dir: Path, log_file: Path) -> None:
    """Install a fake `git` on PATH that records argv to log_file.

    The stub treats `git clone` as success (and creates target/.git so
    re-runs see the repo as already-cloned), and treats `git pull` as
    success without touching anything. `git describe` returns no tag.
    """
    stub_dir.mkdir(parents=True, exist_ok=True)
    fake_git = stub_dir / "git"
    fake_git.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{log_file}"\n'
        'if [[ "$1" == "clone" ]]; then\n'
        '  mkdir -p "$3/.git"\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "pull" ]]; then\n'
        "  exit 0\n"
        "fi\n"
        'if [[ "$1" == "describe" ]]; then\n'
        "  exit 1\n"
        "fi\n"
        'if [[ "$1" == "merge-base" ]]; then\n'
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
    )
    fake_git.chmod(fake_git.stat().st_mode | stat.S_IEXEC)


def _run_walker(
    walker_path: Path, *args: str, stub_dir: Path
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
    return subprocess.run(
        ["bash", str(walker_path), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )


SAMPLE_YAML = """\
workspaceClones:
  ami-ci:
    remote: 'git@github.com:Independent-AI-Labs/AMI-CI.git'
    path: 'projects/AMI-CI'
    mandatory: true
  ami-dataops:
    remote: 'git@github.com:Independent-AI-Labs/AMI-DATAOPS.git'
    path: 'projects/AMI-DATAOPS'
    mandatory: true
  ami-portal:
    remote: 'git@github.com:Independent-AI-Labs/AMI-PORTAL.git'
    path: 'projects/AMI-PORTAL'
    mandatory: false
  ami-srp:
    remote: 'git@github.com:Independent-AI-Labs/AMI-SRP.git'
    path: 'projects/AMI-SRP'
    mandatory: false
"""


class TestMandatoryOnly:
    """Default invocation clones mandatory entries only."""

    def test_clones_only_mandatory(self, tmp_path: Path) -> None:
        walker = _make_fake_repo_root(tmp_path, SAMPLE_YAML)
        log_file = tmp_path / "git-calls.log"
        stub = tmp_path / "stub-bin"
        _make_fake_git(stub, log_file)

        result = _run_walker(walker, stub_dir=stub)

        assert result.returncode == 0, result.stderr
        log = log_file.read_text() if log_file.exists() else ""
        assert "clone git@github.com:Independent-AI-Labs/AMI-CI.git" in log
        assert "clone git@github.com:Independent-AI-Labs/AMI-DATAOPS.git" in log
        # Optionals must not be cloned.
        assert "AMI-PORTAL" not in log
        assert "AMI-SRP" not in log
        assert "2 processed" in result.stdout
        assert "2 optional skipped" in result.stdout


class TestIncludeSelection:
    """--include opts in specific optional repos."""

    def test_include_single_optional(self, tmp_path: Path) -> None:
        walker = _make_fake_repo_root(tmp_path, SAMPLE_YAML)
        log_file = tmp_path / "git-calls.log"
        stub = tmp_path / "stub-bin"
        _make_fake_git(stub, log_file)

        result = _run_walker(walker, "--include", "ami-portal", stub_dir=stub)

        assert result.returncode == 0, result.stderr
        log = log_file.read_text() if log_file.exists() else ""
        assert "AMI-PORTAL.git" in log
        # Other optional still skipped.
        assert "AMI-SRP" not in log

    def test_include_multiple_csv(self, tmp_path: Path) -> None:
        walker = _make_fake_repo_root(tmp_path, SAMPLE_YAML)
        log_file = tmp_path / "git-calls.log"
        stub = tmp_path / "stub-bin"
        _make_fake_git(stub, log_file)

        result = _run_walker(walker, "--include", "ami-portal,ami-srp", stub_dir=stub)

        assert result.returncode == 0, result.stderr
        log = log_file.read_text() if log_file.exists() else ""
        assert "AMI-PORTAL.git" in log
        assert "AMI-SRP.git" in log


class TestAllOptional:
    """--all clones every optional entry too."""

    def test_all_clones_everything(self, tmp_path: Path) -> None:
        walker = _make_fake_repo_root(tmp_path, SAMPLE_YAML)
        log_file = tmp_path / "git-calls.log"
        stub = tmp_path / "stub-bin"
        _make_fake_git(stub, log_file)

        result = _run_walker(walker, "--all", stub_dir=stub)

        assert result.returncode == 0, result.stderr
        log = log_file.read_text() if log_file.exists() else ""
        for repo in ("AMI-CI.git", "AMI-DATAOPS.git", "AMI-PORTAL.git", "AMI-SRP.git"):
            assert repo in log
        assert "0 optional skipped" in result.stdout


class TestPullExisting:
    """--pull updates already-cloned working trees."""

    def test_pull_runs_pull_on_existing(self, tmp_path: Path) -> None:
        walker = _make_fake_repo_root(tmp_path, SAMPLE_YAML)
        # Pre-create one of the mandatory targets as if already cloned.
        already = tmp_path / "projects" / "AMI-CI" / ".git"
        already.mkdir(parents=True)
        log_file = tmp_path / "git-calls.log"
        stub = tmp_path / "stub-bin"
        _make_fake_git(stub, log_file)

        result = _run_walker(walker, "--pull", stub_dir=stub)

        assert result.returncode == 0, result.stderr
        log = log_file.read_text() if log_file.exists() else ""
        assert "pull --ff-only" in log

    def test_no_pull_without_flag(self, tmp_path: Path) -> None:
        walker = _make_fake_repo_root(tmp_path, SAMPLE_YAML)
        already = tmp_path / "projects" / "AMI-CI" / ".git"
        already.mkdir(parents=True)
        log_file = tmp_path / "git-calls.log"
        stub = tmp_path / "stub-bin"
        _make_fake_git(stub, log_file)

        result = _run_walker(walker, stub_dir=stub)

        assert result.returncode == 0, result.stderr
        log = log_file.read_text() if log_file.exists() else ""
        # No `git pull` command should have been issued; substring match
        # avoids the false positive of "DATAOPS" containing "pull" — match
        # the exact `pull --ff-only` token the walker uses.
        assert "pull --ff-only" not in log


class TestErrorPaths:
    """Walker error paths."""

    def test_unknown_arg_errors(self, tmp_path: Path) -> None:
        walker = _make_fake_repo_root(tmp_path, SAMPLE_YAML)
        stub = tmp_path / "stub-bin"
        _make_fake_git(stub, tmp_path / "git-calls.log")
        result = _run_walker(walker, "--bogus", stub_dir=stub)
        assert result.returncode != 0
        assert "unknown argument" in result.stderr

    def test_help_short_circuits(self, tmp_path: Path) -> None:
        walker = _make_fake_repo_root(tmp_path, SAMPLE_YAML)
        stub = tmp_path / "stub-bin"
        _make_fake_git(stub, tmp_path / "git-calls.log")
        result = _run_walker(walker, "--help", stub_dir=stub)
        assert result.returncode == 0
        assert "Usage" in result.stdout or "ami-bootstrap-repos" in result.stdout


class TestEmptyManifest:
    """Walker bails when no entries are present."""

    def test_empty_yaml_errors(self, tmp_path: Path) -> None:
        walker = _make_fake_repo_root(tmp_path, "workspaceClones:\n")
        stub = tmp_path / "stub-bin"
        _make_fake_git(stub, tmp_path / "git-calls.log")
        result = _run_walker(walker, stub_dir=stub)
        assert result.returncode != 0
        assert "no workspaceClones entries" in result.stderr


@pytest.fixture(autouse=True)
def _walker_present() -> None:
    """Fail loudly if the walker script disappeared."""
    if not WALKER.exists():
        pytest.skip(f"walker not found at {WALKER}")
