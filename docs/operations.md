# Operations

`ANTHROPIC_API_KEY` is required. Add `AUTOMERGE_TOKEN` only when the default
`GITHUB_TOKEN` cannot satisfy branch rulesets or repository-settings writes; PyPI/TestPyPI
use trusted publishing environments. Enable Actions write permissions, PR creation,
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
