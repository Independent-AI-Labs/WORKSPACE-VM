"""Host isolation checks: guest operations must not mutate host binaries."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_HOST_GIT = Path("/usr/bin/git")
_HOST_GIT_ORIGINAL = Path("/usr/bin/git.original")
_HOST_BASH = Path("/usr/bin/bash")
_HOST_BASH_REAL = Path("/usr/bin/bash.real")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class HostGitFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    git_exists: bool
    git_sha256: str
    git_mode: int | None
    original_exists: bool
    bash_exists: bool
    bash_sha256: str
    bash_mode: int | None
    bash_real_exists: bool


def snapshot_host_git() -> HostGitFingerprint:
    """Capture host git and bash binary state before/after QEMU guard E2E."""
    git_exists = _HOST_GIT.is_file()
    bash_exists = _HOST_BASH.is_file()
    return HostGitFingerprint(
        git_exists=git_exists,
        git_sha256=_sha256(_HOST_GIT) if git_exists else "",
        git_mode=stat.S_IMODE(_HOST_GIT.stat().st_mode) if git_exists else None,
        original_exists=_HOST_GIT_ORIGINAL.exists(),
        bash_exists=bash_exists,
        bash_sha256=_sha256(_HOST_BASH) if bash_exists else "",
        bash_mode=stat.S_IMODE(_HOST_BASH.stat().st_mode) if bash_exists else None,
        bash_real_exists=_HOST_BASH_REAL.exists(),
    )


def assert_host_git_unchanged(
    before: HostGitFingerprint, after: HostGitFingerprint
) -> None:
    assert before == after, (
        "host /usr/bin/git or /usr/bin/bash changed after QEMU guest E2E\n"
        f"  before: {before}\n"
        f"  after:  {after}"
    )
