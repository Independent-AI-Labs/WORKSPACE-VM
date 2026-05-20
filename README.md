# AMI-AGENTS: Sovereign AI Workspace

The AMI-AGENTS workspace is a federated, hard-walled infrastructure for developing and running AI agents. It prioritizes **data sovereignty, system immutability, and workspace-wide compliance**.

---

## 1. Getting Started

### Prerequisites
- **OS:** Linux (x86_64)
- **Permissions:** You must have `sudo` access to provision system dependencies.

### Installation
```bash
git clone git@github.com:Independent-AI-Labs/AMI-AGENTS.git && cd AMI-AGENTS

# 1. Automate system dependency installation
sudo make pre-req

# 2. Workspace bootstrap (TUI)
make install
```
*The `make install` TUI handles the federated dependency graph. Choose the sub-projects relevant to your development focus. Once finished, `ami-agent` will be available in your path.*

---

## 2. Workspace Philosophy
This workspace is not a standard monorepo; it is a **federated system**. 
- **Fail-Closed Security:** All interactions are gated by `git-guard` (immutability) and `podman-guard` (network/FS isolation).
- **Compliance as Code:** The `AMI-CI` contract enforces strict quality gates (hooks, coverage, linting) on every sub-project.
- **Topological Orchestration:** We use `moon` to manage the dependency graph. **Never run tasks manually in sub-projects** if a `moon` task exists.

---

## 3. Navigation Map
| Purpose | Path | Description |
| :--- | :--- | :--- |
| **Core Agents** | `ami/` | Agent logic, CLI entrypoints, provider handlers. |
| **Workspace CI** | `projects/AMI-CI/` | The enforcement engine. Read this **before** your first PR. |
| **Data/Infra** | `projects/AMI-DATAOPS/` | Sovereign services (Postgres, Keycloak, Vaultwarden). |
| **Orchestration** | `projects/` | Federated projects (TRADING, SRP, PORTAL, etc.). |
| **Specs** | `projects/*/docs/` | Detailed requirements for specific subsystems. |

---

## 4. Common Failure Modes & Troubleshooting

1.  **"Operation not permitted" on `git`:**
    *   **Reason:** `git-guard` has set the `+i` (immutable) attribute on your binaries to prevent history manipulation.
    *   **Fix:** Use `sudo projects/RUST-GUARD/scripts/bootstrap_git_guard.sh --uninstall` if you absolutely must bypass the guard for a maintenance task.
2.  **Podman/Container Failures:**
    *   **Reason:** Service state drift or network policy enforcement.
    *   **Fix:** Use `make -C projects/AMI-DATAOPS runtime-down` then `runtime-up` to reset the container stack.
3.  **Bootstrap Drift:**
    *   **Reason:** Your local `.moon/` cache or `workspace-clones.yaml` is out of sync with the upstream.
    *   **Fix:** Run `moon run :update` to force a topological synchronization of the workspace graph.

---

## 5. Contribution Contract
Before opening a PR, you **must**:
1.  **Pass the Contract:** Ensure your project passes `make contract-check`.
2.  **Align History:** We enforce "No Going Back." Use commits and stashes; rebasing or amending pushed history is physically blocked by the git-guard.
3.  **Documentation:** All new specs must reside in the project's `docs/` subdirectory.

---

**License:** [MIT](LICENSE)
