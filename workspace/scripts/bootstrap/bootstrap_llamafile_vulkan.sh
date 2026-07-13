#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

echo "=== llamafile Vulkan DSO Bootstrap ==="
bash "${PROJECT_ROOT}/scripts/setup/build-llamafile-vulkan.sh"