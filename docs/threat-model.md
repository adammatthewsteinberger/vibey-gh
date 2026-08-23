# Threat model

Protected assets include repository contents, permanent branches, secrets, packages,
releases, Pages deployments, provenance, and maintainer identity. Adversaries may control
fork contents, PR metadata, logs, model prompts, generated output, and dependency names.
Controls include no privileged execution of PR code, exact-SHA decisions, argument/path
validation, bounded attempts, guarded refspecs, immutable pins, independent CI, and no
delete/force operations on main or develop. The narrow exception is a lease-protected
force-update of a same-repository topic branch to repair commit subjects; exact-head,
linear-history, repository-ownership, and permanent-branch guards all precede it. A fork,
merge commit, stale event, or concurrent push fails closed. Operators must protect
repository secrets and review ruleset changes.
