#!/usr/bin/env bash
# Build a llamafile distributable (.llamafile) from the prebuilt llamafile
# engine + a GGUF model + a default-args manifest.
#
# Produces one .llamafile per MODE:
#   server -> <gguf-stem>.llamafile        (HTTP server default)
#   chat   -> <gguf-stem>-chat.llamafile   (interactive TUI chat default)
#   all    -> both
#
# The engine and zipalign are reused from projects/llamafile/o/ (no recompile).
# The mode is chosen purely by which .args manifest is embedded; the engine is
# identical across modes. The embedded zip entry MUST be named ".args" because
# llamafile loads bundled defaults via cosmo_args("/zip/.args"), so the chosen
# manifest is staged into a temp dir as ".args" before zipalign runs.
#
# Usage:
#   build-llamafile-bundle.sh --model <dir> --mode <server|chat|all> [--gguf <file>]
#   build-llamafile-bundle.sh --model <dir> --mode server --gpu vulkan
#
# See docs/SPEC-LLAMAFILE-MINICPM5-1B.md for the full procedure.
set -euo pipefail

usage() {
    cat >&2 <<'EOF'
Usage: build-llamafile-bundle.sh --model <dir> --mode <server|chat|all> [--gpu cpu|vulkan] [--gguf <file>]

  --model   model directory under models/ (e.g. minicpm5-1b)
  --mode    server | chat | all (default: all)
  --gpu     cpu (default) | vulkan: vulkan embeds ggml-vulkan.so from
            projects/llamafile/o/llamafile/ and uses .args.vulkan[*] manifests
  --gguf    explicit GGUF filename inside the model dir (optional; auto-detected)

Requires a prebuilt llamafile engine + zipalign under projects/llamafile/o/.
For --gpu vulkan, run make build-llamafile-vulkan first.
EOF
}

MODEL=""
MODE="all"
GPU="cpu"
GGUF=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --model) MODEL="${2:-}"; shift 2 ;;
        --mode) MODE="${2:-}"; shift 2 ;;
        --gpu) GPU="${2:-}"; shift 2 ;;
        --gguf) GGUF="${2:-}"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'error: unknown argument: %s\n' "$1" >&2; usage; exit 2 ;;
    esac
done

if [ -z "$MODEL" ]; then
    printf 'error: --model is required\n' >&2
    usage
    exit 2
fi
case "$MODE" in
    server|chat|all) ;;
    *) printf 'error: --mode must be server, chat, or all (got: %s)\n' "$MODE" >&2; exit 2 ;;
esac
case "$GPU" in
    cpu|vulkan) ;;
    *) printf 'error: --gpu must be cpu or vulkan (got: %s)\n' "$GPU" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MODEL_DIR="$PROJECT_ROOT/models/$MODEL"
ENGINE="$PROJECT_ROOT/projects/llamafile/o/llamafile/llamafile"
ZIPALIGN="$PROJECT_ROOT/projects/llamafile/o/third_party/zipalign/zipalign"
VULKAN_DSO="$PROJECT_ROOT/projects/llamafile/o/llamafile/ggml-vulkan.so"

missing=0
for p in "$ENGINE" "$ZIPALIGN"; do
    if [ ! -x "$p" ]; then
        printf 'error: missing executable: %s\n' "$p" >&2
        missing=1
    fi
done
if [ ! -d "$MODEL_DIR" ]; then
    printf 'error: model directory not found: %s\n' "$MODEL_DIR" >&2
    missing=1
fi
if [ "$GPU" = "vulkan" ] && [ ! -f "$VULKAN_DSO" ]; then
    printf 'error: missing Vulkan DSO: %s\n' "$VULKAN_DSO" >&2
    printf 'hint: run make build-llamafile-vulkan first\n' >&2
    missing=1
fi
if [ "$missing" -ne 0 ]; then
    printf 'hint: build the engine first - see docs/SPEC-LLAMAFILE-MINICPM5-1B.md Step 1\n' >&2
    exit 1
fi

# Resolve the GGUF: explicit override, else auto-detect exactly one *.gguf.
if [ -n "$GGUF" ]; then
    GGUF="$MODEL_DIR/$GGUF"
else
    found=""
    count=0
    while IFS= read -r -d '' f; do
        found="$f"
        count=$((count + 1))
    done < <(find "$MODEL_DIR" -maxdepth 1 -type f -name '*.gguf' -print0)
    if [ "$count" -eq 0 ]; then
        printf 'error: no .gguf found in %s\n' "$MODEL_DIR" >&2
        exit 1
    fi
    if [ "$count" -gt 1 ]; then
        printf 'error: multiple .gguf found in %s; specify --gguf <filename>\n' "$MODEL_DIR" >&2
        exit 1
    fi
    GGUF="$found"
fi
if [ ! -f "$GGUF" ]; then
    printf 'error: gguf not found: %s\n' "$GGUF" >&2
    exit 1
fi

GGUF_STEM="$(basename "$GGUF" .gguf)"

manifest_for_mode() {
    local mode="$1"
    if [ "$GPU" = "vulkan" ]; then
        case "$mode" in
            server) printf '%s\n' "$MODEL_DIR/.args.vulkan" ;;
            chat) printf '%s\n' "$MODEL_DIR/.args.vulkan.chat" ;;
        esac
        return
    fi
    case "$mode" in
        server) printf '%s\n' "$MODEL_DIR/.args" ;;
        chat) printf '%s\n' "$MODEL_DIR/.args.chat" ;;
    esac
}

suffix_for_mode() {
    local mode="$1"
    if [ "$GPU" = "vulkan" ]; then
        case "$mode" in
            server) printf '%s\n' "-vulkan" ;;
            chat) printf '%s\n' "-vulkan-chat" ;;
        esac
        return
    fi
    case "$mode" in
        server) printf '%s\n' "" ;;
        chat) printf '%s\n' "-chat" ;;
    esac
}

bundle_one() {
    local mode="$1"
    local manifest suffix out stage listing
    manifest="$(manifest_for_mode "$mode")"
    suffix="$(suffix_for_mode "$mode")"
    if [ ! -f "$manifest" ]; then
        printf 'error: manifest not found for mode "%s": %s\n' "$mode" "$manifest" >&2
        exit 1
    fi
    out="$MODEL_DIR/${GGUF_STEM}${suffix}.llamafile"
    stage="$(mktemp -d)"
    # zipalign embeds each file by basename; /zip/.args lookup requires the
    # entry be named exactly ".args", so stage the manifest under that name.
    cp "$manifest" "$stage/.args"
    printf '=== Bundling (mode=%s gpu=%s) ===\n' "$mode" "$GPU"
    printf '  engine:   %s\n' "$ENGINE"
    printf '  gguf:     %s\n' "$GGUF"
    printf '  manifest: %s\n' "$manifest"
    printf '  output:   %s\n' "$out"
    cp "$ENGINE" "$out"
    if [ "$GPU" = "vulkan" ]; then
        printf '  vulkan:   %s\n' "$VULKAN_DSO"
        "$ZIPALIGN" -j0 "$out" "$GGUF" "$VULKAN_DSO" "$stage/.args"
    else
        "$ZIPALIGN" -j0 "$out" "$GGUF" "$stage/.args"
    fi
    chmod +x "$out"
    rm -rf "$stage"
    if ! listing="$(unzip -l "$out" 2>&1)"; then
        printf 'error: zip integrity check failed for %s\n' "$out" >&2
        rm -f "$out"
        exit 1
    fi
    printf '  size: %s\n' "$(ls -lh "$out" | awk '{print $5}')"
    printf '  embedded entries:\n'
    if ! printf '%s\n' "$listing" | grep -E '\.args|\.gguf'; then
        printf 'error: bundle missing .args or .gguf entry in %s\n' "$out" >&2
        rm -f "$out"
        exit 1
    fi
    if [ "$GPU" = "vulkan" ] && ! printf '%s\n' "$listing" | grep -q 'ggml-vulkan\.so'; then
        printf 'error: bundle missing ggml-vulkan.so entry in %s\n' "$out" >&2
        rm -f "$out"
        exit 1
    fi
    printf 'OK (mode=%s) -> %s\n\n' "$mode" "$out"
}

case "$MODE" in
    server) bundle_one server ;;
    chat) bundle_one chat ;;
    all) bundle_one server; bundle_one chat ;;
esac

printf '=== Bundle build complete (model=%s mode=%s gpu=%s) ===\n' "$MODEL" "$MODE" "$GPU"
