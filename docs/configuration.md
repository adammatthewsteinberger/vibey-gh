# Configuration reference

`.vibey-gh.toml` configures fingerprints, semantic version paths, permanent branches,
trusted authors, PR automation, GitHub releases, repository profile, documentation, and
the managed workflow set. Omitted fields use safe defaults from `vibey_gh.config`.

The documentation section controls required files, AI maintenance, model, channel labels,
indexing, robots, sitemap index, LLM files, JSON-LD, and author provenance. Repository
profile configuration owns collaboration features, merge methods, auto-merge, commit
signoff, branch retention, vulnerability alerts, and automated security fixes. Automatic
branch deletion defaults off because `develop` is the head of promotion PRs and must never
be deleted after merging to `main`. Identity and Pages URLs are derived at runtime.

Use `vibey-gh install`, commit generated assets, then run `vibey-gh check --ci`.
