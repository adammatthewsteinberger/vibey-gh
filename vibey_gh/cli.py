# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""`vibey-gh` — the command the hooks and the CI workflows call."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

from vibey_gh import (
    documentation,
    fingerprints,
    github_release,
    install,
    merge_train,
    pr_automation,
    promote,
    realign,
    surfaces,
    versioning,
)
from vibey_gh.config import load_config


def _check(args) -> int:
    cfg = load_config()
    ok, problems = install.installed(cfg, local=not args.ci)
    report = fingerprints.check(cfg, rev_range=args.commits, apply=args.apply)
    docs = documentation.check(cfg)

    if args.quiet:
        return 0 if (ok and report.ok and docs.ok) else 1

    for problem in problems:
        print(f"  hooks: {problem}", file=sys.stderr)
    for path in report.missing_header:
        print(f"  {path.relative_to(cfg.root)}: missing the fingerprint header", file=sys.stderr)
    for commit in report.missing_trailer:
        print(f"  commit {commit}: missing the `{cfg.trailer_key}:` trailer", file=sys.stderr)
    for commit in report.invalid_subject:
        print(f"  commit {commit}: subject is not a Conventional Commit", file=sys.stderr)
    for problem in docs.problems:
        print(f"  documentation: {problem}", file=sys.stderr)

    if ok and report.ok and docs.ok:
        scope = f"{report.checked_files} source file(s)"
        if args.commits:
            scope += f" and every commit in {args.commits}"
        print(f"vibey-gh: ok — hooks installed; {scope} carry the fingerprint")
        return 0

    print("\nvibey-gh: FAILED", file=sys.stderr)
    print(f"\n  header:  {cfg.header}", file=sys.stderr)
    print(f"  trailer: {cfg.trailer}", file=sys.stderr)
    print(
        "\n  `vibey-gh check --apply` adds missing headers; `vibey-gh install` installs the hooks.",
        file=sys.stderr,
    )
    return 1


def _install(args) -> int:
    cfg = load_config()
    for action in install.install(cfg):
        print(f"  {action.hook}: {action.outcome}")
    for notice in install.installation_notices():
        print(f"  notice: {notice}")
    print(f"vibey-gh: installed into {cfg.root}")
    return 0


def _conventional_message(args) -> int:
    if args.file:
        message = args.file.read_text(encoding="utf-8")
        args.file.write_text(fingerprints.normalize_commit_message(message), encoding="utf-8")
    else:
        print(fingerprints.normalize_commit_message(sys.stdin.read()), end="")
    return 0


def _conventional_check(args) -> int:
    invalid = fingerprints.commits_with_invalid_subject(args.commits, load_config())
    for commit in invalid:
        print(commit)
    return 1 if invalid else 0


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


def _summary_rows(rows: list[tuple[int, str, str]], merged: int, skipped: int) -> str:
    """A markdown table for the job summary. A run that merged nothing still has to say
    what it looked at, or the only way to find out is to read the log."""
    lines = ["| PR | Title | Outcome |", "|---|---|---|"]
    lines += [f"| #{n} | {t} | {outcome} |" for n, t, outcome in rows]
    lines += ["", f"Merged {merged}, skipped {skipped}."]
    return "\n".join(lines) + "\n"


def _merge_train(args) -> int:
    cfg = load_config()
    prs = (
        merge_train.open_pull_requests(cfg, number=args.pr)
        if args.pr is not None
        else merge_train.open_pull_requests(cfg)
    )
    if not prs:
        print(f"vibey-gh: no open pull requests into {cfg.integration_branch}")
        _write_summary(args, "No open pull requests.\n")
        return 0

    merged = skipped = 0
    rows: list[tuple[int, str, str]] = []
    for pr in prs:
        v = merge_train.judge(pr, cfg)

        if not v.ready:
            # Only a pull request held on the owner's approval gets labelled and
            # announced. A draft or a red build is the contributor's to fix and needs no
            # notification; this one is waiting on somebody who does not know yet.
            if v.held_for_review and not args.dry_run and args.label != "":
                merge_train.hold_for_review(v, cfg, label=args.label)
            print(f"  #{v.number} skipped — {v.reason}")
            rows.append((v.number, v.title, f"skipped — {v.reason}"))
            skipped += 1
            continue

        if args.dry_run:
            print(f"  #{v.number} would merge ({args.method})")
            rows.append((v.number, v.title, f"would {args.method}-merge"))
            continue

        method = merge_train.method_for(pr, cfg, args.method)
        ok, bypassed = merge_train.merge(v.number, method)
        if ok:
            note = " (review requirement bypassed)" if bypassed else ""
            cleanup = ""
            if merge_train.should_delete_head(pr, cfg):
                cleanup = (
                    "; deleted merged topic branch"
                    if merge_train.delete_head_branch(pr)
                    else "; topic-branch cleanup failed"
                )
            print(f"  #{v.number} {method}-merged{note}{cleanup}")
            rows.append((v.number, v.title, f"{method}-merged{note}{cleanup}"))
            merged += 1
        else:
            print(f"  #{v.number} could not be merged — the ruleset refused it")
            rows.append((v.number, v.title, "blocked by the ruleset"))
            skipped += 1

    print(f"vibey-gh: merged {merged}, skipped {skipped}")
    _write_summary(args, _summary_rows(rows, merged, skipped))
    return 0


def _read_json(value: str) -> dict:
    if value == "-":
        raw = sys.stdin.read()
    else:
        path = Path(value)
        try:
            is_file = path.is_file()
        except OSError:
            # Inline JSON may exceed the platform's filename length limit.
            # A failed path probe must not prevent parsing the value itself.
            is_file = False
        raw = path.read_text(encoding="utf-8") if is_file else value
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise TypeError("input JSON must be an object")
    return parsed


def _pr_automation(args) -> int:
    cfg = load_config()
    try:
        if args.action == "evaluate":
            print(pr_automation.evaluate_pr(args.pr, args.head_sha, cfg).to_json())
        elif args.action == "ready-draft":
            result = pr_automation.ready_draft(args.pr, args.head_sha, cfg)
            print(json.dumps(result, sort_keys=True))
        elif args.action in {"record-review", "record-repair"}:
            kind = args.action.removeprefix("record-")
            state = pr_automation.record(args.pr, _read_json(args.input), kind)
            print(json.dumps(asdict(state), sort_keys=True))
        elif args.action == "mirror-fork":
            print(json.dumps(pr_automation.mirror_fork(args.pr, cfg), sort_keys=True))
        elif args.action == "ensure-labels":
            pr_automation.ensure_labels()
            print("vibey-gh: PR automation labels are ready")
        else:  # pragma: no cover - argparse constrains this
            raise ValueError(f"unknown action: {args.action}")
    except (RuntimeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"vibey-gh: {exc}", file=sys.stderr)
        return 1
    return 0


def _github_release(args) -> int:
    cfg = load_config()
    try:
        result = github_release.publish(cfg, target=args.target, version=args.version)
    except (RuntimeError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"vibey-gh: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


def _write_summary(args, text: str) -> None:
    """Append to the job summary when running in Actions. Best-effort: a summary that
    cannot be written is not a reason to fail a train that merged correctly."""
    path = args.summary or os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)
    except OSError as exc:
        print(f"vibey-gh: could not write the summary: {exc}", file=sys.stderr)


def _promote(args) -> int:
    try:
        result = promote.promote(
            load_config(), dry_run=args.dry_run, method=args.method, wait=args.wait
        )
    except RuntimeError as exc:
        print(f"vibey-gh: {exc}", file=sys.stderr)
        return 1
    for note in result.notes:
        print(f"  {note}")
    print(f"vibey-gh: {result.changed_files} file(s) differ; version {result.version}")
    _write_summary(args, _promotion_summary(result))
    return 0


def _promotion_summary(result) -> str:
    lines = ["## Promotion", ""]
    lines += [f"- {note}" for note in result.notes]
    lines += ["", f"Files differing: {result.changed_files}", f"Version: `{result.version}`"]
    return "\n".join(lines) + "\n"


def _realign(args) -> int:
    try:
        _changed, message = realign.realign(load_config())
    except RuntimeError as exc:
        print(f"vibey-gh: {exc}", file=sys.stderr)
        return 1
    print(f"vibey-gh: {message}")
    return 0


def _surface(args) -> int:
    try:
        arguments = json.loads(args.arguments)
        if not isinstance(arguments, list):
            raise TypeError("arguments must be a JSON array")
        if args.cmd == "api":
            status, payload = surfaces.api_dispatch(
                "POST",
                f"/v1/capabilities/{args.capability}",
                json.dumps({"arguments": arguments}).encode(),
            )
        elif args.cmd == "mcp":
            payload = surfaces.mcp_dispatch(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {"name": args.capability, "arguments": {"arguments": arguments}},
                }
            )
            status = 200 if "result" in payload else 400
        elif args.cmd == "sdk":
            result = surfaces.invoke(args.capability, arguments)
            status, payload = 200, result.as_dict()
        else:
            secret = os.environ.get("VIBEY_GH_WEBHOOK_SECRET", "").encode()
            body = json.dumps({"capability": args.capability, "arguments": arguments}).encode()
            signature = (
                "sha256="
                + __import__("hmac").new(secret, body, __import__("hashlib").sha256).hexdigest()
            )
            state_dir = Path(
                os.environ.get(
                    "VIBEY_GH_WEBHOOK_STATE_DIR",
                    str(load_config().root / ".vibey-gh" / "webhook-deliveries"),
                )
            )
            status, payload = surfaces.WebhookDispatcher(secret, delivery_dir=state_dir).dispatch(
                args.delivery, signature, body
            )
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"vibey-gh: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0 if status == 200 else 1


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

    conventional = sub.add_parser(
        "conventional-message", help="normalize a commit message to Conventional Commits"
    )
    conventional.add_argument("--file", type=Path, help="rewrite this commit-message file")
    conventional.set_defaults(func=_conventional_message)

    conventional_check = sub.add_parser(
        "conventional-check", help="verify Conventional Commit subjects in a range"
    )
    conventional_check.add_argument("--commits", required=True, metavar="RANGE")
    conventional_check.set_defaults(func=_conventional_check)

    m = sub.add_parser("merge-train", help="merge every ready pull request")
    m.add_argument("--method", default="squash", choices=("squash", "rebase", "merge"))
    m.add_argument("--pr", type=int, help="evaluate only this pull request")
    m.add_argument("--dry-run", action="store_true")
    m.add_argument(
        "--label",
        default=merge_train.NEEDS_REVIEW_LABEL,
        help="label applied to a pull request held for the owner's review; "
        "pass an empty string to apply none",
    )
    m.add_argument(
        "--summary",
        metavar="FILE",
        help="write a markdown table here (default: $GITHUB_STEP_SUMMARY)",
    )
    m.set_defaults(func=_merge_train)

    automation = sub.add_parser(
        "pr-automation", help="evaluate and persist event-driven PR automation state"
    )
    automation_sub = automation.add_subparsers(dest="action", required=True)
    evaluate = automation_sub.add_parser("evaluate", help="classify one exact PR head")
    evaluate.add_argument("--pr", type=int, required=True)
    evaluate.add_argument("--head-sha", required=True)
    evaluate.set_defaults(func=_pr_automation)
    ready = automation_sub.add_parser(
        "ready-draft", help="mark an exact stable draft head ready for review"
    )
    ready.add_argument("--pr", type=int, required=True)
    ready.add_argument("--head-sha", required=True)
    ready.set_defaults(func=_pr_automation)
    for command in ("record-review", "record-repair"):
        record = automation_sub.add_parser(command, help=f"persist a structured {command[7:]}")
        record.add_argument("--pr", type=int, required=True)
        record.add_argument("--input", required=True, help="JSON object, file, or - for stdin")
        record.set_defaults(func=_pr_automation)
    mirror = automation_sub.add_parser(
        "mirror-fork", help="open a repository-owned replacement for a fork PR"
    )
    mirror.add_argument("--pr", type=int, required=True)
    mirror.set_defaults(func=_pr_automation)
    labels = automation_sub.add_parser("ensure-labels", help="create or update automation labels")
    labels.set_defaults(func=_pr_automation)

    release = sub.add_parser(
        "github-release", help="idempotently create an immutable version tag and GitHub Release"
    )
    release.add_argument("--target", required=True, help="exact main commit SHA to tag")
    release.add_argument("--version", help="version override (default: configured version file)")
    release.set_defaults(func=_github_release)

    p = sub.add_parser("promote", help="promote the integration branch to the release branch")
    p.add_argument(
        "--method", default=promote.DEFAULT_METHOD, choices=("rebase", "squash", "merge")
    )
    p.add_argument("--dry-run", action="store_true")
    wait_mode = p.add_mutually_exclusive_group()
    wait_mode.add_argument(
        "--wait",
        action="store_true",
        help="legacy synchronous mode: wait for checks and merge in this process",
    )
    wait_mode.add_argument(
        "--no-wait",
        action="store_false",
        dest="wait",
        help="open the promotion PR and let event-driven automation merge it (default)",
    )
    p.add_argument(
        "--summary", metavar="FILE", help="write markdown here (default: $GITHUB_STEP_SUMMARY)"
    )
    p.set_defaults(func=_promote)

    r = sub.add_parser("realign", help="realign the integration branch with the release branch")
    r.set_defaults(func=_realign)

    for surface in ("api", "mcp", "sdk", "webhook"):
        adapter = sub.add_parser(surface, help=f"invoke a capability through the {surface} adapter")
        adapter.add_argument("capability", choices=surfaces.CAPABILITIES)
        adapter.add_argument("--arguments", default="[]", help="JSON array of capability arguments")
        if surface == "webhook":
            adapter.add_argument("--delivery", required=True, help="unique webhook delivery ID")
        adapter.set_defaults(func=_surface)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
