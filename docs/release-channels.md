# Release channels

Every successful release produces matching documentation and package surfaces.

| Branch | Python registry | Documentation | GitHub Package tag |
| --- | --- | --- | --- |
| `develop` | TestPyPI development release | `/develop/` | `develop` |
| `main` | PyPI stable release | `/main/` | `main` and `latest` |

The GitHub Package is an OCI artifact containing the exact wheel and source distribution
published by the corresponding Python release job. Version and commit-SHA tags are also
written so consumers can select an immutable artifact.

GitHub Pages exposes one deployment per repository. The release workflow assembles both
ProperDocs builds into that one deployment so updating either channel preserves the other.
