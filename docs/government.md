# vibey-gh for Governments

Public institutions adopt software under obligations no private buyer carries: every
artifact must be attributable, every automated decision reconstructible, and no part of
the operation hostage to a vendor's continued goodwill. Most release automation fails
those obligations quietly — unpinned tools drift, review verdicts outlive the code they
judged, and provenance is a convention rather than a check. `vibey-gh` was built so that
failure class cannot occur: this page states, in procurement terms, exactly what an
institution gets and how each claim is verified.

## What this is, with no prior context

`vibey-gh` is a small program that watches a software project and carries every proposed
change through checking, review, approval, publication, and record-keeping without a
person pushing it at each step — the way a well-run registry office moves a filing. A
"change" here is a precise, itemized edit to the project's files; nothing moves unless
the checks tied to that exact edit pass, and every action is written down where anyone
can read it later.

## The institutional guarantees

- **Attribution is total.** Every source file carries a provenance header and every
  change carries a provenance trailer ([the fingerprint](https://github.com/adammatthewsteinberger/vibey-gh/blob/main/README.md)),
  enforced by a required check — not by policy memo.
- **Decisions bind to evidence.** A review verdict applies only to the exact revision it
  examined ([exact-head evaluation](paper.md)); a stale approval can never wave newer
  code through. This is the property audit regimes assume and rarely get.
- **The record is public and durable.** Evaluations, repairs, merges, releases, and
  yanks land in workflow logs, signed commits, and immutable release indexes — the audit
  trail exists before any auditor asks.
- **No captive dependencies.** The package has zero runtime dependencies, publishes
  keylessly via [OIDC Trusted Publishing](https://docs.pypi.org/trusted-publishers/),
  builds from source on any machine, and its documentation, book, and
  [research paper](paper.md) regenerate from the repository alone. Exit is always
  possible; that is a design rule ([doctrine 10.a](https://github.com/adammatthewsteinberger/vibey-gh/issues/210)),
  not a promise.
- **Degraded operation is first-class.** Loss of a paid service, a network, or a vendor
  relationship moves work to local lanes and back automatically
  ([sovereign operation](paper.md)) — continuity of operations is in the code, not in a
  binder.
- **Governance is written law.** [The Constitution](constitution.md),
  [the Bill of Rights](bill-of-rights.md), [the Ten Commandments](commandments.md), and
  [standing subdoctrine SD-01](sd-01-counterparties-trust-verification.md) bind every
  agent, human and machine; ratified changes supersede all prior artifacts
  (Article V.4), so nothing circulates under superseded law.

## Verification, not trust

Each claim above is checkable from a clean machine with public materials: install the
pinned release, run `vibey-gh check --ci`, read the rulesets, replay a release run's
logs against its tag. [The configuration reference](configuration.md) names every
policy knob; [the CLI reference](cli.md) names every operation. The formal statements —
soundness, termination, monotone releases, the supersession invariant — are in
[the research paper](paper.md) with proofs or proof sketches.

An institution that adopts this gets what the opening promised: attributable artifacts,
reconstructible decisions, and an exit that never closes. The concrete next step is one
command — `pip install "vibey-gh==1.58.0"` — followed by
[the adoption guide](adoption.md) on a repository that matters to you.
