"""Derived analytics for thorough benchmark reports."""

from __future__ import annotations

from scripts.benchmark.llamafile_transcript_classifier.types import (
    DEFAULT_MAX_CONTEXT_TOKENS,
    NA_CELL,
    JsonMap,
    ctx_label,
)


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((pct / 100.0) * (len(ordered) - 1))
    return ordered[max(0, min(index, len(ordered) - 1))]


def _collect_all_steps(sessions: list) -> list[JsonMap]:
    all_steps: list[JsonMap] = []
    for session in sessions:
        all_steps.extend(
            {
                "session_id": session["session_id"],
                "title": session.get("title", ""),
                "bucket_tokens": session.get("bucket_tokens"),
                **step,
            }
            for step in session.get("steps", [])
        )
    return all_steps


def _gather_step_metrics(
    all_steps: list[JsonMap],
) -> tuple[
    list[float],
    list[tuple[int, float]],
    list[tuple[int, float]],
    dict[str, list[float]],
]:
    cache_ratios: list[float] = []
    ttft_by_prompt: list[tuple[int, float]] = []
    total_by_prompt: list[tuple[int, float]] = []
    category_values: dict[str, list[float]] = {}

    for step in all_steps:
        prompt = step.get("prompt_tokens")
        cache_n = step.get("cache_n")
        if isinstance(prompt, int) and prompt > 0 and isinstance(cache_n, int):
            cache_ratios.append(cache_n / prompt)
        if isinstance(prompt, int) and step.get("ttft_ms") is not None:
            ttft_by_prompt.append((prompt, float(step["ttft_ms"])))
        if isinstance(prompt, int) and step.get("total_ms") is not None:
            total_by_prompt.append((prompt, float(step["total_ms"])))
        scores = step.get("score", {}).get("parsed_scores", {})
        if isinstance(scores, dict):
            for cat_id, value in scores.items():
                if isinstance(value, int | float):
                    category_values.setdefault(str(cat_id), []).append(float(value))

    return cache_ratios, ttft_by_prompt, total_by_prompt, category_values


def _build_session_summaries(sessions: list) -> list[JsonMap]:
    session_summaries: list[JsonMap] = []
    for session in sessions:
        steps = session.get("steps", [])
        prompts = [
            s["prompt_tokens"] for s in steps if isinstance(s.get("prompt_tokens"), int)
        ]
        caches = [s["cache_n"] for s in steps if isinstance(s.get("cache_n"), int)]
        ttfts = [s["ttft_ms"] for s in steps if s.get("ttft_ms") is not None]
        totals = [s["total_ms"] for s in steps if s.get("total_ms") is not None]
        passed = sum(1 for s in steps if s.get("score", {}).get("passed"))
        ratios = [
            caches[i] / prompts[i]
            for i in range(min(len(prompts), len(caches)))
            if prompts[i] > 0
        ]
        session_summaries.append(
            {
                "session_id": session["session_id"],
                "title": session.get("title", ""),
                "target_bucket": session.get("bucket_tokens"),
                "steps": len(steps),
                "steps_passed": passed,
                "turn_count": steps[-1]["turn_index"] if steps else 0,
                "prompt_tokens_min": min(prompts) if prompts else None,
                "prompt_tokens_max": max(prompts) if prompts else None,
                "cache_ratio_avg": _avg(ratios),
                "ttft_ms_first": ttfts[0] if ttfts else None,
                "ttft_ms_last": ttfts[-1] if ttfts else None,
                "total_ms_sum": sum(totals) if totals else None,
            }
        )
    return session_summaries


def _build_category_stats(category_values: dict[str, list[float]]) -> list[JsonMap]:
    category_stats: list[JsonMap] = []
    for cat_id in sorted(category_values):
        vals = category_values[cat_id]
        category_stats.append(
            {
                "category_id": cat_id,
                "count": len(vals),
                "avg": _avg(vals),
                "min": min(vals),
                "max": max(vals),
            }
        )
    return category_stats


def build_extended_summary(
    report: JsonMap,
    duration_s: float | None = None,
) -> JsonMap:
    """Compute cache, latency, scoring, and per-session analytics."""
    sessions = report.get("sessions", [])
    all_steps = _collect_all_steps(sessions)
    cache_ratios, ttft_by_prompt, total_by_prompt, category_values = (
        _gather_step_metrics(all_steps)
    )

    ttft_vals = [v for _p, v in ttft_by_prompt]
    total_vals = [v for _p, v in total_by_prompt]
    prompt_vals = [p for p, _v in ttft_by_prompt]

    session_summaries = _build_session_summaries(sessions)
    category_stats = _build_category_stats(category_values)
    latency_bins = _latency_bins(all_steps, report.get("size_buckets", []))

    return {
        "duration_s": duration_s,
        "steps_total": len(all_steps),
        "cache_hit_ratio_avg": _avg(cache_ratios),
        "cache_hit_ratio_median": _median(cache_ratios),
        "ttft_ms_avg": _avg(ttft_vals),
        "ttft_ms_median": _median(ttft_vals),
        "ttft_ms_p95": _percentile(ttft_vals, 95),
        "total_ms_avg": _avg(total_vals),
        "total_ms_sum": sum(total_vals) if total_vals else None,
        "prompt_tokens_avg": _avg([float(p) for p in prompt_vals]),
        "prompt_tokens_max": max(prompt_vals) if prompt_vals else None,
        "session_summaries": session_summaries,
        "category_stats": category_stats,
        "latency_bins": latency_bins,
    }


def _latency_bins(
    steps: list[JsonMap],
    size_buckets: list[int],
) -> list[JsonMap]:
    if not size_buckets:
        return []
    bins: dict[int, list[JsonMap]] = {}
    ordered = sorted(size_buckets)
    for step in steps:
        prompt = step.get("prompt_tokens")
        if not isinstance(prompt, int):
            continue
        bucket = ordered[-1]
        for candidate in ordered:
            if prompt <= candidate:
                bucket = candidate
                break
        bins.setdefault(bucket, []).append(step)

    rows: list[JsonMap] = []
    for bucket in ordered:
        bucket_steps = bins.get(bucket, [])
        if not bucket_steps:
            continue
        ttfts = [
            float(s["ttft_ms"]) for s in bucket_steps if s.get("ttft_ms") is not None
        ]
        totals = [float(s["total_ms"]) for s in bucket_steps]
        caches = [
            s["cache_n"] for s in bucket_steps if isinstance(s.get("cache_n"), int)
        ]
        prompts = [
            s["prompt_tokens"]
            for s in bucket_steps
            if isinstance(s.get("prompt_tokens"), int)
        ]
        ratios = [
            caches[i] / prompts[i]
            for i in range(min(len(caches), len(prompts)))
            if prompts[i] > 0
        ]
        rows.append(
            {
                "size_bucket": bucket,
                "steps": len(bucket_steps),
                "cache_hit_ratio_avg": _avg(ratios),
                "ttft_ms_avg": _avg(ttfts),
                "ttft_ms_median": _median(ttfts),
                "total_ms_avg": _avg(totals),
                "prompt_tokens_avg": _avg([float(p) for p in prompts]),
            }
        )
    return rows


def _render_executive_summary(
    report: JsonMap,
    extended: JsonMap,
) -> list[str]:
    lines: list[str] = []
    summary = report.get("summary", {})
    max_ctx = ctx_label(int(report.get("max_context_tokens", 0)))

    lines.append("## Executive Summary")
    lines.append("")
    lines.append(
        f"This run replayed **{summary.get('sessions_total', 0)}** "
        f"OpenCode transcripts with incremental KV-cache reuse up to "
        f"**{max_ctx}** context. "
        f"**{summary.get('steps_passed', 0)}/{summary.get('steps_total', 0)}** "
        f"classification steps produced valid YAML "
        f"({summary.get('accuracy', 0) * 100:.1f}% pass rate)."
    )
    if extended.get("duration_s") is not None:
        lines.append(
            f"Wall-clock duration: **{extended['duration_s']:.1f}s** "
            f"({extended['duration_s'] / 60:.1f} min)."
        )
    if extended.get("cache_hit_ratio_avg") is not None:
        lines.append(
            f"Average cache hit ratio (cache_n / prompt_tokens): "
            f"**{extended['cache_hit_ratio_avg'] * 100:.1f}%**."
        )
    if extended.get("prompt_tokens_max") is not None:
        lines.append(
            f"Peak measured prompt size: **{extended['prompt_tokens_max']}** tokens."
        )
    probe = report.get("cache_probe")
    if probe:
        erase = "supported" if probe.get("slot_erase_supported") else "not supported"
        probe_status = "PASS" if probe.get("cache_working") else "FAIL"
        lines.append(f"Preflight cache probe: **{probe_status}** (slot erase {erase}).")
    lines.append("")
    return lines


def _render_run_configuration(report: JsonMap) -> list[str]:
    lines: list[str] = []
    bucket_labels = ", ".join(ctx_label(b) for b in report.get("size_buckets", []))

    lines.append("## Run Configuration")
    lines.append("")
    lines.append(
        f"- **Max context:** {ctx_label(int(report.get('max_context_tokens', 0)))}"
    )
    lines.append(f"- **Size buckets:** {bucket_labels}")
    lines.append(f"- **Base URL:** {report.get('base_url', 'n/a')}")
    lines.append(f"- **Backend:** {report.get('backend', 'unknown')}")
    if report.get("started_at"):
        lines.append(f"- **Started:** {report['started_at']}")
    lines.append(f"- **Finished:** {report.get('finished_at', 'n/a')}")
    lines.append("")
    return lines


def _render_latency_section(extended: JsonMap) -> list[str]:
    lines: list[str] = []
    lines.append("## Latency and Cache Scaling")
    lines.append("")
    lines.append(
        "| Bucket | Steps | Cache Hit % | TTFT ms Avg | TTFT ms Median | "
        "Total ms Avg | Prompt Tok Avg |"
    )
    lines.append(
        "|--------|-------|-------------|-------------|----------------|"
        "-------------|----------------|"
    )
    for row in extended.get("latency_bins", []):
        cache_pct = (
            f"{row['cache_hit_ratio_avg'] * 100:.1f}"
            if row.get("cache_hit_ratio_avg") is not None
            else NA_CELL
        )
        ttft_avg = (
            f"{row['ttft_ms_avg']:.1f}"
            if row.get("ttft_ms_avg") is not None
            else NA_CELL
        )
        ttft_med = (
            f"{row['ttft_ms_median']:.1f}"
            if row.get("ttft_ms_median") is not None
            else NA_CELL
        )
        total_avg = (
            f"{row['total_ms_avg']:.1f}"
            if row.get("total_ms_avg") is not None
            else NA_CELL
        )
        prompt_avg = (
            f"{row['prompt_tokens_avg']:.0f}"
            if row.get("prompt_tokens_avg") is not None
            else NA_CELL
        )
        lines.append(
            f"| {ctx_label(row['size_bucket'])} | {row['steps']} | {cache_pct} | "
            f"{ttft_avg} | {ttft_med} | {total_avg} | {prompt_avg} |"
        )
    lines.append("")
    return lines


def _render_category_section(extended: JsonMap) -> list[str]:
    if not extended.get("category_stats"):
        return []
    lines: list[str] = []
    lines.append("## Classification Score Distribution")
    lines.append("")
    lines.append("| Category | Count | Avg | Min | Max |")
    lines.append("|----------|-------|-----|-----|-----|")
    for row in extended["category_stats"]:
        avg = f"{row['avg']:.3f}" if row.get("avg") is not None else NA_CELL
        lines.append(
            f"| {row['category_id']} | {row['count']} | {avg} | "
            f"{row['min']:.3f} | {row['max']:.3f} |"
        )
    lines.append("")
    return lines


def _render_session_summary_table(extended: JsonMap) -> list[str]:
    lines: list[str] = []
    lines.append("## Per-Session Summary")
    lines.append("")
    lines.append(
        "| Session | Target | Steps | Pass | Turns | Prompt Min | Prompt Max | "
        "Cache Hit % | TTFT First | TTFT Last | Total ms |"
    )
    lines.append(
        "|---------|--------|-------|------|-------|------------|------------|"
        "-------------|------------|-----------|----------|"
    )
    for row in extended.get("session_summaries", []):
        target = (
            ctx_label(int(row["target_bucket"]))
            if row.get("target_bucket") is not None
            else NA_CELL
        )
        cache_pct = (
            f"{row['cache_ratio_avg'] * 100:.1f}"
            if row.get("cache_ratio_avg") is not None
            else NA_CELL
        )
        ttft_first = (
            f"{row['ttft_ms_first']:.0f}"
            if row.get("ttft_ms_first") is not None
            else NA_CELL
        )
        ttft_last = (
            f"{row['ttft_ms_last']:.0f}"
            if row.get("ttft_ms_last") is not None
            else NA_CELL
        )
        total_sum = (
            f"{row['total_ms_sum']:.0f}"
            if row.get("total_ms_sum") is not None
            else NA_CELL
        )
        prompt_min = row.get("prompt_tokens_min", NA_CELL)
        prompt_max = row.get("prompt_tokens_max", NA_CELL)
        lines.append(
            f"| `{row['session_id']}` | {target} | {row['steps']} | "
            f"{row['steps_passed']}/{row['steps']} | {row['turn_count']} | "
            f"{prompt_min} | {prompt_max} | "
            f"{cache_pct} | {ttft_first} | {ttft_last} | {total_sum} |"
        )
    lines.append("")
    return lines


def _render_methodology(report: JsonMap) -> list[str]:
    lines: list[str] = []
    lines.append("## Methodology")
    lines.append("")
    replay_mode = report.get("replay_mode", "rolling_window")
    max_ctx = ctx_label(
        int(report.get("max_context_tokens", DEFAULT_MAX_CONTEXT_TOKENS))
    )
    if replay_mode == "rolling_window":
        lines.append(
            "Each OpenCode session is replayed turn-by-turn on a pinned llamafile "
            "slot with `cache_prompt=true`. At each turn the classifier sees a fixed "
            f"{max_ctx} rolling window: the last n user/assistant pairs that fit "
            "under the token budget. When the transcript grows, oldest turns drop "
            "from the front. Metrics are recorded per turn: window bounds, cache "
            "reuse, TTFT, total latency, and generation throughput."
        )
    else:
        lines.append(
            "Each OpenCode session is replayed turn-by-turn on a pinned llamafile "
            "slot with `cache_prompt=true`. Every step sends the cumulative "
            "transcript (all prior user/assistant pairs) plus a classification task. "
            "Metrics are recorded per turn: prompt size, cache reuse, TTFT, total "
            "latency, and generation throughput. Steps continue until "
            "`max_context_tokens` is exceeded."
        )
    lines.append("")
    return lines


def render_extended_sections(report: JsonMap, extended: JsonMap) -> list[str]:
    """Render thorough markdown sections from extended analytics."""
    lines: list[str] = []
    lines.extend(_render_executive_summary(report, extended))
    lines.extend(_render_run_configuration(report))
    lines.extend(_render_latency_section(extended))
    lines.extend(_render_category_section(extended))
    lines.extend(_render_session_summary_table(extended))
    lines.extend(_render_methodology(report))
    return lines
