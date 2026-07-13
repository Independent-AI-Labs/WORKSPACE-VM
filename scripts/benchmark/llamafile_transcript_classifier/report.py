"""Write growth-oriented benchmark reports under docs/benchmarking/."""

from __future__ import annotations

import json
import time
from pathlib import Path

from scripts.benchmark.llamafile_transcript_classifier.replay import (
    ReplayStepResult,
    SessionReplayResult,
)
from scripts.benchmark.llamafile_transcript_classifier.report_analysis import (
    build_extended_summary,
    render_extended_sections,
)
from scripts.benchmark.llamafile_transcript_classifier.types import (
    NA_CELL,
    JsonMap,
    ctx_label,
)


def _bucket_for_tokens(prompt_tokens: int, buckets: list[int]) -> int:
    for bucket in sorted(buckets):
        if prompt_tokens <= bucket:
            return bucket
    return sorted(buckets)[-1]


def _avg(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarize_replay_results(
    sessions: list[SessionReplayResult],
    size_buckets: list[int],
) -> JsonMap:
    """Aggregate step metrics by measured prompt size and growth."""
    all_steps = [
        (session.session_id, step) for session in sessions for step in session.steps
    ]

    by_bucket: dict[int, list[ReplayStepResult]] = {}
    for _session_id, step in all_steps:
        if step.prompt_tokens is None:
            continue
        bucket = _bucket_for_tokens(step.prompt_tokens, size_buckets)
        by_bucket.setdefault(bucket, []).append(step)

    bucket_summaries: list[JsonMap] = []
    for bucket in sorted(by_bucket):
        rows = by_bucket[bucket]
        passed = sum(1 for r in rows if r.score.get("passed"))
        ttfts = [r.ttft_ms for r in rows if r.ttft_ms is not None]
        totals = [r.total_ms for r in rows]
        tps_vals = [
            r.tokens_per_second for r in rows if r.tokens_per_second is not None
        ]
        prompt_toks = [r.prompt_tokens for r in rows if r.prompt_tokens is not None]
        cache_vals = [r.cache_n for r in rows if r.cache_n is not None]
        cache_ratios = [
            cache_vals[i] / prompt_toks[i]
            for i in range(min(len(cache_vals), len(prompt_toks)))
            if prompt_toks[i] > 0
        ]
        bucket_summaries.append(
            {
                "size_bucket": bucket,
                "steps": len(rows),
                "accuracy": passed / len(rows) if rows else 0.0,
                "prompt_tokens_avg": _avg([float(v) for v in prompt_toks if v]),
                "prompt_tokens_min": min(prompt_toks) if prompt_toks else None,
                "prompt_tokens_max": max(prompt_toks) if prompt_toks else None,
                "cache_n_avg": _avg([float(v) for v in cache_vals if v is not None]),
                "cache_hit_ratio_avg": _avg(cache_ratios),
                "ttft_ms_avg": _avg(ttfts),
                "total_ms_avg": _avg(totals),
                "tokens_per_second_avg": _avg(tps_vals),
            }
        )

    growth_rows = [
        {
            "session_id": session.session_id,
            "title": session.title,
            "turn_index": step.turn_index,
            "prompt_tokens": step.prompt_tokens,
            "cache_n": step.cache_n,
            "prompt_n": step.prompt_n,
            "ttft_ms": step.ttft_ms,
            "total_ms": step.total_ms,
            "tokens_per_second": step.tokens_per_second,
        }
        for session in sessions
        for step in session.steps
    ]

    overall_passed = sum(1 for _sid, step in all_steps if step.score.get("passed"))
    return {
        "steps_total": len(all_steps),
        "steps_passed": overall_passed,
        "accuracy": overall_passed / len(all_steps) if all_steps else 0.0,
        "sessions_total": len(sessions),
        "by_size_bucket": bucket_summaries,
        "growth_curve": growth_rows,
    }


def _bucket_summary_lines(rollup: JsonMap) -> list[str]:
    lines = [
        "## Summary by Measured Context Size",
        "",
        "| Bucket | Steps | Pass Rate | Prompt Tok Avg | Cache Tok Avg | "
        "Cache Hit % | TTFT ms Avg | Total ms Avg | Gen tok/s Avg |",
        "|--------|-------|-----------|----------------|---------------|"
        "------------|-------------|--------------|---------------|",
    ]
    for block in rollup["by_size_bucket"]:
        bucket = ctx_label(block["size_bucket"])
        acc = f"{block['accuracy'] * 100:.1f}%"
        pt_avg = (
            f"{block['prompt_tokens_avg']:.0f}"
            if block["prompt_tokens_avg"] is not None
            else NA_CELL
        )
        cache_avg = (
            f"{block['cache_n_avg']:.0f}"
            if block["cache_n_avg"] is not None
            else NA_CELL
        )
        cache_hit = (
            f"{block['cache_hit_ratio_avg'] * 100:.1f}%"
            if block.get("cache_hit_ratio_avg") is not None
            else NA_CELL
        )
        ttft = (
            f"{block['ttft_ms_avg']:.1f}"
            if block["ttft_ms_avg"] is not None
            else NA_CELL
        )
        total = (
            f"{block['total_ms_avg']:.1f}"
            if block["total_ms_avg"] is not None
            else NA_CELL
        )
        tps = (
            f"{block['tokens_per_second_avg']:.2f}"
            if block["tokens_per_second_avg"] is not None
            else NA_CELL
        )
        lines.append(
            f"| {bucket} | {block['steps']} | {acc} | {pt_avg} | {cache_avg} | "
            f"{cache_hit} | {ttft} | {total} | {tps} |"
        )
    lines.append("")
    return lines


def _session_curve_lines(sessions: list[JsonMap]) -> list[str]:
    lines = ["## Context Growth Curves (per session)", ""]
    for session in sessions:
        lines.append(f"### `{session['session_id']}`: {session.get('title', '')}")
        lines.append("")
        lines.extend(
            [
                "| Turn | Window | Rolled | Prompt Tok | Cache Tok | Prompt New | "
                "TTFT ms | Total ms | tok/s | Pass |",
                "|------|--------|--------|------------|-----------|------------|"
                "---------|---------|-------|------|",
            ]
        )
        for step in session.get("steps", []):
            ok = "PASS" if step["score"]["passed"] else "FAIL"
            window_start = step.get("window_start_turn", step["turn_index"])
            window_label = (
                f"{window_start}-{step['turn_index']} "
                f"({step.get('window_turn_count', NA_CELL)})"
            )
            rolled = "yes" if step.get("window_rolled") else "no"
            lines.append(
                f"| {step['turn_index']} | {window_label} | {rolled} | "
                f"{step.get('prompt_tokens', NA_CELL)} | "
                f"{step.get('cache_n', NA_CELL)} | {step.get('prompt_n', NA_CELL)} | "
                f"{step.get('ttft_ms', NA_CELL)} | {step.get('total_ms', NA_CELL)} | "
                f"{step.get('tokens_per_second', NA_CELL)} | {ok} |"
            )
        lines.append("")
    return lines


def _transcript_source_lines(source: JsonMap) -> list[str]:
    lines = [
        "## Transcript Source",
        "",
        f"- **DB path:** `{source.get('db_path', 'n/a')}`",
        f"- **Catalog size:** {source.get('catalog_size', 'n/a')} sessions",
    ]
    selected = source.get("selected")
    if selected:
        lines.append("- **Selected sessions:**")
        lines.extend(
            f"  - `{item['session_id']}`: {item['title']} "
            f"(bucket={ctx_label(item['bucket_tokens'])}, "
            f"est={item['estimated_tokens']} tok, turns={item['turn_count']})"
            for item in selected
        )
    lines.append("")
    return lines


def render_markdown(report: JsonMap) -> str:
    """Render an aggregated markdown report from the benchmark payload."""
    rollup = report["summary"]
    benchmark_name = report.get("benchmark_name", report.get("benchmark", "classifier"))
    extended = report.get("extended") or build_extended_summary(
        report, report.get("duration_s")
    )

    lines = [
        f"# {benchmark_name}: Incremental Transcript Classifier Report",
        "",
        *render_extended_sections(report, extended),
        *_bucket_summary_lines(rollup),
        *_session_curve_lines(report.get("sessions", [])),
    ]

    failures = [
        step
        for session in report.get("sessions", [])
        for step in session.get("steps", [])
        if not step["score"]["passed"]
    ]
    if failures:
        lines.extend(["## Failure Details", ""])
        for step in failures[:20]:
            lines.extend(
                [
                    f"### turn {step['turn_index']}",
                    "",
                    f"- **Notes:** {step['score']['notes']}",
                    f"- **Response:** {step.get('response_preview', '')}",
                    "",
                ]
            )

    lines.extend(_transcript_source_lines(report.get("transcript_source", {})))
    return "\n".join(lines)


def write_reports(
    repo_root: Path,
    config: JsonMap,
    report: JsonMap,
    config_text: str,
) -> Path:
    """Write report.md, report.json, config snapshot, and latest symlink."""
    benchmark_meta = config.get("benchmark", {})
    benchmark_name = str(benchmark_meta.get("name", "llamafile-transcript-classifier"))
    reports_dir_name = str(benchmark_meta.get("reports_dir", "docs/benchmarking"))

    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    backend = str(report.get("backend", "unknown"))
    run_dir = repo_root / reports_dir_name / benchmark_name / backend / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    md_path = run_dir / "report.md"
    json_path = run_dir / "report.json"
    snapshot_path = run_dir / "config.snapshot.yaml"

    md_path.write_text(render_markdown(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    snapshot_path.write_text(config_text, encoding="utf-8")

    latest_link = repo_root / reports_dir_name / benchmark_name / backend / "latest.md"
    if latest_link.is_symlink() or latest_link.exists():
        latest_link.unlink()
    latest_link.symlink_to(run_dir / "report.md")

    return md_path
