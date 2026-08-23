# Workflow reference

Branch intake opens draft PRs. CI and provenance validate code. Documentation validates
the complete docs contract and periodically authors guarded refresh PRs. PR automation
aggregates exact-head scans, reviews outside contributions, repairs failures, and resolves
conflicts. The merge train squash-merges to develop and rebase-merges promotions to main.
Release publishes develop builds to TestPyPI and main builds to PyPI. Release surfaces
publish branch-specific ProperDocs and GHCR artifacts; repository profile maintains
description, homepage, topics, and verifies releases, deployments, and packages. If a
trusted post-merge workflow fails on `develop` or `main`, release repair reviews its logs
and returns a fixable problem through an ordinary guarded PR.

`CI` and `Release` are not managed templates; `vibey-gh install` never writes them, because
every repository's build, test, and publish steps differ. They must exist under those exact
names, because `github-release.yml`, `release-surfaces.yml`, and `release-repair.yml` all
key off a `workflow_run` named `Release` (and `release-repair.yml` also watches `CI`). A
`Release` workflow that runs on `develop`/`main`, derives the version with `vibey-gh
version --apply`, builds, and publishes through the `testpypi`/`pypi` trusted-publishing
environments is what the rest of this reference assumes exists.

## Conventional Commits

`Conventional Commits` runs from trusted base-branch workflow code on PR open, reopen,
synchronization, and ready-for-review events. It inspects the exact PR head without
executing repository code. For same-repository, linear topic branches, it normalizes every
nonconforming subject, preserves commit bodies and provenance trailers, and publishes the
rewritten history with an exact-SHA `--force-with-lease`. It refuses forks, merge commits,
stale heads, and any branch named by the configured integration or release branch; the
literal `develop` and `main` names are denied independently as defense in depth. It never
deletes a branch. The resulting synchronize event reruns all ordinary scans.
