"""VM lifecycle — CLI entry point for create/rebuild/sync subcommands."""

from __future__ import annotations

import sys

from workspace.cli.vm_manager import create, rebuild, sync

if __name__ == "__main__":
    _MIN_ARGS = 2
    _SUB_CMD_ARGS = 3

    if len(sys.argv) < _MIN_ARGS:
        print(
            "usage: python -m workspace.cli.vm_main <create|rebuild|sync> <args>",
            file=sys.stderr,
        )
        sys.exit(1)

    subcommand = sys.argv[1]
    if subcommand == "create":
        if len(sys.argv) < _SUB_CMD_ARGS:
            print("create: missing config file argument", file=sys.stderr)
            sys.exit(1)
        create(sys.argv[2])
    elif subcommand == "rebuild":
        if len(sys.argv) < _SUB_CMD_ARGS:
            print("rebuild: missing uuid argument", file=sys.stderr)
            sys.exit(1)
        rebuild(sys.argv[2])
    elif subcommand == "sync":
        if len(sys.argv) < _SUB_CMD_ARGS:
            print("sync: missing uuid argument", file=sys.stderr)
            sys.exit(1)
        sync(sys.argv[2])
    else:
        print(f"unknown subcommand: {subcommand}", file=sys.stderr)
        sys.exit(1)
