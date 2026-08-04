"""
Create symlinks and wrappers in the platform-appropriate boot dir for all extensions.

Uses manifest discovery from extension_registry (extension.manifest.yaml
files). Bashrc writing is handled by shell-setup, not here.
"""

from __future__ import annotations

import grp
import os
import platform
import pwd
import re
import stat
import sys
from pathlib import Path

from workspace.scripts.shell.extension_registry import (
    ResolvedExtension,
    Status,
    discover_manifests,
    find_ami_root,
    resolve_extensions,
)
from workspace.scripts.shell.version_enforcer import enforce_versions


def _maybe_chown(path: Path) -> None:
    """If running under sudo, chown path back to SUDO_USER so future
    agent-uid runs can refresh it without sudo. No-op when not under sudo.
    Surfaces chown errors to stderr without aborting registration."""
    sudo_user = os.environ.get("SUDO_USER")
    if not sudo_user:
        return
    try:
        pw = pwd.getpwnam(sudo_user)
        gr = grp.getgrgid(pw.pw_gid)
    except KeyError:
        sys.stderr.write(
            f"Warning: SUDO_USER={sudo_user!r} not found, skipping chown\n"
        )
        return
    try:
        os.chown(path, pw.pw_uid, gr.gr_gid, follow_symlinks=False)
    except OSError as exc:
        sys.stderr.write(f"Warning: chown {path} to {sudo_user} failed: {exc}\n")


def create_wrapper(path: Path, ami_root: Path, script: str) -> None:
    """Create wrapper script that calls run with the script."""
    wrapper = f"""#!/usr/bin/env bash
exec "{ami_root}/workspace/scripts/bin/run" "{ami_root}/{script}" "$@"
"""
    path.unlink(missing_ok=True)
    path.write_text(wrapper)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    _maybe_chown(path)


def fix_stale_shebang(binary: Path, ami_root: Path) -> None:
    """Fix stale shebangs in pip-installed entry points (e.g. matrix-commander, synadm).

    When the project moves to a new directory, pip-installed console_scripts retain
    shebangs pointing to the old venv path. This rewrites them to use the current venv.
    Also fixes wrapper scripts that reference old Python paths.
    """
    if not binary.exists() or not binary.is_file():
        return

    try:
        content = binary.read_text()
    except (OSError, UnicodeDecodeError):
        sys.stderr.write(f"Warning: cannot read {binary.name}, skipping shebang fix\n")
        return

    correct_python = str(ami_root / ".venv" / "bin" / "python3")
    correct_python_no3 = str(ami_root / ".venv" / "bin" / "python")
    stale = False

    lines = content.split("\n")

    # Fix shebang (line 0)
    if lines[0].startswith("#!") and "/python" in lines[0]:
        shebang_path = lines[0][2:].strip()
        if not Path(shebang_path).exists():
            lines[0] = f"#!{correct_python}"
            stale = True

    # Fix inline python paths in bash wrappers (e.g. ami-synadm)
    for i in range(1, len(lines)):
        if "/python" in lines[i]:
            new_line = re.sub(
                r'"[^"]*?/python3?"',
                f'"{correct_python_no3}"',
                lines[i],
            )
            if new_line != lines[i]:
                lines[i] = new_line
                stale = True

    if stale:
        binary.write_text("\n".join(lines))
        print(f"  \u2713 Fixed stale shebang in {binary.name}")


def create_symlink(link: Path, target: Path) -> None:
    """Create symlink, removing existing if present."""
    link.unlink(missing_ok=True)
    link.symlink_to(target)
    _maybe_chown(link)


def _register_one(ext: ResolvedExtension, bin_dir: Path, ami_root: Path) -> None:
    """Register a single resolved extension into bin_dir."""
    entry = ext.entry
    name = entry["name"]
    binary = entry["binary"]
    target_path = bin_dir / name
    source_path = ami_root / binary

    if source_path == target_path:
        print(f"  \u2713 {name} \u2192 {binary} (self, skip)")
        return

    if binary.endswith(".py"):
        create_wrapper(target_path, ami_root, binary)
        print(f"  \u2713 {name} \u2192 wrapper({binary})")
    else:
        fix_stale_shebang(source_path, ami_root)
        create_symlink(target_path, source_path)
        print(f"  \u2713 {name} \u2192 {binary}")


def register_extensions() -> None:
    """Register all extensions as symlinks/wrappers in the boot dir."""
    ami_root = find_ami_root()
    boot_name = ".boot-macos" if platform.system() == "Darwin" else ".boot-linux"
    bin_dir = ami_root / boot_name / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    _maybe_chown(bin_dir)

    manifests = discover_manifests(ami_root)
    if not manifests:
        print("[WARN] No extension.manifest.yaml files found.")
        return

    resolved = enforce_versions(resolve_extensions(manifests, ami_root), ami_root)

    print("\U0001f517 Creating extension symlinks/wrappers...")

    registered = 0
    skipped_unavailable = 0
    skipped_mismatch = 0
    for ext in resolved:
        if ext.status == Status.UNAVAILABLE:
            skipped_unavailable += 1
            continue
        if ext.status == Status.VERSION_MISMATCH:
            name = ext.entry["name"]
            print(f"  \u26a0 {name} skipped: {ext.reason}")
            skipped_mismatch += 1
            continue
        _register_one(ext, bin_dir, ami_root)
        registered += 1

    print(f"\n\u2705 Registered {registered} commands in {bin_dir}")
    if skipped_unavailable:
        print(f"   Skipped {skipped_unavailable} unavailable extensions")
    if skipped_mismatch:
        print(f"   Skipped {skipped_mismatch} version-mismatched extensions")


if __name__ == "__main__":
    register_extensions()
