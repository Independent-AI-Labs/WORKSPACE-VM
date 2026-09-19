"""Tests for workspace/scripts/opencode-wrapper.sh DB sharding."""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from pathlib import Path

import pytest

WRAPPER_SH = (
    Path(__file__).resolve().parents[3]
    / "workspace"
    / "scripts"
    / "opencode-wrapper.sh"
)

FAKE_EXIT_USAGE = 2


def _make_fake_opencode(tmp_path: Path) -> Path:
    fake = tmp_path / "fake-opencode"
    fake.write_text('#!/bin/bash\nprintf "DB=%s\\n" "${OPENCODE_DB:-UNSET}"\n')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return fake


def _run_dispatch(
    tmp_path: Path, cwd: Path, *args: str, env: dict[str, str] | None = None
) -> str:
    fake = _make_fake_opencode(tmp_path)
    run_env = os.environ.copy()
    run_env.pop("OPENCODE_DB", None)
    run_env["XDG_DATA_HOME"] = str(tmp_path / "xdg-data")
    if env:
        run_env.update(env)
    script = (
        f'source "{WRAPPER_SH}" || exit 1\noc_wrapper_dispatch "{fake}" "{cwd}" "$@"\n'
    )
    return subprocess.check_output(
        ["bash", "-c", script, "dispatch", *args],
        stderr=subprocess.STDOUT,
        text=True,
        cwd=cwd,
        env=run_env,
    )


def _make_git_repo(tmp_path: Path, name: str) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.check_output(["git", "init"], cwd=repo, stderr=subprocess.STDOUT)
    return repo


def _expected_shard(repo: Path) -> str:
    digest = hashlib.sha256(str(repo).encode()).hexdigest()[:16]
    return f"shard-{digest}.db"


def test_auto_shard_derived_per_git_root(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path, "repo-a")
    assert f"DB={_expected_shard(repo)}" in _run_dispatch(tmp_path, repo)


def test_two_repos_get_distinct_shards(tmp_path: Path) -> None:
    repo_a = _make_git_repo(tmp_path, "repo-a")
    repo_b = _make_git_repo(tmp_path, "repo-b")
    out_a = _run_dispatch(tmp_path, repo_a)
    out_b = _run_dispatch(tmp_path, repo_b)
    assert _expected_shard(repo_a) in out_a
    assert _expected_shard(repo_b) in out_b
    assert out_a != out_b


def test_shard_registry_records_git_root(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path, "repo-a")
    _run_dispatch(tmp_path, repo)
    registry = tmp_path / "xdg-data" / "opencode" / "shards.tsv"
    lines = registry.read_text().splitlines()
    digest = hashlib.sha256(str(repo).encode()).hexdigest()[:16]
    assert any(line == f"{digest}\t{repo}" for line in lines)


def test_db_flag_overrides_auto_shard(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path, "repo-a")
    assert "DB=custom.db" in _run_dispatch(tmp_path, repo, "--db", "custom.db")


def test_preset_env_is_respected(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path, "repo-a")
    out = _run_dispatch(tmp_path, repo, env={"OPENCODE_DB": "preset.db"})
    assert "DB=preset.db" in out


def test_mono_forces_monolith(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path, "repo-a")
    assert "DB=UNSET" in _run_dispatch(tmp_path, repo, "--mono")


def test_mono_wins_over_preset_env(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path, "repo-a")
    out = _run_dispatch(tmp_path, repo, "--mono", env={"OPENCODE_DB": "preset.db"})
    assert "DB=UNSET" in out


def test_mono_and_db_conflict_rejected(tmp_path: Path) -> None:
    repo = _make_git_repo(tmp_path, "repo-a")
    with pytest.raises(subprocess.CalledProcessError) as excinfo:
        _run_dispatch(tmp_path, repo, "--mono", "--db", "custom.db")
    assert excinfo.value.returncode == FAKE_EXIT_USAGE
    assert "mutually exclusive" in excinfo.value.output


def _seed_shard_with_session(data_home: Path, shard_name: str, session_id: str) -> None:
    db = data_home / "opencode" / shard_name
    db.parent.mkdir(parents=True, exist_ok=True)
    sql = (
        "CREATE TABLE session (id TEXT PRIMARY KEY); "
        f"INSERT INTO session VALUES('{session_id}');"
    )
    subprocess.check_output(
        ["sqlite3", str(db), sql],
        stderr=subprocess.STDOUT,
    )


def test_cross_repo_session_resume_targets_owning_shard(tmp_path: Path) -> None:
    repo_a = _make_git_repo(tmp_path, "repo-a")
    repo_b = _make_git_repo(tmp_path, "repo-b")
    _seed_shard_with_session(
        tmp_path / "xdg-data", _expected_shard(repo_a), "ses_crossdb123"
    )
    out = _run_dispatch(tmp_path, repo_b, "-s", "ses_crossdb123")
    assert f"DB={_expected_shard(repo_a)}" in out


def test_mono_ignores_session_resolver(tmp_path: Path) -> None:
    repo_a = _make_git_repo(tmp_path, "repo-a")
    repo_b = _make_git_repo(tmp_path, "repo-b")
    _seed_shard_with_session(
        tmp_path / "xdg-data", _expected_shard(repo_a), "ses_crossdb123"
    )
    out = _run_dispatch(tmp_path, repo_b, "--mono", "-s", "ses_crossdb123")
    assert "DB=UNSET" in out


def test_unknown_session_id_falls_through_to_shard(tmp_path: Path) -> None:
    repo_a = _make_git_repo(tmp_path, "repo-a")
    out = _run_dispatch(tmp_path, repo_a, "-s", "ses_doesnotexist")
    assert f"DB={_expected_shard(repo_a)}" in out


def test_non_git_directory_passthrough(tmp_path: Path) -> None:
    plain = tmp_path / "plain-dir"
    plain.mkdir()
    assert "DB=UNSET" in _run_dispatch(tmp_path, plain)
