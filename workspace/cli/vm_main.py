"""VM lifecycle - CLI entry point for create/rebuild/sync subcommands."""

from __future__ import annotations

import sys

from workspace.cli.vm_manager import create, rebuild
from workspace.cli.vm_sync import sync

_MIN_ARGS = 1
_SUB_CMD_ARGS = 2


def main(cli_args: list[str] | None = None) -> int:
    """Dispatch vm_main subcommands. Returns exit code.

    Accepts explicit cli_args for in-process testing.
    When None, uses sys.argv[1:].
    """
    args = sys.argv[1:] if cli_args is None else cli_args

    if len(args) < 1:
        print(
            "usage: python -m workspace.cli.vm_main <create|rebuild|sync> <args>",
            file=sys.stderr,
        )
        return 1

    subcommand = args[0]
    if subcommand == "create":
        if len(args) < _SUB_CMD_ARGS:
            print("create: missing config file argument", file=sys.stderr)
            return 1
        create(args[1])
    elif subcommand == "rebuild":
        if len(args) < _SUB_CMD_ARGS:
            print("rebuild: missing uuid argument", file=sys.stderr)
            return 1
        rebuild(args[1])
    elif subcommand == "sync":
        if len(args) < _SUB_CMD_ARGS:
            print("sync: missing uuid argument", file=sys.stderr)
            return 1
        sync(args[1])
    else:
        print(f"unknown subcommand: {subcommand}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
