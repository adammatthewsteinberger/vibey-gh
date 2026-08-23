# CLI reference

- `vibey-gh install`: install or update managed hooks, workflows, and release assets.
- `vibey-gh check`: verify installation, fingerprints, commit provenance, and docs.
- `vibey-gh version`: derive or apply semantic versions.
- `vibey-gh pr-automation`: evaluate, persist, label, and mirror exact-head PR state.
- `vibey-gh merge-train`: merge one or all policy-ready PRs.
- `vibey-gh promote`: create or reuse the develop-to-main promotion PR.
- `vibey-gh github-release`: idempotently tag and publish an immutable release.
- `vibey-gh realign`: bring develop forward after a main release without rewriting it.
- `vibey-gh conventional-message [--file COMMIT_EDITMSG]`: normalize a message supplied
  by file or standard input while retaining its body and trailers.
- `vibey-gh conventional-check --commits BASE..HEAD`: report every nonconforming subject
  in an explicit Git revision range and return a failing status when any are present.
- `vibey-gh api|mcp|sdk|webhook`: invoke the canonical capability through each adapter.

Run any command with `--help` for its complete argument contract.
