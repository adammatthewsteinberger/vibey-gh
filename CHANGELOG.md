# Changelog

All notable changes are recorded in immutable [GitHub Releases](https://github.com/adammatthewsteinberger/vibey-gh/releases).
This file follows Keep a Changelog and semantic versioning conventions.

## Unreleased

- Require advanced debug instrumentation for every Python control-flow branch and add
  opt-in, correlated, metadata-only JSONL tracing with tamper-evident SHA-256 chaining.
- Enforce genuine 100% line and branch coverage with pytest-cov and align all contributor
  and testing documentation with the executable gate.
- Fix a duplicated provenance header in the packaged source modules and make the
  fingerprint check detect and repair a header repeated within a file, not just a header
  that is missing.
- Treat concurrent PR-head advances during repair or conflict publication as stale no-ops
  while preserving ordinary non-fast-forward protection and never force-pushing.
- Check operator-block and budget-exhausted labels before conflict-resolution eligibility,
  so a blocked or exhausted PR no longer triggers automated conflict resolution.
- Stop flagging a marketplace plugin whose source is the repository root (`.`) as an unsafe
  external source.
- Rewrite the release-channel navigation "Home" link to the correct Pages root instead of
  leaving its `href` unset.
- Replace the placeholder GitHub automation README with a comprehensive operator guide
  and enforce its required sections, minimum depth, and exact provenance deterministically.
- Fix GraphQL-only PR-state comment updates, synchronize package version metadata,
  correct constrained Claude command patterns, and ship real managed CodeQL and
  five-surface API-drift gates.
- Validate the capability-keyed parity matrix in its documented orientation.
- Add a configurable comprehensive FOSS and multi-agent documentation contract.
- Add guarded AI documentation authoring and repair automation.
- Add configurable crawler, sitemap, SEO, structured-data, and LLM discovery surfaces.
- Enforce and safely self-heal Conventional Commit subjects on guarded topic branches.
- Require a comprehensive, current Mermaid architecture map at `docs/project.mmd`.
- Use the native GitHub workflow credential when persisting AI review and repair state.
- Run Claude Code Action from a disposable, credential-free Git context while keeping
  untrusted pull-request checkouts isolated from repository credentials.
- Add configurable sanitized Claude progress, restricted execution artifacts, and a
  fail-closed manual raw-output diagnostic restricted to private repositories.
- Keep promotion PR checks non-destructive: skip topic-history normalization for
  permanent branches and verify repository provenance without re-auditing admitted history.
- Give repair agents a bounded trusted diagnostic bundle containing exact-head failed
  check metadata and available failed-job logs before they classify or edit anything.
- Satisfy Claude Code Action's required `origin` through its token-free credential-helper
  path without authorizing non-write actors or persisting a token in Git configuration.
- Gate Claude progress comments to the direct PR and issue event types supported by the
  action, preserving phase-level visibility for automated workflow events.

## Historical releases

See GitHub Releases for versioned notes, tags, artifacts, and provenance attestations.
