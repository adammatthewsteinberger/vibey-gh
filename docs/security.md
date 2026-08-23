# Security architecture

Workflows use least-privilege job permissions and immutable third-party action revisions.
Privileged `pull_request_target` jobs read trusted workflow code and may inspect untrusted
content but cannot execute it. AI tools edit only named scopes; trusted shell steps verify
paths and publish one commit. Secrets never enter prompts or artifacts. The merge train
rechecks exact-head gates immediately before mutation.

The Conventional Commits job is the sole guarded exception that may force-update history.
It can act only on a same-repository topic branch, only from an exact checked SHA, only on
linear history, and only with `--force-with-lease`. Permanent branches are rejected by
both configured and literal names. The job executes the trusted normalizer, never PR code,
and a concurrent contributor push makes the lease fail closed.

Webhook receivers must use a strong `VIBEY_GH_WEBHOOK_SECRET`, verify HMAC over the exact
raw body, and place `VIBEY_GH_WEBHOOK_STATE_DIR` on access-controlled durable storage.
Accepted IDs use atomic mode-0600 marker creation, preventing replay across restarts and
concurrent CLI processes. Operators own TLS, rate limits, request-size limits, backups,
retention, and safe pruning of expired claims.
