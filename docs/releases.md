# Release and promotion

Changes merge to `develop`, receive a derived development version, publish to TestPyPI,
and deploy Preview documentation. Promotion opens a `develop → main` PR. After exact-head
checks and review policy pass, it is rebase-merged without deleting either permanent
branch. Main creates the production tag, GitHub Release, PyPI distribution, GHCR package,
Production documentation, provenance, and then realigns develop safely.
