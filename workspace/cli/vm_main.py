"""VM lifecycle - CLI entry point for vm subcommands."""

from __future__ import annotations

import sys
from collections.abc import Callable

from workspace.cli.vm_lifecycle import (
    delete,
    exec_cmd,
    kill,
    list_vms,
    shell,
    show_logs,
    show_status,
    start,
    stop,
)
from workspace.cli.vm_manager import create, rebuild
from workspace.cli.vm_sync import sync

_SUB_CMD_ARGS = 2


def _usage() -> None:
    commands = "create|rebuild|sync|start|stop|delete|shell|exec|list|status|logs|kill"
    print(
        f"usage: python -m workspace.cli.vm_main <{commands}> <args>",
        file=sys.stderr,
    )


def _require_arg(args: list[str], name: str) -> str | None:
    if len(args) < _SUB_CMD_ARGS:
        print(f"{name}: missing argument", file=sys.stderr)
        return None
    return args[1]


def _run_create(args: list[str]) -> None:
    create(args[1])


def _run_rebuild(args: list[str]) -> None:
    rebuild(args[1])


def _run_sync(args: list[str]) -> None:
    sync(args[1])


def _run_start(args: list[str]) -> None:
    start(args[1])


def _run_stop(args: list[str]) -> None:
    stop(args[1])


def _run_delete(args: list[str]) -> None:
    delete(args[1], purge="--purge" in args[2:])


def _run_shell(args: list[str]) -> None:
    shell(args[1])


def _run_kill(args: list[str]) -> None:
    kill(args[1])


def _run_list(_args: list[str]) -> None:
    list_vms()


def _run_status(args: list[str]) -> None:
    show_status(args[1])


def _run_logs(args: list[str]) -> None:
    show_logs(args[1], args[2:])


def _run_exec(args: list[str]) -> int | None:
    cmd_args = args[2:]
    if cmd_args and cmd_args[0] == "--":
        cmd_args = cmd_args[1:]
    if not cmd_args:
        print("exec: missing command after uuid", file=sys.stderr)
        return 1
    exec_cmd(args[1], cmd_args)
    return 0


_HANDLERS: dict[str, tuple[Callable[[list[str]], int | None], bool]] = {
    "create": (_run_create, True),
    "rebuild": (_run_rebuild, True),
    "sync": (_run_sync, True),
    "start": (_run_start, True),
    "stop": (_run_stop, True),
    "delete": (_run_delete, True),
    "shell": (_run_shell, True),
    "exec": (_run_exec, True),
    "list": (_run_list, False),
    "status": (_run_status, True),
    "logs": (_run_logs, True),
    "kill": (_run_kill, True),
}


def _dispatch(args: list[str]) -> int:
    subcommand = args[0]
    entry = _HANDLERS.get(subcommand)
    if entry is None:
        print(f"unknown subcommand: {subcommand}", file=sys.stderr)
        return 1
    handler, needs_uuid = entry
    if needs_uuid and _require_arg(args, subcommand) is None:
        return 1
    result = handler(args)
    return 0 if result is None else result


def main(cli_args: list[str] | None = None) -> int:
    """Dispatch vm_main subcommands. Returns exit code."""
    args = sys.argv[1:] if cli_args is None else cli_args
    if not args:
        _usage()
        return 1
    return _dispatch(args)


if __name__ == "__main__":
    sys.exit(main())
