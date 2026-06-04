from unittest.mock import MagicMock, patch

import psutil
from dataops.cli_components.text_input_utils import Colors

from workspace.cli.status_utils import (
    C_DIM,
    I_FAIL,
    I_NORESTART,
    I_OK,
    I_RESTART_ALWAYS,
    I_RESTART_FAIL,
    I_STOP,
    I_WARN,
    _format_port_string,
    _get_container_status_display,
    _get_restart_icon,
    format_bytes,
    format_ports,
    get_local_ports,
    get_visual_width,
    parse_size_to_bytes,
    print_box_line,
    run_cmd,
)
from workspace.types.status import PortMapping

_VW_HELLO = 5
_VW_ANSI_OK = 2
_VW_EA_WIDE = 2
_VW_MIXED = 5
_TWO_PORTS = 2
_100B = 100
_1KB = 1024
_12345B = 12345


class TestRunCmd:
    def test_successful_command(self):
        with patch("workspace.cli.status_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="hello\n", stderr="", returncode=0)
            result = run_cmd("echo hello")
            assert result == "hello"

    def test_failed_command_returns_stdout(self):
        with patch("workspace.cli.status_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="error output\n", stderr="", returncode=1
            )
            result = run_cmd("failing command")
            assert result == "error output"

    def test_subprocess_error_returns_empty(self):
        with patch(
            "workspace.cli.status_utils.subprocess.run",
            side_effect=__import__("subprocess").SubprocessError("boom"),
        ):
            result = run_cmd("bad command")
            assert result == ""

    def test_empty_output(self):
        with patch("workspace.cli.status_utils.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="  \n", stderr="", returncode=0)
            result = run_cmd("empty command")
            assert result == ""


class TestGetVisualWidth:
    def test_ascii_text(self):
        assert get_visual_width("hello") == _VW_HELLO

    def test_ansi_codes_stripped(self):
        assert get_visual_width("\033[32mok\033[0m") == _VW_ANSI_OK

    def test_east_asian_wide(self):
        assert get_visual_width("あ") == _VW_EA_WIDE

    def test_gear_emoji_double_counting(self):
        base = len("⚙️")
        visual = get_visual_width("⚙️")
        assert visual == base + 2

    def test_mixed_content(self):
        width = get_visual_width("🟢 ok")
        assert width == _VW_MIXED


class TestGetLocalPorts:
    def test_valid_pid_with_ports(self):
        mock_process = MagicMock()
        mock_process.children.return_value = []
        mock_conn = MagicMock()
        mock_conn.status = psutil.CONN_LISTEN
        mock_conn.laddr.port = 8080
        mock_process.net_connections.return_value = [mock_conn]

        with patch("psutil.Process", return_value=mock_process):
            result = get_local_ports("1234")
            assert result == ["8080"]

    def test_pid_zero_returns_empty(self):
        result = get_local_ports("0")
        assert result == []

    def test_pid_empty_returns_empty(self):
        result = get_local_ports("")
        assert result == []

    def test_no_such_process_returns_empty(self):
        with patch(
            "psutil.Process",
            side_effect=psutil.NoSuchProcess(1234),
        ):
            result = get_local_ports("1234")
            assert result == []

    def test_access_denied_returns_empty(self):
        with patch(
            "psutil.Process",
            side_effect=psutil.AccessDenied(1234),
        ):
            result = get_local_ports("1234")
            assert result == []

    def test_value_error_returns_empty(self):
        with patch(
            "psutil.Process",
            side_effect=ValueError("bad pid"),
        ):
            result = get_local_ports("abc")
            assert result == []

    def test_process_with_children_collects_all(self):
        mock_parent = MagicMock()
        mock_child = MagicMock()

        conn_parent = MagicMock()
        conn_parent.status = psutil.CONN_LISTEN
        conn_parent.laddr.port = 3000
        mock_parent.net_connections.return_value = [conn_parent]

        conn_child = MagicMock()
        conn_child.status = psutil.CONN_LISTEN
        conn_child.laddr.port = 4000
        mock_child.net_connections.return_value = [conn_child]

        mock_parent.children.return_value = [mock_child]

        # _collect_ports_from_process is called for parent first, then child
        def process_side_effect(pid):
            if str(pid) == "9999":
                return mock_parent
            raise psutil.NoSuchProcess(9999)

        with patch("psutil.Process", side_effect=process_side_effect):
            result = get_local_ports("9999")
            assert "3000" in result
            assert "4000" in result
            assert len(result) == _TWO_PORTS


class TestFormatPorts:
    def test_empty_list_returns_empty(self):
        assert format_ports([]) == ""

    def test_single_port_with_host_and_container(self):
        ports = [PortMapping(host_port=8080, container_port=80, protocol="tcp")]
        assert format_ports(ports) == "8080->80/tcp"

    def test_container_port_only(self):
        ports = [PortMapping(host_port=None, container_port=80, protocol="tcp")]
        assert format_ports(ports) == "80/tcp"

    def test_multiple_ports(self):
        ports = [
            PortMapping(host_port=8080, container_port=80, protocol="tcp"),
            PortMapping(host_port=8443, container_port=443, protocol="tcp"),
        ]
        result = format_ports(ports)
        assert "8080->80/tcp" in result
        assert "8443->443/tcp" in result

    def test_ports_with_protocol_field(self):
        ports = [PortMapping(host_port=5432, container_port=5432, protocol="udp")]
        assert format_ports(ports) == "5432->5432/udp"


class TestFormatBytes:
    def test_zero_bytes(self):
        assert format_bytes(0) == "0B"

    def test_negative_bytes(self):
        assert format_bytes(-100) == "0B"

    def test_bytes_range(self):
        assert format_bytes(500) == "500B"

    def test_kb_range(self):
        assert format_bytes(2048) == "2KB"

    def test_mb_range(self):
        assert format_bytes(5 * 1024 * 1024) == "5.0MB"

    def test_gb_range(self):
        assert format_bytes(2.5 * 1024**3) == "2.5GB"

    def test_tb_range(self):
        assert format_bytes(3 * 1024**4) == "3.0TB"

    def test_pb_range(self):
        assert format_bytes(5 * 1024**5) == "5.0PB"


class TestParseSizeToBytes:
    def test_empty_string_returns_zero(self):
        assert parse_size_to_bytes("") == 0

    def test_dash_returns_zero(self):
        assert parse_size_to_bytes("-") == 0

    def test_100b(self):
        assert parse_size_to_bytes("100B") == _100B

    def test_1k(self):
        assert parse_size_to_bytes("1K") == _1KB

    def test_1_5m(self):
        assert parse_size_to_bytes("1.5M") == int(1.5 * 1024**2)

    def test_1g(self):
        assert parse_size_to_bytes("1G") == 1024**3

    def test_2t(self):
        assert parse_size_to_bytes("2T") == 2 * 1024**4

    def test_invalid_format_returns_zero(self):
        assert parse_size_to_bytes("xyz") == 0

    def test_plain_integer_no_suffix(self):
        assert parse_size_to_bytes("12345") == _12345B

    def test_lowercase_suffix(self):
        assert parse_size_to_bytes("100m") == 100 * 1024**2


class TestPrintBoxLine:
    def test_normal_text_within_width(self, capsys):
        print_box_line("hello", 80)
        captured = capsys.readouterr()
        assert "hello" in captured.out
        assert "│" in captured.out

    def test_text_exceeding_width_truncated(self, capsys):
        long_text = "x" * 100
        print_box_line(long_text, 10)
        captured = capsys.readouterr()
        printed_text = captured.out
        visible = long_text[: 10 - 4]
        assert visible in printed_text

    def test_bold_true_uses_bold(self, capsys):
        print_box_line("hello", 80, bold=True)
        captured = capsys.readouterr()
        assert "\033[1m" in captured.out

    def test_uses_box_characters(self, capsys):
        print_box_line("test", 80)
        captured = capsys.readouterr()
        assert "│" in captured.out


class TestGetRestartIcon:
    def test_always(self):
        icon = _get_restart_icon("always")
        assert icon == I_RESTART_ALWAYS

    def test_on_failure(self):
        icon = _get_restart_icon("on-failure")
        assert icon == I_RESTART_FAIL

    def test_on_abnormal(self):
        icon = _get_restart_icon("on-abnormal")
        assert icon == I_RESTART_FAIL

    def test_on_abort(self):
        icon = _get_restart_icon("on-abort")
        assert icon == I_RESTART_FAIL

    def test_on_watchdog(self):
        icon = _get_restart_icon("on-watchdog")
        assert icon == I_RESTART_FAIL

    def test_unknown_policy(self):
        icon = _get_restart_icon("never")
        assert icon == I_NORESTART

    def test_empty_string(self):
        icon = _get_restart_icon("")
        assert icon == I_NORESTART


class TestGetContainerStatusDisplay:
    def test_running(self):
        display = _get_container_status_display("running")
        assert display.icon == I_OK
        assert display.color == Colors.GREEN

    def test_exited(self):
        display = _get_container_status_display("exited")
        assert display.icon == I_FAIL
        assert display.color == Colors.RED

    def test_paused(self):
        display = _get_container_status_display("paused")
        assert display.icon == I_WARN
        assert display.color == Colors.YELLOW

    def test_unknown_state(self):
        display = _get_container_status_display("unknown")
        assert display.icon == I_STOP
        assert display.color == C_DIM


class TestFormatPortString:
    def test_with_host_port(self):
        port = PortMapping(host_port=8080, container_port=80, protocol="tcp")
        assert _format_port_string(port) == "8080->80/tcp"

    def test_without_host_port(self):
        port = PortMapping(host_port=None, container_port=3000, protocol="tcp")
        assert _format_port_string(port) == "3000/tcp"
