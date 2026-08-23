# Release and promotion

Changes merge to `develop`, receive a derived development version, publish to TestPyPI,
and deploy Preview documentation. Promotion opens a `develop → main` PR. After exact-head
checks and review policy pass, it is rebase-merged without deleting either permanent
branch. Main creates the production tag, GitHub Release, PyPI distribution, GHCR package,
Production documentation, provenance, and then realigns develop safely.

The `Release` workflow that performs the TestPyPI/PyPI publish is hand-authored by the
adopting repository, not rendered by `vibey-gh install`: publish steps are project-specific
in a way the other managed workflows are not. It must exist under the exact name `Release`
and, on `develop` and `main`, derive and apply the version with `vibey-gh version --apply`,
build the package, and publish through the `testpypi` (develop) and `pypi` (main)
trusted-publishing environments. `github-release.yml`, `release-surfaces.yml`, and
`release-repair.yml` all trigger from a `workflow_run` named exactly `Release`; without a
correctly named and behaving workflow, none of the tag, GitHub Release, GHCR, documentation,
repository-profile, or release-repair steps below ever run.
