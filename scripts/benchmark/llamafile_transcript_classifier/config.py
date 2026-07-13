"""Load benchmark config and resolve repository root."""

from __future__ import annotations

from pathlib import Path

import yaml

from scripts.benchmark.llamafile_transcript_classifier.types import JsonMap

REPO_ROOT_MARKER = "pyproject.toml"
CONFIG_FILENAME = "benchmark.yaml"
CONFIG_PARENT_DIRNAME = "transcript_classifier"


def find_repo_root(start: Path) -> Path:
    """Walk parents from start until pyproject.toml is found."""
    current = start.resolve()
    for directory in (current, *current.parents):
        if (directory / REPO_ROOT_MARKER).is_file():
            return directory
    msg = f"repository root not found (no {REPO_ROOT_MARKER}) from {start}"
    raise FileNotFoundError(msg)


def discover_config_path(repo_root: Path) -> Path:
    """Locate the single transcript_classifier config.yaml under benchmarks/."""
    matches = sorted(
        repo_root.glob(f"benchmarks/**/{CONFIG_PARENT_DIRNAME}/{CONFIG_FILENAME}")
    )
    if not matches:
        msg = (
            f"no {CONFIG_FILENAME} under benchmarks/**/{CONFIG_PARENT_DIRNAME}/ "
            f"in {repo_root}"
        )
        raise FileNotFoundError(msg)
    if len(matches) > 1:
        listed = ", ".join(str(p.relative_to(repo_root)) for p in matches)
        msg = f"multiple transcript classifier configs found: {listed}"
        raise RuntimeError(msg)
    return matches[0]


def load_config(config_path: Path) -> JsonMap:
    """Parse YAML config and resolve repo_root when set to auto."""
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"config must be a mapping: {config_path}"
        raise TypeError(msg)

    repo_root_value = raw.get("repo_root", "auto")
    if repo_root_value == "auto":
        raw["repo_root"] = str(find_repo_root(config_path.parent))
    else:
        raw["repo_root"] = str(Path(str(repo_root_value)).resolve())

    raw["_config_path"] = str(config_path.resolve())
    return raw


def resolve_config_path(explicit: Path | None) -> Path:
    """Return explicit config path or discover it from the repository."""
    if explicit is not None:
        path = explicit.resolve()
        if not path.is_file():
            msg = f"config not found: {path}"
            raise FileNotFoundError(msg)
        return path
    repo_root = find_repo_root(Path.cwd())
    return discover_config_path(repo_root)
