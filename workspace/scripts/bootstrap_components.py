"""Bootstrap component models, detection, and version checking."""

import os
import re
import shutil
import subprocess
from enum import Enum

from pydantic import BaseModel

from workspace.config_utils import PROJECT_ROOT

__all__ = [
    "PROJECT_ROOT",
    "Component",
    "ComponentStatus",
    "ComponentType",
    "GroupComponents",
]


class ComponentType(Enum):
    """Type of component installation."""

    SCRIPT = "script"
    UV = "uv"
    WORKSPACE_REPO = "workspace_repo"


class ComponentStatus(BaseModel):
    installed: bool
    version: str | None = None
    path: str | None = None


class GroupComponents(BaseModel):
    group: str
    components: list["Component"] = []


class Component(BaseModel):
    name: str
    label: str
    description: str
    type: ComponentType
    group: str

    package: str | None = None
    script: str | None = None
    script_path: str | None = None

    detect_cmd: list[str] | None = None
    detect_path: str | None = None
    version_pattern: str | None = None
    version_cmd: list[str] | None = None

    def get_status(self, env: dict[str, str] | None = None) -> ComponentStatus:
        """Check if component is installed and get version.

        When a version_cmd is declared, the version command is the ground
        truth for whether the binary is functional.  A stale symlink or
        broken install (wrong arch, missing shared libs) will fail the
        version command and be reported as not-installed instead of
        giving a false positive.

        Pass *env* to supply bootstrap environment variables (BOOT_LINUX_DIR,
        RUSTUP_HOME, etc.) that the version command may depend on.
        """
        if self.detect_path:
            path = PROJECT_ROOT / self.detect_path
            if path.exists() and self._runnable_binary_present():
                if self.version_cmd:
                    version = self._get_version_from_cmd(env=env)
                    if version is not None:
                        return ComponentStatus(
                            installed=True, version=version, path=str(path)
                        )
                    return ComponentStatus(installed=False)
                return ComponentStatus(installed=True, version=None, path=str(path))

        if self.detect_cmd:
            try:
                result = subprocess.run(
                    self.detect_cmd,
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=str(PROJECT_ROOT),
                    env=env,
                    check=True,
                )
                if result.returncode == 0:
                    version = self._extract_version(result.stdout + result.stderr)
                    return ComponentStatus(installed=True, version=version)
            except (
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
                FileNotFoundError,
                OSError,
            ):
                pass

        return ComponentStatus(installed=False)

    def _runnable_binary_present(self) -> bool:
        """Verify version_cmd's binary exists and is executable.

        For in-tree paths (relative, not starting with / or ~), checks
        against PROJECT_ROOT.  For bare command names not found in-tree,
        falls back to PATH lookup via shutil.which.
        """
        if not self.version_cmd:
            return True
        binary = self.version_cmd[0]
        if binary.startswith(("/", "~")):
            return True
        bin_path = PROJECT_ROOT / binary
        if bin_path.exists() and os.access(bin_path, os.X_OK):
            return True
        return shutil.which(binary) is not None

    def _get_version_from_cmd(self, env: dict[str, str] | None = None) -> str | None:
        """Get version using version command."""
        if not self.version_cmd:
            return None
        try:
            result = subprocess.run(
                self.version_cmd,
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(PROJECT_ROOT),
                env=env,
                check=True,
            )
            return self._extract_version(result.stdout + result.stderr)
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
            OSError,
        ):
            return None

    def _extract_version(self, output: str) -> str | None:
        """Extract version from command output."""
        if not output:
            return None

        if self.version_pattern:
            match = re.search(self.version_pattern, output)
            if match:
                return match.group(1) if match.groups() else match.group(0)

        patterns = [
            r"(\d+\.\d+\.\d+)",
            r"v(\d+\.\d+\.\d+)",
            r"(\d+\.\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                return match.group(1)

        return None
