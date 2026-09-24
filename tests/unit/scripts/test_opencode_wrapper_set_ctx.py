"""Tests for workspace/scripts/opencode-wrapper.sh --set-ctx overrides."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

WRAPPER_SH = (
    Path(__file__).resolve().parents[3]
    / "workspace"
    / "scripts"
    / "opencode-wrapper.sh"
)

FAKE_EXIT_USAGE = 2

CONTEXT_X = 1000
CONTEXT_Y = 2000
OUTPUT_LIMIT = 500
OVERRIDE_256K = 256000
OVERRIDE_300K = 300000

RUN_TIMEOUT_S = 60

CONFIG = {
    "provider": {
        "workspace-gw-test": {
            "name": "Workspace GW (Test)",
            "models": {
                "model-x": {
                    "name": "Model X",
                    "limit": {"context": CONTEXT_X, "output": OUTPUT_LIMIT},
                },
                "model-y": {
                    "name": "Model Y",
                    "limit": {"context": CONTEXT_Y, "output": OUTPUT_LIMIT},
                },
                "model-z": {
                    "name": "Model Z",
                },
            },
        }
    }
}


def _make_fake_opencode(tmp_path: Path) -> Path:
    fake = tmp_path / "fake-opencode"
    fake.write_text(
        "#!/bin/bash\n"
        'printf "%s\\n" "${OPENCODE_CONFIG_CONTENT:-UNSET}"\n'
        'printf "ARGS=%s\\n" "$*"\n'
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return fake


def _seed_config(tmp_path: Path) -> Path:
    cfg_dir = tmp_path / "opencode"
    cfg_dir.mkdir()
    cfg = cfg_dir / "opencode.jsonc"
    cfg.write_text(json.dumps(CONFIG, indent=2))
    return cfg


def _run_dispatch(
    tmp_path: Path, *args: str, base: str = '{"subagent_depth":0}'
) -> tuple[int, str]:
    fake = _make_fake_opencode(tmp_path)
    run_env = os.environ.copy()
    run_env.pop("OPENCODE_DB", None)
    run_env["OPENCODE_CONFIG_DIR"] = str(tmp_path / "opencode")
    run_env["XDG_DATA_HOME"] = str(tmp_path / "xdg-data")
    run_env["OPENCODE_CONFIG_CONTENT"] = base
    script = (
        f'source "{WRAPPER_SH}" || exit 1\n'
        f'oc_wrapper_dispatch "{fake}" "{tmp_path}" "$@"\n'
    )
    try:
        output = subprocess.check_output(
            ["bash", "-c", script, "dispatch", *args],
            text=True,
            cwd=tmp_path,
            env=run_env,
            stderr=subprocess.STDOUT,
            timeout=RUN_TIMEOUT_S,
        )
    except subprocess.CalledProcessError as exc:
        return exc.returncode, exc.output
    return 0, output


def _payload(out: str) -> dict:
    return json.loads(next(line for line in out.splitlines() if line.startswith("{")))


def test_set_ctx_overrides_context_for_this_run(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    code, out = _run_dispatch(
        tmp_path, "--set-ctx", "workspace-gw-test/model-x", str(OVERRIDE_256K)
    )
    assert code == 0
    model = _payload(out)["provider"]["workspace-gw-test"]["models"]["model-x"]
    assert model["limit"]["context"] == OVERRIDE_256K
    assert model["limit"]["output"] == OUTPUT_LIMIT


def test_set_ctx_preserves_base_config_content(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    _, out = _run_dispatch(
        tmp_path, "--set-ctx", "workspace-gw-test/model-x", str(OVERRIDE_256K)
    )
    assert _payload(out)["subagent_depth"] == 0


def test_set_ctx_matches_provider_and_model_names(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    code, out = _run_dispatch(
        tmp_path, "--set-ctx", "Workspace GW (Test)/Model Y", str(OVERRIDE_300K)
    )
    assert code == 0
    model = _payload(out)["provider"]["workspace-gw-test"]["models"]["model-y"]
    assert model["limit"]["context"] == OVERRIDE_300K


def test_set_ctx_persist_writes_config(tmp_path: Path) -> None:
    cfg = _seed_config(tmp_path)
    code, _ = _run_dispatch(
        tmp_path,
        "--set-ctx",
        "workspace-gw-test/Model Y",
        str(OVERRIDE_300K),
        "--persist",
    )
    assert code == 0
    updated = json.loads(cfg.read_text())
    model = updated["provider"]["workspace-gw-test"]["models"]["model-y"]
    assert model["limit"]["context"] == OVERRIDE_300K
    assert model["limit"]["output"] == OUTPUT_LIMIT


def test_set_ctx_persist_keeps_other_providers(tmp_path: Path) -> None:
    cfg = _seed_config(tmp_path)
    _run_dispatch(
        tmp_path,
        "--set-ctx",
        "workspace-gw-test/model-x",
        str(OVERRIDE_256K),
        "--persist",
    )
    updated = json.loads(cfg.read_text())
    assert (
        updated["provider"]["workspace-gw-test"]["models"]["model-y"]["limit"][
            "context"
        ]
        == CONTEXT_Y
    )


def test_set_ctx_forwards_task_arguments(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    code, out = _run_dispatch(
        tmp_path, "--set-ctx", "workspace-gw-test/model-x", "256000", "do the thing"
    )
    assert code == 0
    assert "ARGS=run --dir" in out


def test_set_ctx_unknown_model_rejected(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    code, out = _run_dispatch(tmp_path, "--set-ctx", "workspace-gw-test/nope", "256000")
    assert code == FAKE_EXIT_USAGE
    assert "No model matches" in out


def test_set_ctx_missing_operands_rejected(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    code, out = _run_dispatch(tmp_path, "--set-ctx", "only-one")
    assert code == FAKE_EXIT_USAGE
    assert "--set-ctx requires" in out


def test_set_ctx_bad_size_rejected(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    code, out = _run_dispatch(tmp_path, "--set-ctx", "workspace-gw-test/model-x", "0")
    assert code == FAKE_EXIT_USAGE
    assert "positive integer" in out


def test_set_ctx_model_without_output_rejected(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    code, out = _run_dispatch(tmp_path, "--set-ctx", "workspace-gw-test/model-z", "256000")
    assert code == FAKE_EXIT_USAGE
    assert "has no limit.output" in out


def test_persist_without_set_ctx_rejected(tmp_path: Path) -> None:
    _seed_config(tmp_path)
    code, out = _run_dispatch(tmp_path, "--persist")
    assert code == FAKE_EXIT_USAGE
    assert "--persist requires --set-ctx" in out
