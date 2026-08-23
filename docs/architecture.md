# Architecture

`vibey-gh` is a dependency-free Python CLI whose configuration model feeds pure policy
decisions, GitHub CLI adapters, installation code, and immutable workflow templates.
Configuration lives in `.vibey-gh.toml`; templates are rendered during installation and
their exact bytes are verified in CI. Remote mutation is isolated to explicit commands
and guarded workflow steps. PR automation separates untrusted inspection/editing from
trusted commit and push operations.

See also the [threat model](threat-model.md), [workflow reference](workflows.md), and
[configuration reference](configuration.md).
