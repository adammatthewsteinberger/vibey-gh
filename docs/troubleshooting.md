# Troubleshooting

- A skipped automation gate usually means evaluation occurred while checks were pending;
  dispatch the exact-head evaluation after scans finish.
- A merge blocked only by self-review may use the documented ruleset fallback only after
  every independent policy gate passes and the owner explicitly authorizes it.
- An empty Anthropic key means it was configured as an environment secret instead of a
  repository secret for a job without that environment.
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
