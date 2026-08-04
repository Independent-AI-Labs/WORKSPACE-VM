"""Tests for workspace.cli.status."""

from unittest.mock import MagicMock, patch

from workspace.cli.status import (
    _print_footer,
    _print_header,
    _print_service_entry,
    main,
)
from workspace.types.results import LegendRender
from workspace.types.status import PodmanContainer, ServiceDisplayInfo, SystemdService

_MIN_HEADER_BOX_CALLS = 4


def _build_svc(**overrides):
    defaults = {
        "name": "ami-test",
        "scope": "system",
        "active": "active",
        "sub": "running",
        "path": "/tmp/testuser/some/path",
        "pid": "1234",
        "managed_container": None,
        "compose_file": None,
        "compose_profiles": [],
        "restart": "always",
        "enabled": "enabled",
        "memory_bytes": 0,
        "cpu_ns": 0,
        "start_time": "",
        "description": "A test service",
        "exec_start": "",
    }
    defaults.update(overrides)
    return SystemdService(**defaults)


def _build_display(**overrides):
    defaults = {
        "row_type": "service",
        "row_details": [],
        "child_items": [],
        "ports_str": "",
    }
    defaults.update(overrides)
    return ServiceDisplayInfo(**defaults)


class TestPrintHeader:
    def test_prints_header_with_box_borders_and_title(self):
        mock_legend = MagicMock()
        mock_legend.render.return_value = LegendRender("ICONS_LINE", "LABELS_LINE")

        with (
            patch("workspace.cli.status.Legend", return_value=mock_legend),
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("builtins.print") as mock_print,
        ):
            _print_header()

            call_strs = [
                str(call.args[0]) if call.args else ""
                for call in mock_print.call_args_list
            ]
            joined = "".join(call_strs)
            assert joined.startswith("\n")
            assert "\u250c" in joined
            assert "\u2500" in joined
            assert "\u2510" in joined
            assert "\u251c" in joined
            assert "\u2524" in joined
            assert mock_pbl.call_count >= _MIN_HEADER_BOX_CALLS
            pbl_texts = [str(c.args[0]) for c in mock_pbl.call_args_list if c.args]
            assert any("SYSTEM STATUS REPORT" in t for t in pbl_texts)

    def test_calls_print_box_line_for_legend_lines(self):
        mock_legend = MagicMock()
        mock_legend.render.return_value = LegendRender("ICONS", "LABELS")

        with (
            patch("workspace.cli.status.Legend", return_value=mock_legend),
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("builtins.print"),
        ):
            _print_header()

            args_list = [call.args for call in mock_pbl.call_args_list]
            texts = [a[0] for a in args_list if a]
            assert any("SYSTEM STATUS REPORT" in t for t in texts)
            assert any("ICONS" in t for t in texts)
            assert any("LABELS" in t for t in texts)


class TestPrintFooter:
    def test_prints_footer_with_closing_box(self):
        with (
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.Colors") as mock_colors,
            patch("builtins.print") as mock_print,
        ):
            mock_colors.CYAN = "\033[36m"
            mock_colors.RESET = "\033[0m"
            _print_footer()

            call_strs = [
                str(call.args[0]) if call.args else ""
                for call in mock_print.call_args_list
            ]
            joined = "".join(call_strs)
            assert "\u2514" in joined
            assert "\u2518" in joined
            assert "\u2500" in joined


class TestPrintServiceEntry:
    def test_prints_active_running_service_green_icon(self):
        svc = _build_svc(active="active", sub="running")
        info = _build_display()

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_OK", "GREEN"),
        ):
            _print_service_entry(svc, info, [], [])

            first_text = mock_pbl.call_args_list[0].args[0]
            assert "GREEN" in first_text
            assert svc.name in first_text

    def test_prints_activating_service_yellow_icon(self):
        svc = _build_svc(active="activating", sub="running")
        info = _build_display()

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_WARN", "YELLOW"),
        ):
            _print_service_entry(svc, info, [], [])

            first_text = mock_pbl.call_args_list[0].args[0]
            assert "YELLOW" in first_text

    def test_prints_inactive_failed_service_red_icon(self):
        svc = _build_svc(active="inactive", sub="dead")
        info = _build_display()

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_FAIL", "RED"),
        ):
            _print_service_entry(svc, info, [], [])

            first_text = mock_pbl.call_args_list[0].args[0]
            assert "RED" in first_text

    def test_shows_enabled_boot_icon(self):
        svc = _build_svc(enabled="enabled")
        info = _build_display()

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_BOOT", "BOOT_ICON"),
            patch("workspace.cli.status.I_OK", "GREEN"),
        ):
            _print_service_entry(svc, info, [], [])

            first_text = mock_pbl.call_args_list[0].args[0]
            assert "BOOT_ICON" in first_text

    def test_shows_disabled_boot_icon(self):
        svc = _build_svc(enabled="disabled")
        info = _build_display()

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_NOBOOT", "NOBOOT_ICON"),
            patch("workspace.cli.status.I_OK", "GREEN"),
        ):
            _print_service_entry(svc, info, [], [])

            first_text = mock_pbl.call_args_list[0].args[0]
            assert "NOBOOT_ICON" in first_text

    def test_shows_restart_always_icon(self):
        svc = _build_svc(restart="always")
        info = _build_display()

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_OK", "GREEN"),
        ):
            _print_service_entry(svc, info, [], [])

            first_text = mock_pbl.call_args_list[0].args[0]
            assert "\u267b" in first_text or "RESTART" in first_text

    def test_shows_pid_when_not_zero(self):
        svc = _build_svc(pid="5678")
        info = _build_display()

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_OK", "GREEN"),
        ):
            _print_service_entry(svc, info, [], [])

            all_texts = [
                call.args[0]
                for call in mock_pbl.call_args_list
                if "PID" in str(call.args[0])
            ]
            assert len(all_texts) >= 1
            assert "5678" in all_texts[0]

    def test_skips_pid_when_zero(self):
        svc = _build_svc(pid="0")
        info = _build_display()

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_OK", "GREEN"),
        ):
            _print_service_entry(svc, info, [], [])

            pid_lines = [
                call.args[0]
                for call in mock_pbl.call_args_list
                if call.args and "PID" in str(call.args[0])
            ]
            assert len(pid_lines) == 0

    def test_shows_ports_when_available(self):
        svc = _build_svc()
        info = _build_display(ports_str="8080->80/tcp, 443->443/tcp")

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_OK", "GREEN"),
        ):
            _print_service_entry(svc, info, [], [])

            all_texts = [str(call.args[0]) for call in mock_pbl.call_args_list]
            port_lines = [t for t in all_texts if "8080" in t]
            assert len(port_lines) >= 1

    def test_calls_print_service_children(self):
        svc = _build_svc()
        info = _build_display(
            child_items=[PodmanContainer(id="c1", name="child1", image="img:1.0")]
        )

        with (
            patch("workspace.cli.status.print_box_line"),
            patch("workspace.cli.status._print_service_children") as mock_children,
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_OK", "GREEN"),
        ):
            _print_service_entry(svc, info, [], [])

            mock_children.assert_called_once()

    def test_shows_origin_with_tilde_expansion(self):
        svc = _build_svc(path="/tmp/testuser/projects/my-service")
        info = _build_display()

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_OK", "GREEN"),
            patch("os.path.expanduser", return_value="/tmp/testuser"),
        ):
            _print_service_entry(svc, info, [], [])

            all_texts = [str(call.args[0]) for call in mock_pbl.call_args_list]
            origin_lines = [t for t in all_texts if "Origin" in t]
            assert len(origin_lines) == 1
            assert "~/projects/my-service" in origin_lines[0]

    def test_shows_row_details_when_present(self):
        svc = _build_svc()
        info = _build_display(row_details=["alpha", "beta", "gamma"])

        with (
            patch("workspace.cli.status.print_box_line") as mock_pbl,
            patch("workspace.cli.status._print_service_children"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("workspace.cli.status.I_OK", "GREEN"),
        ):
            _print_service_entry(svc, info, [], [])

            all_texts = [str(call.args[0]) for call in mock_pbl.call_args_list]
            detail_lines = [t for t in all_texts if "alpha" in t or "beta" in t]
            assert len(detail_lines) >= 1


class TestMain:
    def test_runs_without_system_flag(self):
        mock_svc = _build_svc(name="svc1")
        mock_info = _build_display()
        mock_legend = MagicMock()
        mock_legend.render.return_value = LegendRender("I", "L")

        with (
            patch("workspace.cli.status.get_systemd_services", return_value=[mock_svc]),
            patch("workspace.cli.status.get_podman_containers", return_value=[]),
            patch("workspace.cli.status.get_container_stats", return_value=[]),
            patch("workspace.cli.status.get_container_sizes", return_value=[]),
            patch(
                "workspace.cli.status.get_managed_service_names", return_value={"svc1"}
            ),
            patch("workspace.cli.status.get_declared_compose_files", return_value=[]),
            patch("workspace.cli.status._print_header") as mock_header,
            patch("workspace.cli.status._print_footer") as mock_footer,
            patch("workspace.cli.status._print_service_entry") as mock_entry,
            patch("workspace.cli.status._print_orphans"),
            patch("workspace.cli.status._print_orphan_services"),
            patch("workspace.cli.status._process_service", return_value=mock_info),
            patch("workspace.cli.status.Legend", return_value=mock_legend),
            patch("workspace.cli.status.Colors"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(system=False)
            main()

            mock_header.assert_called_once()
            mock_footer.assert_called_once()
            mock_entry.assert_called_once()

    def test_runs_with_system_flag_calls_system_section(self):
        mock_svc = _build_svc(name="svc1")
        mock_info = _build_display()
        mock_legend = MagicMock()
        mock_legend.render.return_value = LegendRender("I", "L")

        with (
            patch("workspace.cli.status.get_systemd_services", return_value=[mock_svc]),
            patch("workspace.cli.status.get_podman_containers", return_value=[]),
            patch("workspace.cli.status.get_container_stats", return_value=[]),
            patch("workspace.cli.status.get_container_sizes", return_value=[]),
            patch(
                "workspace.cli.status.get_managed_service_names", return_value={"svc1"}
            ),
            patch("workspace.cli.status.get_declared_compose_files", return_value=[]),
            patch("workspace.cli.status._print_header"),
            patch("workspace.cli.status._print_footer"),
            patch("workspace.cli.status._print_service_entry"),
            patch("workspace.cli.status._print_orphans"),
            patch("workspace.cli.status._print_orphan_services"),
            patch("workspace.cli.status._print_system_docker_section") as mock_system,
            patch("workspace.cli.status._process_service", return_value=mock_info),
            patch("workspace.cli.status.Legend", return_value=mock_legend),
            patch("workspace.cli.status.Colors"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(system=True)
            main()

            mock_system.assert_called_once()

    def test_processes_managed_services_separately_from_orphans(self):
        managed_svc = _build_svc(name="managed-svc")
        orphan_svc = _build_svc(name="ami-orphan", scope="user")
        mock_info = _build_display()
        mock_legend = MagicMock()
        mock_legend.render.return_value = LegendRender("I", "L")

        with (
            patch(
                "workspace.cli.status.get_systemd_services",
                return_value=[managed_svc, orphan_svc],
            ),
            patch("workspace.cli.status.get_podman_containers", return_value=[]),
            patch("workspace.cli.status.get_container_stats", return_value=[]),
            patch("workspace.cli.status.get_container_sizes", return_value=[]),
            patch(
                "workspace.cli.status.get_managed_service_names",
                return_value={"managed-svc"},
            ),
            patch("workspace.cli.status.get_declared_compose_files", return_value=[]),
            patch("workspace.cli.status._print_header"),
            patch("workspace.cli.status._print_footer"),
            patch("workspace.cli.status._print_service_entry") as mock_entry,
            patch("workspace.cli.status._print_orphans"),
            patch("workspace.cli.status._print_orphan_services") as mock_orphan_svcs,
            patch("workspace.cli.status._process_service", return_value=mock_info),
            patch("workspace.cli.status.Legend", return_value=mock_legend),
            patch("workspace.cli.status.Colors"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(system=False)
            main()

            mock_entry.assert_called_once()
            assert mock_entry.call_args[0][0].name == "managed-svc"
            mock_orphan_svcs.assert_called_once()

    def test_handles_empty_services_containers_without_error(self):
        mock_legend = MagicMock()
        mock_legend.render.return_value = LegendRender("I", "L")

        with (
            patch("workspace.cli.status.get_systemd_services", return_value=[]),
            patch("workspace.cli.status.get_podman_containers", return_value=[]),
            patch("workspace.cli.status.get_container_stats", return_value=[]),
            patch("workspace.cli.status.get_container_sizes", return_value=[]),
            patch("workspace.cli.status.get_managed_service_names", return_value=set()),
            patch("workspace.cli.status.get_declared_compose_files", return_value=[]),
            patch("workspace.cli.status._print_header") as mock_header,
            patch("workspace.cli.status._print_footer") as mock_footer,
            patch("workspace.cli.status._print_service_entry") as mock_entry,
            patch("workspace.cli.status._print_orphans") as mock_orphans,
            patch("workspace.cli.status._print_orphan_services") as mock_orphan_svcs,
            patch("workspace.cli.status.Legend", return_value=mock_legend),
            patch("workspace.cli.status.Colors"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(system=False)
            main()

            mock_header.assert_called_once()
            mock_footer.assert_called_once()
            mock_entry.assert_not_called()
            mock_orphans.assert_called_once()
            mock_orphan_svcs.assert_called_once()

    def test_marks_containers_processed_for_declared_compose_files(self):
        container = PodmanContainer(
            id="abc",
            name="my-container",
            state="running",
            status="Up",
            image="img:1.0",
            ports=[],
            labels={"com.docker.compose.project.config_files": "/path/compose.yml"},
        )
        mock_svc = _build_svc(name="managed-svc")
        mock_info = _build_display()
        mock_legend = MagicMock()
        mock_legend.render.return_value = LegendRender("I", "L")

        with (
            patch("workspace.cli.status.get_systemd_services", return_value=[mock_svc]),
            patch(
                "workspace.cli.status.get_podman_containers", return_value=[container]
            ),
            patch("workspace.cli.status.get_container_stats", return_value=[]),
            patch("workspace.cli.status.get_container_sizes", return_value=[]),
            patch(
                "workspace.cli.status.get_managed_service_names",
                return_value={"managed-svc"},
            ),
            patch(
                "workspace.cli.status.get_declared_compose_files",
                return_value=["/path/compose.yml"],
            ),
            patch("workspace.cli.status._print_header"),
            patch("workspace.cli.status._print_footer"),
            patch("workspace.cli.status._print_service_entry"),
            patch("workspace.cli.status._print_orphans") as mock_orphans,
            patch("workspace.cli.status._print_orphan_services"),
            patch("workspace.cli.status._process_service", return_value=mock_info),
            patch("workspace.cli.status.Legend", return_value=mock_legend),
            patch("workspace.cli.status.Colors"),
            patch("workspace.cli.status.DISPLAY_WIDTH", 80),
            patch("argparse.ArgumentParser.parse_args") as mock_args,
        ):
            mock_args.return_value = MagicMock(system=False)
            main()

            orphan_args = mock_orphans.call_args[0]
            processed_containers = orphan_args[1]
            assert "my-container" in processed_containers
