# Start here

You push code to GitHub, and then the chores start: wait for the tests, click
merge, remember a version number, cut a release, fix the changelog, update the
docs site. Miss any step and something ships wrong; do them all and you have
spent your evening being a release robot.

`vibey-gh` is a tool that does those chores for you. You push a branch; it
opens the pull request, waits for your tests, has an AI reviewer read the
change, fixes small problems itself, merges when everything is green, picks the
next version number from what actually changed, publishes the package, and
updates the documentation site. When something genuinely needs a human — a
missing password, a judgment call — it stops and says so instead of guessing.

Nothing here costs money to use and nothing gets a worse version for free
users: it is the same tool at full capability for everyone.

## Your first thirty minutes

1. [A guided first session](first-session.md) — install it on one repository
   and watch it do one real thing, with every command copy-pasteable.
2. [The glossary bridge](glossary.md) — every project word, defined in plain
   language, linked to the page with the full depth.

When those feel comfortable, [Adoption](../adoption.md) is the complete map,
and everything after it in the navigation is the engineering reference —
same site, more depth, in the order you'll need it.
