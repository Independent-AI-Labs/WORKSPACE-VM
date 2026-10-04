"""Count findings in a gitleaks JSON report.

The weekly sweep (workspace_gitleaks_sweep.sh) needs the finding count for
its summary email. Parsing lives here, in a scanned source file, instead of
an inline interpreter payload so it is reviewable and testable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def count_findings(report_path: Path) -> int:
    """Return the number of findings in a gitleaks JSON report.

    Raises:
        TypeError: the report is not a JSON array.
        OSError: the report cannot be read.
    """
    data = json.loads(report_path.read_text(encoding="utf-8"))
    if data is None:
        return 0
    if not isinstance(data, list):
        msg = f"gitleaks report is not a JSON array: {report_path}"
        raise TypeError(msg)
    return len(data)


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(f"usage: {Path(__file__).name} <gitleaks-report.json>", file=sys.stderr)
        return 2
    print(count_findings(Path(argv[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
