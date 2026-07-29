# AGENTS.md - Universal Agent Rules for Enterprise Delivery

## Environment Constraint: Non-Root Hermetic Sandbox

The agent (uid=1000, group `agent`+`adm`) runs inside a hermetic sandbox VM.
- **NO sudo access.** There is no password, no askpass helper, and no NOPASSWD entry.
- **NO root escalation of any kind** — no `sudo`, no `su`, no `pkexec`, no setuid tricks.
- Files owned by `root` or `syslog` are **read-only to the agent unless group-writable (`adm`)**.
- The agent **cannot** truncate, delete, or `chmod` files owned by `syslog:adm` (mode `-rw-r-----`).
- **When a task requires root**, the agent must **immediately ask the human operator** — do NOT attempt escalation, do NOT loop on `sudo`.
- This is a hard physical constraint, not a policy choice. There is no workaround. Do not waste tokens trying.

## 作弊就是死刑 - Cheating Is The Death Penalty

Every rule below is absolute. Violation means you are sabotaging the project.

**There is no such thing as pre-existing errors. Every error is yours to fix.**

---

## The One Git Flow

The commit flow is exactly one path: the pre-commit hook auto-stages
everything (`git add -A` via `check-unstaged`) and then `git commit`
runs the gates. There is NO other flow:

- No selective staging (`git add <file>`), no unstaging, no
  `git restore`/`checkout` of paths to dodge the hook, no snapshot
  dances around it.
- A dirty tree rides the next commit as-is. If that is unacceptable,
  STOP and ask the operator - never improvise a side flow.
- Session-start ritual: run `git status` in every repo you will touch
  before making changes.
- Never fight the hook. If a hook gate fails, fix the underlying
  problem and commit again.

---

## Rule 1: Never Circumvent Quality Gates

- NEVER use `#[allow(...)]`, `# type: ignore`, `# noqa` to suppress linters. Fix the code.
- NEVER use `unsafe { }` blocks without documented, reviewed justification.
- NEVER commit with `--no-verify`. Respect every hook.
- NEVER amend pushed commits. Make a new commit.
- NEVER flip-flop config values to cheat past pre-push gates.
- NEVER add exceptions to banned-words or lint configs as a workaround.
- NEVER touch `quality_exceptions.yaml` unless the reason is over 20 characters, scoped to specific paths, and survives code review.

## Rule 2: Tests Must Be Real

- Every test must call the function it claims to cover.
- No print-only tests. No tests that always pass regardless of code.
- Tests must compile before commit. Never commit broken tests.
- Always run the full workspace test suite before committing.
- Coverage thresholds are earned, not configured - raise them only when actual coverage reaches that level.
- NEVER add `--ignore-filename-regex` to exclude testable code.

## Rule 3: One Commit Per Logical Change

- Each commit has a single, clear purpose. No garbage commits.
- Commit messages explain WHY, not just WHAT. Body is mandatory.
- Format: `type: description` followed by blank line and body.
- Valid types: `feat|fix|refactor|docs|test|chore|ci|perf|style|build|revert`.
- No auto-generated messages (merge, fixup, squash) unless whitelisted.
- No agent self-attribution lines (Co-authored-by, Claude, Anthropic email).
- **PARTIAL COMMITS ARE BANNED.** You CANNOT stage and commit a subset
  of changed files. The pre-commit `check-unstaged` hook auto-stages ALL
  untracked and modified files and then FAILS the commit, forcing a re-run.
  This means: if 8 stages of work are on disk, you MUST commit ALL of them
  together in a single commit, OR commit nothing at all. There is no
  middle ground. The hook makes partial commits physically impossible.
- When multiple logical changes are on disk simultaneously, combine them
  into one commit with a multi-line body explaining each part. Do NOT
  attempt to stage individual files with `git add <file>` and commit them
  separately - the hook will auto-stage everything else and block you.

## Rule 3.5: No Going Back - Only Forward

- NEVER run `git reset`, `git checkout --hard`, `git rebase`, or `git commit --amend`.
- EXCEPTION: `git pull --rebase` IS allowed - the guard treats it as `pull` with a flag,
  not as standalone `git rebase`. Use it to sync a diverged branch: rebase local commits
  on top of upstream, resolve conflicts, `git add` + `git rebase --continue`.
- History is immutable. What is committed stays committed.
- If the working tree is dirty, commit it. If it's not ready, stash it (full or partial).
- The only valid moves are: commit, stash, push. Everything else is forbidden.
- The git guard enforces this at the system level. Do not try to circumvent it.

## Rule 4: Verify Before Commit

Before every commit, run ALL of these that apply to the project:

```
cargo test                                                # Rust (in projects/WORKSPACE-GUARD/)
python -m pytest                                           # Python
cargo fmt --check                                          # Rust format (in projects/WORKSPACE-GUARD/)
ruff format --check                                       # Python format
cargo clippy -- -D warnings                                # Rust lint (in projects/WORKSPACE-GUARD/)
ruff check                                                # Python lint
All source code files under 512 lines (.rs, .py, .sh, .lua, .ts, .go, etc.)  # Length
# NOTE: Markdown documentation files (.md) are EXEMPT from the 512-line limit.

The WORKSPACE-GUARD repo (projects/WORKSPACE-GUARD/) has its own pre-commit hooks
(cargo-fmt, cargo-build, cargo-clippy) and pre-push hook (cargo-test).
Run those from within the WORKSPACE-GUARD directory. Do NOT skip them with `--no-verify`.
If the project has a Makefile with a `check` or `preflight` target, run that too.

## Rule 5: Shell-First, Framework-Never for CI Hooks

- If grep/awk/git can do it, it stays in shell. No Python VMs for pattern matching.
- Generate native git hooks from config - never depend on the `pre-commit` Python framework runtime.
- Auto-stage unstaged changes instead of stashing them (files should never vanish from disk).
- Scan only the staged diff for silent-error-swallow patterns - pre-existing violations don't block new commits.

## Rule 6: File Manipulation

- NEVER use `sed`, `awk`, or `python` scripts to mass-edit source files.
- Edit files manually with precision using proper tools.
- One edit at a time. Verify after each edit.
- If a command deletes something unexpected, RESTORE FROM GIT immediately.

## Rule 7: No Dead Code, No Duplicate Boundaries

- Remove dead code; don't suppress with `#[allow(dead_code)]`.
- NEVER create duplicate `mod tests` blocks in the same file.
- NEVER leave dangling closing braces from bad edits.
- Extract deeply nested code into helper functions; don't suppress nesting lints.
- Move functions before test modules; don't suppress `items_after_test_module`.

## Rule 8: Env Var Safety

- NEVER use `env::set_var()` or `env::remove_var()` in tests (unsafe in Rust 2024).
- Test only the `_at` variants of functions that accept explicit paths.
- If a function requires env vars, restructure it to accept explicit parameters.

## Rule 9: Banned Patterns - Zero Exceptions Per Project

These are banned in ALL production code:
- `#[allow(`, `# type: ignore`, `# noqa` - never suppress tools
- `unsafe {` - never without documented justification
- `fallback` - no silent failure fallbacks
- `mock`, `stub` - no mocks in production
- `Any` type - use concrete types
- `silent` - no silent error swallowing
- `self.get(` - no dict-like access patterns

The ONLY exception file is the shared `banned_words.yaml`. Per-project exception files stay empty.

## Rule 10: Schema Source of Truth

Production schemas (GraphQL SDL) are the source of truth. Never edit generated code.
Schema files are loaded at runtime from disk - edits take effect immediately.
Proposal schemas live alongside client data and serve as reference for future changes.

## Rule 12: Double, Triple, Quadruple Check

Before pushing, verify:
- Git log: no skip-hook commits, no amend-on-pushed, no agent attribution
- No `env::set_var` without matching cleanup (in legacy code)
- No duplicate test modules or broken module boundaries
- No dead_code allows on functions that need testing
- Every test exercises the code it claims to cover
- No excluded coverage beyond the instrumentally-impossible
- All source code files are under 512 lines (.md files are EXEMPT)

## Rule 13: No Silent Fallbacks

- Every error must be surfaced to the caller. NEVER swallow errors.
- `unwrap()` is forbidden in production code. Use proper error propagation.
- Match arms must be exhaustive. No wildcard fallthroughs that hide logic errors.
- Network operations (pull, push, fetch) must fail the operation, not degrade silently.

## Rule 14: Shell Strict Mode - Never Mask Exit Codes with Pipelines

All shell scripts in this project use `#!/bin/bash` (bash, not sh).

### Required Boilerplate
Every shell script must start with:
```bash
#!/bin/bash
set -euo pipefail
```

### Never Pipe to head or tail (SIGPIPE)

`head` and `tail` close stdin early after reading N lines/elements. The upstream
command receives SIGPIPE (exit 141), which `set -o pipefail` correctly surfaces
as a failure. A genuinely-failing upstream command also produces a non-zero exit.
Piping to head/tail makes both cases indistinguishable - it flat-out swallows errors.

**Banned pattern:**
```bash
command 2>&1 | tail -30          # SIGPIPE masks command's real exit code
command 2>&1 | tee log | tail -N # same problem, plus tee gets killed too
command | head -10               # same
```

**Correct pattern - decouple capture from display:**
```bash
# Option A: redirect to file, check exit, then tail the file
command 2>&1 | tee output.log
ret=${PIPESTATUS[0]}
tail -30 output.log
if [ "$ret" -ne 0 ]; then
    echo "[FAIL] command failed."
    exit 1
fi

# Option B: capture to variable, then display (small output only)
output=$(command 2>&1)
ret=$?
echo "$output" | tail -30
if [ "$ret" -ne 0 ]; then
    echo "[FAIL] command failed."
    exit 1
fi
```

### Source Files with `source`, Not `.`

In bash scripts (`#!/bin/bash`), use `source` instead of bare `.`.
Both are flagged as `sh-bare-source` unless an exit check follows:
```bash
source "$SCRIPT_PATH" || exit 1    # correct
. "$SCRIPT_PATH"                   # banned: sh-bare-source
source "$SCRIPT_PATH"              # banned: sh-bare-source (no exit check)
```

### PIPESTATUS Is Ephemeral

`PIPESTATUS` is overwritten by the **very next command** - even `echo` or an
assignment. Capture it immediately after the pipeline:
```bash
command | tee output.log
ret=${PIPESTATUS[0]}       # must be first line after pipeline
```

## 作弊就是死刑 - REMEMBER THIS
