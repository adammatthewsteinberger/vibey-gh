# Workflow reference

Repair and conflict publication are optimistic exact-head updates. Immediately before
committing, and again after any non-fast-forward push rejection, the trusted publisher
compares the PR head with the SHA that was evaluated. A concurrent update converts the old
run into a successful stale no-op; it never force-pushes, overwrites newer work, consumes a
repair attempt, or mutates a permanent branch from an obsolete checkout.

Issue automation turns an eligible published issue into one guarded solution branch and
linked pull request, which then enters this same path with no exemption. Branch intake
opens draft PRs. CI and provenance validate code. Documentation validates
the complete docs contract and periodically authors guarded refresh PRs. PR automation
aggregates exact-head scans, reviews outside contributions, repairs failures, and resolves
conflicts. The merge train squash-merges to develop and rebase-merges promotions to main.
Release publishes develop builds to TestPyPI and main builds to PyPI. Release surfaces
publish branch-specific ProperDocs and GHCR artifacts; repository profile maintains
description, homepage, topics, and verifies releases, deployments, and packages. If a
trusted post-merge workflow fails on `develop` or `main`, release repair reviews its logs
and returns a fixable problem through an ordinary guarded PR.

`CI` and `Release` are not managed templates; `vibey-gh install` never writes them, because
every repository's build, test, and publish steps differ. They must exist under those exact
names, because `github-release.yml`, `release-surfaces.yml`, and `release-repair.yml` all
key off a `workflow_run` named `Release` (and `release-repair.yml` also watches `CI`). A
`Release` workflow that runs on `develop`/`main`, derives the version with `vibey-gh
version --apply`, builds, and publishes through the `testpypi`/`pypi` trusted-publishing
environments is what the rest of this reference assumes exists.

## Issue automation

`Issue automation` runs on `issues` (`opened`, `reopened`, `labeled`), `workflow_dispatch`
with an issue number, and — when `[issue_automation].retain_schedule_backstop` is set — a
twice-daily recovery sweep that dispatches only the issues `vibey-gh issue-automation
list-eligible` reports.

The `evaluate` job holds `contents: read` and `issues: read`. It runs trusted default-branch
workflow code, installs the published `vibey-gh` package (never the adopting repository's
own package), and emits one structured decision: `solve`, `skip`, or `blocked`, each with a
stated reason. Only `solve` starts the privileged `solve` job; `blocked` labels and comments
once through the `exhausted` job.

The `solve` job checks out trusted automation under `automation/` and the configured base
branch under `target/` with `persist-credentials: false`. A trusted step renders the issue
into `briefing/issue.md`; the pinned Claude Code Action then runs from a disposable
credential-free Git context with `Read,Glob,Grep,Edit,Write` and no `Bash`, `gh`, or
`Agent` tool, and is told the briefing is an untrusted report rather than an instruction.
It edits files only.

Publication is a separate trusted step that validates the branch against the configured
namespace and the permanent branches, normalizes provenance headers with
`vibey-gh check --ci --apply`, commits with the repository's own configured trailer from
`vibey-gh trailer`, pushes one non-empty-source refspec, and opens one linked pull request
containing `Closes #N`. It publishes nothing when the agent returned `solved=false` or
produced no diff. `branch-intake.yml` is rendered to ignore the same namespace so the two
never race. From there the proposal is an ordinary pull request with no exemption from
scans, review, repair, or the merge train.

Attempts are budgeted per issue content fingerprint and stored in one machine-readable
issue comment, so a redispatch of unchanged text is a no-op and an edit starts a new
lineage.

## CodeQL

`CodeQL` runs on push and pull request against `develop` and `main`, plus a weekly Monday
schedule as a backstop. With `security-events: write` and read-only `contents: read`, it
runs the immutably pinned `github/codeql-action` initializer and analyzer against the
Python codebase. It is one of the required `scan_workflows` entries PR automation
aggregates before publishing the merge gate.

## API drift

`API drift` (workflow name `API drift (Cloud Agents OpenAPI)`) runs on the same push and
pull-request events as CodeQL, with read-only `contents: read` permission. It installs the
package and calls `vibey_gh.surfaces.parity()` to prove every canonical capability is
exposed through all five surfaces — MCP, API, CLI, SDK, and webhook — failing the run on
any drift between them. It is also a required `scan_workflows` entry.

## Conventional Commits

`Conventional Commits` runs from trusted base-branch workflow code on PR open, reopen,
synchronization, and ready-for-review events. It inspects the exact PR head without
executing repository code. For same-repository, linear topic branches, it normalizes every
nonconforming subject, preserves commit bodies and provenance trailers, and publishes the
rewritten history with an exact-SHA `--force-with-lease`. It refuses forks, merge commits,
stale heads, and any branch named by the configured integration or release branch; the
literal `develop` and `main` names are denied independently as defense in depth. It never
deletes a branch. The resulting synchronize event reruns all ordinary scans.

## Automation bootstrap

`Automation bootstrap` is a manual `workflow_dispatch` with three required inputs: the PR
number, the exact reviewed head SHA, and an explicit `authorize` boolean. It exists only for
the case where privileged workflow code itself is broken and a PR therefore cannot repair
its own gate. With `contents: write`, `pull-requests: write`, and `checks: read`, the job
verifies that the dispatching actor holds administrator permission; that the PR is open,
non-draft, targets `develop`, and exactly matches the dispatched head SHA; that changed
files are confined to workflow, template, or automation-core paths; and that every non-gate
check run on that exact SHA — including CodeQL, API drift, the Documentation contract,
Provenance, Build, and Lint — completed successfully. Only then does it perform an
admin `--match-head-commit` squash merge into `develop`, bypassing ordinary PR automation
review, and delete the source branch, and only when that branch is same-repository and not
a configured or literal permanent branch. See [Security](security.md) and
[Threat model](threat-model.md) for the full rationale.
