#!/usr/bin/env bash

# Node.js setup functions for AMI Orchestrator

# Source common functions
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMON_SCRIPT="$SCRIPT_DIR/common.sh"
if [ -f "$COMMON_SCRIPT" ]; then
    source "$COMMON_SCRIPT"
else
    echo "ERROR: common.sh not found at $COMMON_SCRIPT"
    exit 1
fi

# Function to check if node and npm are available in the bootstrapped environment
check_node() {
    # Look for node and npm in the .boot-linux/node-env directory
    if [ -x "$PWD/.boot-linux/node-env/bin/node" ] && [ -x "$PWD/.boot-linux/node-env/bin/npm" ]; then
        return 0
    else
        return 1
    fi
}

# Install nodeenv to create Node.js environment (using uv)
install_nodeenv() {
    # Use uv from bootstrapped environment or PATH
    local uv_cmd
    if [ -n "${UV_CMD:-}" ] && [ -x "$UV_CMD" ]; then
        uv_cmd="$UV_CMD"
    elif [ -x "$PWD/.boot-linux/bin/uv" ]; then
        uv_cmd="$PWD/.boot-linux/bin/uv"
    elif command -v uv &> /dev/null; then
        uv_cmd="uv"
    else
        log_error "uv not found. Install uv first: https://docs.astral.sh/uv/"
        return 1
    fi

    log_info "Installing nodeenv via uv..."
    "$uv_cmd" pip install --reinstall nodeenv --quiet || {
        log_error "Failed to install nodeenv"
        return 1
    }
}

# Create node environment - always ensure local environment exists (using uv)
setup_node_env() {
    local venv_dir="${1:-.boot-linux/node-env}"

    # Use uv from bootstrapped environment or PATH
    local uv_cmd
    if [ -n "${UV_CMD:-}" ] && [ -x "$UV_CMD" ]; then
        uv_cmd="$UV_CMD"
    elif [ -x "$PWD/.boot-linux/bin/uv" ]; then
        uv_cmd="$PWD/.boot-linux/bin/uv"
    elif command -v uv &> /dev/null; then
        uv_cmd="uv"
    else
        log_error "uv not found. Install uv first: https://docs.astral.sh/uv/"
        return 1
    fi

    # Determine nodeenv binary location (in .venv/bin after uv install)
    local nodeenv_cmd="$PWD/.venv/bin/nodeenv"

    # Always reinstall nodeenv to fix shebangs after repo moves
    log_info "Installing nodeenv via uv..."
    "$uv_cmd" pip install --reinstall nodeenv --quiet || {
        log_error "Failed to install nodeenv"
        return 1
    }

    log_info "Creating Node.js environment in $venv_dir (ensuring isolated environment)..."
    # Create fresh node environment to ensure isolation
    if [ -d "$venv_dir" ]; then
        log_warning "⚠️  Found existing node environment at $venv_dir"
        log_info "Removing existing node environment to ensure clean isolation..."
        rm -rf "$venv_dir"
    fi

    "$nodeenv_cmd" --node=24.11.1 "$venv_dir" || {
        log_error "Failed to create isolated Node.js environment in .boot-linux/node-env with Node.js 24.11.1"
        return 1
    }

    # Update PATH to prioritize the local node environment for subsequent commands
    export PATH="$venv_dir/bin:$PATH"

    # Create symlinks in .boot-linux/bin/
    local bin_dir="$PWD/.boot-linux/bin"
    mkdir -p "$bin_dir"

    ln -sf "../node-env/bin/node" "$bin_dir/node"
    ln -sf "../node-env/bin/npm" "$bin_dir/npm"
    ln -sf "../node-env/bin/npx" "$bin_dir/npx"

    log_info "✓ Node.js symlinks created in $bin_dir"

    return 0
}

# Install Node.js CLI agents
install_node_agents() {
    # Get the project root directory before any potential directory changes
    # node.sh is in ami/scripts/setup/, so go 3 levels up to reach project root (agents/)
    local project_root
    project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

    # First make sure we have node and npm available - set up node environment if needed
    if ! check_node; then
        log_info "Node.js or npm not found, installing via nodeenv..."
        install_nodeenv || {
            log_error "Failed to install nodeenv"
            return 1
        }
        setup_node_env || {
            log_error "Failed to set up node environment"
            return 1
        }
    else
        # Even if node/npm exist, ensure we're using an isolated environment
        setup_node_env || {
            log_error "Failed to set up node environment"
            return 1
        }
    fi

    # Install agents using npm from the scripts/package.json - they will go into the existing .venv environment
    log_info "Installing Node.js CLI agents to .venv/node_modules from scripts/package.json..."

    # Change to the scripts directory and install packages to the .venv directory using prefix
    # Use --no-save to prevent creating package.json in .venv and ensure clean local installation
    # Use --force to ensure latest compatible versions according to package.json
    # Install production dependencies only (skip devDependencies)
    #
    # We deliberately DO NOT pass --ignore-scripts. INCIDENT-2026-05-05:
    # @anthropic-ai/claude-code 2.1.113+ ships only a 132 KB wrapper
    # package; the actual native binary lives in per-platform optional
    # deps (e.g. @anthropic-ai/claude-code-linux-x64) and gets copied
    # over the wrapper's bin/claude.exe by the package's postinstall
    # (install.cjs). With --ignore-scripts that copy never happens, so
    # bin/claude.exe is left as the wrapper-package's diagnostic file
    # — `[[ -x .bin/claude ]]` still passes (the file is +x by design)
    # but invoking it just prints "Error: claude native binary not
    # installed" and exits 1. Symptom: tom@tomohawkyo's banner-doctor
    # logs flag ami-claude as "no version extracted (required >=2.0.0)"
    # after `make install` reported success. Drop the flag so the
    # postinstall runs and the native binary lands.
    if [ ! -f "$project_root/scripts/package.json" ]; then
        log_error "scripts/package.json not found, cannot install Node.js agents"
        return 1
    fi

    # Remove existing node_modules to ensure clean installation with latest compatible versions
    if [ -d "$project_root/.venv/node_modules" ]; then
        log_info "Removing existing node_modules to ensure clean installation..."
        rm -rf "$project_root/.venv/node_modules"
    fi

    # Copy the package.json to .venv to ensure npm reads dependencies from it
    cp "$project_root/scripts/package.json" "$project_root/.venv/package.json"

    # Run npm install in .venv. INCIDENT-2026-05-04: this used to swallow
    # npm's exit code, so a network blip / dep resolution failure / disk
    # error would leave .venv/node_modules/.bin/{claude,gemini,qwen}
    # missing while the bootstrap reported "installed successfully".
    # Tom @tomohawkyo hit exactly that on a fresh make install. Fail loud.
    local npm_rc=0
    ( cd "$project_root/.venv" && "$project_root/.boot-linux/node-env/bin/npm" install --no-save --force --production ) || npm_rc=$?
    rm -f "$project_root/.venv/package.json"

    if [[ $npm_rc -ne 0 ]]; then
        log_error "npm install exited $npm_rc -- Node.js CLI agents NOT installed"
        log_error "  Re-run: cd $project_root && make install"
        log_error "  If it keeps failing, capture: npm config get registry; npm doctor"
        return $npm_rc
    fi

    # Verify the agent binaries actually landed. We derive the expected bin
    # list from scripts/package.json + each package's own package.json `bin`
    # field rather than hardcoding {claude,gemini,qwen} -- that way adding or
    # removing a package from package.json doesn't require touching this
    # script, and a future "no-bin variant" of an existing package fails
    # loud against its own manifest. Each declared bin must exist as an
    # executable file in .venv/node_modules/.bin/ -- otherwise the
    # .boot-linux/bin/ami-* symlinks dangle and users report
    # "ami-claude missing after fresh make install".
    local expected_bins
    expected_bins=$("$project_root/.boot-linux/bin/python" -c '
import json, os, sys
project_root = sys.argv[1]
try:
    with open(os.path.join(project_root, "scripts/package.json")) as f:
        deps = json.load(f).get("dependencies", {})
except Exception as exc:
    print(f"package.json parse error: {exc}", file=sys.stderr)
    sys.exit(2)
bins = []
for pkg in deps:
    pkg_json = os.path.join(project_root, ".venv/node_modules", pkg, "package.json")
    if not os.path.isfile(pkg_json):
        print(f"package missing entirely: {pkg}", file=sys.stderr)
        sys.exit(3)
    try:
        with open(pkg_json) as f:
            data = json.load(f)
    except Exception as exc:
        print(f"parse error in {pkg_json}: {exc}", file=sys.stderr)
        sys.exit(4)
    pkg_bin = data.get("bin")
    if isinstance(pkg_bin, str):
        bins.append(pkg.rsplit("/", 1)[-1])
    elif isinstance(pkg_bin, dict):
        bins.extend(pkg_bin.keys())
print(" ".join(bins))
' "$project_root")
    local enum_rc=$?
    if [[ $enum_rc -ne 0 ]]; then
        log_error "Failed to enumerate expected binaries from scripts/package.json (rc=$enum_rc)"
        log_error "  Re-run: cd $project_root && make install-node-agents"
        return 1
    fi

    local missing=()
    local broken=()
    for bin in $expected_bins; do
        local bin_path="$project_root/.venv/node_modules/.bin/$bin"
        if [[ ! -x "$bin_path" ]]; then
            missing+=("$bin")
            continue
        fi
        # Smoke test: --version must exit 0 AND emit a parseable
        # MAJOR.MINOR.PATCH. INCIDENT-2026-05-05: claude-code ships a
        # bin/claude.exe diagnostic file that is technically +x but
        # exits 1 with the message "Error: claude native binary not
        # installed.". The old `[[ -x ]]` check passed and we shipped
        # the broken state. Run the actual command so a wrapper-only
        # install is caught at bootstrap time, not at first-use.
        local version_output version_rc
        version_output=$("$bin_path" --version 2>&1)
        version_rc=$?
        if [[ $version_rc -ne 0 ]] || ! [[ "$version_output" =~ [0-9]+\.[0-9]+\.[0-9]+ ]]; then
            local snippet="${version_output:0:200}"
            broken+=("$bin (rc=$version_rc): ${snippet//$'\n'/ }")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "npm install exit was 0 BUT these CLI agents are missing from .venv/node_modules/.bin/: ${missing[*]}"
        log_error "  Inspect: ls -la $project_root/.venv/node_modules/.bin/"
        log_error "  Inspect: cat $project_root/scripts/package.json"
        return 1
    fi
    if [[ ${#broken[@]} -gt 0 ]]; then
        log_error "npm install exit was 0 AND .bin/<name> is +x BUT --version smoke test failed for:"
        for entry in "${broken[@]}"; do
            log_error "    - $entry"
        done
        log_error "  Most common cause: a package's postinstall step did not run (e.g."
        log_error "  --ignore-scripts in your npm config) and the native binary was never"
        log_error "  copied over its diagnostic file. Remove --ignore-scripts from npm"
        log_error "  flags and rerun, or invoke the package's install.cjs manually."
        return 1
    fi

    log_info "Node.js CLI agents installed successfully (verified runnable: ${expected_bins})"
    return 0
}