# vibey-gh

Release automation for a GitHub repository: provenance fingerprints, derived version
bumps, a merge train, and post-release branch realignment.

**No dependencies.** Everything is stdlib. This runs in every CI job of every repository
that adopts it, so a dependency it grows is a dependency all of them grow.

```bash
pip install vibey-gh
vibey-gh install
```

`install` writes the git hooks and workflow files into your repository and points
`core.hooksPath` at them. A hook you already have is moved aside to `<name>.local` and
chained, never discarded — adopting this should not silently drop checks somebody thought
were important.

## What it does

### Provenance, enforced in two places

Every code change carries a fingerprint. Source files get a header comment; **every commit
gets a trailer**. The trailer is what makes the rule total — a change to a Markdown file or
a JSON manifest still arrives as a commit, and the commit is fingerprinted even when the
file cannot be.

```bash
vibey-gh check                 # are the hooks installed and the fingerprints intact?
vibey-gh check --apply         # add the missing file headers
vibey-gh check --commits main..HEAD    # and every commit trailer in a range
```

The `pre-push` hook refuses the push if either half is missing, to any branch, local or
remote. `git push --no-verify` still works, because a hook that cannot be bypassed in an
emergency gets uninstalled instead; CI applies the same rule server-side, so skipping it
locally defers the failure rather than avoiding it.

### Versions derived, not remembered

```bash
vibey-gh version --since origin/main --explain     # what should this release be?
vibey-gh version --since origin/main --apply       # write it to every version file
vibey-gh version --dev "$GITHUB_RUN_NUMBER"        # <release>.dev<n> for a TestPyPI build
```

| what changed | bump |
|---|---|
| a `content_path` | **minor** — users receive something new |
| only a `code_path` | **patch** — an internal fix |
| neither | **none** — docs and CI do not reach an installed user |
| the version already moved | **none** — a deliberate bump is in place; never double it |

`none` is a legitimate answer. This has to be automatic: a PyPI upload with
`skip-existing` turns an unbumped release into a green run that publishes nothing,
silently, with no warning anywhere. A human-maintained version is a silent-failure
generator.

Version files may be Python (`__version__ = "..."`), JSON (a `version` key, at the top
level or under `metadata`), or TOML (the `[project]` table — and only that table, because
`pyproject.toml` has others carrying a `version` key and bumping the wrong one is worse
than not bumping).

### The merge train

```bash
vibey-gh merge-train --dry-run
vibey-gh merge-train --method squash
```

The normal path is event-driven: the PR-automation gate dispatches
`vibey-gh merge-train --pr NUMBER` as soon as the exact current head is green. The weekly
and manual modes remain recovery backstops. A ready PR is open, current with its target,
conflict-free, green, free of requested changes, and carries a successful exact-head
`PR automation / gate` when an outside-author review is required.

Outside authors receive a fresh structured Claude review after scans pass. Findings feed
the same bounded repair loop as failed scans. Forks are never mutated with privileged
credentials; when a fork needs edits, automation preserves its exact head in a linked
repository-owned replacement PR.

### PR review and repair automation

`branch-intake.yml` opens exactly one draft PR when a new same-repository topic branch is
first pushed. It ignores the integration branch, release branch, and automation-owned fork
repair branches. Later pushes reuse the existing PR. Once the configured scans for the
exact draft head are complete and green, PR automation marks it ready and immediately
continues through review, repair, gating, and the merge train. Pending, failing, stale,
conflicting, closed, and fork draft heads are no-ops; they are never promoted prematurely.

`pr-automation.yml` reacts to configured scan-workflow completions, re-reads the entire
current-head check rollup, and publishes an explicit check run on that exact SHA. It waits
for pending scans, separates cancelled infrastructure from actionable failures, and allows
at most three repair commits per contributor lineage. A new contributor commit starts a
new lineage; bot repair pushes do not reset the counter.

Conflicting same-repository PRs enter a bounded conflict-resolution job instead of failing
permanently. The job materializes Git's exact unresolved path set without executing
repository code, gives the constrained agent read/search/edit access only, rejects edits
outside that set, rechecks the head SHA, and publishes one ordinary non-force resolution
commit. Fork conflicts continue through the repository-owned replacement-PR path. Conflict
attempts share the three-attempt repair budget, so an ambiguous merge cannot loop forever.

Review and repair use the immutable-pinned Claude Code Action with selected `vibey-skills`.
The privileged jobs may inspect source and CI logs but may not execute contributor package
managers, tests, builds, scripts, or binaries. Ordinary PR CI validates every repair push.
The agent has no Git mutation tool: one trusted publisher may push a non-empty source
(`HEAD:refs/heads/<exact-pr-branch>`) only to the exact PR branch. This deliberately
permits forward updates to `develop` or `main` when either is the PR head, while making a
Git deletion refspec (`:branch`) structurally impossible. Managed merges automatically
update `develop` and `main`, but no managed command uses `--delete`, `--delete-branch`, an
empty-source refspec, or a branch-deletion API.
Repositories must configure `ANTHROPIC_API_KEY`; `AUTOMERGE_TOKEN` is required where the
default Actions token cannot push or merge through the repository ruleset. Installation
does not create either secret.

```bash
vibey-gh pr-automation evaluate --pr 123 --head-sha HEAD_SHA
vibey-gh pr-automation ready-draft --pr 123 --head-sha HEAD_SHA
vibey-gh pr-automation mirror-fork --pr 123
vibey-gh merge-train --pr 123
```

### The promotion

```bash
vibey-gh promote --dry-run
vibey-gh promote
```

Moves the integration branch to the release branch, which is what publishes. Three things
it gets right that a hand-written workflow usually does not:

- **It compares by content, not by commit count.** The release branch is rebase-merged, so
  its commits are rewritten copies with different SHAs; the integration branch always looks
  "ahead" even when the trees are identical. A diff is the only honest test.
- **It derives the version before opening anything.** An upload with `skip-existing` turns
  an unbumped promotion into a green run that publishes nothing, silently.
- **It hands the PR to the same event gate as every other change.** `promote` no longer
  holds a runner open with `gh pr checks --watch`; scans, automated review, and the
  exact-head merge train finish the promotion asynchronously. `--wait` retains the legacy
  synchronous mode for recovery.

### Realignment

```bash
vibey-gh realign
```

When the release branch is rebase-merged its commits are rewritten copies with new SHAs,
so the integration branch's tip is never an ancestor of it and a fast-forward is
impossible — yet a ruleset with a strict up-to-date policy treats it as behind, which
blocks the next promotion.

The guard is **tree equality, not ancestry**: this runs only when a diff between the two
branches is empty, so it converges two identical contents onto one history and cannot
discard work. If the integration branch has anything the release branch does not, it is
left alone and says so.

## Configuration

```toml
[pr_automation]
enabled = true
scan_workflows = ["CI", "Provenance", "CodeQL", "Docs", "API drift (Cloud Agents OpenAPI)"]
ignored_checks = ["PR automation / gate", "Merge train / merge"]
max_repair_attempts = 3
model = "claude-sonnet-5"
review_untrusted_authors = true
repair_untrusted_authors = true
replace_fork_prs = true
retain_schedule_backstop = true

[github_release]
enabled = true
tag_prefix = "v"
generate_notes = true
```

After the configured `Release` workflow succeeds on `main`, the managed
`github-release.yml` workflow tags that exact commit and creates a generated-notes GitHub
Release. It is safe to rerun: an existing matching tag/release is reused, while an
existing tag at a different SHA is never moved and fails loudly.

Everything project-specific lives in `.vibey-gh.toml`, so the logic beside it stays
general. Every key has a default; a repository that agrees with them needs no file at all.

```toml
[fingerprint]
text    = "Made with love by ..."          # the source-header comment
trailer = "Made-With: ..."                 # the commit trailer
sources = ["src/**/*.py", ".github/workflows/*.yml"]

[version]
files         = ["pyproject.toml", "src/pkg/__init__.py"]
content_paths = ["plugins/"]               # a change here is a MINOR release
code_paths    = ["src/"]                   # a change here alone is a PATCH

[branches]
integration = "develop"
release     = "main"

[merge_train]
owner           = "your-login"
trusted_authors = ["your-login", "dependabot[bot]"]
```



### Taking the hooks without the workflows

`install` writes the managed workflows alongside the hooks. A repository that already has richer
ones of its own can decline them:

```toml
[install]
workflows = []          # hooks and the CLI only
# workflows = ["provenance.yml"]   # or just the ones you want
```

This is not cosmetic. `check` verifies that everything it manages is present and current,
so without it a repository that deliberately keeps its own workflows would fail the check
forever — and a check that cannot pass is a check people route around.


`trusted_authors` is matched after normalising `app/name` and `name[bot]` to the same
thing. `gh` reports a bot author with the `app/` prefix while the rest of GitHub writes
`[bot]`; a literal allow-list matches whichever spelling it happens to contain and
silently distrusts the other, which once caused an automation to quarantine its own pull
request as an outside contribution.

## What is deliberately not fingerprinted

- **Files whose bytes are meaningful** — generated documents verified against a source,
  Markdown loaded into a model's context. A header would be a diff against the source.
- **Anything without comment syntax** — JSON, most notably.

The commit trailer covers both without touching them. A naive "comment in every changed
file" rule cannot express itself in JSON and corrupts content that is checked byte for
byte.

## Licence

MIT. See [LICENSE](LICENSE).
