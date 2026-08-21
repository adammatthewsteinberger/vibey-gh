# Made with love by Vibey, the auto-vibecoding machine by Adam Matthew Steinberger.
"""Install the git hooks that enforce the automation into a consuming repository.

Installing is deliberately additive. A repository that already has its own `pre-push` or
`commit-msg` keeps it: the existing hook is moved aside to `<name>.local` and the
installed hook chains to it. Adopting this should never silently discard checks somebody
else thought were important.
"""

from __future__ import annotations

import shutil
import stat
from dataclasses import dataclass
from pathlib import Path

from vibey_gh.config import GhConfig, load_config

TEMPLATES = Path(__file__).parent / "templates" / "githooks"
WORKFLOWS = Path(__file__).parent / "templates" / "workflows"
WORKFLOWS_DIR = ".github/workflows"
HOOKS = ("commit-msg", "pre-push")
HOOKS_DIR = ".githooks"


@dataclass
class Action:
    hook: str
    outcome: str  # installed | updated | unchanged | chained


def _executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def install(cfg: GhConfig | None = None, hooks_path: bool = True) -> list[Action]:
    cfg = cfg or load_config()
    target = cfg.root / HOOKS_DIR
    target.mkdir(parents=True, exist_ok=True)
    actions: list[Action] = []

    for hook in HOOKS:
        source = TEMPLATES / hook
        dest = target / hook
        wanted = source.read_text(encoding="utf-8")

        if dest.exists():
            existing = dest.read_text(encoding="utf-8")
            if existing == wanted:
                actions.append(Action(hook, "unchanged"))
                continue
            # Someone else's hook: preserve it and chain rather than overwrite.
            if "vibey-gh" not in existing:
                local = target / f"{hook}.local"
                if not local.exists():
                    shutil.move(str(dest), str(local))
                    _executable(local)
                    actions.append(Action(hook, "chained"))
                dest.write_text(wanted, encoding="utf-8")
                _executable(dest)
                continue
            dest.write_text(wanted, encoding="utf-8")
            _executable(dest)
            actions.append(Action(hook, "updated"))
            continue

        dest.write_text(wanted, encoding="utf-8")
        _executable(dest)
        actions.append(Action(hook, "installed"))

    # Workflows are copied, not chained: a workflow file is standalone and a stale copy
    # is worse than none, so an out-of-date one is replaced outright.
    wf_target = cfg.root / WORKFLOWS_DIR
    wf_target.mkdir(parents=True, exist_ok=True)
    for source in sorted(WORKFLOWS.glob("*.yml")):
        dest = wf_target / source.name
        wanted = source.read_text(encoding="utf-8")
        if dest.exists() and dest.read_text(encoding="utf-8") == wanted:
            actions.append(Action(f"{WORKFLOWS_DIR}/{source.name}", "unchanged"))
            continue
        outcome = "updated" if dest.exists() else "installed"
        dest.write_text(wanted, encoding="utf-8")
        actions.append(Action(f"{WORKFLOWS_DIR}/{source.name}", outcome))

    if hooks_path:
        import subprocess

        subprocess.run(
            ["git", "config", "core.hooksPath", HOOKS_DIR],
            cwd=cfg.root,
            check=False,
            capture_output=True,
        )
    return actions


def installed(cfg: GhConfig | None = None, local: bool = True) -> tuple[bool, list[str]]:
    """Whether the hooks are present, current, and — when `local` — actually wired up.

    The two halves are deliberately separable. Whether the hook FILES are committed and
    current is repository state, and CI can and should check it. Whether `core.hooksPath`
    points at them is per-clone local git config that no CI checkout will ever have, so
    asserting it on a runner would fail every build for a condition that cannot hold there.
    """
    cfg = cfg or load_config()
    problems: list[str] = []
    target = cfg.root / HOOKS_DIR

    for hook in HOOKS:
        dest = target / hook
        if not dest.exists():
            problems.append(f"{HOOKS_DIR}/{hook} is missing")
        elif dest.read_text(encoding="utf-8") != (TEMPLATES / hook).read_text(encoding="utf-8"):
            problems.append(f"{HOOKS_DIR}/{hook} is out of date")

    for source in sorted(WORKFLOWS.glob("*.yml")):
        dest = cfg.root / WORKFLOWS_DIR / source.name
        if not dest.exists():
            problems.append(f"{WORKFLOWS_DIR}/{source.name} is missing")
        elif dest.read_text(encoding="utf-8") != source.read_text(encoding="utf-8"):
            problems.append(f"{WORKFLOWS_DIR}/{source.name} is out of date")

    if local:
        import subprocess

        result = subprocess.run(
            ["git", "config", "--get", "core.hooksPath"],
            cwd=cfg.root,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip() != HOOKS_DIR:
            problems.append(f"core.hooksPath is not {HOOKS_DIR} — run `vibey-gh install`")

    return (not problems), problems
