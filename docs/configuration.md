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

## `[pr_automation]`

| Field | Type / default | Meaning |
|---|---|---|
| `enabled` | boolean / `true` | Enable event-driven evaluation, review, repair, and gating. |
| `scan_workflows` | string list / CI, Provenance, CodeQL, Docs, API drift | Workflow names that trigger evaluation. |
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
| `required_checks` | string list / integration: `pr_automation.scan_workflows` plus `PR automation / gate`; release: `["CI", "Provenance", "CodeQL", "Docs"]` | Required status-check contexts. Empty omits the check requirement entirely. |
| `strict_required_checks` | boolean / `true` | Require the branch to be up to date with its base before merging. |
| `required_approvals` | integer / integration: `0`, release: `1` (0–6) | Required approving reviews. Integration defaults to `0` because PR automation gates it instead. |
| `dismiss_stale_reviews` | boolean / `true` | Dismiss stale reviews when new commits are pushed. |
| `require_conversation_resolution` | boolean / `true` | Require every review thread to be resolved before merging. |
| `require_linear_history` | boolean / `true` | Forbid merge commits onto the branch. |
| `require_signed_commits` | boolean / `false` | Require every commit to be signed. |
| `allow_force_pushes` | boolean / `false` | **Rejected at load time if `true`.** A permanent branch can never be configured to allow force pushes. |
| `allow_deletions` | boolean / `false` | **Rejected at load time if `true`.** A permanent branch can never be configured to allow deletion. |
| `bypass_actors` | string list / empty | `"<ActorType>:<id>"` entries such as `"RepositoryRole:5"`, granted to bypass the ruleset. Empty means nobody. |

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
