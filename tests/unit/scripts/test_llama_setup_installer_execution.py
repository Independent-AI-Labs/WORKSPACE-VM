"""Unit tests for llama_setup_installer main and CI defaults path."""

from pathlib import Path
from unittest.mock import patch

from workspace.scripts.llama_setup_installer import (
    DefaultsConfig,
    RunSummary,
    _load_defaults,
    _print_summary,
    main,
)
from workspace.scripts.llama_setup_registry import load_registry


class TestLoadDefaults:
    def test_load_defaults_parses_stacks(self) -> None:
        path = (
            Path(__file__).resolve().parents[3]
            / "workspace/config/llama-setup-defaults.yaml"
        )
        config = _load_defaults(path)
        assert isinstance(config, DefaultsConfig)
        assert "llamafile_vulkan_server" in config.stack_ids
        assert config.deploy is True


class TestPrintSummary:
    def test_success_exit_code(self) -> None:
        assert _print_summary(RunSummary(success_count=2, failed_labels=[])) == 0

    def test_failure_exit_code(self) -> None:
        assert _print_summary(RunSummary(success_count=1, failed_labels=["step"])) == 1


class TestMain:
    @patch("workspace.scripts.llama_setup_installer._run_from_defaults")
    @patch("sys.stdin")
    def test_defaults_skips_tty_check(self, mock_stdin, mock_run_defaults) -> None:
        mock_run_defaults.return_value = 0
        path = Path("workspace/config/llama-setup-defaults.yaml")
        with patch(
            "sys.argv",
            ["llama_setup_installer.py", "--defaults", str(path)],
        ):
            result = main()
        assert result == 0
        mock_run_defaults.assert_called_once()

    @patch("sys.stdin")
    def test_non_tty_without_defaults_exits(self, mock_stdin) -> None:
        mock_stdin.isatty.return_value = False
        with patch("sys.argv", ["llama_setup_installer.py"]):
            result = main()
        assert result == 1


class TestRegistryIntegration:
    def test_registry_loads_from_disk(self) -> None:
        registry = load_registry()
        ids = {stack.id for stack in registry.stacks}
        assert "llama_cpp_cpu" in ids
        assert "llamafile_vulkan_server" in ids
