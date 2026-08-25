# Made with ❤️ by [Vibey](https://adammatthewsteinberger.github.io/vibey/), Developed by [Adam Matthew Steinberger](https://hire.adam.matthewsteinberger.com/) ([@adammatthewsteinberger](https://github.com/adammatthewsteinberger/)).
"""Reconcile open topic branches after the integration branch is rewritten.

Realign converges the integration branch onto the release branch with a lease-protected
force update, because a rebase-merged release branch holds rewritten copies of the same
commits. That is correct and deliberate — but it strands every topic branch that was cut
from a commit the rewrite replaced. Such a branch still carries the old copy, so Git sees
the same change on two divergent lines and reports a conflict for work that is already
upstream. Nothing about that conflict is real, and no contributor caused it.

This module decides what to do about each stranded branch, and the decision turns on one
question: does the branch carry anything that is not already upstream? `git cherry`
answers it by patch identity rather than by SHA, which is exactly the distinction the
rewrite destroys.

* **Nothing unique** — the branch is now a pure duplicate of history that already landed.
  Its pull request is closed with an explanation and the branch is deleted.
* **Unique work, automation-owned** — rebased onto the new tip. Rebase drops the
  patch-identical commits on its own, leaving only the real work.
* **Unique work, anyone else's** — left exactly as it is. A human's in-progress branch is
  not this automation's to rewrite; it gets a comment explaining what happened instead.

A fork branch is never touched in any case, and no permanent branch can reach a mutating
path: `deletable` and `rebasable` both refuse them by name.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any

from vibey_gh import github_state
from vibey_gh.config import GhConfig

REBASE = "rebase"
CLOSE = "close"
LEAVE = "leave"


@dataclass(frozen=True)
class BranchFacts:
    """What the decision needs to know about one open pull request."""

    number: int
    branch: str
    fork: bool = False
    unique_commits: int = 0


@dataclass(frozen=True)
class Decision:
    number: int
    branch: str
    action: str
    reason: str
    delete_branch: bool = False
    notify: bool = False

    def describe(self) -> str:
        suffix = " and deleted its branch" if self.delete_branch else ""
        return f"#{self.number} ({self.branch}): {self.action}{suffix} — {self.reason}"


def permanent_branches(cfg: GhConfig) -> set[str]:
    """Configured names plus the literal defaults, denied independently as defence."""
    return {cfg.integration_branch, cfg.release_branch, "develop", "main"}


def _unsafe(branch: str) -> bool:
    return not branch or branch.startswith("-") or ":" in branch or ".." in branch


def deletable(branch: str, cfg: GhConfig, *, fork: bool = False) -> bool:
    """Whether this ref may ever be deleted. Permanent branches never qualify."""
    return not (_unsafe(branch) or fork or branch in permanent_branches(cfg))


def rebasable(branch: str, cfg: GhConfig, *, fork: bool = False) -> bool:
    """Whether this ref may ever be force-updated by reconciliation."""
    return deletable(branch, cfg, fork=fork)


def automation_owned(branch: str, cfg: GhConfig) -> bool:
    return any(branch.startswith(prefix) for prefix in cfg.realign.automation_prefixes)


def decide(facts: BranchFacts, cfg: GhConfig) -> Decision:
    """Classify one open pull request without touching GitHub or Git."""
    policy = cfg.realign

    def result(
        action: str, reason: str, delete_branch: bool = False, notify: bool = False
    ) -> Decision:
        return Decision(facts.number, facts.branch, action, reason, delete_branch, notify)

    if not policy.reconcile_branches:
        return result(LEAVE, "branch reconciliation is disabled")
    if facts.fork:
        return result(LEAVE, "a fork branch is never mutated by this repository")
    if facts.branch in permanent_branches(cfg) or _unsafe(facts.branch):
        return result(LEAVE, "permanent and unsafe refs are never reconciled")
    if facts.unique_commits == 0:
        if not policy.close_duplicates:
            return result(LEAVE, "closing duplicate pull requests is disabled")
        return result(
            CLOSE,
            "every commit is already upstream by patch identity, so nothing would be merged",
            delete_branch=policy.delete_duplicate_branches
            and deletable(facts.branch, cfg, fork=facts.fork),
        )
    if not automation_owned(facts.branch, cfg):
        return result(
            LEAVE,
            "a contributor's branch with unique work is left for its author",
            notify=policy.notify_contributor_branches,
        )
    return result(REBASE, f"{facts.unique_commits} unique commit(s) replayed onto the new tip")


def _git(cfg: GhConfig, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cfg.root, capture_output=True, text=True, check=False)


def unique_commits(cfg: GhConfig, branch: str) -> int:
    """Commits on `branch` whose patch is not already on the integration branch.

    `git cherry` compares by patch id, so a commit that the rewrite re-created upstream
    under a new SHA is correctly recognised as already present.
    """
    run = _git(cfg, "cherry", f"origin/{cfg.integration_branch}", f"origin/{branch}")
    if run.returncode:
        # An unreadable ref is not a licence to guess; report work so it is left alone.
        return 1
    return sum(1 for line in run.stdout.splitlines() if line.startswith("+"))


def open_pull_requests(cfg: GhConfig) -> list[BranchFacts]:
    payload = github_state.gh_json(
        "pr",
        "list",
        "--repo",
        github_state.repository(),
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        "number,headRefName,isCrossRepository",
    )
    facts = []
    for item in payload or []:
        branch = str(item.get("headRefName") or "")
        fork = bool(item.get("isCrossRepository"))
        facts.append(
            BranchFacts(
                number=int(item["number"]),
                branch=branch,
                fork=fork,
                unique_commits=0 if not fork and not _unsafe(branch) else 1,
            )
        )
    return facts


def measure(cfg: GhConfig, facts: BranchFacts) -> BranchFacts:
    """Fill in the patch-identity count for a branch worth measuring."""
    if facts.fork or _unsafe(facts.branch) or facts.branch in permanent_branches(cfg):
        return facts
    return BranchFacts(
        number=facts.number,
        branch=facts.branch,
        fork=facts.fork,
        unique_commits=unique_commits(cfg, facts.branch),
    )


def rebase_branch(cfg: GhConfig, branch: str) -> tuple[bool, str]:
    """Replay a branch onto the current integration tip, dropping duplicated commits."""
    if not rebasable(branch, cfg):
        raise ValueError(f"refusing to rebase protected or unsafe branch {branch!r}")
    _git(cfg, "fetch", "--quiet", "origin", cfg.integration_branch, branch)
    before = _git(cfg, "rev-parse", f"origin/{branch}").stdout.strip()
    if not before:
        return False, "branch no longer exists"
    if _git(cfg, "checkout", "--quiet", "--detach", before).returncode:
        return False, "could not check the branch out"
    if _git(cfg, "rebase", f"origin/{cfg.integration_branch}").returncode:
        _git(cfg, "rebase", "--abort")
        return False, "rebase conflicted; left for ordinary conflict resolution"
    after = _git(cfg, "rev-parse", "HEAD").stdout.strip()
    if after == before:
        return False, "already on the current tip"
    push = _git(
        cfg,
        "push",
        f"--force-with-lease=refs/heads/{branch}:{before}",
        "origin",
        f"HEAD:refs/heads/{branch}",
    )
    if push.returncode:
        return False, f"push refused: {push.stderr.strip()}"
    return True, f"rebased {before[:7]} onto the new tip as {after[:7]}"


def close_pull_request(cfg: GhConfig, decision: Decision) -> None:
    repository = github_state.repository()
    body = (
        "Closing automatically: every commit on this branch is already on "
        f"`{cfg.integration_branch}` by patch identity.\n\n"
        "The integration branch was realigned onto the release branch, which replaces "
        "commits with rewritten copies carrying new SHAs. This branch still held the old "
        "copies, so Git reported a conflict for work that had in fact already landed. "
        "Nothing here would be merged, and nothing is lost by closing it."
    )
    subprocess.run(
        ["gh", "pr", "comment", str(decision.number), "--repo", repository, "--body", body],
        cwd=cfg.root,
        capture_output=True,
        check=False,
    )
    subprocess.run(
        ["gh", "pr", "close", str(decision.number), "--repo", repository],
        cwd=cfg.root,
        capture_output=True,
        check=False,
    )


def notify(cfg: GhConfig, decision: Decision) -> None:
    """Tell a contributor why their branch suddenly conflicts, without touching it."""
    subprocess.run(
        [
            "gh",
            "pr",
            "comment",
            str(decision.number),
            "--repo",
            github_state.repository(),
            "--body",
            (
                f"`{cfg.integration_branch}` was realigned onto `{cfg.release_branch}`, "
                "which replaced its commits with rewritten copies. If this branch now "
                "reports a conflict covering changes it did not make, rebase it onto the "
                "new tip:\n\n```bash\ngit fetch origin\n"
                f"git rebase origin/{cfg.integration_branch}\n```\n\n"
                "Automation left the branch untouched because it carries your own work."
            ),
        ],
        cwd=cfg.root,
        capture_output=True,
        check=False,
    )


def delete_branch(cfg: GhConfig, branch: str, *, fork: bool = False) -> bool:
    """Delete one topic branch. Refuses every permanent, fork, or unsafe ref by name."""
    if not deletable(branch, cfg, fork=fork):
        raise ValueError(f"refusing to delete protected or unsafe branch {branch!r}")
    run = subprocess.run(
        [
            "gh",
            "api",
            f"repos/{github_state.repository()}/git/refs/heads/{branch}",
            "--method",
            "DELETE",
        ],
        cwd=cfg.root,
        capture_output=True,
        check=False,
    )
    return run.returncode == 0


def reconcile(cfg: GhConfig, *, dry_run: bool = False) -> list[dict[str, Any]]:
    """Decide and, unless `dry_run`, apply an action for every open pull request."""
    outcomes: list[dict[str, Any]] = []
    if not cfg.realign.reconcile_branches:
        return outcomes
    for raw in open_pull_requests(cfg):
        decision = decide(measure(cfg, raw), cfg)
        outcome: dict[str, Any] = {
            "pr": decision.number,
            "branch": decision.branch,
            "action": decision.action,
            "reason": decision.reason,
            "delete_branch": decision.delete_branch,
        }
        if not dry_run:
            if decision.action == REBASE:
                changed, detail = rebase_branch(cfg, decision.branch)
                outcome["applied"] = changed
                outcome["detail"] = detail
            elif decision.action == CLOSE:
                close_pull_request(cfg, decision)
                outcome["applied"] = True
                if decision.delete_branch:
                    outcome["deleted"] = delete_branch(cfg, decision.branch)
            elif decision.notify:
                notify(cfg, decision)
                outcome["notified"] = True
        outcomes.append(outcome)
    return outcomes
