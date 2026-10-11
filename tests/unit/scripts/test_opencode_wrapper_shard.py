"""Tests for workspace/scripts/opencode-wrapper.sh DB sharding."""

from __future__ import annotations

import hashlib
import os
import sqlite3
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

FIXTURES = Path(__file__).resolve().parent / "fixtures"

FAKE_EXIT_USAGE = 2


def _read_sql(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


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
    schema = (FIXTURES / "session_schema.sql").read_text(encoding="utf-8")
    insert = (FIXTURES / "session_insert.sql").read_text(encoding="utf-8")
    with sqlite3.connect(db) as conn:
        conn.executescript(schema)
        conn.execute(insert, {"sid": session_id})
        conn.commit()


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


def _git(repo: Path, *args: str, env: dict[str, str] | None = None) -> None:
    subprocess.check_output(["git", *args], cwd=repo, stderr=subprocess.STDOUT, env=env)


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.com",
        }
    )
    return env


def _make_repo_with_remote(tmp_path: Path, name: str, remote: str) -> Path:
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init")
    (repo / "file.txt").write_text("x", encoding="utf-8")
    _git(repo, "add", "file.txt")
    _git(repo, "commit", "-m", "root", env=_git_env())
    _git(repo, "remote", "add", "origin", remote)
    return repo


def _seed_reconcile_shard(
    data_home: Path,
    shard_name: str,
    worktree: str,
    stale_id: str,
    canonical_id: str,
) -> Path:
    db = data_home / "opencode" / shard_name
    db.parent.mkdir(parents=True, exist_ok=True)
    schema = _read_sql("project_reconcile_schema.sql")
    project_insert = _read_sql("reconcile_project_insert.sql")
    session_insert = _read_sql("reconcile_session_insert.sql")
    with sqlite3.connect(db) as conn:
        conn.executescript(schema)
        for pid in (stale_id, canonical_id):
            conn.execute(project_insert, {"pid": pid, "worktree": worktree})
        conn.execute(
            session_insert,
            {"sid": "ses_stale1", "pid": stale_id, "directory": worktree},
        )
        conn.execute(
            session_insert,
            {"sid": "ses_canon1", "pid": canonical_id, "directory": worktree},
        )
        conn.execute(
            session_insert,
            {"sid": "ses_other", "pid": "otherproj", "directory": "/elsewhere"},
        )
        conn.commit()
    return db


def test_reconcile_unifies_project_ids_for_git_root(tmp_path: Path) -> None:
    remote = "git@github.com:Modded-Software/Procedural-Worlds.git"
    repo = _make_repo_with_remote(tmp_path, "repo-a", remote)
    root_commit = (
        subprocess.check_output(
            ["git", "rev-list", "--max-parents=0", "HEAD"], cwd=repo, text=True
        )
        .strip()
        .splitlines()[0]
    )
    canonical = hashlib.sha1(
        b"git-remote:github.com/Modded-Software/Procedural-Worlds"
    ).hexdigest()
    assert canonical != root_commit
    db = _seed_reconcile_shard(
        tmp_path / "xdg-data", _expected_shard(repo), str(repo), root_commit, canonical
    )

    _run_dispatch(tmp_path, repo)

    with sqlite3.connect(db) as conn:
        projects = conn.execute(
            _read_sql("reconcile_project_ids.sql"), {"worktree": str(repo)}
        ).fetchall()
        assert projects == [(canonical,)]
        sessions = dict(conn.execute(_read_sql("reconcile_session_all.sql")).fetchall())
    assert sessions["ses_stale1"] == canonical
    assert sessions["ses_canon1"] == canonical
    assert sessions["ses_other"] == "otherproj"


def test_reconcile_is_idempotent(tmp_path: Path) -> None:
    remote = "git@github.com:Modded-Software/Procedural-Worlds.git"
    repo = _make_repo_with_remote(tmp_path, "repo-a", remote)
    root_commit = (
        subprocess.check_output(
            ["git", "rev-list", "--max-parents=0", "HEAD"], cwd=repo, text=True
        )
        .strip()
        .splitlines()[0]
    )
    canonical = hashlib.sha1(
        b"git-remote:github.com/Modded-Software/Procedural-Worlds"
    ).hexdigest()
    db = _seed_reconcile_shard(
        tmp_path / "xdg-data", _expected_shard(repo), str(repo), root_commit, canonical
    )

    _run_dispatch(tmp_path, repo)
    _run_dispatch(tmp_path, repo)

    with sqlite3.connect(db) as conn:
        assert conn.execute(
            _read_sql("reconcile_project_count.sql"), {"worktree": str(repo)}
        ).fetchone() == (1,)
        assert conn.execute(_read_sql("reconcile_session_count.sql")).fetchone() == (3,)


def test_reconcile_noop_without_project_table(tmp_path: Path) -> None:
    repo = _make_repo_with_remote(
        tmp_path, "repo-a", "git@github.com:example/example.git"
    )
    shard = _expected_shard(repo)
    db = tmp_path / "xdg-data" / "opencode" / shard
    db.parent.mkdir(parents=True, exist_ok=True)
    schema = (FIXTURES / "session_schema.sql").read_text(encoding="utf-8")
    insert = (FIXTURES / "session_insert.sql").read_text(encoding="utf-8")
    with sqlite3.connect(db) as conn:
        conn.executescript(schema)
        conn.execute(insert, {"sid": "ses_plain"})
        conn.commit()

    _run_dispatch(tmp_path, repo)

    with sqlite3.connect(db) as conn:
        assert conn.execute(_read_sql("reconcile_session_ids.sql")).fetchall() == [
            ("ses_plain",)
        ]
        assert conn.execute(
            _read_sql("reconcile_project_table_count.sql")
        ).fetchone() == (0,)
