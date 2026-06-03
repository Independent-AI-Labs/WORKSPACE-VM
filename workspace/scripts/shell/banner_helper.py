"""Banner helper: renders extension banner and extra-info output.

Replaces bash YAML parsing for the AMI banner display.
Imports shared logic from extension_registry in the same directory.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from typing import TYPE_CHECKING, NamedTuple

from workspace.scripts.shell.banner_log import banner_log_session, make_check_hook
from workspace.scripts.shell.extension_registry import (
    DEFAULT_CATEGORY_PROPS,
    HealthCheckResult,
    Status,
    check_dep,
    discover_manifests,
    find_ami_root,
    group_by_category,
    resolve_extensions,
    run_check,
)
from workspace.scripts.shell.version_enforcer import enforce_versions

if TYPE_CHECKING:
    from pathlib import Path

    from workspace.scripts.shell.banner_log import LogFn
    from workspace.scripts.shell.extension_registry import ResolvedExtension

# ANSI color codes matching ami-banner.sh
_COLORS = {
    "gold": "\033[38;5;214m",
    "cyan": "\033[0;36m",
    "pink": "\033[38;5;205m",
    "purple": "\033[38;5;99m",
    "blue": "\033[0;34m",
    "red": "\033[38;5;203m",
    "green": "\033[0;32m",
}


class _Style:
    DIM = "\033[2m"
    NC = "\033[0m"
    BOLD = "\033[1m"


def _enable_plain() -> None:
    _Style.DIM = ""
    _Style.NC = ""
    _Style.BOLD = ""


# Fallback props for unknown categories
_UNKNOWN_ICON = "\U0001f539"  # blue diamond
_UNKNOWN_COLOR = "green"

_NAME_PAD = 20  # column width for extension name alignment

# Hard cap so the banner stays within an 80-column terminal. The extension
# line layout is:  "  > {name}{pad}\u2192 {description} {suffix}"
# where the leading marker block (`"  > "`) plus name plus pad lands the
# arrow at column 24, and the suffix is short (`"v1.2.3"` or `"\u2713"`).
# Reserve `_LINE_BUDGET` printable cols for the whole line and truncate the
# description with an ellipsis to make it fit. Features and dim-text lines
# are wrapped separately by `_wrap_features`.
_LINE_BUDGET = 80
_FEATURES_PAD = _NAME_PAD + 4  # indent under the description
_ELLIPSIS = "\u2026"


# ---------------------------------------------------------------------------
# Banner mode
# ---------------------------------------------------------------------------


def _color_for(category: str) -> str:
    """Return ANSI color escape for a category."""
    props = DEFAULT_CATEGORY_PROPS.get(category, {})
    color_name = props.get("color", _UNKNOWN_COLOR)
    return _COLORS.get(color_name, _COLORS["green"])


def _icon_for(category: str) -> str:
    props = DEFAULT_CATEGORY_PROPS.get(category, {})
    icon: str = props.get("icon", _UNKNOWN_ICON)
    return icon


def _title_for(category: str) -> str:
    props = DEFAULT_CATEGORY_PROPS.get(category, {})
    title: str = props.get("title", category.title())
    return title


def _has_failed_container_dep(ext: ResolvedExtension, root: Path) -> bool:
    """Return True if any container dep is missing."""
    return bool(_failed_container_deps(ext, root))


def _failed_container_deps(ext: ResolvedExtension, root: Path) -> list[str]:
    """Return names of declared container deps that are not currently running."""
    return [
        dep.get("container", dep.get("name", "?"))
        for dep in ext.entry.get("deps", [])
        if dep.get("type") == "container" and not check_dep(dep, root)
    ]


def _visible_len(suffix: str) -> int:
    """Length of *suffix* with ANSI escape sequences stripped."""
    out: list[str] = []
    i = 0
    while i < len(suffix):
        if suffix[i] == "\x1b":
            # Skip CSI sequence: ESC [ ... letter
            j = i + 1
            if j < len(suffix) and suffix[j] == "[":
                j += 1
                while j < len(suffix) and not suffix[j].isalpha():
                    j += 1
                i = j + 1
                continue
        out.append(suffix[i])
        i += 1
    return len(out)


def _truncate_to_fit(desc: str, suffix_visible: int) -> str:
    """Trim *desc* so the assembled line stays inside ``_LINE_BUDGET``.

    Visible layout (no ANSI):  ``  > {name}{pad}\u2192 {desc} {suffix}``
    Fixed prefix is 4 cols (``"  > "``); the name + pad sums to
    ``_NAME_PAD`` cols regardless of name length; the arrow + space is 2
    cols; the trailing space before suffix is 1 col. The description has
    therefore ``budget = _LINE_BUDGET - 4 - _NAME_PAD - 2 - 1 - suffix_visible``
    cols available before the truncation ellipsis.
    """
    overhead = 4 + _NAME_PAD + 2 + 1 + suffix_visible
    budget = _LINE_BUDGET - overhead
    if budget <= 0 or len(desc) <= budget:
        return desc
    # Reserve 1 col for the ellipsis.
    return desc[: max(0, budget - 1)].rstrip() + _ELLIPSIS


def _format_partial_line(
    ext: ResolvedExtension,
    color: str,
    suffix: str,
) -> str:
    """Format an extension line with a trailing suffix (countdown or result)."""
    name = ext.entry["name"]
    desc = ext.entry.get("description", "")
    desc = _truncate_to_fit(desc, _visible_len(suffix))
    pad = max(1, _NAME_PAD - len(name))
    return f"  {color}> {name}{_Style.NC}{' ' * pad}\u2192 {desc} {suffix}"


def _format_features(ext: ResolvedExtension) -> str | None:
    features = ext.entry.get("features")
    if not features:
        return None
    joined = ", ".join(features)
    indent = " " * _FEATURES_PAD
    budget = _LINE_BUDGET - _FEATURES_PAD
    if len(joined) > budget:
        joined = joined[: max(0, budget - 1)].rstrip() + _ELLIPSIS
    return f"{indent}{_Style.DIM}{joined}{_Style.NC}"


def _run_check_with_countdown(
    ext: ResolvedExtension,
    root: Path,
    color: str,
    log: LogFn | None = None,
) -> HealthCheckResult:
    """Run check in a background thread with animated countdown."""
    result_holder: list[HealthCheckResult | None] = [None]
    check_cfg = ext.entry.get("check", {})
    timeout = min(check_cfg.get("timeout", 5), 5)
    hook = make_check_hook(log, ext.entry["name"]) if log is not None else None

    def _do_check() -> None:
        result_holder[0] = run_check(ext.entry, root, log_hook=hook)

    thread = threading.Thread(target=_do_check, daemon=True)
    thread.start()

    start = time.monotonic()
    while thread.is_alive() and (time.monotonic() - start) < timeout:
        remaining = max(0.0, timeout - (time.monotonic() - start))
        secs = int(remaining)
        centis = int((remaining - secs) * 100)
        countdown = f"[{secs:02d}:{centis:02d}]"
        line = _format_partial_line(ext, color, countdown)
        sys.stdout.write(f"\r{line}")
        sys.stdout.flush()
        time.sleep(0.1)

    thread.join(timeout=0.5)

    if result_holder[0] is None:
        return HealthCheckResult(
            healthy=False,
            version=None,
            version_ok=None,
            version_reason=None,
        )
    return result_holder[0]


class _BannerCtx(NamedTuple):
    """Rendering context passed through the banner pipeline."""

    quiet: bool
    is_tty: bool
    log: LogFn | None


def _print_extension(
    ext: ResolvedExtension,
    root: Path,
    color: str,
    ctx: _BannerCtx,
) -> None:
    """Print a single extension line with optional health check."""
    has_check = bool(ext.entry.get("check")) and not ctx.quiet
    failed_containers = _failed_container_deps(ext, root)
    skip_check = bool(failed_containers)

    version: str | None = None
    health_ok = True
    version_ok: bool | None = None
    version_reason: str | None = None

    if has_check and not skip_check:
        hook = (
            make_check_hook(ctx.log, ext.entry["name"]) if ctx.log is not None else None
        )
        if ctx.is_tty:
            result = _run_check_with_countdown(ext, root, color, ctx.log)
            # Clear the countdown line before printing final result
            sys.stdout.write("\r\033[2K")
            sys.stdout.flush()
        else:
            result = run_check(ext.entry, root, log_hook=hook)
        health_ok, version = result.healthy, result.version
        version_ok, version_reason = result.version_ok, result.version_reason
    elif ctx.log is not None:
        reason = (
            "quiet"
            if ctx.quiet
            else ("container-dep failed" if skip_check else "no check")
        )
        ctx.log(
            {
                "event": "check_skipped",
                "name": ext.entry["name"],
                "reason": reason,
            },
        )

    # Build status suffix
    green = _COLORS["green"]
    red = _COLORS["red"]
    yellow = _COLORS["gold"]
    if version_ok is False:
        label = version_reason or "version mismatch"
        suffix = f"{yellow}v{version or '?'} \u26a0 {label}{_Style.NC}"
    elif version:
        suffix = f"{green}v{version}{_Style.NC}"
    elif skip_check:
        # Don't render green ✓ when we never ran the check. INCIDENT-2026-
        # 05-05: kcadm needs `podman exec` into ami-keycloak; if the
        # container isn't running we skip the live --help and previously
        # defaulted to ✓ (because health_ok stayed True), then later the
        # user's actual `kcadm` invocation would fail with no warning.
        # Surface the missing container so the user knows what to start.
        joined = ", ".join(failed_containers)
        suffix = f"{yellow}\u26a0 container not running: {joined}{_Style.NC}"
    elif health_ok:
        suffix = f"{green}\u2713{_Style.NC}"
    else:
        suffix = f"{red}\u2717{_Style.NC}"

    line = _format_partial_line(ext, color, suffix)
    print(line)

    feat_line = _format_features(ext)
    if feat_line:
        print(feat_line)


def _log_resolution_snapshot(resolved: list[ResolvedExtension], log: LogFn) -> None:
    """Emit one 'resolved' record per extension, including status and reason."""
    for ext in resolved:
        log(
            {
                "event": "resolved",
                "name": ext.entry["name"],
                "manifest": str(ext.manifest_path),
                "status": ext.status.value,
                "reason": ext.reason,
                "binary": ext.entry.get("binary", ""),
                "category": ext.entry.get("category", ""),
            },
        )


def output_banner(
    resolved: list[ResolvedExtension],
    root: Path,
    *,
    quiet: bool = False,
) -> None:
    """Render the full extension banner to stdout."""
    is_tty = sys.stdout.isatty()
    by_category = group_by_category(resolved)

    with banner_log_session(root, "banner") as log:
        _log_resolution_snapshot(resolved, log)
        ctx = _BannerCtx(quiet=quiet, is_tty=is_tty, log=log)
        for cat_name, extensions in by_category:
            # Check if any visible extensions exist in this category
            visible = [
                e
                for e in extensions
                if e.status not in (Status.UNAVAILABLE, Status.HIDDEN)
            ]
            if not visible:
                continue

            color = _color_for(cat_name)
            icon = _icon_for(cat_name)
            title = _title_for(cat_name)
            print(f"{color}{icon} {title}:{_Style.NC}")
            print()

            for ext in visible:
                _print_extension(ext, root, color, ctx)
                print()

            sys.stdout.flush()


# ---------------------------------------------------------------------------
# Extras and doctor modes
# ---------------------------------------------------------------------------

_STATUS_PAD = 18  # column width for name in extras/doctor output


def _print_hidden(exts: list[ResolvedExtension]) -> None:
    print(f"{_Style.BOLD}Hidden Extensions:{_Style.NC}")
    for ext in exts:
        name = ext.entry["name"]
        desc = ext.entry.get("description", "")
        pad = max(1, _STATUS_PAD - len(name))
        print(f"  {name}{' ' * pad}{desc}")
    print()


def _print_degraded(exts: list[ResolvedExtension]) -> None:
    print(f"{_Style.BOLD}Degraded Extensions:{_Style.NC}")
    yellow = _COLORS["gold"]
    for ext in exts:
        name = ext.entry["name"]
        desc = ext.entry.get("description", "")
        pad = max(1, _STATUS_PAD - len(name))
        print(f"  {name}{' ' * pad}{desc}  {yellow}DEGRADED{_Style.NC} ({ext.reason})")
    print()


def _print_mismatched(exts: list[ResolvedExtension]) -> None:
    print(f"{_Style.BOLD}Version-Mismatched Extensions:{_Style.NC}")
    yellow = _COLORS["gold"]
    for ext in exts:
        name = ext.entry["name"]
        desc = ext.entry.get("description", "")
        pad = max(1, _STATUS_PAD - len(name))
        print(
            f"  {name}{' ' * pad}{desc}"
            f"  {yellow}VERSION_MISMATCH{_Style.NC} ({ext.reason})",
        )
    print()


def _print_unavailable(exts: list[ResolvedExtension]) -> None:
    print(f"{_Style.BOLD}Unavailable Extensions:{_Style.NC}")
    red = _COLORS["red"]
    for ext in exts:
        name = ext.entry["name"]
        desc = ext.entry.get("description", "")
        hint = ext.entry.get("installHint", "")
        pad = max(1, _STATUS_PAD - len(name))
        line = f"  {name}{' ' * pad}{desc}  {red}UNAVAILABLE{_Style.NC} ({ext.reason})"
        if hint:
            line += f" (install: {hint})"
        print(line)
    print()


def output_extras(resolved: list[ResolvedExtension], root: Path | None = None) -> None:
    """List hidden extensions (the opt-in 'extras' menu)."""
    del root  # no log session for a pure readout
    hidden = [e for e in resolved if e.status == Status.HIDDEN]
    if hidden:
        _print_hidden(hidden)
    else:
        print("No hidden extensions.")


def output_doctor(
    resolved: list[ResolvedExtension],
    root: Path | None = None,
) -> None:
    """Diagnose degraded, version-mismatched, and unavailable extensions."""
    if root is not None:
        with banner_log_session(root, "doctor") as log:
            _log_resolution_snapshot(resolved, log)
    degraded = [e for e in resolved if e.status == Status.DEGRADED]
    mismatched = [e for e in resolved if e.status == Status.VERSION_MISMATCH]
    unavailable = [e for e in resolved if e.status == Status.UNAVAILABLE]

    if degraded:
        _print_degraded(degraded)
    if mismatched:
        _print_mismatched(mismatched)
    if unavailable:
        _print_unavailable(unavailable)

    if not degraded and not mismatched and not unavailable:
        print("No problems detected.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for banner_helper."""
    parser = argparse.ArgumentParser(
        prog="run",
        description=("Extension display helper (banner, extras, doctor)."),
    )
    parser.add_argument(
        "--mode",
        choices=["banner", "extras", "doctor"],
        default="banner",
        help="Output mode: banner (default), extras, or doctor",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Skip health/version checks for faster output",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Strip ANSI color codes (machine-readable output)",
    )
    args = parser.parse_args()

    if args.plain:
        for k in _COLORS:
            _COLORS[k] = ""
        _enable_plain()

    quiet = args.quiet or os.environ.get("AMI_QUIET_MODE") == "1"

    root = find_ami_root()
    manifests = discover_manifests(root)
    resolved = resolve_extensions(manifests, root)
    # Doctor mode shows full taxonomy including version mismatches;
    # enforce constraints once up front so `doctor` and `banner` agree.
    if args.mode == "doctor":
        resolved = enforce_versions(resolved, root)

    if args.mode == "banner":
        output_banner(resolved, root, quiet=quiet)
    elif args.mode == "extras":
        output_extras(resolved, root)
    elif args.mode == "doctor":
        output_doctor(resolved, root)


if __name__ == "__main__":
    main()
