# WORKSPACE-VM Handover Document

**Date:** 2025-06-13  
**Status:** PARTIAL — Traefik integration incomplete, container crashes on startup, tests not fully working end-to-end

---

## 1. Repository Structure

```
WORKSPACE-VM/
├── workspace/
│   ├── config/
│   │   ├── install-defaults.yaml          # Component list for CI install
│   │   ├── bootstrap-components.yaml      # All available components
│   │   └── vm-template.yaml               # VM config (exists)
│   ├── scripts/
│   │   ├── install-mac.sh                 # Host prerequisites installer
│   │   ├── launch-mac.sh                  # Container lifecycle manager
│   │   ├── templates/
│   │   │   ├── Dockerfile.vm.j2          # Container build template
│   │   │   ├── systemd-opencode.service.j2
│   │   │   ├── systemd-traefik.service.j2
│   │   │   ├── systemd-workspace-network.service.j2
│   │   │   ├── traefik-static.yml.j2
│   │   │   └── traefik-dynamic.yml.j2
│   │   └── bootstrap/                     # Tool installers
│   │       ├── bootstrap_uv.sh
│   │       ├── bootstrap_traefik.sh
│   │       └── ...
├── tests/
│   └── host_vm/
│       └── mac/
│           ├── conftest.py                # Test fixtures
│           ├── test_vm_functional.py      # 4 functional tests
│           ├── test_scripts_e2e.py        # 6 E2E tests (slow)
│           ├── test_install_mac.py
│           ├── test_launch_mac.py
│           └── test_templates.py
├── Makefile                               # Has install-ci, install-ci
├── pyproject.toml                         # Has [mac] optional deps
└── .vms/workspace-vm-ubuntu/              # Generated build context
```

---

## 2. What Works (Verified)

- ✅ **Container builds successfully** (with all components including Traefik)
- ✅ **Container starts** with systemd, opencode, traefik, workspace-network services
- ✅ **opencode runs** on `127.0.0.1:4096` inside container
- ✅ **Traefik runs** as root on port 443 inside container
- ✅ **Port mapping** works: host `8443` → container `443`
- ✅ **30 unit tests pass** (excluding E2E)
- ✅ **4 functional tests pass** (basic container checks)
- ✅ **SSL certs generated** in `.vms/workspace-vm-ubuntu/certs/`
- ✅ **Password generated** in `.vms/workspace-vm-ubuntu/password`
- ✅ **Tests directory copied** into container at `/opt/workspace/tests/`

---

## 3. What's Broken

### 3.1 Container Crashes After First Run
**Symptom:** Container starts successfully, becomes healthy, then on subsequent starts crashes immediately with exit code 255.

**Root Cause:** After the test cleanup runs, something corrupts the container state. Possibly:
- The cleanup removes the image but the container is still referencing it
- Podman machine gets into a bad state
- The `--health-on-failure=stop` policy combined with failed healthcheck causes systemd to shut down

**Workaround:** Always remove container before starting: `podman rm -f workspace-vm-ubuntu && bash workspace/scripts/launch-mac.sh`

### 3.2 `wait_for_healthy()` Runs Tests Instead of Waiting
**Problem:** The function runs `pytest tests/` inside the container every 2 seconds. It should:
1. First wait for the container to actually be running and healthy
2. Then optionally run tests once

**Current broken code in launch-mac.sh:600-630:**
```bash
wait_for_healthy() {
    # Starts logs in background
    # Runs pytest every 2 seconds in a loop
    # This is wrong - it should wait for healthy first
}
```

**Fix needed:** Wait for `podman inspect` to return `healthy` status, THEN run tests once.

### 3.3 Dockerfile Healthcheck Wrong
**Problem:** `Dockerfile.vm.j2:81-82` checks opencode directly:
```
HEALTHCHECK CMD curl -sf http://127.0.0.1:4096/ || exit 1
```

**Should check:** The full chain via Traefik:
```
HEALTHCHECK CMD curl -sk https://localhost:443/ || exit 1
```

### 3.4 `podman rmi -f` Cascades to Base Layers
**Problem:** Multiple places use `podman rmi -f` which deletes the Ubuntu base image:
- `launch-mac.sh:219` (do_recreate)
- `test_vm_functional.py:43` (cleanup)

**Fix:** Remove `-f` flag, or better: don't delete images at all in cleanup.

### 3.5 E2E Tests Destroy Container Between Each Test
**Problem:** `test_scripts_e2e.py:28-31` has `autouse=True` cleanup that removes the container after EVERY test. This forces a full rebuild for each E2E test, making them take 5+ minutes each.

**Fix:** Remove `autouse=True` or make it session-scoped.

### 3.6 SSH Key Temp File Not Cleaned on Build Failure
**Problem:** `launch-mac.sh:486-502` only cleans up `temp_ssh_key` if `podman build` succeeds. If build fails, the key stays in `.vms/workspace-vm-ubuntu/temp_ssh_key`.

**Fix:** Add trap to clean up on any exit.

### 3.7 Dockerfile Unconditional COPY of SSH Key
**Problem:** `Dockerfile.vm.j2:26` always does `COPY .vms/workspace-vm-ubuntu/temp_ssh_key` even if the file doesn't exist, causing build failure.

**Fix:** Make it conditional or use a build arg.

---

## 4. Key Files and Their Current State

### 4.1 `workspace/scripts/launch-mac.sh` (695 lines)
- **Password generation:** ✅ Works (generates random if missing, prints for user)
- **SSL cert generation:** ✅ Works (CA + server certs)
- **Template rendering:** ✅ Works (opencode, traefik, network services)
- **Dockerfile rendering:** ✅ Works with all conditionals
- **Container creation:** ✅ Works with `-p 8443:443` (rootless can't bind 443)
- **`wait_for_healthy()`:** ❌ BROKEN - runs tests instead of waiting
- **`do_recreate()`:** ⚠️ Uses `podman rmi -f` which cascades

### 4.2 `workspace/scripts/templates/Dockerfile.vm.j2` (84 lines)
- **Base image:** ubuntu:22.04 with systemd
- **User:** workspace (uid 1000)
- **Components installed:** uv, python, node, opencode, podman, gh, go, cloudflared, **traefik**, pandoc, ansible, ci, dataops, workspace-guard
- **Services enabled:** opencode, traefik, workspace-network
- **Volumes:** /workspace, /transcripts, /cache
- **Certs:** /etc/ssl/workspace/
- **Config:** /home/workspace/.config/opencode/config.json
- **HEALTHCHECK:** ❌ Wrong - checks opencode directly, should check Traefik
- **SSH key COPY:** ❌ Unconditional

### 4.3 `workspace/scripts/templates/systemd-traefik.service.j2`
- Runs as **root** (required to bind port 443)
- After=opencode.service
- Uses `/opt/workspace/.boot-linux/bin/traefik`

### 4.4 `workspace/scripts/templates/traefik-dynamic.yml.j2`
- TLS 1.3 minimum
- mTLS with client cert required (`RequireAndVerifyClientCert`)
- Routes all paths to opencode on `http://127.0.0.1:4096`
- Certs at `/etc/ssl/workspace/`

### 4.5 `tests/host_vm/mac/test_vm_functional.py` (135 lines)
- 4 tests that pass:
  1. `test_container_can_run_basic_commands` ✅
  2. `test_opencode_service_running` ✅
  3. `test_essential_binaries_exist_inside_container` ✅
  4. `test_workspace_volumes_mounted` ✅
- Cleanup has `podman rmi` (should be removed)

### 4.6 `tests/host_vm/mac/test_scripts_e2e.py` (146 lines)
- 6 E2E tests - all SLOW because they rebuild container
- `autouse=True` cleanup destroys container between every test
- Should be session-scoped or removed

---

## 5. Current Running State

- **Podman machine:** Running (applehv on macOS arm64)
- **Image:** `localhost/workspace-vm-ubuntu:latest` exists (4.13 GB)
- **Container:** `workspace-vm-ubuntu` may or may not exist
- **Volumes:** `workspace-vm-ubuntu-{workspace,transcripts,cache}` exist
- **Network:** `workspace-vm-net` exists
- **Password:** Stored at `.vms/workspace-vm-ubuntu/password`
- **SSL certs:** Stored at `.vms/workspace-vm-ubuntu/certs/`

---

## 6. Exact Steps to Verify and Debug

```bash
# 1. Check current state
podman ps -a
podman images | grep workspace

# 2. Remove all containers (if any exist)
podman rm -f $(podman ps -aq)

# 3. Launch fresh
bash workspace/scripts/launch-mac.sh

# 4. If container crashes, check logs
podman logs workspace-vm-ubuntu

# 5. If container is healthy, exec in and test
podman exec workspace-vm-ubuntu bash -c "systemctl status"
podman exec workspace-vm-ubuntu bash -c "curl -sk https://localhost:443/"

# 6. Run functional tests
source .venv-mac/bin/activate
pytest tests/host_vm/mac/test_vm_functional.py -v

# 7. Run non-E2E tests
pytest tests/host_vm/mac/ -k "not e2e" -v
```

---

## 7. The 8 Fixes Needed (Priority Order)

### Fix 1: `launch-mac.sh:600-630` — `wait_for_healthy()`
Replace with:
```bash
wait_for_healthy() {
    log_section "Waiting for Health Check"
    
    podman logs -f "$CONTAINER_NAME" &
    local logs_pid=$!
    trap "kill $logs_pid 2>/dev/null" RETURN
    
    local deadline=$((SECONDS + HEALTHCHECK_TIMEOUT))
    
    while [[ $SECONDS -lt $deadline ]]; do
        local status
        status=$(podman inspect -f '{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
        
        if [[ "$status" == "healthy" ]]; then
            log_ok "Container is healthy"
            kill $logs_pid 2>/dev/null
            return 0
        fi
        
        sleep "$HEALTHCHECK_POLL"
    done
    
    kill $logs_pid 2>/dev/null
    log_error "Container did not become healthy within ${HEALTHCHECK_TIMEOUT}s"
    return 1
}
```

### Fix 2: `Dockerfile.vm.j2:81-82` — Healthcheck
Change to:
```
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -skf https://localhost:443/ || exit 1
```

### Fix 3: `Dockerfile.vm.j2:26` — Conditional SSH key COPY
Wrap in Jinja2 conditional:
```
{% if ssh_key_copy %}
COPY {{ vm_ssh_key }} /tmp/temp_ssh_key
{% endif %}
```

### Fix 4: `test_vm_functional.py:42-46` — Remove `podman rmi`
Delete the entire `subprocess.run` block for `podman rmi`.

### Fix 5: `test_scripts_e2e.py:28-31` — Remove autouse cleanup
Change to session-scoped or remove entirely.

### Fix 6: `launch-mac.sh:218-221` — `do_recreate()`
Change `podman rmi -f` to `podman rmi` (no `-f`).

### Fix 7: `launch-mac.sh:486-502` — SSH key cleanup trap
Add `trap "rm -f '$temp_ssh_key'" EXIT` at the start of build_image.

### Fix 8: `Dockerfile.vm.j2:47-48` — Conditional certs COPY
Wrap in `{% if traefik_enabled %}`:
```
{% if traefik_enabled %}
COPY {{ certs }} /etc/ssl/workspace/
{% endif %}
```

---

## 8. What Was NOT Done

- ❌ Tests don't run the full suite inside the container end-to-end
- ❌ mTLS client cert distribution (clients need ca.crt)
- ❌ No cloudflared tunnel configuration
- ❌ No OpenVPN configuration
- ❌ No validation that Traefik → opencode actually works
- ❌ No test for the password actually being set
- ❌ No test that SSL certs are valid

---

## 9. Key Commands Reference

```bash
# Build
bash workspace/scripts/launch-mac.sh --force-rebuild

# Start/stop
bash workspace/scripts/launch-mac.sh --shutdown
bash workspace/scripts/launch-mac.sh --restart
bash workspace/scripts/launch-mac.sh --recreate-vm-from-scratch

# Test
pytest tests/host_vm/mac/test_vm_functional.py -v
pytest tests/host_vm/mac/ -k "not e2e" -v

# Debug
podman logs workspace-vm-ubuntu
podman exec -it workspace-vm-ubuntu bash
podman exec workspace-vm-ubuntu systemctl status

# Clean
podman rm -f workspace-vm-ubuntu
podman rmi localhost/workspace-vm-ubuntu:latest
podman volume rm workspace-vm-ubuntu-{workspace,transcripts,cache}
podman network rm workspace-vm-net
rm -rf .vms/workspace-vm-ubuntu
```

---

## 10. Environment

- **Host:** macOS 26.5.1 (Darwin) arm64
- **Podman:** 5.8.2 (rootless, applehv machine)
- **Python:** 3.11.13 (.venv-mac)
- **uv:** 0.11.21
- **Working directory:** `/Users/vladislavdonchev/WORKSPACE-VM`
- **Shell:** bash with `set -euo pipefail`

---

## 11. Critical Lessons Learned

1. **Don't delete base images** — `podman rmi -f` cascades to parent layers
2. **Don't run tests in health check loops** — wait for healthy first
3. **Don't use `autouse=True` cleanup** — destroys state between tests
4. **Always use traps for temp file cleanup** — handle all exit paths
5. **Make Dockerfile COPYs conditional** — don't assume files exist
6. **Check Traefik in healthcheck, not backend services** — verify the full chain
7. **Rootless podman can't bind < 1024** — use `-p 8443:443` mapping

---

**End of Handover**
