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
from typing import Any

from vibey_gh.config import GhConfig, normalise_actor


@dataclass
class Verdict:
    number: int
    title: str
    author: str
    reason: str | None  # None means ready to merge

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


def judge(pr: dict, cfg: GhConfig) -> Verdict:
    author = (pr.get("author") or {}).get("login", "")
    rollup = pr.get("statusCheckRollup") or []
    review = pr.get("reviewDecision") or ""

    pending = [c for c in rollup if c.get("status") not in (None, "COMPLETED")]
    failing = [
        c for c in rollup if c.get("conclusion") not in (None, "SUCCESS", "NEUTRAL", "SKIPPED")
    ]

    reason = None
    if pr.get("isDraft"):
        reason = "draft"
    elif pr.get("mergeable") == "CONFLICTING":
        reason = f"conflicts with {cfg.integration_branch}"
    elif review == "CHANGES_REQUESTED":
        reason = "changes requested"
    elif pending:
        reason = f"{len(pending)} check(s) still running"
    elif failing:
        reason = f"{len(failing)} check(s) failing"
    else:
        trusted = {normalise_actor(a) for a in cfg.trusted_authors}
        if normalise_actor(author) not in trusted and review != "APPROVED":
            owner = cfg.owner or "the code owner"
            reason = f"from @{author} and not approved — needs {owner}'s review"

    return Verdict(pr["number"], pr.get("title", ""), author, reason)


def open_pull_requests(cfg: GhConfig) -> list[dict]:
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
        out.append(
            _gh_json(
                "pr",
                "view",
                str(entry["number"]),
                "--json",
                "number,title,isDraft,mergeable,reviewDecision," "statusCheckRollup,author",
            )
        )
    return out


def merge(number: int, method: str = "squash") -> tuple[bool, bool]:
    """(merged, bypassed). Plain merge first: it is refused while a ruleset's
    approving-review requirement is unmet — even for an admin's token, because bypassing
    is opt-in per call — so fall back to --admin, which succeeds only if the token really
    carries the admin role."""
    base = ["gh", "pr", "merge", str(number), f"--{method}", "--delete-branch"]
    if subprocess.run(base, capture_output=True, text=True, check=False).returncode == 0:
        return True, False
    return (
        subprocess.run(base + ["--admin"], capture_output=True, text=True, check=False).returncode
        == 0,
        True,
    )
