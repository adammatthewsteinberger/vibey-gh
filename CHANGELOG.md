# Changelog

All notable changes are recorded in immutable [GitHub Releases](https://github.com/adammatthewsteinberger/vibey-gh/releases).
This file follows Keep a Changelog and semantic versioning conventions.

## Unreleased

- Keep a successful realign successful when its branch reconciliation cannot reach GitHub.
  Reconciliation is a follow-up that needs credentials some contexts do not have, and a
  branch left unreconciled is a nuisance rather than a reason to report the realign as
  failed and leave the caller believing the branches never converged.

- Normalize formatting deterministically in the repair job. The repair agent holds no
  shell, so it cannot run a formatter: it hand-formats, guesses the line length, fails the
  lint gate, and the next attempt reformats the other way — a loop that spends the whole
  repair budget without converging. The trusted step now runs the repository's own declared
  formatters, which read their settings from its configuration rather than from a guess.
- Reconcile the `ruff` and `isort` import rules, which were mutually unsatisfiable: each
  rejected the other's output for a module imported both plainly and under an alias, so no
  number of attempts could make such a file green. A test now proves the two agree and do
  not oscillate.

- Bring open branches forward automatically whenever the integration branch moves, so a
  conflict never accumulates. Automation-owned branches are rebased; every other branch,
  fork included, is merged forward through GitHub's own update-branch endpoint, which
  never rewrites a contributor's history and succeeds only where they enabled maintainer
  edits.
- Refill a spent repair budget on a daily schedule, itself bounded by
  `branch_sync.max_self_heals`, so a transient outage stops being a permanent halt that
  only a human notices — while a genuinely stuck pull request still stops for good.
- Terminally block any outside author's pull request whose head is a permanent branch or
  whose base is the release branch, so no untrusted work can steer automation at `develop`
  or `main` from either end.

- Reconcile open topic branches after realign rewrites the integration branch. A branch
  cut from a replaced commit previously reported a conflict covering work that had already
  landed, through nobody's fault. Realign now closes and deletes a branch whose commits are
  all upstream by patch identity, rebases an automation-owned branch that carries real
  work, and leaves a contributor's branch untouched with an explanatory comment. Every
  action is individually configurable through `[realign]`, and no permanent, fork, or
  unsafe ref can reach a mutating path.

- Resolve conflicts on draft pull requests instead of stranding them. Conflict is now
  classified before draft status: a conflicted draft could never be promoted, because
  promotion requires a clean merge, and conflict resolution never ran because it was a
  draft — so every conflicted branch-intake and issue-solution pull request deadlocked.
  Fork drafts still wait, because their conflict path closes the contributor's pull
  request.

- Bound the review-to-repair cycle for every author. The budget check sat behind an
  outside-author condition, so a trusted author's exact-head review could request repair
  after repair without limit; it is now applied wherever another review would be
  dispatched, which is the only point that is reachable while each repair publishes a new
  head.
- Persist the per-lineage attempt reset that was previously computed and discarded. A new
  human commit started a fresh lineage in the evaluation but never in the stored record, so
  the documented per-lineage budget silently behaved as a cumulative per-pull-request one.
  Both paths now share `lineage_for()` and cannot disagree.

- Report the exact-head gate's outcome truthfully when the review, not the scans, decides
  it: a review that returned actionable findings and a review that returned no verdict at
  all are now distinct, named states instead of a failing check whose summary claims every
  scan and review passed.

- Add autonomous issue automation: an eligible published issue is evaluated by trusted
  policy code, implemented by a constrained agent that reads the issue only as bounded
  untrusted data, and published as one guarded solution branch and linked pull request
  that closes the issue on merge.
- Treat issue text as an adversary-controlled input to a privileged job: outside authors
  are opt-in behind a configurable maintainer label, the agent holds no shell, `gh`,
  subagent, or Git tool, and nothing derived from an issue reaches a shell command, a
  workflow expression, or a branch name.
- Budget autonomous solution attempts against a fingerprint of the issue's title and body,
  so a redispatch of unchanged text cannot spend the budget twice and editing an issue
  starts a new lineage with a new branch.
- Render `branch-intake.yml` to yield the configured issue-solution branch namespace, so
  branch intake and issue automation never race to open the same pull request.
- Extract durable marker-comment automation state into `vibey_gh.github_state`, shared by
  pull-request and issue automation instead of duplicated across them.

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
