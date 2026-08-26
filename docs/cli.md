# CLI reference

All commands return zero on success and a nonzero status on validation, policy, or
transport failure. Run `vibey-gh COMMAND --help` for argparse's generated reference.

| Command | Arguments and options | Behavior |
|---|---|---|
| `check` | `--apply`, `--commits RANGE`, `--quiet`, `--ci` | Verify assets, fingerprints, documentation, provenance, that every `scan_workflows` entry present in `.github/workflows/` can fire for a pull request, and optionally a commit range. `--apply` adds missing headers and collapses a header duplicated within a file; `--ci` skips the local hooks-path check. |
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
| `issue-automation evaluate` | required `--issue N` | Classify one issue and emit stable JSON, including the derived solution branch and a Conventional Commit `pr_title`. |
| `issue-automation context` | required `--issue N`; optional `--output FILE`, `--max-bytes N` | Render one issue as a bounded, explicitly untrusted briefing. Writes to stdout when `--output` is omitted; parent directories are created. |
| `issue-automation record-solution` | required `--issue N --input JSON\|FILE\|-` | Persist a structured solution attempt against the issue's content lineage. |
| `issue-automation list-eligible` | none | Emit the JSON array of open issues a recovery sweep should dispatch. |
| `issue-automation ensure-labels` | none | Create or reconcile the issue automation labels idempotently. |
| `github-release` | required `--target SHA`; optional `--version VERSION` | Create or reuse an immutable tag and GitHub Release. |
| `promote` | `--method rebase\|squash\|merge`, `--dry-run`, `--wait` or `--no-wait`, `--summary FILE` | Open/reuse the integration-to-release PR. Event-driven `--no-wait` is the default. |
| `realign` | none | Bring the integration branch forward after release without rewriting it. |
| `pr-automation self-heal` | `--pr N` optional | Refill a spent repair budget, itself bounded by `branch_sync.max_self_heals`. Omit `--pr` to sweep every exhausted pull request. |
| `conversation evaluate` | required `--subject N`; optional `--comment-id ID` | Decide whether one comment gets a response, and how far it may reach. |
| `conversation context` | required `--subject N`; optional `--comment-id ID`, `--output FILE`, `--max-bytes N` | Render the thread as a bounded, explicitly untrusted briefing. |
| `conversation reply` | required `--subject N --body TEXT\|FILE\|-` | Post an answer. A trusted step calls this; the model never gets the tool. |
| `conversation record-response` | required `--subject N --input JSON\|FILE\|-` | Persist one interaction against the thread's budget. |
| `reconcile-branches` | `--dry-run` | Rebase, close, or leave each open pull-request branch stranded by a realign rewrite. `--dry-run` decides without mutating anything. Realign calls this itself; the command exists for recovery and inspection. |
| `rulesets` | `--dry-run` | Reconcile the integration and release branch rulesets declared by `[rulesets]`. `--dry-run` reports drift without creating or updating anything. `repository-profile.yml` calls this itself; the command exists for recovery and inspection. |
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
