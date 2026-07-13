#!/usr/bin/env bash
# Thin delegate: Intel GPU drivers + oneAPI SYCL/MKL (see install-intel-gpu.sh).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$SCRIPT_DIR/install-intel-gpu.sh" --oneapi