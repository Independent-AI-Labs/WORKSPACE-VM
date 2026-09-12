#!/usr/bin/env bash
# Environment setup for AMI Orchestrator
#
# PATH Order (first = highest priority):
# 1. boot bin (dot-boot-macos or dot-boot-linux) - System tools (cloudflared, node, python, etc.)
# 2. .venv/bin - Python packages (playwright, etc.)
# 3. .venv/node_modules/.bin - Node packages (claude, gemini, qwen)

setup_paths() {
    [[ -d "$AMI_ROOT/.venv/node_modules/.bin" ]] && export PATH="$AMI_ROOT/.venv/node_modules/.bin:$PATH"
    [[ -d "$AMI_ROOT/.venv/bin" ]] && export PATH="$AMI_ROOT/.venv/bin:$PATH"
    if [[ -d "$AMI_ROOT/.boot-macos/bin" ]]; then
        export PATH="$AMI_ROOT/.boot-macos/bin:$PATH"
    else
        [[ -d "$AMI_ROOT/.boot-linux/bin" ]] && export PATH="$AMI_ROOT/.boot-linux/bin:$PATH"
    fi
    # Deployed trust-boundary boot bin (provisioned by deploy-ci) fills gaps
    # the checkout boot dir leaves (e.g. podman runtime). Appended LAST so
    # checkout toolchains keep precedence; deploy-ci upgrades flow in here.
    [[ -d "/opt/workspace-ci/.boot-linux/bin" ]] && export PATH="$PATH:/opt/workspace-ci/.boot-linux/bin"
    export VIRTUAL_ENV="${VIRTUAL_ENV:-$AMI_ROOT/.venv}"
    export PYTHONPATH="$AMI_ROOT:${PYTHONPATH:-}"
}
