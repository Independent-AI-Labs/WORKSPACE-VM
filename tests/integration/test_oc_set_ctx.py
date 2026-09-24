"""Integration tests for the oc --set-ctx context override (this-run and persisted)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.integration.oc_config_test_helpers import WRAPPERS, run_wrapper

CONTEXT_X = 1000
CONTEXT_Y = 2000
OUTPUT_LIMIT = 500
OVERRIDE_256K = 256000
OVERRIDE_300K = 300000

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
            },
        }
    }
}


def _seed_config(tmp_path: Path) -> Path:
    config_dir = tmp_path / "seeded-config"
    config_dir.mkdir()
    (config_dir / "opencode.jsonc").write_text(json.dumps(CONFIG, indent=2))
    return config_dir


def _model_on_disk(config_dir: Path, model: str) -> dict:
    config = json.loads((config_dir / "opencode.jsonc").read_text(encoding="utf-8"))
    return config["provider"]["workspace-gw-test"]["models"][model]


def _context_on_disk(config_dir: Path, model: str) -> int:
    return _model_on_disk(config_dir, model)["limit"]["context"]


@pytest.mark.integration
class TestOcSetCtx:
    @pytest.mark.parametrize("wrapper", WRAPPERS)
    def test_override_reaches_opencode_without_touching_disk(
        self, tmp_path: Path, wrapper: Path
    ):
        """The override is exported for the run and the config file is left alone."""
        config_dir = _seed_config(tmp_path)
        values, args, _ = run_wrapper(
            tmp_path,
            wrapper,
            [
                "--set-ctx",
                "workspace-gw-test/model-x",
                str(OVERRIDE_256K),
                "normal task",
            ],
            config_dir,
        )
        content = json.loads(values["content"])
        override = content["provider"]["workspace-gw-test"]["models"]["model-x"]
        assert override["limit"]["context"] == OVERRIDE_256K
        assert override["limit"]["output"] == OUTPUT_LIMIT
        assert content["permission"]["task"] == "deny"
        assert args[-1] == "normal task"
        assert _context_on_disk(config_dir, "model-x") == CONTEXT_X
        assert not (config_dir / "opencode.jsonc.bak").exists()

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    def test_persist_writes_context_to_disk(self, tmp_path: Path, wrapper: Path):
        """--persist rewrites the model limit in the real config file."""
        config_dir = _seed_config(tmp_path)
        run_wrapper(
            tmp_path,
            wrapper,
            [
                "--set-ctx",
                "workspace-gw-test/model-x",
                str(OVERRIDE_256K),
                "--persist",
            ],
            config_dir,
        )
        model = _model_on_disk(config_dir, "model-x")
        assert model["limit"]["context"] == OVERRIDE_256K
        assert model["limit"]["output"] == OUTPUT_LIMIT

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    def test_persist_keeps_unrelated_entries_and_creates_backup(
        self, tmp_path: Path, wrapper: Path
    ):
        """Persisting one model leaves others intact and backs up the original."""
        config_dir = _seed_config(tmp_path)
        original = (config_dir / "opencode.jsonc").read_text(encoding="utf-8")
        run_wrapper(
            tmp_path,
            wrapper,
            [
                "--set-ctx",
                "workspace-gw-test/model-y",
                str(OVERRIDE_300K),
                "--persist",
            ],
            config_dir,
        )
        assert _context_on_disk(config_dir, "model-y") == OVERRIDE_300K
        assert _context_on_disk(config_dir, "model-x") == CONTEXT_X
        backup = config_dir / "opencode.jsonc.bak"
        assert backup.read_text(encoding="utf-8") == original

    @pytest.mark.parametrize("wrapper", WRAPPERS)
    def test_override_matches_provider_and_model_names(
        self, tmp_path: Path, wrapper: Path
    ):
        """Provider/model configured names resolve to the same on-disk keys."""
        config_dir = _seed_config(tmp_path)
        values, _, _ = run_wrapper(
            tmp_path,
            wrapper,
            [
                "--set-ctx",
                "Workspace GW (Test)/Model Y",
                str(OVERRIDE_300K),
                "--persist",
            ],
            config_dir,
        )
        content = json.loads(values["content"])
        override = content["provider"]["workspace-gw-test"]["models"]["model-y"]
        assert override["limit"]["context"] == OVERRIDE_300K
        assert override["limit"]["output"] == OUTPUT_LIMIT
        assert _context_on_disk(config_dir, "model-y") == OVERRIDE_300K
