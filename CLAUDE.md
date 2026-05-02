# AMI workspace — Claude operating rules

This file is auto-loaded into every Claude session run from anywhere
inside `/home/ami/AMI-AGENTS/`. Keep it short — one-line rules with
a link if more context is needed.

## Parallel agents

When launching N≥2 agents against the same git repo, **always** pass
`isolation: "worktree"` to the Agent tool — even when direct commit
to the target repo is authorized. Without isolation, parallel
workers share one working tree, the first to commit is forced to
`git stash` the others' WIP, and the resulting commits are
bisect-unfriendly + review-noisy. AMI-CI hooks intentionally do
not block this pattern (it would also break legitimate
stash-around-commit, hotfix-while-WIP, and partial commits); the
discipline lives at the orchestration layer.

See `projects/AMI-CI/README.md` § *Working with parallel agents*.
