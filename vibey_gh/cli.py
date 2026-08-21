# Made with love by Vibey, the auto-vibecoding machine by Adam Matthew Steinberger.
"""`vibey-gh` — the command the hooks and the CI workflows call."""

from __future__ import annotations

import argparse
import sys

from vibey_gh import fingerprints, install, merge_train, realign, versioning
from vibey_gh.config import load_config


def _check(args) -> int:
    cfg = load_config()
    ok, problems = install.installed(cfg, local=not args.ci)
    report = fingerprints.check(cfg, rev_range=args.commits, apply=args.apply)

    if args.quiet:
        return 0 if (ok and report.ok) else 1

    for problem in problems:
        print(f"  hooks: {problem}", file=sys.stderr)
    for path in report.missing_header:
        print(f"  {path.relative_to(cfg.root)}: missing the fingerprint header", file=sys.stderr)
    for commit in report.missing_trailer:
        print(f"  commit {commit}: missing the `{cfg.trailer_key}:` trailer", file=sys.stderr)

    if ok and report.ok:
        scope = f"{report.checked_files} source file(s)"
        if args.commits:
            scope += f" and every commit in {args.commits}"
        print(f"vibey-gh: ok — hooks installed; {scope} carry the fingerprint")
        return 0

    print("\nvibey-gh: FAILED", file=sys.stderr)
    print(f"\n  header:  {cfg.header}", file=sys.stderr)
    print(f"  trailer: {cfg.trailer}", file=sys.stderr)
    print(
        "\n  `vibey-gh check --apply` adds missing headers; "
        "`vibey-gh install` installs the hooks.",
        file=sys.stderr,
    )
    return 1


def _install(args) -> int:
    cfg = load_config()
    for action in install.install(cfg):
        print(f"  {action.hook}: {action.outcome}")
    print(f"vibey-gh: installed into {cfg.root}")
    return 0


def _version(args) -> int:
    cfg = load_config()
    if args.dev is not None:
        dev = versioning.dev_version(cfg, args.dev)
        if args.apply:
            versioning.apply_version(cfg, dev)
        print(dev)
        return 0
    new, why = versioning.decide(cfg, args.since)
    if args.explain or not new:
        print(f"vibey-gh: {why}", file=sys.stderr)
    if not new:
        print("none")
        return 0
    if args.apply:
        versioning.apply_version(cfg, new)
    print(new)
    return 0


def _merge_train(args) -> int:
    cfg = load_config()
    prs = merge_train.open_pull_requests(cfg)
    if not prs:
        print(f"vibey-gh: no open pull requests into {cfg.integration_branch}")
        return 0
    merged = skipped = 0
    for pr in prs:
        v = merge_train.judge(pr, cfg)
        if not v.ready:
            print(f"  #{v.number} skipped — {v.reason}")
            skipped += 1
            continue
        if args.dry_run:
            print(f"  #{v.number} would merge ({args.method})")
            continue
        ok, bypassed = merge_train.merge(v.number, args.method)
        if ok:
            note = " (review requirement bypassed)" if bypassed else ""
            print(f"  #{v.number} {args.method}-merged{note}")
            merged += 1
        else:
            print(f"  #{v.number} could not be merged — the ruleset refused it")
            skipped += 1
    print(f"vibey-gh: merged {merged}, skipped {skipped}")
    return 0


def _realign(args) -> int:
    try:
        _changed, message = realign.realign(load_config())
    except RuntimeError as exc:
        print(f"vibey-gh: {exc}", file=sys.stderr)
        return 1
    print(f"vibey-gh: {message}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vibey-gh", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="verify hooks and fingerprints")
    c.add_argument("--apply", action="store_true", help="add missing file headers")
    c.add_argument("--commits", metavar="RANGE", help="also check commit trailers, e.g. main..HEAD")
    c.add_argument("--quiet", action="store_true", help="exit status only, for hooks")
    c.add_argument(
        "--ci",
        action="store_true",
        help="skip the local core.hooksPath check, which no runner can satisfy",
    )
    c.set_defaults(func=_check)

    i = sub.add_parser("install", help="install the git hooks")
    i.set_defaults(func=_install)

    v = sub.add_parser("version", help="derive the version to release")
    v.add_argument("--since", default="origin/main")
    v.add_argument("--dev", metavar="BUILD", help="print <release>.dev<BUILD> instead")
    v.add_argument("--apply", action="store_true")
    v.add_argument("--explain", action="store_true")
    v.set_defaults(func=_version)

    for name, attr in (("trailer", "trailer"), ("trailer-key", "trailer_key")):
        p = sub.add_parser(name, help=f"print the {name}")
        p.set_defaults(func=lambda a, _attr=attr: (print(getattr(load_config(), _attr)), 0)[1])

    m = sub.add_parser("merge-train", help="merge every ready pull request")
    m.add_argument("--method", default="squash", choices=("squash", "rebase", "merge"))
    m.add_argument("--dry-run", action="store_true")
    m.set_defaults(func=_merge_train)

    r = sub.add_parser("realign", help="realign the integration branch with the release branch")
    r.set_defaults(func=_realign)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
