# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""Policy and durable state for event-driven pull-request automation.

The workflow is intentionally thin.  It gathers GitHub data, asks this module for a
decision, and dispatches an agent only for the explicit ``repair`` or ``review`` states.
That keeps stale-SHA rejection, trust, retry limits, and check classification testable.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, cast

from vibey_gh import github_state
from vibey_gh.config import GhConfig, normalise_actor
from vibey_gh.issue_automation import sanitize

STATE_MARKER = "vibey-gh-pr-automation"
EXTERNAL_REPAIR_LABEL = "vibey-gh:external-repair"
REPAIRING_LABEL = "vibey-gh:repairing"
EXHAUSTED_LABEL = "vibey-gh:repair-exhausted"
BLOCKED_LABEL = "vibey-gh:automation-blocked"
AUTOMATION_LABELS = (EXTERNAL_REPAIR_LABEL, REPAIRING_LABEL, EXHAUSTED_LABEL, BLOCKED_LABEL)
PASSING = {"SUCCESS", "NEUTRAL", "SKIPPED"}
FAILING = {"FAILURE", "TIMED_OUT", "STARTUP_FAILURE", "ACTION_REQUIRED"}
OPERATIONAL = {"CANCELLED", "STALE"}
_STATE_RE = github_state.marker_pattern(STATE_MARKER)


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    conclusion: str | None
    url: str = ""


@dataclass
class AutomationState:
    lineage_sha: str
    current_sha: str
    attempts: int = 0
    review_sha: str | None = None
    review_passed: bool | None = None
    replacement_pr: int | None = None
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class Evaluation:
    pr: int
    head_sha: str
    base: str
    author: str
    trusted: bool
    state: str
    pending_checks: tuple[str, ...] = ()
    failed_checks: tuple[str, ...] = ()
    repair_attempt: int = 0
    repair_branch: str | None = None
    reason: str = ""

    def to_json(self) -> str:
        payload = asdict(self)
        payload["pending_checks"] = list(self.pending_checks)
        payload["failed_checks"] = list(self.failed_checks)
        return json.dumps(payload, sort_keys=True)


def _check(raw: dict[str, Any]) -> Check:
    return Check(
        name=str(raw.get("name") or raw.get("context") or "unnamed check"),
        status=str(raw.get("status") or "COMPLETED").upper(),
        conclusion=(str(raw["conclusion"]).upper() if raw.get("conclusion") else None),
        url=str(raw.get("detailsUrl") or raw.get("targetUrl") or ""),
    )


def parse_state(comments: Sequence[dict[str, Any] | str]) -> AutomationState | None:
    """Return the newest valid state marker, ignoring ordinary or malformed comments."""
    data = github_state.parse_payload(comments, _STATE_RE)
    if data is None:
        return None
    try:
        return AutomationState(
            lineage_sha=str(data["lineage_sha"]),
            current_sha=str(data["current_sha"]),
            attempts=int(data.get("attempts", 0)),
            review_sha=data.get("review_sha"),
            review_passed=data.get("review_passed"),
            replacement_pr=data.get("replacement_pr"),
            history=list(data.get("history", [])),
        )
    except (KeyError, TypeError, ValueError):
        return None


def state_body(state: AutomationState, summary: str) -> str:
    return github_state.render_body(STATE_MARKER, asdict(state), "Vibey GH PR automation", summary)


def _labels(pr: dict[str, Any]) -> set[str]:
    return {
        str(label.get("name", "")) if isinstance(label, dict) else str(label)
        for label in pr.get("labels") or []
    }


def repair_refspec(branch: str) -> str:
    """Build an update-only refspec; deletion refspecs have an empty source before `:`."""
    if not branch or ":" in branch or branch.startswith("-"):
        raise ValueError(f"unsafe repair branch {branch!r}")
    return f"HEAD:refs/heads/{branch}"


def _trusted(pr: dict[str, Any], cfg: GhConfig) -> bool:
    if EXTERNAL_REPAIR_LABEL in _labels(pr):
        return False
    actor = normalise_actor(str((pr.get("author") or {}).get("login", "")))
    trusted = {normalise_actor(value) for value in cfg.trusted_authors}
    if cfg.owner:
        trusted.add(normalise_actor(cfg.owner))
    return actor in trusted


def lineage_for(stored: AutomationState | None, head: str) -> AutomationState:
    """The state that applies to `head`, starting a new lineage when it has moved on.

    `current_sha` tracks the last head automation itself produced or evaluated, so a head
    that differs from it arrived from a human. That starts a fresh attempt budget — which
    is the documented contract, and was previously computed by `evaluate` and then thrown
    away, because the persisting path built its own state and never applied the same rule.
    Both callers share this so the decision and the record cannot disagree again.
    """
    if stored is None or stored.current_sha != head:
        return AutomationState(
            lineage_sha=head,
            current_sha=head,
            history=list(stored.history) if stored else [],
        )
    return stored


def evaluate(
    pr: dict[str, Any],
    cfg: GhConfig,
    *,
    expected_sha: str,
    stored: AutomationState | None = None,
) -> Evaluation:
    """Classify one exact PR head without mutating GitHub."""
    number = int(pr["number"])
    head = str(pr.get("headRefOid") or "")
    base = str(pr.get("baseRefName") or cfg.integration_branch)
    author = str((pr.get("author") or {}).get("login", ""))
    trusted = _trusted(pr, cfg)

    def result(state: str, reason: str, **kw: Any) -> Evaluation:
        return Evaluation(number, head, base, author, trusted, state, reason=reason, **kw)

    if head != expected_sha:
        return result("blocked", f"stale event for {expected_sha}; current head is {head}")
    if pr.get("state", "OPEN") != "OPEN":
        return result("blocked", "pull request is not open")
    if pr.get("isDraft"):
        # Draft intake is intentionally nonterminal. `ready_draft` promotes the exact
        # head once its scans are stable; until then no failing gate may be published.
        return result("pending", "pull request is a draft awaiting a stable head")
    state = lineage_for(stored, head)

    labels = _labels(pr)
    if BLOCKED_LABEL in labels:
        return result("blocked", "automation is blocked pending operator action")
    if EXHAUSTED_LABEL in labels:
        return result("blocked", "repair budget is exhausted")

    if pr.get("mergeable") == "CONFLICTING":
        if state.attempts >= cfg.pr_automation.max_repair_attempts:
            return result(
                "blocked",
                "conflict resolution budget is exhausted",
                repair_attempt=state.attempts,
            )
        return result(
            "conflict",
            f"conflicts with {base}",
            failed_checks=(f"Merge conflict with {base}",),
            repair_attempt=state.attempts + 1,
        )
    if pr.get("reviewDecision") == "CHANGES_REQUESTED":
        return result("blocked", "a human requested changes")

    ignored = set(cfg.pr_automation.ignored_checks) | {
        "PR automation / gate",
        "gate",
        "Merge train / merge",
    }
    checks = [_check(item) for item in pr.get("statusCheckRollup") or []]
    checks = [item for item in checks if item.name not in ignored]
    if not checks:
        return result("pending", "no current-head scan results are available")
    pending = tuple(item.name for item in checks if item.status != "COMPLETED")
    if pending:
        return result("pending", "checks are still running", pending_checks=pending)

    operational = tuple(item.name for item in checks if item.conclusion in OPERATIONAL)
    if operational:
        return result(
            "blocked",
            "cancelled or stale checks require a rerun",
            failed_checks=operational,
        )

    failed = tuple(item.name for item in checks if item.conclusion in FAILING)
    if failed:
        if state.attempts >= cfg.pr_automation.max_repair_attempts:
            return result(
                "blocked",
                "repair budget is exhausted",
                failed_checks=failed,
                repair_attempt=state.attempts,
            )
        if not trusted and not cfg.pr_automation.repair_untrusted_authors:
            return result(
                "blocked", "repairs for untrusted authors are disabled", failed_checks=failed
            )
        return result(
            "repair",
            "completed checks are failing",
            failed_checks=failed,
            repair_attempt=state.attempts + 1,
        )

    # Every author's exact head is reviewed — the documentation audit is repository-wide,
    # and only the *scope* of the review widens for an outside author. The loop that
    # review can start must therefore be bounded for every author too. Bounding it here,
    # at the point another review would be dispatched, is what makes it finite: each
    # repair publishes a new head and clears `review_sha`, so a check placed after the
    # verdict would never be reached while heads keep advancing.
    reviewable = trusted or cfg.pr_automation.review_untrusted_authors
    if reviewable:
        if state.attempts >= cfg.pr_automation.max_repair_attempts:
            return result(
                "blocked", "review repair budget is exhausted", repair_attempt=state.attempts
            )
        if state.review_sha != head:
            return result("review", "current head requires automated review")
        if state.review_passed is not True:
            return result(
                "repair",
                "automated review has actionable findings",
                failed_checks=("Automated review",),
                repair_attempt=state.attempts + 1,
            )

    return result("ready", "all scans and applicable reviews passed")


_gh_json = github_state.gh_json


def fetch_pr(number: int) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        _gh_json(
            "pr",
            "view",
            str(number),
            "--json",
            "number,title,state,isDraft,mergeable,mergeStateStatus,reviewDecision,"
            "statusCheckRollup,author,labels,comments,headRefOid,headRefName,headRepository,"
            "headRepositoryOwner,isCrossRepository,baseRefName,body",
        ),
    )


def evaluate_pr(number: int, head_sha: str, cfg: GhConfig) -> Evaluation:
    pr = fetch_pr(number)
    return evaluate(pr, cfg, expected_sha=head_sha, stored=parse_state(pr.get("comments") or []))


def ready_draft(number: int, head_sha: str, cfg: GhConfig) -> dict[str, Any]:
    """Promote one exact, green draft head; every unstable condition is a no-op."""
    pr = fetch_pr(number)
    if str(pr.get("headRefOid") or "") != head_sha:
        return {"promoted": False, "reason": "stale head"}
    if pr.get("state", "OPEN") != "OPEN" or not pr.get("isDraft"):
        return {"promoted": False, "reason": "not an open draft"}
    if pr.get("isCrossRepository"):
        return {"promoted": False, "reason": "fork drafts are not mutated"}

    candidate = dict(pr)
    candidate["isDraft"] = False
    decision = evaluate(
        candidate,
        cfg,
        expected_sha=head_sha,
        stored=parse_state(pr.get("comments") or []),
    )
    if decision.state not in {"ready", "review"}:
        return {"promoted": False, "reason": decision.reason}

    run = subprocess.run(
        ["gh", "pr", "ready", str(number)], capture_output=True, text=True, check=False
    )
    if run.returncode:
        raise RuntimeError(f"could not mark PR ready: {run.stderr.strip()}")
    return {"promoted": True, "reason": "current head is stable"}


def updated_state(
    pr: dict[str, Any],
    payload: dict[str, Any],
    *,
    kind: str,
) -> AutomationState:
    current = parse_state(pr.get("comments") or [])
    head = str(payload.get("head_sha") or pr.get("headRefOid") or "")
    if kind == "review":
        # A review is recorded for the exact head just evaluated, so this is the one
        # record that can tell a human push apart from an automation repair — a repair
        # advances `current_sha` to its own new head as it is recorded, leaving them
        # equal. Applying the reset here is what finally persists a new lineage.
        state = lineage_for(current, head)
        state.review_sha = head
        state.review_passed = bool(payload.get("pass"))
    elif kind == "repair":
        state = current or AutomationState(lineage_sha=head, current_sha=head)
        if payload.get("fixable") is not False:
            state.attempts += 1
        state.current_sha = head
        state.review_sha = None
        state.review_passed = None
    else:
        raise ValueError(f"unknown record kind: {kind}")
    state.history.append({"kind": kind, **payload})
    return state


def upsert_state(
    number: int, state: AutomationState, summary: str, comments: list[dict[str, Any]]
) -> None:
    github_state.upsert_comment(
        number,
        state_body(state, summary),
        comments,
        _STATE_RE,
        subject="pr",
        error="could not persist PR automation state",
    )


def record(number: int, payload: dict[str, Any], kind: str) -> AutomationState:
    pr = fetch_pr(number)
    state = updated_state(pr, payload, kind=kind)
    summary = str(payload.get("summary") or f"Recorded {kind} for `{state.current_sha}`.")
    upsert_state(number, state, summary, list(pr.get("comments") or []))
    return state


def ensure_labels() -> None:
    definitions = {
        EXTERNAL_REPAIR_LABEL: ("5319E7", "Repository-owned continuation of a fork PR"),
        REPAIRING_LABEL: ("FBCA04", "Automated scan repair is in progress"),
        EXHAUSTED_LABEL: ("D93F0B", "Automated repair budget is exhausted"),
        BLOCKED_LABEL: ("B60205", "Automation requires repository-operator action"),
    }
    for name, (colour, description) in definitions.items():
        subprocess.run(
            [
                "gh",
                "label",
                "create",
                name,
                "--color",
                colour,
                "--description",
                description,
                "--force",
            ],
            capture_output=True,
            check=False,
        )


def mirror_fork(number: int, cfg: GhConfig) -> dict[str, Any]:
    """Mirror an exact fork head and open a repository-owned replacement PR."""
    pr = fetch_pr(number)
    head = str(pr["headRefOid"])
    short = head[:12]
    branch = f"vibey-gh/repair/pr-{number}-{short}"
    refspec = repair_refspec(branch)
    owner = str((pr.get("headRepositoryOwner") or {}).get("login", ""))
    repo = str((pr.get("headRepository") or {}).get("name", ""))
    if not owner or not repo:
        raise RuntimeError("pull request does not expose a fork repository")
    fetch = subprocess.run(
        ["git", "fetch", "--quiet", f"https://github.com/{owner}/{repo}.git", head],
        cwd=cfg.root,
        capture_output=True,
        text=True,
        check=False,
    )
    if fetch.returncode:
        raise RuntimeError(f"could not fetch fork head: {fetch.stderr.strip()}")
    push = subprocess.run(
        ["git", "push", "origin", refspec.replace("HEAD", head, 1)],
        cwd=cfg.root,
        capture_output=True,
        text=True,
        check=False,
    )
    if push.returncode:
        raise RuntimeError(f"could not publish repair branch: {push.stderr.strip()}")
    author = sanitize(str((pr.get("author") or {}).get("login", "")), limit=100)
    title = sanitize(str(pr.get("title", "")), limit=200)
    body = (
        f"Repository-owned repair continuation of #{number} from @{author}.\n\n"
        f"Original head: `{head}`. The original contributor retains attribution; this branch "
        "exists only because privileged automation cannot write to a contributor fork."
    )
    create = subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--base",
            str(pr["baseRefName"]),
            "--head",
            branch,
            "--title",
            f"Repair #{number}: {title}",
            "--body",
            body,
        ],
        cwd=cfg.root,
        capture_output=True,
        text=True,
        check=False,
    )
    if create.returncode:
        raise RuntimeError(f"could not open replacement pull request: {create.stderr.strip()}")
    replacement = int(re.sub(r"\D", "", create.stdout.rsplit("/", 1)[-1]))
    subprocess.run(
        ["gh", "pr", "edit", str(replacement), "--add-label", EXTERNAL_REPAIR_LABEL],
        cwd=cfg.root,
        capture_output=True,
        check=False,
    )
    subprocess.run(
        [
            "gh",
            "pr",
            "comment",
            str(number),
            "--body",
            f"Repairs continue in #{replacement}; closing this fork PR only after preserving its exact head and attribution.",
        ],
        cwd=cfg.root,
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["gh", "pr", "close", str(number)], cwd=cfg.root, capture_output=True, check=False
    )
    return {
        "original_pr": number,
        "replacement_pr": replacement,
        "branch": branch,
        "head_sha": head,
    }
