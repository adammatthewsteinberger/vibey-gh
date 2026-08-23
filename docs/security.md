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
