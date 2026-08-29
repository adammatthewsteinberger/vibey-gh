# Operations

`ANTHROPIC_API_KEY` is required. Add `AUTOMERGE_TOKEN` only when the default
`GITHUB_TOKEN` cannot satisfy branch rulesets or repository-settings writes; PyPI/TestPyPI
use trusted publishing environments.

## What `AUTOMERGE_TOKEN` must be able to do

The token appears in a minority of the workflows' `GH_TOKEN` assignments — reading the
pull request, commenting, labelling, merging, and pushing the promotion's version bump.
For a fine-grained personal access token that means exactly:

| Permission | Level |
|---|---|
| Contents | Read and write |
| Pull requests | Read and write |
| Workflows | Read and write |
| Actions | Read |
| Metadata | Read (mandatory) |

**Checks is deliberately absent, and the fine-grained token UI offers no such permission.**
Check runs can only be created by a GitHub App, so the gate is published with
`GITHUB_TOKEN` — which is one — and no PAT permission exists or is needed for it. The
workflows' own `permissions:` blocks govern `GITHUB_TOKEN`, not this PAT; do not read
`checks: read` there as a token requirement.

**Workflows is easy to leave out because most of what the token does never needs it** —
until a repair commit happens to touch a file under `.github/workflows/`. GitHub then
rejects the *entire* push, not just the workflow hunk, with `refusing to allow a Personal
Access Token to create or update workflow ... without \`workflow\` scope`. Pin-bump pull
requests make this the common case rather than the rare one, because the diff under
review already lives under `.github/workflows/`. A classic token's single `repo` scope
already covers this; only fine-grained tokens need the permission added explicitly.

There is deliberately no preflight that drops or skips workflow-file hunks before
attempting the push: a classic token's granted scopes are visible in every API
response's `X-OAuth-Scopes` header, but GitHub exposes no equivalent introspection for a
fine-grained token's own permission grant, so nothing running as that token can learn in
advance whether this specific push will be accepted. The push attempt itself is the only
reliable test, which is why the repair job reacts to the rejection after the fact instead
of guessing beforehand.

Four failure modes worth knowing before they cost an afternoon, because each presented as
something else in production:

- **A fine-grained token expires** (a year at most) and returns as `HTTP 401: Bad
  credentials` inside a step whose name says nothing about credentials. A classic token
  with the single `repo` scope covers everything above and supports no expiration — the
  trade is that it reaches every repository the account can.
- **A fine-grained token only reaches the repositories in its own grant list.** The secret
  being set on a repository proves nothing: two repositories out of a token's list behaved
  identically to two inside it for reads, then failed every privileged write. The merge
  train reported each failure as *"the ruleset refused it"* until it learned to print the
  API's own error.
- **The account behind the token is what bypasses rulesets.** The merge train's `--admin`
  fallback works only if that account holds a bypass role on the ruleset; the token's
  permissions cannot add standing its owner does not have.
- **A repair that touches `.github/workflows/**` without the Workflows permission is
  rejected at push, every time, no matter how correct the fix.** The `PR automation /
  gate` check reports `repair blocked (missing Workflows permission)` and names the
  cause directly rather than repeating the generic "completed checks are failing"
  reason, and the attempt is not charged against the pull request's repair budget —
  granting the permission and re-dispatching is the only fix; nothing about the repair
  itself was wrong.

## Recovering from a review with no verdict

`PR automation: review incomplete` means the primary exact-head review returned no verdict
at all — check API credit balance, the `ANTHROPIC_API_KEY` secret, and model availability,
then rerun the review; this is never a defect in the pull request. If
`[pr_automation.fallback].enabled` is set and a self-hosted `vibey-local-gh` runner is
registered, the same no-verdict condition instead dispatches a local Ollama model against
the diff; a clean local verdict passes the gate as `PR automation: gate (local fallback)`
rather than blocking it. That title always names the weaker reviewer — treat it as a
signal to still fix the primary path's root cause, not as a fully reviewed pass.

## Everything else

Enable Actions write permissions, PR creation,
GitHub Pages via Actions, Packages, Releases, and Deployments. Use workflow dispatch for
recovery. Inspect exact run and head SHA before retrying. Never solve a blocked release by
deleting, force-pushing, weakening a gate, or switching production to TestPyPI.

To retry one issue, dispatch `Issue automation` with its number; `vibey-gh
issue-automation list-eligible` shows what the scheduled sweep would pick up. A redispatch
of unchanged issue text is a no-op, so retrying is safe. An issue labelled
`vibey-gh:solve-blocked` is waiting on a human decision named in the issue's state comment,
and one labelled `vibey-gh:solve-exhausted` has spent its budget; editing the issue body
restates the request and starts a new lineage. To stop the feature without uninstalling it,
set `[issue_automation].enabled = false` in reviewed configuration.

When a bug in privileged workflow code itself blocks a repair PR from repairing its own
gate, dispatch `Automation bootstrap` (see [Workflows](workflows.md)) with the exact PR
number, exact head SHA, and explicit authorization. It requires administrator permission
and every independent gate already passing on that SHA, and it is the only path that
squash-merges to `develop` without an ordinary PR automation review.

To preview what `Branch sync` would rebase, close, update, or leave without mutating
anything, dispatch it manually with `dry_run = true`; the decisions are printed to the run
summary. The nightly schedule run of its `heal` job refills the repair budget of every pull
request labeled `vibey-gh:repair-exhausted`, up to `branch_sync.max_self_heals` times per
lineage, and re-dispatches `PR automation` against each healed PR's exact head SHA. Once
that budget is spent for a lineage, the label stays and only a human — typically by pushing
a new commit or editing the PR — starts a fresh lineage. See [Workflows](workflows.md) and
`[branch_sync]` in [Configuration](configuration.md).

When Conventional Commits rewrites a topic branch, synchronize the local checkout before
new work. Preserve unpushed work first, then use `git fetch origin` and rebase it onto the
new remote head; if there is no unpushed work, reset the local topic branch to its explicit
`origin/<branch>` ref. Never run either operation against `develop` or `main`. The workflow
has no per-run bypass: correct the commit locally when a fork or merge-containing branch
cannot be repaired automatically. Disable the managed workflow only through reviewed
`[install].workflows` configuration, which makes the policy change visible to CI.
