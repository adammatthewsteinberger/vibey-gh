# Testing strategy

The suite requires 100% first-party line coverage. Unit tests cover configuration,
decision logic, subprocess contracts, idempotency, and failures. Template tests parse all
YAML, require immutable action pins, assert least privilege, and prohibit permanent-branch
deletion. Dogfood tests compare installed workflows with rendered templates byte for byte.
Release acceptance additionally observes real GitHub runs and public surfaces.
