# Contributing

## Development

Use Python 3.11 or newer. Create a topic branch from `develop`; never work directly on
`main`. Install the development environment with `uv sync --extra dev` and enable the
managed hooks with `uv run vibey-gh install`.

## Required checks

Run:

```bash
uv run pytest
uv run ruff check .
uv run black --check .
uv run isort --check-only .
uv run mypy --strict vibey_gh
uv run vibey-gh check --ci
```

Tests belong under `test/`. Maintain 100% line coverage, add branch-focused tests for new
decisions, and do not weaken checks. Update README, reference docs, changelog, security
guidance, agent instructions, and configuration examples when behavior changes.

## Pull requests and provenance

Keep changes focused. Explain behavior, risk, tests, migration, and documentation impact.
Every source file carries the configured header and every commit carries the configured
`Made-With` trailer. Automated scans, review, repair, and merge operate on the exact head.

See `docs/development.md`, `docs/testing.md`, and `docs/releases.md`.
