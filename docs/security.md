# Security architecture

Workflows use least-privilege job permissions and immutable third-party action revisions.
Privileged `pull_request_target` jobs read trusted workflow code and may inspect untrusted
content but cannot execute it. AI tools edit only named scopes; trusted shell steps verify
paths and publish one commit. Secrets never enter prompts or artifacts. The merge train
rechecks exact-head gates immediately before mutation.
