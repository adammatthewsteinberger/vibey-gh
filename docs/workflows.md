# Workflow reference

Branch intake opens draft PRs. CI and provenance validate code. Documentation validates
the complete docs contract and periodically authors guarded refresh PRs. PR automation
aggregates exact-head scans, reviews outside contributions, repairs failures, and resolves
conflicts. The merge train squash-merges to develop and rebase-merges promotions to main.
Release publishes develop builds to TestPyPI and main builds to PyPI. Release surfaces
publish branch-specific ProperDocs and GHCR artifacts; repository profile maintains
description, homepage, topics, and verifies releases, deployments, and packages.
