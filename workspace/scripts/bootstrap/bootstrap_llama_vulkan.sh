#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

echo "=== llama.cpp (Vulkan) Bootstrap ==="
bash "${PROJECT_ROOT}/scripts/setup/build-llama-vulkan.sh"