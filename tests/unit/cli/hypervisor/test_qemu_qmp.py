"""Unit tests for the QMP shutdown client."""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

import pytest

from workspace.cli.hypervisor import qemu_qmp as qq


def _server(
    path: Path, *, fail: bool = False
) -> tuple[threading.Thread, threading.Event]:
    ready = threading.Event()

    def serve() -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.bind(str(path))
            sock.listen(1)
            ready.set()
            conn, _ = sock.accept()
            with conn, conn.makefile("rw", encoding="utf-8") as stream:
                stream.write(json.dumps({"QMP": {"version": {}}}) + "\n")
                stream.flush()
                stream.readline()
                response = (
                    {"error": {"class": "GenericError"}} if fail else {"return": {}}
                )
                stream.write(json.dumps(response) + "\n")
                stream.flush()
                if fail:
                    return
                stream.readline()
                stream.write(json.dumps({"return": {}}) + "\n")
                stream.flush()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return thread, ready


def test_powerdown_sends_capabilities_and_shutdown(tmp_path: Path) -> None:
    path = tmp_path / "qmp.sock"
    thread, ready = _server(path)
    assert ready.wait(timeout=5)
    qq.powerdown(path)
    thread.join(timeout=5)


def test_powerdown_surfaces_qmp_error(tmp_path: Path) -> None:
    path = tmp_path / "qmp.sock"
    thread, ready = _server(path, fail=True)
    assert ready.wait(timeout=5)
    with pytest.raises(qq.QmpCommandError):
        qq.powerdown(path)
    thread.join(timeout=5)


def test_powerdown_missing_socket(tmp_path: Path) -> None:
    with pytest.raises(qq.QmpConnectError):
        qq.powerdown(tmp_path / "missing.sock")
