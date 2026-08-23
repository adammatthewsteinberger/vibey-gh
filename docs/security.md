# Security architecture

Workflows use least-privilege job permissions and immutable third-party action revisions.
Privileged `pull_request_target` jobs read trusted workflow code and may inspect untrusted
content but cannot execute it. AI tools edit only named scopes; trusted shell steps verify
paths and publish one commit. Secrets never enter prompts or artifacts. The merge train
rechecks exact-head gates immediately before mutation.

Claude Code Action requires a Git repository at the workspace root for its own setup.
Managed workflows satisfy that contract with a disposable repository that has no remote,
source checkout, or persisted credential. Untrusted source remains under `target/`, checked
out with `persist-credentials: false`. The disposable context is removed with `always()`
before trusted persistence or publishing. Only the later trusted publish step attaches
`GH_TOKEN` through `gh auth setup-git`; no Claude step can read that authenticated context.

Claude observability is sanitized by default. Raw `show_full_output` logging can expose
assistant messages, tool results, repository contents, and CI material, so managed
workflows accept it only from an explicit manual dispatch when configuration opts in and
GitHub reports private repository visibility. Public and event-triggered runs fail closed.
Execution logs may instead be retained as access-controlled 90-day workflow artifacts.

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
