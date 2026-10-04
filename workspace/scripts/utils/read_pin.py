"""Read a dotted key from a YAML pins file and print its value.

bootstrap_qemu.sh reads ``qemu.source_url`` from ``res/qemu-pins.yaml``. The
read lives here, in a scanned source file, instead of an inline interpreter
payload. A missing key prints nothing and exits 0; an unreadable or
malformed file raises.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_EXPECTED_ARGS = 2


def read_pin(data: object, dotted_key: str) -> object:
    """Return the value at ``dotted_key`` or None when any segment is absent."""
    value = data
    for part in dotted_key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def main(argv: list[str]) -> int:
    if len(argv) != _EXPECTED_ARGS:
        print(f"usage: {Path(__file__).name} <pins.yaml> <dotted.key>", file=sys.stderr)
        return 2
    raw = yaml.safe_load(Path(argv[0]).read_text(encoding="utf-8"))
    value = read_pin(raw, argv[1])
    if value is not None:
        print(value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
