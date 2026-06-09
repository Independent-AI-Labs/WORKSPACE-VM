"""
Bootstrap installation logic.

Handles the actual installation of components, separate from TUI.
"""

import os
import subprocess
import sys
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import NamedTuple

from workspace.scripts.bootstrap_components import (
    PROJECT_ROOT as _config_root,
)
from workspace.scripts.bootstrap_components import (
    Component,
    ComponentType,
)
from workspace.types.results import InstallationResult

_PROJECT_ROOT = Path(os.environ.get("AMI_ROOT", str(_config_root)))


class CategorizedComponents(NamedTuple):
    """Components separated by installation order."""

    core: list[Component]
    other: list[Component]


def ensure_directories() -> None:
    """Ensure required directories exist."""
    dirs = [
        _PROJECT_ROOT / ".boot-linux" / "bin",
        _PROJECT_ROOT / ".venv" / "bin",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def get_bootstrap_dir() -> Path:
    """Get the bootstrap scripts directory."""
    return _PROJECT_ROOT / "workspace" / "scripts" / "bootstrap"


def get_bootstrap_env() -> dict[str, str]:
    """Return environment dict for bootstrap operations.

    Mirrors what bootstrap shell scripts receive: BOOT_LINUX_DIR,
    VENV_DIR, .boot-linux/bin on PATH, and RUSTUP_HOME/CARGO_HOME
    when the hermetic rust toolchain is present.
    """
    env = dict(os.environ)
    boot_dir = str(_PROJECT_ROOT / ".boot-linux")
    env["BOOT_LINUX_DIR"] = boot_dir
    env["VENV_DIR"] = str(_PROJECT_ROOT / ".venv")
    boot_bin = str(_PROJECT_ROOT / ".boot-linux" / "bin")
    env["PATH"] = f"{boot_bin}:{env.get('PATH', '')}"
    rust_home = str(_PROJECT_ROOT / ".boot-linux" / "rust")
    if Path(rust_home).is_dir():
        env.setdefault("RUSTUP_HOME", rust_home)
        env.setdefault("CARGO_HOME", rust_home)
    return env


def run_bootstrap_script(script_name: str) -> bool:
    """Run a single bootstrap script."""
    script_path = get_bootstrap_dir() / script_name
    if not script_path.exists():
        print(
            f"ERROR: bootstrap script not found: {script_path}",
            file=sys.stderr,
        )
        return False

    try:
        env = get_bootstrap_env()

        # stdin=DEVNULL so bootstrap scripts that probe `[ -t 0 ]` see a
        # non-TTY and take the non-interactive code path. The TUI itself owns
        # the user's terminal — bootstrap scripts running underneath must
        # never prompt (would freeze `make install` mid-walk; INCIDENT-2026-05-08
        # gcloud "Reinstall? (y/N)" hang).
        subprocess.run(
            ["bash", str(script_path)],
            cwd=str(_PROJECT_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.SubprocessError, subprocess.CalledProcessError) as exc:
        print(
            f"ERROR: failed to invoke bootstrap script {script_path}: {exc}",
            file=sys.stderr,
        )
        return False
    else:
        return True


def install_component(component: Component) -> bool:
    """Install a single component based on its type."""
    match component.type:
        case ComponentType.SCRIPT:
            if component.script_path:
                return _run_script_path(component.script_path)
            if component.script:
                return run_bootstrap_script(component.script)
            return False
        case ComponentType.UV:
            return True
        case ComponentType.WORKSPACE_REPO:
            _pull_workspace_repo(component)
            return True


def _run_script_path(script_rel: str) -> bool:
    script_path = _PROJECT_ROOT / script_rel
    if not script_path.exists():
        print(
            f"ERROR: bootstrap script not found: {script_path}",
            file=sys.stderr,
        )
        return False
    try:
        env = get_bootstrap_env()
        subprocess.run(
            ["bash", str(script_path)],
            cwd=str(_PROJECT_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            check=True,
        )
    except (OSError, subprocess.SubprocessError, subprocess.CalledProcessError) as exc:
        print(
            f"ERROR: failed to invoke {script_rel}: {exc}",
            file=sys.stderr,
        )
        return False
    return True


def _pull_workspace_repo(component: Component) -> None:
    repo_path = _PROJECT_ROOT / component.detect_path if component.detect_path else None
    if repo_path is None:
        return
    if (repo_path / ".git").exists():
        with suppress(subprocess.CalledProcessError):
            subprocess.run(
                ["git", "pull", "--ff-only"],
                cwd=repo_path,
                stdin=subprocess.DEVNULL,
                check=True,
            )
        return
    try:
        subprocess.run(
            [
                "bash",
                str(
                    _PROJECT_ROOT / "workspace" / "scripts" / "bin" / "bootstrap-repos"
                ),
                "--include",
                component.name,
            ],
            cwd=str(_PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"ERROR: bootstrap-repos failed for {component.name}: {exc}",
            file=sys.stderr,
        )


def _categorize_components(components: list[Component]) -> CategorizedComponents:
    """Separate components into core and other categories."""
    core = [c for c in components if c.group == "Core Dependencies"]
    other = [c for c in components if c not in core]
    return CategorizedComponents(core=core, other=other)


def _make_result(name: str, success: bool) -> InstallationResult:
    """Create an InstallationResult with keyword arguments."""
    return InstallationResult(component_name=name, success=success, error=None)


def _install_core_deps(cat: CategorizedComponents, ctx: "_InstallContext") -> int:
    """Install core dependencies. Returns next index."""
    for comp in cat.core:
        ctx.idx += 1
        if ctx.on_progress:
            ctx.on_progress(ctx.idx, ctx.total, f"Core: {comp.label}")
        success = install_component(comp)
        ctx.results.append(_make_result(comp.name, success))
        if ctx.on_result:
            ctx.on_result(comp, success)
    return ctx.idx


def _install_other_components(
    cat: CategorizedComponents, ctx: "_InstallContext"
) -> None:
    """Install remaining components."""
    for comp in cat.other:
        ctx.idx += 1
        if ctx.on_progress:
            ctx.on_progress(ctx.idx, ctx.total, comp.label)
        success = install_component(comp)
        ctx.results.append(_make_result(comp.name, success))
        if ctx.on_result:
            ctx.on_result(comp, success)


class _InstallContext:
    """Mutable context for installation process."""

    def __init__(
        self,
        total: int,
        on_progress: Callable[[int, int, str], None] | None,
        on_result: Callable[[Component, bool], None] | None,
    ) -> None:
        self.total = total
        self.on_progress = on_progress
        self.on_result = on_result
        self.results: list[InstallationResult] = []
        self.idx = 0


def install_components(
    components: list[Component],
    on_progress: Callable[[int, int, str], None] | None = None,
    on_result: Callable[[Component, bool], None] | None = None,
) -> list[InstallationResult]:
    """Install components in order: core deps, others."""
    ensure_directories()
    cat = _categorize_components(components)
    ctx = _InstallContext(len(components), on_progress, on_result)

    _install_core_deps(cat, ctx)
    _install_other_components(cat, ctx)

    return ctx.results
