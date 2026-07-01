#!/bin/bash
# bootstrap_hooks.sh: Install native git hooks from .pre-commit-config.yaml.
#
# Runs cleanup-precommit (removes legacy pre-commit Python artifacts) then
# generate-hooks (writes native bash hooks to .git/hooks/).
set -euo pipefail

# Clean up any pre-existing pre-commit framework artifacts
if ! bash projects/CI/scripts/cleanup-precommit; then
    echo "[bootstrap_hooks] cleanup-precommit failed or not found, continuing"
fi

# Generate native git hooks from config
bash projects/CI/scripts/generate-hooks
