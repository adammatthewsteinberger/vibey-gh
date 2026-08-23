# Threat model

Protected assets include repository contents, permanent branches, secrets, packages,
releases, Pages deployments, provenance, and maintainer identity. Adversaries may control
fork contents, PR metadata, logs, model prompts, generated output, and dependency names.
Controls include no privileged execution of PR code, exact-SHA decisions, argument/path
validation, bounded attempts, guarded refspecs, immutable pins, independent CI, and no
delete/force operations on main or develop. Operators must protect repository secrets and
review ruleset changes.
