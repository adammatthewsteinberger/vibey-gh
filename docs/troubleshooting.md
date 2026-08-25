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
- A `PR automation / gate` failure titled `review incomplete` means every scan passed but
  the exact-head review never returned a verdict. Read the review job log: the usual causes
  are an exhausted Anthropic credit balance, a missing or expired `ANTHROPIC_API_KEY`, or
  model unavailability. The gate deliberately fails closed rather than inferring a verdict,
  so correct the operator condition and rerun the review — do not merge past it.
- Repeated repair attempts that only reformat the same file mean the repository's
  formatters disagree with each other. The repair agent has no shell and cannot run one,
  so it hand-formats; if `ruff` and `isort` reject each other's output the loop can never
  converge and the budget is spent for nothing. Run each formatter in turn on a file with
  the disputed shape and check whether the other still accepts it, then match their
  configuration — `test_the_configured_formatters_agree_with_each_other` guards this.
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
