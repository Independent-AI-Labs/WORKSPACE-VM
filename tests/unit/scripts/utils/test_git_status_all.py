"""Unit tests for workspace/scripts/utils/git-status-all vendored filtering."""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

from workspace.config_utils import PROJECT_ROOT as REPO_ROOT

STATUS_ALL = REPO_ROOT / "workspace" / "scripts" / "utils" / "git-status-all"

SAMPLE_CLONES_YAML = """\
workspaceClones:
  ci:
    remote: 'git@github.com:Independent-AI-Labs/WORKSPACE-CI.git'
    path: 'projects/CI'
    mandatory: true
  dataops:
    remote: 'git@github.com:Independent-AI-Labs/AMI-DATAOPS.git'
    path: 'projects/DATAOPS'
    mandatory: true
"""

_ANSI = re.compile(r"\033\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    return _ANSI.sub("", text)


def _make_fake_workspace(tmp_path: Path) -> tuple[Path, Path]:
    """Create a minimal workspace tree and return (script_path, workspace_root)."""
    root = tmp_path / "workspace-vm"
    utils_dir = root / "workspace" / "scripts" / "utils"
    utils_dir.mkdir(parents=True)
    script_copy = utils_dir / "git-status-all"
    shutil.copy(STATUS_ALL, script_copy)
    script_copy.chmod(script_copy.stat().st_mode | stat.S_IEXEC)

    cfg_dir = root / "workspace" / "config"
    cfg_dir.mkdir(parents=True)
    (cfg_dir / "workspace-clones.yaml").write_text(SAMPLE_CLONES_YAML)

    projects_dir = root / "projects"
    projects_dir.mkdir(parents=True)
    (projects_dir / "CI").mkdir()
    (projects_dir / "vendor-lib").mkdir()
    (root / ".git").mkdir()
    (projects_dir / "CI" / ".git").mkdir()
    (projects_dir / "vendor-lib" / ".git").mkdir()

    return script_copy, root


def _make_fake_git(stub_dir: Path, origins: dict[Path, str]) -> None:
    """Install a fake git that answers per-repo based on -C <dir>."""
    stub_dir.mkdir(parents=True, exist_ok=True)
    origins_file = stub_dir / "origins.tsv"
    lines = []
    for repo_dir, origin in origins.items():
        lines.append(f"{repo_dir.resolve()}\t{origin}")
    origins_file.write_text("\n".join(lines) + "\n")

    fake_git = stub_dir / "git"
    fake_git.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f'ORIGINS_FILE="{origins_file}"\n'
        'repo_dir="$(pwd)"\n'
        'args=("$@")\n'
        "idx=0\n"
        "while [[ $idx -lt ${#args[@]} ]]; do\n"
        '  if [[ "${args[$idx]}" == "-C" ]]; then\n'
        '    repo_dir="${args[$((idx + 1))]}"\n'
        "    idx=$((idx + 2))\n"
        "  else\n"
        "    break\n"
        "  fi\n"
        "done\n"
        'cmd="${args[$idx]:-}"\n'
        'subcmd_args=("${args[@]:$((idx + 1))}")\n'
        "lookup_origin() {\n"
        '  local dir="$1"\n'
        '  while [[ "$dir" != "/" ]]; do\n'
        "    local origin\n"
        '    origin=$(awk -F "\\t" -v d="$dir" '
        "'$1 == d { print $2; exit }' \"$ORIGINS_FILE\")\n"
        '    if [[ -n "$origin" ]]; then\n'
        '      echo "$origin"\n'
        "      return 0\n"
        "    fi\n"
        '    dir="$(dirname "$dir")"\n'
        "  done\n"
        "  return 1\n"
        "}\n"
        'case "$cmd" in\n'
        "  remote)\n"
        '    if [[ "${subcmd_args[0]:-}" == "get-url" && '
        '"${subcmd_args[1]:-}" == "origin" ]]; then\n'
        '      if origin=$(lookup_origin "$(cd "$repo_dir" && pwd)"); then\n'
        '        echo "$origin"\n'
        "        exit 0\n"
        "      fi\n"
        "      exit 1\n"
        "    fi\n"
        "    ;;\n"
        "  branch)\n"
        '    if [[ "${subcmd_args[0]:-}" == "--show-current" ]]; then\n'
        '      echo "main"\n'
        "      exit 0\n"
        "    fi\n"
        "    ;;\n"
        "  status)\n"
        '    if [[ "${subcmd_args[0]:-}" == "--porcelain" ]]; then\n'
        "      exit 0\n"
        "    fi\n"
        "    ;;\n"
        "  rev-list)\n"
        '    if [[ "${subcmd_args[0]:-}" == "--left-right" ]]; then\n'
        '      echo "0 0"\n'
        "      exit 0\n"
        "    fi\n"
        "    ;;\n"
        "esac\n"
        "exit 0\n",
    )
    fake_git.chmod(fake_git.stat().st_mode | stat.S_IEXEC)


def _run_status_all(
    script_path: Path, *args: str, stub_dir: Path
) -> subprocess.CompletedProcess[str]:
    # The shell guard scrubs PATH when staging scripts, so a stub git on
    # PATH is unreachable inside git-status-all. Install the stub as
    # `real-git` next to the copied script instead (git-status-all
    # resolves "${SCRIPT_DIR}/real-git" before using PATH).
    real_git = script_path.parent / "real-git"
    shutil.copy(stub_dir / "git", real_git)
    real_git.chmod(real_git.stat().st_mode | stat.S_IEXEC)
    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env.get('PATH', '')}"
    return subprocess.run(
        ["bash", str(script_path), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        timeout=30,
    )


class TestVendoredFiltering:
    def test_default_hides_vendored_repos(self, tmp_path: Path) -> None:
        script, root = _make_fake_workspace(tmp_path)
        stub = tmp_path / "stub-bin"
        origins = {
            root: "git@github.com:Independent-AI-Labs/WORKSPACE-VM.git",
            root / "projects" / "CI": (
                "git@github.com:Independent-AI-Labs/WORKSPACE-CI.git"
            ),
            root / "projects" / "vendor-lib": (
                "https://github.com/someone/vendor-lib.git"
            ),
        }
        _make_fake_git(stub, origins)

        result = _run_status_all(script, stub_dir=stub)
        output = _strip_ansi(result.stdout)

        assert result.returncode == 0, result.stderr
        assert "projects/CI" in output
        assert "projects/vendor-lib" not in output
        assert "1 vendored skipped" in output

    def test_all_repos_includes_vendored(self, tmp_path: Path) -> None:
        script, root = _make_fake_workspace(tmp_path)
        stub = tmp_path / "stub-bin"
        origins = {
            root: "git@github.com:Independent-AI-Labs/WORKSPACE-VM.git",
            root / "projects" / "CI": (
                "git@github.com:Independent-AI-Labs/WORKSPACE-CI.git"
            ),
            root / "projects" / "vendor-lib": (
                "https://github.com/someone/vendor-lib.git"
            ),
        }
        _make_fake_git(stub, origins)

        result = _run_status_all(script, "--all-repos", stub_dir=stub)
        output = _strip_ansi(result.stdout)

        assert result.returncode == 0, result.stderr
        assert "projects/CI" in output
        assert "projects/vendor-lib" in output
        assert "vendored skipped" not in output

    def test_help_exits_zero(self, tmp_path: Path) -> None:
        script, _root = _make_fake_workspace(tmp_path)
        stub = tmp_path / "stub-bin"
        _make_fake_git(stub, {})

        result = _run_status_all(script, "--help", stub_dir=stub)

        assert result.returncode == 0
        assert "vendored" in result.stdout.lower()
        assert "--all-repos" in result.stdout
