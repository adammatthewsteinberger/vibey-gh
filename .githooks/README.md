# Managed Git hooks

`commit-msg` enforces provenance trailers and `pre-push` checks source fingerprints.
`vibey-gh install` configures `core.hooksPath` and chains pre-existing local hooks rather
than discarding them. CI independently verifies committed hook files.
