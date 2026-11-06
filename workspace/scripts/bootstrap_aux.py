"""Auxiliary installer execution helpers.

Runs fixed handlers for features declared in workspace/config/install-aux.yaml.
See docs/specifications/SPEC-INSTALLER.md.
"""

from __future__ import annotations

import os
import pwd
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from workspace.config_utils import PROJECT_ROOT
from workspace.scripts.bootstrap_aux_defs import AuxFeature

DATAOPS_DIR = PROJECT_ROOT / "projects" / "WORKSPACE-DATAOPS"


class AuxResult:
    def __init__(self, feature_id: str, success: bool, message: str) -> None:
        self.feature_id = feature_id
        self.success = success
        self.message = message


def _feature_args(feature: AuxFeature, values: dict[str, str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for name, spec in feature.args.items():
        resolved[name] = values.get(name, spec.default)
    return resolved


def _detect_path(feature: AuxFeature) -> bool:
    if not feature.detect_path:
        return False
    path = Path(feature.detect_path).expanduser()
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.exists()


def _detect_mount(feature: AuxFeature) -> bool:
    mount = feature.detect_mount
    return mount is not None and os.path.ismount(mount)


def _detect_command(feature: AuxFeature) -> bool:
    if not feature.detect_cmd:
        return False
    try:
        subprocess.run(
            feature.detect_cmd,
            cwd=str(PROJECT_ROOT),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        message = detail or f"{feature.label} detect failed rc={exc.returncode}\n"
        sys.stderr.write(message)
        return False
    return True


def detect_configured(feature: AuxFeature) -> bool:
    """Return whether a file, mount, or command proves configuration."""
    return _detect_path(feature) or _detect_mount(feature) or _detect_command(feature)


def _storage_configure(args: dict[str, str]) -> list[list[str]]:
    script = DATAOPS_DIR / "scripts" / "storage" / "write-storage-locations.sh"
    return [["bash", str(script), "--fast", args["fast"], "--backup", args["backup"]]]


def _storage_mount(args: dict[str, str]) -> list[list[str]]:
    return [["make", "-C", str(DATAOPS_DIR), "storage-mount", "NAME=ws-backup"]]


def _storage_persist(args: dict[str, str]) -> list[list[str]]:
    return [["make", "-C", str(DATAOPS_DIR), "storage-persist", "NAME=ws-backup"]]


def _storage_provision(args: dict[str, str]) -> list[list[str]]:
    return [
        ["make", "-C", str(DATAOPS_DIR), "storage-provision", "DRY_RUN=1"],
        ["make", "-C", str(DATAOPS_DIR), "storage-provision"],
    ]


def _storage_migrate(args: dict[str, str]) -> list[list[str]]:
    return [["make", "-C", str(DATAOPS_DIR), "storage-migrate"]]


def _install_diagnostics(args: dict[str, str]) -> list[list[str]]:
    return [["make", "install-diagnostics"]]


def _install_agentci(args: dict[str, str]) -> list[list[str]]:
    return [
        ["make", "install-agentci"],
        ["make", "verify-agentci"],
        ["make", "install-moderator"],
        ["make", "verify-moderator"],
    ]


def _dataops_profiles(args: dict[str, str]) -> list[list[str]]:
    return [
        [
            "make",
            "-C",
            str(DATAOPS_DIR),
            "runtime-up",
            f"PROFILES={args['profiles']}",
        ]
    ]


_HANDLERS: dict[str, Callable[[dict[str, str]], list[list[str]]]] = {
    "storage-configure": _storage_configure,
    "storage-mount-backup": _storage_mount,
    "storage-persist-backup": _storage_persist,
    "storage-provision-fast": _storage_provision,
    "storage-migrate": _storage_migrate,
    "install-diagnostics": _install_diagnostics,
    "install-agentci": _install_agentci,
    "dataops-profiles": _dataops_profiles,
}


def build_commands(feature: AuxFeature, values: dict[str, str]) -> list[list[str]]:
    """Build the fixed command sequence for a feature."""
    handler = _HANDLERS.get(feature.action)
    if handler is None:
        msg = f"unknown auxiliary action: {feature.action}"
        raise ValueError(msg)
    return handler(_feature_args(feature, values))


def _owner_home(user: str) -> str:
    try:
        return pwd.getpwnam(user).pw_dir
    except KeyError as exc:
        msg = f"SUDO_USER does not resolve: {user}"
        raise ValueError(msg) from exc


def _wrap_as_owner(command: list[str]) -> list[str]:
    user = os.environ.get("SUDO_USER", "")
    if not user or user == "root":
        msg = "agent auxiliary action requires SUDO_USER when run as root"
        raise ValueError(msg)
    home = _owner_home(user)
    env = [f"HOME={home}", f"USER={user}", f"LOGNAME={user}"]
    return ["runuser", "-u", user, "--", "env", *env, *command]


def run_feature(
    feature: AuxFeature,
    values: dict[str, str],
    effective_uid: int | None = None,
) -> AuxResult:
    """Run one feature and return its result without raising on failure."""
    uid = os.geteuid() if effective_uid is None else effective_uid
    commands = build_commands(feature, values)

    if feature.scope == "root" and uid != 0:
        return AuxResult(
            feature.id,
            False,
            f"root action skipped outside sudo make init: {feature.label}",
        )
    if feature.scope == "agent" and uid == 0:
        commands = [_wrap_as_owner(command) for command in commands]

    for command in commands:
        failure = _run_one(feature, command)
        if failure is not None:
            return failure
    return AuxResult(feature.id, True, f"{feature.label} complete")


def _run_one(feature: AuxFeature, command: list[str]) -> AuxResult | None:
    try:
        subprocess.run(command, cwd=str(PROJECT_ROOT), check=True)
    except subprocess.CalledProcessError as exc:
        text = f"{feature.label} failed (rc={exc.returncode})"
        return AuxResult(feature.id, False, text)
    except OSError as exc:
        return AuxResult(feature.id, False, f"{feature.label}: {exc}")
    return None


def run_selected(
    features: list[AuxFeature],
    values_by_id: dict[str, dict[str, str]],
    effective_uid: int | None = None,
) -> list[AuxResult]:
    """Run features in order and stop at the first failure."""
    results: list[AuxResult] = []
    for feature in features:
        result = run_feature(
            feature,
            values_by_id.get(feature.id, {}),
            effective_uid=effective_uid,
        )
        results.append(result)
        if not result.success:
            print(f"ERROR: {result.message}", file=sys.stderr)
            break
    return results
