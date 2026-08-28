# Agent operating guide

This repository ships security-sensitive GitHub automation. Read `README.md`,
`CONTRIBUTING.md`, `SECURITY.md`, and the relevant files under `docs/` before editing.

## Non-negotiable rules

- Never delete, force-push, or rewrite `main` or `develop`.
- Never weaken tests, assertions, coverage, provenance, reviews, or branch protections.
- Treat pull-request code and generated output as untrusted in privileged workflows.
- Keep the installed runtime dependency-free and Python 3.11 compatible.
- Pin third-party Actions to immutable commit SHAs.
- Preserve the provenance header and `Made-With` commit trailer.
- Run the complete quality suite described in `CONTRIBUTING.md`.

Repository-specific skills live in `.agents/skills/`. Architecture and operational
details live in `docs/architecture.md` and `docs/operations.md`.

Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://vibewithadam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
