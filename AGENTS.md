# AGENTS.md — Universal Agent Rules for Enterprise Delivery

## 作弊就是死刑 — Cheating Is The Death Penalty

Every rule below is absolute. Violation means you are sabotaging the project.

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
- Coverage thresholds are earned, not configured — raise them only when actual coverage reaches that level.
- NEVER add `--ignore-filename-regex` to exclude testable code.

## Rule 3: One Commit Per Logical Change

- Each commit has a single, clear purpose. No garbage commits.
- Commit messages explain WHY, not just WHAT. Body is mandatory.
- Format: `type: description` followed by blank line and body.
- Valid types: `feat|fix|refactor|docs|test|chore|ci|perf|style|build|revert`.
- No auto-generated messages (merge, fixup, squash) unless whitelisted.
- No agent self-attribution lines (Co-authored-by, Claude, Anthropic email).

## Rule 4: Verify Before Commit

Before every commit, run ALL of these that apply to the project:

```
cargo test --workspace --lib --tests -- --test-threads=1  # Rust
python -m pytest                                           # Python
cargo fmt --check / ruff format --check                    # Format
cargo clippy --workspace -- -D warnings / ruff check       # Lint
All files under 512 lines                                  # Length
```

If the project has a Makefile with a `check` or `preflight` target, run that too.

## Rule 5: Shell-First, Framework-Never for CI Hooks

- If grep/awk/git can do it, it stays in shell. No Python VMs for pattern matching.
- Generate native git hooks from config — never depend on the `pre-commit` Python framework runtime.
- Auto-stage unstaged changes instead of stashing them (files should never vanish from disk).
- Scan only the staged diff for silent-error-swallow patterns — pre-existing violations don't block new commits.
- Use `# silent-ok: <reason>` as the audited escape hatch, never bare `except: pass` or `|| true`.

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

## Rule 9: Data Repository Protocol (Pull-Before-Write, Push-After-Write)

Every mutation to a data repo MUST follow this contract:
1. Pull before read — rebase onto upstream so you never serve stale data.
2. Pull before write — incorporate remote changes before staging local ones.
3. Commit and push after every mutation — one commit per logical change, pushed immediately.

The remote URL is configured on project init via `--remote`. The tooling handles
upstream tracking setup (first push uses `-u`). If the remote is unreachable, the
pipeline fails — no silent fallback to local-only mode.

## Rule 10: Schema Source of Truth

Production schemas (GraphQL SDL) are the source of truth. Never edit generated code.
Schema files are loaded at runtime from disk — edits take effect immediately.
Proposal schemas live alongside client data and serve as reference for future changes.

## Rule 11: Banned Patterns — Zero Exceptions Per Project

These are banned in ALL production code:
- `#[allow(`, `# type: ignore`, `# noqa` — never suppress tools
- `unsafe {` — never without documented justification
- `fallback` — no silent failure fallbacks
- `mock`, `stub` — no mocks in production
- `Any` type — use concrete types
- `silent` — no silent error swallowing (audited escape: `silent-ok:`)
- `self.get(` — no dict-like access patterns

The ONLY exception file is the shared `banned_words.yaml`. Per-project exception files stay empty.

## Rule 12: Double, Triple, Quadruple Check

Before pushing, verify:
- Git log: no skip-hook commits, no amend-on-pushed, no agent attribution
- No `env::set_var` without matching cleanup (in legacy code)
- No duplicate test modules or broken module boundaries
- No dead_code allows on functions that need testing
- Every test exercises the code it claims to cover
- No excluded coverage beyond the instrumentally-impossible
- All files are under 512 lines

## Rule 13: No Silent Fallbacks

- Every error must be surfaced to the caller. NEVER swallow errors.
- `unwrap()` is forbidden in production code. Use proper error propagation.
- Match arms must be exhaustive. No wildcard fallthroughs that hide logic errors.
- Network operations (pull, push, fetch) must fail the operation, not degrade silently.

## 作弊就是死刑 — REMEMBER THIS
