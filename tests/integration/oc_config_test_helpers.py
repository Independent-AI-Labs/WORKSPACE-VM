"""Shared process helpers for OpenCode config deployment tests."""

import json
import os
import subprocess
from pathlib import Path


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / ".git").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent


WORKSPACE_ROOT = _find_project_root()
OC_SRC = WORKSPACE_ROOT / "workspace" / "config" / "opencode"
WRAPPERS = (
    WORKSPACE_ROOT / "workspace" / "scripts" / "bin" / "oc",
    WORKSPACE_ROOT / "workspace" / "scripts" / "bin" / "ocb",
)


def _capture_binary(path: Path) -> Path:
    path.mkdir()
    binary = path / "opencode"
    binary.write_text(
        "#!/bin/bash\n"
        "set -euo pipefail\n"
        ': > "$OC_CAPTURE"\n'
        'printf "db:%s\\n" "${OPENCODE_DB-}" >> "$OC_CAPTURE"\n'
        'printf "config:%s\\n" "$OPENCODE_CONFIG_DIR" >> "$OC_CAPTURE"\n'
        'printf "content:%s\\n" "$OPENCODE_CONFIG_CONTENT" >> "$OC_CAPTURE"\n'
        'for arg in "$@"; do printf "arg:%s\\n" "$arg" >> "$OC_CAPTURE"; done\n',
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def run_wrapper_result(
    tmp_path: Path,
    wrapper: Path,
    args: list[str],
    config_dir: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    name = wrapper.name
    home = tmp_path / f"home-{name}"
    xdg_config = tmp_path / f"xdg-config-{name}"
    data = tmp_path / f"xdg-data-{name}"
    caller = tmp_path / f"caller-{name}"
    for directory in (home, xdg_config, data, caller):
        directory.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg_config),
        "XDG_DATA_HOME": str(data),
        "OPENCODE_BINARY": str(_capture_binary(tmp_path / f"bin-{name}")),
        "OC_CAPTURE": str(tmp_path / f"capture-{name}"),
    }
    env.pop("OPENCODE_CONFIG_DIR", None)
    env.pop("OPENCODE_DB", None)
    if config_dir is not None:
        env["OPENCODE_CONFIG_DIR"] = str(config_dir)
    if extra_env is not None:
        env.update(extra_env)
    return subprocess.run(
        [str(wrapper), *args],
        cwd=caller,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def run_wrapper(
    tmp_path: Path,
    wrapper: Path,
    args: list[str],
    config_dir: Path | None = None,
    extra_env: dict[str, str] | None = None,
) -> tuple[dict[str, str], list[str], Path]:
    result = run_wrapper_result(tmp_path, wrapper, args, config_dir, extra_env)
    assert result.returncode == 0, result.stderr
    name = wrapper.name
    capture = tmp_path / f"capture-{name}"
    lines = capture.read_text(encoding="utf-8").splitlines()
    values = dict(line.split(":", 1) for line in lines[:3])
    return (
        values,
        [line.split(":", 1)[1] for line in lines[3:]],
        tmp_path / f"home-{name}",
    )


def configured_instruction_files(config_dir: Path) -> list[Path]:
    """Resolve config-relative instruction paths as OpenCode does."""
    config = json.loads((config_dir / "opencode.jsonc").read_text(encoding="utf-8"))
    return [
        (config_dir / instruction.removeprefix("./")).resolve()
        for instruction in config["instructions"]
    ]
