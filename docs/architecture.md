# Architecture

The canonical, whole-project machine-readable architecture is
[`project.mmd`](project.mmd). It is a required Mermaid artifact enforced by deterministic
and semantic review gates; changes to modules, interfaces, workflows, security boundaries,
or release paths must update it in the same pull request.

`vibey-gh` is a dependency-free Python CLI whose configuration model feeds pure policy
decisions, GitHub CLI adapters, installation code, and immutable workflow templates.
Configuration lives in `.vibey-gh.toml`; templates are rendered during installation and
their exact bytes are verified in CI. Remote mutation is isolated to explicit commands
and guarded workflow steps. PR automation separates untrusted inspection/editing from
trusted commit and push operations. Issue automation applies the same separation to a
lower-authority input: `vibey_gh.issue_automation` decides eligibility, renders untrusted
issue text into a bounded briefing, and leaves branch publication to a trusted step.
`vibey_gh.conversation` applies the same pattern to a third, even lower-authority input —
a comment mentioning the configured trigger — deciding eligibility (mention, trust,
interaction budget, and a self-reply loop guard checked first), rendering the untrusted
thread into a bounded briefing, and leaving both the reply and any bounded file change to a
trusted step. `vibey_gh.github_state` is the single implementation of durable
marker-comment state, shared by all three.

When the primary Claude review returns no verdict at all, `vibey_gh.local_review` offers an
opt-in fallback: a smaller, locally served model (through an Ollama-compatible endpoint)
reviews the same diff on a distinct, non-privileged self-hosted runner and reports a
narrower verdict than the primary review's documentation-contract schema. It is a separate
security boundary from every other AI path in this project — a self-hosted rather than
GitHub-hosted runner, excluded from fork pull requests by `trusted_only` — documented in
full in [Configuration](configuration.md) under `[pr_automation.fallback]`.

See also the [threat model](threat-model.md), [workflow reference](workflows.md), and
[configuration reference](configuration.md).
