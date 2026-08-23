# Security architecture

Workflows use least-privilege job permissions and immutable third-party action revisions.
Privileged `pull_request_target` jobs read trusted workflow code and may inspect untrusted
content but cannot execute it. AI tools edit only named scopes; trusted shell steps verify
paths and publish one commit. Secrets never enter prompts or artifacts. The merge train
rechecks exact-head gates immediately before mutation.

The managed CodeQL workflow analyzes Python changes on both delivery branches and their
pull requests. The API-drift workflow independently verifies that every canonical
capability remains available through MCP, API, CLI, SDK, and webhook boundaries.

Claude Code Action requires a Git repository at the workspace root for its own setup.
Managed workflows satisfy that contract with a disposable repository containing no source
checkout or persisted credential. It has a clean repository URL as `origin` because the
action requires that remote during setup. A deliberately nonmatching non-write-user sentinel
forces the action's credential-helper and secret-scrubbing path, so the token is never
embedded in `.git/config` and no additional actor is authorized. Untrusted source remains
under `target/`, checked out with `persist-credentials: false`. The disposable context is
removed with `always()` before trusted persistence or publishing. Only the later trusted
publish step attaches `GH_TOKEN` through `gh auth setup-git`; no Claude step can read that
authenticated context.

Claude observability is sanitized by default. The action's `track_progress` input is
strictly gated to its supported direct PR/issue events; privileged automation events rely
on job-phase visibility so an unsupported progress mode cannot fail the review itself.
Raw `show_full_output` logging can expose
assistant messages, tool results, repository contents, and CI material, so managed
workflows accept it only from an explicit manual dispatch when configuration opts in and
GitHub reports private repository visibility. Public and event-triggered runs fail closed.
Execution logs may instead be retained as access-controlled 90-day workflow artifacts.

Before a repair session, trusted automation downloads failed-check metadata and available
failed-job logs for the exact PR head into a bounded local diagnostic bundle. The bundle
is treated as untrusted input, capped at 200,000 bytes, and read-only to the diagnosis;
repository code is still never executed in the privileged job. This avoids speculative
repairs when optional CI MCP tools are unavailable without granting Claude shell access.

Repair and conflict-resolution publication never trusts the head it evaluated. The trusted
publisher re-reads the PR's current head immediately before committing and again after any
non-fast-forward push rejection. A mismatch means a human or another bot advanced the PR
concurrently, so the run is discarded as a stale no-op: it never force-pushes, never
overwrites the newer commit, never consumes a repair attempt, and never mutates a permanent
branch from an obsolete checkout. This applies even when `develop` or `main` is itself the
PR head during a promotion, which is exactly when clobbering unreviewed newer content would
be most damaging. See [Workflows](workflows.md) for the exact recheck points.

The Conventional Commits job is the sole guarded exception that may force-update history.
It can act only on a same-repository topic branch, only from an exact checked SHA, only on
linear history, and only with `--force-with-lease`. Permanent branches are rejected by
both configured and literal names. The job executes the trusted normalizer, never PR code,
and a concurrent contributor push makes the lease fail closed.
Promotion PRs from the integration branch to the release branch skip that history
normalizer entirely. Provenance still checks the complete repository state, but does not
re-audit or rewrite historical subjects already admitted to the protected integration
branch.

Webhook receivers must use a strong `VIBEY_GH_WEBHOOK_SECRET`, verify HMAC over the exact
raw body, and place `VIBEY_GH_WEBHOOK_STATE_DIR` on access-controlled durable storage.
Accepted IDs use atomic mode-0600 marker creation, preventing replay across restarts and
concurrent CLI processes. Operators own TLS, rate limits, request-size limits, backups,
retention, and safe pruning of expired claims.
