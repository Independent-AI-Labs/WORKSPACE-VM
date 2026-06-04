"""Tests for workspace.cli.storage."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

from workspace.cli.storage import (
    _clean_podman_dangling,
    _clean_project_tmp,
    _clean_system_tmp,
    _clean_uv_cache,
    _print_container_sizes,
    _print_root_disk,
    _remove_path,
    _run_clean,
    main,
)

_DISK_PERCENT = 45.2
_ANALYZE_CALL_COUNT = 3


class TestPrintRootDisk:
    def test_prints_root_disk_info_with_progress_bar(self):
        mock_disk = MagicMock()
        mock_disk.percent = 45.2
        mock_disk.used = 50000000000
        mock_disk.total = 200000000000
        mock_bar = MagicMock()
        mock_bar.render.return_value = "PROGRESS BAR LINE"

        with (
            patch("psutil.disk_usage", return_value=mock_disk),
            patch("workspace.cli.storage.ProgressBar", return_value=mock_bar),
            patch("workspace.cli.storage.get_size_str", side_effect=lambda x: f"{x}B"),
            patch("workspace.cli.storage._BAR_WIDTH", 40),
            patch("builtins.print") as mock_print,
        ):
            _print_root_disk()

            mock_bar.render.assert_called_once()
            call_args = mock_bar.render.call_args
            assert call_args[1]["percent"] == _DISK_PERCENT
            assert call_args[1]["label"] == "Root Disk"
            assert "50000000000B" in call_args[1]["value"]
            mock_print.assert_called_once_with("PROGRESS BAR LINE")


class TestCleanUvCache:
    def test_successful_clean(self):
        mock_run = MagicMock()
        mock_run.return_value.returncode = 0

        with patch("subprocess.run", mock_run), patch("builtins.print") as mock_print:
            _clean_uv_cache()

            mock_run.assert_called_once_with(
                ["uv", "cache", "clean", "--force"],
                capture_output=True,
                text=True,
                check=False,
            )
            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "done" in calls_text
            assert "skipped" not in calls_text

    def test_failed_clean_with_stderr(self):
        mock_run = MagicMock()
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "no space left"

        with patch("subprocess.run", mock_run), patch("builtins.print") as mock_print:
            _clean_uv_cache()

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "skipped" in calls_text
            assert "no space left" in calls_text


class TestCleanPodmanDangling:
    def test_successful_with_removals(self):
        mock_run = MagicMock()
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "abc123\ndef456\nghi789"

        with patch("subprocess.run", mock_run), patch("builtins.print") as mock_print:
            _clean_podman_dangling()

            mock_run.assert_called_once_with(
                ["podman", "image", "prune", "-f"],
                capture_output=True,
                text=True,
                check=False,
            )
            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "done" in calls_text
            assert "3 removed" in calls_text

    def test_successful_no_removals(self):
        mock_run = MagicMock()
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""

        with patch("subprocess.run", mock_run), patch("builtins.print") as mock_print:
            _clean_podman_dangling()

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "none to remove" in calls_text

    def test_failed_with_stderr(self):
        mock_run = MagicMock()
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "cannot connect to podman"

        with patch("subprocess.run", mock_run), patch("builtins.print") as mock_print:
            _clean_podman_dangling()

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "skipped" in calls_text
            assert "cannot connect to podman" in calls_text


class TestCleanProjectTmp:
    def test_path_does_not_exist_skipped(self):
        with patch("builtins.print") as mock_print:
            _clean_project_tmp("/nonexistent/path")

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "skipped" in calls_text

    def test_empty_directory_prints_empty(self):
        mock_path = MagicMock(spec=Path)
        mock_path.expanduser.return_value = mock_path
        mock_path.__truediv__.return_value = mock_path
        mock_path.exists.return_value = True
        mock_path.iterdir.return_value = []

        with (
            patch("workspace.cli.storage.Path", return_value=mock_path),
            patch("builtins.print") as mock_print,
        ):
            _clean_project_tmp(".")

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "empty" in calls_text

    def test_directory_with_files_and_gitkeep(self):
        gitkeep = MagicMock()
        gitkeep.name = ".gitkeep"
        regular = MagicMock()
        regular.name = "data.log"
        regular.is_dir.return_value = False
        regular.is_file.return_value = True

        mock_path = MagicMock(spec=Path)
        mock_path.expanduser.return_value = mock_path
        mock_path.__truediv__.return_value = mock_path
        mock_path.exists.return_value = True
        mock_path.iterdir.return_value = [gitkeep, regular]

        with (
            patch("workspace.cli.storage.Path", return_value=mock_path),
            patch("workspace.cli.storage._remove_path", return_value=True),
            patch("builtins.print") as mock_print,
        ):
            _clean_project_tmp(".")

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "done" in calls_text

    def test_error_during_iteration_handled(self):
        mock_path = MagicMock(spec=Path)
        mock_path.expanduser.return_value = mock_path
        mock_path.__truediv__.return_value = mock_path
        mock_path.exists.return_value = True
        mock_path.iterdir.side_effect = PermissionError("denied")

        with (
            patch("workspace.cli.storage.Path", return_value=mock_path),
            patch("builtins.print") as mock_print,
        ):
            _clean_project_tmp(".")

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "error" in calls_text


class TestRemovePath:
    def test_removes_directory_via_rm_rf(self):
        mock_item = MagicMock(spec=Path)
        mock_item.is_dir.return_value = True
        mock_item.is_file.return_value = False

        with patch("subprocess.run") as mock_run:
            result = _remove_path(mock_item)

            mock_run.assert_called_once_with(
                ["rm", "-rf", str(mock_item)],
                capture_output=True,
                check=False,
            )
            assert result is True

    def test_removes_file_via_unlink(self):
        mock_item = MagicMock(spec=Path)
        mock_item.is_dir.return_value = False
        mock_item.is_file.return_value = True

        with patch("subprocess.run") as mock_run:
            result = _remove_path(mock_item)

            mock_item.unlink.assert_called_once_with(missing_ok=True)
            mock_run.assert_not_called()
            assert result is True

    def test_handles_exception_returns_false(self):
        mock_item = MagicMock(spec=Path)
        mock_item.is_dir.side_effect = OSError("permission denied")

        result = _remove_path(mock_item)
        assert result is False


class TestCleanSystemTmp:
    def test_cleans_tmp_with_item_count(self):
        mock_item1 = MagicMock(spec=Path)
        mock_item1.is_dir.return_value = False
        mock_item1.is_file.return_value = True
        mock_item2 = MagicMock(spec=Path)
        mock_item2.is_dir.return_value = True
        mock_item2.is_file.return_value = False

        mock_path = MagicMock(spec=Path)
        mock_path.iterdir.return_value = [mock_item1, mock_item2]

        with (
            patch("workspace.cli.storage.Path", return_value=mock_path),
            patch("workspace.cli.storage._remove_path", return_value=True),
            patch("builtins.print") as mock_print,
        ):
            _clean_system_tmp()

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "done" in calls_text
            assert "2 items removed" in calls_text

    def test_handles_exception_during_iteration(self):
        mock_path = MagicMock(spec=Path)
        mock_path.iterdir.side_effect = PermissionError("denied")

        with (
            patch("workspace.cli.storage.Path", return_value=mock_path),
            patch("builtins.print") as mock_print,
        ):
            _clean_system_tmp()

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "error" in calls_text


class TestRunClean:
    def test_calls_all_clean_functions_in_order(self):
        with (
            patch("workspace.cli.storage._clean_uv_cache") as mock_uv,
            patch("workspace.cli.storage._clean_podman_dangling") as mock_podman,
            patch("workspace.cli.storage._clean_project_tmp") as mock_project,
            patch("workspace.cli.storage._clean_system_tmp") as mock_tmp,
            patch("builtins.print"),
        ):
            _run_clean("/my/project")

            mock_uv.assert_called_once()
            mock_podman.assert_called_once()
            mock_project.assert_called_once_with("/my/project")
            mock_tmp.assert_called_once()


class TestPrintContainerSizes:
    def test_prints_container_sizes(self):
        mock_sizes = [
            {"name": "web", "writable": "100MB", "virtual": "200MB"},
            {"name": "db", "writable": "500MB", "virtual": "1GB"},
        ]

        with (
            patch("workspace.cli.storage.get_container_sizes", return_value=mock_sizes),
            patch("builtins.print") as mock_print,
        ):
            _print_container_sizes()

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "Container Sizes" in calls_text
            assert "web" in calls_text
            assert "db" in calls_text

    def test_prints_no_containers_when_list_empty(self):
        with (
            patch("workspace.cli.storage.get_container_sizes", return_value=[]),
            patch("builtins.print") as mock_print,
        ):
            _print_container_sizes()

            calls_text = " ".join(
                str(c.args[0]) for c in mock_print.call_args_list if c.args
            )
            assert "No containers" in calls_text


class TestMain:
    def test_default_arguments(self):
        with (
            patch("workspace.cli.storage._print_root_disk") as mock_disk,
            patch("workspace.cli.storage._print_container_sizes") as mock_containers,
            patch("workspace.cli.storage.analyze") as mock_analyze,
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(
                path=".",
                no_containers=False,
                no_breakdown=False,
                no_fs_scan=False,
                no_tmp_scan=False,
                clean=False,
            )
            result = main()

            assert result == 0
            mock_disk.assert_called_once()
            mock_containers.assert_called_once()
            assert mock_analyze.call_count == _ANALYZE_CALL_COUNT
            mock_analyze.assert_has_calls(
                [
                    call("."),
                    call("/", same_fs=True),
                    call("/tmp"),
                ]
            )

    def test_with_no_containers_flag(self):
        with (
            patch("workspace.cli.storage._print_root_disk"),
            patch("workspace.cli.storage._print_container_sizes") as mock_containers,
            patch("workspace.cli.storage.analyze"),
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(
                path=".",
                no_containers=True,
                no_breakdown=False,
                no_fs_scan=False,
                no_tmp_scan=False,
                clean=False,
            )
            main()

            mock_containers.assert_not_called()

    def test_with_no_breakdown_flag(self):
        with (
            patch("workspace.cli.storage._print_root_disk"),
            patch("workspace.cli.storage._print_container_sizes"),
            patch("workspace.cli.storage.analyze") as mock_analyze,
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(
                path=".",
                no_containers=False,
                no_breakdown=True,
                no_fs_scan=False,
                no_tmp_scan=False,
                clean=False,
            )
            main()

            assert call(".") not in mock_analyze.call_args_list
            assert call("/", same_fs=True) in mock_analyze.call_args_list
            assert call("/tmp") in mock_analyze.call_args_list

    def test_with_no_fs_scan_flag(self):
        with (
            patch("workspace.cli.storage._print_root_disk"),
            patch("workspace.cli.storage._print_container_sizes"),
            patch("workspace.cli.storage.analyze") as mock_analyze,
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(
                path=".",
                no_containers=False,
                no_breakdown=False,
                no_fs_scan=True,
                no_tmp_scan=False,
                clean=False,
            )
            main()

            assert call("/", same_fs=True) not in mock_analyze.call_args_list
            assert call(".") in mock_analyze.call_args_list
            assert call("/tmp") in mock_analyze.call_args_list

    def test_with_no_tmp_scan_flag(self):
        with (
            patch("workspace.cli.storage._print_root_disk"),
            patch("workspace.cli.storage._print_container_sizes"),
            patch("workspace.cli.storage.analyze") as mock_analyze,
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(
                path=".",
                no_containers=False,
                no_breakdown=False,
                no_fs_scan=False,
                no_tmp_scan=True,
                clean=False,
            )
            main()

            assert call("/tmp") not in mock_analyze.call_args_list
            assert call(".") in mock_analyze.call_args_list
            assert call("/", same_fs=True) in mock_analyze.call_args_list

    def test_with_clean_flag_calls_run_clean(self):
        with (
            patch("workspace.cli.storage._print_root_disk"),
            patch("workspace.cli.storage._print_container_sizes"),
            patch("workspace.cli.storage.analyze"),
            patch("workspace.cli.storage._run_clean") as mock_clean,
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(
                path=".",
                no_containers=False,
                no_breakdown=False,
                no_fs_scan=False,
                no_tmp_scan=False,
                clean=True,
            )
            main()

            mock_clean.assert_called_once_with(".")

    def test_with_custom_path_argument(self):
        with (
            patch("workspace.cli.storage._print_root_disk"),
            patch("workspace.cli.storage._print_container_sizes"),
            patch("workspace.cli.storage.analyze") as mock_analyze,
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(
                path="/custom/path",
                no_containers=False,
                no_breakdown=False,
                no_fs_scan=False,
                no_tmp_scan=False,
                clean=False,
            )
            main()

            mock_analyze.assert_any_call("/custom/path")

    def test_returns_zero(self):
        with (
            patch("workspace.cli.storage._print_root_disk"),
            patch("workspace.cli.storage._print_container_sizes"),
            patch("workspace.cli.storage.analyze"),
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(
                path=".",
                no_containers=False,
                no_breakdown=False,
                no_fs_scan=False,
                no_tmp_scan=False,
                clean=False,
            )
            result = main()
            assert result == 0
