"""Minimal QMP client for controlled QEMU shutdown."""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import TextIO

_QMP_TIMEOUT = 5


class QmpError(RuntimeError):
    """Base error for QMP control failures."""


class QmpClosedError(QmpError):
    """Raised when QMP closes before a command completes."""

    def __init__(self, command: str) -> None:
        super().__init__(f"QMP connection closed during {command}")


class QmpCommandError(QmpError):
    """Raised when QMP returns an error object."""

    def __init__(self, command: str, detail: object) -> None:
        super().__init__(f"QMP error during {command}: {detail}")


class QmpProtocolError(QmpError):
    """Raised when QMP sends an unexpected message."""

    def __init__(self) -> None:
        super().__init__("QMP greeting missing")


class QmpConnectError(QmpError):
    """Raised when the QMP socket cannot be used."""

    def __init__(self, socket_path: Path) -> None:
        super().__init__(f"QMP powerdown failed: {socket_path}")


def _send(sock: socket.socket, command: str) -> None:
    payload = json.dumps({"execute": command}) + "\n"
    sock.sendall(payload.encode("utf-8"))


def _command(sock: socket.socket, stream: TextIO, command: str) -> None:
    _send(sock, command)
    while True:
        line = stream.readline()
        if not line:
            raise QmpClosedError(command)
        message = json.loads(line)
        if "error" in message:
            raise QmpCommandError(command, message["error"])
        if "return" in message:
            return


def powerdown(socket_path: Path, *, timeout: float = _QMP_TIMEOUT) -> None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(socket_path))
            with sock.makefile("r", encoding="utf-8") as stream:
                greeting = stream.readline()
                if not greeting:
                    raise QmpClosedError("greeting")
                config = json.loads(greeting)
                if "QMP" not in config:
                    raise QmpProtocolError
                _command(sock, stream, "qmp_capabilities")
                _command(sock, stream, "system_powerdown")
    except (OSError, json.JSONDecodeError) as exc:
        raise QmpConnectError(socket_path) from exc
