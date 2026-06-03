# Vulkan Backend: SWA/MoE Prompt Re-processing Bug

## Symptom

On the Vulkan backend with Qwen MoE models (SWA/Sliding Window Attention), the first
`/v1/chat/completions` request is fast (~12ms/tok prompt eval), but **every subsequent
request** falls into a slow re-processing path at ~0.6 tok/s (1664ms/tok) — ~100x slower.

The CPU backend handles the same scenario at normal speed (~35ms/tok prompt eval, ~88ms/tok gen)
on every request.

## Root Cause

The chat completion endpoint re-uses the slot for multi-turn conversations. After the first
request, the slot holds `n_past` stale KV tokens (the chat template prefix — typically 3 tokens).

On SWA models, `n_past > 0` triggers **full prompt re-processing** because the Vulkan backend
cannot carry over the SWA memory state when `n_past` tokens already exist in the slot.

The server log shows:

```
slot update_slots: forcing full prompt re-processing due to lack of cache data
  (likely due to SWA or hybrid/recurrent memory)
```

This is a **llama.cpp Vulkan backend bug** specific to SWA/hybrid memory models when
`n_past > 0`. The CPU backend (ggml-cpu) handles the same state transition correctly.

## Affected Models

- Qwen3-30B-A3B
- Qwen3.5-35B-A3B
- Qwen3.6-35B-A3B (UD)
- Qwen3-Next-80B-A3B
- Gemma 4 (all sizes, SWA variants)

Any model with `n_swa > 0` (Sliding Window Attention) or hybrid recurrent memory
architecture is affected on the Vulkan backend.

## What Was Tried (None Fixed It)

| Flag | Result |
|------|--------|
| `--cache-ram 0` | Disables prompt cache entirely — same behavior |
| `--slot-prompt-similarity <0..1>` | Tried 0.0, 0.1, 0.5 — doesn't affect SWA re-proc |
| `--swa-full` | Forces full SWA memory allocation — didn't help |
| `--kv-unified` | Unified KV cache — no effect |
| `--cache-idle-slots` | Prevents slot release — no effect |
| `-np 2` | More parallel slots — still reprocesses in slot |
| `--flash-attn off` / `-fa 0` | Disable flash attention — no improvement |
| `--ctx-checkpoints 0` | Disable context checkpoints — no change |
| `--checkpoint-every-n-tokens -1` | Disable checkpoint creation — same behavior |

## Status

- **Vulkan service**: running on port 8080 (`llamaserver@vulkan`), broken for multi-turn chat
- **CPU service**: running on port 8081 (`llamaserver@cpu`), works correctly for all requests
- **opencode**: switched to CPU backend at `http://127.0.0.1:8081/v1`

## Relevant Upstream Issues

| Issue | Status | Description |
|-------|--------|-------------|
| [#23322](https://github.com/ggml-org/llama.cpp/issues/23322) | Closed | Low MTP Draft Acceptance Rate with SWA/Hybrid Memory Models (Qwen3.6) |
| [#23321](https://github.com/ggml-org/llama.cpp/issues/23321) | Open | Vulkan Backend `no-kv-offload` on Qwen3 produces gibberish |
| [#21912](https://github.com/ggml-org/llama.cpp/issues/21912) | Closed | Gemma 4 & Qwen 3.5 full prompt reprocessing from system prompt |
| [#20099](https://github.com/ggml-org/llama.cpp/issues/20099) | Closed | Constantly use more token than expected with Qwen3.5-35B-A3B |
| [#13164](https://github.com/ggml-org/llama.cpp/issues/13164) | Closed | Qwen3 30B A3B dies after requesting inference |
| [#15293](https://github.com/ggml-org/llama.cpp/pull/15293) | Merged | server: add SWA checkpoints (mitigation, does not fix Vulkan) |
| [#13194](https://github.com/ggml-org/llama.cpp/pull/13194) | Merged | SWA support (comment explains full re-proc on n_past > 0) |

## Next Steps

1. Move inference to a DDR5 machine with CPU backend for reliable multi-turn chat
2. Test the same deployment scenario with a **dense 27B model** (no MoE, no SWA) on Vulkan
3. If dense model works on Vulkan, confirm the bug is SWA-specific (not Vulkan-generic)
4. Upstream fix needed in `ggml-vulkan` for SWA memory state carry-over with `n_past > 0`
