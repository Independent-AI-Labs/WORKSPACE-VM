#!/usr/bin/env bash
# Helper functions for module detection and path resolution in WORKSPACE Orchestrator

# Detect which module PWD is in by walking up
# Returns module name (base, browser, etc.) or "." for root
_detect_current_module() {
    local current="$PWD"

    while [[ "$current" != "/" && "$current" != "$WORKSPACE_ROOT" ]]; do
        # Check if this is a module root (has backend/ or is a known module)
        local rel_path="${current#$WORKSPACE_ROOT/}"

        # If we're at a first-level directory under WORKSPACE_ROOT, that's likely the module
        if [[ "$rel_path" != "$current" && "$rel_path" != */* ]]; then
            echo "$rel_path"
            return 0
        fi

        current="$(dirname "$current")"
    done

    # Default to root
    echo "."
}

_find_module_root() {
    # Find module root by walking up looking for markers
    local current="$PWD"

    while [[ "$current" != "/" ]]; do
        if [[ -f "$current/pyproject.toml" || -d "$current/.git" ]]; then
            echo "$current"
            return 0
        fi
        current="$(dirname "$current")"
    done

    # Default to WORKSPACE_ROOT
    echo "${WORKSPACE_ROOT:-$PWD}"
}
