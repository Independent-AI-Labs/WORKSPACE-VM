"""Single entrypoint: python3 -m scripts.benchmark.llamafile_transcript_classifier"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

from scripts.benchmark.llamafile_transcript_classifier.client import (
    health_ok,
    probe_cache_reuse,
)
from scripts.benchmark.llamafile_transcript_classifier.config import (
    load_config,
    resolve_config_path,
)
from scripts.benchmark.llamafile_transcript_classifier.replay import (
    ReplaySessionRequest,
    replay_session,
)
from scripts.benchmark.llamafile_transcript_classifier.report import (
    summarize_replay_results,
    write_reports,
)
from scripts.benchmark.llamafile_transcript_classifier.report_analysis import (
    build_extended_summary,
)
from scripts.benchmark.llamafile_transcript_classifier.sessions import (
    select_benchmark_sessions,
)
from scripts.benchmark.llamafile_transcript_classifier.transcripts import (
    discover_session_catalog,
    load_session_transcript,
    resolve_db_path,
    sync_fixture_cache,
)
from scripts.benchmark.llamafile_transcript_classifier.types import (
    CLASSIFICATION_CATEGORY_COUNT,
    JsonMap,
    ctx_label,
)


def _category_ids(config: JsonMap) -> list[str]:
    return [str(item["id"]) for item in config.get("categories", [])]


def _print_console_summary(report: JsonMap) -> None:
    rollup = report["summary"]
    print("=" * 72)
    print("LLAMAFILE INCREMENTAL TRANSCRIPT CLASSIFIER BENCHMARK")
    print(f"base_url: {report['base_url']}")
    print(f"finished: {report['finished_at']}")
    print(f"report: {report['report_path']}")
    print("-" * 72)
    print(
        f"overall pass rate: {rollup['steps_passed']}/{rollup['steps_total']} "
        f"({rollup['accuracy'] * 100:.1f}%)"
    )
    print(f"sessions replayed: {rollup['sessions_total']}")
    if report.get("cache_probe"):
        probe = report["cache_probe"]
        print(
            f"cache probe: {'ok' if probe.get('cache_working') else 'FAIL'} "
            f"(second cache_n={probe.get('second_cache_n')})"
        )
    for block in rollup["by_size_bucket"]:
        bucket_k = block["size_bucket"] // 1024
        print(f"\n[{bucket_k}K bucket]")
        print(f"  steps: {block['steps']}")
        print(f"  pass rate: {block['accuracy'] * 100:.1f}%")
        if block["prompt_tokens_avg"] is not None:
            print(
                f"  prompt tokens: avg={block['prompt_tokens_avg']:.0f} "
                f"min={block['prompt_tokens_min']} max={block['prompt_tokens_max']}"
            )
        if block["cache_n_avg"] is not None:
            print(f"  cache tokens avg: {block['cache_n_avg']:.0f}")
        if block["ttft_ms_avg"] is not None:
            print(f"  TTFT ms avg: {block['ttft_ms_avg']:.1f}")
        if block["total_ms_avg"] is not None:
            print(f"  total latency ms avg: {block['total_ms_avg']:.1f}")
        if block["tokens_per_second_avg"] is not None:
            print(f"  gen tok/s avg: {block['tokens_per_second_avg']:.2f}")
    print("=" * 72)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Llamafile incremental transcript classifier benchmark."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=(
            "Config YAML (default: auto-discover under "
            "benchmarks/**/transcript_classifier/)"
        ),
    )
    parser.add_argument(
        "--session",
        action="append",
        default=None,
        help="Subset of session ids to replay (repeatable)",
    )
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument(
        "--backend",
        default=None,
        help="Backend label for reports (default: LLAMAFILE_GPU env or 'unknown')",
    )
    parser.add_argument(
        "--skip-cache-probe",
        action="store_true",
        help="Skip preflight KV cache reuse probe",
    )
    args = parser.parse_args(argv)
    backend = args.backend or os.environ.get("LLAMAFILE_GPU") or "unknown"
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    run_started = time.perf_counter()

    config_path = resolve_config_path(args.config)
    config_text = config_path.read_text(encoding="utf-8")
    config = load_config(config_path)
    repo_root = Path(str(config["repo_root"]))
    category_ids = _category_ids(config)
    if len(category_ids) != CLASSIFICATION_CATEGORY_COUNT:
        print(
            f"error: expected {CLASSIFICATION_CATEGORY_COUNT} categories, "
            f"found {len(category_ids)}",
            file=sys.stderr,
        )
        return 1

    if not health_ok(args.base_url):
        print(
            f"error: llamafile server not healthy at {args.base_url}",
            file=sys.stderr,
        )
        return 1

    replay_cfg = config.get("replay", {})
    id_slot = int(replay_cfg.get("id_slot", 0))
    cache_probe_result: JsonMap | None = None
    if replay_cfg.get("preflight_cache_probe", True) and not args.skip_cache_probe:
        print("running cache preflight probe...", file=sys.stderr, flush=True)
        cache_probe_result = probe_cache_reuse(
            args.base_url,
            id_slot=id_slot,
            timeout_s=min(args.timeout, 120.0),
        )
        if not cache_probe_result.get("cache_working"):
            print(
                "warn: cache preflight probe did not observe cache reuse",
                file=sys.stderr,
            )

    source = config.get("transcript_source", {})
    db_path = resolve_db_path(source.get("db_path"))
    catalog = discover_session_catalog(db_path, source)

    if source.get("sync_on_run", True):
        sync_fixture_cache(repo_root, db_path, source, catalog)

    size_buckets = [
        int(x) for x in config.get("size_buckets", [1024, 2048, 4096, 8192])
    ]
    sessions_per_bucket = int(config.get("sessions_per_bucket", 1))

    selected = select_benchmark_sessions(
        catalog=catalog,
        config=config,
        explicit_session_ids=args.session,
    )
    print(
        f"selected {len(selected)} sessions "
        f"(buckets={len(size_buckets)}, per_bucket={sessions_per_bucket}, "
        f"long_replays={int(config.get('long_session_replays', 0))})",
        file=sys.stderr,
        flush=True,
    )

    session_results = []
    for index, pick in enumerate(selected, start=1):
        print(
            f"[{index}/{len(selected)}] replaying {pick.session_id} "
            f"(target {ctx_label(pick.bucket_tokens)}, "
            f"{pick.turn_count} turns, est={pick.estimated_tokens} tok)...",
            file=sys.stderr,
            flush=True,
        )
        session = load_session_transcript(db_path, pick.session_id, source)
        session_results.append(
            replay_session(
                ReplaySessionRequest(
                    base_url=args.base_url,
                    session=session,
                    bucket_tokens=pick.bucket_tokens,
                    config=config,
                    category_ids=category_ids,
                    timeout_s=args.timeout,
                )
            )
        )

    finished = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    duration_s = time.perf_counter() - run_started
    benchmark_meta = config.get("benchmark", {})
    summary = summarize_replay_results(session_results, size_buckets)
    report_payload: JsonMap = {
        "benchmark": str(benchmark_meta.get("name", "llamafile-transcript-classifier")),
        "benchmark_name": str(
            benchmark_meta.get("name", "llamafile-transcript-classifier")
        ),
        "backend": backend,
        "base_url": args.base_url,
        "config_path": str(config_path.relative_to(repo_root)),
        "started_at": started_at,
        "finished_at": finished,
        "duration_s": duration_s,
        "size_buckets": size_buckets,
        "max_context_tokens": int(config.get("max_context_tokens", 32768)),
        "replay_mode": str(config.get("replay", {}).get("mode", "rolling_window")),
        "sessions_per_bucket": sessions_per_bucket,
        "long_session_replays": int(config.get("long_session_replays", 0)),
        "categories": category_ids,
        "cache_probe": cache_probe_result,
        "transcript_source": {
            "db_path": str(db_path),
            "catalog_size": len(catalog),
            "selected": [pick._asdict() for pick in selected],
        },
        "summary": summary,
        "sessions": [result._asdict() for result in session_results],
    }
    report_payload["extended"] = build_extended_summary(report_payload, duration_s)

    md_path = write_reports(repo_root, config, report_payload, config_text)
    report_payload["report_path"] = str(md_path.relative_to(repo_root))

    _print_console_summary(report_payload)
    return 0 if summary["steps_passed"] == summary["steps_total"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
