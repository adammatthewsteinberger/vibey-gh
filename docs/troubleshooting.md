# Troubleshooting

- A skipped automation gate usually means evaluation occurred while checks were pending;
  dispatch the exact-head evaluation after scans finish.
- A merge blocked only by self-review may use the documented ruleset fallback only after
  every independent policy gate passes and the owner explicitly authorizes it.
- An empty Anthropic key means it was configured as an environment secret instead of a
  repository secret for a job without that environment.
- Package verification should query the GHCR manifest, not account package listing APIs.
- Pages 404s require a successful deployment containing an `index.html` at each channel.
