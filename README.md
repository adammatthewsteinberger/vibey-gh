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

Reviews every open pull request into the integration branch and merges the ready ones.
"Ready" is mechanical and deliberately not a judgement of the code — that is a human's job
and a ruleset's. It decides only whether a change may merge *unattended*: not a draft, no
conflicts, checks green, nobody has asked for changes.

Who may merge unattended is the other half. A pull request from the owner or one of their
own bots merges on a green build; from anyone else it additionally needs an approving
review, because "CI passed" is not a review.

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
