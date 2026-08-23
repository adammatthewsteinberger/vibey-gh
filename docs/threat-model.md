# Threat model

Protected assets include repository contents, permanent branches, secrets, packages,
releases, Pages deployments, provenance, and maintainer identity. Adversaries may control
fork contents, PR metadata, logs, model prompts, generated output, and dependency names.
Controls include no privileged execution of PR code, exact-SHA decisions, argument/path
validation, bounded attempts, guarded refspecs, immutable pins, independent CI, no
delete/force operations on main or develop, and an optimistic-concurrency recheck of the PR
head immediately before and after every repair or conflict publish, which converts a
concurrent human or bot update into a stale no-op instead of overwriting it. The narrow
exception is a lease-protected force-update of a same-repository topic branch to repair
commit subjects; exact-head, linear-history, repository-ownership, and permanent-branch
guards all precede it. A fork, merge commit, stale event, or concurrent push fails closed.
Operators must protect repository secrets and review ruleset changes.

The second narrow exception is the manually dispatched automation-bootstrap admin merge,
used only to recover from a broken privileged workflow that a normal PR cannot repair
because privileged workflow code is loaded from the trusted base branch, not the PR head.
Only a repository administrator can trigger it, and only with explicit `workflow_dispatch`
authorization naming an exact PR and head SHA. Before merging, the workflow independently
re-verifies that the PR is open, non-draft, targets `develop`, and matches the supplied head
exactly; that its changed files are confined to workflow, template, or automation-core
paths; and that every non-gate check run on that exact SHA — including CodeQL, API drift,
documentation, provenance, build, and lint — completed successfully. It then performs a
`--match-head-commit` admin squash merge, which bypasses ordinary `PRAutomation` and `Guard`
review but never deletes a permanent branch. This trades the semantic review step for an
administrator's explicit authorization plus the same independent deterministic gates,
scoped to the one case those gates cannot otherwise unblock.

The AI action's Git-discovery requirement is isolated from source and persisted credentials.
During model execution, workspace-root `.git` points only to an ephemeral empty repository.
Its clean `origin` satisfies action initialization, while a nonmatching actor sentinel selects
the token-free credential-helper and secret-scrubbing path without authorizing anyone.
Exact source is a separate `target/` checkout with persisted credentials disabled. The
context is destroyed before trusted code authenticates and publishes. Tests require this
ordering and fail if a Claude-facing target checkout persists credentials.
