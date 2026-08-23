# Configuration reference

`.vibey-gh.toml` configures fingerprints, semantic version paths, permanent branches,
trusted authors, PR automation, GitHub releases, repository profile, documentation, and
the managed workflow set. Omitted fields use safe defaults from `vibey_gh.config`.

The documentation section controls required files, AI maintenance, model, channel labels,
indexing, robots, sitemap index, LLM files, JSON-LD, and author provenance. Repository
identity and Pages URLs are derived at runtime and are never copied from the source repo.

Use `vibey-gh install`, commit generated assets, then run `vibey-gh check --ci`.
