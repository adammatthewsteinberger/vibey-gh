# Workflow reference

Branch intake opens draft PRs. CI and provenance validate code. Documentation validates
the complete docs contract and periodically authors guarded refresh PRs. PR automation
aggregates exact-head scans, reviews outside contributions, repairs failures, and resolves
conflicts. The merge train squash-merges to develop and rebase-merges promotions to main.
Release publishes develop builds to TestPyPI and main builds to PyPI. Release surfaces
publish branch-specific ProperDocs and GHCR artifacts; repository profile maintains
description, homepage, topics, and verifies releases, deployments, and packages.

## Conventional Commits

`Conventional Commits` runs from trusted base-branch workflow code on PR open, reopen,
synchronization, and ready-for-review events. It inspects the exact PR head without
executing repository code. For same-repository, linear topic branches, it normalizes every
nonconforming subject, preserves commit bodies and provenance trailers, and publishes the
rewritten history with an exact-SHA `--force-with-lease`. It refuses forks, merge commits,
stale heads, and any branch named by the configured integration or release branch; the
literal `develop` and `main` names are denied independently as defense in depth. It never
deletes a branch. The resulting synchronize event reruns all ordinary scans.
