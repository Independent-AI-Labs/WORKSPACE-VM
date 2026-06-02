"""
Bootstrap installation logic.

Handles the actual installation of components, separate from TUI.
"""

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from ami.types.results import InstallationResult

from ami.scripts.bootstrap_components import PROJECT_ROOT, Component, ComponentType


class CategorizedComponents(NamedTuple):
    """Components separated by installation order."""

    core: list[Component]
    other: list[Component]


def ensure_directories() -> None:
    """Ensure required directories exist."""
    dirs = [
        PROJECT_ROOT / ".boot-linux" / "bin",
        PROJECT_ROOT / ".venv" / "bin",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def get_bootstrap_dir() -> Path:
    """Get the bootstrap scripts directory."""
    return PROJECT_ROOT / "ami" / "scripts" / "bootstrap"


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
        # Set environment variables to fix path issues in scripts
        env = dict(os.environ)
        env["BOOT_LINUX_DIR"] = str(PROJECT_ROOT / ".boot-linux")
        env["VENV_DIR"] = str(PROJECT_ROOT / ".venv")

        # stdin=DEVNULL so bootstrap scripts that probe `[ -t 0 ]` see a
        # non-TTY and take the non-interactive code path. The TUI itself owns
        # the user's terminal — bootstrap scripts running underneath must
        # never prompt (would freeze `make install` mid-walk; INCIDENT-2026-05-08
        # gcloud "Reinstall? (y/N)" hang).
        result = subprocess.run(
            ["bash", str(script_path)],
            cwd=str(PROJECT_ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"ERROR: failed to invoke bootstrap script {script_path}: {exc}",
            file=sys.stderr,
        )
        return False
    else:
        return result.returncode == 0


def install_component(component: Component) -> bool:
    """Install a single component based on its type."""
    if component.type == ComponentType.SCRIPT:
        if not component.script:
            return False
        script_ok = run_bootstrap_script(component.script)
        # If script exited non-zero but the component is actually installed
        # (detect_path exists), treat as success. Some bootstrap scripts
        # have non-critical failures in post-install steps.
        if not script_ok and component.detect_path:
            path = PROJECT_ROOT / component.detect_path
            if path.exists() and _binary_is_runnable(component):
                return True
        return script_ok
    elif component.type == ComponentType.UV:
        # UV packages are handled by uv sync
        return True
    elif component.type == ComponentType.WORKSPACE_REPO:
        return run_workspace_repo_clone(component.name)
    return False


def run_workspace_repo_clone(entry_id: str) -> bool:
    """Invoke bootstrap-repos --include <entry_id> for a single repo.

    Mandatory entries clone unconditionally regardless of --include; the
    explicit --include is harmless and keeps the call site uniform.
    """
    script_path = PROJECT_ROOT / "ami" / "scripts" / "bin" / "bootstrap-repos"
    if not script_path.exists():
        print(
            f"ERROR: bootstrap-repos not found at {script_path}",
            file=sys.stderr,
        )
        return False
    try:
        result = subprocess.run(
            ["bash", str(script_path), "--include", entry_id],
            cwd=str(PROJECT_ROOT),
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(
            f"ERROR: failed to invoke bootstrap-repos for {entry_id}: {exc}",
            file=sys.stderr,
        )
        return False
    return result.returncode == 0


def _binary_is_runnable(component: Component) -> bool:
    """Verify the component's runnable binary exists and is executable.

    detect_path on its own is sticky — an npm package directory survives
    a partial install where bin-linking never ran (INCIDENT-2026-05-04).
    When version_cmd is declared and points at an in-tree binary, the
    detect_path success path must also require that binary to be
    executable. Returns True when no in-tree binary is declared
    (preserves prior behaviour for components that don't ship a
    version_cmd).
    """
    if not component.version_cmd:
        return True
    binary = component.version_cmd[0]
    if binary.startswith(("/", "~")):
        return True
    bin_path = PROJECT_ROOT / binary
    return bin_path.exists() and os.access(bin_path, os.X_OK)


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
