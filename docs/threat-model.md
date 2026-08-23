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

The AI action's Git-discovery requirement is isolated from source and persisted credentials.
During model execution, workspace-root `.git` points only to an ephemeral empty repository.
Its clean `origin` satisfies action initialization, while a nonmatching actor sentinel selects
the token-free credential-helper and secret-scrubbing path without authorizing anyone.
Exact source is a separate `target/` checkout with persisted credentials disabled. The
context is destroyed before trusted code authenticates and publishes. Tests require this
ordering and fail if a Claude-facing target checkout persists credentials.
