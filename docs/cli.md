# CLI reference

All commands return zero on success and a nonzero status on validation, policy, or
transport failure. Run `vibey-gh COMMAND --help` for argparse's generated reference.

| Command | Arguments and options | Behavior |
|---|---|---|
| `check` | `--apply`, `--commits RANGE`, `--quiet`, `--ci` | Verify assets, fingerprints, documentation, provenance, and optionally a commit range. `--apply` adds missing headers and collapses a header duplicated within a file; `--ci` skips the local hooks-path check. |
| `install` | none | Render configured workflows, install/chains hooks, and install release-site assets. |
| `version` | `--since REF` (default `origin/main`), `--dev BUILD`, `--apply`, `--explain` | Derive, explain, or write the semantic version. |
| `trailer` / `trailer-key` | none | Print the configured provenance trailer or only its key. |
| `conventional-message` | `--file COMMIT_EDITMSG` or stdin | Normalize the first line without changing the remaining bytes. This git-hook helper is intentionally CLI-only because it edits a local file or stdin. |
| `conventional-check` | required `--commits BASE..HEAD` | Audit every subject in an explicit revision range. This local/CI git helper is intentionally CLI-only, not a remote automation capability. |
| `merge-train` | `--method squash\|rebase\|merge`, `--pr N`, `--dry-run`, `--label LABEL`, `--summary FILE` | Revalidate and merge one or all policy-ready exact heads. |
| `pr-automation evaluate` | required `--pr N --head-sha SHA` | Classify one exact PR head and emit stable JSON. |
| `pr-automation ready-draft` | required `--pr N --head-sha SHA` | Convert a stable exact draft head to ready-for-review. |
| `pr-automation record-review` | required `--pr N --input JSON\|FILE\|-` | Persist a structured exact-head review. Use `-` for large stdin payloads. |
| `pr-automation record-repair` | required `--pr N --input JSON\|FILE\|-` | Persist a structured repair attempt. |
| `pr-automation mirror-fork` | required `--pr N` | Create a linked repository-owned replacement when a fork needs edits. |
| `pr-automation ensure-labels` | none | Create or reconcile all managed labels idempotently. |
| `github-release` | required `--target SHA`; optional `--version VERSION` | Create or reuse an immutable tag and GitHub Release. |
| `promote` | `--method rebase\|squash\|merge`, `--dry-run`, `--wait` or `--no-wait`, `--summary FILE` | Open/reuse the integration-to-release PR. Event-driven `--no-wait` is the default. |
| `realign` | none | Bring the integration branch forward after release without rewriting it. |
| `api`, `mcp`, `sdk` | `CAPABILITY`, `--arguments JSON_ARRAY` | Invoke a canonical capability through that adapter. |
| `webhook` | `CAPABILITY`, `--arguments JSON_ARRAY`, required `--delivery ID` | Sign and dispatch locally using `VIBEY_GH_WEBHOOK_SECRET`; claims persist by default. |

`VIBEY_GH_WEBHOOK_STATE_DIR` overrides the default
`.vibey-gh/webhook-deliveries` store. The CLI atomically creates a mode-0600 SHA-256 marker
for every accepted delivery ID in a mode-0700 directory, so rejection survives restarts
and concurrent invocations. Put it on durable storage when the CLI receives webhooks.

## Library and server adapters

SDK, API, MCP, and webhook implementations are dependency-free application callables, not
bundled network daemons. Adopters own TLS, authentication, process management, rate limits,
and request-size limits in their chosen server framework.

```python
from vibey_gh.surfaces import api_dispatch, mcp_dispatch

status, response = api_dispatch(
    "POST", "/v1/capabilities/check", b'{"arguments":["--ci"]}'
)
tools = mcp_dispatch({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
```

Map HTTP `POST /v1/capabilities/{name}` to `api_dispatch` and MCP JSON-RPC objects to
`mcp_dispatch`. For an inbound webhook, retain the sender's raw bytes and signature:

```python
from pathlib import Path
from vibey_gh.surfaces import WebhookDispatcher

webhooks = WebhookDispatcher(secret, delivery_dir=Path("/var/lib/vibey-gh/deliveries"))
status, response = webhooks.dispatch(delivery_id, signature_header, raw_body)
```

Never put the secret in arguments or logs. The convenience CLI computes its signature for
integration and smoke testing; an HTTP adapter must forward and verify the sender's HMAC.
