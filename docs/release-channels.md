# Release channels

<p class="hero-copy">Every successful release produces matching documentation, Python
packages, OCI artifacts, provenance, and release metadata.</p>

| Branch | Python registry | Documentation | GitHub Package tag |
| --- | --- | --- | --- |
| `develop` | TestPyPI development release | `/develop/` | `develop` |
| `main` | PyPI stable release | `/main/` | `main` and `latest` |

The GitHub Package is an OCI artifact containing the exact wheel and source distribution
published by the corresponding Python release job. Version and commit-SHA tags are also
written so consumers can select an immutable artifact.

GitHub Pages exposes one deployment per repository. The release workflow assembles both
ProperDocs builds into that one deployment so updating either channel preserves the other.

## One source, two promises

`develop` is the earliest honest view of what is coming next. Its uniquely versioned
development distributions are safe to publish repeatedly and its documentation updates
without replacing the production reference.

`main` is the stable promise. It receives rebase-merged promotions only after the exact
head has passed scans, review, and merge policy. Its Python and OCI artifacts are derived
from the same build output.

## Immutable where it matters

Channel tags make discovery convenient. Version and `sha-<commit>` tags make every
published artifact reproducible. A channel may move forward; an immutable release
identity does not.
