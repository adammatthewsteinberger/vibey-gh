# Troubleshooting

- A skipped automation gate usually means evaluation occurred while checks were pending;
  dispatch the exact-head evaluation after scans finish.
- A merge blocked only by self-review may use the documented ruleset fallback only after
  every independent policy gate passes and the owner explicitly authorizes it.
- An empty Anthropic key means it was configured as an environment secret instead of a
  repository secret for a job without that environment.
- An issue that never receives a proposal is almost always a stated eligibility decision
  rather than a failure: read the `Issue automation` job summary. An issue from an author
  outside `[merge_train].owner` and `trusted_authors` is skipped until a maintainer applies
  the configured `required_label`, and a configured ignored label, an absent trigger label,
  an exhausted budget, or a `vibey-gh:solve-blocked` label each produce their own reason.
- An issue labelled `vibey-gh:solve-blocked` means the attempt returned `needs_human`: the
  request needs a human decision, named in the issue's state comment. Answer it in the
  issue, then edit the body to restate the request — editing starts a new attempt lineage.
- A redispatched `Issue automation` run that does nothing is working correctly. Attempts
  are keyed to a fingerprint of the issue's title and body, so unchanged text cannot spend
  a second attempt or open a second pull request.
- Package verification should query the GHCR manifest, not account package listing APIs.
- Pages 404s require a successful deployment containing an `index.html` at each channel.
- A `vibey-gh check` failure printed as `debug logging: <path>: cannot validate branch
  logging: <ExceptionType>` means that configured Python source failed to compile (a
  syntax or encoding error), so the branch tracer in `vibey_gh/debugging.py` could not even
  parse it; fix the underlying syntax/encoding problem in that file.
- A `vibey-gh check` failure printed as `debug logging: <path>:<line>: unsupported branch
  opcode <OPCODE>` means that file contains a control-flow construct whose jump target the
  tamper-evident branch tracer cannot classify as taken or fallthrough. Simplify that
  construct, or remove the file from `[fingerprint].sources` in `.vibey-gh.toml`, rather
  than disabling the check.
