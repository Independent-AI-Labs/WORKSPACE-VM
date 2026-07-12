"""Host isolation checks: guest operations must not mutate host /usr/bin/git."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_HOST_GIT = Path("/usr/bin/git")
_HOST_GIT_ORIGINAL = Path("/usr/bin/git.original")


class HostGitFingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    git_exists: bool
    git_sha256: str
    git_mode: int | None
    original_exists: bool


def snapshot_host_git() -> HostGitFingerprint:
    """Capture host git binary state before/after QEMU guard E2E."""
    if not _HOST_GIT.is_file():
        return HostGitFingerprint(
            git_exists=False,
            git_sha256="",
            git_mode=None,
            original_exists=_HOST_GIT_ORIGINAL.exists(),
        )
    digest = hashlib.sha256()
    with _HOST_GIT.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    mode = stat.S_IMODE(_HOST_GIT.stat().st_mode)
    return HostGitFingerprint(
        git_exists=True,
        git_sha256=digest.hexdigest(),
        git_mode=mode,
        original_exists=_HOST_GIT_ORIGINAL.exists(),
    )


def assert_host_git_unchanged(
    before: HostGitFingerprint, after: HostGitFingerprint
) -> None:
    assert before == after, (
        "host /usr/bin/git changed after QEMU guest E2E\n"
        f"  before: {before}\n"
        f"  after:  {after}"
    )
