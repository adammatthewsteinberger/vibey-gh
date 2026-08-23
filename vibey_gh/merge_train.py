# Made with love by Vibey, the auto-vibecoding machine by Adam Matthew Steinberger.
"""The merge train: review every open pull request into the integration branch and merge
the ones that are ready.

"Ready" is mechanical, and deliberately not a judgement of the code — code review is a
human's job, and a branch ruleset's. This decides only whether a change may merge
UNATTENDED: not a draft, no conflicts, checks green, nobody has asked for changes.

Who may merge unattended is the other half. A pull request from the owner or one of their
own bots merges on a green build; from anyone else it additionally needs an approving
review, because "CI passed" is not a review and an outside change must not reach the
integration branch on a robot's say-so.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, cast

from vibey_gh.config import GhConfig, normalise_actor
from vibey_gh.pr_automation import BLOCKED_LABEL, EXHAUSTED_LABEL, EXTERNAL_REPAIR_LABEL

NEEDS_REVIEW_LABEL = "needs-human-review"
# The phrase the owner-notification comment is recognised by. Matching on our own text is
# what keeps the mention to once per pull request; see hold_for_review().
_NOTIFIED_MARKER = "awaiting your review"


@dataclass
class Verdict:
    number: int
    title: str
    author: str
    reason: str | None  # None means ready to merge
    # True when the ONLY thing standing in the way is the owner's approval. A draft or a
    # failing build is the contributor's to fix and needs no notification; an outside
    # contribution that is green and simply unapproved is waiting on the owner, and
    # nobody finds out unless someone says so.
    held_for_review: bool = False

    @property
    def ready(self) -> bool:
        return self.reason is None


def _gh_json(*args: str) -> Any:
    """Parsed JSON from `gh`. Any, not object: the shape differs per subcommand and the
    callers below index into it."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    if r.returncode:
        raise RuntimeError(f"gh {' '.join(args)}: {r.stderr.strip()}")
    return json.loads(r.stdout or "null")


def _gh(*args: str) -> tuple[bool, str]:
    """Run `gh` and report whether it worked. Never raises: these are courtesy actions
    around a merge decision that has already been made, and failing to apply a label is
    not a reason to abandon the train."""
    r = subprocess.run(["gh", *args], capture_output=True, text=True, check=False)
    return r.returncode == 0, (r.stdout or "") + (r.stderr or "")


def hold_for_review(verdict: Verdict, cfg: GhConfig, label: str = NEEDS_REVIEW_LABEL) -> None:
    """Label a held pull request and mention the owner, once.

    Once is the important part. Repeating the mention every week would train the owner to
    ignore it, which is the opposite of the point, so an existing notification is detected
    before another is posted.
    """
    number = str(verdict.number)
    if label:
        ok, _ = _gh("pr", "edit", number, "--add-label", label)
        if not ok:
            # The usual reason is that the label does not exist yet in this repository.
            _gh(
                "label",
                "create",
                label,
                "--color",
                "D93F0B",
                "--description",
                "Outside contribution awaiting the code owner",
            )
            _gh("pr", "edit", number, "--add-label", label)

    owner = cfg.owner
    if not owner:
        return
    ok, existing = _gh("pr", "view", number, "--json", "comments", "-q", ".comments[].body")
    if ok and _NOTIFIED_MARKER in existing:
        return
    _gh(
        "pr",
        "comment",
        number,
        "--body",
        f"@{owner} this pull request is green but comes from @{verdict.author}, who is not "
        f"on the merge train's trusted list, so it is **{_NOTIFIED_MARKER}** rather than "
        f"merging automatically. Approve it and the next train will take it.",
    )


def judge(pr: dict, cfg: GhConfig) -> Verdict:
    author = (pr.get("author") or {}).get("login", "")
    rollup = pr.get("statusCheckRollup") or []
    review = pr.get("reviewDecision") or ""
    labels = {
        label.get("name", "") if isinstance(label, dict) else str(label)
        for label in pr.get("labels") or []
    }

    pending = [c for c in rollup if c.get("status") not in (None, "COMPLETED")]
    failing = [
        c for c in rollup if c.get("conclusion") not in (None, "SUCCESS", "NEUTRAL", "SKIPPED")
    ]

    reason = None
    held = False
    if pr.get("isDraft"):
        reason = "draft"
    elif pr.get("mergeable") == "CONFLICTING":
        reason = f"conflicts with {cfg.integration_branch}"
    elif pr.get("mergeStateStatus") == "BEHIND":
        reason = "head branch is behind its target"
    elif labels & {BLOCKED_LABEL, EXHAUSTED_LABEL}:
        reason = "PR automation requires operator action"
    elif review == "CHANGES_REQUESTED":
        reason = "changes requested"
    elif pending:
        reason = f"{len(pending)} check(s) still running"
    elif failing:
        reason = f"{len(failing)} check(s) failing"
    else:
        trusted = {normalise_actor(a) for a in cfg.trusted_authors}
        if cfg.owner:
            trusted.add(normalise_actor(cfg.owner))
        automation_passed = any(
            c.get("name") == "PR automation / gate"
            and c.get("status") == "COMPLETED"
            and c.get("conclusion") == "SUCCESS"
            for c in rollup
        )
        untrusted = normalise_actor(author) not in trusted or EXTERNAL_REPAIR_LABEL in labels
        if cfg.pr_automation.enabled and not automation_passed:
            reason = (
                "automated outside-author review has not passed"
                if untrusted
                else "PR automation gate has not passed"
            )
        elif untrusted and not cfg.pr_automation.enabled and review != "APPROVED":
            owner = cfg.owner or "the code owner"
            reason = f"from @{author} and not approved — needs {owner}'s review"
            held = True

    return Verdict(pr["number"], pr.get("title", ""), author, reason, held_for_review=held)


_PR_FIELDS = (
    "number,title,state,isDraft,mergeable,mergeStateStatus,reviewDecision,"
    "statusCheckRollup,author,labels,headRefOid,headRefName,baseRefName,isCrossRepository"
)


def pull_request(number: int) -> dict:
    pr = cast(dict, _gh_json("pr", "view", str(number), "--json", _PR_FIELDS))
    _include_exact_head_gate(pr)
    return pr


def _include_exact_head_gate(pr: dict) -> None:
    """GitHub may omit a freshly API-created check from a PR rollup for a few seconds.

    The check is already durable on the exact commit. Reading that authoritative endpoint
    closes the event-to-merge race without relaxing any gate: only a completed successful
    check with the exact required name is copied into the rollup.
    """
    rollup = pr.setdefault("statusCheckRollup", [])
    if any(item.get("name") == "PR automation / gate" for item in rollup):
        return
    sha = str(pr.get("headRefOid") or "")
    if not sha:
        return
    repository = _gh_json("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    response = _gh_json("api", f"repos/{repository}/commits/{sha}/check-runs")
    for item in response.get("check_runs", []):
        if (
            item.get("name") == "PR automation / gate"
            and item.get("status") == "completed"
            and item.get("conclusion") == "success"
        ):
            rollup.append({"name": item["name"], "status": "COMPLETED", "conclusion": "SUCCESS"})
            return


def open_pull_requests(cfg: GhConfig, number: int | None = None) -> list[dict]:
    if number is not None:
        return [pull_request(number)]
    numbers = _gh_json(
        "pr",
        "list",
        "--base",
        cfg.integration_branch,
        "--state",
        "open",
        "--json",
        "number",
        "--jq",
        "sort_by(.number)",
    )
    out: list[dict] = []
    for entry in numbers or []:
        out.append(pull_request(int(entry["number"])))
    return out


def method_for(pr: dict, cfg: GhConfig, default: str = "squash") -> str:
    return "rebase" if pr.get("baseRefName") == cfg.release_branch else default


def should_delete_head(pr: dict, cfg: GhConfig) -> bool:
    """Delete merged topic branches, never permanent or contributor-fork branches."""
    head = str(pr.get("headRefName") or "")
    permanent = {"main", "develop", cfg.integration_branch, cfg.release_branch}
    return bool(head) and head not in permanent and not pr.get("isCrossRepository", False)


def delete_head_branch(pr: dict) -> bool:
    """Best-effort deletion after a successful merge; never called for permanent refs."""
    repository = _gh_json("repo", "view", "--json", "nameWithOwner")["nameWithOwner"]
    head = str(pr["headRefName"])
    ok, _ = _gh("api", f"repos/{repository}/git/refs/heads/{head}", "--method", "DELETE")
    return ok


def merge(number: int, method: str = "squash") -> tuple[bool, bool]:
    """(merged, bypassed). Plain merge first: it is refused while a ruleset's
    approving-review requirement is unmet — even for an admin's token, because bypassing
    is opt-in per call — so fall back to --admin, which succeeds only if the token really
    carries the admin role."""
    # Never ask GitHub to delete the head branch. In particular, the promotion PR's head
    # is `develop`; deleting it after a develop -> main merge would destroy a permanent
    # branch even though the merge itself was correct.
    base = ["gh", "pr", "merge", str(number), f"--{method}"]
    if subprocess.run(base, capture_output=True, text=True, check=False).returncode == 0:
        return True, False
    return (
        subprocess.run(base + ["--admin"], capture_output=True, text=True, check=False).returncode
        == 0,
        True,
    )
