# Configuration reference

Configuration lives in `.vibey-gh.toml`. Every key is optional; omitted values use the
defaults below. Paths are repository-relative unless stated otherwise.

## `[fingerprint]`

| Field | Type / default | Meaning |
|---|---|---|
| `text` | string / built-in provenance sentence | Required source-header text. |
| `trailer` | string / `Made-With: ...` | Required commit trailer. |
| `sources` | string list / Python and workflow globs | Files checked for headers. |

## `[version]`

| Field | Type / default | Meaning |
|---|---|---|
| `files` | string list / empty | Version-bearing files updated by `version --apply`. |
| `content_paths` | string list / empty | Paths whose changes produce a minor bump. |
| `code_paths` | string list / `["src/"]` | Paths whose changes produce a patch bump. |

## `[branches]`, `[merge_train]`, and `[install]`

| Field | Type / default | Meaning |
|---|---|---|
| `branches.integration` | string / `develop` | Integration and preview branch. |
| `branches.release` | string / `main` | Production branch; managed automation never deletes it. |
| `merge_train.owner` | string / empty | Normalized repository-owner login. |
| `merge_train.trusted_authors` | string list / empty | Authors exempt from outside-author review. |
| `install.workflows` | string list / all managed workflows | Exact managed subset; `[]` installs hooks and CLI assets only. |
| `install.union_merge_paths` | string list / `["CHANGELOG.md"]` | Files declared `merge=union` in `.gitattributes`, so two branches appending to the same section merge instead of conflicting. Appended to an existing `.gitattributes`, never rewriting it. `[]` declares none. |
| `install.pin_version` | boolean / `false` | Pin every managed workflow's `pip install vibey-gh` to the exact version that rendered it (`vibey-gh==X.Y.Z`), instead of the latest release on every run. `false` keeps the historical floating install. The self-hosting path (this repository, and anything else installing from its own `pyproject.toml`) is never pinned — it installs from source regardless. Running `vibey-gh install` from a newer release moves the pin forward as one visible diff. |

## `[ai]`

Where every AI step sends its requests. Unset, nothing changes: requests go to Anthropic
exactly as before this existed.

| Field | Type / default | Meaning |
|---|---|---|
| `base_url` | URL / empty | Endpoint override. Empty uses the Anthropic default. Must be `http(s)` and contain no whitespace. |
| `auth_secret` | secret name / `ANTHROPIC_API_KEY` | The repository secret authorising those requests. A name only — never a token; this file is committed. |

### Running the automation somewhere other than Anthropic

Every AI step runs Claude Code, which honours `ANTHROPIC_BASE_URL`. Any gateway serving
the Anthropic Messages API — LiteLLM and similar translate it to Gemini, Qwen, GitHub
Models, a model on your own machine — therefore works without this project learning a
second vendor's request shape:

```toml
[ai]
base_url = "https://your-gateway.example/v1"
auth_secret = "LITELLM_KEY"
```

That secret fills both `x-api-key` and `Authorization`, because Claude Code sends the
former while some gateways read the latter. A gateway must serve `/v1/messages` **and**
`/v1/messages/count_tokens`, and forward the `anthropic-beta` and `anthropic-version`
headers.

One caveat worth testing before you rely on it: the review and repair steps depend on
structured JSON output and tool calls, and translation layers vary in how faithfully they
carry `tool_use` arguments across providers. A provider that mangles them makes the gate
report `review incomplete` rather than approving anything — it fails closed — but the
review is then no longer running. Verify against a real pull request before turning off
the endpoint you trust.

`auth_secret` is validated as a bare secret identifier. It is rendered inside a
`${{ secrets.… }}` expression in a privileged workflow, so a name that could close that
expression is refused at load time.

## `[pr_automation]`

| Field | Type / default | Meaning |
|---|---|---|
| `enabled` | boolean / `true` | Enable event-driven evaluation, review, repair, and gating. |
| `scan_workflows` | string list / CI, Provenance, CodeQL, Docs | Workflow names that trigger evaluation. Every name must be a workflow with a `pull_request` or `pull_request_target` trigger — one that only runs on `push` can never complete for a pull request, so `state` never leaves `pending`, the gate never publishes, and — made a required check — no pull request can ever merge. `vibey-gh check` fails on any named workflow that exists but cannot fire for a pull request; a name absent from `.github/workflows/` is not an error. |
| `ignored_checks` | string list / orchestration checks | Checks excluded from the ordinary rollup. Own checks are always ignored. |
| `max_repair_attempts` | integer / `3` (1–10) | Repair budget per contributor lineage. |
| `model` | string / `claude-sonnet-5` | Review and repair model. |
| `review_untrusted_authors` | boolean / `true` | Require exact-head outside-author review. |
| `repair_untrusted_authors` | boolean / `true` | Permit constrained outside-author repairs. |
| `replace_fork_prs` | boolean / `true` | Repair forks through linked repository-owned PRs. |
| `retain_schedule_backstop` | boolean / `true` | Retain scheduled recovery beside event triggers. |

### `[pr_automation.observability]`

| Field | Type / default | Meaning |
|---|---|---|
| `sanitized_progress` | boolean / `true` | Request safe action progress only for Claude-supported direct PR/issue events; automated workflow events retain phase-level job visibility. |
| `archive_execution_file` | boolean / `true` | Retain each Claude execution record as a 90-day workflow artifact. |
| `allow_private_full_output` | boolean / `false` | Permit an explicit manual diagnostic run to emit raw Claude JSON, but only in a private repository. |

Raw output additionally requires a manual `workflow_dispatch` with
`full_claude_output = true`. Event-triggered runs can never enable it, and the workflow
fails closed when repository visibility is not private.

### `[pr_automation.fallback]`

Reviews with a local model when the paid path returns **no verdict at all** — an exhausted
API key, expired credentials, an unavailable model. Because the gate is a required check,
that failure otherwise turns a billing problem into a hard stop on every pull request.

| Field | Type / default | Meaning |
|---|---|---|
| `enabled` | boolean / `false` | Off unless a repository opts in. It needs a self-hosted runner, so nothing should inherit it. |
| `runner_label` | string / `"vibey-local"` | Label the fallback job targets, alongside `self-hosted`. |
| `model` | string / `"qwen2.5-coder:14b"` | Model tag served by the Ollama-compatible endpoint. |
| `base_url` | string / `"http://127.0.0.1:11434"` | Where the local model listens. |
| `trusted_only` | boolean / `true` | Never run the fallback for a fork pull request. |
| `max_diff_chars` | integer / `60000` | Diff is truncated past this, and the model is told it was. |
| `timeout_seconds` | integer / `600` | Bound on one review. |

It never overrides a review that actually ran: the job requires the primary to have
produced no verdict, so findings are never discarded in favour of a weaker opinion. The
diff is passed to the model as text — repository code is never executed, and the model has
no shell, no tools, and no network beyond the local port.

The verdict is deliberately narrower than the primary review's. Ollama constrains decoding
to the schema, so the output *shape* is guaranteed; the *judgments* are not, and a 14B model
will emit confident booleans it has no basis for. So it assesses only what it can ground in
a diff — `pass`, `summary`, `findings` — and reports the documentation-contract fields as
unevaluated. The gate titles the result `PR automation: gate (local fallback)` so a
degraded verdict is never mistaken for a full one.

`trusted_only` carries the safety argument. GitHub says self-hosted runners should "almost
never be used for public repositories" because any user can open a pull request against
them; excluding forks is what removes that. Leave it on, register the runner as ephemeral
so it takes one job and exits, and run it in a container rather than on the host.

## `[conversation]`

Answers a mention in a comment on an issue or pull request. Comments are the least guarded
input a repository has, so the defaults are closed.

| Field | Type / default | Meaning |
|---|---|---|
| `enabled` | boolean / `true` | Respond to mentions at all. |
| `trigger` | string / `@vibey-gh` | The mention that addresses the automation. Matched on a word boundary, so `@vibey-gh-bot` is not a mention. |
| `model` | string / `claude-sonnet-5` | Model that reads the thread and answers. |
| `max_interactions` | integer / `10` (1–100) | Responses per thread, so a conversation cannot become an unbounded work queue. |
| `respond_to_untrusted` | boolean / `false` | Answer commenters outside the owner/trusted set. A response costs tokens, so answering everyone is a deliberate spending decision. |
| `allow_changes` | boolean / `true` | Permit file changes. Only ever on a pull request, only from a trusted commenter, and never on a fork or permanent branch. |
| `ignore_actors` | string list / the automation's own bot identities | **The loop guard.** Its own reply mentions the trigger too; answering it would run and bill forever. Cannot be empty while enabled. |

An issue is answered in words only — there is nowhere to put a commit. A pull request from
a trusted commenter may also receive one guarded commit on its own branch.

## `[branch_sync]`

Keeps open branches current so conflicts never accumulate, and refills a spent repair
budget a bounded number of times so a transient outage does not become a permanent stop.

| Field | Type / default | Meaning |
|---|---|---|
| `enabled` | boolean / `true` | Run the sync and self-heal jobs at all. |
| `update_contributor_branches` | boolean / `true` | Merge the integration branch forward into branches this automation does not own, using GitHub's own update-branch endpoint. Never a rewrite. |
| `max_self_heals` | integer / `2` (0–10) | How many times one lineage's repair budget may be refilled before it stays exhausted for a human. `0` disables self-healing. |

A fork is only ever moved *forward*, never rewritten: `update-branch` succeeds only where
the contributor left "allow maintainer edits" enabled, so it carries their consent.
Rebasing, closing, and deleting are unreachable for a fork under every setting.

## `[realign]`

Realign converges the integration branch onto the release branch with a lease-protected
force update, which replaces commits with rewritten copies and strands any topic branch cut
from one of them. These keys decide how much the automation may do about that unaided.

| Field | Type / default | Meaning |
|---|---|---|
| `reconcile_branches` | boolean / `true` | Reconcile open pull-request branches after a realign rewrite. |
| `automation_prefixes` | string list / `["vibey-gh/"]` | Branch prefixes this automation may rebase on its own. Everything else is a human's to rebase. |
| `close_duplicates` | boolean / `true` | Close a pull request whose every commit is already upstream by patch identity. |
| `delete_duplicate_branches` | boolean / `true` | Delete that branch too. Permanent, fork, and unsafe refs are refused by name regardless. |
| `notify_contributor_branches` | boolean / `true` | Comment on a human's stranded branch with the rebase command instead of rewriting it. |

Decisions use `git cherry`, which compares by patch identity, so a commit re-created
upstream under a new SHA is correctly recognised as already present. A ref that cannot be
read reports unique work rather than none, so an unreadable branch is never closed.

## `[issue_automation]`

Turns a published issue into a reviewable pull request. Every field exists because an
adopting repository could reasonably disagree with the default; the defaults themselves are
closed, because anyone with a GitHub account can open an issue.

| Field | Type / default | Meaning |
|---|---|---|
| `enabled` | boolean / `true` | Enable evaluation and autonomous solution proposals. `false` keeps the workflow installed and inert. |
| `model` | string / `claude-sonnet-5` | Model used to design and implement the proposed solution. |
| `max_attempts` | integer / `2` (1–10) | Solution budget per issue content lineage. |
| `max_turns` | integer / `200` (1–1000) | Turn budget for one attempt. An attempt that exhausts it produces nothing, so raise it for a repository whose issues are routinely large — or split the issue, which is usually the better answer. |
| `branch_prefix` | string / `vibey-gh/issue` | Namespace every proposal branch lives under. Validated against the configured permanent branches and rendered into `branch-intake.yml`'s ignore list. |
| `base_branch` | string / empty | Branch a solution is built on. Blank uses `branches.integration`. |
| `solve_untrusted_authors` | boolean / `false` | Permit issues from outside the owner/trusted-author set without a maintainer label. |
| `required_label` | string / `vibey-gh:solve` | Label that opts an outside author's issue in. Empty disables that path entirely. |
| `trigger_labels` | string list / empty | When set, only issues carrying one of these labels are ever attempted. |
| `ignored_labels` | string list / question, discussion, duplicate, wontfix, `vibey-gh:solve-blocked` | Issues carrying one of these are never attempted, whoever wrote them. |
| `open_pull_request` | boolean / `true` | Open a linked pull request after publishing the branch. |
| `draft_pull_request` | boolean / `true` | Open that pull request as a draft, letting PR automation promote it when its exact head is green. |
| `retain_schedule_backstop` | boolean / `true` | Retain the scheduled recovery sweep beside the event triggers. |

An issue's attempt budget is keyed to a SHA-256 fingerprint of its title and body, so
re-running automation on unchanged text cannot spend the budget twice and editing the issue
starts a fresh lineage. Managed labels are `vibey-gh:solve`, `vibey-gh:solving`,
`vibey-gh:solution-proposed`, `vibey-gh:solve-exhausted`, and `vibey-gh:solve-blocked`.

### Documenting your project, not this one

A repository that installs vibey-gh documents **its own product**. It is still held to the
agent-docs *layout* — those files describe the adopter's project and make it navigable to an
agent — but nothing about their contents describes vibey-gh: no `## Why vibey-gh` heading in
their product README, no branded provenance sentence, no architecture surfaces named after
this tool's modules.

Every entry in `required_files` is required: having one never excuses another.

| Field | Type / default | Meaning |
|---|---|---|
| `required_files` | string list / the agent-docs layout | Files that must exist and be non-empty, each one individually. |
| `readme_sections` | string list / empty | Headings required in `README.md`, in your own words. |
| `automation_doc` | path / `.github/AUTOMATION.md` | Where this repository's automation documentation lives. **Not `.github/README.md`** — GitHub resolves that as the repository's landing README ahead of the root one, so naming it that replaces your product README on your repository's front page. |
| `automation_doc_sections` | string list / empty | Headings required in `automation_doc`. Also read from the former name `github_readme_sections`. |
| `automation_doc_min_words` | integer / `0` | Minimum length for `automation_doc`; `0` disables. Also read from the former name `github_readme_min_words`. |
| `mermaid_terms` | string list / empty | Surfaces that must appear in `docs/project.mmd`. |
| `mermaid_min_edges` | integer / `0` | Minimum `-->` edges in that diagram; `0` disables. |
| `require_provenance` | boolean / `false` | Require the Vibey provenance sentence in `provenance_files`. |
| `provenance_files` | string list / `README.md`, `docs/index.md` | Where that sentence is required, when it is. |

This repository declares the full contract for itself in its own `.vibey-gh.toml`, which is
both the dogfooding rule the rest of the tool follows and the reason its own requirements
are visible rather than compiled in.

## `[yank]`

Report which releases on an index the just-published version supersedes.

**It reports. It cannot yank, and neither can anything else you write.** PyPI exposes no
API for yanking. The legacy upload endpoint answers `405 Method Not Allowed` for
`:action=yank` (a recognised action such as `:action=file_upload` answers `403` on bad
credentials, so authentication is never even reached), and the `/manage/...` route the web
UI uses is CSRF-protected against non-browser callers. Programmatic access is an open
upstream request, not a shipped capability:

- [pypa/packaging-problems#633](https://github.com/pypa/packaging-problems/issues/633)
- [pypi/warehouse#12708](https://github.com/pypi/warehouse/issues/12708)

[PyPI's own documentation](https://docs.pypi.org/project-management/yanking/) gives exactly
one method: the release management page, **Options → Yank**. No token changes this; do not
try to add one.

That is arguably the right design. [PEP 592](https://peps.python.org/pep-0592/) defines a
yanked release as one with *"a serious problem which should prevent it from being
installed"* — a distress signal, not a tidiness marker. Installers still resolve a yanked
version when a pin demands one, so nothing is reclaimed; what changes is that everyone
pinned to it starts seeing a warning about a release that may be perfectly good. The manual
click is the friction that keeps that deliberate.

So this automates the analysis and leaves the click: it works out exactly which releases
are superseded and prints them with a link to the page that can action them.

| Field | Type / default | Meaning |
|---|---|---|
| `pypi` | boolean / `false` | Report superseded PyPI releases after a publish. |
| `testpypi` | boolean / `false` | Report superseded TestPyPI releases. |
| `keep` | integer / `0` | How many releases below the newest to leave out of the report, so a rollback target is never suggested. |

Two invariants hold regardless of configuration:

- **the version just published is never listed**, excluded by identity rather than by
  version ordering;
- **a version this cannot parse is never listed.** Ordering covers `N.N.N` and
  `N.N.N.devN`, which is what this tooling publishes. Epochs, local segments, post- and
  pre-releases are left out, because half a PEP 440 parser mis-orders them silently and
  here that means naming a good release as a candidate for yanking.

Run it from a release workflow after the upload step. No credentials are involved — the
index JSON it reads is public:

```bash
vibey-gh report-superseded --index pypi --project my-package --version "$VERSION"
```

It always exits 0: the package is already published by the time it runs, so a bookkeeping
failure is reported rather than turning a successful release red.

## `[github_release]`

| Field | Type / default | Meaning |
|---|---|---|
| `enabled` | boolean / `true` | Enable immutable tags and GitHub Releases. |
| `tag_prefix` | string / `v` | Nonempty, whitespace-free tag prefix. |
| `generate_notes` | boolean / `true` | Ask GitHub to generate release notes. |
| `require_new_version` | boolean / `false` | Fail instead of silently doing nothing when a release-branch push does not carry a new version (the tag it would need already exists at a different commit). Leave off for a repository where a docs-only or tooling-only promotion is a normal, frequent, versionless push. |

## `[rulesets]`

Reconciles GitHub repository rulesets for the integration and release branches, so the
protection `repository-profile.yml` has always only *verified* is actually *set*. Branch
names are not configured here — `[rulesets.integration]` always targets
`branches.integration` and `[rulesets.release]` always targets `branches.release`.

| Field | Type / default | Meaning |
|---|---|---|
| `enabled` | boolean / `true` | Reconcile both rulesets at all. `false` leaves the repository untouched, exactly as before this feature existed. |

### `[rulesets.integration]` and `[rulesets.release]`

| Field | Type / default | Meaning |
|---|---|---|
| `required_checks` | string list / integration: `["Provenance", "Analyze Python", "Documentation contract", "PR automation / gate"]`; release: the same without the gate | Required status-check contexts — **check-run names, not workflow names** (see below). Empty omits the check requirement entirely. |
| `strict_required_checks` | boolean / `true` | Require the branch to be up to date with its base before merging. |
| `required_approvals` | integer / integration: `0`, release: `1` (0–6) | Required approving reviews. Integration defaults to `0` because PR automation gates it instead. |
| `dismiss_stale_reviews` | boolean / `true` | Dismiss stale reviews when new commits are pushed. |
| `require_conversation_resolution` | boolean / `true` | Require every review thread to be resolved before merging. |
| `require_linear_history` | boolean / `true` | Forbid merge commits onto the branch. |
| `require_signed_commits` | boolean / `false` | Require every commit to be signed. |
| `allow_force_pushes` | boolean / `false` | **Rejected at load time if `true`.** A permanent branch can never be configured to allow force pushes. |
| `allow_deletions` | boolean / `false` | **Rejected at load time if `true`.** A permanent branch can never be configured to allow deletion. |
| `bypass_actors` | string list / `["RepositoryRole:5"]` | `"<ActorType>:<id>"` entries granted to bypass the ruleset. The default is the repository admin role. `[]` means nobody — including the owner. |

### `required_checks` names check runs, not workflows

This is the one field here that can lock a branch with no way out, so it is worth stating
plainly. A required status check matches a **check run**, and for GitHub Actions a check
run is named for its **job**, not its workflow. The `CI` workflow in this repository
reports as `Lint`, `Build`, and `Test (3.12)`; nothing ever reports as `CI`.

Requiring a name nothing produces does not fail — it *waits*. The branch reports
`N of M required status checks are expected` forever, and because a ruleset has no
"include administrators" toggle the way classic branch protection did, an empty
`bypass_actors` means no one can merge past it. The only exit is editing the ruleset.

Two habits avoid it: name the job, and keep a bypass actor. `[pr_automation].scan_workflows`
names *workflows* and looks like a tempting list to reuse here — it is not one. To find the
real names, open a recent pull request's checks tab, or:

```bash
gh api "repos/OWNER/REPO/commits/$(git rev-parse HEAD)/check-runs" \
  --jq '.check_runs[].name' | sort -u
```

Reconciliation is idempotent read-compare-write, the same shape `repository-profile.yml`
already uses for settings and topics: an existing rule type the configuration does not
mention is never removed, only reported. A ruleset the API refuses fails the job with the
API's own reason rather than being silently skipped — a skipped reconciliation would look
identical to a satisfied one. Run `vibey-gh rulesets --dry-run` to inspect the diff before
a workflow run applies it.

## `[repository_profile]`

| Field | Type / default | Meaning |
|---|---|---|
| `enabled` | boolean / `true` | Reconcile repository settings. |
| `description` | string / derived | Description, at most 350 characters. |
| `topics` | string list / five automation topics | Lowercase topics, maximum 20. |
| `has_issues`, `has_projects`, `has_discussions` | boolean / `true` | Enable collaboration features. |
| `has_wiki` | boolean / `false` | Enable the wiki. |
| `allow_squash_merge`, `allow_rebase_merge`, `allow_auto_merge` | boolean / `true` | Allowed merge mechanisms. |
| `allow_merge_commit` | boolean / `false` | Permit merge commits. |
| `delete_branch_on_merge` | boolean / `false` | GitHub's own blanket auto-delete-on-merge. Keep false because `develop` heads promotion PRs and would itself be deleted. This is independent of branch cleanup: the merge train and Automation bootstrap already delete a merged PR's head branch themselves, through a guarded API call, whenever it is not a permanent, integration, or release branch and not a fork — regardless of this setting. |
| `web_commit_signoff_required` | boolean / `true` | Require web-editor signoff. |
| `vulnerability_alerts`, `automated_security_fixes` | boolean / `true` | Enable dependency security services. |

## `[documentation]`

| Field | Type / default | Meaning |
|---|---|---|
| `enabled`, `ai_maintenance` | boolean / `true` | Require and AI-maintain the documentation suite. |
| `model` | string / `claude-sonnet-5` | Documentation model. |
| `required_files` | string list / built-in FOSS and agent suite | Required documentation paths. |
| `production_label`, `preview_label` | strings / `Production`, `Preview` | Human-facing channel names. |
| `production_indexing` | boolean / `true` | Permit production indexing. |
| `preview_indexing` | boolean / `false` | Permit preview indexing. |
| `generate_robots`, `generate_sitemap_index`, `generate_llms_txt`, `generate_llms_full_txt`, `generate_json_ld` | boolean / `true` | Generate robot, search, LLM, and structured metadata. |
| `author_name` | string / `Adam Matthew Steinberger` | Reserved documentation-provenance author label. Parsed and validated (non-empty), but not yet emitted into any generated asset. |
| `author_url` | URL / `https://hire.adam.matthewsteinberger.com` | Reserved documentation-provenance author destination. Same current scope as `author_name`. |
| `google_analytics_id` | string / empty (disabled) | GA4 measurement ID (`G-<alphanumeric>`) injected into every page of both generated documentation channels and the channel-picker page. Empty disables Google Analytics entirely: no script tag is emitted and no request ever reaches Google. |
| `site_requirements` | string list / empty | Extra packages installed before the published site is built, as PEP 508 requirement specifiers. Each is shell-quoted, so `"mkdocs-material[imaging] >= 9.5"` stays one argument. |
| `site_requirements_file` | path / `docs/requirements.txt` | Installed with `pip install -r` when the file exists. Absent, the step is skipped; empty disables the hook entirely. |
| `properdocs_version` | string / `1.6.7` | The `properdocs` and `properdocs-theme-mkdocs` version the site build pins. |

### Installing what your site actually needs

ProperDocs depends on `properdocs` and its theme, and on nothing your `properdocs.yml`
declares. A site configuring `mkdocs-gen-files`, `mkdocs-literate-nav`, a Material theme,
or any `pymdownx.*` markdown extension needs those packages present, or the `--strict`
build fails on the first one it reaches — the plugin is simply not installed.

Declare them once, either inline or in the conventional requirements file:

```toml
[documentation]
site_requirements = [
  "mkdocs-gen-files",
  "mkdocs-literate-nav",
  "pymdown-extensions>=10.7",
]
```

Both hooks are no-ops when unused, so a repository whose site needs nothing extra is
unaffected. This cannot have a useful default: which packages a site needs follows from
that site's own configuration.

`author_name` and `author_url` exist for a planned author credit in the generated
Pages sites and are exercised by config parsing, validation, and tests today. The
`release-surfaces.yml` JSON-LD record currently emits only `@context`, `@type`,
`name`, `codeRepository`, `url`, and `version` — no author field — so setting these
two keys has no visible effect on a generated site yet.

Run `vibey-gh install`, review and commit generated assets, then run
`vibey-gh check --ci`. Identity and Pages URLs are derived at runtime.

## Advanced debug environment

| Variable | Default | Meaning |
|---|---|---|
| `VIBEY_GH_DEBUG` | unset | Set to `1`, `true`, `yes`, or `on` to enable structured branch tracing. |
| `VIBEY_GH_DEBUG_LOG` | stderr | Append JSONL trace events to this operator-controlled path. |
| `VIBEY_GH_TRACE_ID` | generated UUID | Correlate the trace with a wider diagnostic session. |

GitHub correlation is read from `GITHUB_RUN_ID`, `GITHUB_RUN_ATTEMPT`, and `GITHUB_SHA`.
These controls affect diagnostics only; source validation always confirms that every
configured Python control-flow opcode can be represented by the tracer.

These environment variables only ever scope the tracer to `vibey_gh`'s own installed
package directory; there is no CLI flag or environment variable to point it at a
consuming project's source tree. A project embedding `vibey_gh.debugging` directly can
call `enable(roots=(...))` with its own package directories to trace its own code instead.
