# Llamafile transcript classifier benchmark

Replays OpenCode sessions turn-by-turn against a local llamafile server, simulating a rolling-window moderator/classifier with KV cache reuse.

## Prerequisites

- Llamafile server running (default `http://127.0.0.1:8765`)
- OpenCode SQLite DB at `~/.local/share/opencode/opencode.db`
- Python 3 with project venv active

## Fixture extraction

On each run, when `sync_on_run: true` in [benchmark.yaml](benchmark.yaml):

1. `discover_session_catalog()` reads sessions from the OpenCode DB filtered by `project_directory_contains: WORKSPACE-VM`
2. `sync_fixture_cache()` writes local copies under `fixtures/`:
   - `fixtures/<session_id>.txt`: turn summaries (`[user]` / `[assistant]` lines)
   - `fixtures/manifest.yaml`: catalog metadata

Fixture `.txt` bodies and `manifest.yaml` are **gitignored** (machine-local, regenerated each run). Only `benchmark.yaml` and this README are tracked; `fixtures/.gitkeep` preserves the directory.

To refresh fixtures without a full benchmark, run the classifier entrypoint with
`--skip-cache-probe` after setting `sync_on_run: true` in config (fixtures sync
at startup before session replay begins).

## Run

```bash
make -f Makefile.llamafile benchmark-llamafile-transcript-classifier
```

Subset of sessions:

```bash
make -f Makefile.llamafile benchmark-llamafile-transcript-classifier SESSION=ses_abc123
```

All backends (CPU + Vulkan):

```bash
bash scripts/benchmark/run-llamafile-transcript-classifier-all-backends.sh
```

## Behavior

- **Rolling 32K window** (`replay.mode: rolling_window`): at each turn, the classifier sees the last n user/assistant pairs that fit under `max_context_tokens` (32768). Oldest turns drop when the transcript grows.
- **KV cache**: pinned `id_slot` with `cache_prompt=true`; incremental steps reuse prefix tokens when the window only grows.
- **Reports**: written to `docs/benchmarking/llamafile-transcript-classifier/<backend>/<timestamp>/` (gitignored). Includes cache hit ratio, TTFT growth, and per-session window curves.

Token counting during window selection calls the llamafile `/v1/chat/completions/input_tokens` endpoint once per trim step; this is intentional for accurate budgets.